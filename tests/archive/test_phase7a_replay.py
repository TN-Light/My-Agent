"""
Phase-7A Test Suite - Deterministic Plan Replay

Tests replay engine functionality with human-controlled execution.
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from replay_engine import ReplayEngine
from storage.plan_logger import PlanLogger
from storage.step_approval_logger import StepApprovalLogger
from execution.controller import Controller
from logic.critic import Critic
from logic.policy_engine import PolicyEngine
from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action
from common.observations import Observation


# Test database paths
TEST_PLANS_DB = "db/test_plans_replay.db"
TEST_HISTORY_DB = "db/test_history_replay.db"
TEST_OBS_DB = "db/test_observations_replay.db"


def cleanup_test_databases():
    """Remove test databases if they exist."""
    import gc
    import time
    
    # Force garbage collection to close any open connections
    gc.collect()
    time.sleep(0.1)  # Brief pause for file handles to release
    
    for db_path in [TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB]:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                # Database still locked, skip cleanup
                pass


def setup_test_plan_successful() -> int:
    """
    Create a successful plan in database for replay testing.
    
    Returns:
        plan_id of created plan
    """
    # Create simple plan
    steps = [
        PlanStep(
            step_id=1,
            item=Action(
                action_type="launch_app",
                target="notepad.exe",
                verify=False
            ),
            intent="Launch notepad application",
            expected_outcome="Notepad window appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(
                action_type="wait",
                target="1",  # Duration in seconds
                verify=False
            ),
            intent="Wait 1 second",
            expected_outcome="Brief pause",
            requires_approval=False
        )
    ]
    
    plan_graph = PlanGraph(
        instruction="launch notepad",
        steps=steps
    )
    
    # Save to database
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "completed")
    plan_logger.close()
    
    return plan_id


def setup_test_plan_with_mixed_steps() -> int:
    """
    Create a plan with multiple steps requiring approval.
    
    Returns:
        plan_id of created plan
    """
    steps = [
        PlanStep(
            step_id=1,
            item=Action(
                action_type="launch_app",
                target="notepad.exe",
                verify=False
            ),
            intent="Launch notepad",
            expected_outcome="Notepad appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(
                action_type="type_text",
                text="hello",
                verify=False
            ),
            intent="Type text",
            expected_outcome="Text appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=3,
            item=Action(
                action_type="wait",
                target="1",  # Duration in seconds
                verify=False
            ),
            intent="Wait",
            expected_outcome="Pause",
            requires_approval=False
        )
    ]
    
    plan_graph = PlanGraph(
        instruction="launch notepad and type hello",
        steps=steps
    )
    
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.close()
    
    return plan_id


class MockController:
    """Mock controller for testing."""
    
    def __init__(self):
        self.executed_actions = []
    
    def execute_action(self, action, plan_id=None):
        """Mock action execution."""
        self.executed_actions.append({
            "action_type": action.action_type,
            "target": action.target,
            "text": action.text,
            "plan_id": plan_id
        })


class MockCritic:
    """Mock critic for testing."""
    
    def __init__(self, fail_verification=False):
        self.fail_verification = fail_verification
        self.verified_actions = []
        self.verified_observations = []
    
    def verify_action(self, action):
        """Mock action verification."""
        self.verified_actions.append(action)
        
        from common.verification import VerificationResult
        return VerificationResult(
            verified=not self.fail_verification,
            confidence=0.9 if not self.fail_verification else 0.3,
            evidence=["MOCK_UIA=SUCCESS" if not self.fail_verification else "MOCK_UIA=FAIL"]
        )
    
    def verify_observation(self, observation):
        """Mock observation verification."""
        self.verified_observations.append(observation)
        
        from common.verification import VerificationResult
        return VerificationResult(
            verified=not self.fail_verification,
            confidence=0.9 if not self.fail_verification else 0.3,
            evidence=["MOCK_OBS=SUCCESS" if not self.fail_verification else "MOCK_OBS=FAIL"]
        )


class MockPolicyEngine:
    """Mock policy engine for testing."""
    
    def __init__(self, deny_all=False):
        self.deny_all = deny_all
    
    def validate_action(self, action):
        """Mock policy check."""
        if self.deny_all:
            return (False, "Policy denied for testing")
        else:
            return (True, None)


def simulate_user_input(inputs):
    """
    Decorator to simulate user input for testing.
    
    Args:
        inputs: List of strings to return for input() calls
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Save original input
            original_input = __builtins__.input
            
            # Create input generator
            input_iter = iter(inputs)
            
            # Replace input with mock
            __builtins__.input = lambda prompt: next(input_iter)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Restore original input
                __builtins__.input = original_input
        
        return wrapper
    return decorator


# ============================
# TEST CASES
# ============================

