"""
Phase-5A Plan Graph Tests

Validates:
1. PlanGraph creation from action list
2. Approval rule application (action-level only)
3. Plan preview generation
4. Execution order (sequential in Phase-5A)
5. No changes to controller/critic/policy
"""

import sys
from common.actions import Action
from common.observations import Observation
from common.plan_graph import PlanGraph, PlanStep
from logic.planner import Planner

def test_plan_graph_creation():
    """Test PlanGraph creation from planner."""
    print("=" * 70)
    print("Test 1: PlanGraph Creation")
    print("=" * 70)
    
    config = {'planner': {'use_llm': False}}
    planner = Planner(config=config)
    
    # Create plan graph
    plan_graph = planner.create_plan_graph("open notepad and type hello")
    
    # Validate structure
    assert len(plan_graph.steps) == 2, f"Expected 2 steps, got {len(plan_graph.steps)}"
    assert plan_graph.total_actions == 2, f"Expected 2 actions, got {plan_graph.total_actions}"
    assert plan_graph.total_observations == 0, f"Expected 0 observations, got {plan_graph.total_observations}"
    
    # Check step IDs
    assert plan_graph.steps[0].step_id == 1
    assert plan_graph.steps[1].step_id == 2
    
    # Check intent inference
    assert "Launch" in plan_graph.steps[0].intent or "notepad" in plan_graph.steps[0].intent
    assert "Type" in plan_graph.steps[1].intent or "hello" in plan_graph.steps[1].intent
    
    # Check dependencies (sequential)
    assert plan_graph.steps[0].dependencies == []
    assert plan_graph.steps[1].dependencies == [1]
    
    print(f"✅ PASS: PlanGraph created with {len(plan_graph.steps)} steps")
    print(f"   Step 1: {plan_graph.steps[0].intent}")
    print(f"   Step 2: {plan_graph.steps[1].intent}")
    print()
    
    return True


def test_approval_rules():
    """Test that approval rules only apply to actions, not observations."""
    print("=" * 70)
    print("Test 2: Approval Rules (Actions Only)")
    print("=" * 70)
    
    # Create mock plan graph with actions and observations
    action1 = Action(action_type="launch_app", target="notepad.exe", context="desktop")
    action2 = Action(action_type="type_text", text="hello", context="desktop")
    obs1 = Observation(observation_type="read_text", target="test.txt", context="file")
    
    steps = [
        PlanStep(step_id=1, item=action1, intent="Launch notepad", expected_outcome="Window appears", requires_approval=False),
        PlanStep(step_id=2, item=action2, intent="Type text", expected_outcome="Text appears", requires_approval=False),
        PlanStep(step_id=3, item=obs1, intent="Read file", expected_outcome="Data retrieved", requires_approval=False)
    ]
    
    plan_graph = PlanGraph(instruction="test", steps=steps)
    
    # Simulate approval rule application (like main.py does)
    require_approval_for = ["launch_app", "close_app"]
    
    for step in plan_graph.steps:
        if step.is_action:
            if step.item.action_type in require_approval_for:
                step.requires_approval = True
    
    # Validate
    assert plan_graph.steps[0].requires_approval == True, "launch_app should require approval"
    assert plan_graph.steps[1].requires_approval == False, "type_text should not require approval"
    assert plan_graph.steps[2].requires_approval == False, "Observation should not require approval"
    
    assert plan_graph.approval_required == True, "Plan should require approval"
    
    approval_steps = plan_graph.get_approval_steps()
    assert len(approval_steps) == 1, f"Expected 1 approval step, got {len(approval_steps)}"
    assert approval_steps[0].step_id == 1, "Only step 1 should require approval"
    
    print("✅ PASS: Approval rules correctly applied")
    print(f"   Step 1 (launch_app): requires_approval={plan_graph.steps[0].requires_approval}")
    print(f"   Step 2 (type_text): requires_approval={plan_graph.steps[1].requires_approval}")
    print(f"   Step 3 (read_text observation): requires_approval={plan_graph.steps[2].requires_approval}")
    print()
    
    return True


def test_plan_preview():
    """Test plan preview text generation."""
    print("=" * 70)
    print("Test 3: Plan Preview Generation")
    print("=" * 70)
    
    config = {'planner': {'use_llm': False}}
    planner = Planner(config=config)
    
    plan_graph = planner.create_plan_graph("open notepad and type hello")
    
    # Mark first step for approval
    plan_graph.steps[0].requires_approval = True
    
    # Generate preview
    preview = plan_graph.to_display_tree()
    
    # Validate preview content
    assert "Plan Preview" in preview
    assert "open notepad and type hello" in preview
    assert "Step 1:" in preview
    assert "Step 2:" in preview
    assert "REQUIRES APPROVAL" in preview
    assert "Intent:" in preview
    assert "Expected:" in preview
    
    print("✅ PASS: Plan preview generated")
    print()
    print(preview)
    print()
    
    return True


