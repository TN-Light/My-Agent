# BASELINE DOCUMENTATION
**Version**: Phase-3D Complete  
**Date**: January 28, 2026  
**Status**: LOCKED - No modifications without explicit approval

---

## 1. ACTION vs OBSERVATION vs VERIFICATION SEPARATION

### 1.1 Actions
**Definition**: State-changing operations that modify the system.

**Properties**:
- Subject to policy validation (Phase 2: POLICY CHECK)
- Subject to verification (Phase 4: VERIFY)
- May be retried on transient failures (max 2 attempts)
- Logged to action_history database
- Examples: `launch_app`, `type_text`, `close_app`

**Execution Flow**:
```
PHASE 1: PLAN
PHASE 2: POLICY CHECK  ← Actions only
PHASE 3: ACT
PHASE 4: VERIFY        ← Actions only
PHASE 5: COMMIT
```

### 1.2 Observations
**Definition**: Read-only queries that gather information without side effects.

**Properties**:
- **BYPASS policy validation** (read-only, inherently safe)
- **NO verification** (nothing to verify for reads)
- **NO retries** (deterministic operations)
- Logged to observation_log database (separate from actions)
- Examples: File reads, window queries, page text extraction

**Execution Flow**:
```
PHASE 1: PLAN
PHASE 2: OBSERVE  ← Direct execution, no policy/verify
PHASE 3: COMMIT
```

**Critical Rule**: File read operations (`launch_app` with `context='file'`) are **OBSERVATIONS**, not actions. This is enforced in Controller.

### 1.3 Verifications
**Definition**: Actions with explicit verification goals (checking that something is true).

**Properties**:
- Marked with `verify` metadata: `{"type": "text_visible", "value": "..."}`
- Subject to policy validation
- Execute normally, then verify with metadata
- **NEVER retry** (verification failures are logical, not transient)
- Set `reason='verification_failed'` on failure
- Examples: "Verify login button is visible", "Verify text appears"

**Execution Flow**:
```
PHASE 1: PLAN          (detects verification intent)
PHASE 2: POLICY CHECK
PHASE 3: ACT
PHASE 4: VERIFY        (uses verify metadata)
[NO RETRY ON FAILURE]  ← Terminal failure
```

---

## 2. RETRY RULES

### 2.1 What RETRIES (Max 2 Attempts)
- **Regular actions** that fail verification due to **transient errors**
- Examples:
  - Window closed unexpectedly
  - Element not yet loaded
  - Transient network issues

**Retry Logic**:
1. First attempt fails verification
2. Check: NOT a verification action (no `verify` metadata)
3. Check: `reason != 'verification_failed'`
4. Retry SAME action (no re-planning)
5. If second attempt fails: abort with `reason='retry_exhausted'`

### 2.2 What NEVER RETRIES
1. **Verification actions** (actions with `verify` metadata)
   - Reason: Verification failures are logical, not transient
   - Detection: `action.verify is not None`
   
2. **Actions with `reason='verification_failed'`**
   - Set by Critic when verification check fails
   - Terminal failure marker
   
3. **Observations**
   - Deterministic operations (file reads, queries)
   - No verification phase, so no retry logic applies

4. **Policy denials**
   - Set `reason='policy_denied'`
   - Security violation, not transient

### 2.3 Retry Detection Logic (main.py)
```python
# Check 1: Is this a verification failure by reason?
if verify_result.reason == 'verification_failed':
    return False  # Terminal

# Check 2: Is this a verification action?
if action.verify:
    return False  # Terminal

# Check 3: First or second attempt?
if attempt == 1:
    return self._execute_single_action(action, action_index, attempt=2)
else:
    self.last_failure_reason = 'retry_exhausted'
    return False
```

---

## 3. FAILURE REASONS AND SEMANTICS

### 3.1 Reason Field
- Added to `ActionResult` dataclass
- Type: `Optional[str]`
- Purpose: Distinguish terminal vs retryable failures

### 3.2 Defined Reasons

#### `'verification_failed'` (TERMINAL)
- **Meaning**: Verification check explicitly failed
- **Set by**: Critic when verification metadata check fails
- **Retry**: NEVER
- **Log message**: "Action {i} failed due to verification failure"
- **Examples**:
  - DOM check: text not found
  - Vision check: NOT_VERIFIED or UNKNOWN
  - File check: file not found

