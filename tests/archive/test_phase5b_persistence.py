"""
Phase-5B Test Suite - Plan Persistence and Audit Trail

Tests:
1. Plan saved before execution
2. Approval recorded correctly
3. Rejected plan never executes
4. Actions linked to correct plan_id
5. Execution failure marks plan as failed
6. JSON serialization round-trip
7. Backward compatibility (plan_id NULL rows)
"""

import sys
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action
from common.observations import Observation
from storage.plan_logger import PlanLogger
from storage.action_logger import ActionLogger


def test_1_plan_saved_before_execution():
    """Test that plans are persisted with all metadata."""
    print("\n=== Test 1: Plan Saved Before Execution ===")
    
    # Create test plan
    instruction = "Open Notepad and type hello"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe"),
            intent="Open Notepad",
            expected_outcome="Notepad window appears"
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="type", text="hello"),
            intent="Type hello",
            expected_outcome="Text appears in editor"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    # Create logger and save plan
    plan_logger = PlanLogger(db_path="db/test_plans.db")
    plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    
    # Verify plan was saved
    assert plan_id is not None, "Plan ID should be assigned"
    assert plan_id > 0, "Plan ID should be positive"
    
    # Retrieve plan and verify
    saved_plan = plan_logger.get_plan(plan_id)
    assert saved_plan is not None, "Plan should be retrievable"
    assert saved_plan["instruction"] == instruction, "Instruction should match"
    assert saved_plan["total_steps"] == 2, "Step count should match"
    assert saved_plan["total_actions"] == 2, "Action count should match"
    assert saved_plan["total_observations"] == 0, "Observation count should match"
    assert saved_plan["execution_status"] == "pending", "Initial status should be pending"
    
    plan_logger.close()
    print("✅ Test 1 PASSED: Plan persisted with all metadata")


def test_2_approval_recorded():
    """Test that approval decisions are recorded."""
    print("\n=== Test 2: Approval Recorded ===")
    
    # Create plan requiring approval
    instruction = "Close Calculator"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="close_app", target="Calculator"),
            intent="Close Calculator",
            expected_outcome="Calculator closes",
            requires_approval=True
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_logger = PlanLogger(db_path="db/test_plans.db")
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    
    # Record approval
    timestamp = datetime.now().isoformat()
    plan_logger.update_approval(plan_id, approved=True, actor="local_user", timestamp=timestamp)
    
    # Verify approval was recorded
    saved_plan = plan_logger.get_plan(plan_id)
    assert saved_plan["approval_status"] == "approved", "Approval status should be approved"
    assert saved_plan["approval_actor"] == "local_user", "Approval actor should be recorded"
    assert saved_plan["approval_timestamp"] is not None, "Approval timestamp should be recorded"
    
    plan_logger.close()
    print("✅ Test 2 PASSED: Approval recorded correctly")


def test_3_rejected_plan_never_executes():
    """Test that rejected plans are marked as cancelled."""
    print("\n=== Test 3: Rejected Plan Never Executes ===")
    
    # Create plan
    instruction = "Launch Calculator"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="calc.exe"),
            intent="Launch Calculator",
            expected_outcome="Calculator opens",
            requires_approval=True
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_logger = PlanLogger(db_path="db/test_plans.db")
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    
    # Reject plan
    timestamp = datetime.now().isoformat()
    plan_logger.update_approval(plan_id, approved=False, actor="local_user", timestamp=timestamp)
    plan_logger.mark_execution_completed(plan_id, timestamp=timestamp, status="cancelled")
    
    # Verify plan is marked as cancelled
    saved_plan = plan_logger.get_plan(plan_id)
    assert saved_plan["approval_status"] == "rejected", "Approval status should be rejected"
    assert saved_plan["execution_status"] == "cancelled", "Execution status should be cancelled"
    assert saved_plan["execution_started_at"] is None, "Execution should never have started"
    
    plan_logger.close()
    print("✅ Test 3 PASSED: Rejected plan marked as cancelled")