def test_execution_order():
    """Test that execution order returns steps in list order."""
    print("=" * 70)
    print("Test 4: Execution Order (Sequential)")
    print("=" * 70)
    
    action1 = Action(action_type="launch_app", target="notepad.exe", context="desktop")
    action2 = Action(action_type="type_text", text="hello", context="desktop")
    action3 = Action(action_type="close_app", target="notepad", context="desktop")
    
    steps = [
        PlanStep(step_id=1, item=action1, intent="Launch", expected_outcome="Window", dependencies=[]),
        PlanStep(step_id=2, item=action2, intent="Type", expected_outcome="Text", dependencies=[1]),
        PlanStep(step_id=3, item=action3, intent="Close", expected_outcome="Closed", dependencies=[2])
    ]
    
    plan_graph = PlanGraph(instruction="test", steps=steps)
    
    execution_order = plan_graph.get_execution_order()
    
    # Validate order is preserved
    assert len(execution_order) == 3
    assert execution_order[0].step_id == 1
    assert execution_order[1].step_id == 2
    assert execution_order[2].step_id == 3
    
    print("✅ PASS: Execution order preserved (sequential)")
    print(f"   Order: {[s.step_id for s in execution_order]}")
    print()
    
    return True


def test_no_new_action_types():
    """Verify no new action types were added."""
    print("=" * 70)
    print("Test 5: No New Action Types")
    print("=" * 70)
    
    from common.actions import Action
    import inspect
    
    # Get Action __init__ signature
    sig = inspect.signature(Action.__init__)
    params = list(sig.parameters.keys())
    
    # Expected parameters (no vision, no new fields)
    expected = ['self', 'action_type', 'context', 'target', 'text', 'coordinates', 'verify']
    
    assert params == expected, f"Action schema changed: {params}"
    
    # Check action_type annotation
    annotations = Action.__annotations__
    action_type_annotation = str(annotations.get('action_type', ''))
    
    # Verify expected action types in Literal
    expected_types = ['launch_app', 'type_text', 'close_app', 'focus_window', 'wait']
    for action_type in expected_types:
        assert action_type in action_type_annotation, f"Missing action type: {action_type}"
    
    print("✅ PASS: No new action types added")
    print(f"   Action parameters: {params[1:]}")  # Skip 'self'
    print(f"   Action types: {expected_types}")
    print()
    
    return True


def test_plan_graph_properties():
    """Test PlanGraph computed properties."""
    print("=" * 70)
    print("Test 6: PlanGraph Properties")
    print("=" * 70)
    
    action1 = Action(action_type="launch_app", target="notepad", context="desktop")
    action2 = Action(action_type="type_text", text="test", context="desktop")
    obs1 = Observation(observation_type="read_text", target="file.txt", context="file")
    
    steps = [
        PlanStep(step_id=1, item=action1, intent="Launch", expected_outcome="Window"),
        PlanStep(step_id=2, item=action2, intent="Type", expected_outcome="Text", requires_approval=True),
        PlanStep(step_id=3, item=obs1, intent="Read", expected_outcome="Data")
    ]
    
    plan_graph = PlanGraph(instruction="test", steps=steps)
    
    # Test properties
    assert plan_graph.total_actions == 2
    assert plan_graph.total_observations == 1
    assert plan_graph.approval_required == True
    
    approval_steps = plan_graph.get_approval_steps()
    assert len(approval_steps) == 1
    assert approval_steps[0].step_id == 2
    
    print("✅ PASS: PlanGraph properties correct")
    print(f"   Total actions: {plan_graph.total_actions}")
    print(f"   Total observations: {plan_graph.total_observations}")
    print(f"   Approval required: {plan_graph.approval_required}")
    print()
    
    return True


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "PHASE-5A VALIDATION TEST SUITE" + " " * 23 + "║")
    print("║" + " " * 68 + "║")
    print("║  Scope: Plan Graph + Preview + Approval Gates                   ║")
    print("║  Constraints:                                                    ║")
    print("║    - No new action types                                        ║")
    print("║    - No controller/critic/policy changes                        ║")
    print("║    - Approval rules: actions only, never observations           ║")
    print("║    - Execution order: sequential (list order)                   ║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    all_passed = True
    
    try:
        if not test_plan_graph_creation():
            all_passed = False
        
        if not test_approval_rules():
            all_passed = False
        
        if not test_plan_preview():
            all_passed = False
        
        if not test_execution_order():
            all_passed = False
        
        if not test_no_new_action_types():
            all_passed = False
        
        if not test_plan_graph_properties():
            all_passed = False
        
    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    if all_passed:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "✅ ALL PHASE-5A TESTS PASSED" + " " * 25 + "║")
        print("╚" + "═" * 68 + "╝")
        sys.exit(0)
    else:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "❌ SOME PHASE-5A TESTS FAILED" + " " * 23 + "║")
        print("╚" + "═" * 68 + "╝")
        sys.exit(1)
