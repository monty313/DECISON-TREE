## 8. Case Studies: Auditing a Real Strategy Portfolio Against the Framework

The framework is operational only if it can decompose, audit, and repair real strategies; a taxonomy that cannot process an arbitrary candidate strategy is dead weight. This section runs eleven real portfolio strategies through the framework as graded case studies. The skill being trained is the AUDIT — the mechanical decomposition of any strategy into roles, gates, licenses, and risk mappings — not the strategies themselves. Every audit below terminates in a binary verdict and, where the verdict is NON_COMPLIANT, an exact repair.

### CS-1 — Is a Candidate Strategy Framework-Compliant?

**Issue:** Given a candidate strategy specification, can every component be decomposed into framework roles and gates such that all six compliance checks return true?

**Rule:** A strategy is COMPLIANT(true) only if ALL six checks below evaluate true. ANY check that evaluates false or that the specification leaves unanswered forces COMPLIANT(false) = NON_COMPLIANT. A NON_COMPLIANT strategy is either repaired by importing the missing gate from another compliant component (example: pairing with the STRAT-006 volatility filter as the ENERGY GATE) or it is not traded. There is no third state and no partial credit.

```text
COMPLIANT(strategy) :=
     CHECK_1_ROLE_INTEGRITY:  every indicator instance maps to exactly one role in
                              {GRAVITY_FILTER, VOLATILITY_GATE, ENTRY_TRIGGER, EXIT_MANAGER};
                              an instance with zero roles is removed; an instance with two
                              duties is split into two declared instances, one role each   # F-5
AND  CHECK_2_ROLE_COVERAGE:   some component answers each of the four role questions:
                              GRAVITY_FILTER  -> GravityState in {BULL, BEAR, NEUTRAL}
                              VOLATILITY_GATE -> VolatilityState in
                                 {NOTHING_HAPPENING, TRADABLE, GREAT_MOVEMENT}
                              ENTRY_TRIGGER   -> a trigger EVENT defined on a closed bar
                              EXIT_MANAGER    -> a mandatory exit condition
AND  CHECK_3_DUAL_TF_GATE:    HTF GravityState and LTF GravityState computed independently,
                              entry permitted only if equal AND directional
                              (both BULL or both BEAR), for EVERY SignalGrade              # F-1
AND  CHECK_4_MIRRORED_EXIT:   every entry condition has a mirrored mandatory exit;
                              regime-flip failure => automatic close                       # U-2
AND  CHECK_5_REENTRY_LICENSE: a standing license state is defined (PERSISTENCE TEST
                              + ENERGY GATE), re-evaluated every closed bar; license
                              failure stops NEW entries only                          # P-1, P-3
AND  CHECK_6_RISK_MAPPING:    per-trade risk <= 1% of equity, no scaling in against
                              dominant gravity, and correlated instruments on the same
                              signal source capped to one position                    # R-1, U-5

if COMPLIANT(strategy) == false:
    repair = import each missing gate from a compliant component  # example: STRAT-006
    if repair impossible: DO_NOT_TRADE(strategy)
    else: re-run all six checks on the repaired bundle; trade only on COMPLIANT(true)
```

**Application:** Audit of STRAT-002 "CCI Surge Sentinel" (HTF = H1, LTF = M15). Specification: H1 CCI(30) and H1 CCI(100) both > 0 AND M15 CCI(30) and M15 CCI(100) both > 0 = bull momentum; both M15 CCIs > +100 = super surge; exit on M15 RSI(7) crossing 50 against the position; re-enter immediately if the CCI conditions hold; trail on CCI(100) zero-cross against; catastrophic stop when both CCIs sit at the opposite extreme.

- CHECK_1 (role integrity): H1 CCI(30) → GRAVITY_FILTER. H1 CCI(100) → GRAVITY_FILTER. M15 CCI(30) → ENTRY_TRIGGER. M15 CCI(100) has two duties in the spec (entry state and trail), which violates F-5 for a single instance; the audit splits it into two declared instances — M15 CCI(100)[entry copy] → ENTRY_TRIGGER and M15 CCI(100)[trail copy] → EXIT_MANAGER. M15 RSI(7) → EXIT_MANAGER. Opposite-extreme stop → EXIT_MANAGER. After the split, every instance holds exactly one role. **true.**
- CHECK_2 (role coverage): GravityState — yes (mixed-sign CCIs = NEUTRAL under F-2, aligned = BULL/BEAR). ENTRY_TRIGGER — yes (the closed M15 bar on which the second CCI completes its zero-cross is the trigger event). EXIT_MANAGER — yes. VOLATILITY_GATE — **no component classifies VolatilityState.** CCI > +100 is directional displacement of an oscillator, not an energy measurement; the strategy defines direction-NEUTRAL (F-2) but has no NOTHING_HAPPENING state (F-3). **false.** Verdict is already NON_COMPLIANT; the audit continues to build the repair inventory.
- CHECK_3 (DUAL-TF GATE): the spec requires H1 both > 0 AND M15 both > 0 for every entry, computed independently. **true.**
- CHECK_4 (mirrored exit): entry state = both CCIs > 0; mirrored exit = M15 CCI(100)[trail copy] zero-cross against, plus RSI(7) fast exit, plus opposite-extreme stop. Regime flip closes the position. **true.**
- CHECK_5 (re-entry license): "re-enter immediately if CCI conditions hold" defines a standing license re-evaluated every closed bar (P-3). **true.**
- CHECK_6 (risk mapping): no per-trade risk fraction, no correlation cap anywhere in the spec. **false.**

