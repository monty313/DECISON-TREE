# DECISON-TREE — IRAC handoff (2026-10-17)

## Issue
US30 decision-tree/rule research to pass FTMO days; produced the 'Runner' strategy + honest backtest harness s11.py.
Central question: Original bar (>=90% day-pass) declared numerically unreachable on M1; Runner edge is thin.

## Rule
PROGRESS.md definition of done: >=90% day-pass on MIN(IS,OOS), +2.5% w/o 4% trailing DD. Doctrine: scalping-only; 5m CCI 30/100 burst entry; 1R=0.25% equity; max 4 concurrent; daily floor -3R; pyramid winners OK, add-to-losers banned.

## Application
3 commits; final ce877df 2026-07-06 'Finalize project'. README: Runner = long-only M5 CCI(14) zero-cross, 2xATR stop, 1% risk; +0.075R IS / +0.025R OOS; FTMO funded ~42-56%. Files: s11.py, s11_diag.py, runner_config.json, S11_Runner.mq5, report.html. Runner violates doctrine: 1% risk (not 0.25%), not CCI 30/100 burst, no TP (not scalping).

## Conclusion
Status: done (target proven unreachable; deliverable shipped). Done/closed. Blocker to the original goal: edge ceiling on data. Doctrine mismatch.
Next: 1) Re-score a doctrine-compliant variant in s11.py (0.25% R, CCI 30/100). 2) Forward-test S11_Runner.mq5 on demo.
