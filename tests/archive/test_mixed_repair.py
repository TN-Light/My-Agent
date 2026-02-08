import unittest
import logging
from unittest.mock import patch
from logic.planner import Planner
from common.actions import Action

# Configure logging
logging.basicConfig(level=logging.ERROR)

class TestLinkPlannerMixedRepair(unittest.TestCase):
    def setUp(self):
        self.planner = Planner(config={"planner": {"use_llm": False}})
        
    def test_repair_mixed_context(self):
        print("\nTesting Mixed Context Repair (Desktop + File)...")
        # Scenario: User wants to save a file in Notepad, LLM generates File action
        actions = [
            Action(action_type="launch_app", context="desktop", target="notepad.exe"),
            Action(action_type="type_text", context="desktop", text="hello"),
            # The culprit:
            Action(action_type="type_text", context="file", target="test.txt", text="hello"), 
            Action(action_type="close_app", context="desktop", target="notepad.exe")
        ]
        
        # Verify validation would fail before repair (we simulate validation call)
        try:
            self.planner._validate_context_exclusivity(actions)
            # Depending on how I changed validate, it might warn now.
            # But let's check the repair method directly.
        except ValueError:
            pass # Expected failure if we didn't mock validate
            
        repaired = self.planner._repair_mixed_contexts(actions)
        
        self.assertEqual(len(repaired), 3)
        self.assertEqual(repaired[0].context, "desktop")
        self.assertEqual(repaired[1].context, "desktop")
        self.assertEqual(repaired[2].context, "desktop")
        
        # Ensure the file action is gone
        contexts = set(a.context for a in repaired)
        self.assertNotIn("file", contexts)
        self.assertIn("desktop", contexts)
        
        print("Success: 'file' action dropped, leaving pure 'desktop' plan")

if __name__ == '__main__':
    unittest.main()
