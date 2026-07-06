## 2. The Five Biggest Issues in FINDING Momentum

This section defines the five classification failures that cause an agent to emit a directional state or a tradable signal where the correct output is NEUTRAL or NO_SIGNAL. Each failure is stated as a binary rule over closed-bar OHLCV and indicator data. The common defect in all five is the same: treating a single measurement, a single scale, a single event, or a single indicator instance as if it were the full classification pipeline. The rules below are vetoes. A veto that fires overrides every downstream check, regardless of how the downstream checks evaluate.

### F-1 — False Regime Reads on a Single Timeframe

**Issue:** Does a directional gravity reading computed on exactly one timeframe authorize the agent to declare GravityState = BULL or GravityState = BEAR?

**Rule:** No. A single-timeframe reading is a timeframe-local state, not a regime. The only path to a directional GravityState is the DUAL-TF GATE: HTF GravityState and LTF GravityState computed independently on their own CLOSED bars, and the gate passes only if both states are equal AND directional. Every other combination outputs NEUTRAL and blocks all momentum entries.

```text
HTF_state = gravity_state(HTF)        # computed on closed HTF bars only
LTF_state = gravity_state(LTF)        # computed on closed LTF bars only, independent calculation

DUAL_TF_GATE_PASS = (HTF_state == LTF_state) AND (HTF_state IN {BULL, BEAR})

IF DUAL_TF_GATE_PASS:
    GravityState = HTF_state
ELSE:
    GravityState = NEUTRAL            # no directional bias declared
    momentum_entries = BLOCKED
```

The rule is violated whenever a directional GravityState is emitted while DUAL_TF_GATE_PASS == false.

**Application:** Per-timeframe gravity condition: close of the last CLOSED bar above SMA(4) shifted forward 8 bars = BULL on that timeframe; below = BEAR. Evaluate M15 and H1 on US30:

1. M15 leg: last closed M15 bar closes at 39,412; the SMA(4) shift-8 baseline reads 39,388 at that bar. 39,412 > 39,388 → true → M15 state = BULL.
2. H1 leg: last closed H1 bar closes at 39,412; the H1 SMA(4) shift-8 baseline reads 39,466. 39,412 > 39,466 → false → H1 state = BEAR.
3. Equality check: BULL == BEAR → false.
4. Directionality check: not reached (equality already failed).
5. Output: DUAL_TF_GATE_PASS = false → GravityState = NEUTRAL. A fresh M5 CCI(14) upward zero-cross trigger event occurring at this moment is void, because entries key off trigger events only inside a directional state.

The same discipline applies to the HTF regime read itself: H1 price above SMA(200) and above the BB(200) middle band is one leg of evidence, and one leg declares nothing on its own.

**Conclusion (Generalized Principle):** A regime is a property of agreement between at least two independently computed directional states at separated scales; it is never a property of one measurement. Any gravity computation — MA baseline, band midline, oscillator equilibrium — evaluated on one timeframe yields only a timeframe-local state with zero authority over GravityState. The directional output exists exclusively at the conjunction of identical directional states on HTF and LTF; any inequality between the legs, or NEUTRAL on either leg, forces GravityState = NEUTRAL and blocks momentum entries.
Transfer test: given a new indicator, the agent computes its gravity condition separately on the HTF and the LTF, feeds both states through the equality-AND-directional check, and confirms the pipeline outputs NEUTRAL in every case where the two legs differ.

### F-2 — Chop Misclassified as Trend

**Issue:** Does a sequence of clean crossover events, occurring while price oscillates around the gravity reference, qualify the market as trending (directional GravityState eligible)?

**Rule:** No. Trend classification on a timeframe requires a stacking census over the last N CLOSED bars against the gravity reference line: at least K of the last N closed bars must all close on ONE side of the reference. If neither side reaches K, the timeframe's gravity state is NEUTRAL, action = WAIT, and NEUTRAL voids every ENTRY_TRIGGER event on all lower timeframes regardless of how clean each individual crossing is.

```text
# stacking test — closed bars only
N = census_window            # example: 12
K = stacking_threshold       # K <= N; example: 10

above = COUNT(i in last N closed bars WHERE close[i] > gravity_ref[i])
below = COUNT(i in last N closed bars WHERE close[i] < gravity_ref[i])

IF above >= K:     stacking = BULL
ELIF below >= K:   stacking = BEAR
ELSE:              stacking = FAIL

IF stacking == FAIL:
    GravityState = NEUTRAL
    action       = WAIT
    ENTRY_TRIGGER_events = VOID     # crossover cleanliness is irrelevant
```

**Application:** Timeframe M15; gravity_ref = BB(200) middle band; N = 12; K = 10. Chop signature present: price is bouncing between the BB(20) upper band and BB(20) lower band with no consistent side of the BB(200) middle. Census over the last 12 closed M15 bars: 7 closes above the BB(200) middle, 5 closes below.

1. above >= K: 7 >= 10 → false.
2. below >= K: 5 >= 10 → false.
3. stacking = FAIL → GravityState = NEUTRAL, action = WAIT.