Result: checks 2 and 6 false → NON_COMPLIANT standalone. Repair: (a) import STRAT-006 as the ENERGY GATE — entries permitted only when STRAT-006 returns VolatilityState ∈ {TRADABLE, GREAT_MOVEMENT}, and the "super surge" grade re-labeled SUPER only when VolatilityState == GREAT_MOVEMENT; (b) bind R-1 sizing (position size = 1% of equity ÷ stop distance) and U-5 (one position per signal source). Re-run: all six checks true → the repaired bundle is COMPLIANT and tradable.

**Conclusion (Generalized Principle):** A strategy is not a named object to be believed or doubted; it is a bundle of answers to the four role questions plus three structural guarantees (dual-timeframe agreement, mirrored exits, bounded risk). Onboarding any candidate strategy — regardless of its indicators, instrument, timeframe, or origin — consists of decomposing it into that bundle, scoring each of the six checks binary, and either importing the missing answers from already-compliant components or refusing to trade it. Compliance is a property of the assembled bundle, never of the strategy name, and it is re-evaluated whenever any component changes. Transfer test: given a strategy specification the agent has never seen, the agent produces the six-check table with a binary verdict per check and, for every false, names the exact component or rule ID that repairs it — or outputs DO_NOT_TRADE.

### Case Study: STRAT-001 — Regime Pulse Tracker

**Mechanical summary:** H1 price above both the BB(200) middle and BB(20) middle defines the up regime; M15 pullback entries at the BB(20) middle/lower band, or SUPER entry when price pierces the BB(20) upper band on both timeframes; exit on M15 RSI(7) crossing 50 against the position, trail on BB(20) middle flip, hard stop 1–2% beyond the BB(20) outer band; "Full Neutral Chop" regime = wait.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| Price vs BB(200) middle | H1 | GRAVITY_FILTER | HTF gravity |
| Price vs BB(20) middle | H1 | GRAVITY_FILTER | HTF gravity |
| Price vs BB(20) upper band (SUPER state) | H1 | GRAVITY_FILTER | HTF gravity |
| BB(20) middle/lower touch (pullback entry copy) | M15 | ENTRY_TRIGGER | LTF timing |
| BB(20) upper-band pierce (SUPER entry event) | M15 | ENTRY_TRIGGER | LTF timing |
| RSI(7) 50-cross against position | M15 | EXIT_MANAGER | exit |
| BB(20) middle flip (trail copy) | M15 | EXIT_MANAGER | exit |
| Hard stop 1–2% beyond BB(20) outer band | M15 | EXIT_MANAGER | exit |

Note on F-5: M15 BB(20) serves entry, trail, and stop reference in the raw spec; the audit declares separate instances (entry copy, trail copy, stop reference) so each holds exactly one role. The H1 upper-band pierce is a STATE (SUPER authorization); the M15 pierce is the EVENT (entry).

**Rules instantiated:**
- G-1 — BB middles are unbounded price-tracking masses, not oscillators.
- G-2 — BB(200) is the heavier mass; on disagreement it dominates and BB(20) is timing only.
- F-1 — the SUPER path requires the upper-band pierce on H1 AND M15 independently.
- F-2 — the "Full Neutral Chop = Wait" table row is NEUTRAL = no momentum entries.
- E-1 — pullback to the BB(20) middle/lower in a directional regime is the retrace-to-gravity-line entry.
- E-2 — the dual-TF band pierce is the volatility-band-pierce SUPER entry.
- U-2 — RSI(7) 50-cross against position is the mirrored fast exit.
- U-4 / P-3 — "re-enter immediately if BB conditions still valid" is the re-entry loop under a standing license.

**Gap audit:** CHECK_1 PASS (after instance splitting). CHECK_2 FAIL — "Full Neutral Chop" is directional NEUTRAL (F-2), not a VolatilityState; no component answers the energy question (F-3). CHECK_3 PASS. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — the hard stop fixes price location, not account risk; no equity fraction, no correlation cap. Repair: import STRAT-006 as ENERGY GATE; bind R-1 sizing and U-5.

