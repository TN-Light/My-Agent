import unittest
import logging
from unittest.mock import MagicMock
from logic.planner import Planner
from common.actions import Action
from common.plan_graph import PlanGraph

# Configure logging
logging.basicConfig(level=logging.ERROR)

class TestTaskDecomposition(unittest.TestCase):
    def setUp(self):
        # Set max actions to 2 to force decomposition even for moderately complex tasks
        self.planner = Planner(config={"planner": {"use_llm": False, "max_actions_per_plan": 2}})
        # Mock create_plan to return dummy actions based on input
        # We need it to return something valid so segmentation logic doesn't crash
        self.planner.create_plan = MagicMock(side_effect=self._mock_plan)
        
    def _mock_plan(self, instruction):
        # Deterministic mock based on instruction content
        if "notepad" in instruction.lower():
            return [Action(action_type="launch_app", context="desktop", target="notepad.exe")]
        if "save" in instruction.lower():
            return [Action(action_type="type_text", context="file", target="test.txt", text="save")]
        if "close" in instruction.lower():
            return [Action(action_type="close_app", context="desktop", target="notepad.exe")]
        return []

    def test_recursive_decomposition(self):
        print("\nTesting Recursive Decomposition (Complexity-Aware)...")
        # Complex instruction WITHOUT explicit "then" keywords
        # 4 distinct actions: open, type, save, close. Complexity ~5-6 depending on heuristic.
        # Max actions is default 5. To ensure split, we can assume "save as" is heavy or just enough items.
        # Let's verify heuristics in test or just behavior.
        instruction = "open notepad, type hello, save as test.txt, close notepad"
        
        # We manually test the private method
        sub_tasks = self.planner._decompose_instruction(instruction)
        print(f"Split results: {sub_tasks}")
        
        # Should be split despite lack of "then" because it is complex
        self.assertTrue(len(sub_tasks) >= 2)
        
    def test_safe_comma_usage(self):
        print("\nTesting Safe Comma Usage (Low Complexity)...")
        # Low complexity instruction with comma
        instruction = "type hello, world"
        
        sub_tasks = self.planner._decompose_instruction(instruction)
        print(f"Split results: {sub_tasks}")
        
        # Should NOT split on comma because complexity is low (1 action)
        self.assertEqual(len(sub_tasks), 1)
        self.assertEqual(sub_tasks[0], "type hello, world")

    def test_end_to_end_decomposition(self):
        print("\nTesting End-to-End Decomposition + Segmentation...")
        instruction = "open notepad, then save as test.txt, then close notepad"
        
        # This should trigger decomposition into 3 tasks
        # Each task mocks create_plan -> returns 1 action
        # Result: 3 PlanGraphs
        
        graphs = self.planner.create_plan_graph(instruction)
        
        self.assertEqual(len(graphs), 3)
        self.assertIn("Task 1/3", graphs[0].instruction)
        self.assertIn("Task 2/3", graphs[1].instruction)
        self.assertIn("Task 3/3", graphs[2].instruction)
        
        print(f"Generated {len(graphs)} graphs as expected.")

if __name__ == '__main__':
    unittest.main()
