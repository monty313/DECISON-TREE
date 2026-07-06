## 5. HTF Persistence and Multiple LTF Re-Entries

This section defines the standing-license model. A persistent HTF state is a battery: while it holds charge, it authorizes an unbounded count of LTF entries, down to high-frequency cadence. Authorization derives from states; entries derive from trigger events; exits derive from each trade's own EXIT_MANAGER rules. The three rules below specify (P-1) what the license is and why prior-trade outcomes are excluded from it, (P-2) why holding time is excluded from trade validity, and (P-3) the exact loop the agent executes on every closed LTF bar.

### P-1 — HTF Persistence Is a Standing License, Not a One-Time Event

**Issue:** On the current closed bar, is the re-entry LICENSE true, such that the next fresh LTF ENTRY_TRIGGER event in the license direction is a separately authorized, independent entry?

**Rule:** The LICENSE is a state, recomputed on every closed bar, defined as the conjunction of the PERSISTENCE TEST on the HTF GRAVITY_FILTER indicator and the ENERGY GATE on every VOLATILITY_GATE indicator. While LICENSE == true, every fresh LTF ENTRY_TRIGGER event in the license direction is one authorized, independent entry. The outcome, P&L, exit reason, or existence of any previous trade taken under the same license is not an input to authorization. Authorization is tied to the state, never to the previous trade's result.

```text
PERSISTENT(I_htf, t) :=
    raw(I_htf, t) is on the directional side of baseline(I_htf, t)
    where baseline(I_htf, t) := SMA_short(I_htf) shifted forward k bars
                                # example: SMA(1) of the indicator, shift 4
    evaluated on the current CLOSED HTF bar only

ENERGY_GATE(t) :=
    for EVERY VOLATILITY_GATE indicator V:
        raw(V, t) > SMA_short(V) shifted forward j bars   # example: SMA(1), shift 5
    ALL must pass; ANY failure = ENERGY_GATE(t) == false

LICENSE(t) := PERSISTENT(I_htf, t) == true
          AND ENERGY_GATE(t) == true
          AND GravityState(HTF) in {BULL, BEAR}           # NEUTRAL never licenses

ENTRY_AUTHORIZED(e) :=
        LICENSE(t_e) == true                              # t_e = closed bar of event e
    AND e is a fresh LTF ENTRY_TRIGGER event on bar t_e
    AND direction(e) == direction(GravityState(HTF))

# FORBIDDEN inputs: outcome(previous_trade), pnl(previous_trade),
# count(trades_under_license), time_since_last_trade.
# None of these symbols occur above.
```

**Application:** HTF = H1, GRAVITY_FILTER = H1 CCI(140). On the closed H1 bar at 13:00, raw CCI(140) = +62. Baseline = SMA(1) of CCI(140) shifted forward 4 bars = the value printed 4 closed H1 bars earlier = +38. Check 1: raw above equilibrium, +62 > 0 → true. Check 2: raw above its shifted baseline, +62 > +38 → true. PERSISTENT(true); GravityState(H1) = BULL. ENERGY GATE on H1: ADX(14) = 27.4 versus its SMA(1) shift-5 baseline 24.1 → true; ATR(14) = 18.2 points versus baseline 16.9 → true; gate passes. LICENSE(13:00) = true, and it re-verifies true on each of the next six closed H1 bars. Inside that window the ENTRY_TRIGGER, M5 CCI(14), completes upward zero-crossings on the closed M5 bars at 13:35, 14:50, and 16:10 — three distinct trigger events. Trade 1 (entered after the 13:35 event) exits at its hard stop for −1R at 14:20. At 14:50 the agent evaluates exactly two things: LICENSE(14:50) == true and the zero-cross is a fresh event → ENTRY_AUTHORIZED = true; trade 2 is entered. The −1R outcome of trade 1 appears in no test. Trade 3 follows identically at 16:10. Generalization of this example: pair ANY HTF indicator with a forward-shifted, lightly smoothed copy of itself; raw on the correct side of its own shifted line = battery charged = re-entries licensed; raw crossing back through the shifted line = stop licensing new entries.

**Conclusion (Generalized Principle):** Authorization attaches to a persistent state; entries attach to instantaneous events. For any indicator family, any instrument, and any HTF/LTF pair, a standing license is the conjunction of (i) the HTF indicator's raw value on the directional side of its own forward-shifted short-SMA baseline on the current closed bar and (ii) an all-pass ENERGY GATE. While that conjunction holds, each fresh LTF trigger event in the license direction is one independent, fully authorized entry, and no property of any prior trade is an admissible input to the authorization function. The license is evaluated fresh on every closed bar; it is never "consumed" by a trade.
Transfer test: Given a never-seen HTF indicator, the agent verifies correct application by writing LICENSE(t) using only the indicator's raw value versus its own forward-shifted short-SMA baseline plus the ENERGY GATE, then confirming by symbol inspection that no term referencing any prior trade's outcome, count, or timing appears in the expression.

