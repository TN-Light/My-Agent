# Critic Verification Metadata Implementation

## Overview
Implemented verification intent handling in Critic to support actions with `verify` metadata. This allows verification instructions (e.g., "verify that X is visible") to be handled by the Critic with proper DOM and vision fallback, rather than generating invalid observations.

## Implementation Date
January 28, 2026

## Changes Made

### 1. Action Dataclass Extension ([common/actions.py](common/actions.py))
**Added verify field:**
```python
@dataclass(frozen=True)
class Action:
    # ... existing fields ...
    verify: Optional[dict] = None  # {"type": "text_visible", "value": "..."}
```

**Purpose:** Allows planner to attach verification metadata to actions for Critic to consume.

### 2. Planner Verification Intent Detection ([logic/planner.py](logic/planner.py))
**Location:** `create_plan()` method

**Added:**
- Verification keyword detection: `["verify", "verify_text_visible", "verify that", "check that", "confirm that"]`
- Text extraction from verification instructions
- Action generation with verify metadata
- **Bypasses LLM completely** for verification intents
- **Explicitly forbids observations** for verification

**Log output:** `"Detected verification intent → action with verification metadata (bypassing observations)"`

### 3. Critic Verification Metadata Handler ([logic/critic.py](logic/critic.py))
**Location:** New method `_verify_with_metadata(action: Action)`

**Verification Flow:**
1. Extract `verify["type"]` and `verify["value"]` from action
2. For `type == "text_visible"`:
   - **Primary:** Attempt DOM verification (web context)
   - **Fallback:** Use vision verification if DOM fails and vision enabled
3. Return status: `VERIFIED` / `NOT_VERIFIED` / `UNKNOWN`
4. Log: `"[VERIFY] text_visible → <status>"`

**Routing:** Modified `verify_action()` to check for `action.verify` and route to `_verify_with_metadata()`

**Confidence Scoring:**
- DOM SUCCESS: 1.0 (highest confidence)
- DOM FAIL + VISION VERIFIED: 0.65 (medium, advisory)
- DOM FAIL + VISION NOT_VERIFIED: 0.3 (low, conflicting)
- DOM FAIL + VISION UNKNOWN: 0.4 (low, uncertainty)

**Evidence Collection:**
- DOM: Primary verification source
- VISION: Fallback verification source
- Both sources tracked in ActionResult.evidence

### 4. BrowserHandler Enhancement ([execution/browser_handler.py](execution/browser_handler.py))
**Added method:**
```python
def get_page_text(self) -> Optional[str]:
    """Extract all visible text content from the page."""
    if self.page is None:
        return None
    try:
        return self.page.locator('body').text_content()
    except Exception as e:
        logger.warning(f"Could not get page text: {e}")
        return None
```

**Purpose:** Enables DOM-based text verification for web context.

## Test Coverage

### Test 1: Planner Verification Intent Detection ([test_verification_intent.py](test_verification_intent.py))
- ✅ 4/4 tests passed
- Validates: Action generation, verify metadata structure, zero observations

### Test 2: LLM Bypass for Verification ([test_verification_llm_bypass.py](test_verification_llm_bypass.py))
- ✅ Test passed
- Validates: LLM completely bypassed even when enabled

### Test 3: Critic Verification Metadata ([test_critic_verification_metadata.py](test_critic_verification_metadata.py))
- ✅ 5/5 tests passed
- Scenarios:
  - DOM success (confidence=1.0)
  - DOM fail + vision VERIFIED (confidence=0.65)
  - DOM fail + vision NOT_VERIFIED (confidence=0.3)
  - DOM fail + vision UNKNOWN (confidence=0.4)
  - Normal action without verify metadata

### Test 4: End-to-End Verification Flow ([test_e2e_verification_flow.py](test_e2e_verification_flow.py))
- ✅ All scenarios passed
- Validates: Complete flow from planner → action → critic → result
- Tests all three verification outcomes with proper confidence scoring

## Design Principles

### 1. Primary Authority Pattern
- DOM/UIA/FILE verification is PRIMARY
- Vision verification is ADVISORY fallback only
- Vision CANNOT override primary verification
- Vision provides additional evidence when primary fails

### 2. Separation of Concerns
- **Observer:** Read-only operations (file reads, DOM queries)
- **Critic:** Verification operations (state comparison, text visibility)
- Verification must NOT generate observations

### 3. LLM Bypass
- Verification intents detected BEFORE LLM routing
- Deterministic handling ensures consistent behavior
- Prevents invalid plans from LLM

### 4. Confidence Scoring (Phase-3C)
- Confidence does NOT affect execution flow
- Metadata only for logging and diagnostics
- Based on evidence source and agreement

### 5. Explicit Logging
- All verification operations logged with `[VERIFY]` prefix
- Status clearly indicated: VERIFIED / NOT_VERIFIED / UNKNOWN
- Confidence scores included in logs

## Integration Points

### Controller Integration
When controller receives action with `action.verify`:
1. Execute action normally (if action_type requires it)
2. Pass action to `critic.verify_action(action)`
3. Critic detects verify metadata and routes to `_verify_with_metadata()`
4. Returns ActionResult with verification status

### Execution Flow
```
User: "verify that Welcome is visible"
  ↓
Planner: Detects verification intent
  ↓
Creates: Action(verify={"type": "text_visible", "value": "Welcome"})
  ↓
Controller: Passes to Critic
  ↓
Critic: verify_action() → _verify_with_metadata()
  ↓
Attempts: DOM verification first
  ↓
Fallback: Vision verification (if DOM fails)
  ↓
Returns: ActionResult(success, confidence, evidence)
```

## Supported Verification Types

### Current
- `text_visible`: Verify text is visible on screen/page

### Future Extensions
- `element_present`: Verify UI element exists
- `window_open`: Verify window/application is open
- `file_exists`: Verify file exists with specific content
- `url_matches`: Verify browser at specific URL

## Log Examples

### DOM Success
```
[VERIFY] text_visible → VERIFIED (DOM, confidence=1.00)
```

### Vision Fallback
```
[VERIFY] text_visible → NOT_VERIFIED (DOM)
[VERIFY] Attempting vision verification for: 'Welcome'
[VERIFY] text_visible → VERIFIED (VISION, confidence=0.65)
```

### Complete Failure
```
[VERIFY] text_visible → NOT_VERIFIED (DOM)
[VERIFY] Attempting vision verification for: 'Error'
[VERIFY] text_visible → NOT_VERIFIED (VISION, confidence=0.30)
```

## Key Benefits

1. **Correct Routing:** Verification handled by Critic (not Observer)
2. **LLM Bypass:** Deterministic verification intent handling
3. **Evidence-Based:** Multi-source verification with confidence scoring
4. **Fallback Support:** Vision provides advisory verification when primary fails
5. **Clean Logs:** Explicit verification status in logs
6. **Extensible:** Easy to add new verification types

## Notes

- Verification actions do NOT override primary action results
- Verification is an assessment, not a corrective action
- Confidence scoring follows Phase-3C specifications
- All verification tests pass with 100% success rate
- No errors detected in codebase
