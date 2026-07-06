## 6. Multi-Period Synergy of a Single Indicator

This section defines how N period instances of ONE indicator family combine into a single compounded directional force, and why that combination is strictly binary. SY-1 specifies the compounding condition and the division of labor: slow instances are the mass (standing confirmation, a STATE), the fastest instance is the orbit (trigger events and the exit clock). SY-2 specifies the only failure mode: any disagreement by any instance is UNANIMOUS(false) = NO_SIGNAL, the bar is skipped, and skipped bars never enter any statistic. All readings in this section are CLOSED-bar readings.

### SY-1 — Unanimous Multi-Period Alignment Creates Compounding Push

**Issue:** Do all N period instances of one indicator family, each measured against its own independent smoothing line, sit on the same directional side of the family equilibrium threshold AND on the same side of their own smoothing line on the current CLOSED bar, so that the family qualifies as one compounded directional force with the fastest instance assigned as trigger and exit clock?

**Rule:** The family MUST contain N >= 3 nested periods P[1] < P[2] < ... < P[N] of the SAME indicator, where P[1] is the fastest. Each instance MUST carry its own independent smoothing line S[i]; a shared smoothing line disqualifies the configuration. A stricter alignment threshold T is permitted in place of the raw equilibrium EQ only if T lies on the directional side of EQ, so that passing T entails passing EQ. UNANIMITY is evaluated per the canonical UNANIMITY TEST. On UNANIMOUS(true), roles are assigned mechanically: all slower instances become GRAVITY_FILTER (a persisting STATE that licenses entries), and the fastest instance alone becomes ENTRY_TRIGGER and EXIT_MANAGER (instantaneous EVENTS). SignalGrade is computed as follows and takes no other value:

```text
INPUTS (current CLOSED bar only):
  family F, nested periods P[1] < P[2] < ... < P[N]     # P[1] = fastest
  S[i] = independent smoothing line of F(P[i])
  EQ = family equilibrium; thresholds T_bull >= EQ, T_bear <= EQ

bull[i] = ( F(P[i]) > T_bull ) AND ( F(P[i]) > S[i] )
bear[i] = ( F(P[i]) < T_bear ) AND ( F(P[i]) < S[i] )

UNANIMOUS_BULL = bull[1] AND bull[2] AND ... AND bull[N]
UNANIMOUS_BEAR = bear[1] AND bear[2] AND ... AND bear[N]
UNANIMOUS(true) = UNANIMOUS_BULL OR UNANIMOUS_BEAR

IF UNANIMOUS(true):
    role(F(P[2..N])) = GRAVITY_FILTER                   # mass: STATE, licenses entries
    role(F(P[1]))    = ENTRY_TRIGGER + EXIT_MANAGER     # orbit: EVENTS, times entries/exits
    IF DUAL-TF GATE == pass
       AND VolatilityState == GREAT_MOVEMENT
       AND fresh ENTRY_TRIGGER event on F(P[1]) inside its trigger window:
        SignalGrade = SUPER
    ELIF DUAL-TF GATE == pass
       AND VolatilityState IN {TRADABLE, GREAT_MOVEMENT}
       AND fresh ENTRY_TRIGGER event on F(P[1]):
        SignalGrade = STANDARD
    ELSE:
        SignalGrade = NO_SIGNAL      # license held, no trigger event: WAIT
    RE-ENTRY LICENSE: while UNANIMOUS(true) holds on each new CLOSED bar,
        each fresh F(P[1]) trigger event = one new licensed entry
    EXIT: keyed off F(P[1]) alone; F(P[2..N]) never issue exits
ELSE:
    SignalGrade = NO_SIGNAL
```