### P-2 — Trade Duration Is Irrelevant to Validity

**Issue:** Given a closed trade, is it VALID based solely on whether its entry satisfied ENTRY_AUTHORIZED at the entry event and its exit satisfied that trade's own EXIT_MANAGER rule at the exit, with holding time excluded from the test?

**Rule:** A trade's legitimacy is a function of rule-satisfaction at exactly two loci: the entry event and the exit condition. Duration is not a term in the validity expression. There is no minimum holding time and no maximum holding time. A trade held for 3 minutes and a trade held for 3 hours receive identical verdicts when both satisfy the same two clauses. High-frequency LTF cadence under a persistent HTF license is a licensed output of this rule, because the HTF gravity state — not the clock and not microstructure noise — is the source of edge.

```text
TRADE_VALID(T) :=
        ENTRY_AUTHORIZED(T.entry_event) == true    # per P-1, on the trigger's CLOSED bar
    AND EXIT_SATISFIED(T) == true

EXIT_SATISFIED(T) :=
    T.exit_reason in {
        EXIT_MANAGER condition true on a CLOSED bar,
        hard_stop_filled,
        hard_target_filled
    }

# The symbols T.duration, T.bar_count, T.holding_minutes do not occur
# in TRADE_VALID. Duration appears nowhere in the validity test.
```

**Application:** Third persistence family, from a different indicator class than P-1: HTF = H4, GRAVITY_FILTER = H4 RSI(14). Closed H4 bar: raw RSI(14) = 61.8; equilibrium = 50; baseline = SMA(5) of RSI(14) shifted forward 3 bars = 57.2. Check 1: 61.8 > 50 → true. Check 2: 61.8 > 57.2 → true. PERSISTENT(true); GravityState(H4) = BULL. H4 ENERGY GATE: ADX(14) = 26.0 > shifted baseline 23.5 → true; ATR(14) = 41.0 points > shifted baseline 38.6 → true. LICENSE = true. Generalization of this example: swapping RSI for CCI changes nothing — ANY HTF oscillator paired with a shifted, lightly smoothed copy of itself yields the same binary persistence read: raw on the correct side of its own shifted line = battery charged = re-entries licensed; crossing back through = stop licensing new entries. Under this license, two trades from two independent signal sources (one position each per the correlation cap, each risking at most 1% of account): Trade A, source S1: M1 CCI(14) crosses above 0 on the closed 09:31 bar; DUAL-TF GATE passes (price above SMA(4) shifted forward 8 bars on both M1 and M15 → both BULL); entry at the 09:32 open; EXIT_MANAGER = M1 RSI(5) reaching 40; RSI(5) prints 39.6 on the 09:34 close; exit at the 09:35 open. Duration ≈ 3 minutes. Trade B, source S2: M5 CCI(14) upward zero-cross on the closed 10:00 bar; entry 10:05 open; EXIT_MANAGER = SMA(20)-smoothed CCI(100) on M5 crossing below 0 against the position; it fires on the 13:10 close; exit 13:15 open. Duration = 3 hours 10 minutes. TRADE_VALID(A): entry authorized true AND exit satisfied true → VALID. TRADE_VALID(B): entry authorized true AND exit satisfied true → VALID. The verdicts are identical; the 60-fold duration ratio is not an input. Trade A is short because its exit clock (RSI(5) on M1) is fast, not because the signal is noise.

**Conclusion (Generalized Principle):** For any indicator set, instrument, and timeframe pair, validity is evaluated at exactly two instants — the entry trigger event and the exit condition — and the clock time between them carries zero evidential weight. Any filter that rejects, penalizes, or grades trades by holding time introduces a non-rule input and is prohibited. Cadence is an emergent output: a fast exit clock under a persistent HTF license produces many short trades, and each is exactly as legitimate as a long one, because the edge lives in the HTF gravity state that licensed them all, not in their duration.
Transfer test: The agent verifies correct application to a new indicator by writing that indicator's TRADE_VALID expression and mechanically confirming that no duration, bar-count, or elapsed-time symbol occurs anywhere in it.

### P-3 — The Re-Entry Loop

**Issue:** On the current closed LTF bar, does the re-entry loop authorize a new entry?

