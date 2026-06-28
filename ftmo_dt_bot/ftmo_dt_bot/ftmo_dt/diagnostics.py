"""diagnostics.py - "is the tree actually learning, or curve-fitting noise?"

The bottom line is always OUT-OF-SAMPLE, AFTER costs. These tools answer it from
several angles and roll them into one plain-English scorecard:

  1. holdout_oos      - real OOS profit factor / return (the headline).
  2. shuffle_null     - retrain on SHUFFLED labels. If the real OOS edge is no
                        better than shuffled, the "edge" is curve-fit luck.
  3. walk_forward     - fold-by-fold OOS across time. Real edge is CONSISTENT,
                        not one lucky window.
  4. learning_curve   - OOS vs training size. Learning curves improve/plateau;
                        noise-fitting degrades or stays flat at break-even.
  5. feature_importance - which features the tree leans on (sanity / story).
  6. overfit gap      - train PF >> OOS PF means it memorised.

A model is "learning" when real OOS PF > 1 after costs, clearly beats the shuffle
null, and stays positive across most walk-forward folds.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import BotConfig
from .features import build_feature_matrix
from .labeling import make_labels
from .feature_spec import FEATURES
from .train import fit_tree
from .backtest import run_backtest


# ---------- data prep ----------
def prepare_xy(df1m, cfg: BotConfig, symbol: str):
    X, meta = build_feature_matrix(df1m, cfg)
    y = make_labels(meta, cfg, symbol)
    d = X.copy(); d["__y"] = y
    d = d.iloc[:-cfg.label_horizon_bars]
    cidx = d.dropna().index
    return dict(X=X, meta=meta, df_atr=df1m.assign(_atr=meta["atr"]), y=y, cidx=cidx, symbol=symbol)


def _subsample(idx, max_train):
    if len(idx) > max_train:
        return idx[np.linspace(0, len(idx) - 1, max_train).astype(int)]
    return idx


def _fit(pre, cfg, idx, backend, max_train):
    idx = _subsample(pd.DatetimeIndex(idx), max_train)
    tree, used = fit_tree(pre["X"].loc[idx].to_numpy(), pre["y"].loc[idx].to_numpy(), cfg, backend)
    return tree


def _oos(pre, tree, cfg, tindex):
    tindex = pd.DatetimeIndex(tindex)
    if len(tindex) == 0:
        return None
    r = run_backtest(pre["df_atr"].loc[tindex[0]:tindex[-1]],
                     pre["X"].loc[tindex[0]:tindex[-1]], tree, cfg, pre["symbol"])
    return r.summary


# ---------- 1. holdout ----------
def holdout_oos(df1m, cfg, symbol, backend="auto", train_frac=0.7, max_train=80000):
    pre = prepare_xy(df1m, cfg, symbol)
    c = pre["cidx"]; sp = int(len(c) * train_frac)
    tr, te = c[:sp], c[sp:]
    tree = _fit(pre, cfg, tr, backend, max_train)
    oos = _oos(pre, tree, cfg, te)
    ins = _oos(pre, tree, cfg, tr)                 # in-sample backtest (overfit gauge)
    sig = oos_signal_stats(tree, pre, te)
    return dict(tree=tree, oos=oos, insample=ins, signal=sig, pre=pre, train=tr, test=te)


def oos_signal_stats(tree, pre, te):
    te = pd.DatetimeIndex(te)
    Xte = pre["X"].loc[te]; yte = pre["y"].loc[te]
    arr = Xte.to_numpy(float); fin = np.isfinite(arr).all(axis=1)
    pred = np.zeros(len(arr), int); pred[fin] = tree.predict(arr[fin])
    y = yte.to_numpy()
    active = (pred != 0)
    both = active & (y != 0)
    return dict(coverage=float(active.mean()),
                dir_hit=float((np.sign(pred[both]) == np.sign(y[both])).mean()) if both.any() else float("nan"),
                three_acc=float((pred[fin] == y[fin]).mean()) if fin.any() else float("nan"))


# ---------- 2. shuffle null ----------
def shuffle_null(df1m, cfg, symbol, backend="auto", n_repeats=3, train_frac=0.7, max_train=80000, seed=0):
    pre = prepare_xy(df1m, cfg, symbol)
    c = pre["cidx"]; sp = int(len(c) * train_frac); tr, te = c[:sp], c[sp:]
    rets, pfs = [], []
    for i in range(n_repeats):
        ysh = pre["y"].copy()
        ysh.loc[tr] = pre["y"].loc[tr].sample(frac=1.0, random_state=seed + i).values
        idx = _subsample(pd.DatetimeIndex(tr), max_train)
        tree, _ = fit_tree(pre["X"].loc[idx].to_numpy(), ysh.loc[idx].to_numpy(), cfg, backend)
        s = _oos(pre, tree, cfg, te)
        if s: rets.append(s["total_return"]); pfs.append(min(s["profit_factor"], 5.0))
    return dict(mean_return=float(np.mean(rets)) if rets else 0.0,
                mean_PF=float(np.nanmean(pfs)) if pfs else 0.0, returns=rets)


# ---------- 3. walk-forward ----------
def walk_forward(df1m, cfg, symbol, n_folds=5, backend="auto", scheme="expanding", max_train=80000):
    pre = prepare_xy(df1m, cfg, symbol)
    blocks = np.array_split(pre["cidx"].to_numpy(), n_folds + 1)
    rows = []
    for k in range(1, n_folds + 1):
        tr = np.concatenate(blocks[:k]) if scheme == "expanding" else blocks[k - 1]
        te = pd.DatetimeIndex(blocks[k])
        tree = _fit(pre, cfg, tr, backend, max_train)
        s = _oos(pre, tree, cfg, te)
        if s:
            rows.append(dict(fold=k, train=len(tr), test=len(te), ret=s["total_return"],
                             PF=round(min(s["profit_factor"], 9.99), 3), win=round(s["win_rate"], 3),
                             trades=s["n_trades"], maxDD=round(s["max_drawdown"], 4),
                             worst_day=round(s["worst_day_pct"], 4)))
    wf = pd.DataFrame(rows)
    agg = dict(folds=len(wf), pos_folds=int((wf["ret"] > 0).sum()) if len(wf) else 0,
               pf_gt1=int((wf["PF"] > 1).sum()) if len(wf) else 0,
               mean_ret=float(wf["ret"].mean()) if len(wf) else 0.0,
               std_ret=float(wf["ret"].std()) if len(wf) else 0.0)
    return wf, agg


# ---------- 4. learning curve ----------
def learning_curve(df1m, cfg, symbol, fractions=(0.25, 0.5, 0.75, 1.0), backend="auto", max_train=80000):
    pre = prepare_xy(df1m, cfg, symbol)
    c = pre["cidx"]; sp = int(len(c) * 0.7); tr, te = c[:sp], c[sp:]
    out = []
    for fr in fractions:
        n = max(500, int(len(tr) * fr)); sub = tr[-n:]
        tree = _fit(pre, cfg, sub, backend, max_train)
        s = _oos(pre, tree, cfg, te)
        out.append(dict(frac=fr, train_rows=n, oos_ret=s["total_return"] if s else 0.0,
                        oos_PF=round(min(s["profit_factor"], 9.99), 3) if s else 0.0))
    return pd.DataFrame(out)


# ---------- 5. feature importance ----------
def feature_importance(tree, top=15):
    val = tree.value; w = val.sum(axis=1)
    def gini(v):
        s = v.sum()
        return 0.0 if s <= 0 else 1.0 - ((v / s) ** 2).sum()
    imp = np.zeros(len(tree.feature_names))
    for nd in range(tree.n_nodes):
        l, r = tree.children_left[nd], tree.children_right[nd]
        if l == -1: continue
        imp[tree.feature[nd]] += w[nd] * gini(val[nd]) - w[l] * gini(val[l]) - w[r] * gini(val[r])
    if imp.sum() > 0: imp = imp / imp.sum()
    order = np.argsort(-imp)
    return pd.DataFrame([(tree.feature_names[i], round(float(imp[i]), 4)) for i in order[:top]],
                        columns=["feature", "importance"])


# ---------- parameter sweep ----------
def param_sweep(df1m, cfg, symbol, grid=None, backend="auto", max_train=60000):
    if grid is None:
        grid = dict(max_depth=[4, 6, 8], min_samples_leaf=[100, 300], deadband_cost_mult=[1.0, 1.5, 2.5])
    import itertools
    keys = list(grid); cache = {}
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        c = BotConfig(**{**cfg.__dict__}); 
        for k, v in zip(keys, combo): setattr(c, k, v)
        lab_key = (c.deadband_cost_mult, c.label_horizon_bars)
        if lab_key not in cache: cache[lab_key] = prepare_xy(df1m, c, symbol)
        pre = cache[lab_key]
        cc = pre["cidx"]; sp = int(len(cc) * 0.7); tr, te = cc[:sp], cc[sp:]
        tree = _fit(pre, c, tr, backend, max_train)
        oos = _oos(pre, tree, c, te); ins = _oos(pre, tree, c, tr)
        rows.append(dict(**{k: v for k, v in zip(keys, combo)},
                         oos_PF=round(min(oos["profit_factor"], 9.99), 3) if oos else 0,
                         oos_ret=round(oos["total_return"], 4) if oos else 0,
                         train_PF=round(min(ins["profit_factor"], 9.99), 3) if ins else 0,
                         trades=oos["n_trades"] if oos else 0))
    df = pd.DataFrame(rows).sort_values("oos_PF", ascending=False).reset_index(drop=True)
    return df


# ---------- the scorecard ----------
def learning_scorecard(df1m, cfg, symbol, backend="auto", n_folds=5, verbose=True):
    h = holdout_oos(df1m, cfg, symbol, backend)
    null = shuffle_null(df1m, cfg, symbol, backend, n_repeats=3)
    wf, agg = walk_forward(df1m, cfg, symbol, n_folds=n_folds, backend=backend)
    fi = feature_importance(h["tree"], top=8)
    oos = h["oos"]; ins = h["insample"]
    real_pf = min(oos["profit_factor"], 9.99); null_pf = null["mean_PF"]
    train_pf = min(ins["profit_factor"], 9.99) if ins else float("nan")
    checks = {
        "OOS profit factor > 1 (after costs)": real_pf > 1.0,
        "Beats shuffled-label null": (oos["total_return"] > max(0.0, null["mean_return"])) and (real_pf > 1.15 * max(null_pf, 1e-9)),
        "Walk-forward majority positive": agg["folds"] and agg["pos_folds"] >= np.ceil(agg["folds"] / 2),
        "Not badly overfit (train PF < 2x OOS PF)": (train_pf < 2.0 * real_pf) if real_pf > 0 else False,
        "Directional hit-rate > 50% OOS": (h["signal"]["dir_hit"] > 0.5) if h["signal"]["dir_hit"] == h["signal"]["dir_hit"] else False,
    }
    score = sum(bool(v) for v in checks.values())
    verdict = ("LEARNING - real, consistent OOS edge" if score >= 4 else
               "MAYBE - weak/borderline; tune or get more data" if score == 3 else
               "NOT LEARNING - looks like noise after costs")
    if verbose:
        print(f"=== LEARNING SCORECARD: {symbol} ===")
        print(f"  OOS  : PF={real_pf:.2f}  ret={oos['total_return']:+.3%}  trades={oos['n_trades']}  "
              f"win={oos['win_rate']:.1%}  maxDD={oos['max_drawdown']:.2%}")
        print(f"  Null : shuffled-label OOS PF={null_pf:.2f}  ret={null['mean_return']:+.3%}  (real should clearly beat this)")
        print(f"  WF   : {agg['pos_folds']}/{agg['folds']} folds positive, {agg['pf_gt1']}/{agg['folds']} folds PF>1, "
              f"meanRet={agg['mean_ret']:+.3%} (std {agg['std_ret']:.3%})")
        print(f"  Fit  : train PF={train_pf:.2f} vs OOS PF={real_pf:.2f}  | OOS dir-hit={h['signal']['dir_hit']:.1%} "
              f"cover={h['signal']['coverage']:.1%}")
        print("  Checks:")
        for k, v in checks.items():
            print(f"    [{'x' if v else ' '}] {k}")
        print(f"  >>> VERDICT: {verdict}  ({score}/5)")
        print("  Top features:", ", ".join(f"{r.feature}={r.importance}" for r in fi.itertuples()))
    return dict(checks=checks, score=score, verdict=verdict, oos=oos, null=null, wf=wf, agg=agg, importance=fi)


# ---- signal-quality report: "how well are the +1/-1/0 signals doing?" --------
def signal_report(df1m, cfg, symbol, backend="auto", train_frac=0.7, max_train=80000, verbose=True):
    """Evaluate the SIGNAL itself (not just the equity curve): does +1/-1/0 predict
    the cost-aware outcome, and does acting on each signal make money after costs?

    Reports, in-sample AND out-of-sample:
      coverage      - % of bars the signal fires (vs sits flat)
      precision     - when it says LONG, how often the label was actually long? (and short)
      dir_hit       - among active, fraction with correct direction
      exp_bps       - average net-of-cost edge PER FIRED SIGNAL, in bps of price
                      (= sign * forward move - round-trip cost). >0 means the
                      signal is economically positive before sizing/management.
      confusion     - pred {-1,0,+1} vs cost-aware label {-1,0,+1}
    """
    import numpy as np, pandas as pd
    from .labeling import round_trip_cost_price
    pre = prepare_xy(df1m, cfg, symbol)
    c = pre["cidx"]; sp = int(len(c) * train_frac); tr, te = c[:sp], c[sp:]
    tree = _fit(pre, cfg, tr, backend, max_train)

    spec = cfg.spec(symbol); H = cfg.label_horizon_bars
    meta = pre["meta"]; entry = meta["entry"]; fwd = meta["close"].shift(-H) - entry
    cost = round_trip_cost_price(meta["spread_points"], spec, cfg)
    if hasattr(cost, "fillna"):
        cost = cost.fillna(spec["point"] * 10)

    def stats(idx):
        idx = pd.DatetimeIndex(idx)
        X = pre["X"].loc[idx].to_numpy(float); fin = np.isfinite(X).all(axis=1)
        pred = np.zeros(len(idx), int); pred[fin] = tree.predict(X[fin])
        y = pre["y"].loc[idx].to_numpy()
        f = fwd.loc[idx].to_numpy()
        cst = cost.loc[idx].to_numpy() if hasattr(cost, "loc") else np.full(len(idx), float(cost))
        ent = entry.loc[idx].to_numpy()
        active = pred != 0
        net = pred * f - np.where(active, cst, 0.0)
        net_bps = np.where(ent > 0, net / ent * 1e4, np.nan)
        both = active & (y != 0)
        conf = {(pv, yv): int(np.sum((pred == pv) & (y == yv))) for pv in (-1, 0, 1) for yv in (-1, 0, 1)}
        return dict(
            n=int(len(idx)), coverage=float(active.mean()),
            long_rate=float((pred == 1).mean()), short_rate=float((pred == -1).mean()),
            prec_long=float(np.mean(y[pred == 1] == 1)) if (pred == 1).any() else float("nan"),
            prec_short=float(np.mean(y[pred == -1] == -1)) if (pred == -1).any() else float("nan"),
            dir_hit=float(np.mean(np.sign(pred[both]) == np.sign(y[both]))) if both.any() else float("nan"),
            exp_bps=float(np.nanmean(net_bps[active])) if active.any() else 0.0,
            n_active=int(active.sum()), conf=conf,
        )

    oos = stats(te); ins = stats(tr)
    if verbose:
        def line(tag, s):
            print(f"  {tag}: cover={s['coverage']:.1%}  precL={s['prec_long']:.1%}  precS={s['prec_short']:.1%}  "
                  f"dir_hit={s['dir_hit']:.1%}  exp/signal={s['exp_bps']:+.2f} bps  (n_active={s['n_active']})")
        print(f"=== SIGNAL REPORT: {symbol} ===")
        line("IN-SAMPLE ", ins); line("OUT-SAMPLE", oos)
        print("  OOS confusion (rows=signal, cols=actual label):")
        print("            actual:-1   0   +1")
        for pv in (1, 0, -1):
            r = oos["conf"]
            print(f"     signal {pv:+d}: {r[(pv,-1)]:7d} {r[(pv,0)]:5d} {r[(pv,1)]:5d}")
        good = (oos["exp_bps"] > 0) and (np.nanmax([oos["prec_long"], oos["prec_short"]]) > 0.40)
        print(f"  >>> OOS net-of-cost expectancy per signal: {oos['exp_bps']:+.2f} bps  "
              f"-> {'POSITIVE (signals add value)' if oos['exp_bps']>0 else 'NEGATIVE (noise/over-trading after costs)'}")
    return dict(oos=oos, insample=ins, tree=tree)
