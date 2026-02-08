# File Read Planning Bug Fix - Phase-2B

**Date**: January 28, 2026  
**Status**: ✅ FIXED  
**Test Results**: 4/4 tests passed

---

## Problem Description

The planner incorrectly treated `read_text` as an **ACTION** when reading files, causing the error:

```
Invalid action_type: read_text (must be one of ['launch_app','type_text','close_app'])
```

### Root Cause

`read_text` is an **OBSERVATION TYPE**, not an action type. File read instructions must generate ONLY observations with NO actions.

---

## Solution Implemented

### 1. Planner - Deterministic File Read Handler

**File**: [logic/planner.py](logic/planner.py)

**Changes**:
- Added explicit "read file" pattern recognition in `parse_instruction()`
- Returns observation-only plan for file read instructions
- Pattern: `"read file <filename>"` → `[Observation(read_text, context=file, target=filename)]`

```python
# Pattern: "read file [filename]" - Phase-2B deterministic file read
if "read file" in instruction_lower or "read text from file" in instruction_lower:
    # Extract filename
    filename = ...
    
    # Return OBSERVATION ONLY - no actions
    return [
        Observation(
            observation_type="read_text",
            context="file",
            target=filename
        )
    ]
```

### 2. Planner - Validation Updates

**File**: [logic/planner.py](logic/planner.py)

**Changes**:

A. **_validate_intent_priority()** - Added file read validation
```python
# File-read intent detection
file_read_keywords = ["read file", "read text from"]
has_file_read_intent = any(keyword in instruction_lower for keyword in file_read_keywords)

if has_file_read_intent:
    # Check if plan has ANY actions
    actions = [item for item in plan if isinstance(item, Action)]
    if actions:
        raise ValueError(
            "File read intent must generate ONLY observations, NO actions."
        )
```

B. **_validate_plan_coherence()** - Allow observation-only plans
```python
# Phase-2B: Allow observation-only plans (e.g., file reads)
if len(actions) == 0 and len(observations) > 0:
    logger.info("Observation-only plan (valid for read operations)")
    return
```

C. **_validate_file_minimality()** - Validate file read plans
```python
# Phase-2B: File read validation - must be observation-only
if file_observations:
    if file_actions:
        raise ValueError(
            "Invalid file read plan: file read operations must be observation-only (no actions allowed)."
        )
```

D. **_create_plan_deterministic()** - Log action vs observation counts
```python
actions = [item for item in plan if isinstance(item, Action)]
observations = [item for item in plan if isinstance(item, Observation)]
logger.info(f"Generated {len(plan)} item(s): {len(actions)} action(s), {len(observations)} observation(s)")
```

### 3. LLM Client - System Prompt Update

**File**: [logic/llm_client.py](logic/llm_client.py)

**Changes**:
- Clarified that `read_text` is ONLY for observations
- Added critical warning in system prompt

```python
OBSERVATION TYPES:
- read_text: Extract text from element/file (OBSERVATION ONLY - never use as action_type!)
  {"observation_type": "read_text", "context": "web", "target": "h1"}
  {"observation_type": "read_text", "context": "file", "target": "notes.txt"}

CRITICAL: "read_text" is ONLY valid as observation_type, NEVER as action_type.
File read instructions (e.g., "read file test.txt") must generate ONLY observations, NO actions.
```

### 4. LLM Client - Action Validation

**File**: [logic/llm_client.py](logic/llm_client.py)

**Changes**:
- Added explicit rejection of `read_text` as action_type in `_dict_to_action()`

```python
# CRITICAL: Reject read_text as action_type (it's an observation)
if action_type == "read_text":
    raise ValueError(
        "Invalid action_type: read_text is an OBSERVATION, not an action. "
        "Use observation_type='read_text' instead."
    )
```

### 5. FileHandler - Public Read Method

**File**: [execution/file_handler.py](execution/file_handler.py)

**Changes**:
- Added `read_file_content(file_path: str) -> str` public method
- Allows observer to read files without creating actions

```python
def read_file_content(self, file_path: str) -> str:
    """
    Read file content for observations (Phase-2B).
    
    Args:
        file_path: File path (relative to workspace)
        
    Returns:
        File content as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If path is invalid or outside workspace
    """
    # Validate path, read content
    content = resolved_path.read_text(encoding='utf-8')
    return content
```

### 6. Observer - Use New Read Method

**File**: [perception/observer.py](perception/observer.py)

**Changes**:
- Updated `_observe_file()` to call `read_file_content()` instead of `_read_file()`

```python
if observation.observation_type == "read_text":
    # Read file contents using new read_file_content method (Phase-2B)
    content = self.file_handler.read_file_content(observation.target)
    return ObservationResult(
        observation=observation,
        status="success",
        result=content,
        timestamp=datetime.now().isoformat()
    )
```

---

## Test Results

### Test Suite: [test_file_read_fix.py](test_file_read_fix.py)

All 4 tests passed:

| Test | Description | Result |
|------|-------------|--------|
| **Test 1** | Deterministic file read parsing | ✅ PASS |
| **Test 2** | Full file read execution flow | ✅ PASS |
| **Test 3** | LLM validation (rejects actions) | ✅ PASS |
| **Test 4** | Validation rejects invalid plans | ✅ PASS |

### Test 1: Deterministic File Read Parsing

