#!/usr/bin/env python3
"""
ITERATION 3: feature PRUNING (one change) + optional regime/structure gate.

Evidence: of 205 features, median MI vs winner-label ~0.004 (98% noise); the real
signal is HTF regime (h1/h4 CCI + slope). RF wastes splits on noise. So:
  - On each TRAIN fold, rank features by MI vs the (long|short) winner label and
    keep the top-N. Refit RF on the pruned set. Measure OOS winner precision AND
    day-pass IS/OOS/MIN.
  - --gate regime: additionally require HTF agreement (h1 CCI100 sign) with the
    trade side before firing (structure/regime gate).

Reports per contract: IS%, OOS%, MIN, oos_days, breaches.

Usage:
  python pruned_bot.py --cache cache_smoke.joblib --topn 30 --trees 200 --diagnose
  python pruned_bot.py --cache cache_smoke.joblib --topn 30 --trees 200 --sweep
"""
import argparse, itertools, time, json
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
import us30_rf_bot as bot


def new_bin(cfg):
    return RandomForestClassifier(
        n_estimators=cfg["n_estimators"], min_samples_leaf=cfg["min_samples_leaf"],
        max_features="sqrt", n_jobs=-1, class_weight="balanced_subsample",
        random_state=cfg["seed"])


def bin_targets(sim, win_R):
    L = np.nan_to_num(sim["long_R"].values, nan=-9.0)
    S = np.nan_to_num(sim["short_R"].values, nan=-9.0)
    return (L >= win_R).astype(np.int8), (S >= win_R).astype(np.int8)


def top_feats(Xtr, ytr, topn, seed=0):
    # MI on a subsample for speed
    n = min(15000, len(Xtr))
    idx = np.random.RandomState(seed).choice(len(Xtr), size=n, replace=False)
    mi = mutual_info_classif(Xtr.values[idx], ytr[idx], discrete_features=False, random_state=seed)
    order = np.argsort(mi)[::-1][:topn]
    return list(Xtr.columns[order])


def pwin(mdl, Xsub):
    P = mdl.predict_proba(Xsub.values); cl = list(mdl.classes_)
    return P[:, cl.index(1)] if 1 in cl else np.zeros(len(Xsub))


def sniper(pL, pS, index, thr, topk, regime=None):
    raw = np.zeros(len(index), dtype=np.int8); conf = np.zeros(len(index))
    takeL = pL >= thr; takeS = (pS >= thr) & (pS > pL)
    if regime is not None:
        takeL &= (regime > 0); takeS &= (regime < 0)   # HTF agreement gate
    raw[takeL] = 1; conf[takeL] = pL[takeL]
    raw[takeS] = -1; conf[takeS] = pS[takeS]
    c = pd.Series(conf, index=index); s = pd.Series(raw, index=index)
    day = pd.Series(pd.DatetimeIndex(index).date, index=index)
    out = pd.Series(0, index=index, dtype=np.int8)
    for _, ix in c.groupby(day.values).groups.items():
        fired = c.loc[ix]; fired = fired[fired > 0]
        if len(fired) == 0: continue
        keep = fired.sort_values(ascending=False).index[:topk]
        out.loc[keep] = s.loc[keep]
    return out


