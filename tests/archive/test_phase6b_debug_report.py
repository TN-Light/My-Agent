"""
Phase-6B Test Suite - Post-Execution Debug Reporting

Tests:
1. Successful plan report
2. Failed plan report
3. Cancelled plan report (plan rejection)
4. Cancelled plan report (step rejection)
5. Verification evidence inclusion
6. Timeline reconstruction
7. Root cause analysis
"""

import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action, ActionResult
from storage.plan_logger import PlanLogger
from storage.action_logger import ActionLogger
from storage.step_approval_logger import StepApprovalLogger
from storage.debug_reporter import DebugReporter


def setup_test_plan_successful():
    """Create a successful plan for testing."""
    plan_logger = PlanLogger(db_path="db/test_debug.db")
    action_logger = ActionLogger(db_path="db/test_debug_history.db")
    
    # Create plan
    instruction = "Open Notepad and type test"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe"),
            intent="Launch Notepad",
            expected_outcome="Notepad opens"
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="type_text", text="test"),
            intent="Type text",
            expected_outcome="Text appears"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
    
    # Log successful actions
    for step in steps:
        result = ActionResult(
            action=step.item,
            success=True,
            message=f"{step.item.action_type} successful"
        )
        action_logger.log_action(result, plan_id=plan_id)
    
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return plan_id


def setup_test_plan_failed():
    """Create a failed plan for testing."""
    plan_logger = PlanLogger(db_path="db/test_debug.db")
    action_logger = ActionLogger(db_path="db/test_debug_history.db")
    
    # Create plan
    instruction = "Click nonexistent button"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe"),
            intent="Launch Notepad",
            expected_outcome="Notepad opens"
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="type_text", text="test"),
            intent="Click button",
            expected_outcome="Button clicked"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
    
    # Log successful action
    result1 = ActionResult(
        action=steps[0].item,
        success=True,
        message="notepad.exe launched"
    )
    action_logger.log_action(result1, plan_id=plan_id)
    
    # Log failed action with verification evidence
    result2 = ActionResult(
        action=steps[1].item,
        success=False,
        message="Verification failed",
        error="Element not found",
        verification_evidence={
            'source': 'UIA',
            'confidence': 0.0,
            'checked_text': 'Button',
            'sample': 'No matching element'
        }
    )
    action_logger.log_action(result2, plan_id=plan_id)
    
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "failed")
    
    plan_logger.close()
    action_logger.close()
    
    return plan_id


