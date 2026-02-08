import unittest
import logging
from unittest.mock import patch
from logic.planner import Planner
from common.actions import Action

# Configure logging to suppress output during test
logging.basicConfig(level=logging.ERROR)

class TestPlannerRepair(unittest.TestCase):
    def setUp(self):
        self.planner = Planner(config={"planner": {"use_llm": False}})
        
    def test_auto_repair_single_candidate(self):
        print("\nTesting Single Candidate Repair...")
        actions = [
            Action(action_type="launch_app", target="notepad.exe"),
            Action(action_type="type_text", text="hello"),
            Action(action_type="close_app", target=None) 
        ]
        
        repaired = self.planner._repair_plan_targets(actions)
        
        self.assertEqual(len(repaired), 3)
        self.assertEqual(repaired[2].target, "notepad.exe")
        print("Success: Repaired to 'notepad.exe'")
        
    @patch('builtins.input', return_value="calc.exe")
    def test_ambiguous_repair_no_history(self, mock_input):
        print("\nTesting Ambiguous Repair (No History)...")
        actions = [
            Action(action_type="close_app", target=None)
        ]
        
        repaired = self.planner._repair_plan_targets(actions)
        self.assertEqual(repaired[0].target, "calc.exe")
        print("Success: Repaired to 'calc.exe' via input")

    @patch('builtins.input', return_value="word.exe")
    def test_ambiguous_repair_multi_history_explicit(self, mock_input):
        print("\nTesting Ambiguous Repair (Multi History - Explicit Input)...")
        actions = [
            Action(action_type="launch_app", target="notepad.exe"),
            Action(action_type="launch_app", target="word.exe"),
            Action(action_type="close_app", target=None)
        ]
        
        repaired = self.planner._repair_plan_targets(actions)
        self.assertEqual(repaired[2].target, "word.exe")
        print("Success: Repaired to 'word.exe' via input")

    @patch('builtins.input', return_value="")
    def test_ambiguous_repair_multi_history_default(self, mock_input):
        print("\nTesting Ambiguous Repair (Multi History - Default)...")
        actions = [
            Action(action_type="launch_app", target="notepad.exe"),
            Action(action_type="launch_app", target="excel.exe"),
            Action(action_type="close_app", target=None)
        ]
        
        # Should default to last launched (excel.exe)
        repaired = self.planner._repair_plan_targets(actions)
        self.assertEqual(repaired[2].target, "excel.exe")
        print("Success: Repaired to 'excel.exe' via default")

if __name__ == '__main__':
    unittest.main()
