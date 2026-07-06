## 1. The Gravity Principle Explained

### 1.1 Mass and Orbit

Every trend indicator is a mass. The period length of the indicator is its mass. A heavier mass (longer period, or same period on a higher timeframe) moves more slowly, changes direction less frequently, and exerts a stronger pull on price. Price and every lighter indicator orbit every heavier indicator: they deviate from it, and — absent an external energy input — they return to it. A lighter mass never overpowers a heavier one; it only reports position and timing inside the heavier mass's field.

Mass is computed, not judged. For two indicator instances A and B of the same family: A is heavier than B if A.timeframe is higher than B.timeframe, or if the timeframes are equal and A.period > B.period. This produces a strict total ordering — the mass hierarchy — for every indicator set the agent runs.

| Family / context | Heaviest (dominant gravity) | Middle | Lightest (fast orbit) | Ordering |
|---|---|---|---|---|
| SMA, single timeframe (H1) | SMA(200) | SMA(20) | SMA(4) | SMA(200) > SMA(20) > SMA(4) |
| CCI, single timeframe (H1) | CCI(900) | CCI(140) | CCI(14) | CCI(900) > CCI(140) > CCI(14) |
| Same indicator, cross-timeframe | H1 SMA(200) | M15 SMA(200) | M1 SMA(200) | H1 > M15 > M1 at equal period |
| Bollinger middle bands (H1) | BB(200) middle | BB(20) middle | — | BB(200) mid > BB(20) mid |
| Mixed timeframe and period | H4 SMA(50) | H1 SMA(200) | M5 SMA(200) | timeframe outranks period |

Period-to-mass principle: for ANY indicator family on ANY instrument, mass = (timeframe rank, period length) compared lexicographically — timeframe first, then period. The heavier instance defines the field; the lighter instance defines position within the field. This ordering is fixed at configuration time and is never re-evaluated based on recent performance, volatility, or any market condition.

### 1.2 Oscillators as Equilibrium-Deviation Meters

An oscillator does not track price level. It measures displacement from a fixed equilibrium constant built into its formula:

- RSI: equilibrium = 50 (range 0–100)
- CCI: equilibrium = 0 (unbounded but centered)
- Stochastic: equilibrium = 50 (range 0–100)

A reading away from equilibrium is a measurement of deviation, not a directive. The same reading has two opposite mechanical classifications depending on the surrounding field:

1. Deviation WITHOUT gravity and energy support: price has stretched away from its orbit with no force behind it. Classification: SNAP-BACK-RISK. Expected resolution: mean reversion toward the heavier mass. Trading the deviation direction is refused.
2. Deviation WITH aligned gravity (GravityState directional, same side as the deviation) AND energy (ENERGY GATE pass): the deviation is being driven by the dominant field. Classification: EXTENSION-ELIGIBLE (slingshot). The deviation extends instead of snapping back.

Generalization to any oscillator: identify the fixed equilibrium constant E from the indicator's definition. Value > E = bullish deviation; value < E = bearish deviation; the magnitude of deviation is meaningless on its own. Deviation direction becomes tradable if and only if GravityState is directional on the same side AND the ENERGY GATE passes on the same timeframe. Otherwise the deviation is classified SNAP-BACK-RISK and produces NO_SIGNAL in the deviation direction.

### 1.3 Slingshot Mechanics

A fast orbit accelerating in the same direction as slow gravity compounds momentum: the light body is being pulled and pushed in the same direction, so each unit of deviation costs less energy and travels farther. A fast orbit moving against slow gravity decays: every unit of travel fights the dominant pull, and the move terminates at the first energy fade. This is why counter-gravity entries are forbidden regardless of how extreme the fast indicator reads.

The forward-shifted moving average is the mechanical slope/acceleration detector that makes this checkable. SMA(4) shifted forward 8 bars places the average value computed 8 bars ago directly under the current bar. Two simultaneous comparisons follow on the current CLOSED bar:

- Price above the live SMA(4): price is above its current local baseline.
- Price above the SMA(4) shifted forward 8: price is also above where that baseline sat 8 bars ago, meaning the baseline itself has risen across the shift window — positive slope.

Both true on the same closed bar = momentum conserved, not dissipating: the orbit is above the baseline AND the baseline is climbing. This is the PERSISTENCE TEST applied to a trend mass. The identical construction applies to oscillators and energy meters: H1 CCI(140) above its own SMA(1) shifted forward 4 bars confirms the oscillator's deviation is still accelerating; ADX(14) above its SMA(1) shifted 5 confirms energy is still building, and gives roughly a 5-bar early warning when energy fades, because the raw value crosses below its own past baseline before the trend visibly stalls. Raw value on the correct side of its own forward-shifted baseline on the current CLOSED bar = PERSISTENT(true); otherwise PERSISTENT(false). There is no intermediate reading.

