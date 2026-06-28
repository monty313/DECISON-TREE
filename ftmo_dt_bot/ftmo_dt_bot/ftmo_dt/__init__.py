"""ftmo_dt - Decision-tree trading bot for the FTMO Challenge (MT5).

One tree, three surfaces:
  A) standalone research/backtest + live MT5 Python bot,
  B) MQL5 Expert Advisor (transpiled tree) for native/VPS live execution,
  C) RL alpha (slot 16) that drops into the locked RL contract.

The indicator vocabulary/naming in indicators.py mirrors the RL project's
44-column cache so the SAME frozen tree is valid in all three surfaces.
"""
__version__ = "0.1.0"
