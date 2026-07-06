## 4. Pullback Entries vs High-Momentum ("Super") Entries

Both entry philosophies in this section trade the SAME directional regime. They differ only in which phase of the orbit they enter. The pullback entry buys the orbit returning to the mass: price retraces to the fast gravity line, and the position harvests the re-acceleration back toward trend. The Super entry buys the orbit escaping with maximum energy: price (or an oscillator) pierces its own volatility band while every layer — HTF gravity, LTF gravity, energy, and multi-speed unanimity — agrees, and the position rides the escape leg. Neither philosophy is superior; each is licensed by a different (GravityState, VolatilityState) precondition and each is bound to a different exit clock.

The classification error this section forbids is MIXING, not choosing. Every order carries exactly one entry-type label, assigned at order creation: `entry_type in {PULLBACK, SUPER}`. The exit engine reads ONLY the exit rule bound to that label. A pullback entry managed with a Super exit overstays the return leg; a Super entry managed with a pullback exit abandons the escape leg on the first fast-oscillator wiggle. Both hybrids are unlicensed trades even when every individual indicator reading was correct. Each IRAC below therefore contains its own exit discipline inside the same block as its entry — the pair is indivisible.

### E-1 — Pullback Entry (Mean Reversion Within Trend)

**Issue:** Is a pullback entry — a retrace touch of the fast gravity line or a fast-oscillator equilibrium recross in the regime direction — licensed AND triggered on the current CLOSED bar?

**Rule:** The pullback license is a STATE: `GravityState in {BULL, BEAR}` AND `VolatilityState in {TRADABLE, GREAT_MOVEMENT}`. The pullback entry is a TRIGGER EVENT on exactly one closed bar: either the retrace-touch event (bar trades to or through the fast gravity line and closes back on the regime side of it) or the fast-oscillator recross event (prior closed bar on the counter-regime side of equilibrium, current closed bar on the regime side). Two instances of the fast oscillator are declared: one with role ENTRY_TRIGGER, one with role EXIT_MANAGER. Exit is a STATE checked on every closed bar: the fast oscillator completing its round trip to the round-trip level, OR price closing through the mean MA. Either exit condition alone closes the position.

```text
# License (STATE, closed bars only)
LICENSE_PULLBACK =
      GravityState in {BULL, BEAR}
  AND VolatilityState in {TRADABLE, GREAT_MOVEMENT}

# Entry (TRIGGER EVENT, exactly one closed bar) — BULL case; mirror every comparison for BEAR
TOUCH_EVENT   = (low[0] <= FAST_GRAVITY_LINE[0]) AND (close[0] > FAST_GRAVITY_LINE[0])
RECROSS_EVENT = (FAST_OSC[1] < EQUILIBRIUM) AND (FAST_OSC[0] > EQUILIBRIUM)
ENTER_PULLBACK_LONG = LICENSE_PULLBACK
                  AND GravityState == BULL
                  AND (TOUCH_EVENT OR RECROSS_EVENT)

# Exit (STATE, checked every closed bar while the position is open) — long case
EXIT_PULLBACK_LONG = (FAST_OSC[0] <= ROUND_TRIP_LEVEL)     # oscillator round trip complete
                  OR (close[0] < MEAN_MA[0])               # mean gravity line broken
# [0] = current closed bar, [1] = prior closed bar
```

