"""train.py - orchestrator: CSV -> features -> cost-aware labels -> tree -> freeze.

Trains ONE decision tree (per symbol and/or pooled across symbols) and emits every
runtime surface from the same frozen tree:
  * models/tree_<name>.py        frozen pure-Python evaluator (+ golden rows)
  * models/tree_<name>.npz/json  raw TreeArrays (reload without sklearn)
  * rl_alpha/decision_tree_ftmo_alpha.py (+ register_...py)   RL slot-16 alpha
  * reports/backtest_<name>.json out-of-sample FTMO backtest summary

Backend = sklearn DecisionTreeClassifier if available, else the dependency-free
NumpyCART. Both produce identical TreeArrays, so the frozen surfaces are the same.
Pooled training uses scale-free features, so one tree generalises to ANY broker
symbol (train on the 4 you have, deploy on all).
"""
from __future__ import annotations
import os, json, glob
import numpy as np
import pandas as pd

from .config import BotConfig
from .data_loader import load_mt5_csv
from .features import build_feature_matrix
from .labeling import make_labels
from .feature_spec import FEATURES
from .tree_model import NumpyCART, from_sklearn, TreeArrays
from .export_tree import write_python_module, write_rl_alpha, write_register, write_mql5_ea
from .backtest import run_backtest


def detect_symbol(path: str) -> str:
    base = os.path.basename(path).upper()
    for s in ("XAUUSD", "EURUSD", "GBPUSD", "US30", "US100", "GER40", "USDJPY"):
        if s in base:
            return s
    return base.split("_")[0]


def prepare(df1m: pd.DataFrame, cfg: BotConfig, symbol: str):
    X, meta = build_feature_matrix(df1m, cfg)
    y = make_labels(meta, cfg, symbol)
    df_atr = df1m.assign(_atr=meta["atr"])
    return X, y, df_atr


def fit_tree(X: np.ndarray, y: np.ndarray, cfg: BotConfig, backend="auto") -> tuple[TreeArrays, str]:
    if backend in ("auto", "sklearn"):
        try:
            from sklearn.tree import DecisionTreeClassifier
            clf = DecisionTreeClassifier(max_depth=cfg.max_depth,
                                         min_samples_leaf=cfg.min_samples_leaf,
                                         class_weight=cfg.class_weight, random_state=0)
            clf.fit(X, y)
            t = from_sklearn(clf, FEATURES); t.min_confidence = cfg.min_confidence
            return t, "sklearn"
        except Exception as e:
            if backend == "sklearn":
                raise
            print(f"[train] sklearn unavailable ({e}); using NumpyCART")
    cart = NumpyCART(max_depth=cfg.max_depth, min_samples_leaf=cfg.min_samples_leaf,
                     class_weight=cfg.class_weight)
    t = cart.fit(X, y, FEATURES); t.min_confidence = cfg.min_confidence
    return t, "numpy"


def _clean(X: pd.DataFrame, y: pd.Series, cfg: BotConfig):
    d = X.copy(); d["__y"] = y
    d = d.iloc[:-cfg.label_horizon_bars]          # drop unlabelable tail
    d = d.dropna()
    return d[FEATURES], d["__y"], d.index


def time_split(index, train_frac=0.7, val_frac=0.15):
    n = len(index); a = int(n * train_frac); b = int(n * (train_frac + val_frac))
    return index[:a], index[a:b], index[b:]


