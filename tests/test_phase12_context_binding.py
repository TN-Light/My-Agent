"""
Test Phase 12: Context Binding & Vision Follow-Up Resolution
Verifies that:
1. Observations are stored in memory (FollowupResolver).
2. "read it" commands are resolved to specific vision buffer queries.
3. Vision buffer queries bypass real OCR and read from memory.
"""
import unittest
from unittest.mock import MagicMock
from logic.followup_resolver import FollowupResolver
from common.observations import Observation, ObservationResult
from logic.execution_engine import ExecutionEngine

class TestContextBinding(unittest.TestCase):
    def setUp(self):
        self.resolver = FollowupResolver()
        
    def test_update_and_resolve(self):
        # 1. Simulate a successful vision observation
        obs = Observation(observation_type="vision", context="vision", target="what do you see?")
        result = ObservationResult(
            observation=obs,
            status="success",
            result="I see a window titled 'Notepad' containing text 'Hello World'.",
            # Fix: Use 'raw_ocr' which FollowupResolver expects
            metadata={"raw_ocr": "Hello World", "source": "tesseract"}
        )
        
        # 2. Update resolver memory
        self.resolver.update_observation(result)
        
        # 3. Verify memory is set
        self.assertIsNotNone(self.resolver.get_last_observation())
        self.assertEqual(self.resolver.get_last_observation().metadata["raw_ocr"], "Hello World")
        
        # 4. Test Intent Resolution
        # "read it" should become a specific instruction
        resolved = self.resolver.resolve("read it")
        self.assertIn("summarize the last vision ocr text", resolved.lower())
        
        # 5. Test Buffer Retrieval
        content = self.resolver.get_last_vision_content()
        self.assertIn("Hello World", content)

    def test_no_history_handling(self):
        # Test behavior when memory is empty
        resolved = self.resolver.resolve("read it")
        # Should NOT change if no history
        self.assertEqual(resolved, "read it")

if __name__ == '__main__':
    unittest.main()
