# DECISON TREE — Project Finalization Plan

## Context

Two overnight research sessions concluded honestly: the self-imposed "90% of days each lock +2.5%" goal is numerically unreachable on US30 M1 OHLCV (best breach-free MIN(IS,OOS) ≈ 18.7%), but the work produced a validated, positive-EV, DD-safe strategy — the **"runner"** (long-only NY-session drift capture) — with an honestly simulated **42-56% per-attempt chance of passing the real FTMO challenge** (+10% / 5% daily / 10% overall). The user wants to wrap the project: capture the deliverables, build the deployable MT5 EA of the runner, archive the experiment debris, commit + push to GitHub, and move on.

User decisions (asked & answered):
- Experiment logs/scripts → **archive/ folder** (not deleted)
- Git → **commit AND push** to `origin` (https://github.com/monty313/DECISON-TREE.git)
- **Build the MQL5 EA** of the runner config as the final deliverable

Current repo state (inventoried): branch `main`, **nothing tracked** (everything `??`), no `.gitignore`; 126MB CSV exceeds GitHub's 100MB hard limit; ~112MB of regenerable caches; 42 log files; `undefined/` holds the gravity-framework sections 1-8 (misnamed export); `__pycache__/` and a `.lnk` shortcut are junk.

## The validated runner config (source of truth for Steps 1-2)

**Canonical config — empirically verified** (Plan agent re-ran both interpretations; only this one reproduces the recorded numbers: OOS avgR +0.025, cov 90.2%, 825 trades, win 31.6%, pass(traded) 12.9%, 0 breaches):

```json
{"side":"long","trigger":"cci","rr":99,"sl_mult":2.0,"min_sd":15,
 "session":[990,1380],"energy":"none","license":"none"}
```
plus BASE defaults: `risk_pct=1.0, target=2.5, ddh=3.5, ddf=4.0, guard=true, eod=true, adapt=false, spread="data"`. No H1 license, no energy gate — the EA needs only CCI(14,M5) + ATR(14,M5).

Rules the EA must reproduce (from `s11.py harness()`):
- LONG only, US30, decisions on **closed M5 bars**; entries only 16:30-23:00 broker time (decision minute 990-1379)
- Entry: M5 CCI(14) crosses above 0 on the just-closed bar (`cci[1]>0 && cci[2]<=0`) → market buy on the new bar's first tick
- Stop: 2.0×**Wilder** ATR(14,M5); **refuse trade if stop distance ≤ 15 index points**
- No TP (rr=99 = unreachable). Exits: +2.5% day-lock (balance OR floating equity vs day-start balance) → flat + done for day; trailing intraday DD ≥ 3.5% from the day's single equity peak (both equity- and balance-DD vs that peak) → flat + halt (true fail line 4%); EOD flat 23:55; or the server-side stop
- Risk 1.0% of **current balance** (harness uses day-compounded `closed`, not day-start); entry guard: skip if a full stop-out would push day DD past 3.5%; one position at a time; stop-outs do NOT halt the day — re-entry on the next cross is allowed
- Reference numbers (recorded per-bar spread): avgR +0.075 DEV / +0.025 OOS, +0.109%/day full-6yr, worst day −2.97%, 0 OOS breaches

## Step 0 — Save this plan into the project

Copy this plan to `FINALIZATION_PLAN.md` at the project root so the wrap-up procedure lives with the repo (user request).

## Step 1 — Capture the strategy as data + docs

1. **`runner_config.json`** (new, project root): the exact winning cfg dict (trigger=cci, license=none, energy=none, side=long, rr=99, sl_mult=2.0, session=[990,1380], min_sd=15, risk_pct=1.0, ddh=3.5, spread="data") plus the headline results (DEV/OOS avgR, day-pass, phase-sim odds) and the s11.py command line that reproduces them.
2. **`README.md`** (new, project root) — the project's front page:
   - One-paragraph outcome (honest verdict + what was delivered)
   - The runner strategy rules and its measured numbers
   - How to reproduce: `python s11.py --csv <CSV> --cache s11_full.joblib --build` then `python s11.py --cache s11_full.joblib --slice final --cfg "<runner cfg>"`
   - The five backtest bug classes checklist (from PROGRESS.md) — the project's hardest-won lesson
   - Map of the repo: `s11.py` (honest harness), `s11_diag.py` (requirement curve), `us30_rf_bot.py` (original RF bot + FTMO harness), `framework/` (gravity law book), `PROGRESS.md` (full research log), `report.html` (published verdict), `S11_Runner.mq5` (EA), `archive/` (experiment history)
   - EA install/run instructions + the verification checklist (Step 2)

## Step 2 — Build the EA: `S11_Runner.mq5`

Single-file MQL5 EA at project root, plus a copy into the user's MT5 Experts folder:
`C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\49CDDEAA95A409ED22BD2287BB67CB9C\MQL5\Experts\S11_Runner.mq5`

Convention sources to mirror: `US30_ExpansionTrigger_v1.mq5` (input groups, daily reset / circuit-breaker module, CalcLotSize, OnTester day-pass scorer) and `ftmo_dt_bot/ftmo_dt_bot/ea/FtmoDecisionTree.mq5` (new-bar detection, magic-filtered HasPosition/CloseMine, CTrade deviation setup).

Design decisions (all verified against `s11.py harness()` by the design agent):
- **Inputs** (grouped, user's style): session 990/1380/EOD-flat 1435; CciPeriod 14, AtrPeriod 14, SlAtrMult 2.0, MinStopPts 15.0, RiskPct 1.0; DayTargetPct 2.5, DdHaltPct 3.5; SlippagePts 100, MaxSpreadPts 0 (**off by default** — backtest never refused on spread), Magic 110011
- **CCI**: built-in `iCCI(_Symbol, PERIOD_M5, 14, PRICE_TYPICAL)` is safe — python's 0.79788×std denominator differs from MT5's MAD, but both are positive so **zero-cross events are identical**. CopyBuffer shifts 1/2: `cci1 > 0 && cci2 <= 0`
- **ATR**: built-in `iATR` is an SMA of TR; python is **Wilder RMA** — values differ by a few % and shift the 15-pt refusal boundary. **Implement Wilder ATR manually** (CopyRates ~500 M5 bars warm-up, seed = SMA of first 14 TRs, then `atr += (tr − atr)/14`), recomputed once per new M5 bar
- **Tick vs bar split**: day-reset → equity-peak update → EOD flat (incl. stale prior-day position adoption/close) → DD-halt → day-lock run **every tick** (they reproduce the harness's intrabar `p_halt`/`p_lock` synthetic exits); entry pipeline runs once per **new M5 bar** (`iTime` change) — the new bar's open time IS the decision minute for the session check
- **Sizing**: riskMoney = current balance × 1%; `lossPerLot = sd/TICK_SIZE×TICK_VALUE`; lots floored to volume step; **refuse (don't bump) below VOLUME_MIN** — the user's existing helpers clamp up, which would overshoot 1% risk and break the 3.5% guard math; clamp down at VOLUME_MAX only. DD guard before sizing: `(peak − (balance − riskMoney))/peak ≥ 3.5%` → skip
- **Execution**: CTrade, `SetTypeFillingBySymbol`, deviation 100pts; market buy with SL attached (server-side — gap slippage behaves like the harness's gap-through exits), no TP; on failure log retcode and skip (signal consumed; single retry only on requote); partial fills are SL-protected by construction, log-only
- **Restart persistence** (mid-day crash/restart): layer 1 — MT5 GlobalVariables (`S11R_<magic>_day/_dsb/_peak/_halt`) written on reset/peak/halt; layer 2 fallback — recompute dayStartBalance = balance − today's closed P&L via `HistorySelect(todayMidnight, now)`, seed peak conservatively as max(dsb, equity, balance), then re-derive the halted flag by re-evaluating lock/DD on recovered values; adopt any open position with matching magic
- **Edge cases**: holiday early close (EOD can't fire) → stale-position check closes at next available tick; indicator warm-up gate in OnInit (wait, don't fail); degenerate CCI bars consistent between platforms (no cross either way)
- **OnTester()**: reuse ExpansionTrigger's day-pass scorer so Strategy Tester runs report the day-pass metric directly

## Step 3 — EA/backtest parity verification (manual, user-run; full checklist goes in README)

Gold reference command (already verified to reproduce the recorded numbers):
```
python s11.py --cache s11_full.joblib --slice final --cfg "{\"side\":\"long\",\"trigger\":\"cci\",\"rr\":99,\"sl_mult\":2.0,\"min_sd\":15,\"session\":[990,1380],\"energy\":\"none\",\"license\":\"none\"}"
```
Expected: `tr 825  win 31.6%  avgR +0.025  cov 90.2%  pass(traded) 12.9% (53/412)  brch 0  trig/d 2.5`

1. Compile in MetaEditor (zero warnings target).
2. Strategy Tester: US30, M5, "Every tick based on real ticks", 2024-07 → 2026-05, 100k deposit, broker on the CSV's server timezone.
3. **Signal-time parity** (strongest test): one sample month — every EA entry is a BUY stamped at an M5 bar open in 16:30-22:55, matching the python trigger bars ~1:1 (only ATR-refusals near the 15-pt boundary may differ)
4. Spot-check stop distances (≈2×Wilder-ATR, always >15pts) and sizing (≤1.0% of balance at stop, never over)
5. Day-lock, DD-halt, EOD behavior on known python P/halt days; **zero days touch −4%**; no overnight positions anywhere
6. Aggregate parity: trades ±10% of 825, win ±3pts of 31.6%, pass(traded) near 12.9%, breach days = 0 (tester spread ≠ recorded CSV spread, and tester compounds vs python's per-day 100k — compare day outcomes in %, not $)

## Step 4 — Archive & cleanup

1. Create `archive/` with subfolders and `git mv`-style moves (plain moves; nothing is tracked yet):
   - `archive/logs/` ← all 42 `*.log`
   - `archive/experiments/` ← dead-end scripts: `optimize.py`, `opt2.py`, `precision_bot.py`, `pruned_bot.py`, `sniper.py`, `cache_prep.py`, `strat011_wf.py`, `gravity_ftmo.py`
   - `archive/results/` ← superseded result JSONs: `strat011_wf.json`, `strat011_honest.json`, `strat011_ext.json`, `opt2_quick.json`, `gravity_ftmo_results.json` (keep `s11_stage1.json`, `s11_stage2.json` at root — they back the final report)
2. Rename `undefined/` → `framework/` (it's the gravity law book, sections 1-8); update the three references to `undefined/` in `AGENT_PROMPT.md` and `PROGRESS.md` with a one-line note
3. Delete regenerable/junk (not archived — they're reproducible or meaningless): `__pycache__/`, `us30_rf_cache.pkl`, `_smoke.csv`, `_smoke_model.joblib`, `cache_smoke.joblib`, `s11_smoke.joblib`, `us30_rf_bot - Shortcut.lnk` (keep `s11_full.joblib` locally for instant re-runs; it will be gitignored)
4. Leave `DTResources/` and `ftmo_dt_bot/` untouched (reference material / separate sub-project), both committed

## Step 5 — Git finalize

1. **`.gitignore`** (new): `US30_M1_*.csv`, `_smoke.csv`, `*.joblib`, `*.pkl`, `__pycache__/`, `*.lnk` — the 126MB CSV is over GitHub's hard limit; caches are regenerable. (`archive/` IS committed — it's small, ~200KB, and the user wants history recoverable.)
2. `git add -A` → verify with `git status` that no file >50MB is staged
3. Commit: `Finalize project: honest harness, runner strategy + EA, archived experiments` (with the standard co-author trailer)
4. `git push origin main`. Note: repo has 2 prior commits; if push is rejected (remote ahead), fetch + rebase first — do not force-push

## Step 6 — Close-out

1. Update memory: mark project wrapped in `us30-goal.md` / `us30-90pct-outcome.md` (one line each: finalized 2026-07-06, runner EA delivered, repo pushed); add `S11_Runner.mq5` to `mt5-experts-location.md`
2. Optional: republish `report.html` artifact only if its content changes (it shouldn't)

## Verification (end-to-end)

1. `python s11.py --cache s11_full.joblib --slice final --cfg "$(cat runner_config.json | jq .cfg)"` still reproduces OOS avgR +0.025 / 12.9% traded-pass / 0 breaches after all file moves (proves nothing load-bearing was archived)
2. `python -c "import s11, s11_diag"` imports clean from the reorganized root
3. Fresh clone test: `git clone` into a temp dir → README renders, `s11.py --build` works after user supplies the CSV (documented in README)
4. EA parity checklist (Step 3) — user-run in MT5; code-level review before delivery since MQL5 can't be compiled from this environment

## Explicitly out of scope (so the project can end)

- No further strategy research or parameter sweeps
- No promises of 90% day-pass — README states the honest ceiling and the real-FTMO odds
- ftmo_dt_bot/ sub-project stays as-is