#### `'retry_exhausted'` (TERMINAL)
- **Meaning**: Action retried and failed both times
- **Set by**: Main.py after second attempt fails
- **Retry**: Already exhausted
- **Log message**: "Action {i} failed after retry"
- **Examples**:
  - Window closed on both attempts
  - Element not found after 2 tries

#### `'policy_denied'` (TERMINAL)
- **Meaning**: Policy engine rejected action
- **Set by**: Policy engine on whitelist violation
- **Retry**: NEVER (security invariant)
- **Log message**: "Policy denied action"

#### `None` (SUCCESS or RETRYABLE)
- **Meaning**: No specific failure reason
- **Set by**: Default value
- **Retry**: Eligible for retry (if attempt == 1)

### 3.3 Reason Tracking
- `Agent.last_failure_reason`: Instance variable tracking most recent failure
- Updated on every failure path
- Used for plan abortion log messages

---

## 4. CONFIDENCE SCORING

### 4.1 Purpose
**Metadata only** - quantifies verification reliability for diagnostics.

**DOES NOT**:
- Affect control flow
- Trigger retries
- Influence planning
- Change success/failure status

**DOES**:
- Provide post-mortem insight
- Aid debugging
- Quantify verification quality

### 4.2 Scoring Rules

| Scenario | Confidence | Meaning |
|----------|-----------|---------|
| Pure DOM/UIA/FILE success | 1.0 | Highest - authoritative source confirmed |
| DOM/UIA fail + Vision VERIFIED | 0.65 | Medium - advisory vision confirms |
| DOM/UIA fail + Vision UNKNOWN | 0.4 | Low - primary failed, vision uncertain |
| DOM/UIA fail + Vision NOT_VERIFIED | 0.3 | Low - conflicting evidence |
| DOM/UIA fail, no vision | 0.2 | Low - primary failed, no fallback |
| Vision only VERIFIED | 0.5 | Medium-low - no authoritative source |
| Vision only NOT_VERIFIED | 0.2 | Low - vision-only negative |
| No evidence | 0.0 | None - no verification performed |

### 4.3 Confidence Computation
- Implemented in `Critic._compute_confidence(evidence: list)`
- Aggregates `VerificationEvidence` objects
- Returns float [0.0, 1.0]
- Logged with every verification result

### 4.4 Limits
- **Not a probability**: Not calibrated against ground truth
- **Not comparable across contexts**: DOM vs Vision scores use different scales
- **Advisory only**: Human interpretation required
- **No thresholds**: No automatic actions triggered by confidence values

---

## 5. EVIDENCE COLLECTION GUARANTEES

### 5.1 What is Collected
Every verification produces structured evidence:

```json
{
    "source": "DOM|VISION|UIA|FILE",
    "checked_text": "what was verified",
    "sample": "text excerpt or context (optional)",
    "confidence": 0.0-1.0
}
```

### 5.2 Collection Points

#### DOM Verification (Web)
- **Source**: `"DOM"`
- **checked_text**: Search term or URL
- **sample**: Text excerpt around found text (200 chars)
- **Collection**: `_verify_with_metadata()`, web action verification