During this same window, M5 CCI(14) printed two textbook upward zero-line crossings. Both are trigger EVENTS; both are void, because a trigger event only fires an entry inside a directional STATE, and the state check failed first. Counter-case for calibration: 11 of the last 12 closed bars above the middle band → 11 >= 10 → stacking = BULL on M15; that leg then still passes through the F-1 DUAL-TF GATE before any directional GravityState is declared.

**Conclusion (Generalized Principle):** Trend is a persistence property measured by census over a fixed window of closed bars, never an event property measured by crossings. For any gravity reference on any timeframe, the binary test is K-of-N closes on one side; a window in which neither side reaches K is NEUTRAL, and NEUTRAL is an unconditional veto on momentum entries. Chop mechanically produces MORE crossover events while producing LOWER stacking counts, so event frequency is anti-correlated with trend validity and is never admissible as evidence of trend.
Transfer test: for a new gravity reference, the agent replays a known ranging window and confirms the classifier outputs NEUTRAL/WAIT on every bar where neither side's census count reaches K, with zero entries emitted in that window.

### F-3 — Low-Volatility States Mistaken for Early Momentum

**Issue:** Does a directional crossing (zero-line cross or MA cross) that completes while the ENERGY GATE fails qualify as early momentum eligible for entry?

**Rule:** No. VolatilityState is classified on an axis independent of direction. The ENERGY GATE requires every VOLATILITY_GATE instance's raw value to be above its own forward-shifted SMA baseline on the current CLOSED bar; all instances must pass. If the gate fails, VolatilityState = NOTHING_HAPPENING, and NOTHING_HAPPENING blocks all entries even when GravityState is directional and a fresh trigger event exists.

```text
# ENERGY GATE — per timeframe, closed bars only
FOR each V in VOLATILITY_GATE_instances:        # example set: {ADX(14), ATR(14)}
    baseline_V = SMA(V, 1) shifted forward S bars   # example: S = 5
    pass_V = (V[t] > baseline_V[t])

ENERGY_GATE_PASS = AND(all pass_V)

IF NOT ENERGY_GATE_PASS:        VolatilityState = NOTHING_HAPPENING
ELIF expansion_check_pass:      VolatilityState = GREAT_MOVEMENT   # example extra threshold: ADX(14) > 25
ELSE:                           VolatilityState = TRADABLE

IF VolatilityState == NOTHING_HAPPENING:
    entries = BLOCKED           # regardless of GravityState and trigger events
```

**Application:** Long side on M5. The DUAL-TF GATE passes: price above SMA(4) shift 8 on both M1 and M15, both BULL. A fresh trigger event exists: M5 CCI(14) crossed 0 upward on the just-closed bar. Energy check on M5:

1. ADX(14) at the closed bar = 16.8; its SMA(1) shifted forward 5 bars reads 19.3 at the same bar. 16.8 > 19.3 → false.
2. ATR(14) = 11.2 points; its shifted baseline reads 12.6. 11.2 > 12.6 → false.
3. ENERGY_GATE_PASS = false → VolatilityState = NOTHING_HAPPENING.
4. Entry decision: BLOCKED. Direction passed, trigger fired, energy failed — no trade.

The forward shift compares the current value against the recent past projected forward, so a fading ADX fails this test roughly 5 bars before a same-bar comparison would flag it — a built-in early warning that the crossing has no force behind it. The crossing was a trap, not a slingshot.

**Conclusion (Generalized Principle):** Direction and energy are orthogonal classification axes, and a tradable state exists only at their intersection. A crossing event carries zero information about the force available to extend the move; force is measured exclusively by energy indicators compared against their own forward-shifted baselines, combined as a strict conjunction. When the energy axis reads NOTHING_HAPPENING, the directional axis is not read at all — the agent does not reduce size, widen stops, or wait-and-enter; it emits no entry.
Transfer test: given a new volatility measure, the agent constructs its forward-shifted SMA baseline, replays a historical flat window containing directional crossings, and confirms the gate returned false and zero entries were emitted across that window.

### F-4 — Multi-Scale Oscillator Divergence Creating False Herd Signals

**Issue:** When fast, mid, and slow instances of the same oscillator family disagree on side, does majority agreement (for example 2-of-3 bullish) produce any signal grade above NO_SIGNAL?

**Rule:** No. The UNANIMITY TEST is the law: N periods of the SAME indicator family (fast/mid/slow), each with its own independent smoothing line, must all be on the same side of their equilibrium AND on the same side of their own smoothing line on the current CLOSED bar. ANY disagreement = UNANIMOUS(false) = SignalGrade NO_SIGNAL. There is no intermediate grade; partial agreement is a binary fail, never a "weak signal".

