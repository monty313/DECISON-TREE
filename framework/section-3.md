## 3. The Five Biggest Issues in UTILIZING Momentum Once Found

This section assumes upstream identification is already correct: GravityState, VolatilityState, and SignalGrade have been computed on CLOSED bars per the identification rules. What follows are the five execution failures that destroy realized edge after a correct read. Each failure is neutralized by one binary guard, evaluated on CLOSED bars only, with no discretionary path around it.

### U-1 — Entering After the Move Has Extended

**Issue:** Is the entry under evaluation backed by a fresh LTF TRIGGER EVENT whose crossing bar lies within W closed bars of the current closed bar, with price not yet at the outer volatility band?

**Rule:** A TRIGGER EVENT is an INSTANT: the single closed bar on which a crossing completed. A STATE is a CONDITION that persists across bars. Entries key off trigger events; states grant holding authorization only, never entry authorization. Entry validity is a fixed window of W closed bars counted from the trigger event's bar, where W is declared per signal type before that signal type is traded. Outside the window, the persistence of the directional state is irrelevant: the entry is refused. Independently, if the current closed bar's close sits at or beyond the outer volatility band in the trade direction and no fresh trigger event exists inside the window, the location has migrated from entry-zone to exit-zone and entry is blocked.

```text
trigger_event_bar t := the single CLOSED bar on which the LTF ENTRY_TRIGGER
                       crossing completed (e.g., M5 CCI(14) closing across 0
                       in the regime direction)
bars_since := index(current_closed_bar) - index(t)

WINDOW_OPEN     := (bars_since <= W)                    // W fixed per signal type
EXTENSION_BLOCK := (close >= BB(20).upper)              // long side; mirror for shorts

ENTRY_ALLOWED := WINDOW_OPEN == true
             AND EXTENSION_BLOCK == false
             AND DUAL-TF GATE == PASS
             AND ENERGY GATE == PASS
// A true directional STATE (e.g., CCI(14) > 0 for many bars) with
// bars_since > W yields ENTRY_ALLOWED == false. No exception.
```

**Application:** Signal type: M5 CCI(14) upward zero-cross, declared W = 3. At the 10:35 M5 closed bar, CCI(14) closes at +34 after the prior closed bar's −12 — a completed upward crossing, so bar 10:35 is the trigger event, index t. Evaluation at the 10:50 closed bar: bars_since = 3 ≤ 3 → WINDOW_OPEN true. Close = 44,120; BB(20) upper on M5 = 44,180; 44,120 < 44,180 → EXTENSION_BLOCK false. DUAL-TF GATE: M1 close 44,121 > SMA(4) shifted forward 8 at 44,096 → BULL; M15 close 44,115 > its shifted SMA(4) at 44,060 → BULL; both equal and directional → PASS. ENERGY GATE: M5 ADX(14) = 27.1 > its SMA(1) shifted 5 at 24.8 → true; M5 ATR(14) = 18.4 > its shifted baseline 16.9 → true → PASS. ENTRY_ALLOWED = true. Evaluation at the 10:55 closed bar instead: bars_since = 4 > 3 → WINDOW_OPEN false → ENTRY_ALLOWED = false, even though CCI(14) = +58 remains above 0 (state true, event stale). Second scenario at 10:45: bars_since = 2 (window open) but close = 44,205 ≥ BB(20) upper 44,190 → EXTENSION_BLOCK true → entry refused; the setup is in the exit-zone.

**Conclusion (Generalized Principle):** Entry rights are granted by events and expire on a fixed closed-bar count; states never substitute for events. For any indicator on any instrument and timeframe, the agent must be able to name the single closed bar on which the crossing completed and prove bars_since ≤ W; additionally, price located at the outer volatility envelope with no in-window event reclassifies the location from entry-zone to exit-zone regardless of how directional the state remains. Transfer test: given a new indicator, the agent outputs the exact closed-bar index of the claimed crossing event and the computed bars_since; if it can only assert that a condition "is currently true" without an event bar index, it has a state, not a trigger, and must refuse the entry.

### U-2 — Holding Through a Regime Flip

**Issue:** Does the exact condition set that licensed the open position still evaluate true on the current closed bar?

