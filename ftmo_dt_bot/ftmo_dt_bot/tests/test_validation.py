"""test_validation.py - one runnable suite re-proving every guarantee.

Run:  python tests/test_validation.py     (exit code 0 = all pass)
Also importable as pytest tests (test_* functions).
No sklearn required (uses the NumpyCART); validates the WHOLE chain.
"""
import os, sys, importlib.util
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ftmo_dt.config import BotConfig
from ftmo_dt.indicators import compute_tf_indicators, expected_columns, cci, _cci_fast
from ftmo_dt.features import build_feature_matrix
from ftmo_dt.labeling import make_labels
from ftmo_dt.feature_spec import FEATURES, eval_features_scalar, div
from ftmo_dt.tree_model import NumpyCART
from ftmo_dt.export_tree import export_python, export_mql5
from ftmo_dt.backtest import run_backtest


def _synth(days=45, seed=11, px0=1.18, vol0=0.00012):
    np.random.seed(seed); n = days*1440
    idx = pd.date_range("2021-02-01", periods=n, freq="1min", tz="UTC")
    mn = (np.arange(n) % 1440)
    vol = vol0*(1+1.4*np.exp(-((mn-810)/180)**2)+0.8*np.exp(-((mn-480)/120)**2))
    ret = np.random.normal(np.sin(np.arange(n)/2000.)*1e-5, vol); close = px0*np.exp(np.cumsum(ret))
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close)+np.abs(np.random.normal(0, vol*px0))
    lo = np.minimum(op, close)-np.abs(np.random.normal(0, vol*px0))
    spread = np.clip(np.random.normal(8, 3, n), 3, 30).round()
    return pd.DataFrame({"open": op, "high": hi, "low": lo, "close": close, "spread": spread}, index=idx)


def test_indicator_vocab():
    df = _synth(5)
    ind = compute_tf_indicators(df)
    assert ind.shape[1] == 44 and list(ind.columns) == expected_columns()
    assert (_cci_fast(df.high, df.low, df.close, 30) - cci(df.high, df.low, df.close, 30)).abs().max() < 1e-9


def test_no_leak():
    df = _synth(45); cfg = BotConfig()
    X, _ = build_feature_matrix(df, cfg)
    t = 4000; d2 = df.copy()
    for c in ("close", "high", "low"):
        d2.iloc[t+1:, d2.columns.get_loc(c)] *= 1.5
    X2, _ = build_feature_matrix(d2, cfg)
    a = X.iloc[:t+1].to_numpy(); b = X2.iloc[:t+1].to_numpy()
    nan = np.isnan(a) & np.isnan(b)
    assert np.allclose(np.where(nan, 0, a), np.where(nan, 0, b), equal_nan=True)


def test_labels_ternary():
    df = _synth(45); cfg = BotConfig()
    _, meta = build_feature_matrix(df, cfg)
    y = make_labels(meta, cfg, "EURUSD")
    assert set(np.unique(y)).issubset({-1, 0, 1})
    assert 0.05 < (y == 0).mean() < 0.98


def _train_small(cfg):
    df = _synth(45)
    X, meta = build_feature_matrix(df, cfg); y = make_labels(meta, cfg, "EURUSD")
    d = X.copy(); d["y"] = y; d = d.iloc[:-cfg.label_horizon_bars].dropna()
    sp = int(len(d)*0.6); tr = d.iloc[:sp]
    sel = np.random.RandomState(0).choice(len(tr), min(12000, len(tr)), replace=False)
    tree = NumpyCART(cfg.max_depth, cfg.min_samples_leaf).fit(tr[FEATURES].to_numpy()[sel], tr["y"].to_numpy()[sel], FEATURES)
    return df, X, meta, d, sp, tree


def test_freeze_equivalence():
    cfg = BotConfig(); _, X, _, d, sp, tree = _train_small(cfg)
    te = d.iloc[sp:][FEATURES].to_numpy()
    ns = {}; exec(export_python(tree), ns); f = ns["evaluate_tree"]
    assert (tree.predict(te) == np.array([f(list(map(float, r))) for r in te])).all()
    mq = export_mql5(tree); assert mq.count("{") == mq.count("}")


def test_backtest_walls():
    cfg = BotConfig(); df, X, meta, d, sp, tree = _train_small(cfg)
    df = df.assign(_atr=meta["atr"]); ti = d.index[sp:]
    r = run_backtest(df.loc[ti[0]:], X.loc[ti[0]:], tree, cfg, "EURUSD")
    assert np.isfinite(r.equity).all()
    assert r.summary["worst_day_pct"] >= -cfg.max_daily_loss_pct - 1e-6
    bad = BotConfig(risk_per_trade_pct=0.05, daily_stop_pct=0.99, daily_lock_profit_pct=9.0, total_stop_pct=0.99, sl_atr_mult=0.5)
    r2 = run_backtest(df.loc[ti[0]:], X.loc[ti[0]:], tree, bad, "EURUSD")
    assert r2.summary["breach_daily"] or r2.summary["breach_total"]


ALL = [test_indicator_vocab, test_no_leak, test_labels_ternary, test_freeze_equivalence, test_backtest_walls]

if __name__ == "__main__":
    ok = 0
    for t in ALL:
        try:
            t(); print(f"PASS  {t.__name__}"); ok += 1
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{ok}/{len(ALL)} passed")
    sys.exit(0 if ok == len(ALL) else 1)
