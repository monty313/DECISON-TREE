# What training does, what you get, and how to judge the signals

## 1. The one mental model to keep
**The decision tree is an *alpha* (a signal generator), not a *policy*.**
- An **alpha** answers one narrow question each bar: *"is there a setup right now?"* → **+1 / -1 / 0**.
- A **policy** (your RL model) decides what to actually *do*: HOLD / BUY / SELL / CLOSE, how big, when to exit.

The tree produces a *suggestion*. The policy makes the *decision*.

## 2. What training does (the purpose)
The tree starts empty. Training shows it your history as (inputs → outcome) pairs:
- **inputs** = the 48 scale-free features (RSI, CCI, BB-width-normalised SMA distances, %b, ATR-fraction) on 1m/5m/30m/4h;
- **outcome (label)** = what price did next, *cost-aware*: **+1** if it then moved up enough to beat spread+commission, **-1** down enough, **0** if the move wasn't worth the costs.

The training algorithm searches for the `if feature <= threshold` splits that best separate those three outcomes. **Training = finding those threshold numbers.** Those thresholds *are* the learned knowledge — nothing else is "the model."

## 3. What you get when it finishes
A **frozen function**: 48 numbers in → one of {+1, -1, 0} out. Deterministic (same input always gives the same output; no more learning). Concretely:

| Artifact | What it is | Where it's used |
|---|---|---|
| `models/tree_<name>.py` | the tree as pure-Python `if/else` | live Python bot, backtest |
| `models/tree_<name>.npz` | the raw tree arrays | reload without sklearn |
| `rl_alpha/decision_tree_ftmo_alpha.py` | the same tree as an RL alpha | **slot 16 of your RL pack** |
| `ea/FtmoDecisionTree.mq5` | the same tree transpiled to MQL5 | live trading inside MT5 |
| `reports/…json` + diagnostics | OOS backtest + "is it learning" verdict | tells you if it's any good |

All four evaluate the **same** tree, pinned together by a golden-row test, so they can't drift.

## 4. Alpha vs policy — the difference that matters
| | Decision tree (this) | RL policy (your model) |
|---|---|---|
| Type | **alpha / signal** | **policy** |
| Output | +1 / -1 / 0 | HOLD / BUY / SELL / CLOSE (+ sizing) |
| Trained how | **supervised** on labeled history | **reinforcement** on reward/P&L |
| Decides trades? | **no** — it suggests | **yes** — it decides |
| Lives where | one of 64 alpha slots | the agent that consumes all alphas |

## 5. The tree's two lives
1. **RL alpha (slot 16).** You add the generated `decision_tree_ftmo_alpha.py` to your pack. From then on the policy sees the tree's +1/-1/0 as part of its 479-float observation (the slot's value + mask bit + streak). The policy **learns how much to trust it** alongside the other 15 alphas. The tree's +1 never forces a trade.
2. **Standalone bot / EA.** No RL policy — here the tree's signal *is* the trade trigger, wrapped in the FTMO risk manager (0.01% risk, daily/total walls, sessions). This is the "pass the challenge directly" path.

Same frozen tree, two ways to deploy it.

## 6. Adding it to your RL model (give the policy a new signal)
1. Copy `rl_alpha/decision_tree_ftmo_alpha.py` and `register_decision_tree_ftmo_alpha.py` into `src/strategies/`.
2. Call its `register(...)` in `register_all(...)` in `alpha_pack.py` → it takes slot 16. (Full snippet: `docs/RL_INTEGRATION.md`.)
3. Adding to a free slot is **shape-stable** — a trained policy keeps running and just starts seeing non-zero values in slot 16. To actually **exploit** the signal, continue/retrain the RL policy so it learns to weight it.

> Note: training the **tree** (supervised, once) and training the **policy** (reinforcement) are two different "trainings." This package does the first. The second is your RL project's job.

---

## 7. How do I know how well the signals are doing?
Two different questions — measure both:

**A) Is the *signal* any good?** → `diagnostics.signal_report(df, cfg, symbol)`
Run on out-of-sample data. Reads:

