# NEGATIVE CAPABILITY AUDIT
**Purpose**: Safety Documentation - What the Agent CANNOT and WILL NOT Do  
**Date**: January 28, 2026  
**Status**: Official Safety Boundaries

---

## 1. UNSUPPORTED USER INTENTS

### 1.1 Coordinate-Based Interactions
**Intent**: "Click at position (100, 200)"

**Status**: ❌ NOT SUPPORTED (Phase-2A constraint)

**Reason**: Coordinate clicking disabled in current phase for safety.

**Enforcement**:
- Action.__post_init__() raises ValueError if coordinates != None
- Controller rejects actions with coordinates
- Planner does not generate coordinate-based actions

**User Impact**: Requests like "click the button at coordinates X,Y" will fail with validation error.

---

### 1.2 Multi-Monitor Operations
**Intent**: "Open app on second monitor"

**Status**: ❌ NOT SUPPORTED

**Reason**: No multi-monitor awareness in accessibility tree queries.

**Workarounds**: None. Agent operates on primary monitor only.

**User Impact**: Cannot target specific monitors, cannot move windows between monitors.

---

### 1.3 Advanced Keyboard Shortcuts
**Intent**: "Press Ctrl+Alt+Delete", "Press F12", "Hold Shift while clicking"

**Status**: ❌ NOT SUPPORTED

**Reason**: 
- Controller.type_text() only sends plain text characters
- No key combination support
- No modifier key handling (Ctrl, Alt, Shift)

**Supported**: Plain text typing only (alphanumeric + basic punctuation)

**User Impact**: Cannot trigger shortcuts, cannot press function keys, cannot use modifier combinations.

---

### 1.4 Mouse Drag Operations
**Intent**: "Drag file from A to B", "Select text by dragging"

**Status**: ❌ NOT SUPPORTED

**Reason**: No drag-and-drop implementation in Controller.

**User Impact**: Cannot move items via drag, cannot select via mouse drag, cannot resize windows by dragging.

---

### 1.5 Right-Click / Context Menus
**Intent**: "Right-click and select Copy"

**Status**: ❌ NOT SUPPORTED

**Reason**: No context menu interaction in current implementation.

**User Impact**: Cannot access context menus, cannot use right-click options.

---

### 1.6 File Upload via Dialog
**Intent**: "Upload file through file picker dialog"

**Status**: ❌ NOT SUPPORTED

**Reason**: No dialog automation, cannot interact with system file picker.

**User Impact**: Cannot upload files through UI dialogs. Workaround: Direct file operations only.

---

### 1.7 System Tray Interactions
**Intent**: "Click the WiFi icon in system tray"

**Status**: ❌ NOT SUPPORTED

**Reason**: System tray not accessible via UIA in current implementation.

**User Impact**: Cannot interact with system tray icons, cannot access tray menus.

---

### 1.8 Window Management
**Intent**: "Minimize window", "Maximize window", "Move window to left half"

**Status**: ❌ NOT SUPPORTED

**Reason**: No window manipulation actions in Controller.

**Supported**: launch_app, type_text, close_app only.

**User Impact**: Cannot resize, move, minimize, or maximize windows.

---

### 1.9 Clipboard Operations
**Intent**: "Copy text to clipboard", "Paste from clipboard"

**Status**: ❌ NOT SUPPORTED

**Reason**: No clipboard integration.

**User Impact**: Cannot use copy/paste operations.

---

### 1.10 Screen Capture by User Request
**Intent**: "Take a screenshot", "Save what's on screen"

**Status**: ❌ NOT SUPPORTED

**Reason**: Screen capture is internal for verification only, not exposed to users.

**User Impact**: Cannot request screenshots as an action result.

---

### 1.11 Audio/Video Playback Control
**Intent**: "Play video", "Pause music", "Adjust volume"

**Status**: ❌ NOT SUPPORTED

**Reason**: No media control actions implemented.

**User Impact**: Cannot control media playback.

---

### 1.12 Nested/Conditional Plans
**Intent**: "If text appears, then click button, else retry"

