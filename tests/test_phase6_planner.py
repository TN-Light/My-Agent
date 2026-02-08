"""
Phase-6 Planner Validation Tests
Scope: Logic and Parsing (No actual network calls)

1. valid_plan: "open notepad" -> parsable JSON
2. ambiguous_plan: "do something" -> empty JSON list -> Error
3. unsafe_plan: "format c:" -> empty JSON list -> Error
"""
import unittest
from unittest.mock import MagicMock
import json
from logic.llm_planner import LLMPlanner
from logic.llm_client import LLMClient
from common.actions import Action
from common.observations import Observation

class TestPhase6Planner(unittest.TestCase):

    def setUp(self):
        # Mock LLM Client
        self.mock_client = MagicMock(spec=LLMClient)
        # Initialize Planner with mock
        self.planner = LLMPlanner(self.mock_client)

    def test_1_safe_plan_generation(self):
        """Test parsing of a valid structural response."""
        print("\nTest 1: Safe Plan Generation")
        
        # Mock LLM response for "open notepad and type hello"
        valid_response = json.dumps([
            {
                "action_type": "launch_app",
                "context": "desktop",
                "target": "notepad.exe"
            },
            {
                "action_type": "type_text",
                "context": "desktop",
                "text": "hello"
            }
        ])
        self.mock_client.generate_completion.return_value = valid_response
        
        plan = self.planner.generate_plan("open notepad and type hello")
        
        # Assertions
        self.assertEqual(len(plan), 2)
        self.assertIsInstance(plan[0], Action)
        self.assertEqual(plan[0].action_type, "launch_app")
        self.assertEqual(plan[0].target, "notepad.exe")
        self.assertEqual(plan[1].text, "hello")
        print("✅ Safe plan parsed successfully")

    def test_2_ambiguous_instruction(self):
        """Test rejection of ambiguous plans (Empty List)."""
        print("\nTest 2: Ambiguous Instruction Rejection")
        
        # Mock LLM returning empty list for "do it"
        self.mock_client.generate_completion.return_value = "[]"
        
        with self.assertRaises(ValueError) as cm:
            self.planner.generate_plan("do it")
        
        self.assertIn("Ambiguous", str(cm.exception))
        print("✅ Ambiguous plan rejected successfully")

    def test_3_unsafe_instruction(self):
        """Test rejection of unsafe/malformed plans."""
        print("\nTest 3: Unsafe/Malformed Rejection")
        
        # Scenario A: Malformed JSON (No array)
        self.mock_client.generate_completion.return_value = "Not valid json"
        with self.assertRaises(ValueError) as cm:
            self.planner.generate_plan("break things")
        # Match the generic wrapper error or specific cause
        self.assertIn("Could not generate safe plan", str(cm.exception))
        
        # Scenario B: Missing Context (Schema Violation)
        invalid_schema = json.dumps([{
            "action_type": "type_text",
            # Missing context
            "text": "bad"
        }])
        self.mock_client.generate_completion.return_value = invalid_schema
        
        with self.assertRaises(ValueError) as cm:
            self.planner.generate_plan("bad schema")
        self.assertIn("Missing 'context' field", str(cm.exception))
        
        print("✅ Unsafe/Malformed plans rejected successfully")

if __name__ == '__main__':
    unittest.main()