**Rule:** Every entry rule carries a mirrored, non-negotiable exit rule constructed mechanically from the entry condition itself. At fill time the agent stores ENTRY_LICENSE: the full machine-checkable predicate that authorized the entry (for a directional trade, at minimum the DUAL-TF GATE in the trade direction). On every closed bar of the evaluation timeframe while the position is open, ENTRY_LICENSE is re-evaluated verbatim. The first closed bar on which it evaluates false forces CLOSE_POSITION at the next available price. There is no confirmation wait, no partial hold, no re-check on a slower timeframe, and no override input. A position whose license predicate is not stored, or not scheduled for per-closed-bar re-evaluation, is an illegal position and must be closed.

```text
at fill:
    ENTRY_LICENSE := stored copy of the exact entry predicate, e.g. for a long:
        (M1 close > SMA(4) shifted forward 8 on M1)      // M1 GravityState == BULL
    AND (M15 close > SMA(4) shifted forward 8 on M15)     // M15 GravityState == BULL
    // i.e., DUAL-TF GATE == PASS with both == BULL

on every CLOSED bar of the evaluation timeframe while position open:
    if evaluate(ENTRY_LICENSE) == false:
        CLOSE_POSITION at next available price            // unconditional
```

**Application:** Long US30 entered at 14:10 under the license above, evaluated on the M1 closed-bar schedule. 14:30 M1 close: M1 close 44,042 > shifted SMA(4) 44,031 → true; last M15 closed bar (14:30) close 44,040 > its shifted SMA(4) 43,995 → true; license true → hold. 14:32 M1 close: M1 close 44,010 < shifted SMA(4) 44,025 → M1 leg false; M15 leg (last closed 14:30 bar) still true. License requires both; the two GravityStates are no longer equal and directional → DUAL-TF GATE FAIL → license false → mandatory close executes at the next available price. By 14:45 the M15 closed bar has also dropped below its shifted SMA(4) — price below SMA(4) shift 8 on both M1 and M15, the full regime flip — but the mirror rule already exited 13 minutes earlier at the first license failure, surrendering none of the deterioration between first failure and full flip. Holding through 14:32 "to see if it recovers" is not a defined operation; no rule path produces it.

**Conclusion (Generalized Principle):** Every position carries a live license: the exact predicate that authorized entry, stored at fill and re-evaluated on every closed bar; its first failure is an unconditional close instruction. Entry logic and exit logic are the same predicate observed at two different times — for any indicator set, instrument, and timeframe, if condition C justified opening, then NOT C on any later closed bar mandates closing, with zero judgment inserted between detection and execution. Transfer test: for a new indicator, the agent verifies that the stored license predicate is byte-identical to the condition it evaluated at fill time and that a per-closed-bar re-evaluation job exists for it; if either is missing, the position is illegal and is closed immediately.

### U-3 — Ignoring Signal Decay and Edge Half-Life

**Issue:** Is the intended position size less than or equal to the size fraction assigned by the pre-declared decay schedule to the current bars-since-trigger count?

**Rule:** Every momentum signal type carries a decay clock that starts at its TRIGGER EVENT. Before a signal type is traded for the first time, a decay schedule must be on file: a mapping from bars_since_trigger to allowed_size_fraction that is monotone non-increasing and terminates at 0.00. No schedule on file = the signal type is untradeable (treated as NO_SIGNAL for sizing). Position risk = base risk (never more than 1% of account) × allowed_size_fraction. Entry at fraction 0.00 is forbidden. The U-1 trigger window W and this schedule are the same object viewed two ways: W = max{b : fraction(b) > 0}. Fast signal types decay within bars; slow ones within hours to days; the schedule encodes this per type, never per trade.

```text
require schedule[signal_type] exists                  // declared BEFORE first trade
require monotone_non_increasing(schedule[signal_type])
require final_entry(schedule[signal_type]).fraction == 0.00

fraction := schedule[signal_type][bars_since_trigger]
allowed_risk := base_risk * fraction                  // base_risk <= 1% of account

SIZE_OK := (fraction > 0.00) AND (requested_risk <= allowed_risk)
// SIZE_OK == false -> entry refused; resizing down to allowed_risk is the
// only permitted correction.
```

