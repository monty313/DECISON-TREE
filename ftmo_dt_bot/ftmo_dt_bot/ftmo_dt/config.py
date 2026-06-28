"""config.py - one place for every tunable. FTMO-safe defaults.

Account size is DYNAMIC: set `account_balance` (default 100_000) or, live, let the
bot read equity from MT5 every loop. All risk is expressed in PERCENT of current
equity, so the same config drives a $10k or a $200k challenge unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json

# Trigger TF first, then context TFs (user-confirmed set; daily dropped).
ACTIVE_TIMEFRAMES = ("1m", "5m", "30m", "4h")
BASE_TF = "1m"

# Per-symbol contract specs for BACKTEST cost/sizing. Live, these are overridden
# by mt5.symbol_info(...). Values are broker-typical; tune to your FTMO server.
SYMBOL_SPECS = {
    # symbol:  point,    digits, contract, tick_size, tick_value($/lot), comm/lot/side, asset_class
    "EURUSD": dict(point=1e-5, digits=5, contract=100_000, tick_size=1e-5, tick_value=1.0, commission=3.0, asset="fx"),
    "GBPUSD": dict(point=1e-5, digits=5, contract=100_000, tick_size=1e-5, tick_value=1.0, commission=3.0, asset="fx"),
    "XAUUSD": dict(point=1e-2, digits=2, contract=100,     tick_size=1e-2, tick_value=1.0, commission=0.0, asset="metal"),
    "US30":   dict(point=1e-1, digits=1, contract=1,       tick_size=1e-1, tick_value=0.1, commission=0.0, asset="index"),
}
DEFAULT_SPEC = dict(point=1e-5, digits=5, contract=100_000, tick_size=1e-5, tick_value=1.0, commission=3.0, asset="fx")


@dataclass
class BotConfig:
    # --- account (dynamic) ---
    account_balance: float = 100_000.0          # starting equity; any size
    account_currency: str = "USD"

    # --- FTMO challenge rules (percent of INITIAL balance) ---
    profit_target_pct: float = 0.10             # Step 1 = 10%, Step 2 (verification) = 0.05
    max_daily_loss_pct: float = 0.05            # hard fail at -5% from day's start equity/balance
    max_total_loss_pct: float = 0.10            # hard fail at -10% from initial balance
    min_trading_days: int = 0                   # FTMO removed the 4-day minimum; set if needed

    # --- risk (user spec) ---
    risk_per_trade_pct: float = 0.0001          # 0.01% of equity at risk per trade
    max_trades_per_day: int = 800               # CAP / safety ceiling, NOT a target
                                                # (selectivity is set by deadband + min_confidence)
    max_concurrent_positions: int = 5
    one_position_per_symbol: bool = True

    # --- internal guards (protect the FTMO walls BEFORE they trigger) ---
    daily_stop_pct: float = 0.03                # stop opening new trades after -3% on the day
    daily_lock_profit_pct: float = 0.02         # after +2% on the day, flatten & stop (lock the green)
    total_stop_pct: float = 0.08                # kill switch at -8% total (buffer to the -10% wall)

    # --- stop / target (ATR units; scalper-tight by default) ---
    atr_period: int = 14
    atr_tf: str = "1m"                          # ATR timeframe used for SL/TP + sizing
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.0
    use_trailing: bool = False
    trail_atr_mult: float = 1.0
    max_hold_bars: int = 30                     # force-exit a scalp after N base-TF bars

    # --- sessions / holding (Normal account = intraday only) ---
    swing_mode: bool = False                    # False = flat before rollover/weekend/news
    trade_sessions_utc: tuple = ((7, 0, 21, 0),)  # (h1,m1,h2,m2) windows in UTC; London+NY
    flat_before_rollover_min: int = 5           # minutes before broker midnight to flatten
    broker_utc_offset: int = 2                  # MT5 server time = UTC + this (FTMO ~ +2/+3 DST)

    # --- labeling (training) ---
    label_horizon_bars: int = 5                 # forward return horizon on the base TF
    deadband_cost_mult: float = 1.5             # flat unless |fwd move| > cost * this multiple
    slippage_points: float = 2.0                # modeled slippage per side, in points

    # --- model / tree ---
    max_depth: int = 6
    min_samples_leaf: int = 200
    min_confidence: float = 0.0                 # leaf-purity gate: only fire +1/-1 when the
                                                # leaf is >= this fraction one class, else 0 (selectivity)
    class_weight: str = "balanced"

    symbols: tuple = ("EURUSD", "GBPUSD", "XAUUSD", "US30")
    timeframes: tuple = ACTIVE_TIMEFRAMES

    def spec(self, symbol: str) -> dict:
        return SYMBOL_SPECS.get(symbol.upper(), DEFAULT_SPEC)

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "BotConfig":
        with open(path) as f:
            d = json.load(f)
        d["trade_sessions_utc"] = tuple(tuple(w) for w in d.get("trade_sessions_utc", ((7,0,21,0),)))
        d["symbols"] = tuple(d.get("symbols", ()))
        d["timeframes"] = tuple(d.get("timeframes", ACTIVE_TIMEFRAMES))
        return cls(**d)


# Convenience presets
def ftmo_step1(balance: float = 100_000.0) -> BotConfig:
    return BotConfig(account_balance=balance, profit_target_pct=0.10)

def ftmo_step2(balance: float = 100_000.0) -> BotConfig:
    return BotConfig(account_balance=balance, profit_target_pct=0.05)


def ftmo_consistent(balance: float = 100_000.0) -> BotConfig:
    """Selectivity-first preset: trade FEWER, higher-conviction setups and bank the
    day green early. 800/day stays only as a safety cap. Tune on your OOS diagnostics."""
    return BotConfig(account_balance=balance, profit_target_pct=0.10,
                     deadband_cost_mult=2.5,        # only label moves that clearly beat costs
                     min_confidence=0.55,           # only fire confident leaves
                     daily_lock_profit_pct=0.015,   # lock the day green at +1.5% and stop
                     max_concurrent_positions=2)
