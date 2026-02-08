# Phase-11: Signal Eligibility Layer

## Purpose
Convert Phase-X verdicts (STRONG/CAUTION/WAIT/AVOID/NO_TRADE) into structured, trade-eligible signals.

**Still READ-ONLY - No execution, no prices, no quantities, no automation.**

## Why Phase-11 Matters

Before any automation can be considered, you must prove:
1. **Signals are RARE** - Most conditions produce NOT_ELIGIBLE
2. **Signals are CONSISTENT** - Same structure = same signal (deterministic)
3. **Signals are REPEATABLE** - Logic is explicit, testable, verifiable

**Without Phase-11, automation will destroy capital.**

## Signal Contract

Every signal evaluation produces a `SignalContract` with:

### Core Fields
- `SIGNAL_STATUS`: ELIGIBLE | NOT_ELIGIBLE
- `SIGNAL_TYPE`: TREND_CONTINUATION | TREND_REVERSAL | BREAKOUT | PULLBACK | RANGE_BOUND
- `DIRECTION`: LONG | SHORT | NEUTRAL
- `ENTRY_STYLE`: PULLBACK_ONLY | BREAKOUT_ONLY | IMMEDIATE_OK | NO_ENTRY
- `TIMEFRAME`: SWING | DAY | SCALP | POSITION
- `RISK_CLASS`: LOW | MEDIUM | HIGH | EXTREME
- `EXECUTION`: HUMAN_ONLY (always hardcoded)

### Context Fields (for transparency)
- `verdict`: Phase-X verdict (STRONG/CAUTION/etc.)
- `confidence`: Phase-X confidence (HIGH/MEDIUM/LOW)
- `summary`: Human-readable explanation
- `alignment_state`: FULL/PARTIAL/UNSTABLE/CONFLICT
- `htf_location`: SUPPORT/MID/RESISTANCE
- `trend_state`: UP/DOWN/RANGE
- `active_scenario`: SCENARIO_A/B/C

## Eligibility Rules

### Rule 1: Verdict Filter
**Only STRONG or CAUTION verdicts can be ELIGIBLE**
- WAIT → NOT_ELIGIBLE (HIGH risk)
- AVOID → NOT_ELIGIBLE (EXTREME risk)
- NO_TRADE → NOT_ELIGIBLE (EXTREME risk)

### Rule 2: Gate Override
**Execution gate BLOCKED → Always NOT_ELIGIBLE**
- Even STRONG verdict with perfect structure
- Gate blocking = EXTREME risk (overrides everything)