**Generalized lesson:** Directional NEUTRAL (F-2) and energy-dead NOTHING_HAPPENING (F-3) are independent blocking states; defining one never defines the other, and a compliant strategy must hold both.

### Case Study: STRAT-002 — CCI Surge Sentinel

**Mechanical summary:** H1 and M15 CCI(30)+CCI(100) all > 0 = bull momentum (mirror for bear), M15 pair > +100 = "super surge"; exit on M15 RSI(7) 50-cross against, trail on CCI(100) zero-cross against, stop when both CCIs reach the opposite extreme; immediate re-entry while the CCI state holds.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| CCI(30) vs 0 | H1 | GRAVITY_FILTER | HTF gravity |
| CCI(100) vs 0 | H1 | GRAVITY_FILTER | HTF gravity |
| CCI(30) zero-cross / +100 threshold | M15 | ENTRY_TRIGGER | LTF timing |
| CCI(100) (entry-state copy) | M15 | ENTRY_TRIGGER | LTF timing |
| CCI(100) zero-cross against (trail copy) | M15 | EXIT_MANAGER | exit |
| RSI(7) 50-cross against position | M15 | EXIT_MANAGER | exit |
| Both-CCI opposite-extreme stop | M15 | EXIT_MANAGER | exit |

**Rules instantiated:**
- F-1 — H1 pair AND M15 pair required for every entry is an explicit DUAL-TF GATE.
- F-2 — mixed-sign CCIs on either timeframe = NEUTRAL = no entry.
- F-4 / SY-1 — CCI(30) and CCI(100) agreeing is a two-period unanimity family; the faster period is the trigger clock.
- SY-2 — one CCI positive and one negative = NO_SIGNAL, never "half bullish".
- U-2 — the CCI(100) zero-cross against is the mirrored exit of the both-above-zero entry state.
- U-4 / P-3 — immediate re-entry while the CCI state holds is the license loop.

**Gap audit:** the full six-check walkthrough is the CS-1 Application above. CHECK_1 PASS, CHECK_2 FAIL (no VOLATILITY_GATE), CHECK_3 PASS, CHECK_4 PASS, CHECK_5 PASS, CHECK_6 FAIL (no R-1/U-5 mapping). Repair: STRAT-006 as ENERGY GATE; SUPER grade issued only when VolatilityState == GREAT_MOVEMENT; R-1 sizing and U-5 cap bound at the portfolio layer.

**Generalized lesson:** Oscillator displacement past a magnitude threshold measures direction intensity, not market energy; a SUPER SignalGrade is issued by a VOLATILITY_GATE reading GREAT_MOVEMENT, never by a bigger oscillator number.

### Case Study: STRAT-003 — CCI Trinity Vanguard

**Mechanical summary:** M15 CCI(14), CCI(100), CCI(900), each smoothed by its own SMA(20); all three CCIs and their smoothing lines above −100 = long base, all above +100 (or H1 trinity alignment plus M15 > +100) = SUPER; exit when CCI(14) crosses 0 against AND its SMA(20) confirms; trail on CCI(100)+SMA zero-cross against; stop when all three flip past the opposite extreme; re-enter while the trinity persists.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| CCI(14) + SMA(20) (fastest member, trigger clock) | M15 | ENTRY_TRIGGER | LTF timing |
| CCI(14) + SMA(20) (fast exit copy) | M15 | EXIT_MANAGER | exit |
| CCI(100) + SMA(20) (mid member) | M15 | GRAVITY_FILTER | LTF timing |
| CCI(100) + SMA(20) (mid trail copy) | M15 | EXIT_MANAGER | exit |
| CCI(900) + SMA(20) (heaviest member, anchor) | M15 | GRAVITY_FILTER | LTF timing |
| CCI(14)/(100)/(900) + SMA(20) alignment (SUPER state) | H1 | GRAVITY_FILTER | HTF gravity |
| All-three opposite-extreme flip (stop) | M15 | EXIT_MANAGER | exit |

**Rules instantiated:**
- SY-1 — three periods of one family aligned with their own smoothing lines = compounding push; CCI(14) is the trigger/exit clock.
- SY-2 / F-4 — any member off-side (raw or smoothing line) = UNANIMOUS(false) = NO_SIGNAL; skipped bars never enter edge statistics.
- UNANIMITY TEST — each member carries its own independent smoothing line, matching the canonical definition exactly.
- E-2 (exit clause) — trailing on the MID-speed CCI(100)+SMA flip is E-2's mid-indicator trail.
- U-2 — the fast cross-plus-confirm exit mirrors the fast entry condition.
- U-4 / P-3 — re-entry while the trinity persists is the license loop.

