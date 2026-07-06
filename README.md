# US30 Decision Tree — Final State

A two-session autonomous research project that set out to make a US30 (Dow CFD) system pass
**+2.5% of initial balance on 90% of trading days without ever breaching a 4% trailing daily
drawdown** (FTMO-style). The honest conclusion: that specific bar is **numerically unreachable on
M1 OHLCV data** (proof in `PROGRESS.md` and `report.html`) — but the project produced a validated,
positive-expectancy, drawdown-safe strategy (the **Runner**) with an honestly simulated
**42-56% per-attempt probability of passing a real FTMO challenge**, plus the tooling to score any
future idea truthfully in seconds.

## The Runner (the deliverable strategy)

Long-only NY-session drift capture. Rules (exactly as backtested, see `runner_config.json`):

| Rule | Value |
|---|---|
| Symbol / TF | US30 CFD, decisions on closed M5 bars |
| Direction | LONG only |
| Session | entries 16:30–23:00 broker time (FTMO server time) |
| Entry | M5 CCI(14) closes above 0 while prior close ≤ 0 → buy at next bar open |
| Stop | 2.0 × Wilder ATR(14, M5); **refuse the trade if stop < 15 index points** |
| Take profit | none — exits are the +2.5% day-lock, the 3.5% trailing-DD halt, EOD flat (23:55), or the stop |
| Risk | 1.0% of balance per trade; skip entry if a full stop-out would push intraday trailing DD past 3.5% |
| Re-entry | stop-outs do not end the day; next fresh cross re-enters (lock/halt do end the day) |

Measured honestly (recorded per-bar spread, next-bar fills, day-independent scoring):
**+0.075R/trade in-sample (2020-24), +0.025R out-of-sample (2024-26), 0 OOS drawdown breaches,
worst day −2.97% across 6 years, +0.05–0.11%/day.** Real-FTMO phase simulation: Phase 1 pass
59–72%, Phase 2 71–79%, **funded ≈ 42–56% per attempt**.

The edge is thin — this strategy's strength is survival and repeatability, not speed.

## Repo map

| Path | What it is |
|---|---|
| `s11.py` | **The honest backtest harness.** Next-bar-open fills, recorded per-bar spread, every day scored independently from a fixed base, path-accurate trailing DD (DD-before-target inside each bar), ≤1% risk cap, consistency metrics. Score any idea: build a cache once, then evaluate configs in seconds. |
| `s11_diag.py` | Requirement-curve tool: given a trigger stream, computes the win rate a strategy would need for any day-pass target — kills doomed ideas before you build them. |
| `runner_config.json` | The validated Runner config + all headline numbers + the exact reproduce command. |
| `S11_Runner.mq5` | The MT5 Expert Advisor implementing the Runner (also copied to the MT5 Experts folder). |
| `us30_rf_bot.py` | The original Random-Forest bot with the debugged FTMO harness (historical baseline). |
| `framework/section-1..8.md` | The Gravity Framework "law book" (regime/energy/unanimity/persistence rules, STRAT-001..011 audits). |
| `PROGRESS.md` | The complete research log — every iteration, every failure, every number. |
| `report.html` | The final verdict report (requirement curve, coverage-quality frontier, walk-forward tables). |
| `s11_stage1.json` / `s11_stage2.json` | Sweep results backing the final report. |
| `archive/` | Experiment history: 42 run logs, dead-end scripts, superseded results. |
| `AGENT_PROMPT.md` / `FINALIZATION_PLAN.md` | The mission brief and the wrap-up plan. |
| `DTResources/`, `ftmo_dt_bot/` | Reference material / separate blueprint sub-project (untouched). |

Not in git (see `.gitignore`): the 126MB M1 CSV (`US30_M1_202007231046_202605262359.csv`) and the
regenerable `s11_full.joblib` feature cache.

## Reproduce the numbers

```bash
# one-time: build the feature cache from the M1 CSV (~15s)
python s11.py --csv US30_M1_202007231046_202605262359.csv --cache s11_full.joblib --build

# score the Runner on the untouched out-of-sample slice (2024-07 .. 2026-05)
python s11.py --cache s11_full.joblib --slice final --cfg "{\"side\":\"long\",\"trigger\":\"cci\",\"rr\":99,\"sl_mult\":2.0,\"min_sd\":15,\"session\":[990,1380],\"energy\":\"none\",\"license\":\"none\"}"
# expected: tr 825  win 31.6%  avgR +0.025  cov 90.2%  pass(traded) 12.9% (53/412)  brch 0
```

Slices: `--slice dev` = 2020-07..2024-06 (tuning span), `--slice final` = 2024-07..2026-05
(held out during tuning), `--slice full` = everything.

## Running the EA

1. `S11_Runner.mq5` lives in the MT5 Experts folder (`MQL5\Experts\`). Compile in MetaEditor.
2. Attach to a **US30, M5** chart. Defaults match the backtest exactly — do not optimize them.
3. Session inputs are **broker/server time** (16:30 NY cash open on FTMO server time). If your
   broker's clock differs, shift `InpSessionStartMin/EndMin/EodFlatMin` accordingly.

### EA ↔ backtest parity checklist (run once in Strategy Tester before going live)

Tester: US30, M5, "Every tick based on real ticks", 2024-07 → 2026-05, 100k deposit.

1. Every entry is a BUY stamped at an M5 bar open between 16:30 and 22:55.
2. Sampled stop distances ≈ 2× Wilder ATR(14,M5) of the signal bar, always > 15 points.
3. Sizing: loss-at-stop ≈ 1.0% of balance (under, never over).
4. Day-lock days flatten at +2.5% and stop trading; **no day ever touches −4%**; no overnight positions.
5. Aggregates vs the Python line above: trades within ±10% of 825, win% within ±3pts of 31.6,
   breach days = 0. (Tester spread ≠ recorded CSV spread; compare day outcomes in %, not $.)

## The five backtest bug classes (check before believing ANY backtest)

Every fake "breakthrough" in this project traced to one of these:

1. **Stale/look-ahead fills** — entering at the signal bar's open after computing the signal at its
   close. Fill at the *next* bar's open.
2. **Frictionless costs** — spread modeled in the wrong units (0.03 pts instead of 1–3). Use the
   recorded per-bar spread.
3. **Compounding inflation** — sizing risk on current balance while scoring the target vs initial
   balance. Score each day independently.
4. **R-normalization errors** — hand-rolled R-multiple math producing impossible EVs (−7R on a
   1R-floored bracket, +EV both directions simultaneously).
5. **No-stop exits** — exit-on-target-only sims letting losers run to −5..−9R while sized as 1R.

And the structural theorem that focuses all future work: **on a zero-drift price, no money-management
scheme can pass more than 3.5/(2.5+3.5) = 58.3% of days** (optional stopping). New ideas must find
*conditional drift* — new information (order flow, cross-asset leads, news timing), not new
arrangements of OHLCV indicators.
