# MISSION PROMPT — Gravity-Gated 90% Day-Pass Bot

Copy everything below this line into a fresh agent session started in `c:\Users\user\Downloads\DECISON TREE`.

---

## MISSION

Make this project produce a trading system that, on US30 data, achieves **at least a 90% day-pass rate**: a day PASSES when the account locks **+2.5% of initial balance** without ever breaching the **4% trailing daily drawdown** (trailed from each day's intraday equity peak, checked on both balance and equity, DD checked before target). The score that counts is **MIN(in-sample, out-of-sample)** over **at least 30 distinct trading days** of out-of-sample data. That is the binding Definition of Done. No metric-gaming: no cherry-picked windows, no denominator tricks, no redefining "day," no removing losing days. You keep looping — creatively — until the Definition of Done is met. A dead end kills an approach family, never the mission: diagnose, mutate, and attack from a new angle.

## REQUIRED READING — IN THIS ORDER, BEFORE ANY CODE

1. **`THE_GRAVITY_FRAMEWORK.md`** (delivered as `framework/section-1.md` … `section-8.md` in this folder) — this is your LAW BOOK. It was written specifically to train you. Every rule in it is binary and mechanically checkable, indexed by rule ID (G-1..G-2, F-1..F-5, U-1..U-5, E-1..E-2, R-1, P-1..P-3, SY-1..SY-2, M-1, CS-1). You must implement its gates as code, not treat it as commentary. Its Section 5 (standing license, uninterrupted momentum via shifted-SMA persistence, duration-irrelevant validity, the re-entry loop) and Section 8 (how to audit any strategy for compliance, with the STRAT-001..011 portfolio as case studies) are your operating system for this mission.
2. **`PROGRESS.md`** — the full log of a prior investigation. Read it so you never repeat what already failed.
3. **`us30_rf_bot.py`** (in the folder ROOT — the copy under `DTResources/` is STALE, ignore it) — contains a **correct, already-debugged FTMO harness**: true bracket exits (stop + target, losses floored at −1R) and the exact +2.5% lock / 4% trailing-DD day logic. **Reuse this harness for all scoring. Do not reinvent it.** If you change it, prove equivalence first.
4. **`US30_M1_202007231046_202605262359.csv`** — 6 years of US30 M1 OHLCV. Model costs at 3-point spread minimum.
5. `gravity_ftmo.py` + `gravity_ftmo_results.json`, `how to use momentum.md` — earlier gravity work and the original notes the framework grew from. Context, not law.

## WHAT IS ALREADY PROVEN — DO NOT RELITIGATE, DO NOT REPEAT

- Nine independent methods (RF thresholds, parameter sweeps, feature pruning, leaf mining, EA voting, ATR labels, seasonality, money-management-only, structure gates) all failed at **bar-by-bar direction prediction on flat feature pools**. Win rate at 1:1 was 49.7% — a coin flip. That framing is DEAD. Do not build another predict-every-bar model on undifferentiated features.
- An **oracle test proved ~28 winning setups exist per day** (95–98% oracle day-pass). The target is physically reachable in this data. The entire unsolved problem is SELECTION: isolating the small set of licensed windows before direction is even asked.
- The DD-safety machinery works. Keep it working — any candidate that breaches the 4% trailing DD on any tested day is INVALID regardless of its pass rate.

## THE APPROACH THE FRAMEWORK MANDATES

Your edge test is not "can I predict every M1 bar" — it is "**when do I refuse to play**." Build the refusal machine first:

1. **Encode the state machine** from the framework: GravityState {BULL, BEAR, NEUTRAL} via the DUAL-TF GATE (F-1), VolatilityState {NOTHING_HAPPENING, TRADABLE, GREAT_MOVEMENT} via the ENERGY GATE with forward-shifted SMA baselines (F-3), UNANIMITY across multi-period families (F-4, SY-1/SY-2), and the PERSISTENCE TEST — raw HTF indicator vs its own forward-shifted short SMA; consecutive closed bars on the correct side = **uninterrupted momentum**; one cross back = license revoked (P-1).
2. **Trade only under a standing license** (P-1/P-3): license true → every fresh LTF trigger is an independent entry, including many short trades in one HTF push (P-2 — duration is not a validity input); license false → refuse everything, no matter how pretty the trigger.
3. **Measure edge only inside the licensed denominator** — win rate over all bars is meaningless by construction; report win rate, expectancy, and trade count strictly on licensed windows.
4. **Entries** per E-1 (pullback to the gravity line) and E-2 (Super band-pierce with full alignment); mirrored mandatory exits (U-2); trigger windows not states (U-1); decay schedules (U-3); rule-based re-entry after whipsaw (U-4); ≤1% risk, never scale against gravity (R-1).
5. **Audit every candidate with CS-1** (Section 8): every indicator instance mapped to exactly one role, all four roles covered, dual-TF gate present, mirrored exits, re-entry license, risk mapping. Non-compliant candidates are repaired or discarded before backtesting.

## CREATIVE DEGREES OF FREEDOM (loop across these, one hypothesis at a time)

Indicator families and periods for each role (CCI/RSI/ADX/ATR/BB/SMA fans and beyond); HTF/LTF pairs (H4/H1 down to M5/M1); shift lengths and smoothing for persistence baselines; unanimity set sizes; STANDARD vs SUPER entry grades; per-day trade budgets and stop-after-target logic (once +2.5% locks, STOP trading that day — the day is won); day-level risk throttles that spend far less than 4% DD to reach 2.5%; compounding trade sequencing within a day; session/time filters as exogenous energy gates (Section 8's carrier-agnostic principle). Combining gates is expected; weakening the harness is forbidden.

## EVIDENCE RULES — EVERY LOOP, NO EXCEPTIONS

- Closed bars only; HTF features from the last CLOSED HTF bar; zero look-ahead anywhere.
- Walk-forward: train/tune on one span, test untouched forward spans; report IS and OOS separately and score on MIN.
- ≥30 OOS trading days in the reported window; also run the full 6-year data as a robustness check.
- 3-point spread costs on every fill; slippage assumption stated.
- After each loop, append to `PROGRESS.md`: hypothesis, exact gate configuration (rule IDs used), licensed-window count/day, licensed win rate, day-pass rate IS/OOS, worst day, DD breaches (must be 0), and the diagnosis of which gate leaked. Save each candidate's config + results as JSON.

## LOOP PROTOCOL

`hypothesize → implement gates → CS-1 audit → walk-forward backtest through the us30_rf_bot.py harness → score MIN(IS,OOS) day-pass → if < 90%: diagnose the leaking gate (was it selection? sizing? day-stop? exits?), mutate ONE thing or pivot family → log → repeat.`
Never stop on frustration; stop only on Definition of Done. If an approach family is exhausted, write its post-mortem in PROGRESS.md and open a new family — the framework's M-1 meta-rule tells you how to manufacture new rules for anything not covered. Report honestly every cycle: real numbers, including the failures.

---
*Prompt prepared 2026-07-06. Framework document: `framework/section-*.md` in this folder. Harness + data: `us30_rf_bot.py`, `US30_M1_202007231046_202605262359.csv`.*
