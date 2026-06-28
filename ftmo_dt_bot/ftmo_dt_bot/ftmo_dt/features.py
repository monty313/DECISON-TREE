"""features.py - causal, leak-free feature matrix from a 1m OHLC frame.

Causality rules (no look-ahead, ever):
  * BASE TF (1m): at the open of bar t we may only use indicators finalised on
    bar t-1, so the 1m indicator frame is shifted by 1 bar.
  * HIGHER TFs: a higher bar is usable only AFTER it closes. We move each higher
    bar to its CLOSE time (open + tf_delta) and merge_asof backward with
    allow_exact_matches=False, so a 4h bar closing at 12:00 is first usable at
    12:01 -- never on the bar it is still forming.
The action price is this bar's OPEN (known at time t). Entry/label/backtest all
use that price, so a signal at t executes at open[t] with no peeking.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import BotConfig, BASE_TF
from .indicators import compute_tf_indicators
from .data_loader import resample_ohlc
from .feature_spec import FEATURE_FUNCS, FEATURES

TF_DELTA = {"1m": pd.Timedelta("1min"), "5m": pd.Timedelta("5min"),
            "30m": pd.Timedelta("30min"), "4h": pd.Timedelta("4h"), "1d": pd.Timedelta("1D")}


def build_raw_columns(df1m: pd.DataFrame, cfg: BotConfig, fast_cci: bool = True) -> pd.DataFrame:
    grid = df1m.index
    parts = []
    for tf in cfg.timeframes:
        ohlc = df1m if tf == BASE_TF else resample_ohlc(df1m, tf)
        ind = compute_tf_indicators(ohlc, fast_cci=fast_cci).add_prefix(f"{tf}__")
        if tf == BASE_TF:
            part = ind.shift(1).reindex(grid)
        else:
            ind = ind.copy()
            ind.index = ind.index + TF_DELTA[tf]                 # -> bar CLOSE time
            ind = ind[~ind.index.duplicated(keep="last")].sort_index()
            L = pd.DataFrame({"time": grid})
            R = ind.reset_index().rename(columns={ind.index.name or "index": "time"})
            m = pd.merge_asof(L, R, on="time", direction="backward", allow_exact_matches=False)
            part = m.set_index("time")
        parts.append(part)
    return pd.concat(parts, axis=1)


def build_feature_matrix(df1m: pd.DataFrame, cfg: BotConfig, fast_cci: bool = True):
    """Return (X, meta): X = features in FEATURES order; meta = entry/atr/spread."""
    raw = build_raw_columns(df1m, cfg, fast_cci=fast_cci)
    g = lambda col, tf: raw[f"{tf}__{col}"]
    X = pd.DataFrame({name: fn(g) for name, fn in FEATURE_FUNCS}, index=raw.index)[FEATURES]
    atr_col = f"{cfg.atr_tf}__atr14_raw"
    meta = pd.DataFrame({
        "entry": df1m["open"],                       # executable price at time t
        "close": df1m["close"],
        "atr": raw[atr_col] if atr_col in raw.columns else np.nan,
        "spread_points": df1m["spread"] if "spread" in df1m.columns else np.nan,
    }, index=raw.index)
    return X, meta
