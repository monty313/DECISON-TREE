"""feature_spec.py - the SINGLE source of truth for the tree's input features.

Every feature is a small ARITHMETIC function of the 44-column vocabulary, so it
is (a) scale-free / symbol-agnostic (distances are in ATR units, oscillators are
already bounded) and (b) identical whether evaluated vectorised (pandas, training)
or scalar (pure-Python, the RL alpha + EA). The getter `g(col, tf)` returns a
pandas Series in training and a float in the alpha -- same code, same numbers.

FEATURES is the ORDERED contract between training and every runtime surface: the
exported tree references features by their index here, so train with EXACTLY this
order. All features derive from existing cached columns (no new indicator), so the
RL observation stays 479/220.
"""
from __future__ import annotations
import numpy as np
try:
    import pandas as pd
    _PD = True
except Exception:
    _PD = False

from .config import ACTIVE_TIMEFRAMES


def div(a, b):
    """Safe divide for Series OR float; 0/non-finite denominator -> NaN."""
    if _PD and (isinstance(a, pd.Series) or isinstance(b, pd.Series)):
        if isinstance(b, pd.Series):
            b = b.where(b != 0)
        elif b == 0:
            b = np.nan
        return a / b
    if b == 0 or not np.isfinite(b) or not np.isfinite(a):
        return float("nan")
    return a / b


def _tf_features(tf):
    """12 features per timeframe. Distances are normalized by BOLLINGER-BAND WIDTH
    (deviation 1.0): BB200 width for the long SMA200 distance, BB20 width for the
    shorter ones. ATR is used ONLY in atrfrac (#10) and for stops/sizing. Widths
    are in price units, so every ratio is scale-free (symbol-agnostic)."""
    return [
        (f"rsi14_{tf}",    lambda g, tf=tf: g("rsi14_raw", tf) - 50.0),
        (f"rsi4_{tf}",     lambda g, tf=tf: g("rsi4_raw", tf) - 50.0),
        (f"cci30_{tf}",    lambda g, tf=tf: g("cci30_raw", tf)),
        (f"cci100_{tf}",   lambda g, tf=tf: g("cci100_raw", tf)),
        (f"d_sma200_{tf}", lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("sma_p200_s0", tf),
                                                g("bb200_dev1.0_upper", tf) - g("bb200_dev1.0_lower", tf))),
        (f"d_sma50_{tf}",  lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("sma_p50_s0", tf),
                                                g("bb20_dev1.0_upper", tf) - g("bb20_dev1.0_lower", tf))),
        (f"d_sma20_{tf}",  lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("bb20_dev1.0_middle", tf),
                                                g("bb20_dev1.0_upper", tf) - g("bb20_dev1.0_lower", tf))),
        (f"bbpctb_{tf}",   lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("bb20_dev2.0_lower", tf),
                                                g("bb20_dev2.0_upper", tf) - g("bb20_dev2.0_lower", tf))),
        (f"fan_{tf}",      lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("sma_p4_s3", tf),
                                                g("bb20_dev1.0_upper", tf) - g("bb20_dev1.0_lower", tf))),
        (f"atrfrac_{tf}",  lambda g, tf=tf: div(g("atr14_raw", tf), g("sma_p1_s0", tf))),
        (f"stack_hi_{tf}", lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("sma4_sh4_high", tf),
                                                g("bb20_dev1.0_upper", tf) - g("bb20_dev1.0_lower", tf))),
        (f"stack_lo_{tf}", lambda g, tf=tf: div(g("sma_p1_s0", tf) - g("sma4_sh4_low", tf),
                                                g("bb20_dev1.0_upper", tf) - g("bb20_dev1.0_lower", tf))),
    ]


def build_feature_funcs(timeframes=ACTIVE_TIMEFRAMES):
    funcs = []
    for tf in timeframes:
        funcs.extend(_tf_features(tf))
    return funcs


FEATURE_FUNCS = build_feature_funcs()
FEATURES = [name for name, _ in FEATURE_FUNCS]          # ordered names (the contract)
N_FEATURES = len(FEATURES)


def eval_features_scalar(getter):
    """Scalar path (alpha/EA): returns a list[float] in FEATURES order."""
    return [fn(getter) for _, fn in FEATURE_FUNCS]