def test_replay_success():
    """
    Test 1: Replay successful plan
    
    Verifies:
    - Plan loads from database
    - PlanGraph reconstructs correctly
    - Replay approval prompt works
    - Steps execute in order
    - New replay execution is persisted
    """
    print("\n" + "="*70)
    print("=== Test 1: Replay Successful Plan ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_successful()
    
    # Create replay engine with mocks
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic()
    policy_engine = MockPolicyEngine()
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "yes" to start replay, "approve" for step 1
    @simulate_user_input(["yes", "approve"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == True, "Replay should succeed"
    assert len(controller.executed_actions) == 2, f"Expected 2 actions executed, got {len(controller.executed_actions)}"
    assert controller.executed_actions[0]["action_type"] == "launch_app"
    assert controller.executed_actions[1]["action_type"] == "wait"
    
    # Verify new replay execution was persisted
    recent_plans = plan_logger.get_recent_plans(limit=5)
    assert len(recent_plans) >= 2, "Should have original plan + replay execution"
    
    # Check replay plan has execution timestamps
    replay_plan = recent_plans[0]  # Most recent
    assert replay_plan["execution_started_at"] is not None
    assert replay_plan["execution_completed_at"] is not None
    assert replay_plan["execution_status"] == "completed"
    
    print("✅ Test 1 PASSED: Successful plan replay")
    plan_logger.close()


def test_replay_aborted():
    """
    Test 2: Replay aborted by user
    
    Verifies:
    - User can reject initial replay approval
    - No execution happens when aborted
    - Graceful handling of abort
    """
    print("\n" + "="*70)
    print("=== Test 2: Replay Aborted by User ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_successful()
    
    # Create replay engine with mocks
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic()
    policy_engine = MockPolicyEngine()
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "no" to reject replay
    @simulate_user_input(["no"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == False, "Replay should be aborted"
    assert len(controller.executed_actions) == 0, "No actions should execute when aborted"
    
    print("✅ Test 2 PASSED: Replay aborted by user")
    plan_logger.close()


def test_replay_skipped_steps():
    """
    Test 3: Replay with skipped steps
    
    Verifies:
    - User can skip individual steps
    - Skipped steps don't execute
    - Remaining steps continue
    - Step decisions are logged
    """
    print("\n" + "="*70)
    print("=== Test 3: Replay with Skipped Steps ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_with_mixed_steps()
    
    # Create replay engine with mocks
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic()
    policy_engine = MockPolicyEngine()
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "yes" to start, "approve" step 1, "skip" step 2
    @simulate_user_input(["yes", "approve", "skip"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == True, "Replay should succeed even with skipped steps"
    
    # Step 1 should execute, step 2 should be skipped, step 3 should execute
    assert len(controller.executed_actions) == 2, f"Expected 2 actions (step 1 and 3), got {len(controller.executed_actions)}"
    assert controller.executed_actions[0]["action_type"] == "launch_app", "Step 1 should execute"
    assert controller.executed_actions[1]["action_type"] == "wait", "Step 3 should execute"
    
    # Verify step decisions logged
    replay_plan = plan_logger.get_recent_plans(limit=1)[0]
    replay_plan_id = replay_plan["plan_id"]
    
    decisions = step_approval_logger.get_decisions_for_plan(replay_plan_id)
    assert len(decisions) == 2, f"Expected 2 logged decisions, got {len(decisions)}"
    
    # Check decisions
    decision_map = {d["step_id"]: d["decision"] for d in decisions}
    assert decision_map[1] == "approved", "Step 1 should be approved"
    assert decision_map[2] == "skipped", "Step 2 should be skipped"
    
    print("✅ Test 3 PASSED: Replay with skipped steps")
    plan_logger.close()


def test_replay_step_rejection():
    """
    Test 4: Replay with step rejection (aborts plan)
    
    Verifies:
    - User can reject individual steps
    - Rejection aborts entire replay
    - Subsequent steps don't execute
    - Replay marked as cancelled
    """
    print("\n" + "="*70)
    print("=== Test 4: Replay with Step Rejection ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_with_mixed_steps()
    
    # Create replay engine with mocks
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic()
    policy_engine = MockPolicyEngine()
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "yes" to start, "approve" step 1, "reject" step 2
    @simulate_user_input(["yes", "approve", "reject"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == False, "Replay should fail when step is rejected"
    
    # Only step 1 should execute (step 2 rejected, step 3 never reached)
    assert len(controller.executed_actions) == 1, f"Expected 1 action (step 1 only), got {len(controller.executed_actions)}"
    assert controller.executed_actions[0]["action_type"] == "launch_app"
    
    # Verify replay marked as cancelled
    replay_plan = plan_logger.get_recent_plans(limit=1)[0]
    assert replay_plan["execution_status"] == "cancelled", "Replay should be marked as cancelled"
    
    # Verify rejection logged
    decisions = step_approval_logger.get_decisions_for_plan(replay_plan["plan_id"])
    decision_map = {d["step_id"]: d["decision"] for d in decisions}
    assert decision_map[2] == "rejected", "Step 2 should be rejected"
    
    print("✅ Test 4 PASSED: Replay with step rejection")
    plan_logger.close()


def setup_test_plan_with_verification() -> int:
    """
    Create a plan with verification enabled for testing failures.
    
    Returns:
        plan_id of created plan
    """
    steps = [
        PlanStep(
            step_id=1,
            item=Action(
                action_type="launch_app",
                target="notepad.exe",
                verify=True  # Verification enabled
            ),
            intent="Launch notepad application",
            expected_outcome="Notepad window appears",
            requires_approval=True
        ),
        PlanStep(
            step_id=2,
            item=Action(
                action_type="wait",
                target="1",
                verify=False
            ),
            intent="Wait 1 second",
            expected_outcome="Brief pause",
            requires_approval=False
        )
    ]
    
    plan_graph = PlanGraph(
        instruction="launch notepad with verification",
        steps=steps
    )
    
    # Save to database
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    plan_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.update_approval(plan_id, approved=True, actor="test_user", timestamp=datetime.now().isoformat())
    plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
    plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), "completed")
    plan_logger.close()
    
    return plan_id


def test_replay_verification_failure():
    """
    Test 5: Replay with verification failure
    
    Verifies:
    - Verification failures stop replay
    - Failure propagates correctly
    - No automatic retries
    """
    print("\n" + "="*70)
    print("=== Test 5: Replay with Verification Failure ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_with_verification()
    
    # Create replay engine with failing critic
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic(fail_verification=True)  # Critic will fail verification
    policy_engine = MockPolicyEngine()
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "yes" to start, "approve" step 1
    @simulate_user_input(["yes", "approve"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == False, "Replay should fail when verification fails"
    assert len(controller.executed_actions) == 1, "Action should execute before verification fails"
    assert len(critic.verified_actions) == 1, "Verification should be attempted"
    
    # Verify replay marked as cancelled
    replay_plan = plan_logger.get_recent_plans(limit=1)[0]
    assert replay_plan["execution_status"] == "cancelled"
    
    print("✅ Test 5 PASSED: Replay with verification failure")
    plan_logger.close()


def test_replay_policy_denial():
    """
    Test 6: Replay with policy denial
    
    Verifies:
    - Policy checks enforced during replay
    - Denied actions stop replay
    - Same policy rules as normal execution
    """
    print("\n" + "="*70)
    print("=== Test 6: Replay with Policy Denial ===")
    print("="*70)
    
    # Setup
    plan_id = setup_test_plan_successful()
    
    # Create replay engine with denying policy
    plan_logger = PlanLogger(db_path=TEST_PLANS_DB)
    step_approval_logger = StepApprovalLogger(db_path=TEST_PLANS_DB)
    controller = MockController()
    critic = MockCritic()
    policy_engine = MockPolicyEngine(deny_all=True)  # Policy denies everything
    
    replay_engine = ReplayEngine(
        plan_logger=plan_logger,
        step_approval_logger=step_approval_logger,
        controller=controller,
        critic=critic,
        policy_engine=policy_engine
    )
    
    # Simulate user input: "yes" to start, "approve" step 1
    @simulate_user_input(["yes", "approve"])
    def run_replay():
        return replay_engine.replay_plan(plan_id)
    
    # Execute replay
    success = run_replay()
    
    # Verify results
    assert success == False, "Replay should fail when policy denies action"
    assert len(controller.executed_actions) == 0, "No actions should execute when policy denies"
    
    # Verify replay marked as cancelled
    replay_plan = plan_logger.get_recent_plans(limit=1)[0]
    assert replay_plan["execution_status"] == "cancelled"
    
    print("✅ Test 6 PASSED: Replay with policy denial")
    plan_logger.close()


def main():
    """Run all Phase-7A tests."""
    print("\n" + "="*70)
    print("PHASE-7A TEST SUITE - DETERMINISTIC PLAN REPLAY")
    print("="*70)
    
    # Cleanup before tests
    print("\n🧹 Test databases cleaned up")
    cleanup_test_databases()
    
    # Run tests
    try:
        test_replay_success()
        test_replay_aborted()
        test_replay_skipped_steps()
        test_replay_step_rejection()
        test_replay_verification_failure()
        test_replay_policy_denial()
        
        # Cleanup after tests
        print("\n🧹 Test databases cleaned up")
        cleanup_test_databases()
        
        print("\n" + "="*70)
        print("✅ ALL PHASE-7A TESTS PASSED (6/6)")
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
