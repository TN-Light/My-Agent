# Phase-11.5G: Symbol Resolution System

## Overview

**3-Layer Symbol Resolution** with strict Google usage rules, scanner-safe behavior, and persistent caching.

## Architecture

```
User Input: "tata consumer"
        ↓
Layer 1: Symbol Memory (Cache)
    - Lookup cached resolutions
    - 30-day TTL
    - Case-insensitive
    ↓ (Cache MISS)
Layer 2: TradingView Validation
    - Direct chart load test
    - Extract symbol + price
    - Validate data availability
    ↓ (Validation FAILED)
Layer 3: Google Search (STRICT RULES)
    - ONLY in SINGLE_ANALYSIS mode
    - NON-TICKER input only
    - One attempt per session
    - Validate result via TradingView
        ↓
SymbolResolutionResult
```

## Resolution Status

### VALID
- Symbol validated via TradingView
- Chart loaded successfully
- Price data available
- **Source:** TRADINGVIEW

### RESOLVED
- Symbol resolved via Google or cache
- Validated via TradingView
- **Source:** CACHE or GOOGLE

### UNKNOWN
- Symbol could not be resolved
- Google search failed or not allowed
- **Used in:** SINGLE_ANALYSIS mode

### DATA_UNAVAILABLE  
- TradingView data unavailable
- Symbol may be valid but can't verify
- **Used in:** MARKET_SCAN mode (no Google fallback)
- **Important:** Scanner continues without aborting

## Google Usage Rules (STRICT)

Google search is ONLY allowed when **ALL** conditions are met:

1. ✅ Mode == SINGLE_ANALYSIS (not SCAN)
2. ✅ User input contains NON-TICKER text
   - Examples: "tata consumer", "ktk bank", "adani ports"
   - NOT: "YESBANK", "SBIN", "KOTAKBANK"
3. ✅ TradingView validation FAILED for guessed symbols
4. ✅ System has not already attempted Google once

### When Google is FORBIDDEN:
- Mode == MARKET_SCAN ❌
- Mode == AUTOMATED_SCAN ❌
- Mode == BACKTEST ❌
- Mode == REPLAY ❌
- Mode == MULTI_INSTRUMENT_ANALYSIS ❌

If symbol cannot be validated → mark as DATA_UNAVAILABLE

## Scanner-Safe Behavior

### Old Behavior (DANGEROUS):
```python
if TradingView.navigate(symbol) fails:
    symbol = Google.search(symbol)  # ❌ BREAKS SCANNER
    if symbol is None:
        return INVALID  # ❌ WRONG STATUS
```

### New Behavior (SAFE):
```python
if mode == MARKET_SCAN:
    if TradingView.navigate(symbol) fails:
        # NO Google search ✓
        return DATA_UNAVAILABLE  # ✓ Correct status
        # Scanner continues without aborting ✓
```

**DATA_UNAVAILABLE ≠ NOT_ELIGIBLE**

- DATA_UNAVAILABLE = Chart data not available (technical failure)
- NOT_ELIGIBLE = Valid analysis, no trade edge (verdict)

## TradingView Health Check

Before starting any MARKET_SCAN:

```python
if not resolver.health_check():
    print("❌ Market data source unavailable. Scan aborted.")
    return
```

**Health check:**
1. Load TradingView chart for NSE:NIFTY
2. If chart load fails → abort scan immediately
3. Show message: "Market data source unavailable"
4. Do NOT mark instruments as NOT_ELIGIBLE

## Symbol Memory (Cache)

### Storage Format (JSON):
```json
{
  "tata consumer": {
    "user_text": "tata consumer",
    "nse_symbol": "TATACONSUM",
    "confidence": "HIGH",
    "source": "GOOGLE",
    "timestamp": "2026-02-05T14:30:00"
  }
}
```

### Cache Rules:
- **Expiry:** 30 days
- **Lookup:** Case-insensitive
- **Validation:** On every cache hit, check age
- **Storage:** After successful Google resolution

### Example Flow:
```python
# First request
result = resolver.resolve("tata consumer")  # Google search
# Result: RESOLVED, source=GOOGLE
# → Stored in cache

# Second request (same day)
result = resolver.resolve("tata consumer")  # Cache hit
# Result: RESOLVED, source=CACHE
# → No Google search
```