| Metric | Meaning | "Good" looks like |
|---|---|---|
| `coverage` | % of bars it fires (vs flat) | depends on style; high = more cost exposure |
| `precL` / `precS` | when it says long/short, how often the cost-aware label agreed | **> ~base rate**, ideally > 45–50% |
| `dir_hit` | direction correct among active signals | **> 50%** |
| `exp_bps` | **net-of-cost edge PER FIRED SIGNAL** (bps of price) | **> 0** — this is the money metric |
| `confusion` | signal vs actual label table | diagonal-heavy is good |

`exp_bps` is the one that matters most: **positive out-of-sample = the signal adds value after costs**; negative = it's over-trading noise. Watch the **in-sample → out-of-sample drop**: a big fall (e.g. +4 bps IS → −0.1 bps OOS) means overfitting.

**B) Does *trading* it pass FTMO?** → `diagnostics.learning_scorecard(...)` + the backtest reports
- `learning_scorecard` → a 5-check verdict (OOS profit factor > 1, beats a shuffled-label null, walk-forward majority positive, not overfit, dir-hit > 50%). 4–5/5 = learning; ≤2 = noise.
- `walk_forward(...)` → fold-by-fold OOS — real edge is consistent across time, not one lucky window.
- `reports/backtest_*.json` → return, max drawdown, **worst day vs the 5% wall**, and `FTMO_PASS`.

### Rules of thumb
- **Trust OOS, never in-sample.** In-sample always looks good; it's meaningless.
- **`exp_bps` > 0 OOS** and **scorecard ≥ 4/5** = the signal is real.
- At 800 trades/day, **costs dominate** — if `exp_bps` ≤ 0, raise `deadband_cost_mult` or `label_horizon_bars` (fewer, cleaner setups) and retrain.
- **Red flags:** big IS→OOS drop (overfit → lower `max_depth`, raise `min_samples_leaf`); one feature ~100% of importance (fragile); walk-forward mostly negative.

### Quick commands
```python
from ftmo_dt import diagnostics as DG
DG.signal_report(frames['EURUSD'], cfg, 'EURUSD')      # signal quality, OOS vs IS
DG.learning_scorecard(frames['EURUSD'], cfg, 'EURUSD') # 5-check learning verdict
DG.walk_forward(frames['EURUSD'], cfg, 'EURUSD', n_folds=6)
DG.param_sweep(frames['EURUSD'], cfg, 'EURUSD')        # tune OOS, watch overfit
```
These are notebook sections 7–11.

---

## 8. Trade frequency, selectivity & consistency
**800 trades/day is a CAP, not a target.** Passing the FTMO Challenge consistently
comes from *fewer, higher-conviction trades + tight risk*, never from volume. The
cap (`max_trades_per_day`) only stops a runaway loop; it is rarely the binding
constraint.

**Dials that make it MORE selective (trade less, cleaner):**
- `min_confidence` (0 → ~0.6): the tree only fires +1/-1 when a leaf is at least
  this pure; otherwise it stays flat (0). Higher = fewer, more confident trades.
- `deadband_cost_mult` (↑): label a bar directional only when the move clearly
  beats costs, so the tree learns to sit out marginal setups.
- `label_horizon_bars` (↑): target larger moves that more easily clear the spread.

**Machinery that protects CONSISTENCY (don't breach the walls):**
- `risk_per_trade_pct = 0.01%` — any single loss is negligible.
- `daily_lock_profit_pct` — once the day is +X%, flatten and stop (bank the green).
- `daily_stop_pct` / `total_stop_pct` — stop the day at -3%, kill at -8%, both
  inside the 5% / 10% FTMO walls.

**Shortcut:** `from ftmo_dt.config import ftmo_consistent; cfg = ftmo_consistent(100_000)`
sets a selectivity-first starting point (min_confidence 0.55, dead band 2.5, lock
the day at +1.5%). Then verify with `signal_report` / `learning_scorecard` and tune.