The SMA fan extends the same test: five SMA(4) instances at shifts 0, 1, 2, 3, 4 form a bullish fan on the current CLOSED bar if and only if (a) for every k in {0, 1, 2, 3} the shift-k instance is strictly above the shift-(k+1) instance, AND (b) all five instances are strictly above SMA(50). Both conditions true = fan state true: a conserved directional force — a state, not a single crossing event — read as continuous authorization, not as an entry instant. Any single comparison false = fan state false; there is no partial fan.

### 1.4 Multi-Timeframe Hierarchy

| Layer | Role | Concrete example | Generalized rule |
|---|---|---|---|
| HTF trend/oscillator | Regime filter (dominant gravity) | H1 price above SMA(200) AND above BB(200) middle band; H1 CCI(140) above 0 AND above its SMA(1) shifted forward 4 bars → HTF GravityState = BULL | The heaviest mass and heaviest oscillator jointly set GravityState. No entry is ever taken against it. This layer produces states, never entry events. |
| LTF trend/oscillator | Entry trigger (fast orbit) | M5 CCI(14) crossing 0 upward while HTF GravityState = BULL; the crossing bar is the trigger event | The lightest indicator supplies the entry INSTANT. It fires only in the HTF gravity direction; a crossing against gravity is discarded as NO_SIGNAL. |
| Volatility filter | Energy gate | ADX(14) above its SMA(1) shifted 5 AND ATR(14) above its SMA(1) shifted 5, checked per timeframe | Every configured volatility indicator above its own forward-shifted baseline, all simultaneously, or VolatilityState is downgraded and entries are refused. |
| Full alignment | SUPER signal | DUAL-TF GATE pass (HTF = M15, LTF = M5: M15 GravityState = BULL and M5 GravityState = BULL, each read as price above SMA(4) shifted forward 8 bars on its own timeframe) AND VolatilityState = GREAT_MOVEMENT AND CCI(14)/CCI(100)/CCI(900) each above its own SMA(20) and all above +100 (UNANIMITY) AND a fresh M5 CCI(14) zero-cross this closed bar (LTF ENTRY_TRIGGER event on the same LTF as the gate) | All four layers true on the same closed bar = SUPER. Any single layer false downgrades the grade mechanically; there is no discretionary override in either direction. |

### 1.5 State Axes, Indicator Roles, and the Master Classification Loop

Three state axes describe the market at every closed bar; every axis has a finite value set and no other values exist:

- GravityState ∈ {BULL, BEAR, NEUTRAL}
- VolatilityState ∈ {NOTHING_HAPPENING, TRADABLE, GREAT_MOVEMENT}
- SignalGrade ∈ {NO_SIGNAL, STANDARD, SUPER}

Every indicator instance is assigned EXACTLY one of four roles at configuration time: GRAVITY_FILTER (sets GravityState), VOLATILITY_GATE (sets VolatilityState), ENTRY_TRIGGER (produces trigger events), EXIT_MANAGER (produces exit events). An instance never plays two roles; if the same formula is needed twice, two instances are configured.

```text
ON each CLOSED bar of the LTF:

    # 1. Classify gravity (states)
    HTF_gravity = GRAVITY_FILTER(HTF)          # BULL | BEAR | NEUTRAL
    LTF_gravity = GRAVITY_FILTER(LTF)          # BULL | BEAR | NEUTRAL
    DUAL_TF_GATE = (HTF_gravity == LTF_gravity) AND (HTF_gravity != NEUTRAL)

    # 2. Classify volatility (ENERGY GATE)
    energy_pass = ALL v IN VOLATILITY_GATE_set:
                      v.raw > SMA(v.raw, 1) shifted forward 5   # PERSISTENCE TEST
    VolatilityState = NOTHING_HAPPENING if NOT energy_pass
                      else TRADABLE or GREAT_MOVEMENT per configured thresholds

    # 3. Unanimity (same family, fast/mid/slow, each vs its own smoothing line)
    UNANIMOUS = ALL of {fast, mid, slow}:
                    same side of equilibrium AND same side of own smoothing line
    IF NOT UNANIMOUS: SignalGrade = NO_SIGNAL; REFUSE; NEXT bar

    # 4. Trigger (event, not state)
    trigger = ENTRY_TRIGGER crossing completed ON THIS closed bar,
              in the direction of HTF_gravity, inside its trigger window

    # 5. Grade
    IF DUAL_TF_GATE AND VolatilityState == GREAT_MOVEMENT AND UNANIMOUS AND trigger:
        SignalGrade = SUPER
    ELSE IF DUAL_TF_GATE AND VolatilityState == TRADABLE AND UNANIMOUS AND trigger:
        SignalGrade = STANDARD
    ELSE:
        SignalGrade = NO_SIGNAL

    # 6. Act or refuse
    IF SignalGrade != NO_SIGNAL AND risk_limits_pass():   # <=1% risk, correlation cap
        ENTER in direction of HTF_gravity
    ELSE:
        WAIT   # refusal is the default action, not a failure state
```