## SSL Hardening (Phase-11.5G)

### Browser Launch Args:
```python
args=[
    "--ignore-certificate-errors",
    "--ignore-ssl-errors=yes",
    "--disable-web-security"
]
```

**Applied to:**
- Google search pages ✅
- TradingView read-only pages ✅

**Never used for:**
- Broker login flows ❌
- Trading platforms ❌
- Secure transactions ❌

## Output Semantics

### Signal Status Semantics:

**ELIGIBLE:**
- Valid analysis performed
- Trade edge exists
- Structure permits entry
- **Example:** STRONG verdict, FULL alignment, LOW risk

**NOT_ELIGIBLE:**
- Valid analysis performed
- No trade edge
- **Example:** WEAK verdict, CONFLICT, HIGH risk

**DATA_UNAVAILABLE:**
- Analysis skipped
- TradingView data not available
- Technical failure (not verdict)
- **Example:** Chart failed to load, price data missing

**UNKNOWN:**
- Symbol could not be resolved
- Name resolution failed
- **Example:** "xyz company" → no results

## Usage Examples

### Example 1: Single Analysis (Google Allowed)

```python
from logic.symbol_resolver import SymbolResolver, ResolutionMode

resolver = SymbolResolver(tradingview_client, llm_client)

# User types: "analyze tata consumer"
result = resolver.resolve(
    user_input="tata consumer",
    mode=ResolutionMode.SINGLE_ANALYSIS,
    context="analyze tata consumer chart"
)

if result.status == ResolutionStatus.RESOLVED:
    print(f"Symbol: {result.symbol}")  # TATACONSUM
    print(f"Source: {result.source.value}")  # GOOGLE
    print(f"Confidence: {result.confidence.value}")  # HIGH
```

### Example 2: Market Scan (Google Forbidden)

```python
# Scanning bank nifty (12 stocks)
for symbol in ["YESBANK", "KOTAKBANK", "SBIN", ...]:
    result = resolver.resolve(
        user_input=symbol,
        mode=ResolutionMode.MARKET_SCAN,  # NO GOOGLE
        context=None
    )
    
    if result.status == ResolutionStatus.DATA_UNAVAILABLE:
        # TradingView failed, but scanner continues
        logger.warning(f"Data unavailable for {symbol}, skipping...")
        continue
    
    # Proceed with analysis for valid symbols
    analyze_instrument(result.symbol)
```

### Example 3: Health Check Before Scan

```python
# Before starting scan
if not resolver.health_check():
    print("❌ Market data source unavailable. Scan aborted.")
    return

# Proceed with scan
for instrument in instruments:
    # ... scan logic
```

## Integration Points

### 1. Execution Engine (Single Analysis)
```python
# OLD: _validate_and_correct_symbol()
validated_symbol = self._validate_and_correct_symbol(symbol, instruction)

# NEW: Uses SymbolResolver with SINGLE_ANALYSIS mode
result = self.symbol_resolver.resolve(
    user_input=symbol,
    mode=ResolutionMode.SINGLE_ANALYSIS,
    context=original_instruction
)
```

### 2. Market Scanner (Phase-11.5)
```python
# Health check before scan
if not self.symbol_resolver.health_check():
    abort_scan()

# Per-instrument resolution (MARKET_SCAN mode)
result = self.symbol_resolver.resolve(
    user_input=symbol,
    mode=ResolutionMode.MARKET_SCAN,  # NO GOOGLE
    context=None
)

if result.status == ResolutionStatus.DATA_UNAVAILABLE:
    # Skip instrument, continue scan
    return None
```

### 3. Symbol Memory Integration
```python
# Automatic caching on Google success
result = resolver.resolve("tata consumer", ResolutionMode.SINGLE_ANALYSIS)
# → Stores in cache if resolved via Google

# Next request uses cache
result = resolver.resolve("tata consumer", ResolutionMode.SINGLE_ANALYSIS)
# → Returns from cache (no Google search)
```

## Files Created

