# INVARIANTS - NON-NEGOTIABLE RULES
**Version**: Phase-3D Complete  
**Date**: January 28, 2026  
**Status**: IMMUTABLE - Violating these breaks the system

---

## CATEGORY 1: EXECUTION FLOW INVARIANTS

### INV-1.1: Observation Purity
**Rule**: Observations MUST NEVER modify system state.

**Enforcement**:
- File reads use `open(..., 'r')` only
- Window queries use read-only APIs
- No write operations in Observer

**Violations**:
- ❌ File write in observation
- ❌ Window manipulation in query
- ❌ Action execution in Observer

**Test**: `test_file_read_fix.py`

---

### INV-1.2: Observation Policy Bypass
**Rule**: Observations MUST NEVER require policy validation.

**Rationale**: Read-only operations are inherently safe.

**Enforcement**:
- Observer bypasses PolicyEngine
- No policy check phase for observations
- Observation flow: PLAN → OBSERVE → COMMIT

**Violations**:
- ❌ Policy check for file read
- ❌ Whitelist validation for query
- ❌ Observation in action execution path

**Test**: `test_llm_bypass.py`

---

### INV-1.3: Observation No-Verification
**Rule**: Observations MUST NEVER be verified.

**Rationale**: Nothing to verify for read-only operations.

**Enforcement**:
- Observer has no verification phase
- Critic is not invoked for observations
- Success determined by execution only

**Violations**:
- ❌ Critic.verify_action() on observation
- ❌ Verification phase for file read
- ❌ Retry logic for observation

**Test**: `test_file_read_fix.py`

---

### INV-1.4: File Read Classification
**Rule**: File reads MUST be classified as OBSERVATIONS, not actions.

**Detection**: `action_type='launch_app' AND context='file'`

**Enforcement**:
- Controller routes to FileHandler.read_file()
- Planner marks as observation-only
- No policy/verify phases

**Violations**:
- ❌ File read through action execution
- ❌ Policy validation for file read
- ❌ Verification of file read

**Test**: `test_file_read_fix.py`

---

## CATEGORY 2: RETRY INVARIANTS

### INV-2.1: Verification Failure is Terminal
**Rule**: Actions with `reason='verification_failed'` MUST NEVER retry.

**Rationale**: Verification failures are logical, not transient.

**Enforcement**:
- Check `verify_result.reason == 'verification_failed'`
- Return False (no retry)
- Log: "This is a terminal failure (no retry allowed)"

**Violations**:
- ❌ Retry after verification_failed
- ❌ Ignore reason field
- ❌ Override terminal status

**Test**: `test_verification_terminal.py`, `test_verification_no_retry.py`

---

### INV-2.2: Verification Action No-Retry
**Rule**: Actions with `verify` metadata MUST NEVER retry.

**Detection**: `action.verify is not None`

**Rationale**: Verification intents are explicit checks, not operations.

**Enforcement**:
- Check `action.verify` before retry
- Return False if verify metadata exists
- Log: "Retries forbidden for verification failures"

**Violations**:
- ❌ Retry verification action
- ❌ Ignore verify metadata
- ❌ Treat as regular action

**Test**: `test_verification_no_retry.py`

---

### INV-2.3: Maximum 2 Attempts
**Rule**: Regular actions MUST NOT exceed 2 execution attempts.

**Enforcement**:
- Attempt 1: Initial execution
- Attempt 2: Retry if failed (not verification action)
- No attempt 3

**Violations**:
- ❌ Third execution attempt
- ❌ Infinite retry loop
- ❌ Retry after retry_exhausted

**Test**: `test_verification_no_retry.py`

---

### INV-2.4: Policy Denial is Terminal
**Rule**: Actions with `reason='policy_denied'` MUST NEVER retry.

**Rationale**: Security policy violations are not transient.

**Enforcement**:
- PolicyEngine sets reason='policy_denied'
- No retry logic for policy failures
- Immediate plan abortion

**Violations**:
- ❌ Retry after policy denial
- ❌ Attempt to bypass whitelist
- ❌ Override security policy

**Test**: Policy engine tests

---

## CATEGORY 3: AUTHORITY INVARIANTS

### INV-3.1: Primary Authority Finality
**Rule**: Primary authority (DOM/UIA/FILE) result is FINAL for success/failure.

**Authority Hierarchy**:
```
PRIMARY (Final)     ADVISORY (Context)
├── DOM            └── Vision
├── UIA
└── FILE
```