**Application:** US30, entry timeframe M15. Bindings: FAST_GRAVITY_LINE = SMA(20), MEAN_MA = SMA(50), FAST_OSC = RSI(5), EQUILIBRIUM = 50, ROUND_TRIP_LEVEL = 40. Step-by-step on the current closed M15 bar: (1) GravityState — H1 close 40,512 > SMA(200) = 40,180 AND > BB(200) middle band = 40,196 → BULL → true. (2) VolatilityState — M15 ADX(14) = 24.1 > its SMA(1) shifted forward 5 bars = 21.6 → true; M15 ATR(14) = 37.8 > its shifted baseline 33.2 → true; ENERGY GATE passes → VolatilityState = TRADABLE → true. (3) LICENSE_PULLBACK = true. (4) RECROSS_EVENT — RSI(5)[1] = 46.3 (< 50), RSI(5)[0] = 57.1 (> 50) → true. TOUCH_EVENT — low 40,455 <= SMA(20) = 40,470 AND close 40,498 > 40,470 → also true; either alone suffices. (5) ENTER_PULLBACK_LONG = true → long opened at the next bar's open, labeled `entry_type = PULLBACK`. Exit walk: seven closed bars later RSI(5)[0] = 39.6 <= 40 → EXIT_PULLBACK_LONG = true → position closed. Close never printed below SMA(50) = 40,441 during the trade; the price-through-mean leg stayed false and was not needed.

**Conclusion (Generalized Principle):** In any directional regime with at least tradable energy, a mean-reversion-within-trend entry is licensed by the regime STATE and triggered only by the single-bar EVENT of price re-converging to the fast gravity mean, or of the fastest oscillator re-crossing its equilibrium in the regime direction. Its exit is symmetric to its entry: the SAME speed class that timed the entry completes a round trip to a level between equilibrium and the entry side, or price closes through the slower mean line. Entry clock speed equals exit clock speed — that identity is what classifies the trade as harvesting the return leg of the orbit, on any oscillator, instrument, or timeframe.
Transfer test: Given a never-seen oscillator, the agent verifies it has identified that oscillator's equilibrium and a round-trip level nearer equilibrium than the entry extreme, and confirms the entry fires only on the closed-bar equilibrium recross event while the exit fires only on the round-trip level or a close through the mean line.

### E-2 — Super Entry (Volatility-Band Pierce With Full Alignment)

**Issue:** Is a Super entry — a volatility-band pierce in the regime direction under the full SUPER definition — licensed AND triggered on the current CLOSED bar?

**Rule:** The Super license is the complete SUPER definition; every clause is required and each is binary: DUAL-TF GATE pass (HTF GravityState == LTF GravityState, both directional) AND `VolatilityState == GREAT_MOVEMENT` AND UNANIMITY TEST pass AND a fresh LTF ENTRY_TRIGGER event within TRIGGER_WINDOW closed bars. The entry is a TRIGGER EVENT: the current closed bar closes beyond the volatility band in the regime direction while the prior closed bar did not (price beyond BB upper for BULL, beyond BB lower for BEAR; a band computed ON an oscillator is an equally valid band instance). The exit is a STATE bound to the MID-speed instance with role EXIT_MANAGER: the SMA-smoothed mid oscillator crossing equilibrium against the position. Hard prohibition, stated as a binary role rule: the fastest indicator instance holds role ENTRY_TRIGGER; role assignments are exclusive; exit logic reading an instance whose role is ENTRY_TRIGGER = role violation = unlicensed order management. A SUPER position exited on the fastest indicator is thereby reclassified as an unlicensed scalp and is forbidden in every state.

```text
# License (SUPER definition — all four clauses required)
SUPER_LICENSE =
      DUAL_TF_GATE_PASS                                  # HTF GravityState == LTF GravityState, both in {BULL, BEAR}
  AND VolatilityState == GREAT_MOVEMENT
  AND UNANIMOUS == true                                  # fast/mid/slow family: same side of equilibrium AND own smoothing line
  AND bars_since(LTF_TRIGGER_EVENT) <= TRIGGER_WINDOW

# Entry (TRIGGER EVENT) — BULL case; mirror every comparison for BEAR
BAND_PIERCE_EVENT = (close[0] > VOL_BAND_UPPER[0]) AND (close[1] <= VOL_BAND_UPPER[1])
ENTER_SUPER_LONG  = SUPER_LICENSE AND GravityState == BULL AND BAND_PIERCE_EVENT

# Exit (STATE) — MID-speed EXIT_MANAGER only; long case
EXIT_SUPER_LONG = (MID_OSC_SMOOTHED[0] < EQUILIBRIUM)    # mid flip against the position

# Role law (binary)
role(FAST_INSTANCE) == ENTRY_TRIGGER                     # entry clock
role(MID_INSTANCE)  == EXIT_MANAGER                      # exit clock
exit_reads(FAST_INSTANCE) -> FORBIDDEN                   # role violation: reclassifies trade as unlicensed scalp
```