def test_4_actions_linked_to_plan():
    """Test that actions are linked to their parent plan."""
    print("\n=== Test 4: Actions Linked to Plan ===")
    
    # Create action logger
    action_logger = ActionLogger(db_path="db/test_history.db")
    
    # Create test action and result
    from common.actions import ActionResult
    action = Action(action_type="click", target="OK")
    result = ActionResult(
        action=action,
        success=True,
        message="Clicked OK button"
    )
    
    # Log action with plan_id
    test_plan_id = 42
    action_logger.log_action(result, plan_id=test_plan_id)
    
    # Verify action was linked
    conn = sqlite3.connect("db/test_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plan_id FROM action_history ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "Action should be logged"
    assert row[0] == test_plan_id, "Action should be linked to plan"
    
    action_logger.close()
    print("✅ Test 4 PASSED: Actions linked to parent plan")


def test_5_execution_failure_marks_plan():
    """Test that failed executions mark the plan as failed."""
    print("\n=== Test 5: Execution Failure Marks Plan ===")
    
    # Create plan
    instruction = "Click missing button"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="click", target="NonExistentButton"),
            intent="Click button",
            expected_outcome="Button is clicked"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_logger = PlanLogger(db_path="db/test_plans.db")
    plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    
    # Mark execution started
    start_time = datetime.now().isoformat()
    plan_logger.mark_execution_started(plan_id, start_time)
    
    # Mark execution failed
    end_time = datetime.now().isoformat()
    plan_logger.mark_execution_completed(plan_id, end_time, status="failed")
    
    # Verify plan is marked as failed
    saved_plan = plan_logger.get_plan(plan_id)
    assert saved_plan["execution_status"] == "failed", "Execution status should be failed"
    assert saved_plan["execution_started_at"] is not None, "Start time should be recorded"
    assert saved_plan["execution_completed_at"] is not None, "Completion time should be recorded"
    
    plan_logger.close()
    print("✅ Test 5 PASSED: Failed execution marked correctly")


