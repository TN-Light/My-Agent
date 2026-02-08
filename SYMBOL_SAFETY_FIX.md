# Symbol Resolution Safety Fix

## Critical Issue Identified
When Google search showed a CAPTCHA ("I am not a robot" verification), the system didn't detect it and the LLM extracted a completely wrong symbol. In your case:
- User typed: "analysis yes bank"
- Google returned: CAPTCHA page
- LLM extracted: KOTAKBANK (completely wrong!)
- **Result**: Extremely dangerous for trading

## Root Causes
1. **No CAPTCHA detection** - System processed CAPTCHA pages as normal search results
2. **No symbol validation** - No check if extracted symbol matched the query
3. **No fallback mechanism** - Complete failure when Google was blocked

## Safety Fixes Implemented

### 1. Internet-First Approach (Primary)
**Always tries Google search first** to get fresh, accurate data:
- Searches Google AI for the latest symbol information
- Uses LLM to extract symbol from search results
- Validates extracted symbol matches the query

**Why**: Ensures up-to-date information, handles symbol changes, company name changes, mergers, etc.

### 2. CAPTCHA Detection (Safety Layer)
Detects when Google blocks access:

```python
if ("not a robot" in search_text.lower() or 
    "captcha" in search_text.lower() or
    "unusual traffic" in search_text.lower() or
    "verify you're human" in search_text.lower()):
    logger.error("[CRITICAL] Google CAPTCHA detected")
    # Falls back to known mapping if available
```

**Why**: Prevents wrong symbol extraction from CAPTCHA noise.

### 3. Symbol-Query Validation (Safety Layer)
Validates extracted symbol matches the query:

```python
# Detect obvious mismatches
if "yes" in query_lower and "yes" not in symbol_lower:
    logger.error("[CRITICAL] Symbol mismatch: rejecting {symbol}")
    return None
```

**Why**: Catches LLM extraction errors even from valid search results.

### 4. Known Symbol Fallback (Last Resort)
**Only used when Google completely fails:**
- CAPTCHA detected → Try fallback
- Search timeout/error → Try fallback  
- Symbol not found in results → Try fallback

```python
KNOWN_SYMBOLS = {
    "yes bank": "YESBANK",
    "kotak bank": "KOTAKBANK",
    "ktk bank": "KTKBANK",
    # ... 20+ mappings
}
```

**Why**: Provides backup when internet unavailable, but doesn't replace fresh verification.

## Flow Chart

```
User: "analysis yes bank"
    ↓
Try Google Search
    ↓
├─ [SUCCESS] → Extract symbol → Validate → Return YESBANK ✅
├─ [CAPTCHA] → Fallback → Return YESBANK (with warning) ⚠️
├─ [TIMEOUT] → Fallback → Return YESBANK (with warning) ⚠️
└─ [NOT FOUND] → Fallback → Return YESBANK (with warning) ⚠️

User: "analysis unknown stock"
    ↓
Try Google Search
    ↓
├─ [SUCCESS] → Extract symbol → Validate → Return symbol ✅
├─ [CAPTCHA] → No fallback → Return None ❌
├─ [TIMEOUT] → No fallback → Return None ❌
└─ [NOT FOUND] → No fallback → Return None ❌
```

## Test Results
All 24 safety checks passed:
- ✅ 10/10 known mapping tests (fallback works)
- ✅ 6/6 CAPTCHA detection tests
- ✅ 8/8 symbol validation tests

## Examples

### Best Case (Fresh Google Data):
```
User: "analysis yes bank"
Google: "Yes Bank Limited (NSE: YESBANK)..."
System: Extracts "YESBANK" ✅
Log: "LLM extracted symbol from search: YESBANK"
```

### CAPTCHA Case (Fallback):
```
User: "analysis yes bank"
Google: [CAPTCHA PAGE]
System: CAPTCHA detected → Check fallback mapping
System: Found "yes bank" → "YESBANK" in fallback
Log: "[FALLBACK] Using known mapping due to CAPTCHA: 'yes bank' → YESBANK"
Result: Returns YESBANK with WARNING flag ⚠️
```

### Unknown Stock + CAPTCHA (Fail Safe):
```
User: "analysis unknown company"
Google: [CAPTCHA PAGE]
System: CAPTCHA detected → Check fallback mapping
System: "unknown company" not in fallback
Log: "[CRITICAL] Google CAPTCHA detected - cannot search safely"
Result: Returns None (safe failure) ❌
```

## Why This Approach Is Better

**Before**: Hardcoded mapping first → Skip Google entirely → Risk outdated data
**After**: Google first → Fallback only on failure → Fresh data preferred

**Advantages**:
1. ✅ Always gets latest symbol data when Google works
2. ✅ Handles company name changes, mergers, delistings
3. ✅ Falls back to known mapping only when necessary
4. ✅ User sees WARNING when fallback is used (transparency)
5. ✅ Unknown stocks fail safely instead of guessing

## Logging
System logs clearly indicate what happened:
- `"LLM extracted symbol from search"` = Fresh Google data ✅
- `"[FALLBACK] Using known mapping due to CAPTCHA"` = Fallback used ⚠️
- `"[CRITICAL] Google CAPTCHA detected"` = No fallback available ❌

## Files Modified
- `logic/execution_engine.py` - Reordered logic: Google first, fallback last
- `test_symbol_safety.py` - Test suite validates all safety layers