All readings use CLOSED bars only. Intra-bar values are never used unless a rule explicitly says otherwise.

### 1.6 Glossary of Canonical Terms

| Term | Definition |
|---|---|
| GravityState | Regime classification per timeframe: one of {BULL, BEAR, NEUTRAL}. |
| VolatilityState | Energy classification: one of {NOTHING_HAPPENING, TRADABLE, GREAT_MOVEMENT}. |
| SignalGrade | Entry grade: one of {NO_SIGNAL, STANDARD, SUPER}. |
| GRAVITY_FILTER | Indicator role: sets GravityState. Produces states, never entries. |
| VOLATILITY_GATE | Indicator role: sets VolatilityState via the ENERGY GATE. |
| ENTRY_TRIGGER | Indicator role: produces trigger events (entry instants). |
| EXIT_MANAGER | Indicator role: produces exit events; never used for entries. |
| PERSISTENCE TEST | Raw indicator value vs its own forward-shifted short SMA baseline (example: SMA(1) shifted forward 4 bars). Correct side on the current CLOSED bar = PERSISTENT(true); otherwise PERSISTENT(false). |
| UNANIMITY TEST | N periods of the SAME indicator family (fast/mid/slow), each with its own independent smoothing line, all on the same side of their equilibrium AND of their own smoothing line simultaneously = UNANIMOUS(true). ANY disagreement = UNANIMOUS(false) = NO_SIGNAL. Partial agreement is never "weak signal". |
| DUAL-TF GATE | HTF GravityState and LTF GravityState computed independently; passes only if both are equal AND directional (both BULL or both BEAR). |
| ENERGY GATE | Every volatility indicator (example: ADX, ATR) above its own forward-shifted SMA baseline; all must pass. |
| SUPER signal | DUAL-TF GATE pass AND VolatilityState == GREAT_MOVEMENT AND UNANIMITY TEST pass AND a fresh LTF ENTRY_TRIGGER event inside its trigger window. |
| TRIGGER EVENT | An INSTANT: the single closed bar on which a crossing completed. Entries key off trigger events. |
| STATE | A CONDITION persisting across bars. Authorizations (licenses) key off states. |
| HTF | Higher timeframe: the regime layer (e.g., H4, H1). |
| LTF | Lower timeframe: the timing layer (e.g., M15, M5, M1). |
| CLOSED bar | The only bar on which indicator readings are valid. Intra-bar values are never used unless a rule explicitly says otherwise. |

### G-1 — Mass or Oscillator? Role Classification

**Issue:** Is a given indicator instance an equilibrium-deviation meter (oscillator) rather than a mass (trend gravity)?

**Rule:** Classify by output domain, evaluated once at configuration time. An indicator whose output is denominated in the instrument's price units and tracks the price level with no fixed equilibrium constant is a MASS: gravity laws apply (mass hierarchy, orbit, dominance under G-2, eligibility for GRAVITY_FILTER role via level comparison). An indicator whose output is normalized around a fixed equilibrium constant defined by its formula — bounded (RSI in [0,100], equilibrium 50; Stochastic in [0,100], equilibrium 50) or unbounded but centered (CCI, equilibrium 0) — is an OSCILLATOR: equilibrium-deviation laws apply (Section 1.2 snap-back/extension classification, zero/mid-line crossings as trigger events). Every indicator instance receives exactly one classification; no instance is both.

```text
FUNCTION classify(indicator):
    IF output_units(indicator) == price_units(instrument)
       AND fixed_equilibrium_constant(indicator) == NONE:
        RETURN MASS          # laws: hierarchy, orbit, G-2 dominance
    IF fixed_equilibrium_constant(indicator) != NONE:
        RETURN OSCILLATOR    # laws: deviation, snap-back vs slingshot
    # derived lines inherit the classification of their base formula
```