**Rule:** On every closed LTF bar the agent recomputes the license as the conjunction of the PERSISTENCE TEST, the ENERGY GATE, and the DUAL-TF GATE. A new entry is taken iff the license is true AND a fresh LTF ENTRY_TRIGGER event completed on this bar in the license direction AND no position from this signal source is open. When the license turns false, authorization of NEW entries stops on that same closed bar. Open positions are not closed by license failure; each open position is governed exclusively by its own EXIT_MANAGER rules. License failure gates new entries; exit rules gate open positions — two independent mechanisms that never substitute for each other.

```text
on each CLOSED LTF bar t:

    # 1. Recompute the license (states, not events)
    persistence := PERSISTENT(I_htf, t)        # raw vs own forward-shifted SMA baseline
    energy      := ENERGY_GATE(t)              # ALL VOLATILITY_GATE indicators above
                                               # their own shifted baselines
    dual_tf     := DUAL_TF_GATE(t)             # GravityState(HTF) == GravityState(LTF)
                                               # AND both in {BULL, BEAR}
    LICENSE     := persistence AND energy AND dual_tf

    # 2. New-entry branch — gated by LICENSE only
    if LICENSE == true
       AND a fresh ENTRY_TRIGGER event completed on bar t
           in the direction of GravityState(HTF)
       AND no open position exists from this signal source:
            enter at the open of bar t+1
            attach this trade's EXIT_MANAGER rules and hard stop
            risk <= 1% of account; never against dominant gravity
    else:
            authorize no new entry on bar t

    # 3. Open-position branch — gated ONLY by each trade's own exit rules
    for each open position p:
        if p.exit_rule(t) == true: close p
        # LICENSE == false does NOT close p; it ONLY blocks new entries
```

**Application:** Instrument US30; HTF = H1 with GRAVITY_FILTER CCI(140); LTF = M5 with ENTRY_TRIGGER CCI(14) zero-cross; EXIT_MANAGER = M5 RSI(5) reaching 40. Timeline of closed bars: 13:00 H1 close — CCI(140) = +71 versus shifted SMA(1)-shift-4 baseline +52 → PERSISTENT(true); ADX(14) = 28.3 > 25.6 and ATR(14) = 19.4 > 17.8 → ENERGY GATE true; price above SMA(4) shifted forward 8 bars on both H1 and M5 → DUAL-TF GATE true; LICENSE = true. 13:05 M5 close — fresh CCI(14) upward zero-cross, no open position from this source → enter long at 13:10 open. 13:40 M5 close — RSI(5) = 38.9 ≤ 40 → exit rule true → position closed. 14:15 M5 close — LICENSE still true, fresh zero-cross → second entry at 14:20 open. 15:00 H1 close — ADX(14) = 24.9 falls below its shift-5 baseline 26.2 → ENERGY GATE false → LICENSE = false on the 15:00 M5 recheck; the forward shift makes this fail roughly 5 bars before an unshifted comparison would, an early warning of energy fade. New entries are blocked immediately. The 14:15 position stays open — license failure is not an exit rule — and closes at 15:35 when RSI(5) prints 39.2. 15:25 and 15:50 M5 closes — CCI(14) crosses 0 upward twice; both events are ignored: trigger events without a license authorize nothing. An equivalent persistence read from a structural family: five SMA(4) instances at shifts 0, 1, 2, 3, 4 on M15, all stacked in shift order and all above SMA(50) → persistence true; any pairwise crossing in the fan → persistence false. Generalization of both reads: ANY HTF indicator versus a shifted, lightly smoothed copy of itself is the license input; raw on the correct side = battery charged = the loop keeps admitting fresh trigger events; crossing back through = the loop stops admitting them, while open trades finish under their own exit logic.

**Conclusion (Generalized Principle):** The re-entry loop is a two-gate architecture that holds for any indicator set, instrument, and timeframe pair: an admission gate (the license — persistence AND energy AND dual-timeframe agreement, recomputed from states on every closed LTF bar) decides whether new trades enter, and a per-trade exit gate (each position's own EXIT_MANAGER) decides when existing trades leave. Entries require the simultaneous truth of a state (license) and an event (fresh trigger) plus a vacancy condition (no open position from the same source). License failure terminates admission instantly but never touches open positions; exit rules close positions but never re-open admission. Neither gate reads prior-trade outcomes, trade counts, or clock time.
Transfer test: The agent verifies correct application to a new indicator by simulating one licensed window on historical closed bars and confirming that every entry coincides with license-true AND fresh-trigger AND no-open-position, that zero entries occur after the license's first false bar, and that each open position's exit bar satisfies only its own exit rule.