```text
# UNANIMITY TEST — family OSC, periods {fast, mid, slow}, closed bar t
FOR P in {fast, mid, slow}:
    eq_side_P     = SIGN(OSC_P[t] - equilibrium)           # +1 or -1; 0 counts as fail
    smooth_side_P = SIGN(OSC_P[t] - SMA(OSC_P, L_P)[t])    # own independent smoothing line

UNANIMOUS = (eq_side_fast == eq_side_mid == eq_side_slow)
        AND (smooth_side_fast == smooth_side_mid == smooth_side_slow)
        AND (eq_side_fast == smooth_side_fast)
        AND (eq_side_fast != 0)

IF NOT UNANIMOUS:
    SignalGrade = NO_SIGNAL     # majority, weighting, and "mostly bullish" outputs are forbidden
```

**Application:** Family CCI on M5, periods 14 / 100 / 900, each smoothed by its own SMA(20). Closed-bar readings:

1. CCI(14) = +143: above equilibrium 0 → +1; above its SMA(20) = +96 → +1. Fast leg bull.
2. CCI(100) = +41: above 0 → +1; above its SMA(20) = +18 → +1. Mid leg bull.
3. CCI(900) = −58: below 0 → −1. Equilibrium sides are {+1, +1, −1} → equality fails.
4. UNANIMOUS = false → SignalGrade = NO_SIGNAL.

The 2-of-3 reading is not "mostly bullish"; it is the divergence signature of a counter-trend bounce inside a larger decline — the fast and mid scales rallying against slow-scale gravity. The herd/SUPER pathway (all three above +100 with the fastest also breaking its extreme) is reachable only FROM UNANIMOUS(true); grading is evaluated strictly after unanimity, never instead of it.

**Conclusion (Generalized Principle):** Multi-scale confirmation is a boolean conjunction over independent instances of one measurement family at separated scales, and its output space is exactly {UNANIMOUS(true), NO_SIGNAL} with no interpolation, because cross-scale disagreement is itself a defined market state (divergence) rather than a weaker version of agreement. Any voting, weighting, averaging, or majority scheme over the instances is a contract violation regardless of how the weights are chosen.
Transfer test: the agent instantiates the new oscillator at three separated periods with independent smoothing lines, constructs a bar state where exactly one instance sits on the opposite side, and confirms the signal function returns NO_SIGNAL.

### F-5 — Indicator Role Confusion

**Issue:** Is a strategy configuration valid when one indicator instance (same family, same period, same timeframe) is referenced by two or more of the four roles?

**Rule:** No. Every indicator instance is assigned EXACTLY one role from {GRAVITY_FILTER, VOLATILITY_GATE, ENTRY_TRIGGER, EXIT_MANAGER}. An instance referenced by zero roles is removed. An instance referenced by two or more roles makes the configuration INVALID and halts trading until roles are reassigned to distinct instances. Dual roles create circular logic: an ENTRY_TRIGGER event on an instance logically implies the GRAVITY_FILTER state of that same instance on the trigger bar, so the confirmation count is inflated by construction.

```text
# role audit — run over the full strategy graph before any live evaluation
FOR each instance I = (family, period, timeframe, smoothing):
    roles(I) = { r : role r references I anywhere in strategy logic }

    IF |roles(I)| == 0:  REMOVE I                          # dead weight
    IF |roles(I)| >= 2:  CONFIG = INVALID; HALT_TRADING    # circular logic
    IF |roles(I)| == 1:  I = VALID

# explicit circularity clause
FOR each pair (G, T) WHERE G.role == GRAVITY_FILTER AND T.role == ENTRY_TRIGGER:
    REQUIRE instance(G) != instance(T)
```

**Application:** The audit enumerates instances and finds RSI(7) on M5 referenced by two roles: GRAVITY_FILTER (state condition: RSI(7) > 50 = bull bias) and ENTRY_TRIGGER (event: RSI(7) crossing above 50).

1. |roles(RSI(7), M5)| = 2 → CONFIG = INVALID → HALT_TRADING.
2. Circularity demonstration: on the crossing bar, the trigger event guarantees RSI(7) > 50 is true, so the "independent bias confirmation" is true by construction. The strategy counted two checks; it possessed one measurement.
3. Reassignment: GRAVITY_FILTER = H1 close above SMA(200) AND above the BB(200) middle band (a distinct instance set on a distinct timeframe). ENTRY_TRIGGER = M5 CCI(14) crossing 0 in the regime direction. RSI(7) on M5 retains exactly one role: EXIT_MANAGER, closing the long when RSI(7) on the closed bar <= 40.
4. Audit re-run: every retained instance has |roles| = 1 → CONFIG = VALID → trading resumes.

**Conclusion (Generalized Principle):** A strategy is a mapping from indicator instances to functions, and validity requires that mapping to be single-valued: exactly one role per retained instance, zero shared instances across roles. One measurement referenced by two roles is one piece of evidence counted twice, which fabricates confluence that does not exist in the data; independence of checks is achieved structurally, by assigning distinct instances (distinct family, period, or timeframe) to distinct roles — never by re-reading the same instance.
Transfer test: before wiring any new indicator, the agent writes its (family, period, timeframe) tuple into the role map, re-runs the audit, and confirms the audit returns VALID with exactly one role attached to that tuple and no HALT_TRADING condition raised.
