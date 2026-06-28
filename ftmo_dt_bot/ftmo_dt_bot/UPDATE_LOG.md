# UPDATE_LOG

## 2026-06-28 — initial build
- Indicator vocabulary (44 cols/TF) matching the RL cache, pure pandas.
- Causal, leak-free feature matrix on 1m/5m/30m/4h (validated: future shock
  leaves past features unchanged).
- Cost-aware 3-class labels using per-bar MT5 spread + commission + slippage.
- Tree: dependency-free NumpyCART + sklearn adapter -> shared TreeArrays.
- Freeze: tree -> pure-Python `evaluate_tree`, MQL5 `EvaluateTree`, RL alpha;
  golden-row equivalence test pins all surfaces together.
- FTMO backtester: dynamic account size, 5% daily / 10% max walls, internal
  guards (stop -3% day / lock +2% / kill -8%), real costs both sides.
- Live MT5 Python bot + MQL5 EA (FTMO risk manager) + MT5 data exporter.
- Colab training notebook (4 Drive symbols prewired) + regression suite (5/5).
- Risk profile: 0.01% / trade, up to 800 trades/day, intraday-only by default.
- Patch: daily reference + worst_day now use day-start EQUITY (not initial
  balance); removed dead code. Suite still 5/5.

## 2026-06-28 — learning diagnostics
- ftmo_dt/diagnostics.py: walk-forward, shuffled-label null, learning curve,
  feature importance, overfit gap, and a 5-check "is it learning?" scorecard.
- param_sweep over depth/leaf/dead-band. Notebook gains sections 7–11.
- Validated: scorecard = NOT LEARNING on pure noise (0/5), LEARNING on a
  series with embedded momentum edge (5/5).

## 2026-06-28 — feature normalizer change (user request)
- Features 5-7,9,11-12 now divide by BOLLINGER-BAND WIDTH (dev 1.0) instead of
  ATR: BB200 width for the SMA200 distance, BB20 width for the shorter ones,
  on all 4 timeframes. ATR remains only in atrfrac (#10) and stops/sizing.
- Still scale-free (BB width in price units) -> pooled cross-symbol model intact.
- feature_spec + RL-alpha codegen + MQL5 codegen updated in lockstep; equivalence,
  leak, and 5/5 suite re-verified; EA/alpha regenerated (BB200+BB20 dev1 handles).

## 2026-06-28 — concepts doc + signal-quality report
- docs/TRAINING_AND_SIGNALS.md: what training does, alpha vs policy, RL slot-16
  integration, and how to judge signals.
- diagnostics.signal_report: coverage, per-class precision, dir-hit, confusion,
  and net-of-cost expectancy per signal (OOS vs in-sample). Notebook section 7b.

## 2026-06-28 — selectivity (800 = cap, not target)
- Wired min_confidence: frozen tree abstains (0) on low-conviction leaves; baked
  into all surfaces at export (export==predict verified at every threshold).
- train persists min_confidence in npz and writes the full EA directly.
- Added ftmo_consistent() preset; clarified max_trades_per_day is a CAP.
- Docs: TRAINING_AND_SIGNALS section 8 (selectivity & consistency); README reframed.
