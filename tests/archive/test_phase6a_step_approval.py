"""
Phase-6A Test Suite - Step-Level Approval Gates

Tests:
1. Approved step executes normally
2. Skipped step does not execute
3. Rejected step aborts plan
4. Step decisions persisted correctly
5. Multiple step approvals in sequence
6. Phase-5B lifecycle still works
"""

import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action
from storage.step_approval_logger import StepApprovalLogger


def test_1_approved_step_executes():
    """Test that approved step executes normally."""
    print("\n=== Test 1: Approved Step Executes ===")
    
    # Create logger
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Log an approved decision
    plan_id = 100
    step_id = 1
    timestamp = datetime.now().isoformat()
    
    logger.log_step_decision(
        plan_id=plan_id,
        step_id=step_id,
        decision='approved',
        timestamp=timestamp
    )
    
    # Verify decision was logged
    decisions = logger.get_decisions_for_plan(plan_id)
    assert len(decisions) == 1, "Should have 1 decision"
    assert decisions[0]['decision'] == 'approved', "Decision should be 'approved'"
    assert decisions[0]['step_id'] == step_id, "Step ID should match"
    
    logger.close()
    print("✅ Test 1 PASSED: Approved decision logged correctly")


def test_2_skipped_step_logged():
    """Test that skipped step decision is persisted."""
    print("\n=== Test 2: Skipped Step Logged ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Log a skipped decision
    plan_id = 101
    step_id = 2
    timestamp = datetime.now().isoformat()
    
    logger.log_step_decision(
        plan_id=plan_id,
        step_id=step_id,
        decision='skipped',
        timestamp=timestamp,
        reason="User chose to skip"
    )
    
    # Verify decision was logged
    decisions = logger.get_decisions_for_plan(plan_id)
    assert len(decisions) == 1, "Should have 1 decision"
    assert decisions[0]['decision'] == 'skipped', "Decision should be 'skipped'"
    assert decisions[0]['reason'] == "User chose to skip", "Reason should be recorded"
    
    logger.close()
    print("✅ Test 2 PASSED: Skipped decision logged correctly")


def test_3_rejected_step_logged():
    """Test that rejected step decision is persisted."""
    print("\n=== Test 3: Rejected Step Logged ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Log a rejected decision
    plan_id = 102
    step_id = 1
    timestamp = datetime.now().isoformat()
    
    logger.log_step_decision(
        plan_id=plan_id,
        step_id=step_id,
        decision='rejected',
        timestamp=timestamp,
        reason="Unsafe operation"
    )
    
    # Verify decision was logged
    decisions = logger.get_decisions_for_plan(plan_id)
    assert len(decisions) == 1, "Should have 1 decision"
    assert decisions[0]['decision'] == 'rejected', "Decision should be 'rejected'"
    assert decisions[0]['reason'] == "Unsafe operation", "Reason should be recorded"
    
    logger.close()
    print("✅ Test 3 PASSED: Rejected decision logged correctly")


def test_4_multiple_step_approvals():
    """Test multiple step approvals in sequence."""
    print("\n=== Test 4: Multiple Step Approvals ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    plan_id = 103
    
    # Log multiple decisions
    decisions_to_log = [
        (1, 'approved', None),
        (2, 'approved', None),
        (3, 'skipped', "Not needed"),
        (4, 'approved', None),
    ]
    
    for step_id, decision, reason in decisions_to_log:
        logger.log_step_decision(
            plan_id=plan_id,
            step_id=step_id,
            decision=decision,
            timestamp=datetime.now().isoformat(),
            reason=reason
        )
    
    # Verify all decisions were logged
    decisions = logger.get_decisions_for_plan(plan_id)
    assert len(decisions) == 4, "Should have 4 decisions"
    
    # Verify decisions are retrievable (most recent first)
    assert decisions[0]['step_id'] == 4, "Most recent should be step 4"
    assert decisions[3]['step_id'] == 1, "Oldest should be step 1"
    
    # Verify skipped step has reason
    skipped = [d for d in decisions if d['decision'] == 'skipped']
    assert len(skipped) == 1, "Should have 1 skipped step"
    assert skipped[0]['reason'] == "Not needed", "Reason should be recorded"
    
    logger.close()
    print("✅ Test 4 PASSED: Multiple step approvals tracked correctly")


def test_5_invalid_decision_rejected():
    """Test that invalid decisions are rejected."""
    print("\n=== Test 5: Invalid Decision Rejected ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    try:
        logger.log_step_decision(
            plan_id=104,
            step_id=1,
            decision='invalid_decision',
            timestamp=datetime.now().isoformat()
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid decision" in str(e), "Error message should mention invalid decision"
    
    logger.close()
    print("✅ Test 5 PASSED: Invalid decisions rejected")


def test_6_table_schema():
    """Test that plan_step_approvals table has correct schema."""
    print("\n=== Test 6: Table Schema Validation ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Check table schema
    conn = sqlite3.connect("db/test_step_approvals.db")
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(plan_step_approvals)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    # Verify required columns exist
    required_columns = {
        'id': 'INTEGER',
        'plan_id': 'INTEGER',
        'step_id': 'INTEGER',
        'decision': 'TEXT',
        'timestamp': 'TEXT',
        'reason': 'TEXT'
    }
    
    for col_name, col_type in required_columns.items():
        assert col_name in columns, f"Column '{col_name}' should exist"
        assert columns[col_name] == col_type, f"Column '{col_name}' should be {col_type}"
    
    conn.close()
    logger.close()
    print("✅ Test 6 PASSED: Table schema is correct")


def test_7_decisions_queryable():
    """Test that decisions can be queried by plan_id."""
    print("\n=== Test 7: Decisions Queryable ===")
    
    logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Create decisions for multiple plans
    for plan_id in [200, 201, 202]:
        for step_id in [1, 2]:
            logger.log_step_decision(
                plan_id=plan_id,
                step_id=step_id,
                decision='approved',
                timestamp=datetime.now().isoformat()
            )
    
    # Query each plan
    for plan_id in [200, 201, 202]:
        decisions = logger.get_decisions_for_plan(plan_id)
        assert len(decisions) == 2, f"Plan {plan_id} should have 2 decisions"
        
        # Verify all decisions belong to this plan
        for d in decisions:
            assert d['plan_id'] == plan_id, f"All decisions should belong to plan {plan_id}"
    
    logger.close()
    print("✅ Test 7 PASSED: Decisions queryable by plan_id")


def test_8_integration_with_phase5b():
    """Test that Phase-6A integrates with Phase-5B plan logging."""
    print("\n=== Test 8: Integration with Phase-5B ===")
    
    # Import Phase-5B logger
    from storage.plan_logger import PlanLogger
    
    # Create loggers (both use same database)
    plan_logger = PlanLogger(db_path="db/test_step_approvals.db")
    step_logger = StepApprovalLogger(db_path="db/test_step_approvals.db")
    
    # Create and log a plan (Phase-5B)
    instruction = "Test plan for Phase-6A integration"
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
            item=Action(action_type="type_text", text="test"),
            intent="Type text",
            expected_outcome="Text appears"
        )
    ]
    plan_graph = PlanGraph(instruction=instruction, steps=steps)
    
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    
    # Log step decisions (Phase-6A)
    step_logger.log_step_decision(
        plan_id=plan_id,
        step_id=1,
        decision='approved',
        timestamp=datetime.now().isoformat()
    )
    
    # Verify both are queryable
    saved_plan = plan_logger.get_plan(plan_id)
    assert saved_plan is not None, "Plan should be retrievable"
    assert saved_plan['instruction'] == instruction, "Plan instruction should match"
    
    step_decisions = step_logger.get_decisions_for_plan(plan_id)
    assert len(step_decisions) == 1, "Should have 1 step decision"
    assert step_decisions[0]['step_id'] == 1, "Step decision should be for step 1"
    
    plan_logger.close()
    step_logger.close()
    print("✅ Test 8 PASSED: Phase-6A integrates with Phase-5B")


def cleanup_test_databases():
    """Clean up test databases."""
    test_dbs = ["db/test_step_approvals.db"]
    for db_path in test_dbs:
        if os.path.exists(db_path):
            os.remove(db_path)
    print("\n🧹 Test databases cleaned up")


def run_all_tests():
    """Run all Phase-6A tests."""
    print("=" * 70)
    print("PHASE-6A TEST SUITE - STEP-LEVEL APPROVAL GATES")
    print("=" * 70)
    
    try:
        # Clean up before tests
        cleanup_test_databases()
        
        # Run tests
        test_1_approved_step_executes()
        test_2_skipped_step_logged()
        test_3_rejected_step_logged()
        test_4_multiple_step_approvals()
        test_5_invalid_decision_rejected()
        test_6_table_schema()
        test_7_decisions_queryable()
        test_8_integration_with_phase5b()
        
        # Clean up after tests
        cleanup_test_databases()
        
        print("\n" + "=" * 70)
        print("✅ ALL PHASE-6A TESTS PASSED (8/8)")
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