Declared schedule for signal type "M5 trinity SUPER" (UNANIMITY TEST pass on CCI(14)/CCI(100)/CCI(900), each smoothed by its own SMA(20), all beyond +100, fastest breaking its extreme; VolatilityState == GREAT_MOVEMENT):

| Bars since trigger (closed M5 bars) | Allowed size fraction | Risk at 1.00% base |
| --- | --- | --- |
| 0–2 | 1.00 | 1.00% |
| 3–5 | 0.50 | 0.50% |
| 6–8 | 0.25 | 0.25% |
| ≥9 | 0.00 (entry forbidden) | 0.00% |

**Application:** Account = 100,000; base risk = 1.00% = 1,000. The SUPER trigger event fires on the M5 bar closing 09:35 (all three CCIs above +100 on the same closed bar with CCI(14) breaking its extreme, DUAL-TF GATE PASS). Entry evaluated at the 09:55 closed bar: bars_since_trigger = 4 → bracket 3–5 → fraction 0.50 → allowed_risk = 500. Requested risk 750: 750 ≤ 500 false → SIZE_OK false → entry refused; resubmission at 500 → true → entry executes at 0.50% risk. Same signal evaluated at bars_since_trigger = 9 → fraction 0.00 → entry forbidden regardless of how the state reads. Separate case: a newly proposed signal type "M1 stochastic(5,3,3) cross" has no schedule on file → untradeable until a schedule is declared and validated.

**Conclusion (Generalized Principle):** A signal's authority over capital decays on a declared clock that starts at the trigger event; size is a function of event age alone, never of how convincing the persisting state appears, and an undeclared decay schedule means an untradeable signal. This holds for any indicator, instrument, and timeframe: fast triggers get short non-zero regions, slow triggers get long ones, and every schedule ends at zero. Transfer test: before trading a new indicator's trigger, the agent verifies a monotone non-increasing fraction table terminating at 0.00 exists on file for that signal type, then computes the allowed fraction from bars_since_trigger alone and confirms the requested size does not exceed it.

### U-4 — No Re-Entry Logic After Whipsaw Exits

