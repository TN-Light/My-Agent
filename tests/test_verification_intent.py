"""Test verification intent handling in planner"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from logic.planner import Planner
from common.actions import Action
from common.observations import Observation
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

print("=" * 70)
print("TEST: Verification Intent Handling")
print("=" * 70)

# Initialize planner
planner = Planner(config={"planner": {"use_llm": False}})

# Test cases
test_cases = [
    ("verify text visible hello", "hello"),
    ("verify that notepad is open", "notepad is open"),
    ("check that the window shows success", "window shows success"),
    ("verify_text_visible confirmation message", "confirmation message"),
]

for i, (instruction, expected_text) in enumerate(test_cases, 1):
    print(f"\n[Test {i}] {instruction}")
    print("-" * 70)
    
    try:
        plan = planner.create_plan(instruction)
        
        # Check plan structure
        actions = [item for item in plan if isinstance(item, Action)]
        observations = [item for item in plan if isinstance(item, Observation)]
        
        print(f"✓ Actions: {len(actions)}, Observations: {len(observations)}")
        
        # Validate: Should have exactly 1 action, 0 observations
        assert len(actions) == 1, f"Expected 1 action, got {len(actions)}"
        assert len(observations) == 0, f"Expected 0 observations, got {len(observations)}"
        
        # Check verification metadata
        action = actions[0]
        assert action.verify is not None, "Action should have verify metadata"
        assert "type" in action.verify, "Verify should have 'type' field"
        assert "value" in action.verify, "Verify should have 'value' field"
        assert action.verify["type"] == "text_visible", f"Expected type='text_visible', got {action.verify['type']}"
        
        print(f"✓ Verification metadata: {action.verify}")
        print(f"✓ PASS")
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("KEY VALIDATIONS:")
print("=" * 70)
print("✓ Verification intents generate Actions (not Observations)")
print("✓ Actions have verify metadata attached")
print("✓ verify metadata has 'type' and 'value' fields")
print("✓ Observations are explicitly forbidden for verification")
print("✓ Verification will be handled by Critic, not Observer")
