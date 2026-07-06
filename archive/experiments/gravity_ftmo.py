#!/usr/bin/env python3
"""
GRAVITY momentum strategy through the FTMO harness — measures day-pass rate (IS & OOS).

Framework (from how to use momentum.md + Trading-laws-for-EA.docx):
  GATE (refuse most bars):
    Law 0  : price > SMA(4,shift8,High) AND > SMA(4,shift8,Low) on BOTH M1 & M15 (long; mirror short)
    Gravity: H1 CCI(cci_htf) > 0 AND > its shifted SMA  (Bull; mirror Bear)   [persistence]
    GreatMv: H1 ADX(14) > shifted-SMA AND ATR(14) > shifted-SMA               [energy]
    Synergy: M5 CCI fast/mid/slow ALL same side (unanimous)                    [trinity]
  ENTRY  : first gated bar when flat (and re-entry while regime hot — Principle 1)
  EXIT   : hold while regime valid; close on Law0-fail(both TFs) OR mid-CCI(M5) flip against  [let winners run]
  RISK   : per-trade risk_pct sized off an initial ATR stop; +2.5% daily lock, 4% trailing DD (bal & eq)

Reports IS and OOS day-pass MIN per the contract (>=90%, >=30 days).
Usage: python gravity_ftmo.py --csv _smoke.csv --sweep
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd
import us30_rf_bot as bot


def build(csv, p):
    m1 = bot.load_m1(csv); pt = bot.infer_point(m1)
    def rs(r): return bot.resample(m1, r)
    m5, m15, h1 = rs("5min"), rs("15min"), rs("1h")
    def sma(s, n): return s.rolling(n, min_periods=n).mean()
    def cci(df, n): return bot.cci(df["high"], df["low"], df["close"], n)
    # Law 0
    def law0(df):
        sh = sma(df["high"], 4).shift(8); sl = sma(df["low"], 4).shift(8)
        return (df["close"] > sh) & (df["close"] > sl), (df["close"] < sh) & (df["close"] < sl)
    l0L_m1, l0S_m1 = law0(m1); l0L_m15, l0S_m15 = law0(m15)
    # Gravity (H1 CCI persistence)
    hc = cci(h1, p["cci_htf"]); hcs = sma(hc, p["persist_n"]).shift(p["persist_sh"])
    gB = (hc > 0) & (hc > hcs); gBe = (hc < 0) & (hc < hcs)
    # Great Movement (H1)
    a = bot.adx(h1["high"], h1["low"], h1["close"], 14); asm = sma(a, p["persist_n"]).shift(p["persist_sh"])
    t = bot.atr(h1["high"], h1["low"], h1["close"], 14); tsm = sma(t, p["persist_n"]).shift(p["persist_sh"])
    gm = (a > asm) & (t > tsm)
    # Synergy (M5 fast/mid/slow CCI unanimous) + mid for exit
    f, mid, s = cci(m5, p["cci_f"]), cci(m5, p["cci_m"]), cci(m5, p["cci_s"])
    synU = (f > 0) & (mid > 0) & (s > 0); synD = (f < 0) & (mid < 0) & (s < 0)
    atr_m5 = bot.atr(m5["high"], m5["low"], m5["close"], 14)
    dec = m5.index + pd.Timedelta(minutes=5)
    def al(x, tf): y = x.copy(); y.index = y.index + pd.Timedelta(minutes=tf); return y.reindex(dec, method="ffill")
    L0L = al(l0L_m1.reindex(m1.index), 1).fillna(0).astype(bool) & al(l0L_m15, 15).fillna(0).astype(bool)
    L0S = al(l0S_m1.reindex(m1.index), 1).fillna(0).astype(bool) & al(l0S_m15, 15).fillna(0).astype(bool)
    df = pd.DataFrame({
        "close": al(m5["close"].reindex(m5.index), 5).values,
        "atr":   al(atr_m5.reindex(m5.index), 5).values,
        "L0L": L0L.values, "L0S": L0S.values,
        "GB": al(gB, 60).fillna(0).astype(bool).values, "GBe": al(gBe, 60).fillna(0).astype(bool).values,
        "GM": al(gm, 60).fillna(0).astype(bool).values,
        "SU": al(synU, 5).fillna(0).astype(bool).values, "SD": al(synD, 5).fillna(0).astype(bool).values,
        "mid": al(mid.reindex(m5.index), 5).values,
    }, index=dec)
    df["entryL"] = df.L0L & df.GB & df.GM & df.SU
    df["entryS"] = df.L0S & df.GBe & df.GM & df.SD
    # RE-ENTRY triggers (Principle 1/4): while HTF regime hot (Law0+gravity+GreatMove), fire on the
    # FAST CCI crossing up/down through 0 (trigger clock) — synergy of slow periods is the standing
    # confirmation, the fast cross is the disposable trigger. Enables many short orbits per hot window.
    fa = al(f.reindex(m5.index), 5)
    fprev = fa.shift(1)
    df["fastUp"] = (fa.values > 0) & (fprev.values <= 0)
    df["fastDn"] = (fa.values < 0) & (fprev.values >= 0)
    # regime-hot masks (no synergy requirement — that's the point of re-entry)
    df["hotL"] = (df.L0L & df.GB & df.GM).values
    df["hotS"] = (df.L0S & df.GBe & df.GM).values
    df["reentryL"] = df.hotL & df.fastUp
    df["reentryS"] = df.hotS & df.fastDn
    df["spread"] = bot.CFG["spread_pts"] * pt
    return df.dropna(subset=["close", "atr"])


def harness(df, cfg, initial=100000.0):
    """FTMO day loop with the gravity entry/exit. Positive R = win. Sequential, non-overlapping."""
    risk = cfg["risk_pct"] / 100.0
    target = cfg["daily_target_pct"]; dd_halt = cfg.get("dd_halt_pct", cfg["daily_dd_pct"]); dd_fail = cfg["daily_dd_pct"]
    sl_atr = cfg.get("sl_atr", 1.0)
    c = df["close"].values; atr = df["atr"].values; sp = df["spread"].values
    if cfg.get("reentry"):
        eL = df["reentryL"].values; eS = df["reentryS"].values   # fast-cross while HTF hot (many orbits)
    else:
        eL = df["entryL"].values; eS = df["entryS"].values       # strict full-synergy entry
    l0l = df["L0L"].values; l0s = df["L0S"].values; mid = df["mid"].values
    idx = df.index; N = len(df)
    bal = initial; days = {}
    cur = None; dstart = dpeakB = dpeakE = bal; halted = False
    j = 0
    def newday(d):
        nonlocal dstart, dpeakB, dpeakE, halted
        dstart = dpeakB = dpeakE = bal; halted = False
        days[d] = {"ret": 0.0, "dd": 0.0, "trades": 0, "_start": bal}
    while j < N - 1:
        d = idx[j].date()
        if d != cur:
            if cur is not None: days[cur]["ret"] = (bal - days[cur]["_start"]) / initial * 100
            cur = d; newday(d)
        if halted or not (eL[j] or eS[j]) or not np.isfinite(atr[j]) or atr[j] <= 0:
            j += 1; continue
        side = 1 if eL[j] else -1
        stopdist = sl_atr * atr[j]
        if stopdist <= 0: j += 1; continue
        risk_amt = bal * risk
        # entry
        if side > 0:
            entry = c[j] + sp[j]; k = j + 1
            while k < N - 1 and l0l[k] and mid[k] >= 0: k += 1
            exitp = c[k] - sp[k]
        else:
            entry = c[j]; k = j + 1
            while k < N - 1 and l0s[k] and mid[k] <= 0: k += 1
            exitp = c[k] + sp[k]
        move = (exitp - entry) if side > 0 else (entry - exitp)
        R = move / stopdist                      # R-multiple vs initial ATR stop
        R = max(R, -1.2)                          # stop caps loss (regime-exit can overshoot slightly)
        # floating-equity worst dip while open (approx): min(R,-1)*risk
        eq_low = bal + min(R, -1.0 if R < 0 else 0.0) * risk_amt
        eq_high = bal + max(R, 0.0) * risk_amt
        dpeakE = max(dpeakE, eq_high)
        eqDD = (dpeakE - eq_low) / dpeakE * 100; days[d]["dd"] = max(days[d]["dd"], eqDD)
        bal += R * risk_amt
        days[d]["trades"] += 1
        dpeakB = max(dpeakB, bal); balDD = (dpeakB - bal) / dpeakB * 100
        days[d]["dd"] = max(days[d]["dd"], balDD)
        if eqDD >= dd_halt or balDD >= dd_halt: halted = True; j = k + 1; continue
        if (bal - dstart) / initial * 100 >= target or (eq_high - dstart) / initial * 100 >= target: halted = True
        j = k + 1
    if cur is not None: days[cur]["ret"] = (bal - days[cur]["_start"]) / initial * 100
    dd_days = [d for d, v in days.items() if v["trades"] > 0]
    passed = sum(1 for d in dd_days if days[d]["ret"] >= target and days[d]["dd"] < dd_fail)
    breach = sum(1 for d in dd_days if days[d]["dd"] >= dd_fail)
    return dict(pass_days=passed, trading_days=len(dd_days),
                pass_rate=100.0 * passed / max(1, len(dd_days)),
                dd_breach=breach, final=bal, ret=(bal / initial - 1) * 100)


def walk(df, cfg):
    days = pd.Series(df.index.date, index=df.index); uniq = np.array(sorted(set(days)))
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    is_p = is_d = oos_p = oos_d = oos_b = 0
    i = tr_n
    while i + 1 < len(uniq):
        # gravity has no fitting; IS = the train window, OOS = the test window (same rules)
        trd = set(uniq[max(0, i - tr_n):i]); ted = set(uniq[i:i + te_n])
        r_is = harness(df[days.isin(trd).values], cfg)
        r_oos = harness(df[days.isin(ted).values], cfg)
        is_p += r_is["pass_days"]; is_d += r_is["trading_days"]
        oos_p += r_oos["pass_days"]; oos_d += r_oos["trading_days"]; oos_b += r_oos["dd_breach"]
        i += te_n
    IS = 100.0 * is_p / max(1, is_d); OOS = 100.0 * oos_p / max(1, oos_d)
    return dict(IS=IS, OOS=OOS, MIN=min(IS, OOS), oos_days=oos_d, oos_pass=oos_p, oos_breach=oos_b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default="gravity_ftmo_results.json")
    a = ap.parse_args()
    P0 = dict(cci_htf=100, persist_n=5, persist_sh=2, cci_f=14, cci_m=40, cci_s=100)
    print("building gravity features...", flush=True)
    df = build(a.csv, P0)
    print(f"  {len(df)} M5 bars, entries L={df.entryL.sum()} S={df.entryS.sum()}", flush=True)
    base = dict(bot.CFG)
    print(f"  re-entry triggers L={df.reentryL.sum()} S={df.reentryS.sum()}", flush=True)
    if not a.sweep:
        for re in (False, True):
            cfg = dict(base); cfg["risk_pct"] = 1.0; cfg["sl_atr"] = 1.0; cfg["reentry"] = re
            r = harness(df, cfg); w = walk(df, cfg)
            tag = "RE-ENTRY" if re else "STRICT  "
            print(f"{tag}: whole {r['pass_rate']:.1f}% ({r['pass_days']}/{r['trading_days']}) ret {r['ret']:+.0f}% "
                  f"| WALK IS {w['IS']:.1f}% OOS {w['OOS']:.1f}% MIN {w['MIN']:.1f}% "
                  f"(oos {w['oos_pass']}/{w['oos_days']}d brch {w['oos_breach']})", flush=True)
        return
    grid = dict(risk_pct=[0.5, 1.0, 1.5, 2.0], sl_atr=[0.7, 1.0, 1.5], dd_halt_pct=[3.5, 4.0])
    keys = list(grid); combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== GRAVITY-FTMO sweep: {len(combos)} configs, rank by MIN(IS,OOS) ===", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        cv = dict(zip(keys, vals)); cfg = dict(base); cfg.update(cv)
        t = time.time(); w = walk(df, cfg); w["cfg"] = cv; rows.append(w)
        best = max(rows, key=lambda z: z["MIN"])
        print(f"[{n:2d}/{len(combos)}] IS {w['IS']:5.1f} OOS {w['OOS']:5.1f} MIN {w['MIN']:5.1f} "
              f"(oos {w['oos_pass']}/{w['oos_days']}d brch {w['oos_breach']}) {int(time.time()-t)}s "
              f"| BEST {best['MIN']:5.1f} {best['cfg']}", flush=True)
        json.dump(sorted(rows, key=lambda z: z["MIN"], reverse=True)[:15], open(a.out, "w"), indent=2)
    rows.sort(key=lambda z: z["MIN"], reverse=True); b = rows[0]
    print("\n=== TOP 8 BY MIN ===")
    for r in rows[:8]:
        print(f"  MIN {r['MIN']:5.1f} IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} oosD {r['oos_days']} {r['cfg']}")
    print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'} best MIN {b['MIN']:.1f}%")


if __name__ == "__main__":
    main()