**Application:** CCI trinity on US30 M5. Instances: CCI(14), CCI(100), CCI(900), each smoothed by its own SMA(20). T_bull = +100 (stricter than EQ = 0; +100 pass entails 0 pass). On the CLOSED M5 bar at 14:35: (1) CCI(14) = +168 > +100 → true; +168 > its SMA(20) = +121 → true; bull[1] = true. (2) CCI(100) = +134 > +100 → true; +134 > its SMA(20) = +112 → true; bull[2] = true. (3) CCI(900) = +118 > +100 → true; +118 > its SMA(20) = +104 → true; bull[3] = true. (4) UNANIMOUS_BULL = true. (5) Fresh trigger event: CCI(14) closed this bar at +214 versus +196 on the prior closed bar — the crossing of the +200 extreme completed on this single closed bar, so a trigger event (an INSTANT) exists. (6) DUAL-TF GATE: H1 GravityState = BULL (H1 CCI(140) = +87 > 0 AND above its own SMA(1) shifted forward 4 bars); M5 GravityState = BULL; both equal and directional → pass. (7) ENERGY GATE: M5 ADX(14) = 31 > its SMA(1) shifted 5 bars = 27 → true; M5 ATR(14) = 14.2 > its SMA(1) shifted 5 bars = 12.9 → true → VolatilityState = GREAT_MOVEMENT. (8) All four SUPER conditions true → SignalGrade = SUPER; long entry at the next bar open. Exit clock: CCI(14) alone — exit on the first CLOSED M5 bar with CCI(14) below its SMA(20). CCI(100) and CCI(900) never issue exits; when their own alignment fails, they revoke the re-entry license only. While bull[2] and bull[3] remain true, each fresh CCI(14) recross above +100 after an exit is a new licensed entry — the trades cycle on the fast clock while the mass holds. Second instantiation, same structure with different raw material: SMA fan on M15 — five SMA(4) instances at shifts 0, 1, 2, 3, 4, plus SMA(50). Bull fan condition on the CLOSED bar: SMA(4,shift 0) > SMA(4,shift 1) > SMA(4,shift 2) > SMA(4,shift 3) > SMA(4,shift 4) AND all five above SMA(50). Here period diversity is instantiated as shift diversity, and each instance's "own baseline" is the adjacent slower-shifted instance; the strict monotonic ordering is the unanimity readout. This is a conserved directional force — a STATE that licenses — not a crossing event; the trigger event still comes from the fastest element (M5 CCI(14) crossing 0 in the fan's direction). The transferable point of both examples is identical: many instances of one measurement, each with an independent baseline, unanimously aligned, behave as one compounded signal with fast = clock and slow = confirmation.

**Conclusion (Generalized Principle):** For ANY indicator family on ANY instrument and ANY timeframe: N nested speed instances of the same indicator, each with one independent smoothing baseline, evaluated as a single boolean AND over side-of-equilibrium and side-of-own-baseline, constitute one compounded signal that is materially stronger than any single instance. The slow instances contribute persistence — mass, a STATE used as a re-entry license (GRAVITY_FILTER) — and the fastest instance contributes timing — orbit, EVENTS used as ENTRY_TRIGGER and EXIT_MANAGER. This division of labor is the exact mechanism that authorizes multiple rapid low-timeframe re-entries: the fast clock opens and closes trades repeatedly while the slow mass holds UNANIMOUS(true), and the license dies the instant unanimity dies. The structure is indifferent to whether "speed diversity" comes from lookback periods (CCI 14/100/900) or from forward shifts of one period (SMA(4) at shifts 0–4); what is required is N instances, independent baselines, and a boolean unanimity readout. Transfer test: For a never-seen indicator, the agent instantiates N nested speed variants each with its own smoothing baseline, confirms its code emits exactly one boolean UNANIMOUS(true/false) per CLOSED bar, and confirms role assignment is fastest = ENTRY_TRIGGER/EXIT_MANAGER and all slower = GRAVITY_FILTER — any instance lacking its own baseline, or any non-boolean output, means the principle was misapplied.

### SY-2 — Partial Agreement Is NO_SIGNAL, Not Weak Signal

**Issue:** Is the current CLOSED bar classified NO_SIGNAL whenever at least one of the N period instances of the indicator family sits on the wrong side of its equilibrium threshold OR on the wrong side of its own smoothing line?

**Rule:** Unanimity is a boolean AND across all N instances. One failed check by one instance — wrong side of the equilibrium threshold OR wrong side of its own smoothing line — collapses the entire family readout to UNANIMOUS(false) = NO_SIGNAL. There is no partial grade: no 2-of-3 vote, no weighted sum, no scaled position size, no "weak signal" output. SignalGrade takes only values in {NO_SIGNAL, STANDARD, SUPER}, and UNANIMOUS(false) maps to exactly NO_SIGNAL. Bars classified NO_SIGNAL are SKIPPED and are EXCLUDED from every performance statistic: win rate, expectancy, and edge denominators contain licensed bars only. Substituting agreement from an UNRELATED indicator for a failed family member is forbidden: majority voting across unrelated indicators is not synergy and never satisfies the UNANIMITY TEST, which requires the SAME indicator family at nested periods.

```text
FOR the current CLOSED bar, family F, instances i = 1..N:
  bull[i] = ( F(P[i]) > T_bull ) AND ( F(P[i]) > S[i] )
  bear[i] = ( F(P[i]) < T_bear ) AND ( F(P[i]) < S[i] )

IF NOT ( AND(bull[1..N]) OR AND(bear[1..N]) ):
    UNANIMOUS(false)
    SignalGrade = NO_SIGNAL          # never "weak", never fractional, never scaled
    action     = SKIP bar
    statistics = bar EXCLUDED from win-rate / expectancy / edge denominators
                 (denominator = licensed bars only)

FORBIDDEN OPERATIONS:
  - vote counting inside the family (2-of-3, majority, weighted average)
  - position sizing proportional to the number of agreeing instances
  - replacing a failed family member with an UNRELATED indicator's reading
    (cross-family majority voting != UNANIMITY TEST; it does not qualify)
```

