# Phase-5B Audit Trail Examples

This document demonstrates the complete audit trail capability enabled by Phase-5B.

---

## Complete Audit Trail Flow

### 1. User Issues Instruction
```
Instruction: "Open Notepad and type Hello World"
```

### 2. Plan Created and Logged
```
Plan ID: 42
Status: pending
Approval Required: Yes
Created: 2026-01-28T10:30:00
```

**Plan JSON (stored in database):**
```json
{
  "instruction": "Open Notepad and type Hello World",
  "created_at": "2026-01-28T10:30:00",
  "steps": [
    {
      "step_id": 1,
      "intent": "Launch Notepad application",
      "expected_outcome": "Notepad window appears",
      "requires_approval": true,
      "item_type": "action",
      "item": {
        "action_type": "launch_app",
        "target": "notepad.exe"
      }
    },
    {
      "step_id": 2,
      "intent": "Type text into editor",
      "expected_outcome": "Text appears in Notepad",
      "item_type": "action",
      "item": {
        "action_type": "type_text",
        "text": "Hello World"
      }
    }
  ]
}
```

### 3. Plan Preview Shown to User
```
┌─ Plan Preview ──────────────────────────────────────────────────────
│ Instruction: Open Notepad and type Hello World
│ Total Steps: 2 (2 actions, 0 observations)
│ ⚠️  Approval Required: 1 step(s) marked
│
│ Step 1: launch_app [⚠️  REQUIRES APPROVAL]
│   Intent: Launch Notepad application
│   Expected: Notepad window appears
│   Target: notepad.exe
│   Dependencies: None
│
│ Step 2: type_text
│   Intent: Type text into editor
│   Expected: Text appears in Notepad
│   Text: 'Hello World'
│   Dependencies: Step 1
│
└──────────────────────────────────────────────────────────────────────
```

### 4. User Approves Plan
```
Approval Status: approved
Approval Actor: local_user
Approval Timestamp: 2026-01-28T10:30:15
```

**Database Update:**
```sql
UPDATE plans 
SET approval_status = 'approved',
    approval_actor = 'local_user',
    approval_timestamp = '2026-01-28T10:30:15'
WHERE plan_id = 42;
```

### 5. Execution Starts
```
Execution Started: 2026-01-28T10:30:16
Status: in_progress
```

**Database Update:**
```sql
UPDATE plans
SET execution_started_at = '2026-01-28T10:30:16',
    execution_status = 'in_progress'
WHERE plan_id = 42;
```

### 6. Actions Executed and Logged

**Action 1: Launch Notepad**
```sql
INSERT INTO action_history (
    plan_id, timestamp, action_type, target,
    success, message
) VALUES (
    42, '2026-01-28T10:30:17', 'launch_app', 'notepad.exe',
    1, 'notepad.exe launched successfully'
);
```

**Action 2: Type Text**
```sql
INSERT INTO action_history (
    plan_id, timestamp, action_type, text_content,
    success, message
) VALUES (
    42, '2026-01-28T10:30:18', 'type_text', 'Hello World',
    1, 'Text typed successfully'
);
```

### 7. Execution Completes
```
Execution Completed: 2026-01-28T10:30:19
Status: completed
```

**Database Update:**
```sql
UPDATE plans
SET execution_completed_at = '2026-01-28T10:30:19',
    execution_status = 'completed'
WHERE plan_id = 42;
```

---

## Audit Queries

### Query 1: Get Complete Plan History
```sql
SELECT 
    plan_id,
    instruction,
    approval_status,
    execution_status,
    created_at,
    execution_started_at,
    execution_completed_at
FROM plans
ORDER BY created_at DESC
LIMIT 10;
```

**Example Output:**
```
plan_id | instruction                      | approval_status | execution_status | created_at           | execution_started_at | execution_completed_at
--------|----------------------------------|-----------------|------------------|----------------------|----------------------|------------------------
42      | Open Notepad and type Hello World| approved        | completed        | 2026-01-28T10:30:00  | 2026-01-28T10:30:16  | 2026-01-28T10:30:19
41      | Close Calculator                 | rejected        | cancelled        | 2026-01-28T10:25:00  | NULL                 | 2026-01-28T10:25:10
40      | Focus Chrome window              | not_required    | completed        | 2026-01-28T10:20:00  | 2026-01-28T10:20:01  | 2026-01-28T10:20:02
```

### Query 2: Get All Actions for a Plan
```sql
SELECT 
    a.timestamp,
    a.action_type,
    a.target,
    a.text_content,
    a.success,
    a.message
FROM action_history a
WHERE a.plan_id = 42
ORDER BY a.timestamp;
```

**Example Output:**
```
timestamp            | action_type | target        | text_content | success | message
---------------------|-------------|---------------|--------------|---------|----------------------------------
2026-01-28T10:30:17  | launch_app  | notepad.exe   | NULL         | 1       | notepad.exe launched successfully
2026-01-28T10:30:18  | type_text   | NULL          | Hello World  | 1       | Text typed successfully
```

### Query 3: Find Failed Plans
```sql
SELECT 
    p.plan_id,
    p.instruction,
    p.execution_status,
    a.action_type,
    a.target,
    a.message,
    a.error
FROM plans p
LEFT JOIN action_history a ON p.plan_id = a.plan_id
WHERE p.execution_status = 'failed'
ORDER BY p.created_at DESC, a.timestamp;
```

