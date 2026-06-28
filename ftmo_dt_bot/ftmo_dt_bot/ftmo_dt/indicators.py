"""indicators.py - the 44-column indicator vocabulary, per timeframe.

Reproduces the RL project's cached-indicator vocabulary EXACTLY (names + maths)
using pure numpy/pandas (TA-Lib-equivalent formulas), so a tree trained here is
valid when wrapped as RL alpha slot 16 (same columns via ctx.ind(col, tf)).

Per-TF make-up of the 44 columns (matches ALPHAS.md):
    6  SMA   : sma_p1_s0, sma_p2_s1, sma_p3_s2, sma_p4_s3, sma_p50_s0, sma_p200_s0
    4  extra : sma_p30_s0, sma_p1_s1, sma4_sh4_high, sma4_sh4_low
    4  CCI   : cci30_raw, cci100_raw, cci30_sma2sh4, cci100_sma2sh4
    4  RSI   : rsi4_raw, rsi14_raw, rsi4_sma2sh2, rsi14_sma2sh2
    2  ATR   : atr14_raw, atr14_sma2sh4
    24 BB    : bb{20,200}_dev{0.5,1.0,2.0,4.0}_{upper,middle,lower}
    = 44
"""
from __future__ import annotations
import numpy as np
import pandas as pd

TIMEFRAMES = ("1m", "5m", "30m", "4h", "1d")
BB_PERIODS = (20, 200)
BB_DEVS = (0.5, 1.0, 2.0, 4.0)
CCI_PERIODS = (30, 100)
RSI_PERIODS = (4, 14)
ATR_PERIOD = 14
RESAMPLE_RULE = {"1m": "1min", "5m": "5min", "30m": "30min", "4h": "4h", "1d": "1D"}


def sma(series, period, shift=0):
    out = series.rolling(window=period, min_periods=period).mean()
    return out.shift(shift) if shift else out


def rsi(close, period):
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out[avg_loss == 0.0] = 100.0
    return out


def atr(high, low, close, period=ATR_PERIOD):
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def cci(high, low, close, period):
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mad = tp.rolling(window=period, min_periods=period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma_tp) / (0.015 * mad)


def bbands(close, period, dev):
    mid = close.rolling(window=period, min_periods=period).mean()
    sd = close.rolling(window=period, min_periods=period).std(ddof=0)
    return mid + dev * sd, mid, mid - dev * sd


def _cci_fast(high, low, close, period):
    tp = (high + low + close) / 3.0
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    vals = tp.to_numpy(dtype=np.float64)
    n = vals.size
    mad = np.full(n, np.nan)
    if n >= period:
        try:
            from numpy.lib.stride_tricks import sliding_window_view as _swv
            chunk = max(1, int(4_000_000 / period))
            start = period - 1
            for lo_i in range(start, n, chunk):
                hi_i = min(lo_i + chunk, n)
                win = _swv(vals[lo_i - period + 1: hi_i], period)
                mad[lo_i:hi_i] = np.abs(win - win.mean(axis=1, keepdims=True)).mean(axis=1)
        except Exception:
            mad_s = tp.rolling(period, min_periods=period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
            return (tp - sma_tp) / (0.015 * mad_s)
    return (tp - sma_tp) / (0.015 * pd.Series(mad, index=tp.index))


def compute_tf_indicators(df, fast_cci=True):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    out = {}
    out["sma_p1_s0"] = c.copy()
    out["sma_p2_s1"] = sma(c, 2, 1)
    out["sma_p3_s2"] = sma(c, 3, 2)
    out["sma_p4_s3"] = sma(c, 4, 3)
    out["sma_p50_s0"] = sma(c, 50)
    out["sma_p200_s0"] = sma(c, 200)
    out["sma_p30_s0"] = sma(c, 30)
    out["sma_p1_s1"] = c.shift(1)
    out["sma4_sh4_high"] = sma(h, 4, 4)
    out["sma4_sh4_low"] = sma(l, 4, 4)
    for p in CCI_PERIODS:
        raw = _cci_fast(h, l, c, p) if fast_cci else cci(h, l, c, p)
        out[f"cci{p}_raw"] = raw
        out[f"cci{p}_sma2sh4"] = sma(raw, 2, 4)
    for p in RSI_PERIODS:
        raw = rsi(c, p)
        out[f"rsi{p}_raw"] = raw
        out[f"rsi{p}_sma2sh2"] = sma(raw, 2, 2)
    a = atr(h, l, c, ATR_PERIOD)
    out["atr14_raw"] = a
    out["atr14_sma2sh4"] = sma(a, 2, 4)
    for p in BB_PERIODS:
        for x in BB_DEVS:
            up, mid, lo = bbands(c, p, x)
            tag = f"bb{p}_dev{x:.1f}"
            out[f"{tag}_upper"] = up
            out[f"{tag}_middle"] = mid
            out[f"{tag}_lower"] = lo
    frame = pd.DataFrame(out, index=df.index)
    assert frame.shape[1] == 44, f"expected 44 columns, got {frame.shape[1]}"
    return frame


def expected_columns():
    cols = ["sma_p1_s0", "sma_p2_s1", "sma_p3_s2", "sma_p4_s3", "sma_p50_s0", "sma_p200_s0",
            "sma_p30_s0", "sma_p1_s1", "sma4_sh4_high", "sma4_sh4_low"]
    for p in CCI_PERIODS:
        cols += [f"cci{p}_raw", f"cci{p}_sma2sh4"]
    for p in RSI_PERIODS:
        cols += [f"rsi{p}_raw", f"rsi{p}_sma2sh2"]
    cols += ["atr14_raw", "atr14_sma2sh4"]
    for p in BB_PERIODS:
        for x in BB_DEVS:
            tag = f"bb{p}_dev{x:.1f}"
            cols += [f"{tag}_upper", f"{tag}_middle", f"{tag}_lower"]
    return cols
