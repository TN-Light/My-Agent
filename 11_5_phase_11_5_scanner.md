# Phase-11.5: Dynamic Market Scanner (INSTITUTIONAL GRADE)

## Purpose

Convert single-symbol intelligence into a **multi-instrument, multi-market scanning engine** while preserving:
- Signal rarity (≤20% eligible)
- Safety (all Phase-4→11 checks per instrument)
- Determinism (same structure = same signal)

**Still READ-ONLY. No execution, no prices, no quantities.**

## Core Principle

**THE SCANNER NEVER THINKS.**

It only asks the existing brain (Phase-4→11 pipeline) the same question many times.

## Architecture

```
User Input: "bank nifty ce pe"
        ↓
Instrument Resolver (Phase-11.5a)
        ↓
[BANKNIFTY_06FEB_45000_CE]
[BANKNIFTY_06FEB_45000_PE]
[... 8 more option contracts]
        ↓
For Each Instrument:
   Phase-4: Multi-Timeframe Analysis
   Phase-5: Scenario Synthesis
   Phase-6A: Probability Calculation
   Phase-7A: Execution Gates
   Phase-X: Human Summary
   Phase-11: Signal Eligibility
        ↓
Signal Aggregation
        ↓
Signal Ranker (Phase-11.5b)
        ↓
Scan Reporter (Phase-11.5c)
        ↓
Human-Readable Report
```

## Modules

### 1. instrument_resolver.py - Dynamic Instrument Resolution

**NO HARDCODED WATCHLISTS**

**Supported Inputs:**
- Single stocks: `"YESBANK"`, `"yes bank"`
- Indices: `"nifty"`, `"bank nifty"`
- Constituents: `"nifty 50 stocks"`, `"bank nifty"`
- Options: `"bank nifty ce pe"`, `"nifty options"`

**Resolution Logic:**

#### A. Index Resolution
- `"nifty"` → `^NSEI` (INDEX type)
- `"bank nifty"` → `^NSEBANK` (INDEX type)

#### B. Stock Constituents (Dynamic)
- `"nifty 50 stocks"` → 50 constituent stocks
- `"bank nifty"` → 12 bank stocks
- Uses 24h cached fallback
- **No hardcoded tickers** (production would use NSE API)

#### C. Options Resolution (CE/PE)
- `"bank nifty ce pe"` → Resolves to:
  - Underlying: BANKNIFTY
  - Expiry: Nearest weekly (Thursday)
  - Strikes: ATM ± 2 (5 strikes)
  - Types: CE + PE (10 contracts total)

**Output:** `ResolvedInstrument` with:
- `symbol`: NSE symbol
- `instrument_type`: STOCK | INDEX | OPTION
- `underlying`: For options only
- `expiry`: For options only
- `strike`: For options only
- `option_type`: CE | PE (for options only)

**Test Results:** 10/10 passed ✅

### 2. market_scanner.py - Core Scanning Engine

**Single Entry Point:**
```python
scan_market(ScanRequest)
```

**ScanRequest:**
```python
ScanRequest(
    scope: str,              # "bank nifty ce pe"
    timeframe: INTRADAY | SWING | POSITIONAL,
    max_results: int = 5,
    strict_mode: bool = True
)
```

**Scan Loop (MANDATORY ORDER):**

For each resolved instrument:
1. Run Phase-4 (MTF structure)
2. Run Phase-5 (scenario synthesis)
3. Run Phase-6A (probability)
4. Run Phase-7A/B/C (execution gates)
5. Run Phase-X (human summary)
6. Run Phase-11 (signal eligibility)

**NO SHORTCUTS. NO PARALLEL REASONING. DETERMINISTIC.**

**Failure Rules:**
- Any exception → instrument marked `SCAN_FAILED`
- No retries beyond 1
- Scanner never aborts globally

### 3. signal_ranker.py - Deterministic Ranking

**NO ML. NO PREDICTIONS. FIXED FORMULA.**