**Gap audit:** CHECK_1 PASS (after copy splitting). CHECK_2 FAIL — no VolatilityState component. CHECK_3 FAIL — H1 alignment appears only in the SUPER branch; base entries execute on M15 alone, which F-1 forbids. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — no risk fraction stated. Repair: STRAT-006 as ENERGY GATE; extend the H1 trinity check to ALL grades (F-1); bind R-1.

**Generalized lesson:** In any unanimity family the fastest member is the trigger and exit clock and the slowest member is the anchor; role assignment by relative period transfers unchanged to any indicator family.

### Case Study: STRAT-004 — SMA Stack Prophet

**Mechanical summary:** M15 price above SMA(50) AND above SMA(4) AND above SMA(4) shifted forward 4 bars = bull stack (mirror for bear); the same stack on H1 upgrades to SUPER; exit when price crosses SMA(4); trail on SMA(50) flip; hard stop 1% beyond the SMA(4)-shift extreme; re-enter when the full stack reforms.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| Price vs SMA(50) | M15 | GRAVITY_FILTER | LTF timing |
| Price vs SMA(4) (entry copy) | M15 | ENTRY_TRIGGER | LTF timing |
| Price vs SMA(4) (cross-against exit copy) | M15 | EXIT_MANAGER | exit |
| Price vs SMA(4) shifted forward 4 (persistence baseline) | M15 | GRAVITY_FILTER | LTF timing |
| Full stack state | H1 | GRAVITY_FILTER | HTF gravity |
| SMA(50) flip (trail) | M15 | EXIT_MANAGER | exit |
| Hard stop 1% beyond SMA(4)-shift extreme | M15 | EXIT_MANAGER | exit |

**Rules instantiated:**
- G-1 — all three SMA constructs are masses tracking price.
- G-2 — SMA(50) is the heavier mass; SMA(4) is timing only when they disagree.
- P-1 — price vs the forward-shifted SMA(4) is the PERSISTENCE TEST construction: the shifted copy is the indicator's own displaced baseline.
- F-1 — dual-TF agreement exists but only as the SUPER qualifier (gap: base grade is single-TF).
- U-2 — price crossing SMA(4) is the exact mirror of the entry condition.
- U-4 / P-3 — stack reformation re-arms entry under the standing license.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — no VolatilityState component. CHECK_3 FAIL — dual-TF required only for SUPER; F-1 requires it for every grade. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — "1% beyond the extreme" is a price offset for stop placement, not an equity risk fraction; position size is undefined. Repair: STRAT-006 as ENERGY GATE; enforce F-1 on all grades; R-1 sizing (1% of equity ÷ stop distance) and U-5.

**Generalized lesson:** A stop's price location and the account risk fraction are two independent objects measured in different units; specifying one never specifies the other, and R-1 binds only the equity fraction.

### Case Study: STRAT-005 — SMA Reversion Rally

**Mechanical summary:** M15 SMA(30) > SMA(50) = up regime; entry when price crosses back above SMA(30) after a pullback OR when RSI(5) crosses above 50; the same SMA relation on H1 upgrades to SUPER; exit long when RSI(5) < 40 or price < SMA(50); re-enter on a new cross while the regime persists.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| SMA(30) vs SMA(50) | M15 | GRAVITY_FILTER | LTF timing |
| SMA(30) vs SMA(50) (SUPER state) | H1 | GRAVITY_FILTER | HTF gravity |
| Price recross above SMA(30) (round-trip event) | M15 | ENTRY_TRIGGER | LTF timing |
| RSI(5) cross above 50 (alternative event) | M15 | ENTRY_TRIGGER | LTF timing |
| RSI(5) < 40 | M15 | EXIT_MANAGER | exit |
| Price < SMA(50) (regime-line failure) | M15 | EXIT_MANAGER | exit |

**Rules instantiated:**
- E-1 — the pullback-and-recross above SMA(30) is the retrace-to-gravity-line entry with a round-trip exit at SMA(50).
- G-2 — SMA(50) is the heavier line; its breach closes the position regardless of RSI(5).
- F-1 — H1 agreement exists only in the SUPER branch (gap).
- U-1 — both entries are crossing EVENTS on a closed bar, not extended states.
- U-2 — price < SMA(50) is the mirrored regime-failure close.
- P-3 — "re-enter on a new cross while the regime persists" is the license loop.
- U-5 — two alternative triggers feed one license: one signal source, one position.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — no VolatilityState component. CHECK_3 FAIL — dual-TF only in the SUPER branch. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — no equity risk fraction; U-5 implied by the audit, not by the spec. Repair: STRAT-006 as ENERGY GATE; enforce F-1 on all grades; bind R-1 and U-5.

**Generalized lesson:** Alternative entry triggers under one license are one signal source; they share one risk budget and can never produce two concurrent positions (U-5), no matter how many trigger paths the specification lists.

### Case Study: STRAT-006 — Dual Momentum-Volatility Filter v2