**Enforcement**:
- If primary SUCCESS: return SUCCESS (don't check vision)
- If primary FAIL: return FAIL (vision provides context only)
- Confidence adjusted, but success/failure unchanged

**Violations**:
- ❌ Vision overrides primary success
- ❌ Vision promotes failure to success
- ❌ Vision treated as primary authority

**Test**: `test_phase_3c.py`, confidence scoring tests

---

### INV-3.2: Vision Advisory-Only
**Rule**: Vision results MUST NEVER override primary authority.

**Vision Role**: Provide diagnostic context, not authoritative verification.

**Enforcement**:
- Vision consulted ONLY after primary fails
- Vision result affects confidence, not success/failure
- Vision evidence logged but not decisive

**Scenarios**:
- DOM SUCCESS → Vision NOT consulted (primary sufficient)
- DOM FAIL + Vision VERIFIED → Still FAIL (confidence 0.65)
- DOM FAIL + Vision NOT_VERIFIED → Still FAIL (confidence 0.3)

**Violations**:
- ❌ Vision SUCCESS overrides DOM FAIL
- ❌ Vision used without primary attempt
- ❌ Vision promoted to primary authority

**Test**: `test_phase_3b.py`, `test_phase_3c.py`

---

### INV-3.3: Context-Specific Primary
**Rule**: Each context MUST have exactly one primary authority.

**Context Mapping**:
- Desktop context → UIA (Accessibility Tree)
- Web context → DOM (Browser state)
- File context → FILE (File system)

**Enforcement**:
- Critic routes by action.context
- No cross-context authority (DOM for desktop, UIA for web)
- Each context has deterministic primary

**Violations**:
- ❌ Use DOM for desktop verification
- ❌ Use UIA for web verification
- ❌ Multiple primary authorities per context

**Test**: Context routing tests

---

## CATEGORY 4: CONFIDENCE INVARIANTS

### INV-4.1: Confidence is Metadata
**Rule**: Confidence scores MUST NEVER affect control flow.

**Enforcement**:
- Confidence logged but not checked in conditionals
- No branches based on confidence value
- No retry logic triggered by low confidence

**Violations**:
- ❌ `if confidence < 0.5: retry()`
- ❌ `if confidence > 0.8: skip_verification()`
- ❌ Use confidence for planning decisions

**Test**: `test_phase_3c.py`

---

### INV-4.2: Confidence Range [0.0, 1.0]
**Rule**: Confidence scores MUST be in range [0.0, 1.0].

**Enforcement**:
- _compute_confidence() returns float [0.0, 1.0]
- No negative confidence
- No confidence > 1.0

**Violations**:
- ❌ Confidence = -0.5
- ❌ Confidence = 1.5
- ❌ Confidence = None (use 0.0)

**Test**: Confidence computation tests

---

### INV-4.3: No Automatic Thresholds
**Rule**: System MUST NOT have automatic confidence thresholds.

**Rationale**: Confidence is advisory, not probabilistic.

**Enforcement**:
- No hardcoded confidence cutoffs
- Human interpretation required
- Confidence for diagnostics only

**Violations**:
- ❌ `if confidence < 0.6: mark_suspicious()`
- ❌ Automatic rejection below threshold
- ❌ Confidence-based action selection

**Test**: No threshold logic exists

---

## CATEGORY 5: EVIDENCE INVARIANTS

### INV-5.1: Evidence Does Not Affect Execution
**Rule**: Evidence collection MUST NEVER change control flow.

**Enforcement**:
- Evidence gathered after success/failure determined
- No branches based on evidence content
- No retry triggered by evidence

**Violations**:
- ❌ `if evidence.sample contains 'error': retry()`
- ❌ Change success to failure based on evidence
- ❌ Use evidence for planning

**Test**: `test_evidence_collection.py`

---

### INV-5.2: Evidence Always Collected
**Rule**: Evidence MUST be collected for ALL verification attempts.

**Coverage**:
- Success paths: collect evidence
- Failure paths: collect evidence
- Vision fallback: collect evidence
- All contexts: collect evidence

**Enforcement**:
- Every verification sets verification_evidence
- Evidence logged regardless of outcome
- Evidence stored in database

**Violations**:
- ❌ Skip evidence on success
- ❌ Skip evidence on failure
- ❌ Conditional evidence collection

**Test**: `test_evidence_collection.py`

---

### INV-5.3: Evidence Structure Consistency
**Rule**: Evidence MUST follow defined structure.

**Required Fields**:
```json
{
    "source": "DOM|VISION|UIA|FILE|NONE",
    "checked_text": "string or null",
    "sample": "string or null",
    "confidence": 0.0-1.0
}
```

**Enforcement**:
- All evidence creation uses this schema
- Database stores JSON with these fields
- Logs display these fields

**Violations**:
- ❌ Missing required fields
- ❌ Wrong field types
- ❌ Extra undocumented fields

**Test**: `test_evidence_collection.py`

---

## CATEGORY 6: LOGGING INVARIANTS

### INV-6.1: ASCII-Only Logging
**Rule**: All logs MUST be ASCII-only (Windows cp1252 compatible).

**Rationale**: Windows console encoding limitations.

**Enforcement**:
- `sanitize_for_ascii()` on all log messages
- Replace unicode with ASCII equivalents
- No emoji, no special symbols

**Symbol Replacements**:
- ✓ → `[OK]`
- ✗ → `[FAIL]`
- → → `->`
- • → `-`

**Violations**:
- ❌ Unicode emoji in logs
- ❌ Non-ASCII characters
- ❌ Platform-specific symbols

**Test**: `test_ascii_logging.py`

---

### INV-6.2: Log Message Accuracy
**Rule**: Log messages MUST accurately reflect failure types.

**Enforcement**:
- Check `last_failure_reason` for log message selection
- "failed due to verification failure" for verification_failed
- "failed after retry" for retry_exhausted

**Violations**:
- ❌ "retry" in verification failure message
- ❌ Misleading failure descriptions
- ❌ Incorrect retry counts

**Test**: `test_failure_reason_logs.py`

---

### INV-6.3: Phase Log Ordering
**Rule**: Phase logs MUST appear in execution order.

**Execution Order**:
1. PHASE 1: PLAN
2. PHASE 2: POLICY CHECK (actions only)
3. PHASE 3: ACT
4. PHASE 4: VERIFY (actions only)
5. PHASE 5: COMMIT

**Enforcement**:
- Logs emitted at phase boundaries
- No phase skipping in logs
- No out-of-order phases

**Violations**:
- ❌ VERIFY before ACT
- ❌ COMMIT before VERIFY
- ❌ Missing phase logs

**Test**: Log parsing tests

---

## CATEGORY 7: DATA INTEGRITY INVARIANTS

### INV-7.1: Reason Field Semantics
**Rule**: Reason field MUST have consistent semantics.

**Defined Values**:
- `'verification_failed'`: Verification check failed (TERMINAL)
- `'retry_exhausted'`: Both attempts failed (TERMINAL)
- `'policy_denied'`: Whitelist violation (TERMINAL)
- `None`: No specific reason (success or retryable)

**Enforcement**:
- Only these values used
- Set at appropriate locations
- Checked before retry logic

**Violations**:
- ❌ Custom reason strings
- ❌ Empty string instead of None
- ❌ Ignore reason field

**Test**: `test_verification_terminal.py`, `test_failure_reason_logs.py`

---

### INV-7.2: Action Immutability
**Rule**: Action dataclass MUST be frozen (immutable).

**Enforcement**:
- `@dataclass(frozen=True)` for Action
- No field modification after creation
- No workarounds (setattr, __dict__)

**Rationale**: Actions are planned, not modified during execution.

**Violations**:
- ❌ Modify action.target during execution
- ❌ Change action.verify metadata
- ❌ Use mutable dataclass

**Test**: Dataclass definition

---

### INV-7.3: Evidence Persistence
**Rule**: Evidence MUST be persisted to database.

**Enforcement**:
- verification_evidence column in action_history
- JSON serialization of evidence dict
- Evidence survives process restart

**Violations**:
- ❌ Evidence only in memory
- ❌ Skip database storage
- ❌ Evidence lost after execution

**Test**: `test_evidence_collection.py` (Database storage test)

---

## CATEGORY 8: SEPARATION INVARIANTS

### INV-8.1: Action-Observation Separation
**Rule**: Actions and Observations MUST have separate execution paths.

**Separation Points**:
- Different database tables (action_history vs observation_log)
- Different execution methods (_execute_single_action vs _execute_single_observation)
- Different phase sequences

**Enforcement**:
- Planner detects observation intents
- Controller routes to appropriate handler
- No mixing of execution paths

**Violations**:
- ❌ Observation through action path
- ❌ Action through observation path
- ❌ Shared execution logic

**Test**: `test_file_read_fix.py`, `test_llm_bypass.py`

---

### INV-8.2: Policy-Execution Separation
**Rule**: Policy validation MUST occur before execution.

**Sequence**: POLICY CHECK → ACT → VERIFY

**Enforcement**:
- PolicyEngine.validate_action() before Controller.execute_action()
- No execution on policy denial
- Policy check is Phase 2, execution is Phase 3

**Violations**:
- ❌ Execute before policy check
- ❌ Execute on policy denial
- ❌ Skip policy validation

**Test**: Policy engine tests

---

### INV-8.3: Verification-Retry Separation
**Rule**: Verification logic MUST be separate from retry logic.

**Responsibilities**:
- Critic: Determines success/failure, sets reason
- Main.py: Checks reason, decides retry

**Enforcement**:
- Critic returns ActionResult with reason
- Main.py interprets reason for retry decision
- No retry logic in Critic

**Violations**:
- ❌ Critic triggers retry
- ❌ Main.py performs verification
- ❌ Mixed responsibilities

**Test**: `test_verification_no_retry.py`

---

## CATEGORY 9: CONFIGURATION INVARIANTS

### INV-9.1: Whitelist Enforcement
**Rule**: Policy whitelist MUST be enforced for all actions.

**Enforcement**:
- PolicyEngine checks action against whitelist
- Denial sets reason='policy_denied'
- No execution without approval

**Exceptions**:
- Observations bypass policy (read-only)

**Violations**:
- ❌ Execute non-whitelisted action
- ❌ Skip policy check
- ❌ Override whitelist

**Test**: Policy engine tests

---

### INV-9.2: Configuration Immutability During Execution
**Rule**: Configuration MUST NOT change during plan execution.

**Enforcement**:
- Config loaded at Agent initialization
- No config reload mid-execution
- No runtime config modification

**Violations**:
- ❌ Reload config during plan
- ❌ Modify config in-memory
- ❌ Different config per action

**Test**: Configuration loading tests

---

## CATEGORY 10: FAILURE HANDLING INVARIANTS

### INV-10.1: Terminal Failure No-Retry
**Rule**: Terminal failures MUST NEVER retry.

**Terminal Reasons**:
- `'verification_failed'`
- `'policy_denied'`

**Enforcement**:
- Check reason before retry
- Return False on terminal reason
- Log terminal status

**Violations**:
- ❌ Retry verification_failed
- ❌ Retry policy_denied
- ❌ Override terminal status

**Test**: `test_verification_terminal.py`, `test_verification_no_retry.py`

---

### INV-10.2: Plan Abortion on Failure
**Rule**: Plan MUST abort on action failure (no continuation).

**Enforcement**:
- Loop breaks on False return from _execute_single_action()
- No skip-and-continue on failure
- Log plan abortion

**Violations**:
- ❌ Continue plan after action failure
- ❌ Skip failed action
- ❌ Partial plan execution

**Test**: Plan execution tests

---

### INV-10.3: Failure Reason Tracking
**Rule**: Agent MUST track last failure reason.

**Enforcement**:
- `self.last_failure_reason` instance variable
- Updated on every failure
- Used for plan abortion logs

**Violations**:
- ❌ Lose failure reason
- ❌ Wrong reason in logs
- ❌ No reason tracking

**Test**: `test_failure_reason_logs.py`

---

## INVARIANT VIOLATION DETECTION

### How to Detect Violations
1. **Test Suite**: All tests pass → invariants likely preserved
2. **Code Review**: Manual inspection against invariant list
3. **Log Analysis**: Check for contradiction patterns:
   - "retry" in verification failure message
   - Policy check after execution
   - Evidence affecting control flow
4. **Database Audit**: Verify evidence persistence, reason values

### Violation Consequences
- ❌ Unreliable verification
- ❌ Incorrect retry behavior
- ❌ Security policy bypass
- ❌ Data corruption
- ❌ Unpredictable system behavior

---

## INVARIANT ENFORCEMENT CHECKLIST

Before modifying codebase:
- [ ] Review relevant invariants
- [ ] Identify affected components
- [ ] Verify no invariant violations
- [ ] Update tests to cover changes
- [ ] Run full test suite
- [ ] Document any necessary deviations

---

## IMMUTABILITY NOTICE

These invariants define the system's core correctness properties.

**Violating ANY invariant requires**:
1. Explicit approval
2. Updated documentation
3. New test coverage
4. Risk assessment
5. Rollback plan

**No exceptions without justification.**

---

**END OF INVARIANTS**