def run(X, sim, days, uniq, cfg, win_R, thr, topk, topn, gate, diag_only=False):
    yL, yS = bin_targets(sim, win_R)
    tr_n, te_n = int(cfg["train_days"]), int(cfg["test_days"])
    is_p=is_d=oos_p=oos_d=oos_b=tr=0
    prec_tp=prec_fp=0
    regcol = "h1_cci100" if "h1_cci100" in X.columns else None
    i = tr_n
    while i + 1 < len(uniq):
        trd=set(uniq[max(0,i-tr_n):i]); ted=set(uniq[i:i+te_n])
        trm=days.isin(trd).values; tem=days.isin(ted).values
        if trm.sum()<3000 or tem.sum()<100: i+=te_n; continue
        featsL = top_feats(X[trm], yL[trm], topn); featsS = top_feats(X[trm], yS[trm], topn)
        mL=new_bin(cfg); mL.fit(X[trm][featsL].values, yL[trm])
        mS=new_bin(cfg); mS.fit(X[trm][featsS].values, yS[trm])
        # OOS precision at thr
        pLte=pwin(mL, X[tem][featsL]); pSte=pwin(mS, X[tem][featsS])
        for p,tru in ((pLte,yL[tem]),(pSte,yS[tem])):
            sel=p>=thr; prec_tp+=int(((sel)&(tru==1)).sum()); prec_fp+=int(((sel)&(tru==0)).sum())
        if not diag_only:
            for dset,dm,isoos in ((trd,trm,False),(ted,tem,True)):
                pL=pwin(mL,X[dm][featsL]); pS=pwin(mS,X[dm][featsS])
                reg = X[dm][regcol].values if (gate and regcol) else None
                sig=sniper(pL,pS,X[dm].index,thr,topk,reg)
                res=bot.run_harness(sig, sim[dm], cfg)
                if isoos: oos_p+=res["pass_days"]; oos_d+=res["trading_days"]; oos_b+=res["dd_breach_days"]; tr+=res["trades"]
                else: is_p+=res["pass_days"]; is_d+=res["trading_days"]
        i+=te_n
    prec = 100.0*prec_tp/max(1,prec_tp+prec_fp)
    IS=100.0*is_p/max(1,is_d); OOS=100.0*oos_p/max(1,oos_d)
    return dict(IS=IS,OOS=OOS,MIN=min(IS,OOS),oos_days=oos_d,oos_pass=oos_p,
                oos_breach=oos_b,trades=tr,precision=prec,picks=prec_tp+prec_fp)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",required=True); ap.add_argument("--topn",type=int,default=30)
    ap.add_argument("--trees",type=int,default=200); ap.add_argument("--diagnose",action="store_true")
    ap.add_argument("--sweep",action="store_true"); ap.add_argument("--gate",action="store_true")
    ap.add_argument("--out",default="pruned_results.json")
    a=ap.parse_args()
    d=joblib.load(a.cache); X,sim=d["X"],d["sim"]
    base=dict(bot.CFG); base["n_estimators"]=a.trees; base["min_samples_leaf"]=200
    days=pd.Series(X.index.date,index=X.index); uniq=np.array(sorted(set(days)))
    print(f"loaded {X.shape} | {len(uniq)} days | topn={a.topn} trees={a.trees} gate={a.gate}", flush=True)

    if a.diagnose:
        for win_R in (0.6,):
            for thr in (0.5,0.6,0.7,0.8):
                r=run(X,sim,days,uniq,base,win_R,thr,2,a.topn,a.gate,diag_only=True)
                print(f"  win_R{win_R} thr{thr}: OOS precision {r['precision']:.1f}% picks {r['picks']}", flush=True)

    if a.sweep:
        grid=dict(win_R=[0.6,1.0],thr=[0.6,0.7,0.8],topk=[1,2],risk_pct=[1.0,1.5,2.0],tp_R=[1.0,1.5])
        keys=list(grid); combos=list(itertools.product(*[grid[k] for k in keys]))
        print(f"=== PRUNED SWEEP topn={a.topn} gate={a.gate}: {len(combos)} configs ===",flush=True)
        rows=[]
        for n,vals in enumerate(combos,1):
            cv=dict(zip(keys,vals)); cfg=dict(base); cfg["tp_R"]=cv["tp_R"]; cfg["risk_pct"]=cv["risk_pct"]
            t=time.time(); r=run(X,sim,days,uniq,cfg,cv["win_R"],cv["thr"],cv["topk"],a.topn,a.gate); r["cfg"]=cv; rows.append(r)
            best=max(rows,key=lambda z:z["MIN"])
            print(f"[{n:3d}/{len(combos)}] IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} MIN {r['MIN']:5.1f} "
                  f"prec {r['precision']:4.1f}% (oos {r['oos_pass']}/{r['oos_days']}d tr {r['trades']} brch {r['oos_breach']}) "
                  f"{int(time.time()-t)}s | BEST {best['MIN']:5.1f} {best['cfg']}",flush=True)
            json.dump(sorted(rows,key=lambda z:z["MIN"],reverse=True)[:15],open(a.out,"w"),indent=2)
        rows.sort(key=lambda z:z["MIN"],reverse=True); b=rows[0]
        print("\n=== TOP 10 BY MIN ===")
        for r in rows[:10]:
            print(f"  MIN {r['MIN']:5.1f} IS {r['IS']:5.1f} OOS {r['OOS']:5.1f} prec {r['precision']:.1f}% oosD {r['oos_days']} {r['cfg']}")
        print(f"\nDONE={'YES' if (b['MIN']>=90 and b['oos_days']>=30) else 'NO'} best MIN {b['MIN']:.1f}%")


if __name__=="__main__":
    main()
