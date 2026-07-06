#!/usr/bin/env python3
"""
STRAT-011 "Shifted CCI Momentum Aligner" — HONEST evaluation stack (v2).

Fixes vs strat011_wf.py (every one of these INFLATED the old numbers):
  1. COSTS: spread charged in INDEX POINTS (mission floor 3.0). Old code used
     CFG.spread_pts * inferred_point(0.01) = 0.03 pts -> frictionless.
  2. FILLS: entry at the NEXT M5 bar's open. Old code filled at the CLOSED
     bar's open, a 5-minute-stale price (favorable look-ahead for momentum).
  3. DAY SCORING: every calendar day is an independent trial from a fixed
     100k base (the FTMO day metric: +2.5% of initial, 4% trailing DD).
     Old code compounded balance across days inside folds while scoring the
     target vs initial -> late-fold days passed mechanically.
  4. RISK: base risk capped at 1.0% per trade (rule R-1). Old best used 2%.
Additions:
  - Path-accurate intraday equity: bar-by-bar floating DD, DD checked before
    target inside each bar (conservative down-first ordering), trailing-DD
    halt implemented as a synthetic exit level with gap handling.
  - EOD flat (no overnight), session filter, composable gates
    (H1/M5 energy, M15 dual-TF, F-2 census, SY-1 CCI-trinity unanimity).
  - Consistency metrics: coverage, all-days pass rate, PASS streaks,
    worst rolling 30-market-day pass rate.
Slippage assumption: 0 beyond the 3-pt spread (next-bar-open fills).
"""
import argparse, itertools, json, sys, time
import numpy as np
import pandas as pd
import joblib
import us30_rf_bot as bot

INIT = 100000.0

P_DEFAULT = dict(cci_htf=140, sh_htf=4, cen_n=12, cen_k=10)


def load_m1_full(path):
    """Like bot.load_m1 but keeps tick volume and spread (raw broker units)."""
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.strip("<>").strip().lower() for c in df.columns]
    idx = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    out = pd.DataFrame({
        "open": pd.to_numeric(df["open"], errors="coerce").values,
        "high": pd.to_numeric(df["high"], errors="coerce").values,
        "low": pd.to_numeric(df["low"], errors="coerce").values,
        "close": pd.to_numeric(df["close"], errors="coerce").values,
        "tickvol": pd.to_numeric(df.get("tickvol", 1), errors="coerce").values,
        "spread_raw": pd.to_numeric(df.get("spread", 0), errors="coerce").values,
    }, index=pd.DatetimeIndex(np.asarray(idx)))
    out = out.dropna(subset=["open", "high", "low", "close"]).sort_index()
    return out[~out.index.duplicated(keep="last")]


NY_OPEN_MIN = 990    # 16:30 broker time
OR_END_MIN = 1020    # 17:00 — opening range = 16:30-17:00