**Application:** Classify four instances on US30. (1) H1 SMA(200): output in index points — true; tracks price level — true; fixed equilibrium constant — none. Result: MASS. (2) H1 CCI(140): output dimensionless — price-units test false; fixed equilibrium constant 0 exists — true. Result: OSCILLATOR; its "above 0 AND above its SMA(1) shifted forward 4" read is a deviation-plus-persistence state, not a price-level orbit. (3) M5 RSI(5): bounded [0,100], equilibrium 50 exists — true. Result: OSCILLATOR; the recross above 50 in an up-regime is a trigger event at equilibrium, and the exit at RSI(5) = 40 is a deviation threshold. (4) BB(200) middle band on H1: the middle band is SMA(200) — price units true, equilibrium none. Result: MASS, even though the Bollinger envelope is drawn as bands; the band width belongs to a separate VOLATILITY_GATE instance. Each check resolved true/false with no residual ambiguity.

**Conclusion (Generalized Principle):** For ANY indicator on ANY instrument and timeframe, the applicable physical law is decided by one binary test on the output domain: price-unit output with no fixed equilibrium = mass, governed by hierarchy and dominance; fixed-equilibrium output = oscillator, governed by deviation mechanics where distance from equilibrium is tradable only under aligned gravity and energy. The classification is a property of the formula, not of recent behavior, and is assigned before any market data is read.

Transfer test: given a NEW indicator it has never seen, the agent inspects the formula's output domain, states the fixed equilibrium constant or proves none exists, assigns exactly one of {MASS, OSCILLATOR}, and confirms that every rule it subsequently applies to that indicator comes from that classification's law set only.

### G-2 — Which Gravity Dominates?

**Issue:** When two mass indicators report conflicting directions on the same instrument, does the heavier mass (higher timeframe first, then longer period) alone set the regime?

**Rule:** Yes — by fixed precedence, never by vote and never by recent accuracy. Compare the two masses lexicographically: (1) higher timeframe dominates; (2) if timeframes are equal, longer period dominates. The dominant mass's direction is the regime read for its layer. The subordinate mass is demoted to timing only: its disagreement fails the DUAL-TF GATE and blocks entries (action = WAIT), but it never inverts GravityState and never authorizes a position against the dominant mass. Scaling in against dominant gravity is forbidden under the same rule.

```text
FUNCTION dominant(A, B):          # A, B are MASS instances, directions conflict
    IF A.timeframe != B.timeframe:
        RETURN higher_timeframe_of(A, B)
    RETURN longer_period_of(A, B)

regime_direction = direction(dominant(A, B))
subordinate.role  = timing_only            # never sets regime
IF direction(subordinate) != regime_direction:
    DUAL_TF_GATE = FAIL
    action = WAIT                          # no entry either direction
counter_regime_entry = FORBIDDEN           # in all cases
```

**Application:** US30, two conflicts. Conflict 1 — cross-timeframe: H1 price is above SMA(200) (heavy mass reads BULL); on M5, price is below SMA(4) shifted forward 8 bars (light mass reads BEAR). Check timeframes: H1 > M5 — true, so H1 SMA(200) dominates; regime = BULL. Check subordinate agreement: M5 direction BEAR != BULL — true, so DUAL-TF GATE = FAIL; shorts are refused (counter-regime), longs are refused (gate fail); action = WAIT until M5 closes back above its shifted SMA(4) and both layers read BULL. Conflict 2 — same timeframe: H1 price above SMA(200) but below SMA(20). Timeframes equal — true; compare periods: 200 > 20 — true, so SMA(200) dominates; regime remains BULL; SMA(20) is demoted to timing (the pullback toward the fast MA becomes the entry zone, per the pullback-entry pattern), and no BEAR regime is declared at any point.

**Conclusion (Generalized Principle):** For ANY pair of conflicting trend masses on ANY instrument, regime authority follows a fixed lexicographic precedence — timeframe rank first, period length second — and the loser of that comparison is permanently reassigned to the timing layer for as long as the conflict lasts: its disagreement can only withhold authorization (gate fail, WAIT), never grant or reverse it. Regime is a dictatorship of the heaviest mass, not a democracy of indicators, and the precedence order is decided at configuration time from indicator parameters alone, independent of market data.

Transfer test: given a NEW pair of conflicting trend indicators, the agent computes (timeframe rank, period) for each, states which one sets the regime and which is demoted to timing, and demonstrates that no entry it would take opposes the dominant one's direction while the conflict persists.
