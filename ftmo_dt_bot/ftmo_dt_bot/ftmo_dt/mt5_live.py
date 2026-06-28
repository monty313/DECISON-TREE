"""mt5_live.py - live trading bot on MetaTrader5 (Python bridge).

Reuses the EXACT same feature pipeline as training/backtest (ftmo_dt.features),
so live signals match the research surface bar-for-bar. Loads the frozen tree
module (models/tree_<name>.py) and applies the identical FTMO risk guards the
backtest enforces. Account size is read live, so it adapts to any challenge size.

Run (on a Windows box with the MT5 terminal + `pip install MetaTrader5`):
    python -m ftmo_dt.mt5_live --symbol EURUSD --model models/tree_pooled.py
Nothing here trades by itself until you start it; review inputs first.
"""
from __future__ import annotations
import argparse, importlib.util, time, math
import numpy as np
import pandas as pd

from .config import BotConfig
from .features import build_feature_matrix

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None          # importable without the package; run() will require it


def load_frozen(model_path: str):
    spec = importlib.util.spec_from_file_location("frozen_tree", model_path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.evaluate_tree, m.FEATURES


def rates_to_df(rates, offset: int) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s") - pd.Timedelta(hours=offset)
    df = df.set_index("time"); df.index = df.index.tz_localize("UTC")
    out = pd.DataFrame({"open": df["open"], "high": df["high"], "low": df["low"],
                        "close": df["close"],
                        "spread": df["spread"] if "spread" in df else np.nan}, index=df.index)
    return out


class Mt5Bot:
    def __init__(self, symbol: str, model_path: str, cfg: BotConfig, warmup_bars=70000):
        self.symbol = symbol; self.cfg = cfg; self.warmup = warmup_bars
        self.evaluate_tree, self.FEATURES = load_frozen(model_path)
        self.init_balance = None; self.day_start_eq = None; self.cur_day = None
        self.trades_today = 0; self.day_blocked = False; self.killed = False
        self.last_bar = None

    # --- account / data ---
    def equity(self): return mt5.account_info().equity
    def balance(self): return mt5.account_info().balance

    def fetch(self):
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, self.warmup)
        return rates_to_df(rates, self.cfg.broker_utc_offset)

    def server_day(self, ts):
        return (ts + pd.Timedelta(hours=self.cfg.broker_utc_offset)).normalize()

    def in_session(self, ts):
        m = ts.hour * 60 + ts.minute
        for (h1, m1, h2, m2) in self.cfg.trade_sessions_utc:
            if h1*60+m1 <= m < h2*60+m2: return True
        return False

    # --- one decision per closed bar ---
    def step(self):
        df = self.fetch()
        if len(df) < 300: return
        last_ts = df.index[-1]
        if last_ts == self.last_bar: return
        self.last_bar = last_ts
        eq = self.equity()
        if self.init_balance is None:
            self.init_balance = self.balance(); self.day_start_eq = eq; self.cur_day = self.server_day(last_ts)
        # rollover
        d = self.server_day(last_ts)
        if d != self.cur_day:
            self.cur_day = d; self.day_start_eq = eq; self.trades_today = 0; self.day_blocked = False
        day_pl = (eq - self.day_start_eq) / max(self.day_start_eq, 1e-9)
        # FTMO walls + guards
        if eq <= self.day_start_eq*(1-self.cfg.max_daily_loss_pct): self._flatten("daily_wall"); self.day_blocked=True; return
        if eq <= self.init_balance*(1-self.cfg.max_total_loss_pct): self._flatten("total_wall"); self.killed=True; return
        if day_pl <= -self.cfg.daily_stop_pct: self.day_blocked = True
        if day_pl >= self.cfg.daily_lock_profit_pct: self._flatten("daily_lock"); self.day_blocked = True
        if eq <= self.init_balance*(1-self.cfg.total_stop_pct): self.killed = True

        self._manage(last_ts)
        if self.killed or self.day_blocked or self._has_position(): return
        if self.trades_today >= self.cfg.max_trades_per_day: return
        if not self.in_session(last_ts): return

        X, meta = build_feature_matrix(df, self.cfg)
        x = X.iloc[-1].to_numpy(float)
        if not np.isfinite(x).all(): return            # warm-up -> abstain
        s = self.evaluate_tree(list(map(float, x)))
        if s == 0: return
        atr = float(meta["atr"].iloc[-1])
        if not (atr > 0): return
        self._enter(s, atr)

    # --- execution ---
    def _has_position(self):
        pos = mt5.positions_get(symbol=self.symbol)
        return bool(pos) and any(p.magic == 16016 for p in pos)

    def _lots(self, atr):
        info = mt5.symbol_info(self.symbol)
        risk_cash = self.cfg.risk_per_trade_pct * self.equity()
        sl_dist = self.cfg.sl_atr_mult * atr
        per_lot = sl_dist / info.trade_tick_size * info.trade_tick_value
        lots = risk_cash / max(per_lot, 1e-9)
        step = info.volume_step
        lots = math.floor(lots/step)*step
        return max(info.volume_min, min(info.volume_max, lots))

    def _enter(self, direction, atr):
        info = mt5.symbol_info_tick(self.symbol)
        lots = self._lots(atr)
        if lots <= 0: return
        sl_d = self.cfg.sl_atr_mult*atr; tp_d = self.cfg.tp_atr_mult*atr
        if direction > 0:
            price = info.ask; sl = price-sl_d; tp = price+tp_d; otype = mt5.ORDER_TYPE_BUY
        else:
            price = info.bid; sl = price+sl_d; tp = price-tp_d; otype = mt5.ORDER_TYPE_SELL
        req = dict(action=mt5.TRADE_ACTION_DEAL, symbol=self.symbol, volume=lots, type=otype,
                   price=price, sl=sl, tp=tp, deviation=int(self.cfg.slippage_points),
                   magic=16016, comment="dt_ftmo", type_filling=mt5.ORDER_FILLING_FOK)
        r = mt5.order_send(req)
        if r and r.retcode == mt5.TRADE_RETCODE_DONE: self.trades_today += 1

    def _manage(self, ts):
        if not self._has_position(): return
        near_roll = (ts.hour*60+ts.minute) >= 1440-self.cfg.flat_before_rollover_min
        if (not self.cfg.swing_mode) and (not self.in_session(ts) or near_roll):
            self._flatten("session_flat"); return
        for p in mt5.positions_get(symbol=self.symbol) or []:
            if p.magic == 16016 and (time.time()-p.time) >= self.cfg.max_hold_bars*60:
                self._close_ticket(p)

    def _flatten(self, why=""):
        for p in (mt5.positions_get(symbol=self.symbol) or []):
            if p.magic == 16016: self._close_ticket(p)

    def _close_ticket(self, p):
        tick = mt5.symbol_info_tick(self.symbol)
        otype = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
        mt5.order_send(dict(action=mt5.TRADE_ACTION_DEAL, symbol=self.symbol, volume=p.volume,
                            type=otype, position=p.ticket, price=price,
                            deviation=int(self.cfg.slippage_points), magic=16016,
                            type_filling=mt5.ORDER_FILLING_FOK))


def run(symbol, model_path, cfg, login=None, password=None, server=None, poll=5.0):
    if mt5 is None:
        raise SystemExit("MetaTrader5 package not installed (Windows + `pip install MetaTrader5`).")
    assert mt5.initialize(login=login, password=password, server=server) if login else mt5.initialize()
    bot = Mt5Bot(symbol, model_path, cfg)
    print(f"[mt5_live] {symbol} | balance={bot.balance()} | tree={model_path}")
    try:
        while True:
            bot.step(); time.sleep(poll)
    finally:
        mt5.shutdown()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--model", default="models/tree_pooled.py")
    ap.add_argument("--config", default=None, help="config.json (else FTMO defaults)")
    ap.add_argument("--offset", type=int, default=2)
    ap.add_argument("--login", type=int, default=None); ap.add_argument("--password", default=None)
    ap.add_argument("--server", default=None)
    a = ap.parse_args()
    cfg = BotConfig.load(a.config) if a.config else BotConfig(broker_utc_offset=a.offset)
    run(a.symbol, a.model, cfg, a.login, a.password, a.server)


if __name__ == "__main__":
    main()