**Mechanical summary:** Per timeframe, ADX(14) above its own SMA(1) shifted forward 5 AND ATR(14) above its own SMA(1) shifted forward 5 = energy pass; LTF fail = Nothing Happening; LTF pass with HTF both below = Do Not Trade; LTF pass with HTF partial = OK to Trade; LTF pass AND HTF pass = Great Movement; absolute floor ADX > 20 rejects weak above-baseline readings. Non-directional by construction.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| ADX(14) vs own SMA(1) shift +5 | M15 | VOLATILITY_GATE | energy |
| ATR(14) vs own SMA(1) shift +5 | M15 | VOLATILITY_GATE | energy |
| ADX(14) vs own SMA(1) shift +5 | H1 | VOLATILITY_GATE | energy |
| ATR(14) vs own SMA(1) shift +5 | H1 | VOLATILITY_GATE | energy |
| ADX(14) > 20 absolute floor (sub-condition of each ADX instance) | M15 and H1 | VOLATILITY_GATE | energy |

Canonical state mapping (every cell binary):

| LTF gate (both above + floor) | HTF gate | VolatilityState |
|---|---|---|
| fail | any | NOTHING_HAPPENING |
| pass | both below | NOTHING_HAPPENING |
| pass | one of two above | TRADABLE |
| pass | both above + floor | GREAT_MOVEMENT |

**Rules instantiated:**
- F-3 — VolatilityState is classified with zero directional input; NOTHING_HAPPENING blocks all entries in any host strategy.
- P-1 — the ENERGY GATE is the shifted-SMA PERSISTENCE TEST applied to volatility indicators: raw ADX/ATR above their own forward-shifted SMA(1) baselines on the closed bar.
- F-5 — ADX and ATR instances hold exactly one role each (VOLATILITY_GATE); no directional duty is assigned to them anywhere in the portfolio.
- F-1 (structural analog) — energy is computed independently on LTF and HTF, mirroring the dual-TF architecture on the energy axis.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — only the energy question is answered; no GravityState, no trigger, no exit. CHECK_3 FAIL — no GravityState exists to gate. CHECK_4 FAIL — no entries, therefore no mirrored exits. CHECK_5 FAIL — it supplies the ENERGY GATE half of every license but defines no re-entry loop of its own. CHECK_6 FAIL — no risk object. Verdict: NON_COMPLIANT standalone **by design** — STRAT-006 is the portfolio's canonical imported component, not a host. Repair: pair with any directional STRAT; compliance is then evaluated on the host+gate bundle.

**Generalized lesson:** A component that answers exactly one role question with binary precision is portfolio infrastructure — more valuable than a strategy that answers all four loosely — and the PERSISTENCE TEST applies to volatility indicators identically as to directional ones.

### Case Study: STRAT-007 — SMA Fan Accord

**Mechanical summary:** Five M15 SMA(4) instances at forward shifts 0, 1, 2, 3, 4 running straightened/parallel AND all above SMA(50) = bull accord (all below = bear); the same accord on H1 upgrades to SUPER; exit when any SMA(4) crosses SMA(50) or the fan crosses itself; trail on SMA(50) flip; re-enter when the fan straightens again.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| SMA(4) shift 0 (fan member) | M15 | GRAVITY_FILTER | LTF timing |
| SMA(4) shift +1 (fan member) | M15 | GRAVITY_FILTER | LTF timing |
| SMA(4) shift +2 (fan member) | M15 | GRAVITY_FILTER | LTF timing |
| SMA(4) shift +3 (fan member) | M15 | GRAVITY_FILTER | LTF timing |
| SMA(4) shift +4 (fan member) | M15 | GRAVITY_FILTER | LTF timing |
| Fan-completion crossing (derived event: bar on which the last member aligns) | M15 | ENTRY_TRIGGER | LTF timing |
| Fan vs SMA(50) | M15 | GRAVITY_FILTER | LTF timing |
| Fan accord state (SUPER) | H1 | GRAVITY_FILTER | HTF gravity |
| Any SMA(4) × SMA(50) cross, or fan self-cross | M15 | EXIT_MANAGER | exit |
| SMA(50) flip (trail) | M15 | EXIT_MANAGER | exit |

**Rules instantiated:**
- SY-1 — five shifted copies of one average form a unanimity family; full parallel alignment = compounding push.
- SY-2 / F-4 — a fanned-out (self-crossed) fan is disagreement = flat; skipped bars never enter edge statistics.
- P-1 — each forward-shifted copy is a displaced baseline; the accord is a stack of persistence comparisons.
- G-2 — SMA(50) is the heavy anchor; any member crossing it overrides the fan.
- U-1 — entry is valid only on the fresh completion EVENT, never on the extended straight-fan state.
- U-2 — the fan self-cross is the mirrored exit of the fan-alignment entry.
- U-4 / P-3 — re-straightening re-arms entry under the standing license.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — no VolatilityState component. CHECK_3 FAIL — H1 accord required only for SUPER. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — no risk object. Repair: STRAT-006 as ENERGY GATE; enforce F-1 on all grades; bind R-1.

