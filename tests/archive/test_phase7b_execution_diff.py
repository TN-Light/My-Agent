"""
Phase-7B Test Suite - Execution Diff Comparison

Tests deterministic comparison of two plan executions.
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime
import json
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from storage.execution_diff import ExecutionDiff, DiffResult, StepDiff
from storage.plan_logger import PlanLogger
from storage.step_approval_logger import StepApprovalLogger
from storage.action_logger import ActionLogger
from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action, ActionResult


# Test database paths
TEST_PLANS_DB = "db/test_plans_diff.db"
TEST_HISTORY_DB = "db/test_history_diff.db"
TEST_OBS_DB = "db/test_observations_diff.db"


def create_action_result(action: Action, success: bool, error: str = None) -> ActionResult:
    """Helper to create ActionResult for testing."""
    return ActionResult(
        action=action,
        success=success,
        message="OK" if success else None,
        error=error,
        verification_evidence=None
    )


def cleanup_test_databases():
    """Remove test databases if they exist."""
    import gc
    import time
    
    # Force garbage collection to close any open connections
    gc.collect()
    time.sleep(0.1)
    
    for db_path in [TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB]:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass


def setup_identical_executions():
    """
    Create two identical plan executions for testing.
    
    Returns:
        (original_plan_id, replay_plan_id)
    """
    # Create plan
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe", verify=False),
            intent="Launch notepad",
            expected_outcome="Notepad appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="wait", target="1", verify=False),
            intent="Wait 1 second",
            expected_outcome="Brief pause",
            requires_approval=False
        )
    ]
    
    plan_graph = PlanGraph(instruction="launch notepad", steps=steps)
    
    # Create original execution
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    action_logger = ActionLogger(db_path=TEST_HISTORY_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    
    original_plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(original_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(original_plan_id, datetime.now().isoformat())
    
    # Log actions
    action_logger.log_action(
        create_action_result(steps[0].item, success=True),
        plan_id=original_plan_id
    )
    action_logger.log_action(
        create_action_result(steps[1].item, success=True),
        plan_id=original_plan_id
    )
    
    # Log step approvals
    step_approval_logger.log_step_decision(
        original_plan_id, 1, "approved",
        timestamp=datetime.now().isoformat()
    )
    
    time.sleep(0.1)  # Small delay for timing
    plan_logger.mark_execution_completed(original_plan_id, datetime.now().isoformat(), "completed")
    
    # Create replay execution (identical)
    time.sleep(0.1)  # Ensure different timestamps
    
    replay_plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(replay_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(replay_plan_id, datetime.now().isoformat())
    
    # Log actions (identical)
    action_logger.log_action(
        create_action_result(steps[0].item, success=True),
        plan_id=replay_plan_id
    )
    action_logger.log_action(
        create_action_result(steps[1].item, success=True),
        plan_id=replay_plan_id
    )
    
    # Log step approvals (identical)
    step_approval_logger.log_step_decision(
        replay_plan_id, 1, "approved",
        timestamp=datetime.now().isoformat()
    )
    
    time.sleep(0.1)
    plan_logger.mark_execution_completed(replay_plan_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return original_plan_id, replay_plan_id


def setup_different_approvals():
    """
    Create two executions with different approval decisions.
    
    Returns:
        (original_plan_id, replay_plan_id)
    """
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe", verify=False),
            intent="Launch notepad",
            expected_outcome="Notepad appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="type_text", text="hello", verify=False),
            intent="Type text",
            expected_outcome="Text appears",
            requires_approval=True
        )
    ]
    
    plan_graph = PlanGraph(instruction="launch notepad and type", steps=steps)
    
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    action_logger = ActionLogger(db_path=TEST_HISTORY_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    
    # Original: both approved
    original_plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(original_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(original_plan_id, datetime.now().isoformat())
    
    step_approval_logger.log_step_decision(original_plan_id, 1, "approved", timestamp=datetime.now().isoformat())
    step_approval_logger.log_step_decision(original_plan_id, 2, "approved", timestamp=datetime.now().isoformat())
    
    action_logger.log_action(
        create_action_result(steps[0].item, success=True),
        plan_id=original_plan_id
    )
    action_logger.log_action(
        create_action_result(steps[1].item, success=True),
        plan_id=original_plan_id
    )
    
    plan_logger.mark_execution_completed(original_plan_id, datetime.now().isoformat(), "completed")
    
    # Replay: step 2 skipped
    time.sleep(0.1)
    
    replay_plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(replay_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(replay_plan_id, datetime.now().isoformat())
    
    step_approval_logger.log_step_decision(replay_plan_id, 1, "approved", timestamp=datetime.now().isoformat())
    step_approval_logger.log_step_decision(replay_plan_id, 2, "skipped", timestamp=datetime.now().isoformat())  # DIFFERENT
    
    action_logger.log_action(ActionResult(action=steps[0].item, success=True, message="OK", error=None, verification_evidence=None), plan_id=replay_plan_id)
    # Step 2 not executed (skipped)
    
    plan_logger.mark_execution_completed(replay_plan_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return original_plan_id, replay_plan_id


def setup_failure_vs_success():
    """
    Create two executions: one failed, one succeeded.
    
    Returns:
        (failed_plan_id, success_plan_id)
    """
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe", verify=False),
            intent="Launch notepad",
            expected_outcome="Notepad appears",
            requires_approval=False
        )
    ]
    
    plan_graph = PlanGraph(instruction="launch notepad", steps=steps)
    
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    action_logger = ActionLogger(db_path=TEST_HISTORY_DB)
    
    # Failed execution
    failed_plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.update_approval(failed_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(failed_plan_id, datetime.now().isoformat())
    
    action_logger.log_action(ActionResult(action=steps[0].item, success=False, message=None, error="Application not found", verification_evidence=None), plan_id=failed_plan_id)
    
    plan_logger.mark_execution_completed(failed_plan_id, datetime.now().isoformat(), "failed")
    
    # Successful execution
    time.sleep(0.1)
    
    success_plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.update_approval(success_plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(success_plan_id, datetime.now().isoformat())
    
    action_logger.log_action(ActionResult(action=steps[0].item, success=True, message="OK", error=None, verification_evidence=None), plan_id=success_plan_id)
    
    plan_logger.mark_execution_completed(success_plan_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return failed_plan_id, success_plan_id


# ============================
# TEST CASES
# ============================

def test_identical_executions():
    """
    Test 1: Identical executions → empty diff
    
    Verifies:
    - No differences detected when executions are identical
    - has_differences = False
    - Empty diff report
    """
    print("\n" + "="*70)
    print("=== Test 1: Identical Executions (Empty Diff) ===")
    print("="*70)
    
    # Setup
    original_id, replay_id = setup_identical_executions()
    
    # Create diff tool
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    # Generate diff
    result = diff_tool.diff_plans(original_id, replay_id)
    
    # Verify
    assert result.has_differences == False, "Identical executions should have no differences"
    assert len(result.differences) == 0, f"Expected 0 differences, got {len(result.differences)}"
    assert result.original_plan_id == original_id
    assert result.replay_plan_id == replay_id
    
    # Check text output
    text_report = result.to_text()
    assert "NO DIFFERENCES DETECTED" in text_report
    
    print(text_report)
    print("\n✅ Test 1 PASSED: Identical executions produce empty diff")


def test_different_approvals():
    """
    Test 2: Different approval decisions
    
    Verifies:
    - Approval differences are detected
    - Correct dimension ("approval")
    - Accurate original vs replay values
    """
    print("\n" + "="*70)
    print("=== Test 2: Different Approval Decisions ===")
    print("="*70)
    
    # Setup
    original_id, replay_id = setup_different_approvals()
    
    # Create diff tool
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    # Generate diff
    result = diff_tool.diff_plans(original_id, replay_id)
    
    # Verify
    assert result.has_differences == True, "Should detect differences"
    assert len(result.approval_diffs) > 0, "Should have approval differences"
    
    # Check for step 2 approval difference
    step2_diffs = [d for d in result.approval_diffs if d.step_id == 2]
    assert len(step2_diffs) == 1, "Should detect step 2 approval difference"
    
    diff = step2_diffs[0]
    assert diff.original_value == "approved"
    assert diff.replay_value == "skipped"
    assert diff.dimension == "approval"
    
    # Check execution differences (fewer actions in replay)
    assert len(result.execution_diffs) > 0, "Should detect execution differences (action count)"
    
    text_report = result.to_text()
    assert "Approval Differences" in text_report
    print(text_report)
    
    print("\n✅ Test 2 PASSED: Approval differences detected correctly")


def test_failure_vs_success():
    """
    Test 3: Failed execution vs successful execution
    
    Verifies:
    - Execution status differences detected
    - Action success/failure differences detected
    - Correct dimension ("execution")
    """
    print("\n" + "="*70)
    print("=== Test 3: Failed vs Successful Execution ===")
    print("="*70)
    
    # Setup
    failed_id, success_id = setup_failure_vs_success()
    
    # Create diff tool
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    # Generate diff
    result = diff_tool.diff_plans(failed_id, success_id)
    
    # Verify
    assert result.has_differences == True, "Should detect differences"
    assert len(result.execution_diffs) > 0, "Should have execution differences"
    
    # Check for execution status difference
    status_diffs = [d for d in result.execution_diffs if d.step_id == 0 and "status" in d.description.lower()]
    assert len(status_diffs) > 0, "Should detect execution status difference"
    
    # Check for action success/failure difference
    action_diffs = [d for d in result.execution_diffs if d.step_id > 0]
    assert len(action_diffs) > 0, "Should detect action execution result difference"
    
    text_report = result.to_text()
    assert "Execution Differences" in text_report
    print(text_report)
    
    print("\n✅ Test 3 PASSED: Failure vs success differences detected")


def test_deterministic_output():
    """
    Test 4: Deterministic output
    
    Verifies:
    - Running diff twice produces identical results
    - DiffResult is deterministic
    - Text output is consistent
    """
    print("\n" + "="*70)
    print("=== Test 4: Deterministic Output ===")
    print("="*70)
    
    # Setup
    original_id, replay_id = setup_different_approvals()
    
    # Create diff tool
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    # Generate diff twice
    result1 = diff_tool.diff_plans(original_id, replay_id)
    result2 = diff_tool.diff_plans(original_id, replay_id)
    
    # Verify identical results
    assert len(result1.differences) == len(result2.differences), "Should produce same number of differences"
    assert result1.has_differences == result2.has_differences
    
    # Check text output is identical
    text1 = result1.to_text()
    text2 = result2.to_text()
    assert text1 == text2, "Text output should be deterministic"
    
    print("First run:")
    print(text1)
    print("\nSecond run:")
    print(text2)
    
    print("\n✅ Test 4 PASSED: Output is deterministic")


def test_missing_plan():
    """
    Test 5: Graceful handling of missing plan
    
    Verifies:
    - Handles missing original plan gracefully
    - Handles missing replay plan gracefully
    - Returns valid DiffResult with error message
    """
    print("\n" + "="*70)
    print("=== Test 5: Missing Plan Handling ===")
    print("="*70)
    
    # Create diff tool
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    # Test missing original plan
    result = diff_tool.diff_plans(9999, 1)
    assert "ERROR" in result.instruction or result.instruction == "ERROR: Original plan not found"
    print(f"Missing original: {result.instruction}")
    
    # Test missing replay plan
    original_id, _ = setup_identical_executions()
    result = diff_tool.diff_plans(original_id, 9999)
    assert result.original_plan_id == original_id
    assert result.replay_plan_id == 9999
    print(f"Missing replay: handled gracefully")
    
    print("\n✅ Test 5 PASSED: Missing plans handled gracefully")


def test_read_only():
    """
    Test 6: Read-only operations (no database modifications)
    
    Verifies:
    - No database writes during diff
    - Database state unchanged after diff
    """
    print("\n" + "="*70)
    print("=== Test 6: Read-Only Operations ===")
    print("="*70)
    
    # Setup
    original_id, replay_id = setup_identical_executions()
    
    # Count records before
    plans_conn = sqlite3.connect(TEST_PLANS_DB)
    history_conn = sqlite3.connect(TEST_HISTORY_DB)
    
    plans_count_before = plans_conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
    actions_count_before = history_conn.execute("SELECT COUNT(*) FROM action_history").fetchone()[0]
    
    plans_conn.close()
    history_conn.close()
    
    # Create diff tool and run diff
    diff_tool = ExecutionDiff(
        plans_db_path=TEST_PLANS_DB,
        history_db_path=TEST_HISTORY_DB,
        observations_db_path=TEST_OBS_DB
    )
    
    result = diff_tool.diff_plans(original_id, replay_id)
    
    # Count records after
    plans_conn = sqlite3.connect(TEST_PLANS_DB)
    history_conn = sqlite3.connect(TEST_HISTORY_DB)
    
    plans_count_after = plans_conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
    actions_count_after = history_conn.execute("SELECT COUNT(*) FROM action_history").fetchone()[0]
    
    plans_conn.close()
    history_conn.close()
    
    # Verify no changes
    assert plans_count_before == plans_count_after, "Plans database should be unchanged"
    assert actions_count_before == actions_count_after, "History database should be unchanged"
    
    print(f"Plans before: {plans_count_before}, after: {plans_count_after}")
    print(f"Actions before: {actions_count_before}, after: {actions_count_after}")
    
    print("\n✅ Test 6 PASSED: No database modifications (read-only)")


def main():
    """Run all Phase-7B tests."""
    print("\n" + "="*70)
    print("PHASE-7B TEST SUITE - EXECUTION DIFF COMPARISON")
    print("="*70)
    
    # Cleanup before tests
    print("\n🧹 Test databases cleaned up")
    cleanup_test_databases()
    
    # Run tests
    try:
        test_identical_executions()
        test_different_approvals()
        test_failure_vs_success()
        test_deterministic_output()
        test_missing_plan()
        test_read_only()
        
        # Cleanup after tests
        print("\n🧹 Test databases cleaned up")
        cleanup_test_databases()
        
        print("\n" + "="*70)
        print("✅ ALL PHASE-7B TESTS PASSED (6/6)")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        cleanup_test_databases()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup_test_databases()
        sys.exit(1)


if __name__ == "__main__":
    main()
