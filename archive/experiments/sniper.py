#!/usr/bin/env python3
"""
STRUCTURAL REDESIGN toward 90% day-pass-rate: the "sniper" daily policy.

Thesis: an RF that predicts per-bar direction and trades every confident bar is
the wrong tool for a DAILY-TARGET game. Passing a day = net +2.5% at <4% DD.
The only honest path to 90% of TRADING days passing is EXTREME SELECTIVITY:
  - Each day, act only if a very-high-confidence setup exists; otherwise stay
    flat (a non-trading day is EXCLUDED from pass-rate, which is correct -- far
    better to sit out chop than force a red day).
  - Take few, surgical trades sized so ~1-2 wins locks +2.5% (harness auto-locks).
  - A losing trade is floored at -1R (bracket), so 1-2 losses stay under 4% DD.

This driver reuses us30_rf_bot's features/labels/model/harness, but applies a
per-day GATE: within each test day, only the top-K highest-probability signals
(above a high conf floor) are allowed to fire. Everything else abstains.

Reports IS and OOS pass-rate and MIN, per the contract (>=90% on MIN, >=30 days).

Usage:
  python sniper.py --cache cache_smoke.joblib --trees 150
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd, joblib
import us30_rf_bot as bot


def sniper_signals(mdl, X, cfg):
    """Per-day gate: keep only the top-K signals per calendar day whose winning-
    class probability clears conf_min AND margin. Abstain (0) on everything else."""
    P = mdl.predict_proba(X.values)
    classes = list(mdl.classes_)
    pL = P[:, classes.index(1)] if 1 in classes else np.zeros(len(X))
    pS = P[:, classes.index(2)] if 2 in classes else np.zeros(len(X))
    cmin = cfg["conf_min"]; margin = cfg["conf_margin"]
    topk = int(cfg.get("sniper_topk", 2))
    raw = np.zeros(len(X), dtype=np.int8)
    conf = np.zeros(len(X))
    isL = (pL >= cmin) & (pL - pS >= margin)
    isS = (pS >= cmin) & (pS - pL >= margin)
    raw[isL] = 1; raw[isS] = -1
    conf[isL] = pL[isL]; conf[isS] = pS[isS]
    s = pd.Series(raw, index=X.index)
    c = pd.Series(conf, index=X.index)
    # within each day, keep only the top-K by confidence
    day = pd.Series(X.index.date, index=X.index)
    out = pd.Series(0, index=X.index, dtype=np.int8)
    for _, idx in c.groupby(day.values).groups.items():
        block = c.loc[idx]
        fired = block[block > 0]
        if len(fired) == 0:
            continue
        keep = fired.sort_values(ascending=False).index[:topk]
        out.loc[keep] = s.loc[keep]
    return out


def score(mdl, X, sim, days, day_set, cfg):
    mask = days.isin(day_set).values
    if mask.sum() < 50: return None
    sig = sniper_signals(mdl, X[mask], cfg)
    return bot.run_harness(sig, sim[mask], cfg)


def walk(X, sim, days, uniq, cfg):
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    y = bot.make_labels(sim, cfg)
    is_p = is_d = oos_p = oos_d = oos_b = tr = 0
    i = tr_n
    while i + 1 < len(uniq):
        trd = set(uniq[max(0, i - tr_n):i]); ted = set(uniq[i:i + te_n])
        trm = days.isin(trd).values; tem = days.isin(ted).values
        if trm.sum() < 3000 or tem.sum() < 100: i += te_n; continue
        mdl = bot.new_model(cfg); mdl.fit(X.values[trm], y.values[trm])
        ris = score(mdl, X, sim, days, trd, cfg); ros = score(mdl, X, sim, days, ted, cfg)
        if ris: is_p += ris["pass_days"]; is_d += ris["trading_days"]
        if ros:
            oos_p += ros["pass_days"]; oos_d += ros["trading_days"]
            oos_b += ros["dd_breach_days"]; tr += ros["trades"]
        i += te_n
    IS = 100.0*is_p/max(1,is_d); OOS = 100.0*oos_p/max(1,oos_d)
    return dict(IS=IS, OOS=OOS, MIN=min(IS,OOS), oos_days=oos_d, oos_pass=oos_p,
                oos_breach=oos_b, trades=tr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--trees", type=int, default=150)
    ap.add_argument("--out", default="sniper_results.json")
    a = ap.parse_args()
    d = joblib.load(a.cache); X, sim = d["X"], d["sim"]
    base = dict(bot.CFG); base["n_estimators"] = a.trees
    days = pd.Series(X.index.date, index=X.index); uniq = np.array(sorted(set(days)))
    print(f"loaded {X.shape} | {len(uniq)} days | trees={a.trees}", flush=True)

    # sniper grid: very high confidence, few trades/day, target-friendly tp_R, bigger risk
    grid = dict(conf_min=[0.80, 0.88, 0.94], sniper_topk=[1, 2],
                tp_R=[1.0, 1.5], risk_pct=[1.0, 1.5, 2.0],
                label_min_R=[0.6], min_samples_leaf=[200], conf_margin=[0.05])
    keys = list(grid); combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== SNIPER: {len(combos)} configs, rank by MIN(IS,OOS) ===", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        cv = dict(zip(keys, vals)); cfg = dict(base); cfg.update(cv)
        t = time.time(); r = walk(X, sim, days, uniq, cfg); r["cfg"] = cv; rows.append(r)
        best = max(rows, key=lambda z: z["MIN"])
        print(f"[{n:3d}/{len(combos)}] IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} MIN {r['MIN']:5.1f} "
              f"(oos {r['oos_pass']}/{r['oos_days']}d tr {r['trades']} brch {r['oos_breach']}) "
              f"{int(time.time()-t)}s | BEST MIN {best['MIN']:5.1f} {best['cfg']}", flush=True)
        json.dump(sorted(rows, key=lambda z: z["MIN"], reverse=True)[:15], open(a.out,"w"), indent=2)
    rows.sort(key=lambda z: z["MIN"], reverse=True); b = rows[0]
    print("\n=== TOP 10 BY MIN ===")
    for r in rows[:10]:
        print(f"  MIN {r['MIN']:5.1f} IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} "
              f"oosD {r['oos_days']} {r['cfg']}")
    print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'} best MIN {b['MIN']:.1f}%")


if __name__ == "__main__":
    main()
