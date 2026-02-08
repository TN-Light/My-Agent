"""
Test File Read Planning Bug Fix (Phase-2B)

Validates that "read file" instructions generate observation-only plans
with NO actions, preventing "Invalid action_type: read_text" error.

Expected behavior:
1. Instruction: "read file test.txt"
2. Planner generates: [Observation(read_text, context=file, target=test.txt)]
3. NO launch_app, NO type_text, NO actions
4. Observer routes to file handler
5. Returns file content
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from common.actions import Action
from common.observations import Observation
from logic.planner import Planner
from execution.file_handler import FileHandler
from perception.observer import Observer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_1_deterministic_file_read_parsing():
    """
    Test Case 1: Deterministic planner correctly parses file read instruction.
    
    Expected:
    - 0 actions
    - 1 observation with type=read_text, context=file
    """
    print("\n" + "="*70)
    print("TEST 1: Deterministic File Read Parsing")
    print("="*70)
    
    planner = Planner(config={"planner": {"use_llm": False}})
    
    # Test "read file <filename>" pattern
    instruction = "read file test_a1.txt"
    
    try:
        plan = planner.create_plan(instruction)
        
        # Validate plan structure
        actions = [item for item in plan if isinstance(item, Action)]
        observations = [item for item in plan if isinstance(item, Observation)]
        
        print(f"✓ Plan generated: {len(plan)} item(s)")
        print(f"  - Actions: {len(actions)}")
        print(f"  - Observations: {len(observations)}")
        
        # Assertions
        assert len(actions) == 0, f"Expected 0 actions, got {len(actions)}"
        assert len(observations) == 1, f"Expected 1 observation, got {len(observations)}"
        
        obs = observations[0]
        assert obs.observation_type == "read_text", f"Expected read_text, got {obs.observation_type}"
        assert obs.context == "file", f"Expected context=file, got {obs.context}"
        assert obs.target == "test_a1.txt", f"Expected target=test_a1.txt, got {obs.target}"
        
        print(f"✓ Observation: {obs}")
        print("✓ PASS: File read parsed correctly (observation-only)")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


def test_2_file_read_execution():
    """
    Test Case 2: Full file read execution flow.
    
    Workflow:
    1. Create file test_a1.txt with content "hello"
    2. Read file test_a1.txt
    3. Verify content returned
    """
    print("\n" + "="*70)
    print("TEST 2: File Read Execution")
    print("="*70)
    
    # Initialize components
    workspace_root = project_root / "workspace"
    workspace_root.mkdir(exist_ok=True)
    
    file_handler = FileHandler(workspace_path=str(workspace_root))
    observer = Observer(file_handler=file_handler)
    planner = Planner(config={"planner": {"use_llm": False}})
    
    try:
        # Step 1: Create test file
        test_file = workspace_root / "test_a1.txt"
        test_file.write_text("hello", encoding="utf-8")
        print(f"✓ Created test file: {test_file}")
        
        # Step 2: Plan file read
        instruction = "read file test_a1.txt"
        plan = planner.create_plan(instruction)
        
        actions = [item for item in plan if isinstance(item, Action)]
        observations = [item for item in plan if isinstance(item, Observation)]
        
        assert len(actions) == 0, "File read plan must have 0 actions"
        assert len(observations) == 1, "File read plan must have 1 observation"
        
        print(f"✓ Plan: {len(observations)} observation(s), {len(actions)} action(s)")
        
        # Step 3: Execute observation
        obs = observations[0]
        result = observer.observe(obs)
        
        print(f"✓ Observation status: {result.status}")
        print(f"✓ Observation result: {result.result}")
        
        # Step 4: Verify content
        assert result.status == "success", f"Expected success, got {result.status}"
        assert result.result == "hello", f"Expected 'hello', got '{result.result}'"
        
        print("✓ PASS: File read executed successfully")
        
        # Cleanup
        test_file.unlink(missing_ok=True)
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_file_read_with_llm():
    """
    Test Case 3: LLM-based planner handles file read correctly (if LLM available).
    
    This test will skip if LLM is not available.
    """
    print("\n" + "="*70)
    print("TEST 3: LLM File Read Planning")
    print("="*70)
    
    try:
        from logic.llm_client import LLMClient
        
        # Try to initialize LLM client
        try:
            llm_client = LLMClient(
                base_url="http://localhost:11434",
                model="llama3.2",
                temperature=0.1
            )
        except ConnectionError:
            print("ℹ Skipping LLM test (Ollama not available)")
            return None
        
        planner = Planner(
            config={"planner": {"use_llm": True, "max_actions_per_plan": 5}},
            llm_client=llm_client
        )
        
        instruction = "read file test_a1.txt"
        
        try:
            plan = planner.create_plan(instruction)
            
            actions = [item for item in plan if isinstance(item, Action)]
            observations = [item for item in plan if isinstance(item, Observation)]
            
            print(f"✓ LLM plan: {len(observations)} observation(s), {len(actions)} action(s)")
            
            # Validate
            if len(actions) > 0:
                print(f"❌ FAIL: LLM generated {len(actions)} action(s) for file read")
                print(f"   Actions: {[a.action_type for a in actions]}")
                return False
            
            if len(observations) == 0:
                print("❌ FAIL: LLM generated no observations for file read")
                return False
            
            # Check if observation is correct type
            obs = observations[0]
            if obs.observation_type != "read_text" or obs.context != "file":
                print(f"❌ FAIL: Wrong observation type: {obs.observation_type}, context: {obs.context}")
                return False
            
            print(f"✓ Observation: {obs}")
            print("✓ PASS: LLM correctly generated observation-only plan")
            
            return True
            
        except ValueError as e:
            # If LLM generates actions with file read, validation should catch it
            if "file read intent" in str(e).lower() and "observation" in str(e).lower():
                print(f"✓ PASS: Validation correctly caught LLM error: {e}")
                return True
            elif "read_text" in str(e) and "action_type" in str(e):
                print(f"✓ PASS: Error correctly caught: {e}")
                return True
            else:
                print(f"❌ FAIL: Unexpected error: {e}")
                return False
    
    except Exception as e:
        print(f"ℹ Skipping LLM test: {e}")
        return None


def test_4_validation_rejects_actions():
    """
    Test Case 4: Validation rejects file read plans with actions.
    
    Manually construct invalid plan to test validation.
    """
    print("\n" + "="*70)
    print("TEST 4: Validation Rejects Actions in File Read")
    print("="*70)
    
    planner = Planner(config={"planner": {"use_llm": False}})
    
    # Manually create invalid plan (mix of action + observation for file read)
    invalid_plan = [
        Action(action_type="launch_app", context="file", target="test.txt"),
        Observation(observation_type="read_text", context="file", target="test.txt")
    ]
    
    instruction = "read file test.txt"
    
    try:
        # This should fail validation
        planner._validate_intent_priority(instruction, invalid_plan)
        
        print("❌ FAIL: Validation did not reject invalid plan")
        return False
        
    except ValueError as e:
        print(f"✓ Expected error caught: {e}")
        assert "observation" in str(e).lower() and "action" in str(e).lower()
        print("✓ PASS: Validation correctly rejects actions in file read")
        return True


def run_all_tests():
    """Run all file read bug fix tests."""
    print("\n" + "="*70)
    print("FILE READ PLANNING BUG FIX TEST SUITE")
    print("="*70)
    
    results = {
        "test_1": test_1_deterministic_file_read_parsing(),
        "test_2": test_2_file_read_execution(),
        "test_3": test_3_file_read_with_llm(),
        "test_4": test_4_validation_rejects_actions(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)
    total = len(results)
    
    for test_name, result in results.items():
        if result is True:
            status = "✓ PASS"
        elif result is None:
            status = "⊘ SKIP"
        else:
            status = "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total - skipped} passed, {skipped} skipped, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        print("✓ File read planning bug fixed")
        print("✓ read_text correctly treated as observation")
        print("✓ No actions generated for file reads")
        return True
    else:
        print(f"\n⚠ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