**Issue:** After an exit fired by the fast exit trigger, does the regime license (DUAL-TF GATE PASS AND ENERGY GATE PASS in the prior trade's direction) still evaluate true on the current closed bar?

**Rule:** The fast exit trigger (role: EXIT_MANAGER) and the regime license are independent objects; one firing says nothing about the other. When a position is closed by the fast exit trigger on a closed bar where the regime license still evaluates true, the agent sets REENTRY_ARMED := true. While REENTRY_ARMED is true, the next fresh LTF ENTRY_TRIGGER event in the license direction mandates a new entry — subject to the U-1 window of the NEW event, the U-3 decay schedule reset to bar 0 of the NEW event, and the U-5 exposure check. Re-entry under these conditions is a RULE; skipping it is a rule violation, not caution. REENTRY_ARMED is revoked on the first closed bar where the regime license evaluates false.

```text
on fast_exit_trigger fires (position closes):
    LICENSE := (DUAL-TF GATE == PASS) AND (ENERGY GATE == PASS)   // same direction
    REENTRY_ARMED := (LICENSE == true)

on every CLOSED bar while REENTRY_ARMED:
    if LICENSE == false: REENTRY_ARMED := false
    else if fresh LTF ENTRY_TRIGGER event in license direction:
        ENTER (new trigger event => new U-1 window, U-3 clock reset to 0,
               U-5 exposure check)                                 // mandatory
```

**Application:** Long US30 on M5, entered from an M5 CCI(14) upward zero-cross; EXIT_MANAGER is RSI(7) closing below 50. At the 11:40 M5 closed bar, RSI(7) = 47.2 < 50 → exit executes. License check on the same closed bar: M1 close 44,130 > SMA(4) shifted forward 8 at 44,102 → true; M15 close 44,125 > its shifted SMA(4) at 44,070 → true → DUAL-TF GATE PASS. ENERGY GATE on M5: ADX(14) = 26.3 > its SMA(1) shifted 5 at 23.9 → true; ATR(14) = 17.2 > 15.8 → true → PASS. LICENSE true → REENTRY_ARMED := true. At the 11:55 closed bar, M5 CCI(14) closes at +21 after the prior bar's −8 → fresh upward zero-cross event. U-1: bars_since = 0 ≤ W → true. U-3: fraction(0) = 1.00 → full 1.00% risk. U-5: no open position shares this signal source → pass. Entry is mandatory and executes. Counterfactual at 11:40: had the M15 leg read 44,050 < 44,070, the license would be false, REENTRY_ARMED := false, and the 11:55 trigger event would be ignored.

**Conclusion (Generalized Principle):** An exit fired by the fastest layer terminates a trade, not the authorization to trade; authorization lives in the slower state gates, and while those states hold, each fresh timing event obligates a re-entry — the agent harvests a regime as a sequence of trades cycled by the fast layer, not as one trade defended past its exit. This applies to any fast/slow indicator pairing on any instrument: separate the object that closes trades from the object that licenses trading. Transfer test: for a new fast exit indicator, the agent verifies that closing the position leaves the license variables untouched and that REENTRY_ARMED is set true exactly when the license predicate evaluates true on the exit bar.

### U-5 — Overexposure via Correlated Instruments on the Same Signal

**Issue:** Is the candidate entry's signal source already represented in the open position set, either by an identical signal_source_id or by an open instrument whose |rho| with the candidate instrument exceeds 0.70?

**Rule:** Risk budget attaches to independent signal sources, not to instruments. Every entry carries a signal_source_id identifying the upstream signal instance that produced it (indicator set + timeframe + trigger event bar). Before any entry, two binary checks run against every open position: (1) identity — candidate.signal_source_id equals the open position's signal_source_id; (2) co-movement — |rho| between the candidate instrument and the open position's instrument exceeds 0.70, where rho is the Pearson correlation of log returns over a declared lookback (100 closed H1 bars in this configuration; lookback and timeframe are fixed in portfolio config before trading). Either check true for any open position → ENTRY BLOCKED. Instruments inside the same rho-cluster count as one instrument: total risk across them is capped at the single-source budget (1% of account), and adding a second position in the cluster is scaling in on one signal, which is forbidden.

```text
for each open_position P:
    CHECK_SOURCE := (candidate.signal_source_id == P.signal_source_id)
    CHECK_RHO    := (abs(rho(candidate.instrument, P.instrument,
                             lookback=100 closed H1 bars, log_returns)) > 0.70)
    if CHECK_SOURCE == true OR CHECK_RHO == true:
        ENTRY := BLOCKED

require sum(risk of positions sharing a source or rho-cluster) <= 1% of account
```

**Application:** Open position: long US30, signal_source_id = "H1-REGIME-BULL/20260706-0900" (H1 close > SMA(200) AND > BB(200) middle band; DUAL-TF GATE PASS). Candidate: long XLK (technology sector ETF), generated by the same H1 regime signal. Check 1: candidate.signal_source_id == open.signal_source_id → true → ENTRY BLOCKED; evaluation stops. Hypothetical variant with a distinct source id: Check 1 false; Check 2: rho(US30, XLK) over the last 100 closed H1 bars of log returns = +0.83; |0.83| > 0.70 → true → ENTRY BLOCKED. The two longs were one bet on one signal wearing two tickers; a single adverse H1 bar would have hit both simultaneously, doubling effective risk on a 1% budget. Contrast case: candidate long XAUUSD from an independent M15 pullback signal (its own source id); Check 1 false; rho(US30, XAUUSD) = +0.22; |0.22| > 0.70 false → both checks false → entry allowed under its own separate 1% budget.

**Conclusion (Generalized Principle):** Exposure is counted per underlying signal source; instruments whose returns co-move above a fixed correlation threshold are one instrument for risk purposes, and one signal source is entitled to at most one position's worth of risk no matter how many tickers can express it. The pre-entry check is a source-id lookup plus one correlation computation against each open position — never a qualitative judgment about diversification. This holds for any signal, instrument universe, and timeframe: declare the correlation metric, lookback, and threshold before trading, then enforce them as binary gates. Transfer test: before entering on a new instrument, the agent prints the signal_source_id of every open position and the computed |rho| between the candidate and each open instrument, and confirms every pair passes both binary thresholds.
