"""labeling.py - cost-aware 3-class labels {+1 long, -1 short, 0 flat}.

'Flat' is a LEARNED state, not a coin-flip: a bar is labeled directional only if
the forward price move over `label_horizon_bars` clears a dead band sized to the
REAL round-trip cost (per-bar spread from the MT5 feed + commission + slippage),
times `deadband_cost_mult`. This stops the tree learning to trade noise that the
spread would eat -- critical at 800 trades/day.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .config import BotConfig


def round_trip_cost_price(spread_points, spec: dict, cfg: BotConfig) -> "pd.Series|float":
    """Round-trip cost expressed as a PRICE distance (same units as the move)."""
    point = spec["point"]
    sp = spread_points
    if isinstance(sp, pd.Series):
        sp = sp.fillna(np.nan)
    spread_price = sp * point
    slip_price = cfg.slippage_points * point
    # commission ($/lot/side) -> price move that costs the same: $ * tick_size/tick_value
    comm_price = cfg.commission_price(spec) if hasattr(cfg, "commission_price") else \
        spec["commission"] * spec["tick_size"] / spec["tick_value"]
    return spread_price + 2.0 * slip_price + 2.0 * comm_price


def make_labels(meta: pd.DataFrame, cfg: BotConfig, symbol: str) -> pd.Series:
    spec = cfg.spec(symbol)
    H = cfg.label_horizon_bars
    entry = meta["entry"]
    # exit at the close H bars ahead (hold H base-TF bars)
    exit_px = meta["close"].shift(-H)
    fwd_move = exit_px - entry                      # signed price move long-perspective
    cost = round_trip_cost_price(meta["spread_points"], spec, cfg)
    # default spread if the feed had none
    if isinstance(cost, pd.Series):
        cost = cost.fillna((spec["point"] * 10) + 2 * cfg.slippage_points * spec["point"]
                           + 2 * spec["commission"] * spec["tick_size"] / spec["tick_value"])
    band = cost * cfg.deadband_cost_mult
    y = pd.Series(0, index=meta.index, dtype="int8")
    y[fwd_move > band] = 1
    y[fwd_move < -band] = -1
    y[fwd_move.isna()] = 0
    return y