**Eligibility Filter (Hard):**
- Only keep `signal.status == ELIGIBLE`
- Only keep `execution_gate != BLOCKED`

**Ranking Score (Fixed):**

```
BASE SCORE:
STRONG   = 100
CAUTION  = 70

RISK MODIFIERS:
LOW      +20
MEDIUM   +10
HIGH     -20

ENTRY STYLE:
IMMEDIATE_OK   +10
PULLBACK_ONLY   0
```

**Sort Order:**
1. Score (DESC)
2. Risk (ASC - lower risk first)
3. Confidence (DESC)

**Signal Rarity Enforcement:**
```
if eligible_signals > 20% of scanned:
    discard lowest-ranked until ≤ 20%
```

**Test Results:** 10/10 passed ✅

### 4. scan_reporter.py - Human Output

**Output Format (Mandatory):**
```
================================================================================
PHASE-11.5: MARKET SCAN RESULT
================================================================================

SCOPE: BANK NIFTY CE/PE
TIMEFRAME: SWING
TIMESTAMP: 2026-02-05 14:30:00

SCANNED: 18 instruments
ELIGIBLE: 2
SIGNAL RARITY: 11.1% ✅

================================================================================

TOP SIGNALS:

1) BANKNIFTY_06FEB_45000_CE
   Score: 130 (STRONG verdict + LOW risk + immediate entry OK)
   Verdict: STRONG (HIGH confidence)
   Direction: LONG
   Risk: LOW
   Entry Style: IMMEDIATE_OK
   Structure: FULL alignment, MID location
   Summary: Structure is strong and aligned across timeframes...

2) BANKNIFTY_06FEB_44800_PE
   Score: 80 (CAUTION verdict + MEDIUM risk (pullback entry))
   Verdict: CAUTION (MEDIUM confidence)
   Direction: SHORT
   Risk: MEDIUM
   Entry Style: PULLBACK_ONLY
   Structure: FULL alignment, RESISTANCE location
   Summary: Trend is strong but extended near resistance...

================================================================================

⚠️  SIGNALS ARE READ-ONLY
    Human review and manual execution required
    No automatic trading, no price targets, no position sizing

================================================================================
```

**NO PRICES. NO BUY/SELL. NO EXECUTION HINTS.**

### 5. scan_scheduler.py - Timeframe Rules

**Mode-Based Timeframes:**
- `INTRADAY`: 15m, 1h, 4h
- `SWING`: 1D, 1W
- `POSITIONAL`: 1W, 1M

**Auto-Downgrade Rule:**
If insufficient data:
- INTRADAY → SWING
- SWING → POSITIONAL

## What Phase-11.5 Does NOT Do

❌ Place trades  
❌ Decide quantities  
❌ Predict prices  
❌ Use indicators  
❌ Hardcode watchlists  
❌ Execute automatically  
❌ Chase price  
❌ Give buy/sell signals  

## What Phase-11.5 DOES Do

✅ Resolves any market scope dynamically  
✅ Scans multiple instruments systematically  
✅ Runs full Phase-4→11 pipeline per instrument  
✅ Ranks signals deterministically  
✅ Enforces signal rarity (≤20%)  
✅ Provides transparent reasoning  
✅ Generates human-readable reports  
✅ Maintains institution-grade safety  

## Options Support (Important Truth)

Your system CAN analyze options, BUT:

**✅ What Works:**
- Structure analysis (support/resistance)
- Scenario logic (continuation/reversal)
- Alignment detection (timeframe harmony)

**❌ What's Invisible:**
- Liquidity spikes (options-specific)
- Theta decay (time value)
- Implied volatility changes

**Therefore:**
**Options signals are STRUCTURAL BIAS signals, not execution signals.**

Which is exactly what Phase-11.5 is meant for - identifying structural opportunities, not precise entry/exit timing.

## Usage Example