### Rule 3: STRONG Verdict Requirements
**STRONG + FULL alignment = ELIGIBLE**
- Location = SUPPORT → Entry: PULLBACK_ONLY
- Location = MID → Entry: IMMEDIATE_OK
- Location = RESISTANCE → NOT_ELIGIBLE (shouldn't happen with STRONG)
- Risk class: LOW

### Rule 4: CAUTION Verdict Requirements
**CAUTION + FULL alignment = ELIGIBLE (with restrictions)**
- Any location → Entry: PULLBACK_ONLY (never immediate)
- Risk class: MEDIUM

### Rule 5: Direction Mapping
- Trend UP → Direction: LONG
- Trend DOWN → Direction: SHORT
- Trend RANGE → Direction: NEUTRAL

## Signal Rarity

Most market conditions are **NOT ELIGIBLE**:

### Eligible (Rare):
1. STRONG + FULL + SUPPORT/MID + Gate PASS
2. CAUTION + FULL + Any location + Gate PASS

### Not Eligible (Common):
1. WAIT verdict (alignment building)
2. AVOID verdict (unstable/conflict)
3. NO_TRADE verdict (gate blocked)
4. STRONG but gate BLOCKED
5. STRONG but not FULL alignment
6. CAUTION but not FULL alignment

**Expected ratio: ~10-20% of analyzed stocks produce ELIGIBLE signals.**

## Entry Styles

### PULLBACK_ONLY
- Wait for price to retrace to safer level
- Used at SUPPORT (already pulled back)
- Used with CAUTION (extended, need better entry)
- **Never chase current price**

### IMMEDIATE_OK
- Current level is acceptable entry
- Used at MID with STRONG + FULL alignment
- Structure supports immediate entry
- **Still requires human decision**

### BREAKOUT_ONLY
- Wait for structure to break (not yet implemented)
- Future use for consolidation breakouts

### NO_ENTRY
- Signal is NOT_ELIGIBLE
- Do not trade under any circumstances

## Example Outputs

### Eligible Signal (STRONG):
```
======================================================================
PHASE-11: SIGNAL ELIGIBILITY
======================================================================
✅ SIGNAL_STATUS: ELIGIBLE
   SIGNAL_TYPE: TREND_CONTINUATION
   DIRECTION: LONG
   ENTRY_STYLE: PULLBACK_ONLY
   TIMEFRAME: SWING
   RISK_CLASS: LOW
   EXECUTION: HUMAN_ONLY

STRUCTURAL CONTEXT:
   Verdict: STRONG (HIGH confidence)
   Alignment: FULL
   HTF Location: SUPPORT
   Trend: UP
   Scenario: SCENARIO_A

HUMAN SUMMARY:
   Structure is strong and aligned across timeframes. Conditions favor continuation.
======================================================================
```

### Eligible Signal (CAUTION):
```
======================================================================
PHASE-11: SIGNAL ELIGIBILITY
======================================================================
✅ SIGNAL_STATUS: ELIGIBLE
   SIGNAL_TYPE: TREND_CONTINUATION
   DIRECTION: LONG
   ENTRY_STYLE: PULLBACK_ONLY
   TIMEFRAME: SWING
   RISK_CLASS: MEDIUM
   EXECUTION: HUMAN_ONLY

STRUCTURAL CONTEXT:
   Verdict: CAUTION (MEDIUM confidence)
   Alignment: FULL
   HTF Location: RESISTANCE
   Trend: UP
   Scenario: SCENARIO_A

HUMAN SUMMARY:
   Trend is strong but stock is extended near higher-timeframe resistance.
======================================================================
```

### Not Eligible Signal (AVOID):
```
======================================================================
PHASE-11: SIGNAL ELIGIBILITY
======================================================================
❌ SIGNAL_STATUS: NOT_ELIGIBLE
   REASON: AVOID verdict - Stock overextended near resistance with unstable structure.
   DIRECTION: LONG
   RISK_CLASS: EXTREME

STRUCTURAL CONTEXT:
   Verdict: AVOID (LOW confidence)
   Alignment: UNSTABLE
   HTF Location: RESISTANCE
   Trend: UP
   Scenario: SCENARIO_B

HUMAN SUMMARY:
   Stock is overextended near higher-timeframe resistance with unstable structure.
======================================================================
```

## Integration Flow

```
Phase-4: Multi-Timeframe Analysis
    ↓ (technical structure)
Phase-5: Classification
    ↓ (alignment, location, scenarios)
Phase-6A: Scenario Probabilities
    ↓ (probability distribution)
Phase-7A: Execution Gates
    ↓ (gate status: PASS/BLOCKED)
Phase-X: Human Summary
    ↓ (verdict, confidence, summary)
Phase-11: Signal Eligibility ← NEW
    ↓ (ELIGIBLE / NOT_ELIGIBLE)
Human Decision
    ↓
Manual Execution (if desired)
```

## Critical Guarantees

### 1. No Prices
Signal contains **zero price information**:
- No entry price
- No stop loss price
- No target price
- Human determines exact levels

### 2. No Quantities
Signal contains **zero position sizing**:
- No number of shares
- No capital allocation
- Human determines position size based on risk tolerance

### 3. No Automation
Signal execution mode is **always HUMAN_ONLY**:
- No automatic order placement
- No broker integration
- No autonomous trading
- Human makes final decision

### 4. Deterministic
Same market structure produces same signal:
- No randomness
- No LLM creativity
- Fully testable
- Fully repeatable

## Test Results

All 10 tests passed:
- ✅ STRONG + FULL + SUPPORT → ELIGIBLE (pullback)
- ✅ STRONG + FULL + MID → ELIGIBLE (immediate OK)
- ✅ CAUTION + FULL + RESISTANCE → ELIGIBLE (pullback only)
- ✅ WAIT verdict → NOT_ELIGIBLE
- ✅ AVOID verdict → NOT_ELIGIBLE
- ✅ NO_TRADE verdict → NOT_ELIGIBLE
- ✅ Gate BLOCKED → NOT_ELIGIBLE (overrides STRONG)
- ✅ SHORT direction for DOWN trend
- ✅ Execution mode always HUMAN_ONLY
- ✅ Signal rarity validated (most are NOT_ELIGIBLE)

## Usage

Phase-11 automatically runs after Phase-X in market analysis:

```bash
python main.py
>> analysis yes bank
```

Output includes:
1. Multi-timeframe analysis
2. Phase-X human summary
3. **Phase-11 signal eligibility** ← NEW

## Files

- `logic/signal_eligibility.py` - Signal evaluation engine (326 lines)
- `test_phase_11_signals.py` - Comprehensive test suite (10 tests)
- `logic/execution_engine.py` - Integration point (after Phase-X)

## What Phase-11 Does NOT Do

❌ Place orders
❌ Connect to broker
❌ Calculate position size
❌ Set stop losses
❌ Set profit targets
❌ Execute trades
❌ Manage risk automatically
❌ Track performance

All of the above remain **HUMAN responsibilities**.

## What Phase-11 DOES Do

✅ Evaluates if market structure is trade-eligible
✅ Classifies signal type and direction
✅ Recommends entry style (pullback vs immediate)
✅ Assigns risk class based on structure
✅ Provides transparent reasoning
✅ Maintains signal rarity (quality > quantity)
✅ Ensures consistency and repeatability

## Next Phase (Not Implemented)

Phase-12 (future): Performance tracking of signal outcomes
- Track which ELIGIBLE signals human chose to take
- Track outcomes (win/loss/breakeven)
- Validate signal quality over time
- Still no automation - just measurement

**Phase-11 is the final phase before any execution consideration.**