# ---------------------------------------------------------------- features
def build(csv, P=P_DEFAULT):
    m1 = load_m1_full(csv)
    m5 = bot.resample(m1, "5min"); m15 = bot.resample(m1, "15min"); h1 = bot.resample(m1, "1h")
    sma = lambda s, n: s.rolling(n, min_periods=n).mean()
    cci = lambda df, n: bot.cci(df["high"], df["low"], df["close"], n)

    # --- LICENSE: H1 CCI(140) persistence (P-1) ---
    hc = cci(h1, P["cci_htf"]); hb = sma(hc, 1).shift(P["sh_htf"])
    persB = (hc > 0) & (hc > hb); persBe = (hc < 0) & (hc < hb)
    # --- ENERGY GATES (STRAT-006): per-TF ADX/ATR vs own shifted baseline + ADX>20 floor ---
    def energy(df):
        a = bot.adx(df["high"], df["low"], df["close"], 14)
        t = bot.atr(df["high"], df["low"], df["close"], 14)
        return (a > sma(a, 1).shift(5)) & (t > sma(t, 1).shift(5)) & (a > 20)
    h1e = energy(h1); m5e = energy(m5)
    # --- F-1 dual-TF gravity leg on M15 (SMA(4) shift 8 on highs/lows) ---
    sh15 = sma(m15["high"], 4).shift(8); sl15 = sma(m15["low"], 4).shift(8)
    m15bull = (m15["close"] > sh15) & (m15["close"] > sl15)
    m15bear = (m15["close"] < sh15) & (m15["close"] < sl15)
    # --- F-2 census on M15: K of last N closes one side of SMA(4).shift(8) on close ---
    ref15 = sma(m15["close"], 4).shift(8)
    ab = (m15["close"] > ref15).rolling(P["cen_n"]).sum()
    be = (m15["close"] < ref15).rolling(P["cen_n"]).sum()
    cenB = ab >= P["cen_k"]; cenBe = be >= P["cen_k"]
    # --- SY-1 CCI trinity unanimity on M5 (14/100/900, own SMA(20), T=+/-100) ---
    c14 = cci(m5, 14); c100 = cci(m5, 100); c900 = cci(m5, 900)
    uniB = ((c14 > 100) & (c14 > sma(c14, 20)) & (c100 > 100) & (c100 > sma(c100, 20))
            & (c900 > 100) & (c900 > sma(c900, 20)))
    uniBe = ((c14 < -100) & (c14 < sma(c14, 20)) & (c100 < -100) & (c100 < sma(c100, 20))
             & (c900 < -100) & (c900 < sma(c900, 20)))
    # --- ENTRY TRIGGER: fresh M5 CCI(14) zero-cross (U-1 event) ---
    xup = (c14 > 0) & (c14.shift(1) <= 0); xdn = (c14 < 0) & (c14.shift(1) >= 0)
    # --- E-1 pullback trigger: retrace touch of fast gravity line (M5 SMA(20)) ---
    g20 = sma(m5["close"], 20)
    tchB = (m5["low"] <= g20) & (m5["close"] > g20)
    tchS = (m5["high"] >= g20) & (m5["close"] < g20)
    # --- session-anchored structure (new branch family) ---
    d1 = m1.index.normalize()
    mint1 = m1.index.hour * 60 + m1.index.minute
    tp = (m1["high"] + m1["low"] + m1["close"]) / 3
    tv = m1["tickvol"].clip(lower=1)
    vwap = (tp * tv).groupby(d1).cumsum() / tv.groupby(d1).cumsum()   # day-anchored VWAP
    inOR = pd.Series((mint1 >= NY_OPEN_MIN) & (mint1 < OR_END_MIN), index=m1.index)
    orh = m1["high"].where(inOR).groupby(d1).cummax().groupby(d1).ffill()
    orl = m1["low"].where(inOR).groupby(d1).cummin().groupby(d1).ffill()
    orDone = pd.Series(mint1 >= OR_END_MIN, index=m1.index) & orh.notna() & orl.notna()
    or_open = m1["open"].where(inOR).groupby(d1).transform("first")
    or_close = m1["close"].where(inOR).groupby(d1).transform("last")
    drive = or_close - or_open        # leaky before 17:00 by construction -> ALWAYS gate by orDone
    daily = m1.groupby(d1).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    pdh = pd.Series(daily["h"].shift(1).reindex(d1).values, index=m1.index)
    pdl = pd.Series(daily["l"].shift(1).reindex(d1).values, index=m1.index)
    pdc = pd.Series(daily["c"].shift(1).reindex(d1).values, index=m1.index)
    sp1 = m1["spread_raw"] * 0.01     # MT5 raw spread -> index points (2-decimal quotes, point=0.01)
    r5 = lambda s: s.resample("5min", label="left", closed="left").last()
    # --- M15 trigger family: CCI(14) zero-cross on M15, with M15 ATR stop ---
    c14_15 = cci(m15, 14)
    x15up = (c14_15 > 0) & (c14_15.shift(1) <= 0); x15dn = (c14_15 < 0) & (c14_15.shift(1) >= 0)
    atr15 = bot.atr(m15["high"], m15["low"], m15["close"], 14)

    dec = m5.index + pd.Timedelta(minutes=5)   # decision = M5 bar close time
    def al(x, tf):
        y = x.copy(); y.index = y.index + pd.Timedelta(minutes=tf)
        return y.reindex(dec, method="ffill")
    fb = lambda s, tf: al(s, tf).fillna(False).astype(bool).values
    out = pd.DataFrame({
        "open":  al(m5["open"], 5).values,   # OHLC of the bar that CLOSED at dec
        "high":  al(m5["high"], 5).values,
        "low":   al(m5["low"], 5).values,
        "close": al(m5["close"], 5).values,
        "ofill": al(m5["open"].shift(-1), 5).values,   # open of bar STARTING at dec = fill
        "atr":   al(bot.atr(m5["high"], m5["low"], m5["close"], 14), 5).values,
        "cci":   al(c14, 5).values,
        "persB": fb(persB, 60), "persBe": fb(persBe, 60),
        "h1e": fb(h1e, 60), "m5e": fb(m5e, 5),
        "m15bull": fb(m15bull, 15), "m15bear": fb(m15bear, 15),
        "cenB": fb(cenB, 15), "cenBe": fb(cenBe, 15),
        "uniB": fb(uniB, 5), "uniBe": fb(uniBe, 5),
        "tchB": fb(tchB, 5), "tchS": fb(tchS, 5),
        "x15up": fb(x15up, 15), "x15dn": fb(x15dn, 15),
        "atr15": al(atr15, 15).values,
        "sp": al(r5(sp1), 5).values,
        "vwap": al(r5(vwap), 5).values,
        "orh": al(r5(orh), 5).values, "orl": al(r5(orl), 5).values,
        "orDone": fb(r5(orDone.astype(float)) > 0, 5),
        "drive": al(r5(drive), 5).values,
        "pdh": al(r5(pdh), 5).values, "pdl": al(r5(pdl), 5).values, "pdc": al(r5(pdc), 5).values,
    }, index=dec)
    out = out.dropna(subset=["close", "atr", "ofill"])
    return out