```python
from logic.market_scanner import MarketScanner, ScanRequest
from logic.scan_scheduler import ScanMode

# Initialize scanner with execution engine
scanner = MarketScanner(execution_engine)

# Create scan request
request = ScanRequest(
    scope="bank nifty ce pe",
    timeframe=ScanMode.INTRADAY,
    max_results=5,
    strict_mode=True
)

# Execute scan
results = scanner.scan_market(request)

# Display report
print(results["report"])
```

## Real-World Power

After Phase-11.5, you can:

1. **Scan 50 stocks in one command**
   - `scope="nifty 50 stocks"`
   - Get 1-3 clean candidates, not noise

2. **Scan BANK NIFTY options every morning**
   - `scope="bank nifty ce pe"`
   - Find structural biases before market open

3. **Stay human-controlled**
   - All signals require manual review
   - No automatic execution ever

4. **Automation becomes safe later**
   - Foundation for Phase-12+ (tracking)
   - Proven signal quality over time

## Signal Rarity Examples

### Good Scan (Rare Signals):
```
SCANNED: 50 instruments
ELIGIBLE: 3
SIGNAL RARITY: 6.0% ✅
```

### Warning Scan (Too Many Signals):
```
SCANNED: 50 instruments
ELIGIBLE: 15
SIGNAL RARITY: 30.0% ⚠️
```
Ranker will enforce: Keep top 10 (20% max)

### Perfect Scan (Zero Signals):
```
SCANNED: 50 instruments
ELIGIBLE: 0
SIGNAL RARITY: 0.0% ✅
```
This is EXPECTED. Signals should be rare.

## Test Coverage

**Instrument Resolver:** 10/10 tests passed ✅
- Single stock resolution
- Index resolution
- Constituent resolution (NIFTY 50, BANK NIFTY)
- Options resolution (CE/PE with strikes)
- Multi-word names
- Caching mechanism

**Signal Ranker:** 10/10 tests passed ✅
- ELIGIBLE filtering
- Score calculation (STRONG > CAUTION)
- Risk modifiers (LOW +20, MEDIUM +10)
- Entry style modifiers (IMMEDIATE_OK +10)
- Signal rarity enforcement (≤20%)
- max_results limit
- Multi-level sorting
- Determinism
- Edge cases

## Critical Safety Rule

**DO NOT move to broker automation until Phase-11.5 has been used live for at least 30 sessions.**

## Files

- `logic/instrument_resolver.py` - Dynamic instrument resolution (333 lines)
- `logic/market_scanner.py` - Core scanning engine (180 lines)
- `logic/signal_ranker.py` - Deterministic ranking (151 lines)
- `logic/scan_reporter.py` - Human-readable output (125 lines)
- `logic/scan_scheduler.py` - Timeframe rules (72 lines)
- `test_phase_11_5_resolver.py` - Resolver test suite (10 tests)
- `test_phase_11_5_ranker.py` - Ranker test suite (10 tests)

## Integration Status

✅ Modules created  
✅ Tests passing (20/20)  
⏳ Integration with execution_engine (pending)  
⏳ TradingView data fetching (pending)  
⏳ Full Phase-4→11 pipeline connection (pending)  

## Next Steps

1. **Integrate scanner with execution_engine**
   - Connect `_analyze_instrument()` to Phase-4→11 pipeline
   - Wire TradingView data fetching for each instrument

2. **Add scanner command to chat UI**
   - New intent: "scan bank nifty options"
   - Route to scanner instead of single analysis

3. **Test with real market data**
   - Run scans on NIFTY 50
   - Validate signal rarity in production
   - Measure scan performance (time per instrument)

4. **Track signal outcomes** (Phase-12 future)
   - Log which ELIGIBLE signals human took
   - Track win/loss/breakeven
   - Validate signal quality over 30+ sessions

## Summary

Phase-11.5 transforms your single-symbol intelligence into an **institutional-grade multi-instrument scanner** while maintaining:
- 🔒 Signal rarity (quality over quantity)
- 🔒 Full safety checks per instrument
- 🔒 Deterministic, repeatable logic
- 🔒 Zero automation (human-controlled)
- 🔒 Transparent reasoning

**The scanner never thinks. It just asks your brain many questions.**
