#!/usr/bin/env python3
"""
Contract-compliant optimizer for us30_rf_bot.

DEFINITION OF DONE: >=90% day-pass-rate on MIN(in-sample, out-of-sample),
>=30 trading days. Rank configs by MIN(IS, OOS) so overfit configs (great IS,
weak OOS) are rejected automatically.

Fast: loads cached features/labels (cache_*.joblib from cache_prep.py); per config
only refits the RF and replays the harness on walk-forward folds.

For each fold we score:
  IS  = harness pass-rate on the fold's TRAIN window (in-sample days)
  OOS = harness pass-rate on the fold's TEST window (out-of-sample days)
Aggregated across folds -> IS%, OOS%, MIN = min(IS, OOS).

Usage:
  python opt2.py --cache cache_smoke.joblib --grid quick
  python opt2.py --cache cache_full.joblib  --grid focused --trees 120
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd, joblib
import us30_rf_bot as bot


def score_window(mdl, X, sim, days, day_set, cfg):
    mask = days.isin(day_set).values
    if mask.sum() < 50:
        return None
    sig, _, _ = bot.signals_from_proba(mdl, X[mask], cfg)
    return bot.run_harness(sig, sim[mask], cfg)


def walk(X, sim, days, uniq, cfg):
    """Returns aggregate IS and OOS across all folds."""
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    y = bot.make_labels(sim, cfg)
    is_p = is_d = oos_p = oos_d = oos_b = tr_tot = 0
    i = tr_n
    while i + 1 < len(uniq):
        tr_days = set(uniq[max(0, i - tr_n):i]); te_days = set(uniq[i:i + te_n])
        tr = days.isin(tr_days).values; te = days.isin(te_days).values
        if tr.sum() < 3000 or te.sum() < 100:
            i += te_n; continue
        mdl = bot.new_model(cfg); mdl.fit(X.values[tr], y.values[tr])
        # in-sample: score the TRAIN days with the same model (upper bound / overfit gauge)
        r_is = score_window(mdl, X, sim, days, tr_days, cfg)
        r_oos = score_window(mdl, X, sim, days, te_days, cfg)
        if r_is:  is_p += r_is["pass_days"];  is_d += r_is["trading_days"]
        if r_oos:
            oos_p += r_oos["pass_days"]; oos_d += r_oos["trading_days"]
            oos_b += r_oos["dd_breach_days"]; tr_tot += r_oos["trades"]
        i += te_n
    IS = 100.0 * is_p / max(1, is_d)
    OOS = 100.0 * oos_p / max(1, oos_d)
    return dict(IS=IS, OOS=OOS, MIN=min(IS, OOS), is_days=is_d, oos_days=oos_d,
                oos_pass=oos_p, oos_breach=oos_b, trades=tr_tot)


GRIDS = {
    "quick": dict(conf_min=[0.55, 0.70, 0.85], tp_R=[1.0, 1.5],
                  risk_pct=[0.5, 1.0], max_trades_day=[0, 3],
                  label_min_R=[0.5], min_samples_leaf=[250], conf_margin=[0.10]),
    "focused": dict(conf_min=[0.60, 0.72, 0.82, 0.90], tp_R=[0.8, 1.2, 1.6],
                    risk_pct=[0.5, 0.9, 1.3], max_trades_day=[0, 2, 4],
                    label_min_R=[0.35, 0.6], min_samples_leaf=[150, 400],
                    conf_margin=[0.08]),
    "selective": dict(conf_min=[0.80, 0.86, 0.92, 0.96], tp_R=[0.8, 1.1, 1.5],
                      risk_pct=[0.8, 1.2, 1.6], max_trades_day=[1, 2, 3],
                      label_min_R=[0.5, 0.8], min_samples_leaf=[200],
                      conf_margin=[0.05, 0.10]),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--grid", default="quick", choices=list(GRIDS))
    ap.add_argument("--trees", type=int, default=0, help="override n_estimators for speed")
    ap.add_argument("--out", default="opt2_results.json")
    a = ap.parse_args()

    d = joblib.load(a.cache)
    X, sim = d["X"], d["sim"]
    base = dict(bot.CFG)
    if a.trees: base["n_estimators"] = a.trees
    days = pd.Series(X.index.date, index=X.index)
    uniq = np.array(sorted(set(days)))
    print(f"loaded {X.shape} | {len(uniq)} trading days | trees={base['n_estimators']}", flush=True)

    grid = GRIDS[a.grid]; keys = list(grid)
    combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== {len(combos)} configs, ranked by MIN(IS,OOS) ===", flush=True)
    rows = []
    for n, vals in enumerate(combos, 1):
        cvals = dict(zip(keys, vals)); cfg = dict(base); cfg.update(cvals)
        t = time.time()
        r = walk(X, sim, days, uniq, cfg)
        r["cfg"] = cvals
        rows.append(r)
        best = max(rows, key=lambda z: z["MIN"])
        print(f"[{n:3d}/{len(combos)}] IS {r['IS']:5.1f}  OOS {r['OOS']:5.1f}  "
              f"MIN {r['MIN']:5.1f}  (oos {r['oos_pass']}/{r['oos_days']}d, tr {r['trades']}, "
              f"brch {r['oos_breach']})  {int(time.time()-t)}s | BEST MIN {best['MIN']:5.1f} {best['cfg']}",
              flush=True)
        json.dump(sorted(rows, key=lambda z: z["MIN"], reverse=True)[:15],
                  open(a.out, "w"), indent=2)

    rows.sort(key=lambda z: z["MIN"], reverse=True)
    print("\n=== TOP 10 BY MIN(IS,OOS) ===")
    for r in rows[:10]:
        print(f"  MIN {r['MIN']:5.1f}  IS {r['IS']:5.1f}  OOS {r['OOS']:5.1f}  "
              f"oos_days {r['oos_days']}  {r['cfg']}")
    b = rows[0]
    print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'}  "
          f"best MIN {b['MIN']:.1f}% (IS {b['IS']:.1f}, OOS {b['OOS']:.1f}, {b['oos_days']} oos days)")


if __name__ == "__main__":
    main()
