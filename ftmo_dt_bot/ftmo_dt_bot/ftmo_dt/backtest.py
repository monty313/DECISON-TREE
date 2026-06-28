"""backtest.py - event-driven FTMO backtester (per symbol).

Models the things that actually fail an FTMO challenge:
  * the 5% DAILY loss wall and the 10% MAX loss wall (hard fails),
  * real costs: per-bar spread (from the feed) + commission + slippage on BOTH
    sides of every trade,
  * dynamic % risk sizing off CURRENT equity (any account size),
  * internal guards that stop trading BEFORE the walls (daily_stop / lock / kill),
  * intraday-only handling (flat before rollover) unless swing_mode.

Signals come from the frozen tree; a bar with any non-finite feature abstains (0),
exactly like the live alpha. Entry executes at THIS bar's open (the price known
when the signal fires); SL/TP are checked intrabar against high/low.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .config import BotConfig


def compute_signals(tree, X: pd.DataFrame) -> np.ndarray:
    arr = X.to_numpy(dtype=float)
    finite = np.isfinite(arr).all(axis=1)
    sig = np.zeros(len(arr), dtype=int)
    if finite.any():
        sig[finite] = tree.predict(arr[finite])
    return sig


@dataclass
class BacktestResult:
    symbol: str
    equity: pd.Series
    trades: pd.DataFrame
    daily: pd.DataFrame
    summary: dict


def run_backtest(df1m: pd.DataFrame, X: pd.DataFrame, tree, cfg: BotConfig, symbol: str) -> BacktestResult:
    spec = cfg.spec(symbol)
    point, tick_size, tick_value = spec["point"], spec["tick_size"], spec["tick_value"]
    comm = spec["commission"]
    half_default = 10 * point / 2.0
    slip = cfg.slippage_points * point

    idx = df1m.index
    o = df1m["open"].to_numpy(float); hi = df1m["high"].to_numpy(float)
    lo = df1m["low"].to_numpy(float); cl = df1m["close"].to_numpy(float)
    spr = (df1m["spread"].to_numpy(float) * point) if "spread" in df1m.columns else np.full(len(idx), np.nan)
    half = np.where(np.isfinite(spr), spr / 2.0, half_default)
    atr_arr = df1m["_atr"].to_numpy(float) if "_atr" in df1m.columns else None
    sig = compute_signals(tree, X)

    # server-time day keys (FTMO day boundary) + minute-of-day in UTC
    server = idx + pd.Timedelta(hours=cfg.broker_utc_offset)
    day_key = server.normalize()
    mod = (idx.hour * 60 + idx.minute).to_numpy()
    last_min_of_day = 1440 - cfg.flat_before_rollover_min

    def in_session(m):
        for (h1, m1, h2, m2) in cfg.trade_sessions_utc:
            if h1 * 60 + m1 <= m < h2 * 60 + m2:
                return True
        return False

    init_bal = cfg.account_balance
    balance = init_bal
    equity_curve = np.empty(len(idx))
    pos = None  # dict: dir, lots, entry_fill, sl, tp, bar
    trades = []
    cur_day = None; day_start_eq = balance; trades_today = 0
    day_blocked = False; killed = False
    daily_rows = []
    breach_daily = breach_total = False
    target_hit = False
    costs_paid = 0.0

    def close_position(price_mid, t, reason):
        nonlocal balance, pos, costs_paid
        d = pos["dir"]; lots = pos["lots"]
        if d > 0:
            exit_fill = price_mid - half[t] - slip
        else:
            exit_fill = price_mid + half[t] + slip
        gross = (exit_fill - pos["entry_fill"]) * d / tick_size * tick_value * lots
        commission = 2 * comm * lots
        pnl = gross - commission
        balance += pnl
        costs_paid += commission + (half[t] + slip) / tick_size * tick_value * lots \
            + (pos["half_in"] + slip) / tick_size * tick_value * lots
        trades.append(dict(entry_time=pos["time"], exit_time=idx[t], dir=d, lots=lots,
                           entry=pos["entry_fill"], exit=exit_fill, pnl=pnl, reason=reason))
        pos = None

    for t in range(len(idx)):
        # mark to market FIRST (so the daily baseline uses equity incl. floating P&L)
        float_pnl = 0.0
        if pos is not None:
            d = pos["dir"]
            mid = cl[t]
            exit_fill = (mid - half[t] - slip) if d > 0 else (mid + half[t] + slip)
            float_pnl = (exit_fill - pos["entry_fill"]) * d / tick_size * tick_value * pos["lots"] - 2 * comm * pos["lots"]
        equity = balance + float_pnl
        equity_curve[t] = equity

        # new day bookkeeping (FTMO daily reference = equity at the day's start)
        if cur_day != day_key[t]:
            if cur_day is not None:
                daily_rows.append(dict(day=cur_day, day_start=day_start_eq,
                                       end_equity=equity, pnl=equity - day_start_eq))
            cur_day = day_key[t]; day_start_eq = equity
            trades_today = 0; day_blocked = False

        # ---- FTMO HARD WALLS ----
        if equity <= day_start_eq * (1 - cfg.max_daily_loss_pct) + 1e-9:
            breach_daily = True
            if pos is not None: close_position(cl[t], t, "daily_breach")
            equity_curve[t:] = balance; break
        if equity <= init_bal * (1 - cfg.max_total_loss_pct) + 1e-9:
            breach_total = True
            if pos is not None: close_position(cl[t], t, "total_breach")
            equity_curve[t:] = balance; break
        if equity >= init_bal * (1 + cfg.profit_target_pct):
            target_hit = True   # keep trading allowed but flag reached

        # ---- internal guards ----
        day_pnl_pct = (equity - day_start_eq) / max(day_start_eq, 1e-9)
        if day_pnl_pct <= -cfg.daily_stop_pct: day_blocked = True
        if day_pnl_pct >= cfg.daily_lock_profit_pct:
            if pos is not None: close_position(cl[t], t, "daily_lock"); 
            day_blocked = True
        if equity <= init_bal * (1 - cfg.total_stop_pct): killed = True

        # ---- manage open position (intrabar SL/TP, time, session/rollover) ----
        if pos is not None:
            d = pos["dir"]
            hit = None
            if d > 0:
                if lo[t] <= pos["sl"]: hit = ("sl", pos["sl"])
                elif hi[t] >= pos["tp"]: hit = ("tp", pos["tp"])
            else:
                if hi[t] >= pos["sl"]: hit = ("sl", pos["sl"])
                elif lo[t] <= pos["tp"]: hit = ("tp", pos["tp"])
            if hit is not None:
                close_position(hit[1], t, hit[0])
            elif (t - pos["bar"]) >= cfg.max_hold_bars:
                close_position(cl[t], t, "max_hold")
            elif (not cfg.swing_mode) and (mod[t] >= last_min_of_day or not in_session(mod[t])):
                close_position(cl[t], t, "session_flat")

        # ---- entries ----
        if pos is None and not killed and not day_blocked and not breach_daily:
            if sig[t] != 0 and in_session(mod[t]) and trades_today < cfg.max_trades_per_day:
                a = atr_arr[t] if atr_arr is not None else np.nan
                if np.isfinite(a) and a > 0:
                    risk_cash = cfg.risk_per_trade_pct * equity
                    sl_dist = cfg.sl_atr_mult * a
                    per_lot_risk = sl_dist / tick_size * tick_value
                    lots = risk_cash / max(per_lot_risk, 1e-9)
                    lots = max(0.01, round(lots, 2))
                    d = int(sig[t])
                    if d > 0:
                        entry_fill = o[t] + half[t] + slip
                        sl = o[t] - sl_dist; tp = o[t] + cfg.tp_atr_mult * a
                    else:
                        entry_fill = o[t] - half[t] - slip
                        sl = o[t] + sl_dist; tp = o[t] - cfg.tp_atr_mult * a
                    pos = dict(dir=d, lots=lots, entry_fill=entry_fill, sl=sl, tp=tp,
                               bar=t, time=idx[t], half_in=half[t])
                    trades_today += 1

    else:
        if pos is not None: close_position(cl[-1], len(idx) - 1, "end")
        if cur_day is not None:
            daily_rows.append(dict(day=cur_day, day_start=day_start_eq, end_equity=balance, pnl=balance - day_start_eq))

    eq = pd.Series(equity_curve, index=idx, name="equity")
    tdf = pd.DataFrame(trades)
    ddf = pd.DataFrame(daily_rows)
    summary = _summarize(eq, tdf, ddf, cfg, init_bal, breach_daily, breach_total, target_hit, costs_paid, symbol)
    return BacktestResult(symbol, eq, tdf, ddf, summary)


def _summarize(eq, tdf, ddf, cfg, init_bal, breach_daily, breach_total, target_hit, costs_paid, symbol):
    ret = eq.iloc[-1] / init_bal - 1 if len(eq) else 0.0
    roll_max = eq.cummax(); dd = (eq / roll_max - 1.0)
    max_dd = dd.min() if len(eq) else 0.0
    worst_day = (ddf["pnl"] / ddf["day_start"]).min() if len(ddf) and "day_start" in ddf else 0.0
    n = len(tdf); wins = int((tdf["pnl"] > 0).sum()) if n else 0
    gross_win = tdf.loc[tdf.pnl > 0, "pnl"].sum() if n else 0.0
    gross_loss = -tdf.loc[tdf.pnl < 0, "pnl"].sum() if n else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    passed = bool(target_hit and not breach_daily and not breach_total)
    return dict(
        symbol=symbol, final_equity=float(eq.iloc[-1]) if len(eq) else init_bal,
        total_return=float(ret), max_drawdown=float(max_dd), worst_day_pct=float(worst_day),
        n_trades=n, win_rate=(wins / n if n else 0.0), profit_factor=float(pf),
        avg_trade=float(tdf.pnl.mean()) if n else 0.0, costs_paid=float(costs_paid),
        breach_daily=breach_daily, breach_total=breach_total, target_hit=target_hit,
        FTMO_PASS=passed,
    )