def setup_test_plan_cancelled_plan_rejection():
    """Create a plan cancelled by plan-level rejection."""
    plan_logger = PlanLogger(db_path="db/test_debug.db")
    
    instruction = "Close important app"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="close_app", target="important.exe"),
            intent="Close app",
            expected_outcome="App closes",
            requires_approval=True
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    
    # User rejects plan
    plan_logger.update_approval(plan_id, approved=False, actor="local_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "cancelled")
    
    plan_logger.close()
    
    return plan_id


def setup_test_plan_cancelled_step_rejection():
    """Create a plan cancelled by step-level rejection."""
    plan_logger = PlanLogger(db_path="db/test_debug.db")
    step_approval_logger = StepApprovalLogger(db_path="db/test_debug.db")
    
    instruction = "Multi-step plan with rejection"
    steps = [
        PlanStep(
            step_id=1,
            item=Action(action_type="launch_app", target="notepad.exe"),
            intent="Launch Notepad",
            expected_outcome="Notepad opens",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(action_type="close_app", target="notepad.exe"),
            intent="Close Notepad",
            expected_outcome="Notepad closes",
            requires_approval=True
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(plan_id, approved=True, actor="local_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
    
    # Approve step 1
    step_approval_logger.log_step_decision(
        plan_id, 1, 'approved', datetime.now().isoformat()
    )
    
    # Reject step 2
    step_approval_logger.log_step_decision(
        plan_id, 2, 'rejected', datetime.now().isoformat(), reason="Unsafe operation"
    )
    
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "cancelled")
    
    plan_logger.close()
    step_approval_logger.close()
    
    return plan_id


def test_1_successful_plan_report():
    """Test debug report for successful plan."""
    print("\n=== Test 1: Successful Plan Report ===")
    
    plan_id = setup_test_plan_successful()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Generate report
    report = reporter.generate_debug_report(plan_id)
    
    # Verify report content
    assert f"PLAN {plan_id}" in report, "Report should include plan ID"
    assert "Open Notepad and type test" in report, "Report should include instruction"
    assert "execution_completed" in report.lower(), "Report should show completion"
    assert "completed" in report.lower(), "Report should show completed status"
    assert "SUCCESS" in report, "Report should show successful actions"
    
    reporter.close()
    print("✅ Test 1 PASSED: Successful plan report generated")


def test_2_failed_plan_report():
    """Test debug report for failed plan."""
    print("\n=== Test 2: Failed Plan Report ===")
    
    plan_id = setup_test_plan_failed()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Generate report
    report = reporter.generate_debug_report(plan_id)
    
    # Verify report content
    assert "ROOT CAUSE ANALYSIS" in report, "Report should include root cause analysis"
    assert "FAILED" in report, "Report should show failed status"
    assert "Element not found" in report, "Report should include error message"
    assert "Verification Source: UIA" in report, "Report should include verification evidence"
    
    # Get root cause
    root_cause = reporter.get_failure_root_cause(plan_id)
    assert root_cause['failure'] == True, "Should identify as failure"
    assert root_cause['root_cause'] == 'action_failed', "Should identify action failure"
    assert root_cause['error'] == "Element not found", "Should include error"
    
    reporter.close()
    print("✅ Test 2 PASSED: Failed plan report generated with root cause")


def test_3_cancelled_plan_rejection_report():
    """Test debug report for plan-level rejection."""
    print("\n=== Test 3: Cancelled Plan (Plan Rejection) Report ===")
    
    plan_id = setup_test_plan_cancelled_plan_rejection()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Get root cause
    root_cause = reporter.get_failure_root_cause(plan_id)
    assert root_cause['failure'] == True, "Should identify as failure"
    assert root_cause['root_cause'] == 'plan_rejected', "Should identify plan rejection"
    assert root_cause['status'] == 'cancelled', "Should show cancelled status"
    
    # Generate report
    report = reporter.generate_debug_report(plan_id)
    assert "cancelled" in report.lower(), "Report should show cancelled status"
    assert "rejected" in report.lower(), "Report should mention rejection"
    
    reporter.close()
    print("✅ Test 3 PASSED: Plan rejection report generated")


def test_4_cancelled_step_rejection_report():
    """Test debug report for step-level rejection."""
    print("\n=== Test 4: Cancelled Plan (Step Rejection) Report ===")
    
    plan_id = setup_test_plan_cancelled_step_rejection()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Get root cause
    root_cause = reporter.get_failure_root_cause(plan_id)
    assert root_cause['failure'] == True, "Should identify as failure"
    assert root_cause['root_cause'] == 'step_rejected', "Should identify step rejection"
    assert root_cause['step_id'] == 2, "Should identify rejected step"
    assert root_cause['reason'] == "Unsafe operation", "Should include rejection reason"
    
    # Generate report
    report = reporter.generate_debug_report(plan_id)
    assert "step_approval" in report.lower(), "Report should include step approvals"
    assert "approved" in report.lower(), "Report should show approved step"
    assert "rejected" in report.lower(), "Report should show rejected step"
    assert "Unsafe operation" in report, "Report should include rejection reason"
    
    reporter.close()
    print("✅ Test 4 PASSED: Step rejection report generated")


def test_5_verification_evidence_inclusion():
    """Test that verification evidence is included in reports."""
    print("\n=== Test 5: Verification Evidence Inclusion ===")
    
    plan_id = setup_test_plan_failed()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Build timeline
    timeline = reporter.build_timeline(plan_id)
    
    # Find action with verification evidence
    action_events = [e for e in timeline if e['event_type'] == 'action_executed' and not e['details']['success']]
    assert len(action_events) > 0, "Should have failed action"
    
    failed_action = action_events[0]
    assert failed_action['details']['verification_evidence'] is not None, "Should have verification evidence"
    
    evidence = failed_action['details']['verification_evidence']
    assert evidence['source'] == 'UIA', "Evidence source should be UIA"
    assert evidence['confidence'] == 0.0, "Confidence should be 0.0"
    
    reporter.close()
    print("✅ Test 5 PASSED: Verification evidence included in timeline")


def test_6_timeline_reconstruction():
    """Test timeline reconstruction accuracy."""
    print("\n=== Test 6: Timeline Reconstruction ===")
    
    plan_id = setup_test_plan_successful()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    timeline = reporter.build_timeline(plan_id)
    
    # Verify timeline structure
    assert len(timeline) > 0, "Timeline should not be empty"
    
    # Verify event types present
    event_types = [e['event_type'] for e in timeline]
    assert 'plan_created' in event_types, "Timeline should include plan creation"
    assert 'execution_started' in event_types, "Timeline should include execution start"
    assert 'action_executed' in event_types, "Timeline should include actions"
    assert 'execution_completed' in event_types, "Timeline should include completion"
    
    # Verify chronological order
    timestamps = [e['timestamp'] for e in timeline]
    assert timestamps == sorted(timestamps), "Timeline should be chronologically ordered"
    
    reporter.close()
    print("✅ Test 6 PASSED: Timeline reconstructed accurately")


def test_7_root_cause_determinism():
    """Test that root cause analysis is deterministic."""
    print("\n=== Test 7: Root Cause Determinism ===")
    
    plan_id = setup_test_plan_failed()
    
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    # Get root cause multiple times
    cause1 = reporter.get_failure_root_cause(plan_id)
    cause2 = reporter.get_failure_root_cause(plan_id)
    cause3 = reporter.get_failure_root_cause(plan_id)
    
    # Verify identical results
    assert cause1 == cause2 == cause3, "Root cause analysis should be deterministic"
    assert cause1['root_cause'] == 'action_failed', "Root cause should be consistent"
    
    reporter.close()
    print("✅ Test 7 PASSED: Root cause analysis is deterministic")


def test_8_read_only_operations():
    """Test that reporter has no side effects."""
    print("\n=== Test 8: Read-Only Operations ===")
    
    plan_id = setup_test_plan_successful()
    
    # Get initial state
    conn = sqlite3.connect("db/test_debug.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    initial_plan = cursor.fetchone()
    conn.close()
    
    # Run reporter operations
    reporter = DebugReporter(
        plans_db_path="db/test_debug.db",
        history_db_path="db/test_debug_history.db",
        obs_db_path="db/observations.db"
    )
    
    reporter.build_timeline(plan_id)
    reporter.get_failure_root_cause(plan_id)
    reporter.generate_debug_report(plan_id)
    
    reporter.close()
    
    # Verify no changes
    conn = sqlite3.connect("db/test_debug.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
    final_plan = cursor.fetchone()
    conn.close()
    
    assert initial_plan == final_plan, "Reporter should not modify database"
    
    print("✅ Test 8 PASSED: Reporter has no side effects (read-only)")


def cleanup_test_databases():
    """Clean up test databases."""
    test_dbs = ["db/test_debug.db", "db/test_debug_history.db"]
    for db_path in test_dbs:
        if os.path.exists(db_path):
            os.remove(db_path)
    print("\n🧹 Test databases cleaned up")


def run_all_tests():
    """Run all Phase-6B tests."""
    print("=" * 70)
    print("PHASE-6B TEST SUITE - POST-EXECUTION DEBUG REPORTING")
    print("=" * 70)
    
    try:
        # Clean up before tests
        cleanup_test_databases()
        
        # Run tests
        test_1_successful_plan_report()
        test_2_failed_plan_report()
        test_3_cancelled_plan_rejection_report()
        test_4_cancelled_step_rejection_report()
        test_5_verification_evidence_inclusion()
        test_6_timeline_reconstruction()
        test_7_root_cause_determinism()
        test_8_read_only_operations()
        
        # Clean up after tests
        cleanup_test_databases()
        
        print("\n" + "=" * 70)
        print("✅ ALL PHASE-6B TESTS PASSED (8/8)")
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