# ---------------------------------------------------------------- harness
BASE = dict(risk_pct=1.0, rr=2.5, spread="data", target=2.5, ddh=3.5, ddf=4.0,
            adapt=False, guard=True, eod=True, recross=False, lic_exit=False,
            energy="h1", require15=False, census=False, uni=False,
            session=None, min_sd=0.0, sl_mult=1.0, trigger="cci",
            license="h1", drv_k=0.5)


def harness(df, cfg, collect_days=False):
    """Each calendar day = independent trial from INIT. Returns aggregates."""
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    ofill = df["ofill"].values; atr = df["atr"].values; cciv = df["cci"].values
    persB = df["persB"].values; persBe = df["persBe"].values
    h1e = df["h1e"].values; m5e = df["m5e"].values
    m15b = df["m15bull"].values; m15be = df["m15bear"].values
    cenB = df["cenB"].values; cenBe = df["cenBe"].values
    uniB = df["uniB"].values; uniBe = df["uniBe"].values
    idx = df.index
    dates = idx.normalize().values
    minute = (idx.hour * 60 + idx.minute).values
    N = len(df)
    lastbar = np.empty(N, dtype=bool); lastbar[:-1] = dates[:-1] != dates[1:]; lastbar[-1] = True

    e = cfg["energy"]
    if e == "h1":     enB = h1e; enS = h1e
    elif e == "m5":   enB = m5e; enS = m5e
    elif e == "both": enB = h1e & m5e; enS = h1e & m5e
    elif e == "none": enB = np.ones(len(df), bool); enS = enB
    else:             enB = h1e | m5e; enS = h1e | m5e
    ones = np.ones(N, bool)
    hb = persB if cfg["license"] == "h1" else ones
    hs = persBe if cfg["license"] == "h1" else ones
    licB = hb & enB; licS = hs & enS
    if cfg["require15"]: licB = licB & m15b; licS = licS & m15be
    if cfg["census"]:    licB = licB & cenB; licS = licS & cenBe
    if cfg["uni"]:       licB = licB & uniB; licS = licS & uniBe
    side = cfg.get("side", "both")
    if side == "long":  licS = np.zeros(N, bool)
    elif side == "short": licB = np.zeros(N, bool)
    trig = cfg["trigger"]
    if trig == "cci":
        xup = np.empty(N, dtype=bool); xdn = np.empty(N, dtype=bool)
        xup[0] = False; xdn[0] = False
        xup[1:] = (cciv[1:] > 0) & (cciv[:-1] <= 0)
        xdn[1:] = (cciv[1:] < 0) & (cciv[:-1] >= 0)
        sd_arr = df["atr"].values
    elif trig == "pullback":
        xup = df["tchB"].values; xdn = df["tchS"].values
        sd_arr = df["atr"].values
    elif trig == "m15":
        xup = df["x15up"].values; xdn = df["x15dn"].values
        sd_arr = df["atr15"].values
    elif trig == "orb":
        # NY opening-range breakout: fresh M5 close beyond the 16:30-17:00 range
        od = df["orDone"].values; c_ = df["close"].values
        orh_ = df["orh"].values; orl_ = df["orl"].values
        upst = od & (c_ > orh_); dnst = od & (c_ < orl_)
        xup = np.zeros(N, bool); xdn = np.zeros(N, bool)
        xup[1:] = upst[1:] & ~upst[:-1]; xdn[1:] = dnst[1:] & ~dnst[:-1]
        licB = licB & od; licS = licS & od
        sd_arr = df["atr"].values
    elif trig == "vwap":
        # VWAP-trend pullback: bull = above VWAP and above OR-high; buy the VWAP touch
        od = df["orDone"].values; c_ = df["close"].values
        v = df["vwap"].values; orh_ = df["orh"].values; orl_ = df["orl"].values
        l_ = df["low"].values; h_ = df["high"].values
        licB = licB & od & (c_ > v) & (c_ > orh_)
        licS = licS & od & (c_ < v) & (c_ < orl_)
        xup = (l_ <= v) & (c_ > v); xdn = (h_ >= v) & (c_ < v)
        sd_arr = df["atr"].values
    elif trig == "drive":
        # open-drive continuation: OR net move > k*ATR15 sets the day's direction;
        # every fresh M5 CCI(14) cross in that direction is an entry until EOD
        od = df["orDone"].values; drv = df["drive"].values; a15 = df["atr15"].values
        drvUp = od & (drv > cfg["drv_k"] * a15); drvDn = od & (drv < -cfg["drv_k"] * a15)
        xup = np.zeros(N, bool); xdn = np.zeros(N, bool)
        xup[1:] = (cciv[1:] > 0) & (cciv[:-1] <= 0)
        xdn[1:] = (cciv[1:] < 0) & (cciv[:-1] >= 0)
        licB = licB & drvUp; licS = licS & drvDn
        sd_arr = df["atr"].values
    else:  # 'either' = cci OR pullback
        xup = np.empty(N, dtype=bool); xdn = np.empty(N, dtype=bool)
        xup[0] = False; xdn[0] = False
        xup[1:] = (cciv[1:] > 0) & (cciv[:-1] <= 0)
        xdn[1:] = (cciv[1:] < 0) & (cciv[:-1] >= 0)
        xup = xup | df["tchB"].values; xdn = xdn | df["tchS"].values
        sd_arr = df["atr"].values

    ses = cfg["session"]
    risk = min(cfg["risk_pct"], 1.0)   # R-1 hard cap
    spc = cfg["spread"]
    spv = df["sp"].values.copy() if spc == "data" else np.full(N, float(spc))
    spv[~np.isfinite(spv)] = 1.5
    rr = cfg["rr"]; tgt_pct = cfg["target"]
    ddh = cfg["ddh"]; ddf = cfg["ddf"]
    adapt = cfg["adapt"]; guard = cfg["guard"]; eod = cfg["eod"]
    recross = cfg["recross"]; lic_exit = cfg["lic_exit"]; min_sd = cfg["min_sd"]
    lock_eq = INIT * (1 + tgt_pct / 100.0)

    day_rows = []          # (date, ret%, dd%, trades, wins, ntrig)
    closed = INIT; peak = INIT; ddmax = 0.0; trades = 0; wins = 0; ntrig = 0
    halted = False
    pos = None             # (side, entry, sd, size, start_i)
    cur = dates[0]
    tot_R = 0.0

    def day_flush(d):
        day_rows.append((d, (closed - INIT) / INIT * 100.0, ddmax, trades, wins, ntrig))

    i = 0
    while i < N:
        if dates[i] != cur:
            day_flush(cur)
            cur = dates[i]; closed = INIT; peak = INIT; ddmax = 0.0
            trades = 0; wins = 0; ntrig = 0; halted = False; pos = None
        # ---------- open-position management on bar i ----------
        if pos is not None and i >= pos[4]:
            side, entry, sd, size, _ = pos
            sp = spv[i]
            halt_eq = peak * (1 - ddh / 100.0)
            exit_px = None; kind = None
            if side > 0:
                p_stop = entry - sd
                p_halt = entry + (halt_eq - closed) / size
                p_dn = max(p_stop, p_halt)
                p_tgt = entry + rr * sd
                p_lock = entry + (lock_eq - closed) / size
                p_up = min(p_tgt, p_lock)
                if o[i] <= p_dn:   exit_px, kind = o[i], ("halt" if p_halt > p_stop else "stop")
                elif l[i] <= p_dn:
                    exit_px, kind = p_dn, ("halt" if p_halt > p_stop else "stop")
                    peak = max(peak, closed + (min(h[i], p_up) - entry) * size)  # high-first worst case
                elif o[i] >= p_up: exit_px, kind = o[i], ("lock" if p_lock < p_tgt else "tgt")
                elif h[i] >= p_up:
                    exit_px, kind = p_up, ("lock" if p_lock < p_tgt else "tgt")
                    ddmax = max(ddmax, (peak - (closed + (l[i] - entry) * size)) / peak * 100.0)  # dip-first
                if exit_px is None:
                    eq_hi = closed + (h[i] - entry) * size
                    eq_lo = closed + (l[i] - entry) * size
                    peak = max(peak, eq_hi)
                    ddmax = max(ddmax, (peak - eq_lo) / peak * 100.0)
                    if recross and i > 0 and cciv[i] < 0 and cciv[i - 1] >= 0:
                        exit_px, kind = c[i], "recross"
                    elif lic_exit and not licB[i]:
                        exit_px, kind = c[i], "lic"
                    elif eod and lastbar[i]:
                        exit_px, kind = c[i], "eod"
                if exit_px is not None:
                    pnl = (exit_px - entry) * size
            else:
                p_stop = entry + sd - sp            # raw-bid trigger levels (exits at ask)
                p_halt = entry - sp - (halt_eq - closed) / size
                p_dn = min(p_stop, p_halt)          # adverse = UP for shorts
                p_tgt = entry - rr * sd - sp
                p_lock = entry - sp - (lock_eq - closed) / size
                p_up = max(p_tgt, p_lock)
                if o[i] >= p_dn:   exit_px, kind = o[i], ("halt" if p_halt < p_stop else "stop")
                elif h[i] >= p_dn:
                    exit_px, kind = p_dn, ("halt" if p_halt < p_stop else "stop")
                    peak = max(peak, closed + (entry - (max(l[i], p_up) + sp)) * size)
                elif o[i] <= p_up: exit_px, kind = o[i], ("lock" if p_lock > p_tgt else "tgt")
                elif l[i] <= p_up:
                    exit_px, kind = p_up, ("lock" if p_lock > p_tgt else "tgt")
                    ddmax = max(ddmax, (peak - (closed + (entry - (h[i] + sp)) * size)) / peak * 100.0)
                if exit_px is None:
                    eq_hi = closed + (entry - (l[i] + sp)) * size
                    eq_lo = closed + (entry - (h[i] + sp)) * size
                    peak = max(peak, eq_hi)
                    ddmax = max(ddmax, (peak - eq_lo) / peak * 100.0)
                    if recross and i > 0 and cciv[i] > 0 and cciv[i - 1] <= 0:
                        exit_px, kind = c[i], "recross"
                    elif lic_exit and not licS[i]:
                        exit_px, kind = c[i], "lic"
                    elif eod and lastbar[i]:
                        exit_px, kind = c[i], "eod"
                if exit_px is not None:
                    pnl = (entry - (exit_px + sp)) * size
            if exit_px is not None:
                closed += pnl
                trades += 1; wins += pnl > 0; tot_R += pnl / (sd * size)
                peak = max(peak, closed)
                ddmax = max(ddmax, (peak - closed) / peak * 100.0)
                pos = None
                if kind == "halt" or (peak - closed) / peak * 100.0 >= ddh:
                    halted = True
                if (closed - INIT) / INIT * 100.0 >= tgt_pct:
                    halted = True   # day won -> stop (lock)
        # ---------- entry decision on bar i ----------
        if (pos is None and not halted and not lastbar[i]
                and (i + 1 < N and dates[i + 1] == dates[i])):
            trigL = licB[i] and xup[i]; trigS = licS[i] and xdn[i]
            if (trigL or trigS) and (ses is None or (ses[0] <= minute[i] < ses[1])):
                sd = sd_arr[i] * cfg["sl_mult"]
                if np.isfinite(sd) and sd > max(min_sd, 1e-9) and np.isfinite(ofill[i]):
                    ntrig += 1
                    curDD = (peak - closed) / peak * 100.0
                    r_eff = max(risk * (1 - curDD / ddh), risk * 0.3) if adapt else risk
                    ra = closed * r_eff / 100.0
                    worst = (peak - (closed - ra)) / peak * 100.0
                    if not (guard and worst >= ddh):
                        size = ra / sd
                        entry = ofill[i] + spv[i] if trigL else ofill[i]
                        pos = (1 if trigL else -1, entry, sd, size, i + 1)
        i += 1
    day_flush(cur)

    # ---------------- day outcomes & consistency metrics ----------------
    outc = []   # 'P' pass, 'M' miss, 'B' breach, 'N' no-trade
    for d, ret, dd, tr, w, nt in day_rows:
        if dd >= ddf:        outc.append("B")
        elif tr == 0:        outc.append("N")
        elif ret >= tgt_pct: outc.append("P")
        else:                outc.append("M")
    n_all = len(day_rows)
    traded = [k for k, s in enumerate(outc) if s != "N"]
    n_tr = len(traded)
    n_pass = outc.count("P"); n_breach = outc.count("B")
    # streaks over traded days
    best_streak = s = 0
    for k in traded:
        s = s + 1 if outc[k] == "P" else 0
        best_streak = max(best_streak, s)
    # worst rolling 30 market days (all-days denominator)
    pa = np.array([1.0 if x == "P" else 0.0 for x in outc])
    worst30 = float(np.min(np.convolve(pa, np.ones(30) / 30, "valid")) * 100) if n_all >= 30 else float("nan")
    ttrades = sum(r[3] for r in day_rows); twins = sum(r[4] for r in day_rows)
    res = dict(days_all=n_all, days_traded=n_tr, pass_days=n_pass, breach=n_breach,
               pass_traded=100.0 * n_pass / max(1, n_tr),
               pass_all=100.0 * n_pass / max(1, n_all),
               coverage=100.0 * n_tr / max(1, n_all),
               best_streak=best_streak, worst30=worst30,
               trades=ttrades, win=100.0 * twins / max(1, ttrades),
               avgR=tot_R / max(1, ttrades),
               trig_day=sum(r[5] for r in day_rows) / max(1, n_tr))
    if collect_days:
        res["day_rows"] = [(str(pd.Timestamp(d).date()), r, dd, t) for d, r, dd, t, w, n in day_rows]
        res["outcomes"] = outc
    return res