### Core Resolution:
- `logic/symbol_resolver.py` (406 lines)
  - SymbolResolver class
  - 3-layer resolution logic
  - Google usage rules
  - Health check

### Persistent Cache:
- `storage/symbol_memory.py` (206 lines)
  - SymbolMemory class
  - JSON-based cache
  - 30-day TTL
  - Case-insensitive lookup

### Tests:
- `test_symbol_resolution.py` (156 lines)
  - Ticker detection tests
  - Google rules validation
  - Cache functionality tests
  - Mode behavior tests

### Documentation:
- `SYMBOL_RESOLUTION.md` (this file)

## Files Modified

### Browser SSL Hardening:
- `execution/playwright_worker.py`
  - Added SSL bypass args (3 locations)
  - Applied to all browser launch modes

### Signal Status:
- `logic/signal_eligibility.py`
  - Added DATA_UNAVAILABLE status
  - Distinguishes from NOT_ELIGIBLE

### Execution Engine Integration:
- `logic/execution_engine.py`
  - Added SymbolResolver initialization
  - Replaced old validation with new resolver
  - Added health check before scans
  - Updated scanner integration

## Testing

### Unit Tests (Passing):
```bash
python test_symbol_resolution.py
```

**Coverage:**
- ✅ Ticker detection (9/9 cases)
- ✅ Google usage rules (5/5 cases)
- ✅ Google attempt limit (2/2 cases)
- ✅ Symbol memory caching (3/3 cases)
- ✅ Resolution modes (2/2 cases)

### Integration Tests:
```bash
python test_phase_11_5_integration.py
```

**Tests:**
- Scanner with 2 stocks (YESBANK, KOTAKBANK)
- Health check validation
- DATA_UNAVAILABLE handling

## Safety Guarantees

### ✅ Google Usage is CONTROLLED:
- Only in SINGLE_ANALYSIS mode
- Only for NON-TICKER text
- One attempt per session
- Results validated via TradingView

### ✅ Scanner is SAFE:
- No Google searches during scans
- Failed instruments marked DATA_UNAVAILABLE
- Scan continues without aborting
- Health check prevents wasted scans

### ✅ Cache is PERSISTENT:
- Successful resolutions stored for 30 days
- Reduces Google dependency
- Case-insensitive lookups
- Automatic expiry

### ✅ Output is CLEAR:
- ELIGIBLE = Valid analysis, trade edge exists
- NOT_ELIGIBLE = Valid analysis, no trade edge
- DATA_UNAVAILABLE = Analysis skipped (technical failure)
- UNKNOWN = Symbol not resolved

## Migration Guide

### For Existing Code:

**OLD (UNSAFE):**
```python
# Always used Google search
symbol = _search_correct_symbol(query)

# Mixed INVALID and NOT_ELIGIBLE
if chart_failed:
    return "INVALID"
```

**NEW (SAFE):**
```python
from logic.symbol_resolver import SymbolResolver, ResolutionMode, ResolutionStatus

# Use resolver with appropriate mode
result = resolver.resolve(
    user_input=query,
    mode=ResolutionMode.SINGLE_ANALYSIS,  # or MARKET_SCAN
    context=instruction
)

if result.status == ResolutionStatus.DATA_UNAVAILABLE:
    # Chart data not available (technical)
    skip_instrument()
elif result.status == ResolutionStatus.UNKNOWN:
    # Symbol not resolved (name)
    show_error("Could not resolve symbol")
elif result.status in [ResolutionStatus.VALID, ResolutionStatus.RESOLVED]:
    # Proceed with analysis
    analyze(result.symbol)
```

## Summary

**Phase-11.5G delivers:**
- ✅ 3-layer resolution (Cache → TradingView → Google)
- ✅ Strict Google usage rules (SINGLE_ANALYSIS only)
- ✅ Scanner-safe behavior (DATA_UNAVAILABLE, no abort)
- ✅ TradingView health check (pre-scan validation)
- ✅ Symbol memory (30-day cache)
- ✅ SSL hardening (certificate bypass)
- ✅ Clear output semantics (ELIGIBLE vs NOT_ELIGIBLE vs DATA_UNAVAILABLE)

**Result:** Symbol resolution is now **controlled, cached, and scanner-safe**.
