"""data_loader.py - robust loader for MetaTrader5-exported bar CSVs.

Handles the standard MT5 'Export Bars' format and common variants:
    <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
    2021.01.13  11:30:00  1.21500  1.21520  1.21490  1.21510  123  0  12
Auto-detects delimiter (tab/comma/semicolon), strips <> from headers, parses
DATE+TIME into a single UTC index, and keeps the per-bar SPREAD (in points) so
costs can be modeled from the real feed rather than estimated.

NOTE on time: MT5 bar timestamps are SERVER time (broker), and label the bar's
OPEN. We convert to UTC with `broker_utc_offset` and keep the open-time index;
the feature pipeline handles causal alignment (a bar is only 'known' at its close).
"""
from __future__ import annotations
import io, csv
import numpy as np
import pandas as pd

_COLMAP = {
    "date": "date", "time": "time",
    "open": "open", "high": "high", "low": "low", "close": "close",
    "tickvol": "tick_volume", "vol": "real_volume", "volume": "tick_volume",
    "spread": "spread",
}


def _sniff_sep(sample: str) -> str:
    for sep in ("\t", ";", ","):
        if sep in sample:
            return sep
    return "\t"


def load_mt5_csv(path: str, broker_utc_offset: int = 2, nrows: int | None = None) -> pd.DataFrame:
    """Return a 1-minute OHLC(+spread) DataFrame indexed by UTC bar-open time."""
    with open(path, "r", errors="ignore") as f:
        head = f.readline()
    sep = _sniff_sep(head)
    df = pd.read_csv(path, sep=sep, nrows=nrows, dtype=str, engine="python")
    # normalise headers: strip <>, lower, trim
    df.columns = [c.strip().strip("<>").lower() for c in df.columns]
    df = df.rename(columns={c: _COLMAP.get(c, c) for c in df.columns})

    if "date" not in df.columns:
        raise ValueError(f"no DATE column found; headers were {list(df.columns)}")
    # time may be missing on some daily exports
    tcol = df["time"] if "time" in df.columns else "00:00:00"
    dt = pd.to_datetime(df["date"].str.replace(".", "-", regex=False) + " " + (tcol if isinstance(tcol, str) else tcol.fillna("00:00:00")),
                        errors="coerce", utc=False)
    df.index = dt
    for c in ("open", "high", "low", "close", "spread", "tick_volume", "real_volume"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    keep = [c for c in ("open", "high", "low", "close", "tick_volume", "spread") if c in df.columns]
    df = df[keep].dropna(subset=["open", "high", "low", "close"]).sort_index()
    # server -> UTC
    if broker_utc_offset:
        df.index = df.index - pd.Timedelta(hours=broker_utc_offset)
    df.index = df.index.tz_localize("UTC")
    df.index.name = "time"
    if "spread" not in df.columns:
        df["spread"] = np.nan      # caller falls back to a per-symbol default spread
    return df


def resample_ohlc(df1m: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample the 1m frame to `tf` using MT5 bar-open-time convention."""
    from .indicators import RESAMPLE_RULE
    rule = RESAMPLE_RULE[tf]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "tick_volume" in df1m.columns:
        agg["tick_volume"] = "sum"
    if "spread" in df1m.columns:
        agg["spread"] = "mean"
    out = df1m.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open", "high", "low", "close"])
    return out
