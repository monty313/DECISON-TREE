# RL integration — Decision-Tree FTMO alpha (slot 16)

This adds ONE alpha to the RL pack. It fills the next free slot (16), which is
**free and shape-stable** — the observation stays **479 / 220**. No new cached
indicator is introduced: every feature is plain arithmetic of columns already in
the 44-column vocabulary, read via `ctx.ind(col, tf)` on TFs `1m/5m/30m/4h`.

## Files to copy into the RL project
```
src/strategies/decision_tree_ftmo_alpha.py            <- rl_alpha/decision_tree_ftmo_alpha.py
src/strategies/register_decision_tree_ftmo_alpha.py   <- rl_alpha/register_decision_tree_ftmo_alpha.py
```
Regenerate both from your trained tree (notebook step 5 / `export_tree.write_rl_alpha`)
so the frozen if/else matches your data. Never hand-edit the if/else.

## Wire it into the pack (slot 16)
In `src/strategies/alpha_pack.py`, inside `register_all(registry)`, after the ORB
alpha (slot 15):
```python
from .register_decision_tree_ftmo_alpha import register as _register_dt_ftmo
# ... existing slot 0..15 registrations ...
_register_dt_ftmo(registry)   # -> grabs the next free slot = 16
```

## ALPHAS.md writeup (paste under the slot-15 section)

### Slot 16 — `decision_tree_ftmo_5m_30m_4h` (Decision Tree, learned)
📄 `src/strategies/decision_tree_ftmo_alpha.py` · class `DecisionTreeFtmoAlpha`

**Idea.** A supervised **CART decision tree**, trained offline on the FTMO symbols
to predict a cost-aware 3-class label {long / short / flat}, then **frozen into a
pure-Python `if feature <= threshold` chain** (no sklearn at runtime). Each bar it
builds **48 scale-free features** — 12 per timeframe on `1m/5m/30m/4h` — by plain
arithmetic of cached columns:
- centered **RSI(4)/RSI(14)**, raw **CCI(30)/CCI(100)**;
- **Bollinger-width (dev 1.0) normalised** distances of close from **SMA20/50/200**
  (BB200 width for SMA200; BB20 width for the rest), the **SMA fan** (`sma_p4_s3`),
  and the **SMA(4)-of-high/low envelope**;
- **Bollinger %b** (`bb20_dev2.0`); and **ATR/price** (`atrfrac`, the only ATR use).

It returns the leaf's class as `+1 / -1 / 0`.

```text
x   = [ 48 scale-free features in the frozen FEATURES order ]
BUY  (+1):  evaluate_tree(x) ==  1     # tree leaf = long setup
SELL (-1):  evaluate_tree(x) == -1     # tree leaf = short setup
INACTIVE (0): any feature non-finite (warm-up), OR tree leaf = flat
```

| Property | Value |
|---|---|
| Reads | `sma_p1_s0, sma_p50_s0, sma_p200_s0, sma_p4_s3, bb200_dev1.0_{upper,lower}, bb20_dev1.0_{upper,middle,lower}, bb20_dev2.0_{upper,lower}, sma4_sh4_{high,low}, atr14_raw, rsi{4,14}_raw, cci{30,100}_raw` on `1m/5m/30m/4h` |
| New cached indicator | **none** (arithmetic of existing columns) |
| Warm-up | abstains (`0`) until every feature is finite (4h SMA200 ≈ 33 days) |
| State | **stateless** — no `reset()` needed |
| Hot-loop cost | 48 float ops + a shallow `if/else` chain; no pandas/sklearn/TA-Lib |

Quick-index row:
```
| 16 | decision_tree_ftmo_5m_30m_4h | Decision Tree | learned 3-class | 1m/5m/30m/4h | RSI,CCI,BB,SMA,ATR (derived) |
```

## docs/UPDATE_LOG.md entry
```
## 2026-06-28 — add slot 16 `decision_tree_ftmo_5m_30m_4h`
- New learned alpha: frozen CART -> +1/-1/0 from 48 scale-free features
  (12 per TF on 1m/5m/30m/4h), all derived by arithmetic from the existing
  44-column vocabulary. No new cached indicator; observation stays 479/220.
- compute_signal: pure if/else, abstains on any non-finite feature. Stateless.
- Golden-row test pins the in-repo if/else to the trained tree (no drift).
```