def train_from_frames(frames: dict, cfg: BotConfig, out_dir: str, backend="auto",
                      pooled=True, per_symbol=True, max_train=400_000):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "models"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "reports"), exist_ok=True)
    alpha_dir = os.path.join(out_dir, "rl_alpha"); os.makedirs(alpha_dir, exist_ok=True)
    cfg.save(os.path.join(out_dir, "config.json"))

    prepared = {}
    for sym, df in frames.items():
        X, y, df_atr = prepare(df, cfg, sym)
        prepared[sym] = (X, y, df_atr)

    reports = {}

    def _finish(name, Xc, yc, idx, test_index, df_atr_map):
        tree, used = fit_tree(Xc.loc[idx].to_numpy(), yc.loc[idx].to_numpy(), cfg, backend)
        modp = os.path.join(out_dir, "models", f"tree_{name}.py")
        write_python_module(tree, modp, symbol=name,
                            meta=dict(backend=used, depth=tree.depth(), nodes=tree.n_nodes))
        np.savez(os.path.join(out_dir, "models", f"tree_{name}.npz"),
                 feature=tree.feature, threshold=tree.threshold,
                 children_left=tree.children_left, children_right=tree.children_right,
                 value=tree.value, classes=tree.classes,
                 min_confidence=np.array([float(tree.min_confidence)]))
        # OOS backtest per contributing symbol
        summ = {}
        for sym, (Xs, ys, df_atr) in df_atr_map.items():
            ti = test_index.get(sym)
            if ti is None or len(ti) == 0:
                continue
            r = run_backtest(df_atr.loc[ti[0]:], Xs.loc[ti[0]:], tree, cfg, sym)
            summ[sym] = r.summary
            r.equity.to_frame().to_csv(os.path.join(out_dir, "reports", f"equity_{name}_{sym}.csv"))
        with open(os.path.join(out_dir, "reports", f"backtest_{name}.json"), "w") as f:
            json.dump(summ, f, indent=2, default=float)
        return tree, used, summ

    # per-symbol models
    per_sym_test = {}
    for sym, (X, y, df_atr) in prepared.items():
        Xc, yc, idx = _clean(X, y, cfg)
        tr, va, te = time_split(idx)
        train_idx = idx[idx.isin(tr)]
        if len(train_idx) > max_train:
            train_idx = train_idx[np.linspace(0, len(train_idx) - 1, max_train).astype(int)]
        per_sym_test[sym] = te
        if per_symbol:
            tree, used, summ = _finish(sym, Xc, yc, train_idx, {sym: te},
                                       {sym: (X, y, df_atr)})
            reports[sym] = summ
            print(f"[{sym}] backend={used} depth={tree.depth()} nodes={tree.n_nodes} "
                  f"-> OOS {summ.get(sym, {})}")

    # pooled model (train on all symbols' train portions; features are scale-free)
    if pooled and len(prepared) > 1:
        Xparts, yparts = [], []
        test_index = {}; df_atr_map = {}
        for sym, (X, y, df_atr) in prepared.items():
            Xc, yc, idx = _clean(X, y, cfg)
            tr, va, te = time_split(idx)
            ti = idx[idx.isin(tr)]
            if len(ti) > max_train // max(1, len(prepared)):
                ti = ti[np.linspace(0, len(ti) - 1, max_train // len(prepared)).astype(int)]
            Xparts.append(Xc.loc[ti]); yparts.append(yc.loc[ti])
            test_index[sym] = te; df_atr_map[sym] = (X, y, df_atr)
        Xpool = pd.concat(Xparts); ypool = pd.concat(yparts)
        tree, used, summ = _finish("pooled", Xpool, ypool, Xpool.index, test_index, df_atr_map)
        reports["pooled"] = summ
        # the SHIPPED RL alpha + EA-source come from the pooled (generalising) tree
        write_rl_alpha(tree, os.path.join(alpha_dir, "decision_tree_ftmo_alpha.py"), cfg.timeframes)
        write_register(os.path.join(alpha_dir, "register_decision_tree_ftmo_alpha.py"))
        from .export_tree import export_mql5
        with open(os.path.join(out_dir, "models", "EvaluateTree.mqh"), "w") as f:
            f.write(export_mql5(tree))
        ea_dir = os.path.join(out_dir, "ea"); os.makedirs(ea_dir, exist_ok=True)
        write_mql5_ea(tree, os.path.join(ea_dir, "FtmoDecisionTree.mq5"), cfg, cfg.timeframes)
        print(f"[pooled] backend={used} depth={tree.depth()} nodes={tree.n_nodes} -> {summ}")

    with open(os.path.join(out_dir, "reports", "summary.json"), "w") as f:
        json.dump(reports, f, indent=2, default=float)
    return reports


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Train the FTMO decision tree.")
    ap.add_argument("--data", default="./data", help="dir of MT5 CSVs (SYMBOL_M1_*.csv)")
    ap.add_argument("--out", default="./", help="output root")
    ap.add_argument("--backend", default="auto", choices=["auto", "sklearn", "numpy"])
    ap.add_argument("--balance", type=float, default=100_000.0)
    ap.add_argument("--offset", type=int, default=2, help="broker server UTC offset")
    ap.add_argument("--no-pooled", action="store_true")
    args = ap.parse_args()
    cfg = BotConfig(account_balance=args.balance, broker_utc_offset=args.offset)
    paths = sorted(glob.glob(os.path.join(args.data, "*.csv")))
    if not paths:
        raise SystemExit(f"no CSVs in {args.data}")
    frames = {}
    for p in paths:
        sym = detect_symbol(p)
        print(f"loading {sym} <- {os.path.basename(p)}")
        frames[sym] = load_mt5_csv(p, broker_utc_offset=args.offset)
    train_from_frames(frames, cfg, args.out, backend=args.backend, pooled=not args.no_pooled)


if __name__ == "__main__":
    main()