**Generalized lesson:** Time-shifted copies of one indicator form a unanimity family exactly as different periods do; agreement geometry (parallel vs crossed) is a binary state whose fresh transition — not its continuation — is the entry event.

### Case Study: STRAT-008 — CCI BB Outbreak Hunter

**Mechanical summary:** M15 CCI(30), CCI(100), CCI(300), each with BB(14,1,0) computed on the CCI line itself; all three CCIs above their own BB upper band = bull outbreak (mirror below the lower band); all inside their bands = consolidation chop masking every entry; H1 same condition = SUPER; exit when any CCI crosses its own BB middle against; stop when all CCIs flip to the opposite band; re-enter while the outbreak holds.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| CCI(30) vs own BB(14,1,0) upper (fastest member, completion clock) | M15 | ENTRY_TRIGGER | LTF timing |
| CCI(100) vs own BB(14,1,0) upper (mid member) | M15 | GRAVITY_FILTER | LTF timing |
| CCI(300) vs own BB(14,1,0) upper (heaviest member) | M15 | GRAVITY_FILTER | LTF timing |
| All-inside-bands compression state (chop mask) | M15 | VOLATILITY_GATE | energy |
| Any CCI vs own BB middle (exit copies, one per member) | M15 | EXIT_MANAGER | exit |
| All CCIs at opposite band (stop) | M15 | EXIT_MANAGER | exit |
| Triple outbreak state (SUPER) | H1 | GRAVITY_FILTER | HTF gravity |

**Rules instantiated:**
- E-2 — the band pierce is E-2's volatility-band-pierce entry applied to an oscillator instead of price: same abstract pierce/mask/recross structure, different carrier.
- SY-1 / F-4 — three periods of one family must all pierce simultaneously; the fastest member's pierce completes the trigger event.
- SY-2 — two-of-three above the band = NO_SIGNAL, never a reduced position.
- F-3 — the all-inside-bands compression state is a NOTHING_HAPPENING classifier masking all entries.
- U-2 — the own-BB-middle recross is the mirrored exit of the own-BB-upper pierce.
- U-4 / P-3 — re-entry while the outbreak state holds is the license loop.

**Gap audit:** CHECK_1 PASS. CHECK_2 PASS — the compression mask answers the energy question in weak form (it distinguishes NOTHING_HAPPENING from not-nothing but cannot grade GREAT_MOVEMENT, so the SUPER grade still requires STRAT-006). CHECK_3 FAIL — H1 required only for SUPER. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 FAIL — no risk object. Repair: STRAT-006 for GREAT_MOVEMENT grading; enforce F-1 on all grades; bind R-1.

**Generalized lesson:** E-2's pierce/mask/recross algebra is carrier-agnostic — bands computed on an oscillator obey the same binary entry, mask, and exit structure as bands computed on price.

### Case Study: STRAT-0009 — Opening Bell Breakout

**Mechanical summary:** Pre-open, mark the highest high and lowest low of the last 5 closed H1 bars; within 5 minutes after the scheduled cash open (MT5 GMT+2 winter: Nikkei 02:00, ASX 04:00, HSI 03:30, DAX 08:00, FTSE 09:00, US500/NAS100 15:30), a confirmed M5 close above the high = bullish, below the low = bearish; M5 SMA(200) filters direction (above = buys only, below = sells only).

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| Highest high of last 5 closed H1 bars (breakout line) | H1 → M5 | ENTRY_TRIGGER | LTF timing |
| Lowest low of last 5 closed H1 bars (breakdown line) | H1 → M5 | ENTRY_TRIGGER | LTF timing |
| Session-open clock (5-minute post-open window) | M5 | VOLATILITY_GATE | energy |
| Price vs SMA(200) | M5 | GRAVITY_FILTER | LTF timing |