**Status**: ❌ NOT SUPPORTED

**Reason**: Planner generates linear action sequences only, no conditionals.

**User Impact**: Cannot create if/else logic, cannot create loops, cannot create branches.

---

### 1.13 Parallel Action Execution
**Intent**: "Open both Notepad and Calculator at the same time"

**Status**: ❌ NOT SUPPORTED

**Reason**: Sequential execution only (one action at a time).

**User Impact**: Actions execute in sequence, not parallel. No concurrent operations.

---

### 1.14 Network Operations
**Intent**: "Download file from URL", "Check network status", "Ping server"

**Status**: ❌ NOT SUPPORTED

**Reason**: No network action types implemented.

**Workaround**: Browser can navigate to URLs, but no direct network operations.

**User Impact**: Cannot download files, cannot check connectivity, cannot access network APIs.

---

### 1.15 Database Operations
**Intent**: "Query database", "Insert record", "Update table"

**Status**: ❌ NOT SUPPORTED

**Reason**: No database action types (internal DB is for logging only).

**User Impact**: Cannot perform database operations via user requests.

---

### 1.16 API Calls / Web Services
**Intent**: "Call REST API", "Send HTTP POST request", "Check API response"

**Status**: ❌ NOT SUPPORTED

**Reason**: No API client actions implemented.

**User Impact**: Cannot make API calls, cannot integrate with web services.

---

### 1.17 Email Operations
**Intent**: "Send email", "Read inbox", "Reply to message"

**Status**: ❌ NOT SUPPORTED

**Reason**: No email client integration.

**User Impact**: Cannot send or read emails.

---

### 1.18 Calendar/Scheduling
**Intent**: "Create calendar event", "Set reminder", "Check schedule"

**Status**: ❌ NOT SUPPORTED

**Reason**: No calendar integration.

**User Impact**: Cannot manage calendar, cannot set reminders.

---

### 1.19 System Administration
**Intent**: "Install software", "Modify registry", "Change system settings", "Run as administrator"

**Status**: ❌ NOT SUPPORTED (By design)

**Reason**: Security policy. Agent runs with user permissions only.

**User Impact**: Cannot perform privileged operations, cannot modify system configuration.

---

### 1.20 Cross-Application Data Transfer
**Intent**: "Copy text from Notepad and paste into Word"

**Status**: ❌ NOT SUPPORTED

**Reason**: No clipboard, no cross-app data passing.

**User Impact**: Cannot transfer data between applications in a single plan.

---

## 2. REJECTED ACTION PATTERNS

### 2.1 Non-Whitelisted Applications
**Pattern**: Attempting to launch applications not in policy.yaml whitelist.

**Detection**: PolicyEngine.validate_action() checks whitelist.

**Result**: DENIED with reason='policy_denied' (TERMINAL)

**Example**:
```python
Action(action_type="launch_app", target="malware.exe")
# Result: DENIED - malware.exe not in whitelist
```

**Logs**: `[FAIL] DENIED: malware.exe not in whitelist`

**User Impact**: Cannot launch arbitrary applications. Only whitelisted apps allowed.

---

### 2.2 Non-Whitelisted URLs
**Pattern**: Navigating to URLs not in policy.yaml whitelist.

**Detection**: PolicyEngine checks URL against whitelist patterns.

**Result**: DENIED with reason='policy_denied' (TERMINAL)

**Example**:
```python
Action(action_type="launch_app", context="web", target="https://malicious-site.com")
# Result: DENIED - URL not in whitelist
```

**User Impact**: Cannot navigate to arbitrary websites. Only whitelisted domains allowed.

---

### 2.3 Unsafe File Paths
**Pattern**: Accessing files outside allowed directories.

**Detection**: PolicyEngine checks file paths against whitelist patterns.

**Result**: DENIED with reason='policy_denied' (TERMINAL)

**Example**:
```python
Action(action_type="launch_app", context="file", target="C:\\Windows\\System32\\config\\SAM")
# Result: DENIED - System files not in whitelist
```

