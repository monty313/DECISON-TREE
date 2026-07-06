#!/usr/bin/env python3
"""
STRAT-011 "Shifted CCI Momentum Aligner" — exact framework spec, walk-forward IS/OOS/MIN.

LICENSE (P-1): H1 CCI(cci_htf) > 0 AND > its SMA(1) shifted +sh_htf  (persistence)
  AND ENERGY GATE (H1 ADX(14) > SMA(1)shift5 AND ATR(14) > SMA(1)shift5 AND ADX>20).
ENTRY (U-1 event): fresh M5 CCI(14) zero-cross in license direction, within window W bars.
EXIT: 1-ATR hard stop / (rr*ATR) target bracket; optional fast CCI(14) recross-against.
RISK (R-1): 1% base, adaptive down as intraday DD grows; +2.5% daily lock / 4% trailing DD (both bal+eq).
Re-entry loop (P-3): each fresh trigger while license true is a new licensed entry.

Reports IS, OOS, MIN(IS,OOS) per contract. Usage: python strat011_wf.py --csv _smoke.csv --sweep
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd
import us30_rf_bot as bot


def build(csv, P):
    m1 = bot.load_m1(csv); pt = bot.infer_point(m1)
    m5 = bot.resample(m1, "5min"); h1 = bot.resample(m1, "1h"); m15 = bot.resample(m1, "15min")
    def sma(s, n): return s.rolling(n, min_periods=n).mean()
    def cci(df, n): return bot.cci(df["high"], df["low"], df["close"], n)
    # LICENSE
    hc = cci(h1, P["cci_htf"]); hb = sma(hc, 1).shift(P["sh_htf"])
    persB = (hc > 0) & (hc > hb); persBe = (hc < 0) & (hc < hb)
    adx = bot.adx(h1["high"], h1["low"], h1["close"], 14); atrh = bot.atr(h1["high"], h1["low"], h1["close"], 14)
    energy = (adx > sma(adx, 1).shift(5)) & (atrh > sma(atrh, 1).shift(5)) & (adx > 20)
    licB = persB & energy; licBe = persBe & energy
    # optional F-2 chop census on M15 vs SMA(4,shift8) (K of N closes one side)
    sh15 = sma(m15["high"], 4).shift(8); sl15 = sma(m15["low"], 4).shift(8)
    m15bull = (m15["close"] > sh15) & (m15["close"] > sl15)
    m15bear = (m15["close"] < sh15) & (m15["close"] < sl15)
    # TRIGGER
    m5cci = cci(m5, 14)
    xup = (m5cci > 0) & (m5cci.shift(1) <= 0); xdn = (m5cci < 0) & (m5cci.shift(1) >= 0)
    # M1 trigger stream (section-5 P-2: M1 CCI(14) zero-cross under the same HTF license)
    m1cci = cci(m1, 14)
    x1up = ((m1cci > 0) & (m1cci.shift(1) <= 0)).resample("5min", label="left", closed="left").max().fillna(False)
    x1dn = ((m1cci < 0) & (m1cci.shift(1) >= 0)).resample("5min", label="left", closed="left").max().fillna(False)
    dec = m5.index + pd.Timedelta(minutes=5)
    def al(x, tf): y = x.copy(); y.index = y.index + pd.Timedelta(minutes=tf); return y.reindex(dec, method="ffill")
    out = pd.DataFrame({
        "open": al(m5["open"].reindex(m5.index), 5).values,
        "high": al(m5["high"].reindex(m5.index), 5).values,
        "low":  al(m5["low"].reindex(m5.index), 5).values,
        "close":al(m5["close"].reindex(m5.index), 5).values,
        "atr":  al(bot.atr(m5["high"], m5["low"], m5["close"], 14).reindex(m5.index), 5).values,
        "cci":  al(m5cci.reindex(m5.index), 5).values,
        "licB": al(licB, 60).fillna(False).astype(bool).values,
        "licBe":al(licBe, 60).fillna(False).astype(bool).values,
        "xup":  al(xup.reindex(m5.index), 5).fillna(False).astype(bool).values,
        "xdn":  al(xdn.reindex(m5.index), 5).fillna(False).astype(bool).values,
        "x1up": al(x1up.reindex(m5.index).fillna(False), 5).fillna(False).astype(bool).values,
        "x1dn": al(x1dn.reindex(m5.index).fillna(False), 5).fillna(False).astype(bool).values,
        "m15bull": al(m15bull, 15).fillna(False).astype(bool).values,
        "m15bear": al(m15bear, 15).fillna(False).astype(bool).values,
    }, index=dec)
    out["spread"] = bot.CFG["spread_pts"] * pt
    return out.dropna(subset=["close", "atr"])


def harness(df, cfg, initial=100000.0):
    risk = cfg["risk_pct"]; rr = cfg["rr"]; recross = cfg.get("recross", False)
    ddhalt = cfg.get("dd_halt_pct", 3.5); adapt = cfg.get("adapt", True); require15 = cfg.get("require15", False)
    target = cfg["daily_target_pct"]; ddf = cfg["daily_dd_pct"]
    o = df["open"].values; hi = df["high"].values; lo = df["low"].values; c = df["close"].values
    atr = df["atr"].values; cci = df["cci"].values; sp = df["spread"].values
    LB = df["licB"].values; LBe = df["licBe"].values
    if cfg.get("m1trig"):
        XU = (df["xup"].values | df["x1up"].values); XD = (df["xdn"].values | df["x1dn"].values)
    else:
        XU = df["xup"].values; XD = df["xdn"].values
    M15b = df["m15bull"].values; M15be = df["m15bear"].values
    idx = df.index; N = len(df)
    bal = initial; days = {}; cur = None; ds = dpB = dpE = bal; halted = False
    j = 0
    while j < N - 1:
        d = idx[j].date()
        if d != cur:
            if cur is not None: days[cur]["ret"] = (bal - days[cur]["_start"]) / initial * 100
            cur = d; ds = dpB = dpE = bal; halted = False; days[d] = {"ret": 0.0, "dd": 0.0, "trades": 0, "_start": bal}
        if halted or not np.isfinite(atr[j]) or atr[j] <= 0: j += 1; continue
        goL = LB[j] and XU[j] and (M15b[j] if require15 else True)
        goS = LBe[j] and XD[j] and (M15be[j] if require15 else True)
        if not (goL or goS): j += 1; continue
        curDD = (dpB - bal) / dpB * 100 if dpB > 0 else 0
        if curDD >= ddhalt: halted = True; j += 1; continue
        rr_eff = max(risk * (1 - curDD / ddhalt), risk * 0.3) if adapt else risk
        side = 1 if goL else -1; sd = atr[j]; ra = bal * (rr_eff / 100.0); k = j + 1
        if side > 0:
            entry = c[j] + sp[j]; stop = entry - sd; tgt = entry + rr * sd; R = None
            while k < N - 1:
                if lo[k] <= stop: R = -1.0; break
                if hi[k] >= tgt: R = rr; break
                if recross and cci[k] < 0 and cci[k-1] >= 0: R = ((c[k]-sp[k]) - entry)/sd; break
                k += 1
            if R is None: R = ((c[min(k, N-1)]-sp[min(k, N-1)]) - entry)/sd
        else:
            entry = c[j]; stop = entry + sd; tgt = entry - rr * sd; R = None
            while k < N - 1:
                if hi[k] + sp[k] >= stop: R = -1.0; break
                if lo[k] + sp[k] <= tgt: R = rr; break
                if recross and cci[k] > 0 and cci[k-1] <= 0: R = (entry - (c[k]+sp[k]))/sd; break
                k += 1
            if R is None: R = (entry - (c[min(k, N-1)]+sp[min(k, N-1)]))/sd
        R = max(R, -1.1)
        eqlow = bal + min(R, -1.0 if R < 0 else 0.0) * ra; dpE = max(dpE, bal + max(R, 0.0)*ra)
        eqDD = (dpE - eqlow)/dpE*100; days[d]["dd"] = max(days[d]["dd"], eqDD)
        bal += R * ra; days[d]["trades"] += 1
        dpB = max(dpB, bal); balDD = (dpB - bal)/dpB*100; days[d]["dd"] = max(days[d]["dd"], balDD)
        if eqDD >= ddhalt or balDD >= ddhalt: halted = True; j = k+1; continue
        if (bal - ds)/initial*100 >= target: halted = True
        j = k + 1
    if cur is not None: days[cur]["ret"] = (bal - days[cur]["_start"]) / initial * 100
    dd = [d for d, v in days.items() if v["trades"] > 0]
    p = sum(1 for d in dd if days[d]["ret"] >= target and days[d]["dd"] < ddf)
    b = sum(1 for d in dd if days[d]["dd"] >= ddf); tr = sum(days[d]["trades"] for d in dd)
    return dict(pass_days=p, trading_days=len(dd), pass_rate=100*p/max(1, len(dd)),
                breach=b, trades=tr, ret=(bal/initial-1)*100)


def walk(df, cfg):
    days = pd.Series(df.index.date, index=df.index); uniq = np.array(sorted(set(days)))
    trn, ten = int(cfg["train_days"]), int(cfg["test_days"]); i = trn
    isp = isd = osp = osd = osb = 0
    while i + 1 < len(uniq):
        trd = set(uniq[max(0, i-trn):i]); ted = set(uniq[i:i+ten])
        r = harness(df[days.isin(trd).values], cfg); isp += r["pass_days"]; isd += r["trading_days"]
        r = harness(df[days.isin(ted).values], cfg); osp += r["pass_days"]; osd += r["trading_days"]; osb += r["breach"]
        i += ten
    IS = 100*isp/max(1, isd); OOS = 100*osp/max(1, osd)
    return dict(IS=IS, OOS=OOS, MIN=min(IS, OOS), oos_days=osd, oos_pass=osp, oos_breach=osb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True); ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default="strat011_wf.json")
    a = ap.parse_args()
    P = dict(cci_htf=140, sh_htf=4)
    print("building STRAT-011 features...", flush=True)
    df = build(a.csv, P)
    print(f"  {len(df)} M5 bars", flush=True)
    base = dict(bot.CFG)
    if not a.sweep:
        cfg = dict(base); cfg.update(dict(risk_pct=1.0, rr=1.5, recross=False, adapt=True))
        r = harness(df, cfg); w = walk(df, cfg)
        print(f"WHOLE: {r['pass_rate']:.1f}% ({r['pass_days']}/{r['trading_days']}) breach {r['breach']} ret {r['ret']:+.0f}%", flush=True)
        print(f"WALK: IS {w['IS']:.1f}% OOS {w['OOS']:.1f}% MIN {w['MIN']:.1f}% (oos {w['oos_pass']}/{w['oos_days']}d brch {w['oos_breach']})", flush=True)
        return
    grid = dict(rr=[1.0, 1.3, 1.5, 2.0], risk_pct=[1.0, 1.5, 2.0, 2.5], recross=[False],
                require15=[False], m1trig=[False, True])
    keys = list(grid); combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== STRAT-011 sweep: {len(combos)} configs, rank by MIN(IS,OOS) ===", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        cv = dict(zip(keys, vals)); cfg = dict(base); cfg.update(cv); cfg["adapt"] = True
        t = time.time(); w = walk(df, cfg); w["cfg"] = cv; rows.append(w)
        best = max(rows, key=lambda z: z["MIN"])
        print(f"[{n:2d}/{len(combos)}] IS {w['IS']:5.1f} OOS {w['OOS']:5.1f} MIN {w['MIN']:5.1f} "
              f"(oos {w['oos_pass']}/{w['oos_days']}d brch {w['oos_breach']}) {int(time.time()-t)}s "
              f"| BEST {best['MIN']:5.1f} {best['cfg']}", flush=True)
        json.dump(sorted(rows, key=lambda z: z["MIN"], reverse=True)[:15], open(a.out, "w"), indent=2)
    rows.sort(key=lambda z: z["MIN"], reverse=True); b = rows[0]
    print("\n=== TOP 8 BY MIN ===")
    for r in rows[:8]:
        print(f"  MIN {r['MIN']:5.1f} IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} oosD {r['oos_days']} brch {r['oos_breach']} {r['cfg']}")
    print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'} best MIN {b['MIN']:.1f}%")


if __name__ == "__main__":
    main()