**Application:** US30, LTF = M5, HTF = M15/H1. Step-by-step on the current closed M5 bar: (1) DUAL-TF GATE — M15 close 40,540 > SMA(4) shifted forward 8 bars = 40,488 → BULL; M1 close 40,541 > its shifted SMA(4) = 40,522 → BULL; equal and directional → pass → true. (2) VolatilityState — M5 ADX(14) = 31.4 > shifted SMA(1) baseline 24.9 AND M5 ATR(14) = 41.2 > 34.0 → true; M15 ADX(14) = 27.8 > 23.1 AND M15 ATR(14) = 55.6 > 49.4 → true; H1 CCI(140) = +162 > 0 AND above its SMA(1) shifted forward 4 bars = +141 → true; ENERGY GATE passes on all layers → GREAT_MOVEMENT → true. (3) UNANIMITY TEST — M5 CCI(14) = +178 > its SMA(20) smoothing +150; CCI(100) = +141 > +122; CCI(900) = +119 > +104; all three above +100 → UNANIMOUS(true); the fastest, CCI(14), is also beyond its +100 extreme. (4) Fresh trigger — M5 CCI(14) crossed 0 upward 2 closed bars ago; TRIGGER_WINDOW = 3 → true. (5) BAND_PIERCE_EVENT — close[0] = 40,568 > BB(20,2) upper 40,561 AND close[1] = 40,543 <= prior upper 40,552 → true. ENTER_SUPER_LONG = true → long opened, labeled `entry_type = SUPER`. Exit walk: over the next 46 M5 bars, CCI(14) crossed below 0 three times; each crossing was ignored — role(CCI(14)) == ENTRY_TRIGGER. On bar 46, SMA(20)-smoothed CCI(100) printed −4 < 0 → EXIT_SUPER_LONG = true → position closed.

**Conclusion (Generalized Principle):** A maximum-energy continuation entry is licensed only when every layer agrees simultaneously — dual-timeframe gravity, maximum energy state, multi-speed unanimity, and a fresh timing event — and is triggered by the single-bar event of price or oscillator escaping its own volatility envelope in the regime direction. Its exit clock is structurally slower than its entry clock: the mid-speed instance flips through equilibrium against the position; the fastest instance never manages the exit, because entry and exit roles are exclusive and asymmetric by design. This clock asymmetry — fast in, mid out — is what lets the position hold through fast-oscillator noise and capture the escape leg, on any indicator family, instrument, or timeframe pair.
Transfer test: Given a never-seen indicator family, the agent verifies it has ranked the instances by speed, bound the fastest to ENTRY_TRIGGER and a strictly slower smoothed instance to EXIT_MANAGER, and confirms no exit evaluation ever reads the ENTRY_TRIGGER instance.

### R-1 — Shared Risk-Sizing Law

**Issue:** Does the proposed order — new entry or scale-in, whether `entry_type == PULLBACK` or `entry_type == SUPER` — pass the binary pre-trade risk checklist on the current CLOSED bar?

**Rule:** One law governs both entry types with zero variation. C1: the amount at risk (position size × stop distance) is less than or equal to 1% of account equity. C2: `GravityState in {BULL, BEAR}` — NEUTRAL licenses no order of any type. C3: the order's direction equals the direction of GravityState; any order against the dominant GravityState is forbidden in every state, and scaling in against it is forbidden without exception. C4: a scale-in WITH the dominant GravityState is permitted only if the position's ORIGINAL entry-type license (LICENSE_PULLBACK for PULLBACK, SUPER_LICENSE for SUPER) evaluates true on the current closed bar — license validity is re-evaluated at the add, never inherited from entry time. C5: one open position per independent signal source (correlation cap); a second position from the same source is permitted only as a scale-in under C4. ORDER_ALLOWED requires all five; ANY false clause rejects the order. A rejected scale-in does not force an exit: exits remain governed solely by the entry-type exit rule (E-1 or E-2).

