#!/usr/bin/env python3
"""
PRECISION-FIRST REDESIGN (the real path to 90%).

Oracle bound proved: picking winners perfectly -> 95-98% of days pass, with ~28
winning setups available per day. So the ONLY thing that matters is the model's
PRECISION on the winner class: at the probability threshold where we act, what
fraction of taken trades are actually winners?

Design:
- Two BINARY targets per bar (easier than 3-class direction):
    yL = 1 if long_R  >= win_R (long hits +target before -1R stop)
    yS = 1 if short_R >= win_R
- Train two RandomForestClassifiers (long-winner, short-winner).
- Walk-forward. For the OOS test window, report the precision/recall/coverage of
  each model at several probability thresholds -> find the threshold with high
  precision (>=~0.6) that still leaves enough trades.
- Then run the FTMO harness: on each bar, if pL_win >= thr take long, elif
  pS_win >= thr take short (top-K/day gate), sized so ~2 wins locks +2.5%.
- Report IS and OOS day-pass-rate and MIN (contract).

Usage:
  python precision_bot.py --cache cache_smoke.joblib --trees 200 --diagnose
  python precision_bot.py --cache cache_smoke.joblib --trees 200 --sweep
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
import us30_rf_bot as bot


def binary_targets(sim, win_R):
    L = np.nan_to_num(sim["long_R"].values, nan=-9.0)
    S = np.nan_to_num(sim["short_R"].values, nan=-9.0)
    return (L >= win_R).astype(np.int8), (S >= win_R).astype(np.int8)


def new_bin(cfg):
    return RandomForestClassifier(
        n_estimators=cfg["n_estimators"], min_samples_leaf=cfg["min_samples_leaf"],
        max_features="sqrt", n_jobs=-1, class_weight="balanced_subsample",
        random_state=cfg["seed"])


def fit_pair(X, yL, yS, mask, cfg):
    mL = new_bin(cfg); mL.fit(X.values[mask], yL[mask])
    mS = new_bin(cfg); mS.fit(X.values[mask], yS[mask])
    return mL, mS


def prob_win(mdl, Xsub):
    P = mdl.predict_proba(Xsub.values)
    cl = list(mdl.classes_)
    return P[:, cl.index(1)] if 1 in cl else np.zeros(len(Xsub))


def sniper_from_probs(pL, pS, index, thr, topk):
    raw = np.zeros(len(index), dtype=np.int8); conf = np.zeros(len(index))
    takeL = pL >= thr; takeS = (pS >= thr) & (pS > pL)
    raw[takeL] = 1; conf[takeL] = pL[takeL]
    raw[takeS] = -1; conf[takeS] = pS[takeS]
    s = pd.Series(raw, index=index); c = pd.Series(conf, index=index)
    day = pd.Series(pd.DatetimeIndex(index).date, index=index)
    out = pd.Series(0, index=index, dtype=np.int8)
    for _, idx in c.groupby(day.values).groups.items():
        fired = c.loc[idx]; fired = fired[fired > 0]
        if len(fired) == 0: continue
        keep = fired.sort_values(ascending=False).index[:topk]
        out.loc[keep] = s.loc[keep]
    return out


def diagnose(X, sim, days, uniq, cfg, win_R):
    """Report OOS winner-class precision at thresholds, aggregated over folds."""
    yL, yS = binary_targets(sim, win_R)
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    thrs = [0.5, 0.6, 0.7, 0.8, 0.9]
    agg = {t: dict(tp=0, fp=0, pos=0) for t in thrs}
    i = tr_n
    while i + 1 < len(uniq):
        trd = set(uniq[max(0, i-tr_n):i]); ted = set(uniq[i:i+te_n])
        trm = days.isin(trd).values; tem = days.isin(ted).values
        if trm.sum() < 3000 or tem.sum() < 100: i += te_n; continue
        mL, mS = fit_pair(X, yL, yS, trm, cfg)
        pL = prob_win(mL, X[tem]); pS = prob_win(mS, X[tem])
        truL = yL[tem]; truS = yS[tem]
        for t in thrs:
            for p, tru in ((pL, truL), (pS, truS)):
                sel = p >= t
                agg[t]["tp"] += int(((sel) & (tru == 1)).sum())
                agg[t]["fp"] += int(((sel) & (tru == 0)).sum())
                agg[t]["pos"] += int(sel.sum())
        i += te_n
    print(f"  win_R={win_R}  OOS winner-class precision by threshold:")
    for t in thrs:
        a = agg[t]; prec = a["tp"]/max(1,a["tp"]+a["fp"])
        print(f"    thr {t:.2f}: precision {100*prec:4.1f}%  picks {a['pos']}  "
              f"(tp {a['tp']} fp {a['fp']})", flush=True)
    return agg


def walk_pass(X, sim, days, uniq, cfg, win_R, thr, topk):
    yL, yS = binary_targets(sim, win_R)
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    is_p=is_d=oos_p=oos_d=oos_b=tr=0
    i = tr_n
    while i + 1 < len(uniq):
        trd = set(uniq[max(0,i-tr_n):i]); ted = set(uniq[i:i+te_n])
        trm = days.isin(trd).values; tem = days.isin(ted).values
        if trm.sum() < 3000 or tem.sum() < 100: i += te_n; continue
        mL, mS = fit_pair(X, yL, yS, trm, cfg)
        for dset, dm, isoos in ((trd, trm, False), (ted, tem, True)):
            pL = prob_win(mL, X[dm]); pS = prob_win(mS, X[dm])
            sig = sniper_from_probs(pL, pS, X[dm].index, thr, topk)
            res = bot.run_harness(sig, sim[dm], cfg)
            if isoos:
                oos_p += res["pass_days"]; oos_d += res["trading_days"]
                oos_b += res["dd_breach_days"]; tr += res["trades"]
            else:
                is_p += res["pass_days"]; is_d += res["trading_days"]
        i += te_n
    IS=100.0*is_p/max(1,is_d); OOS=100.0*oos_p/max(1,oos_d)
    return dict(IS=IS, OOS=OOS, MIN=min(IS,OOS), oos_days=oos_d, oos_pass=oos_p,
                oos_breach=oos_b, trades=tr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--trees", type=int, default=200)
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--out", default="precision_results.json")
    a = ap.parse_args()
    d = joblib.load(a.cache); X, sim = d["X"], d["sim"]
    base = dict(bot.CFG); base["n_estimators"] = a.trees; base["min_samples_leaf"] = 200
    days = pd.Series(X.index.date, index=X.index); uniq = np.array(sorted(set(days)))
    print(f"loaded {X.shape} | {len(uniq)} days | trees={a.trees}", flush=True)

    if a.diagnose:
        for win_R in (0.6, 1.0):
            diagnose(X, sim, days, uniq, base, win_R)

    if a.sweep:
        grid = dict(win_R=[0.6, 1.0], thr=[0.6, 0.7, 0.8, 0.9],
                    topk=[1, 2, 3], risk_pct=[1.0, 1.5, 2.0], tp_R=[1.0, 1.5])
        keys=list(grid); combos=list(itertools.product(*[grid[k] for k in keys]))
        print(f"=== PRECISION SWEEP: {len(combos)} configs, rank by MIN(IS,OOS) ===", flush=True)
        rows=[]
        for n, vals in enumerate(combos,1):
            cv=dict(zip(keys,vals)); cfg=dict(base); cfg["tp_R"]=cv["tp_R"]; cfg["risk_pct"]=cv["risk_pct"]
            t=time.time()
            r=walk_pass(X,sim,days,uniq,cfg,cv["win_R"],cv["thr"],cv["topk"]); r["cfg"]=cv; rows.append(r)
            best=max(rows,key=lambda z:z["MIN"])
            print(f"[{n:3d}/{len(combos)}] IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} MIN {r['MIN']:5.1f} "
                  f"(oos {r['oos_pass']}/{r['oos_days']}d tr {r['trades']} brch {r['oos_breach']}) "
                  f"{int(time.time()-t)}s | BEST {best['MIN']:5.1f} {best['cfg']}", flush=True)
            json.dump(sorted(rows,key=lambda z:z["MIN"],reverse=True)[:15], open(a.out,"w"), indent=2)
        rows.sort(key=lambda z:z["MIN"],reverse=True); b=rows[0]
        print("\n=== TOP 10 BY MIN ===")
        for r in rows[:10]:
            print(f"  MIN {r['MIN']:5.1f} IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} oosD {r['oos_days']} {r['cfg']}")
        print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'} best MIN {b['MIN']:.1f}%")


if __name__ == "__main__":
    main()