**Application:** CCI trinity on US30 M5, same configuration as SY-1 (CCI(14), CCI(100), CCI(900), each with its own SMA(20), T_bull = +100). On the CLOSED M5 bar at 15:10: (1) CCI(14) = +156 > +100 → true; +156 > its SMA(20) = +120 → true; bull[1] = true. (2) CCI(100) = +141 > +100 → true; +141 > its SMA(20) = +117 → true; bull[2] = true. (3) CCI(900) = +64: is +64 > +100 → false; the side-of-own-smoothing check is irrelevant once the first check fails; bull[3] = false. (4) AND(bull[1..3]) = false; AND(bear[1..3]) = false; UNANIMOUS(false). (5) SignalGrade = NO_SIGNAL. Two of three readings are bullish and the classification is still NO_SIGNAL, because "2-of-3 bullish" is not a defined output — the slow mass has not confirmed, so there is no compounded force to trade. (6) The bar is skipped and does not enter the win-rate denominator; only bars carrying a license populate edge statistics, so reported edge is never diluted or inflated by unlicensed bars. (7) Forbidden repair: reading RSI(14) = 63 > 50 and counting it as a third bullish vote to replace the failed CCI(900) does NOT restore unanimity — RSI is a different family measuring a different quantity, so its agreement is coincidence, not compounding; nested periods of one family measure one force at different masses, which is the only structure that compounds. The exhaustive enumeration for a three-instance family (aligned = correct side of threshold AND of own smoothing; MISALIGNED = fails either check):

| # | Fast F(P1) — CCI(14) | Mid F(P2) — CCI(100) | Slow F(P3) — CCI(900) | UNANIMITY | Classification |
|---|---|---|---|---|---|
| 1 | BULL-aligned + fresh extreme-break event | BULL-aligned | BULL-aligned | UNANIMOUS(true) | SUPER candidate (still requires DUAL-TF GATE pass + GREAT_MOVEMENT) |
| 2 | BULL-aligned, no fresh event this bar | BULL-aligned | BULL-aligned | UNANIMOUS(true) | STANDARD candidate (license held; WAIT for trigger event) |
| 3 | BEAR-aligned + fresh extreme-break event | BEAR-aligned | BEAR-aligned | UNANIMOUS(true) | SUPER candidate, short (same gate requirements) |
| 4 | BEAR-aligned, no fresh event this bar | BEAR-aligned | BEAR-aligned | UNANIMOUS(true) | STANDARD candidate, short (license held; WAIT) |
| 5 | MISALIGNED | BULL-aligned | BULL-aligned | UNANIMOUS(false) | NO_SIGNAL |
| 6 | BULL-aligned | MISALIGNED | BULL-aligned | UNANIMOUS(false) | NO_SIGNAL |
| 7 | BULL-aligned | BULL-aligned | MISALIGNED | UNANIMOUS(false) | NO_SIGNAL |
| 8 | BULL-aligned | BEAR-aligned | BEAR-aligned | UNANIMOUS(false) | NO_SIGNAL |
| 9 | BEAR-aligned | BULL-aligned | BULL-aligned | UNANIMOUS(false) | NO_SIGNAL |
| 10 | BULL-aligned | BEAR-aligned | BULL-aligned | UNANIMOUS(false) | NO_SIGNAL |

**Conclusion (Generalized Principle):** For ANY indicator family, unanimity is a boolean AND over all N instances, where each instance contributes two sub-checks (side of equilibrium threshold, side of its own smoothing line) and one failed sub-check anywhere collapses the family output to UNANIMOUS(false) = NO_SIGNAL. Graded confidence, vote counts, and agreement-proportional sizing are undefined operations on this output; the only legal downstream values are the members of SignalGrade. The statistical population is defined by the license, not the calendar: bars failing unanimity are skipped and excluded from every win-rate and edge denominator, so measured edge describes licensed bars only. Cross-family agreement never substitutes for within-family unanimity — synergy exists only among nested periods of one measurement, because only there does agreement represent the same force observed at different masses rather than a coincidence of unrelated quantities. Transfer test: For a never-seen indicator, the agent runs a unit test that flips exactly one instance to the wrong side of either its equilibrium threshold or its own smoothing line and verifies that the classifier output becomes NO_SIGNAL and the bar vanishes from the win-rate denominator — any surviving partial grade, vote count, or statistic containing that bar means the principle was misapplied.