def test_6_json_serialization():
    """Test JSON serialization round-trip for PlanGraph."""
    print("\n=== Test 6: JSON Serialization Round-Trip ===")
    
    # Create complex plan
    instruction = "Mixed plan with actions and observations"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe", context="desktop"),
            intent="Open Notepad",
            expected_outcome="Notepad opens",
            requires_approval=True,
            dependencies=[],
            metadata={"step_info": "first"}
        ),
        PlanStep(
            step_id=2,
            item=Observation(observation_type="read_text", target="window_title", context="desktop"),
            intent="Get window",
            expected_outcome="Window name returned",
            dependencies=[1]
        ),
        PlanStep(
            step_id=3,
            item=Action(action_type="type_text", text="Hello World", context="desktop"),
            intent="Type text",
            expected_outcome="Text appears",
            dependencies=[1, 2]
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    # Serialize to JSON
    json_str = plan_graph.to_json()
    assert json_str is not None, "JSON should be generated"
    
    # Verify it's valid JSON
    data = json.loads(json_str)
    assert data["instruction"] == instruction, "Instruction should match"
    assert len(data["steps"]) == 3, "Step count should match"
    
    # Deserialize back
    restored_graph = PlanGraph.from_json(json_str)
    
    # Verify restoration
    assert restored_graph.instruction == instruction, "Instruction should match after restoration"
    assert len(restored_graph.steps) == 3, "Step count should match"
    
    # Verify first step (Action)
    step1 = restored_graph.steps[0]
    assert step1.step_id == 1, "Step ID should match"
    assert step1.is_action, "Step should be an action"
    assert step1.item.action_type == "launch_app", "Action type should match"
    assert step1.item.target == "notepad.exe", "Target should match"
    assert step1.requires_approval == True, "Approval flag should match"
    assert step1.metadata["step_info"] == "first", "Metadata should match"
    
    # Verify second step (Observation)
    step2 = restored_graph.steps[1]
    assert step2.is_observation, "Step should be an observation"
    assert step2.item.observation_type == "read_text", "Observation type should match"
    assert step2.dependencies == [1], "Dependencies should match"
    
    # Verify third step (Action with text)
    step3 = restored_graph.steps[2]
    assert step3.item.text == "Hello World", "Text should match"
    assert step3.dependencies == [1, 2], "Dependencies should match"
    
    print("✅ Test 6 PASSED: JSON serialization round-trip works correctly")


def test_7_backward_compatibility():
    """Test that NULL plan_id values are supported (backward compatibility)."""
    print("\n=== Test 7: Backward Compatibility ===")
    
    # Create action without plan_id
    action_logger = ActionLogger(db_path="db/test_history.db")
    
    from common.actions import ActionResult
    action = Action(action_type="click", target="Button")
    result = ActionResult(
        action=action,
        success=True,
        message="Clicked button"
    )
    
    # Log action WITHOUT plan_id (backward compatibility)
    action_logger.log_action(result, plan_id=None)
    
    # Verify action was logged with NULL plan_id
    conn = sqlite3.connect("db/test_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plan_id FROM action_history ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "Action should be logged"
    assert row[0] is None, "plan_id should be NULL for backward compatibility"
    
    action_logger.close()
    print("✅ Test 7 PASSED: Backward compatibility maintained (NULL plan_id)")


def test_8_execution_lifecycle():
    """Test complete execution lifecycle tracking."""
    print("\n=== Test 8: Execution Lifecycle Tracking ===")
    
    # Create plan
    instruction = "Complete lifecycle test"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="click", target="Test"),
            intent="Test action",
            expected_outcome="Action completes"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_logger = PlanLogger(db_path="db/test_plans.db")
    
    # 1. Log plan (status: pending)
    plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    saved = plan_logger.get_plan(plan_id)
    assert saved["execution_status"] == "pending", "Initial status should be pending"
    
    # 2. Mark execution started (status: in_progress)
    start_time = datetime.now().isoformat()
    plan_logger.mark_execution_started(plan_id, start_time)
    saved = plan_logger.get_plan(plan_id)
    assert saved["execution_status"] == "in_progress", "Status should be in_progress"
    assert saved["execution_started_at"] == start_time, "Start time should be recorded"
    
    # 3. Mark execution completed (status: completed)
    end_time = datetime.now().isoformat()
    plan_logger.mark_execution_completed(plan_id, end_time, status="completed")
    saved = plan_logger.get_plan(plan_id)
    assert saved["execution_status"] == "completed", "Status should be completed"
    assert saved["execution_completed_at"] == end_time, "End time should be recorded"
    
    plan_logger.close()
    print("✅ Test 8 PASSED: Execution lifecycle tracked correctly")


def cleanup_test_databases():
    """Clean up test databases."""
    test_dbs = ["db/test_plans.db", "db/test_history.db"]
    for db_path in test_dbs:
        if os.path.exists(db_path):
            os.remove(db_path)
    print("\n🧹 Test databases cleaned up")


def run_all_tests():
    """Run all Phase-5B tests."""
    print("=" * 70)
    print("PHASE-5B TEST SUITE - PLAN PERSISTENCE AND AUDIT TRAIL")
    print("=" * 70)
    
    try:
        # Clean up before tests
        cleanup_test_databases()
        
        # Run tests
        test_1_plan_saved_before_execution()
        test_2_approval_recorded()
        test_3_rejected_plan_never_executes()
        test_4_actions_linked_to_plan()
        test_5_execution_failure_marks_plan()
        test_6_json_serialization()
        test_7_backward_compatibility()
        test_8_execution_lifecycle()
        
        # Clean up after tests
        cleanup_test_databases()
        
        print("\n" + "=" * 70)
        print("✅ ALL PHASE-5B TESTS PASSED (8/8)")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("=" * 70)
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 70)
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
