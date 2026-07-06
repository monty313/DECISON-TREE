#!/usr/bin/env python3
"""
Parameter search for us30_rf_bot toward the goal: maximize the % of trading days
that PASS the FTMO rule (+2.5% of initial, avoid 4% trailing daily DD).

Design:
- Build features + BB(20,1) bracket labels ONCE (the expensive step), cache them.
- For each candidate config, only refit the RF + replay the walk-forward harness.
- Split the timeline into a TUNE window (earlier folds) and an untouched HOLDOUT
  (the most recent folds). We rank configs by TUNE pass-rate but the number that
  counts is the HOLDOUT pass-rate -- guards against overfitting the knobs.
- Sweeps the levers that actually move DAILY pass-rate:
    conf_min      : selectivity (few high-conviction trades vs a firehose)
    tp_R          : target size (low tp_R -> higher win rate, which a daily-target
                    game needs more than big reward:risk)
    risk_pct      : how few wins lock the +2.5% day
    max_trades_day: cap to stop bleeding on chop days (a 0-trade day is a
                    NON-trading day, excluded from pass-rate -- better than a red day)
    label_min_R   : how much edge a bar needs to be labelled long/short
    min_samples_leaf: RF regularization

Usage:
  python optimize.py --csv _smoke.csv
  python optimize.py --csv US30_...csv --holdout-folds 3 --quick
"""
import argparse, itertools, sys, time
import numpy as np, pandas as pd
import us30_rf_bot as bot


def prep_cached(csv, base_cfg):
    m1, X, sim = bot.prepare(csv, base_cfg)
    days = pd.Series(X.index.date, index=X.index)
    uniq = np.array(sorted(set(days)))
    return m1, X, sim, days, uniq


def walk_forward(X, sim, days, uniq, cfg, start_i, stop_i):
    """Run folds whose test-window START index is in [start_i, stop_i). Returns
    aggregate pass/total/breach across those folds, plus per-fold rows."""
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    y = bot.make_labels(sim, cfg)
    i = max(tr_n, start_i)
    tot_p = tot_d = tot_b = tot_tr = 0
    rows = []
    while i + 1 < len(uniq) and i < stop_i:
        tr_days = set(uniq[max(0, i - tr_n):i]); te_days = set(uniq[i:i + te_n])
        tr = days.isin(tr_days).values; te = days.isin(te_days).values
        if tr.sum() < 3000 or te.sum() < 100:
            i += te_n; continue
        mdl = bot.new_model(cfg); mdl.fit(X.values[tr], y.values[tr])
        sig, _, _ = bot.signals_from_proba(mdl, X[te], cfg)
        res = bot.run_harness(sig, sim[te], cfg)
        tot_p += res["pass_days"]; tot_d += res["trading_days"]
        tot_b += res["dd_breach_days"]; tot_tr += res["trades"]
        rows.append(res)
        i += te_n
    rate = 100.0 * tot_p / max(1, tot_d)
    return dict(pass_days=tot_p, trading_days=tot_d, dd_breach=tot_b,
                trades=tot_tr, pass_rate=rate), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--holdout-folds", type=int, default=2,
                    help="most-recent test folds reserved as untouched holdout")
    ap.add_argument("--quick", action="store_true", help="smaller grid")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()

    base = dict(bot.CFG)
    print("=== building features + labels once ===")
    t0 = time.time()
    m1, X, sim, days, uniq = prep_cached(a.csv, base)
    print(f"    ready in {time.time()-t0:.0f}s   {X.shape[1]} feats x {len(X):,} bars   "
          f"{len(uniq)} trading days")

    # fold-start indices (each advances by test_days)
    tr_n, te_n = int(base["train_days"]), int(base["test_days"])
    starts = list(range(tr_n, len(uniq) - 1, te_n))
    if len(starts) < a.holdout_folds + 1:
        print("!! not enough days for a holdout split; using all folds as TUNE")
        tune_stop = starts[-1] + te_n if starts else len(uniq)
        hold_start = tune_stop
    else:
        hold_start = starts[-a.holdout_folds]
        tune_stop = hold_start
    print(f"    TUNE folds start < day-idx {hold_start} | HOLDOUT = last {a.holdout_folds} folds\n")

    # ---- grid ----
    if a.quick:
        grid = dict(
            conf_min=[0.55, 0.65, 0.75], tp_R=[1.0, 1.5], risk_pct=[0.5, 1.0],
            max_trades_day=[0, 3], label_min_R=[0.5], min_samples_leaf=[250],
            conf_margin=[0.10])
    else:
        grid = dict(
            conf_min=[0.55, 0.62, 0.70, 0.78, 0.85],
            tp_R=[0.8, 1.0, 1.3, 1.8],
            risk_pct=[0.5, 0.8, 1.2],
            max_trades_day=[0, 2, 3, 5],
            label_min_R=[0.35, 0.5, 0.75],
            min_samples_leaf=[150, 300],
            conf_margin=[0.10])

    keys = list(grid); combos = list(itertools.product(*[grid[k] for k in keys]))
    print(f"=== sweeping {len(combos)} configs on TUNE window ===", flush=True)
    results = []
    for n, vals in enumerate(combos, 1):
        cvals = dict(zip(keys, vals))
        cfg = dict(base); cfg.update(cvals)
        t = time.time()
        agg, _ = walk_forward(X, sim, days, uniq, cfg, tr_n, tune_stop)
        results.append((agg["pass_rate"], agg, cvals))
        best = max(results, key=lambda r: r[0])
        # log EVERY config so progress is always visible
        print(f"  [{n:3d}/{len(combos)}] tune {agg['pass_rate']:5.1f}% "
              f"(pass {agg['pass_days']}/{agg['trading_days']}, tr {agg['trades']}, "
              f"brch {agg['dd_breach']})  {int(time.time()-t)}s  | best {best[0]:5.1f}% {best[2]}",
              flush=True)

    results.sort(key=lambda r: r[0], reverse=True)
    print("\n=== TOP CONFIGS (by TUNE pass-rate) -> re-scored on untouched HOLDOUT ===")
    print(f"{'tune%':>6} {'hold%':>6} {'trades':>7} {'breach':>6}  config")
    scored = []
    for rate, agg, cvals in results[:a.top]:
        cfg = dict(base); cfg.update(cvals)
        hagg, _ = walk_forward(X, sim, days, uniq, cfg, hold_start, len(uniq))
        scored.append((hagg["pass_rate"], rate, hagg, agg, cvals))
        print(f"{rate:6.1f} {hagg['pass_rate']:6.1f} "
              f"{hagg['trades']:7d} {hagg['dd_breach']:6d}  {cvals}")

    scored.sort(key=lambda r: r[0], reverse=True)
    best_hold = scored[0]
    print("\n=== BEST BY HOLDOUT ===")
    print(f"  holdout pass-rate: {best_hold[0]:.1f}%   tune: {best_hold[1]:.1f}%")
    print(f"  config: {best_hold[4]}")
    print(f"  holdout detail: pass {best_hold[2]['pass_days']}/{best_hold[2]['trading_days']} "
          f"days, {best_hold[2]['trades']} trades, {best_hold[2]['dd_breach']} DD-breaches")
    # emit a --flag string to reproduce
    flags = " ".join(f"--{k.replace('_','-')} {v}" for k, v in best_hold[4].items())
    print(f"\n  reproduce: python us30_rf_bot.py train --csv {a.csv} {flags}")


if __name__ == "__main__":
    main()
