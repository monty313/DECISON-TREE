# FTMO Decision-Tree Bot (MT5)

One decision tree, **trained once**, frozen into **three identical surfaces**:

| Surface | File | Runs where |
|---|---|---|
| **A. Research / backtest + live Python bot** | `ftmo_dt/backtest.py`, `ftmo_dt/mt5_live.py` | your PC next to the MT5 terminal |
| **B. MQL5 Expert Advisor** | `ea/FtmoDecisionTree.mq5` | inside MT5 / a VPS, no Python |
| **C. RL alpha (slot 16)** | `rl_alpha/decision_tree_ftmo_alpha.py` | your reinforcement-learning project |

A decision tree is just a chain of `if feature <= threshold` tests, so the *same*
frozen tree transpiles to pure-Python, to MQL5, and to a no-dependency RL alpha —
they can never silently drift (a golden-row test pins them together).

## Why this design passes-challenge-shaped
- **Dynamic account size** — everything is a % of *current* equity, so one config
  runs a $10k or $200k challenge. Default $100k.
- **Your risk profile** — `risk_per_trade_pct = 0.01%`; `800` trades/day is a
  safety **CAP, not a target** — it trades only on confident setups (often far
  fewer). Selectivity = `deadband_cost_mult` + `min_confidence`; or use the
  `ftmo_consistent()` preset. The goal is consistent passing, not volume.
- **FTMO walls are hard-coded guards** — stops trading at the 5% daily / 10% max
  walls, with *internal* buffers (stop the day at -3%, lock green at +2%, kill at -8%).
- **Real costs** — per-bar **spread from your MT5 feed** + commission + slippage,
  applied on both sides. At 800 trades/day costs dominate, so labels only mark a
  trade directional if the forward move **clears modeled cost** (cost-aware dead band).
- **Leak-free** — higher-TF features are only used *after* the bar closes; a future
  price shock provably leaves every past feature unchanged (see tests).
- **Symbol-agnostic** — features are scale-free (Bollinger-width-normalised distances, bounded
  oscillators), so the **pooled** tree trained on your 4 symbols deploys on *any*
  broker symbol.

## Layout
```
ftmo_dt/                package (indicators, features, labeling, tree, export, backtest, live)
  indicators.py         the 44-column RL vocabulary (TA-Lib-equivalent, pure pandas)
  feature_spec.py       48 scale-free features (SINGLE source of truth)
  features.py           causal, leak-free feature matrix
  labeling.py           cost-aware 3-class {+1,-1,0} labels
  tree_model.py         TreeArrays + dependency-free NumpyCART (+ sklearn adapter)
  export_tree.py        freeze tree -> pure-Python / MQL5 / RL-alpha generators
  backtest.py           FTMO-rule event-driven backtester
  mt5_live.py           live Python bot (MetaTrader5 package)
  train.py              orchestrator (CSV -> features -> labels -> tree -> all surfaces)
ea/FtmoDecisionTree.mq5 generated Expert Advisor (tree + FTMO risk manager)
rl_alpha/               generated RL alpha + register helper (slot 16)
scripts/export_mt5_data.py   dump fresh MT5 history to CSV
notebooks/Train_FTMO_DecisionTree.ipynb   one-click Colab training (your 4 Drive IDs prewired)
models/ reports/        trained tree(s) + OOS backtest summaries
tests/test_validation.py  regression suite (leak, equivalence, walls)
docs/RL_INTEGRATION.md  paste-ready slot-16 wiring + ALPHAS.md writeup
```

## Quickstart
**Train in Colab (recommended — data + sklearn already there):** open
`notebooks/Train_FTMO_DecisionTree.ipynb`, run top to bottom. It downloads your 4
symbols, trains per-symbol + pooled, freezes every surface, and prints an FTMO
pass/fail table.

**Train locally:**
```bash
pip install pandas numpy scikit-learn        # sklearn optional; NumpyCART is the fallback
python -m ftmo_dt.train --data ./data --out . --balance 100000 --offset 2
```

**Backtest only / inspect:** see `tests/test_validation.py` and `reports/`.

**Live (Python bridge, Windows + MT5):**
```bash
pip install MetaTrader5
python -m ftmo_dt.mt5_live --symbol EURUSD --model models/tree_pooled.py --offset 2
```

**Live (EA):** copy `ea/FtmoDecisionTree.mq5` to `MQL5/Experts`, compile in
MetaEditor, attach to an M1 chart. Re-generate it from your trained tree (notebook
step 5) so the EA's tree matches your data. Inputs default to your FTMO params.

**RL alpha:** copy `rl_alpha/*.py` into the RL project's `src/strategies/` and wire
slot 16 — see `docs/RL_INTEGRATION.md`.

## Honest caveats (read this)
- On random/synthetic data this strategy **loses after costs** — by design (no edge
  to find). That is the *opposite* of a look-ahead-leak red flag. Whether real edge
  exists is an empirical question your real-data Colab run answers.
- **Costs scale with trade count.** 800/day is only a cap; fewer, cleaner trades
  is the goal. If `profit_factor` < 1 after costs, raise `min_confidence` and/or
  `deadband_cost_mult`, or lengthen `label_horizon_bars`.
- A single tree overfits easily. Use the walk-forward / OOS numbers, not in-sample.
- Set `broker_utc_offset` to YOUR FTMO server (≈2, 3 in DST) — it affects the daily
  reset and session filter.
- Nothing here places a trade until you start the bot/EA. Review inputs first.
