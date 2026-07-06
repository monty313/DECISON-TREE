#!/usr/bin/env python3
"""Diagnostics for the honest STRAT-011 stack.

1) Day anatomy of a config: how do non-pass days end (near-miss vs bleed)?
2) REQUIREMENT CURVE: keep the REAL licensed trigger stream (same days, same
   trigger times, same day machinery: guard, halt, lock, EOD) but replace
   trade outcomes with synthetic Bernoulli(p) at the config's rr.
   -> shows the day-pass rate the DoD demands as a function of per-trade
   win probability, given the coverage the license actually provides.
3) Hour-of-day EV table for licensed triggers.
"""
import json, sys
import numpy as np
import pandas as pd
import joblib
import s11

rng = np.random.default_rng(7)


def requirement_curve(df, cfg, ps):
    """Synthetic-outcome day simulation on the real trigger stream."""
    o = df["open"].values
    atr = df["atr"].values
    cciv = df["cci"].values
    persB = df["persB"].values; persBe = df["persBe"].values
    h1e = df["h1e"].values
    idx = df.index; dates = idx.normalize().values
    minute = (idx.hour * 60 + idx.minute).values
    N = len(df)
    licB = persB & h1e; licS = persBe & h1e
    xup = np.zeros(N, bool); xdn = np.zeros(N, bool)
    xup[1:] = (cciv[1:] > 0) & (cciv[:-1] <= 0)
    xdn[1:] = (cciv[1:] < 0) & (cciv[:-1] >= 0)
    trig = (licB & xup) | (licS & xdn)
    ses = cfg.get("session")
    if ses is not None:
        trig = trig & (minute >= ses[0]) & (minute < ses[1])
    trig = trig & np.isfinite(atr) & (atr > 0)
    # per-day trigger counts
    day_trigs = {}
    for i in np.nonzero(trig)[0]:
        d = dates[i]
        day_trigs.setdefault(d, 0)
        day_trigs[d] += 1
    all_days = sorted(set(dates.tolist()))
    n_all = len(all_days)
    rr = cfg["rr"]; tgt = cfg["target"]; ddh = cfg["ddh"]
    rows = []
    NSIM = 400
    for p in ps:
        passes = np.zeros(NSIM)
        for s in range(NSIM):
            np_pass = 0
            for d in all_days:
                k = day_trigs.get(d, 0)
                if k == 0:
                    continue
                cum = 0.0   # in R units (risk 1% of initial per trade)
                # sequential trades: stop at lock (+tgt) or guard (next full loss would cross ddh)
                for _ in range(k):
                    if cum >= tgt:
                        break
                    if -(cum - 1.0) >= ddh:      # guard: a -1R loss would cross halt
                        break
                    cum += rr if rng.random() < p else -1.0
                if cum >= tgt:
                    np_pass += 1
            passes[s] = np_pass
        traded_days = sum(1 for d in all_days if day_trigs.get(d, 0) > 0)
        rows.append(dict(p=p, pass_traded=100 * passes.mean() / max(1, traded_days),
                         pass_all=100 * passes.mean() / n_all))
        print(f"  p={p:.2f} rr={rr}: pass(traded) {rows[-1]['pass_traded']:5.1f}%  "
              f"pass(all) {rows[-1]['pass_all']:5.1f}%  (traded {traded_days}/{n_all} days)", flush=True)
    return rows


def day_anatomy(df, cfg):
    r = s11.harness(df, cfg, collect_days=True)
    rets = np.array([x[1] for x in r["day_rows"]])
    out = np.array(r["outcomes"])
    m = out == "M"
    print(f"config {json.dumps({k: v for k, v in cfg.items() if k in ('trigger','rr','session','energy','sl_mult')})}")
    print(f"  P {np.sum(out=='P')}  M {np.sum(m)}  B {np.sum(out=='B')}  N {np.sum(out=='N')}")
    if m.any():
        mr = rets[m]
        print(f"  MISS days: mean {mr.mean():+.2f}%  median {np.median(mr):+.2f}%  "
              f">0: {(mr>0).mean()*100:.0f}%  in(1.5,2.5): {((mr>=1.5)&(mr<2.5)).mean()*100:.0f}%  "
              f"<=-2: {(mr<=-2).mean()*100:.0f}%")
    return r


def hour_ev(df, cfg):
    """avgR of licensed cci triggers by hour, honest bracket sim (vectorized rough)."""
    r = s11.harness(df, cfg)   # ensure same config machinery; then quick per-hour re-run via session windows
    print("hour-of-day EV via session windows (2h):")
    for h0 in range(0, 24, 2):
        c = dict(cfg); c["session"] = (h0 * 60, (h0 + 2) * 60)
        x = s11.harness(df, c)
        if x["trades"] >= 30:
            print(f"  {h0:02d}-{h0+2:02d}h: tr {x['trades']:5d} win {x['win']:4.1f}% aR {x['avgR']:+.3f} "
                  f"pass(traded) {x['pass_traded']:4.1f}% cov {x['coverage']:4.1f}%", flush=True)


if __name__ == "__main__":
    df = joblib.load("s11_full.joblib")
    df = df[df.index < pd.Timestamp("2024-07-01")]
    base = dict(s11.BASE)
    print("=== DAY ANATOMY: best stage-1 (pullback rr2.5 all-hours h1) ===")
    cfg = dict(base); cfg.update(trigger="pullback", rr=2.5)
    day_anatomy(df, cfg)
    print("\n=== REQUIREMENT CURVE (cci rr2.5 all-hours h1, real trigger stream) ===")
    cfg2 = dict(base); cfg2.update(trigger="cci", rr=2.5)
    requirement_curve(df, cfg2, [0.30, 0.40, 0.50, 0.60, 0.70, 0.80])
    print("\n=== HOUR-OF-DAY EV (cci rr2.5 h1) ===")
    hour_ev(df, cfg2)