**User Impact**: Cannot access system files, cannot read arbitrary paths.

---

### 2.4 Coordinate-Based Actions (Phase-2A)
**Pattern**: Any action with coordinates field set.

**Detection**: Action.__post_init__() validates coordinates is None.

**Result**: ValueError raised during action creation.

**Example**:
```python
Action(action_type="click", coordinates=(100, 200))
# Result: ValueError - Coordinates not allowed in Phase-2A
```

**User Impact**: Cannot use coordinate-based clicking at all.

---

### 2.5 Empty or Invalid Actions
**Pattern**: Actions missing required fields.

**Detection**: Action.__post_init__() validates required fields.

**Result**: ValueError raised during action creation.

**Examples**:
```python
Action(action_type="launch_app", target=None)
# Result: ValueError - launch_app requires 'target' field

Action(action_type="type_text", text=None)
# Result: ValueError - type_text requires 'text' field
```

**User Impact**: All actions must have valid parameters.

---

### 2.6 Close App in File Context
**Pattern**: Attempting to close in file context.

**Detection**: Action.__post_init__() validates context compatibility.

**Result**: ValueError raised.

**Example**:
```python
Action(action_type="close_app", context="file")
# Result: ValueError - close_app not supported in file context
```

**User Impact**: Cannot close files (files don't have close semantics).

---

### 2.7 Retry After Terminal Failure
**Pattern**: Attempting to retry actions that failed with terminal reasons.

**Detection**: Main.py checks reason field before retry.

**Result**: No retry, plan aborted.

**Terminal Reasons**:
- `reason='verification_failed'`
- `reason='policy_denied'`
- Actions with verify metadata

**Example Flow**:
```
Action with verify metadata fails
→ reason='verification_failed'
→ Main.py checks reason
→ No retry
→ Plan aborted
```

**User Impact**: Some failures are immediate and final - no second chances.

---

### 2.8 Modification of Immutable Actions
**Pattern**: Attempting to modify action after creation.

**Detection**: @dataclass(frozen=True) enforces immutability.

**Result**: FrozenInstanceError raised.

**Example**:
```python
action = Action(action_type="launch_app", target="notepad.exe")
action.target = "calc.exe"  # Attempt to modify
# Result: FrozenInstanceError - Action is immutable
```

**User Impact**: Actions cannot be modified after creation.

---

### 2.9 Verification Override
**Pattern**: Attempting to skip verification or override verification result.

**Detection**: Execution flow is fixed (PLAN → POLICY → ACT → VERIFY → COMMIT).

**Result**: Not possible - verification always runs.

**User Impact**: Cannot bypass verification, cannot force success on verification failure.

---

### 2.10 Policy Override
**Pattern**: Attempting to execute without policy check.

**Detection**: Execution flow requires POLICY CHECK phase.

**Result**: Not possible - policy always validated.

**Exception**: Observations bypass policy (read-only safety).

**User Impact**: Cannot bypass whitelist, cannot override security policy.

---

## 3. TERMINAL FAILURE CONDITIONS

### 3.1 Verification Failure (reason='verification_failed')
**Condition**: Verification check explicitly fails.

**Causes**:
- DOM verification: text not found in page
- Vision verification: NOT_VERIFIED or UNKNOWN
- UIA verification: window not found after launch
- File verification: file not found

**Behavior**: 
- No retry attempted
- Plan immediately aborted
- Log: "Action {i} failed due to verification failure. Aborting plan."

**Recovery**: None. Requires user to revise request or fix environment.

---

### 3.2 Policy Denial (reason='policy_denied')
**Condition**: Action rejected by security policy.

**Causes**:
- Application not in whitelist
- URL not in whitelist
- File path not in whitelist

**Behavior**:
- No execution attempted
- Plan immediately aborted
- Log: "[FAIL] DENIED: {reason}"

**Recovery**: None. Requires whitelist update or user to change request.

---

### 3.3 Retry Exhaustion (reason='retry_exhausted')
**Condition**: Regular action fails twice (initial + 1 retry).

**Causes**:
- Window closed on both attempts
- Element not found on both attempts
- Transient errors persisted

**Behavior**:
- Plan aborted after second failure
- Log: "Action {i} failed after retry. Aborting plan."

**Recovery**: None. Requires user to investigate why action failed twice.

---

### 3.4 Action Validation Error
**Condition**: Action dataclass validation fails.

**Causes**:
- Missing required fields
- Invalid field values
- Coordinate field set (Phase-2A)
- Incompatible context/action_type

**Behavior**:
- ValueError raised during action creation
- Plan cannot be created
- Log: Validation error message

**Recovery**: None. Planner must generate valid actions.

---

### 3.5 LLM Planning Failure
**Condition**: LLM fails to generate valid plan.

**Causes**:
- LLM returns invalid JSON
- LLM generates no actions
- LLM generates invalid action types

**Behavior**:
- Planner returns empty plan
- Execution aborted
- Log: "[FAIL] Planner could not generate a safe plan"

**Recovery**: Falls back to deterministic planner if available.

---

### 3.6 Browser Initialization Failure
**Condition**: Browser handler fails to initialize.

**Causes**:
- Playwright not installed
- Browser binary not found
- Port already in use

**Behavior**:
- Browser actions disabled
- Web context actions will fail verification
- Log: "Failed to initialize browser handler"

**Recovery**: Browser automation disabled. Web actions not available.

---

### 3.7 Vision Client Unavailable
**Condition**: Vision client fails to initialize.

**Causes**:
- Ollama not running
- VLM model not available
- Network error to Ollama

**Behavior**:
- Vision fallback disabled
- Verification uses primary authority only
- Log: "Vision client unavailable"

**Recovery**: System continues without vision fallback.

---

### 3.8 Database Write Failure
**Condition**: Cannot write to action_history or observation_log.

**Causes**:
- Database file locked
- Disk full
- Permission denied

**Behavior**:
- Execution continues but logging fails
- Log: "Failed to commit to database"

**Recovery**: Execution completes but history not persisted.

---

### 3.9 Planner Cannot Detect Intent
**Condition**: User request is ambiguous or unsupported.

**Causes**:
- Request doesn't map to available actions
- Request is too vague
- Request requires unsupported capability

**Behavior**:
- Planner returns empty plan or incorrect plan
- Execution may fail or do nothing
- Log: "Could not generate plan"

**Recovery**: User must clarify or simplify request.

---

### 3.10 Observation Execution Error
**Condition**: File read or window query fails.

**Causes**:
- File not found
- Permission denied
- Window closed

**Behavior**:
- Observation fails
- Result logged as failure
- No retry (observations never retry)

**Recovery**: None. User must check target exists.

---

## 4. CAPABILITIES INTENTIONALLY EXCLUDED

### 4.1 Learning from Failures
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope for baseline. Future phase (episodic memory).

**Impact**: Agent does not remember past failures, does not adapt behavior based on history.

---

### 4.2 Plan Optimization
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope for baseline. Future phase.

**Impact**: Plans are not optimized for efficiency, no plan reordering, no step minimization.

---

### 4.3 Dynamic Confidence Thresholds
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Confidence is metadata only (INV-4.3). No automatic thresholds by design.

**Impact**: Low confidence does not trigger retry or alternative strategies.

---

### 4.4 Automatic Evidence Analysis
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Evidence is descriptive only (INV-5.1). No control flow impact.

**Impact**: Evidence not analyzed for patterns, not used for decision making.

---

### 4.5 Cross-Session Memory
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope for baseline. Future phase.

**Impact**: Each execution is independent, no memory between sessions.

---

### 4.6 Vision Model Fine-Tuning
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope. Vision is advisory only.

**Impact**: Vision results are not calibrated, not improved over time.

---

### 4.7 Multi-Agent Coordination
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope. Single agent only.

**Impact**: Cannot coordinate with other agents, cannot distribute tasks.

---

### 4.8 Self-Modification
**Status**: ❌ NOT IMPLEMENTED (Intentional)

**Reason**: Safety. Agent cannot modify its own code.

**Impact**: Cannot update itself, cannot change behavior at runtime.

---

### 4.9 Privilege Escalation
**Status**: ❌ NOT IMPLEMENTED (Intentional)

**Reason**: Security. Agent runs with user permissions only.

**Impact**: Cannot perform admin tasks, cannot modify system settings.

---

### 4.10 Distributed Execution
**Status**: ❌ NOT IMPLEMENTED

**Reason**: Out of scope. Single machine only.

**Impact**: Cannot execute across multiple machines, cannot use remote resources.

---

## 5. THINGS THE AGENT WILL NEVER ATTEMPT

### 5.1 Override Security Policy
**Never**: Bypass whitelist, ignore policy denials, execute unauthorized actions.

**Enforcement**: PolicyEngine is mandatory, no bypass mechanism exists.

**Invariant**: INV-9.1 (Whitelist enforcement)

---

### 5.2 Retry Terminal Failures
**Never**: Retry after verification_failed, retry after policy_denied.

**Enforcement**: Reason field checked before retry logic.

**Invariants**: INV-2.1, INV-2.2, INV-2.4, INV-10.1

---

### 5.3 Execute Without Verification
**Never**: Skip verification phase for actions, assume success without checking.

**Enforcement**: Execution flow is fixed (5 phases).

**Invariant**: INV-8.2 (Policy-execution separation)

---

### 5.4 Modify Immutable Actions
**Never**: Change action fields after creation, mutate frozen dataclass.

**Enforcement**: @dataclass(frozen=True)

**Invariant**: INV-7.2 (Action immutability)

---

### 5.5 Silent Failures
**Never**: Fail without logging, suppress errors, hide exceptions.

**Enforcement**: All exceptions logged, all failures tracked.

**Verification**: Code audit shows all exception handlers log errors.

---

### 5.6 Override Primary Authority with Vision
**Never**: Change success to failure or vice versa based on vision.

**Enforcement**: Vision is advisory only, confidence adjustment only.

**Invariants**: INV-3.1, INV-3.2

---

### 5.7 Use Confidence for Control Flow
**Never**: Branch based on confidence score, retry based on low confidence.

**Enforcement**: Confidence is metadata only.

**Invariant**: INV-4.1

---

### 5.8 Ignore Evidence Collection
**Never**: Skip evidence collection, collect evidence selectively.

**Enforcement**: Evidence always collected regardless of outcome.

**Invariant**: INV-5.2

---

### 5.9 Execute Observations as Actions
**Never**: Apply policy to observations, verify observations, retry observations.

**Enforcement**: Separate execution paths for actions vs observations.

**Invariants**: INV-1.2, INV-1.3, INV-8.1

---

### 5.10 Exceed 2 Execution Attempts
**Never**: Third attempt, infinite retry loops.

**Enforcement**: Attempt counter checked before retry.

**Invariant**: INV-2.3

---

### 5.11 Continue Plan After Action Failure
**Never**: Skip failed action and continue, partial plan execution.

**Enforcement**: Loop breaks on False return from _execute_single_action().

**Invariant**: INV-10.2

---

### 5.12 Use Non-ASCII in Logs
**Never**: Unicode emojis, platform-specific symbols, non-cp1252 characters.

**Enforcement**: sanitize_for_ascii() applied to all logs.

**Invariant**: INV-6.1

---

### 5.13 Modify System Files
**Never**: Write to C:\\Windows, modify registry, change system configuration.

**Enforcement**: File path whitelist, user permissions only.

**Invariant**: INV-9.1

---

### 5.14 Execute Code from External Sources
**Never**: Download and run scripts, execute user-provided code.

**Enforcement**: No code execution actions, fixed action types only.

---

### 5.15 Exfiltrate Data
**Never**: Send data to external servers, upload files without user action.

**Enforcement**: No network operations, no API calls.

---

### 5.16 Access Credentials
**Never**: Read passwords, access keychains, steal authentication tokens.

**Enforcement**: No credential access actions, file whitelist prevents credential paths.

---

### 5.17 Disable Logging
**Never**: Turn off audit trail, hide actions from database.

**Enforcement**: Logging is mandatory, no disable mechanism.

---

### 5.18 Modify Its Own Database
**Never**: Delete action history, modify observation logs, tamper with evidence.

**Enforcement**: Database is append-only from agent's perspective.

---

### 5.19 Impersonate Users
**Never**: Masquerade as another user, escalate to admin.

**Enforcement**: Runs with current user permissions, no escalation mechanism.

---

### 5.20 Operate Outside Defined Contexts
**Never**: Create custom contexts, mix context behaviors.

**Enforcement**: Context enum is fixed (desktop, web, file only).

---

## 6. FAILURE MODE SUMMARY

### Immediate Failure (No Retry)
1. Policy denial → reason='policy_denied'
2. Verification failure → reason='verification_failed'
3. Verification action failure → verify metadata present
4. Action validation error → ValueError
5. File read failure → observation error (logged, not retried)

### Retry Then Failure
1. Regular action failure (non-verification)
   - Attempt 1 fails
   - Attempt 2 fails
   - reason='retry_exhausted'
   - Plan aborted

### Degraded Operation
1. Browser unavailable → web actions fail verification
2. Vision unavailable → no fallback verification
3. Database write failure → execution continues, no persistence

### Fatal (Execution Stops)
1. LLM planning failure → no plan generated
2. Planner initialization failure → cannot create plans
3. Controller initialization failure → cannot execute actions

---

## 7. USER EXPECTATION SETTING

### What Users Can Expect
✅ Simple desktop application automation (launch, type, close)  
✅ Basic web navigation (open URL, type in fields)  
✅ File read operations  
✅ Text verification (is text visible?)  
✅ Whitelist-based security  
✅ Automatic retry for transient failures  
✅ Complete audit trail  

### What Users Should NOT Expect
❌ Advanced UI interactions (drag, right-click, shortcuts)  
❌ Coordinate-based clicking  
❌ Multi-step conditional logic  
❌ Learning from past errors  
❌ Arbitrary application control  
❌ System administration  
❌ Network operations  
❌ Cross-application data transfer  
❌ Perfect success rate (some requests will fail)  

---

## 8. SAFETY BOUNDARIES

### Hard Boundaries (Cannot Be Bypassed)
1. **Security Policy**: Whitelist enforcement is mandatory
2. **Immutability**: Actions cannot be modified after creation
3. **Verification**: All actions must be verified
4. **Logging**: All operations logged to audit trail
5. **User Permissions**: Agent runs with user privileges only

### Soft Boundaries (Design Limitations)
1. **Action Types**: Limited to launch_app, type_text, close_app
2. **Contexts**: Limited to desktop, web, file
3. **Retry Logic**: Maximum 2 attempts
4. **Primary Authority**: DOM/UIA/FILE always final
5. **ASCII Logging**: No unicode characters

### Ethical Boundaries
1. **No Deception**: Agent identifies itself, doesn't impersonate users
2. **No Credential Theft**: Cannot access passwords or auth tokens
3. **No Data Exfiltration**: Cannot send data to external servers
4. **No Self-Modification**: Cannot change its own code
5. **No Privilege Escalation**: Cannot gain admin rights

---

## 9. DOCUMENTATION PURPOSE

This document serves as:

1. **Safety Reference**: Clear boundaries for what agent will not do
2. **User Guide**: Set expectations for supported capabilities
3. **Security Audit**: Document security constraints
4. **Development Guide**: Ensure new features respect boundaries
5. **Compliance**: Demonstrate intentional safety design

---

## VALIDATION

All negative capabilities verified against:
- ✅ BASELINE.md (feature scope)
- ✅ INVARIANTS.md (non-negotiable rules)
- ✅ Code audit (no backdoors, no overrides)
- ✅ Test suite (boundaries enforced)

---

**END OF NEGATIVE CAPABILITY AUDIT**