```text
PRE_TRADE_CHECK(order):
  C1 = (order.size * order.stop_distance) <= 0.01 * account_equity
  C2 = GravityState in {BULL, BEAR}
  C3 = (order.direction == direction_of(GravityState))       # NEUTRAL -> false; counter-gravity -> false
  C4 = if order.is_scale_in:
           license_of(order.entry_type)[0] == true            # PULLBACK -> LICENSE_PULLBACK; SUPER -> SUPER_LICENSE
       else:
           true
  C5 = (open_positions_from(order.signal_source) == 0) OR order.is_scale_in

  ORDER_ALLOWED = C1 AND C2 AND C3 AND C4 AND C5
  if NOT ORDER_ALLOWED: reject(order)                         # no override path exists
```

**Application:** Account equity 100,000 → risk cap 1,000. The E-2 SUPER long above: entry 40,568, stop below the M5 SMA(4) fan low at 40,488 → stop distance 80 points → size = 1,000 / 80 = 12.5 USD/point. Checklist: C1 — 12.5 × 80 = 1,000 <= 1,000 → true. C2 — GravityState = BULL → true. C3 — long == BULL → true. C4 — not a scale-in → true. C5 — no open position from this signal source → true. ORDER_ALLOWED = true. Thirty bars later, a scale-in long is proposed: C1 true (new risk 700 <= 1,000), C2 true, C3 true, but C4 re-evaluates SUPER_LICENSE and M5 CCI(100) has fallen to +84, below its +100 requirement → UNANIMOUS(false) → SUPER_LICENSE = false → C4 false → scale-in rejected. The original position stays open; its exit still waits on the E-2 mid-speed flip. Counterexample: a proposed short "hedge" while GravityState == BULL fails C3 regardless of size → rejected.

**Conclusion (Generalized Principle):** Risk law is entry-type-invariant: a fixed-fraction cap on the amount at risk per trade, a total prohibition on adding against the dominant gravity in every state, adds with gravity only under the original entry-type license re-verified on the current closed bar, and one position per independent signal source. Sizing and scaling are properties of the account and the regime, never of the entry philosophy — which is why the same five-clause checklist runs unchanged whether the order came from a mean-reversion trigger or a band-escape trigger, on any instrument or timeframe.
Transfer test: Given a never-seen entry strategy, the agent verifies it has mapped that strategy's license condition into clause C4 and confirms the identical five-clause checklist rejects any order that risks over the fixed fraction, opposes gravity, or duplicates a signal source.

### Entry-License Decision Table

Column semantics: "Pullback licensed?" and "Super licensed?" state whether the (GravityState, VolatilityState) precondition of that entry type is satisfied — for Super, the remaining SUPER clauses (DUAL-TF GATE, UNANIMITY TEST, fresh LTF trigger) must still evaluate true before entry. Action YES = proceed to the licensed entry's trigger evaluation; Action WAIT = evaluate no triggers, place no orders.

| GravityState | VolatilityState | Pullback licensed? | Super licensed? | Action |
|---|---|---|---|---|
| BULL | NOTHING_HAPPENING | NO | NO | WAIT |
| BULL | TRADABLE | YES | NO | YES |
| BULL | GREAT_MOVEMENT | YES | YES | YES |
| BEAR | NOTHING_HAPPENING | NO | NO | WAIT |
| BEAR | TRADABLE | YES | NO | YES |
| BEAR | GREAT_MOVEMENT | YES | YES | YES |
| NEUTRAL | NOTHING_HAPPENING | NO | NO | WAIT |
| NEUTRAL | TRADABLE | NO | NO | WAIT |
| NEUTRAL | GREAT_MOVEMENT | NO | NO | WAIT |