def split_eval(df, cfg):
    """Half-split stability check inside a tuning slice (both halves are DEV)."""
    dts = df.index.normalize(); u = dts.unique()
    half = u[len(u) // 2]
    a = harness(df[dts < half], cfg); b = harness(df[dts >= half], cfg)
    return a, b


def fmt(tag, r):
    return (f"{tag} pass(traded) {r['pass_traded']:5.1f}% ({r['pass_days']}/{r['days_traded']}) "
            f"| pass(all) {r['pass_all']:5.1f}% cov {r['coverage']:4.1f}% | brch {r['breach']} "
            f"| streak {r['best_streak']} worst30 {r['worst30']:4.1f}% "
            f"| tr {r['trades']} win {r['win']:4.1f}% avgR {r['avgR']:+.3f} trig/d {r['trig_day']:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv"); ap.add_argument("--cache", default="s11_cache.joblib")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--slice", default="dev", choices=["dev", "final", "full"])
    ap.add_argument("--cfg", default="{}")
    ap.add_argument("--sweep", default=""); ap.add_argument("--out", default="s11_results.json")
    a = ap.parse_args()

    if a.build:
        t0 = time.time()
        df = build(a.csv)
        joblib.dump(df, a.cache, compress=1)
        print(f"built {len(df)} M5 rows {df.index[0]} -> {df.index[-1]} in {time.time()-t0:.0f}s")
        return

    df = joblib.load(a.cache)
    cut = pd.Timestamp("2024-07-01")
    if a.slice == "dev":     df = df[df.index < cut]
    elif a.slice == "final": df = df[df.index >= cut]
    print(f"slice={a.slice}: {len(df)} rows {df.index[0].date()} -> {df.index[-1].date()}", flush=True)

    if not a.sweep:
        cfg = dict(BASE); cfg.update(json.loads(a.cfg))
        r = harness(df, cfg); print(fmt("WHOLE", r), flush=True)
        h1, h2 = split_eval(df, cfg)
        print(fmt("H1   ", h1)); print(fmt("H2   ", h2))
        print(f"MIN(H1,H2) pass(traded) = {min(h1['pass_traded'], h2['pass_traded']):.1f}%")
        return

    grids = {
        "stage1": dict(trigger=["cci", "pullback"],
                       sl_mult=[1.0, 2.0, 3.0],
                       rr=[1.5, 2.5, 3.5],
                       session=[None, (990, 1380)],   # all | 16:30-23:00 broker (NY)
                       energy=["h1", "both"]),
        "stage2": dict(trigger=["cci", "pullback", "either", "m15"],
                       census=[False, True], uni=[False, True],
                       require15=[False, True],
                       recross=[False, True], lic_exit=[False, True]),
    }
    grid = grids[a.sweep]
    keys = list(grid); combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== sweep {a.sweep}: {len(combos)} configs ===", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        cv = dict(zip(keys, vals)); cfg = dict(BASE); cfg.update(json.loads(a.cfg)); cfg.update(cv)
        t0 = time.time()
        h1, h2 = split_eval(df, cfg)
        w = harness(df, cfg)
        m = min(h1["pass_traded"], h2["pass_traded"])
        rec = dict(cfg={k: (list(v) if isinstance(v, tuple) else v) for k, v in cv.items()},
                   MIN=m, H1=h1["pass_traded"], H2=h2["pass_traded"],
                   pass_all=w["pass_all"], cov=w["coverage"], breach=w["breach"],
                   streak=w["best_streak"], worst30=w["worst30"], trades=w["trades"],
                   win=w["win"], avgR=w["avgR"])
        rows.append(rec)
        best = max(rows, key=lambda z: (z["breach"] == 0, z["MIN"]))
        print(f"[{n:3d}/{len(combos)}] MIN {m:5.1f} (H1 {h1['pass_traded']:5.1f} H2 {h2['pass_traded']:5.1f}) "
              f"all {w['pass_all']:5.1f} cov {w['coverage']:4.0f} brch {w['breach']:3d} "
              f"win {w['win']:4.1f} aR {w['avgR']:+.2f} {int(time.time()-t0)}s "
              f"| BEST {best['MIN']:5.1f} {best['cfg']}", flush=True)
        json.dump(sorted(rows, key=lambda z: (z["breach"] == 0, z["MIN"]), reverse=True),
                  open(a.out, "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
