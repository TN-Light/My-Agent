"""
Phase-8A Test Suite - Recommendation Engine
Verifies deterministic recommendation generation.
"""

import sys
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from logic.recommendation_engine import RecommendationEngine
from storage.execution_diff import ExecutionDiff
from storage.debug_reporter import DebugReporter
from storage.plan_logger import PlanLogger
from storage.action_logger import ActionLogger
from storage.step_approval_logger import StepApprovalLogger
from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action, ActionResult

# Test database paths
TEST_PLANS_DB = "db/test_plans_rec.db"
TEST_HISTORY_DB = "db/test_history_rec.db"
TEST_OBS_DB = "db/test_observations_rec.db"


def cleanup_test_databases():
    """Remove test databases if they exist."""
    import gc
    gc.collect()
    time.sleep(0.1)
    for db_path in [TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB]:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass


def create_mock_plan(instruction: str, steps: list) -> PlanGraph:
    return PlanGraph(instruction=instruction, steps=steps)


def setup_timing_scenario():
    """
    Scenario:
    - Original: Step 2 fails with "Element not found"
    - Replay: Step 2 succeeds
    Expected: "Insert wait before Step 2"
    """
    cleanup_test_databases()
    
    steps = [
        PlanStep(1, Action("launch_app", target="notepad.exe"), "Launch", "Window open"),
        PlanStep(2, Action("type_text", text="hello"), "Type", "Text appears")
    ]
    plan_graph = create_mock_plan("launch and type", steps)

    plan_logger = PlanLogger(TEST_PLANS_DB)
    action_logger = ActionLogger(TEST_HISTORY_DB)
    
    # 1. Original Execution (Failed)
    orig_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.mark_execution_started(orig_id, datetime.now().isoformat())
    
    # Step 1 Success
    action_logger.log_action(ActionResult(steps[0].item, True, "OK"), orig_id)
    # Step 2 Fail
    action_logger.log_action(ActionResult(steps[1].item, False, "Fail", error="Element not found"), orig_id)
    
    plan_logger.mark_execution_completed(orig_id, datetime.now().isoformat(), "failed")

    # 2. Replay Execution (Success)
    replay_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.mark_execution_started(replay_id, datetime.now().isoformat())
    
    action_logger.log_action(ActionResult(steps[0].item, True, "OK"), replay_id)
    action_logger.log_action(ActionResult(steps[1].item, True, "OK"), replay_id)
    
    plan_logger.mark_execution_completed(replay_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return orig_id, replay_id


def setup_focus_scenario():
    """
    Scenario:
    - Original: Step 1 fails with "Window not focused"
    - Replay: Step 1 succeeds
    Expected: "Add focus_window before Step 1"
    """
    cleanup_test_databases()
    
    steps = [PlanStep(1, Action("type_text", text="hello"), "Type", "Text appears")]
    plan_graph = create_mock_plan("type hello", steps)

    plan_logger = PlanLogger(TEST_PLANS_DB)
    action_logger = ActionLogger(TEST_HISTORY_DB)
    
    # Original (Fail)
    orig_id = plan_logger.log_plan(plan_graph, approval_required=False)
    plan_logger.mark_execution_started(orig_id, datetime.now().isoformat())
    action_logger.log_action(ActionResult(steps[0].item, False, "Fail", error="Window not focused"), orig_id)
    plan_logger.mark_execution_completed(orig_id, datetime.now().isoformat(), "failed")

    # Replay (Success)
    replay_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.mark_execution_started(replay_id, datetime.now().isoformat())
    action_logger.log_action(ActionResult(steps[0].item, True, "OK"), replay_id)
    plan_logger.mark_execution_completed(replay_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    
    return orig_id, replay_id


def setup_skip_scenario():
    """
    Scenario:
    - Original: All success (or fail, doesn't matter much contextually, but let's say success)
    - Replay: User SKIPS step 2
    Expected: "Consider removing or modifying Step 2"
    """
    cleanup_test_databases()
    
    steps = [
        PlanStep(1, Action("launch_app", target="notepad"), "Launch", "OK"),
        PlanStep(2, Action("wait", target="1"), "Wait", "OK")
    ]
    plan_graph = create_mock_plan("test skip", steps)

    plan_logger = PlanLogger(TEST_PLANS_DB)
    action_logger = ActionLogger(TEST_HISTORY_DB)
    approval_logger = StepApprovalLogger(TEST_PLANS_DB)
    
    # Original (Approved & Executed)
    orig_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.mark_execution_started(orig_id, datetime.now().isoformat())
    approval_logger.log_step_decision(orig_id, 1, "approved", datetime.now().isoformat())
    action_logger.log_action(ActionResult(steps[0].item, True, "OK"), orig_id)
    approval_logger.log_step_decision(orig_id, 2, "approved", datetime.now().isoformat())
    action_logger.log_action(ActionResult(steps[1].item, True, "OK"), orig_id)
    plan_logger.mark_execution_completed(orig_id, datetime.now().isoformat(), "completed")

    # Replay (Step 2 Skipped)
    replay_id = plan_logger.log_plan(plan_graph, approval_required=True)
    plan_logger.mark_execution_started(replay_id, datetime.now().isoformat())
    approval_logger.log_step_decision(replay_id, 1, "approved", datetime.now().isoformat())
    action_logger.log_action(ActionResult(steps[0].item, True, "OK"), replay_id)
    approval_logger.log_step_decision(replay_id, 2, "skipped", datetime.now().isoformat())
    # No action log for step 2
    plan_logger.mark_execution_completed(replay_id, datetime.now().isoformat(), "completed")
    
    plan_logger.close()
    action_logger.close()
    approval_logger.close()
    
    return orig_id, replay_id


def test_timing_recommendation():
    print("\n" + "="*70)
    print("Test 1: Timing Recommendation")
    
    orig_id, replay_id = setup_timing_scenario()
    
    diff_tool = ExecutionDiff(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    reporter = DebugReporter(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    engine = RecommendationEngine(diff_tool, reporter)
    
    recs = engine.generate_recommendations(orig_id, replay_id)
    
    print(engine.to_text_report(recs))
    
    assert len(recs) >= 1
    assert any(r.category == "TIMING" and "Insert wait" in r.description for r in recs)
    assert any(r.step_id == 2 for r in recs)
    print("✅ Test 1 Passed")


def test_focus_recommendation():
    print("\n" + "="*70)
    print("Test 2: Focus Recommendation")
    
    orig_id, replay_id = setup_focus_scenario()
    
    diff_tool = ExecutionDiff(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    reporter = DebugReporter(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    engine = RecommendationEngine(diff_tool, reporter)
    
    recs = engine.generate_recommendations(orig_id, replay_id)
    
    print(engine.to_text_report(recs))
    
    assert any(r.category == "FOCUS" and "Add focus_window" in r.description for r in recs)
    print("✅ Test 2 Passed")


def test_structure_recommendation():
    print("\n" + "="*70)
    print("Test 3: Structure Recommendation (Skipped Step)")
    
    orig_id, replay_id = setup_skip_scenario()
    
    diff_tool = ExecutionDiff(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    reporter = DebugReporter(TEST_PLANS_DB, TEST_HISTORY_DB, TEST_OBS_DB)
    engine = RecommendationEngine(diff_tool, reporter)
    
    recs = engine.generate_recommendations(orig_id, replay_id)
    
    print(engine.to_text_report(recs))
    
    assert any(r.category == "STRUCTURE" and "Step 2" in r.description for r in recs)
    print("✅ Test 3 Passed")


def main():
    try:
        test_timing_recommendation()
        test_focus_recommendation()
        test_structure_recommendation()
        print("\n" + "="*70)
        print("✅ ALL PHASE-8A TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup_test_databases()

if __name__ == "__main__":
    main()