**Input**: `"read file test_a1.txt"`

**Output**:
```
Plan generated: 1 item(s)
- Actions: 0
- Observations: 1

Observation: Observation(
    observation_type='read_text',
    context='file',
    target='test_a1.txt'
)
```

✅ **Result**: File read correctly parsed as observation-only

### Test 2: Full File Read Execution

**Steps**:
1. Create file `test_a1.txt` with content `"hello"`
2. Plan instruction: `"read file test_a1.txt"`
3. Execute observation
4. Verify content returned

**Output**:
```
Plan: 1 observation(s), 0 action(s)
Observation status: success
Observation result: hello
```

✅ **Result**: File read executed successfully, content retrieved

### Test 3: LLM Validation

**Input**: `"read file test_a1.txt"` (with LLM planner)

**LLM Attempted**: Generated 1 launch_app action + 1 observation

**Validation**: Correctly rejected with error:
```
File read intent must generate ONLY observations, NO actions.
Expected: [Observation(read_text, context=file)].
Got: 1 action(s).
```

✅ **Result**: Validation correctly caught and rejected invalid LLM plan

### Test 4: Validation Rejects Actions

**Manual Test**: Created invalid plan with both action and observation

**Validation**: Correctly rejected:
```
Expected error caught: File read intent must generate ONLY observations, NO actions.
```

✅ **Result**: Validation correctly enforces observation-only constraint

---

## Correct Flow After Fix

### Instruction
```
"read file test_a1.txt"
```

### Planner Output
```python
[
    Observation(
        observation_type="read_text",
        context="file",
        target="test_a1.txt"
    )
]
```

**Key Properties**:
- **0 actions** (no launch_app, no type_text)
- **1 observation** (read_text with context=file)
- **No policy checks** (observations bypass policy)
- **No verification** (observations are read-only)

### Execution Flow

1. **PLAN phase**: Planner generates observation-only plan
2. **OBSERVE phase**: Observer routes to file handler
   - Calls `file_handler.read_file_content(target)`
   - Returns file content as string
3. **No ACT phase** (no actions to execute)
4. **No VERIFY phase** (no actions to verify)

**Output**: File content returned to user

---

## Files Modified

1. **logic/planner.py**
   - Added deterministic file read handler
   - Updated validation (intent priority, coherence, file minimality)
   - Added action vs observation logging

2. **logic/llm_client.py**
   - Updated system prompt to clarify read_text is observation-only
   - Added validation to reject read_text as action_type

3. **execution/file_handler.py**
   - Added `read_file_content()` public method for observations

4. **perception/observer.py**
   - Updated `_observe_file()` to use `read_file_content()`

5. **test_file_read_fix.py** (new)
   - 4 comprehensive tests validating the fix

---

## Validation Checklist

✅ **read_text is NEVER treated as action_type**
- Planner generates observation-only plans
- LLM client rejects read_text as action_type
- Validation enforces observation-only for file reads

✅ **File read plans contain 0 actions**
- Deterministic planner: Returns observation only
- LLM validation: Rejects plans with actions
- Test confirmation: 0 actions generated

✅ **Observer correctly handles file reads**
- Routes to file handler
- Returns file content as string
- No action execution attempted

✅ **Validation prevents invalid plans**
- _validate_intent_priority(): Rejects actions in file read
- _validate_file_minimality(): Enforces observation-only
- _validate_plan_coherence(): Allows observation-only plans

✅ **LLM guidance improved**
- System prompt explicitly states read_text is observation-only
- Critical warning added to prevent confusion
- Action parser rejects read_text with clear error

---

## Error Prevention

### Before Fix

**Instruction**: `"read file test.txt"`

**LLM Output** (incorrect):
```json
[
    {"action_type": "launch_app", "context": "file", "target": "test.txt"},
    {"action_type": "read_text", "context": "file", "target": "test.txt"}
]
```

**Error**:
```
Invalid action_type: read_text (must be one of ['launch_app','type_text','close_app'])
```

### After Fix

**Instruction**: `"read file test.txt"`

**Deterministic Output** (correct):
```python
[
    Observation(observation_type="read_text", context="file", target="test.txt")
]
```

**LLM Output** (if generates actions):
```
ValidationError: File read intent must generate ONLY observations, NO actions.
```

**Result**: File read executes successfully OR validation rejects invalid plan

---

## Future Considerations

### LLM Training

While validation now prevents invalid plans, the LLM still occasionally generates actions for file reads. Future improvements:

1. **Few-shot examples** in system prompt showing correct observation-only plans
2. **Temperature reduction** for file operations (lower = more deterministic)
3. **Model fine-tuning** with correct file read examples

### Other Read Operations

This fix applies to:
- File reads: `read_text` with `context=file`
- Web reads: `read_text` with `context=web` (already supported)
- Desktop reads: `read_text` with `context=desktop` (future)

All use the same observation-only pattern.

---

## Summary

**Bug**: `read_text` incorrectly treated as action

**Root Cause**: Missing deterministic handler + insufficient LLM guidance + no validation

**Fix**: 
1. Deterministic file read handler (observation-only)
2. Validation enforces observation-only for file reads
3. LLM guidance clarified + action parser rejects read_text
4. FileHandler public read method for observers

**Result**: ✅ All tests passed, file reads work correctly

**Status**: **FIXED** ✅