**Example Output:**
```
plan_id | instruction        | execution_status | action_type | target    | message           | error
--------|--------------------|--------------------|-------------|-----------|-------------------|-------------------
38      | Click OK button    | failed             | click       | OK        | Verification failed| Element not found
```

### Query 4: Approval Decision History
```sql
SELECT 
    plan_id,
    instruction,
    approval_status,
    approval_actor,
    approval_timestamp,
    execution_status
FROM plans
WHERE approval_required = 1
ORDER BY created_at DESC;
```

**Example Output:**
```
plan_id | instruction              | approval_status | approval_actor | approval_timestamp   | execution_status
--------|--------------------------|-----------------|----------------|----------------------|------------------
42      | Open Notepad and type... | approved        | local_user     | 2026-01-28T10:30:15  | completed
41      | Close Calculator         | rejected        | local_user     | 2026-01-28T10:25:10  | cancelled
39      | Launch regedit           | pending         | NULL           | NULL                 | pending
```

### Query 5: Execution Time Analysis
```sql
SELECT 
    plan_id,
    instruction,
    execution_status,
    JULIANDAY(execution_completed_at) - JULIANDAY(execution_started_at) * 86400 AS duration_seconds
FROM plans
WHERE execution_status = 'completed'
ORDER BY duration_seconds DESC
LIMIT 10;
```

### Query 6: Success Rate by Instruction Pattern
```sql
SELECT 
    SUBSTR(instruction, 1, 20) AS instruction_pattern,
    COUNT(*) AS total_plans,
    SUM(CASE WHEN execution_status = 'completed' THEN 1 ELSE 0 END) AS successful,
    ROUND(100.0 * SUM(CASE WHEN execution_status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_rate
FROM plans
GROUP BY instruction_pattern
ORDER BY total_plans DESC;
```

### Query 7: Actions Without Plans (Legacy Data)
```sql
SELECT 
    timestamp,
    action_type,
    target,
    success
FROM action_history
WHERE plan_id IS NULL
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Complete Lifecycle States

### Plan Approval Status
- `pending` - Waiting for user approval
- `approved` - User approved the plan
- `rejected` - User rejected the plan
- `not_required` - Plan doesn't require approval

### Plan Execution Status
- `pending` - Plan created, not yet started
- `in_progress` - Currently executing
- `completed` - All actions succeeded
- `failed` - At least one action failed
- `cancelled` - Rejected by user before execution

---

## Temporal Tracking

Every plan has complete temporal tracking:

1. **created_at** - When plan was generated
2. **approval_timestamp** - When user made approval decision (if required)
3. **execution_started_at** - When execution began
4. **execution_completed_at** - When execution ended (success or failure)

This enables:
- Execution duration analysis
- Approval delay tracking
- Time-of-day pattern analysis
- Performance optimization

---

## Audit Trail Use Cases

### 1. Debugging Failed Plans
```sql
-- Find the plan that failed
SELECT plan_id, instruction, plan_json 
FROM plans 
WHERE execution_status = 'failed' 
ORDER BY created_at DESC LIMIT 1;

-- Get all actions for that plan
SELECT * FROM action_history 
WHERE plan_id = [failed_plan_id] 
ORDER BY timestamp;

-- Reconstruct the plan from JSON for replay/analysis
```

### 2. User Activity Review
```sql
-- What did the agent do today?
SELECT 
    p.created_at,
    p.instruction,
    p.execution_status,
    COUNT(a.id) AS action_count
FROM plans p
LEFT JOIN action_history a ON p.plan_id = a.plan_id
WHERE DATE(p.created_at) = DATE('now')
GROUP BY p.plan_id
ORDER BY p.created_at;
```

### 3. Security Audit
```sql
-- Check all rejected/cancelled plans
SELECT 
    instruction,
    approval_status,
    approval_timestamp,
    execution_status
FROM plans
WHERE approval_status = 'rejected' OR execution_status = 'cancelled'
ORDER BY created_at DESC;
```

### 4. Performance Analysis
```sql
-- Average execution time by action type
SELECT 
    a.action_type,
    COUNT(*) AS count,
    AVG(JULIANDAY(a.timestamp) - JULIANDAY(p.execution_started_at)) * 86400 AS avg_seconds
FROM action_history a
JOIN plans p ON a.plan_id = p.plan_id
WHERE p.execution_status = 'completed'
GROUP BY a.action_type
ORDER BY avg_seconds DESC;
```

---

## Backward Compatibility

Phase-5B maintains full backward compatibility:

- Old action_history rows have `plan_id = NULL`
- These rows are still queryable and valid
- No data loss during migration
- Schema migration is safe and idempotent

**Example Query Including Legacy Data:**
```sql
SELECT 
    timestamp,
    action_type,
    target,
    CASE 
        WHEN plan_id IS NULL THEN 'Legacy Action'
        ELSE 'Plan ' || plan_id
    END AS source
FROM action_history
ORDER BY timestamp DESC
LIMIT 20;
```

---

## Status: COMPLETE ✅

Phase-5B provides a complete, queryable audit trail from instruction through planning, approval, execution, and results.