#### Vision Verification (VLM)
- **Source**: `"VISION"`
- **checked_text**: Text to verify
- **sample**: `None` (vision doesn't extract text)
- **Collection**: Vision fallback in `_verify_with_metadata()`

#### UIA Verification (Desktop)
- **Source**: `"UIA"`
- **checked_text**: Window title or typed text
- **sample**: Window name
- **Collection**: `verify_launch_app()`, `verify_type_text()`

#### File Verification
- **Source**: `"FILE"`
- **checked_text**: File path
- **sample**: `None` (don't include file content)
- **Collection**: `_verify_file_action()`

### 5.3 Storage Guarantees

1. **Attached to ActionResult**:
   - Field: `verification_evidence: Optional[dict]`
   - Available in-memory during execution

2. **Logged to Console**:
   - Format: `[EVIDENCE] Source: {source}, Checked: '{text}', Confidence: {conf}`
   - Logged after every verification (success or failure)

3. **Persisted to Database**:
   - Table: `action_history`
   - Column: `verification_evidence` (TEXT, JSON-serialized)
   - Query: `SELECT verification_evidence FROM action_history`

### 5.4 Evidence vs VerificationEvidence

**VerificationEvidence** (list):
- Legacy field: `ActionResult.evidence: list[VerificationEvidence]`
- Purpose: Multi-source tracking (DOM + Vision)
- Used for confidence computation

**verification_evidence** (dict):
- New field: `ActionResult.verification_evidence: Optional[dict]`
- Purpose: Structured post-mortem evidence
- Single source (final verification authority)

### 5.5 Evidence Invariants
- Evidence NEVER affects control flow
- Evidence NEVER triggers retries
- Evidence NEVER influences planning
- Evidence is descriptive only

---

## 6. AUTHORITY HIERARCHY

### 6.1 Verification Authority Levels

```
PRIMARY AUTHORITY (1.0 confidence)
├── DOM (Web browser state)
├── UIA (Desktop accessibility tree)
└── FILE (File system state)

ADVISORY AUTHORITY (0.5-0.7 confidence)
└── Vision (VLM visual inspection)
```

### 6.2 Authority Rules

#### Rule 1: Primary Authority is Final
If DOM/UIA/FILE verification **succeeds**:
- Result: SUCCESS
- Confidence: 1.0
- Vision is NOT consulted

If DOM/UIA/FILE verification **fails**:
- Result: FAILURE (primary authority failed)
- Confidence: 0.2 (without vision) or 0.3-0.65 (with vision)
- Vision may be consulted for advisory context

#### Rule 2: Vision is Advisory Only
Vision results **NEVER override** primary authority:
- Vision VERIFIED + DOM FAIL = FAIL (confidence 0.65)
- Vision NOT_VERIFIED + DOM FAIL = FAIL (confidence 0.3)
- Vision is context for post-mortem, not authoritative

#### Rule 3: Vision as Fallback (Optional)
Vision is consulted when:
1. Primary authority fails
2. VisionClient is configured
3. ScreenCapture is available

Vision provides:
- Additional diagnostic context
- Confidence adjustment
- Evidence for debugging

**Vision does NOT**:
- Change success/failure outcome
- Trigger retries
- Override primary authority

### 6.3 Multi-Source Verification Flow

```
Action requires verification
    ↓
Try PRIMARY (DOM/UIA/FILE)
    ↓
SUCCESS? → Return SUCCESS (1.0 confidence)
    ↓ NO
FAIL → Primary authority failed
    ↓
Vision available?
    ↓ YES
Try VISION (advisory)
    ↓
Collect vision result
    ↓
Adjust confidence (0.3-0.65)
    ↓
Return FAILURE with vision context
```

### 6.4 Authority by Context

| Context | Primary Authority | Vision Role |
|---------|------------------|-------------|
| Desktop | UIA (Accessibility Tree) | Advisory fallback |
| Web | DOM (Browser state) | Advisory fallback |
| File | FILE (File system) | Not applicable |

### 6.5 Authority Invariants
1. Primary authority result is **final** for success/failure
2. Vision results are **advisory** and **contextual** only
3. Confidence scoring reflects authority hierarchy
4. No automatic promotion of vision to primary authority

---

## 7. EXECUTION PHASES

### 7.1 Action Execution (5 Phases)
```
PHASE 1: PLAN
- Planner generates action
- Detects verification intents
- Detects file read intents (observation)

PHASE 2: POLICY CHECK
- Validate action against whitelist
- TERMINAL if denied (reason='policy_denied')

PHASE 3: ACT
- Controller executes action
- State change occurs

PHASE 4: VERIFY
- Critic verifies outcome
- Multi-source verification (primary + vision)
- Collect evidence
- TERMINAL if verification_failed

PHASE 5: COMMIT
- Log to action_history database
- Store evidence
```

### 7.2 Observation Execution (2 Phases)
```
PHASE 1: PLAN
- Planner detects observation intent
- Bypasses LLM (deterministic)

PHASE 2: OBSERVE
- Observer executes query
- No policy check (read-only)
- No verification (nothing to verify)

PHASE 3: COMMIT
- Log to observation_log database
```

---

## 8. DATABASE SCHEMA

### 8.1 action_history Table
```sql
CREATE TABLE action_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target TEXT,
    text_content TEXT,
    coordinates TEXT,
    success INTEGER NOT NULL,
    message TEXT,
    error TEXT,
    verification_evidence TEXT  -- JSON-serialized dict
);
```

**Evidence Column**:
- Type: TEXT
- Format: JSON string
- Example: `{"source": "DOM", "checked_text": "Login", "sample": "...Login button...", "confidence": 1.0}`

### 8.2 observation_log Table
```sql
CREATE TABLE observation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    query_type TEXT NOT NULL,
    target TEXT,
    result TEXT,
    success INTEGER NOT NULL
);
```

---

## 9. LOGGING CONVENTIONS

### 9.1 Windows Compatibility
- **Encoding**: ASCII-only (cp1252 compatible)
- **No unicode characters**: All replaced with ASCII equivalents
- **Symbols**:
  - `[OK]` instead of ✓
  - `[FAIL]` instead of ✗
  - `->` instead of →

### 9.2 Log Message Standards

#### Phase Logs
- `PHASE 1: PLAN`
- `PHASE 2: POLICY CHECK`
- `PHASE 3: ACT`
- `PHASE 4: VERIFY`
- `PHASE 5: COMMIT`

#### Status Logs
- `[OK] APPROVED: {action}`
- `[FAIL] DENIED: {reason}`
- `[OK] EXECUTED: {message}`
- `[FAIL] VERIFICATION FAILED: {error}`
- `[OK] VERIFIED: {message}`
- `[OK] COMMITTED to action history`

#### Evidence Logs
- `[EVIDENCE] Source: {source}, Checked: '{text}', Confidence: {conf}`
- `[EVIDENCE] Sample: {sample[:100]}...`

#### Failure Logs
- `Action {i} failed due to verification failure. Aborting plan.`
- `Action {i} failed after retry. Aborting plan.`
- `Verification failed. This is a terminal failure (no retry allowed).`

---

## 10. CONFIGURATION

### 10.1 Agent Config (agent_config.yaml)
```yaml
planner:
  use_llm: true  # Enable LLM planning (bypass for observations)

controller:
  execution_delay: 0.5  # Delay between actions (seconds)

critic:
  vision_enabled: false  # Enable vision fallback verification

policy:
  whitelist_file: "config/policy.yaml"
```

### 10.2 Policy Config (policy.yaml)
```yaml
whitelist:
  applications:
    - notepad.exe
    - calc.exe
  
  urls:
    - "https://example.com"
  
  files:
    - "C:\\Users\\*\\Documents\\*.txt"
```

---

## 11. KEY INVARIANTS (See INVARIANTS.md)

1. Observations NEVER require policy validation
2. Observations NEVER require verification
3. Verification failures NEVER retry
4. Vision results NEVER override primary authority
5. Confidence scores NEVER affect control flow
6. Evidence collection NEVER affects execution
7. File reads are OBSERVATIONS, not actions
8. Policy denials are TERMINAL (no retry)
9. Retry exhaustion is TERMINAL (no third attempt)
10. All logs are ASCII-only (Windows cp1252)

---

## 12. TEST COVERAGE

### Core Tests (All Passing)
- ✅ `test_verification_terminal.py` - Verification failures marked terminal
- ✅ `test_verification_no_retry.py` - Retry logic correct
- ✅ `test_failure_reason_logs.py` - Log messages accurate
- ✅ `test_evidence_collection.py` - Evidence collected and stored
- ✅ `test_ascii_logging.py` - Windows cp1252 compatible

### Test Guarantees
1. Verification actions don't retry
2. Regular actions retry once
3. Evidence collected on all paths
4. Logs distinguish terminal vs exhausted failures
5. No unicode encoding errors

---

## 13. BASELINE STATUS

**Version**: Phase-3D Complete  
**Date**: January 28, 2026  
**Status**: ✅ LOCKED

**What Works**:
- ✅ Action/Observation/Verification separation
- ✅ Retry logic (regular vs verification)
- ✅ Failure reason tracking
- ✅ Confidence scoring
- ✅ Evidence collection and storage
- ✅ Authority hierarchy (primary > vision)
- ✅ Windows-compatible logging
- ✅ Complete test coverage

**What is NOT Included** (Future Phases):
- ❌ Multi-step plan optimization
- ❌ Learning from failures
- ❌ Dynamic confidence thresholds
- ❌ Automatic evidence analysis
- ❌ Cross-session memory
- ❌ Coordinate-based clicking (Phase-2B)

**Modification Policy**:
- No changes without explicit approval
- All modifications require test updates
- Backward compatibility required
- Document all deviations from baseline

---

**END OF BASELINE DOCUMENTATION**
