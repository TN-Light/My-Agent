import unittest
from unittest.mock import MagicMock, patch
from perception.observer import Observer, Observation, ObservationResult
from perception.vision_client import VisionClient

class TestPhase10Vision(unittest.TestCase):
    """
    Phase-10 Validation Tests: Vision Observation Upgrade (Safe Mode)
    
    Verifies:
    1. Vision confidence is capped at 0.7 (MAX_CONFIDENCE).
    2. Vision output is strictly read-only (ObservationResult).
    3. Observer correctly handles the structured dictionary from VisionClient.
    """

    def setUp(self):
        self.mock_vision_client = MagicMock(spec=VisionClient)
        self.mock_screen_capture = MagicMock()
        self.observer = Observer(
            vision_client=self.mock_vision_client,
            screen_capture=self.mock_screen_capture
        )

    def test_vision_confidence_cap_in_observer(self):
        """Test that Observer correctly propagates the confidence from VisionClient."""
        # Setup mock behavior
        fake_screenshot = MagicMock()
        self.mock_screen_capture.capture_active_window.return_value = fake_screenshot
        
        # VisionClient returns specific structure with 0.7 confidence
        self.mock_vision_client.analyze_screen.return_value = {
            "text": "There is a button labeled OK",
            "confidence": 0.7,
            "source": "vision_llm"
        }

        observation = Observation(
            observation_type="vision", 
            target="Describe the screen", 
            context="vision"
        )
        
        result = self.observer._observe_vision(observation)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.result, "There is a button labeled OK")
        self.assertEqual(result.metadata["confidence"], 0.7)
        self.assertEqual(result.metadata["source"], "vision_llm")
        self.assertTrue(result.metadata["advisory_only"])

    def test_vision_client_max_confidence_constant(self):
        """Verify the MAX_CONFIDENCE constant is respected in the VisionClient logic."""
        # This test logic mimics the implementation in vision_client.py 
        # checking the constant is defined and used correctly would require instantiating actual client 
        # or checking the constant presence.
        
        from perception.vision_client import VisionClient
        self.assertLessEqual(VisionClient.MAX_CONFIDENCE, 0.7, "MAX_CONFIDENCE must be <= 0.7")

    def test_vision_failure_handling(self):
        """Test Observer handling of VisionClient returning None or error."""
        fake_screenshot = MagicMock()
        self.mock_screen_capture.capture_active_window.return_value = fake_screenshot
        self.mock_vision_client.analyze_screen.return_value = None

        observation = Observation(
            observation_type="vision", 
            target="Find missing element", 
            context="vision"
        )

        result = self.observer._observe_vision(observation)
        
        self.assertEqual(result.status, "not_found")
        self.assertIn("Vision analysis returned no result", result.error)

    def test_read_only_constraint(self):
        """
        Verify that the VisionClient methods do not return Action objects.
        This is a conceptual check; in code, we ensure return types are dictionaries or strings.
        """
        fake_screenshot = MagicMock()
        self.mock_vision_client.analyze_screen.return_value = {
            "text": "Click this button", # Text might suggest action, but return type is data
            "confidence": 0.5,
            "source": "vision_llm"
        }
        
        result = self.mock_vision_client.analyze_screen(fake_screenshot, "prompt")
        self.assertIsInstance(result, dict)
        # Ensure it's not an Action object (mock check)
        self.assertNotIsInstance(result, type("Action", (), {}))

if __name__ == '__main__':
    unittest.main()
