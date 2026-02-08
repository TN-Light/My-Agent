import unittest
import logging
from unittest.mock import MagicMock
from logic.planner import Planner
from common.actions import Action
from common.plan_graph import PlanGraph

# Configure logging
logging.basicConfig(level=logging.ERROR)

class TestPlanSegmentation(unittest.TestCase):
    def setUp(self):
        self.planner = Planner(config={"planner": {"use_llm": False}})
        # Mock LLM response to simulate mixed context result
        self.planner.create_plan = MagicMock()
        
    def test_segmentation_logic(self):
        print("\nTesting Plan Segmentation Logic...")
        
        # Scenario: Mixed Context [Desktop, Desktop, File, Desktop]
        # This simulates "Open Notepad, Type Hello, Save(File), Close Notepad"
        mixed_actions = [
            Action(action_type="launch_app", context="desktop", target="notepad.exe"),
            Action(action_type="type_text", context="desktop", text="hello"),
            Action(action_type="type_text", context="file", target="test.txt", text="hello"), 
            Action(action_type="close_app", context="desktop", target="notepad.exe")
        ]
        
        # Force create_plan to return our mixed list directly (bypassing its internal validation)
        # Note: In real usage, create_plan would return this because we removed the destructive repair
        self.planner.create_plan.return_value = mixed_actions
        
        # Execute
        plan_graphs = self.planner.create_plan_graph("dummy instruction")
        
        # Verify
        self.assertIsInstance(plan_graphs, list)
        self.assertEqual(len(plan_graphs), 3, "Should be split into 3 segments")
        
        # Segment 1: Desktop
        print(f"Segment 1: {len(plan_graphs[0].steps)} steps")
        self.assertEqual(len(plan_graphs[0].steps), 2)
        self.assertEqual(plan_graphs[0].steps[0].item.context, "desktop")
        
        # Segment 2: File
        print(f"Segment 2: {len(plan_graphs[1].steps)} steps")
        self.assertEqual(len(plan_graphs[1].steps), 1)
        self.assertEqual(plan_graphs[1].steps[0].item.context, "file")
        
        # Segment 3: Desktop
        print(f"Segment 3: {len(plan_graphs[2].steps)} steps")
        self.assertEqual(len(plan_graphs[2].steps), 1)
        self.assertEqual(plan_graphs[2].steps[0].item.context, "desktop")
        
        print("Success: Plan successfully segmented by context boundaries")

if __name__ == '__main__':
    unittest.main()