**Rules instantiated:**
- U-1 — the 5-minute post-open window is the trigger window; the entry event is the first confirmed M5 close beyond the line inside it, never a later extended state.
- F-3 (substituted) — the scheduled open is a calendar-known energy injection: a KNOWN-in-advance VolatilityState spike substituting for the measured ENERGY GATE.
- G-1 — SMA(200) is a mass; its side sets the only directional filter.
- TRIGGER EVENT vs STATE — the range lines are static levels; only the crossing bar is the event.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — no EXIT_MANAGER exists anywhere in the spec. CHECK_3 FAIL — direction is checked on M5 only; no independent HTF GravityState. CHECK_4 FAIL — no mirrored exit for the breakout entry. CHECK_5 FAIL — no license or re-entry rule. CHECK_6 FAIL — no risk object. Repair: import U-2 (mirrored exit = confirmed M5 close back inside the range; hard stop at the opposite range line), import an H1 GravityState (H1 price vs SMA(200), or STRAT-001's H1 regime block) to satisfy F-1, define the license per P-3 as the inside-window state (window close = license expiry, zero re-entries after it), and bind R-1 sizing.

**Generalized lesson:** A scheduled session open is an exogenous, calendar-known energy injection — it replaces the measured ENERGY GATE and nothing else; every directional gate (DUAL-TF, trigger window, mirrored exit) applies unchanged.

### Case Study: STRAT-0010 — Red News + COT Bias

**Mechanical summary:** Weekly CFTC COT positioning extremes (fade speculator extremes at >80/20 index readings) set the directional bias; daily red-folder events filtered to COT-relevant assets; 5–15 minutes post-release, if actual-vs-forecast agrees with the COT bias, enter on a pullback to SMA(200); never contra-COT, never inside the first spike; SL at the event low/high, RR 1:2, risk 1%.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| COT positioning index (>80/20 speculator extreme, faded) | Weekly | GRAVITY_FILTER | HTF gravity |
| Red-folder calendar event (COT-relevant assets only) | Event/daily | VOLATILITY_GATE | energy |
| Actual-vs-forecast agreement with COT bias | Event | ENTRY_TRIGGER (qualifier) | LTF timing |
| Pullback to SMA(200), 5–15 min post-release | M5 | ENTRY_TRIGGER | LTF timing |
| SL at event low/high; TP at 1:2 RR | M5 | EXIT_MANAGER | exit |

**Rules instantiated:**
- G-2 — weekly COT positioning is the heaviest, slowest mass in the portfolio; it dominates every lighter directional read, exactly like an HTF GRAVITY_FILTER.
- F-1 — the weekly bias and the M5 pullback direction are two independently computed directional layers that must agree.
- F-3 (substituted) — the red-folder release is a scheduled GREAT_MOVEMENT substitute: a known-in-advance VolatilityState spike.
- U-1 — the 5–15 minute post-release window is the trigger window; the first-spike exclusion forbids entry on an unconfirmed intra-window state.
- E-1 — the entry is a pullback to the SMA(200) gravity line in the bias direction.
- R-1 — 1% risk with a defined SL and RR floor is an explicit risk mapping.

**Gap audit:** CHECK_1 PASS. CHECK_2 PASS. CHECK_3 PASS. CHECK_4 PASS — the SL at the event extreme is the mirrored falsification of the release-direction premise; TP is mechanical. CHECK_5 FAIL — no re-entry rule after a stop-out inside the window; the license is undefined. Repair per P-3: license = COT bias unchanged AND clock inside the post-release window; one re-entry per fresh pullback event while the license holds (U-4), zero after window expiry. CHECK_6 FAIL — R-1 is met, but U-5 is absent: multiple COT-relevant assets keyed to the same weekly extreme are one signal source and must be capped to one position. Repair: bind U-5.

**Generalized lesson:** Exogenous inputs map onto the same four roles as indicators — weekly positioning is a very heavy slow mass (HTF GRAVITY_FILTER), a red-folder release is a known-in-advance VolatilityState spike (VOLATILITY_GATE); the framework's gates are carrier-agnostic across indicator-based, time-based, and event-based inputs.

### Case Study: STRAT-011 — Shifted CCI Momentum Aligner

**Mechanical summary:** H1 CCI(140) > 0 AND above its own SMA(1) shifted forward 4 bars = persistent bull gravity (mirror for bear); M5 CCI(14) zero-cross in the same direction = entry; exit when M5 CCI(14) recrosses 0 against; trail on the H1 CCI(140)/shifted-baseline flip; SL = 1 ATR from entry; risk 1%; RR ≥ 1:2.

| Indicator instance | Timeframe | Assigned role | Framework layer |
|---|---|---|---|
| CCI(140) vs 0 | H1 | GRAVITY_FILTER | HTF gravity |
| CCI(140) vs own SMA(1) shift +4 (PERSISTENCE TEST) | H1 | GRAVITY_FILTER | HTF gravity |
| CCI(140)/shifted-baseline flip (trail copy) | H1 | EXIT_MANAGER | exit |
| CCI(14) zero-cross with the license (entry) | M5 | ENTRY_TRIGGER | LTF timing |
| CCI(14) recross 0 against (exit copy) | M5 | EXIT_MANAGER | exit |
| ATR(14) stop distance (SL = 1 ATR from entry) | M5 | EXIT_MANAGER | exit |

**Rules instantiated:**
- P-1 (purest implementation in the portfolio) — H1 CCI(140) vs its own SMA(1) shifted forward 4 is the PERSISTENCE TEST verbatim: the raw value holding the correct side of its own forward-shifted baseline across consecutive closed H1 bars defines UNINTERRUPTED momentum; one cross back on a single closed H1 bar = interruption = license revoked.
- P-3 — the license is re-evaluated on every closed H1 bar; failure stops NEW entries only, the open position runs on its own exits.
- U-4 — an M5 exit while the H1 license holds mandates re-entry on the next fresh M5 zero-cross.
- F-1 — H1 GravityState and M5 direction computed independently and required equal and directional.
- U-2 — the M5 recross is the exact mirror of the M5 entry cross.
- R-1 — 1% equity risk, 1 ATR stop, RR ≥ 1:2 is a complete risk mapping.
- P-2 — no duration condition exists anywhere; entry/exit rule satisfaction is the only test.
- F-5 — the ATR instance is EXIT_MANAGER only; the same indicator serves as a VOLATILITY_GATE elsewhere (STRAT-006), but each instance holds exactly one role.

**Gap audit:** CHECK_1 PASS. CHECK_2 FAIL — ATR sizes the stop but no component classifies VolatilityState. CHECK_3 PASS. CHECK_4 PASS. CHECK_5 PASS. CHECK_6 PASS. Repair: import STRAT-006 as ENERGY GATE; the bundle is then fully COMPLIANT.

**Generalized lesson:** Uninterrupted momentum has a mechanical definition — the raw indicator holding one side of its own forward-shifted baseline across consecutive closed bars, with a single recross revoking the license — and that definition transfers to any indicator, instrument, and timeframe.

#### The Reinforcement Learning reward layer

The portfolio's RL layer (23 shaped rewards and penalties across Momentum, Profit/Risk, Operational, and Consistency clusters) is the incentive encoding of the same binary gates audited above — nothing more. Audit rule for the layer: map every reward or penalty to the specific gate it reinforces (a momentum-alignment reward encodes F-1/P-1; a drawdown penalty encodes R-1; an overtrading penalty encodes U-1/P-3). Any reward that pays for an action a gate forbids — paying for entries while VolatilityState == NOTHING_HAPPENING, paying for holding through a mirrored-exit condition, paying for size added against dominant gravity — is a specification bug and is removed or inverted before training. Rewards price compliance; they never create permissions.

#### Portfolio compliance matrix

Standalone verdicts against CS-1's six checks. Every cell is binary; the Repair column names the imported component or rule that flips each FAIL.

| STRAT | Role integrity (F-5) | Four roles covered | DUAL-TF GATE (F-1) | Mirrored exit (U-2) | Re-entry license (P-1/P-3) | Risk mapping (R-1/U-5) | Repair |
|---|---|---|---|---|---|---|---|
| STRAT-001 | PASS | FAIL | PASS | PASS | PASS | FAIL | STRAT-006 (ENERGY GATE); R-1 sizing + U-5 |
| STRAT-002 | PASS | FAIL | PASS | PASS | PASS | FAIL | STRAT-006 (ENERGY GATE); R-1 + U-5 |
| STRAT-003 | PASS | FAIL | FAIL | PASS | PASS | FAIL | STRAT-006; F-1 on all grades; R-1 |
| STRAT-004 | PASS | FAIL | FAIL | PASS | PASS | FAIL | STRAT-006; F-1 on all grades; R-1 |
| STRAT-005 | PASS | FAIL | FAIL | PASS | PASS | FAIL | STRAT-006; F-1 on all grades; R-1 + U-5 |
| STRAT-006 | PASS | FAIL | FAIL | FAIL | FAIL | FAIL | Pair as component with any directional host STRAT; host supplies gravity/trigger/exit; R-1 |
| STRAT-007 | PASS | FAIL | FAIL | PASS | PASS | FAIL | STRAT-006; F-1 on all grades; R-1 |
| STRAT-008 | PASS | PASS | FAIL | PASS | PASS | FAIL | STRAT-006 (GREAT_MOVEMENT grading for SUPER); F-1 on all grades; R-1 |
| STRAT-0009 | PASS | FAIL | FAIL | FAIL | FAIL | FAIL | U-2 mirrored exit; H1 GravityState import (STRAT-001 regime block); P-3 window license; R-1 |
| STRAT-0010 | PASS | PASS | PASS | PASS | FAIL | FAIL | P-3 in-window re-entry license; U-5 one-position cap across COT-correlated assets |
| STRAT-011 | PASS | FAIL | PASS | PASS | PASS | PASS | STRAT-006 (ENERGY GATE) |

Reading of the matrix: zero of the eleven strategies is COMPLIANT standalone; that is the expected result, not a defect. The portfolio becomes tradable only as assembled bundles — directional host + STRAT-006 ENERGY GATE + R-1/U-5 risk mapping — re-audited through CS-1 after every assembly change.
