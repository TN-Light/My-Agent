
import unittest
from unittest.mock import MagicMock, patch
from common.observations import Observation
from perception.observer import Observer

class TestObserverBurstMode(unittest.TestCase):
    def setUp(self):
        self.mock_capture = MagicMock()
        self.mock_vision = MagicMock()
        self.observer = Observer(
            screen_capture=self.mock_capture,
            vision_client=self.mock_vision
        )
        # Mock screen capture return
        self.mock_image = MagicMock()
        self.mock_image.width = 100
        self.mock_image.height = 100
        self.mock_capture.capture_active_app.return_value = (self.mock_image, "Test Window")
        self.mock_capture.capture_active_window.return_value = (self.mock_image, "Test Window")

    @patch('time.sleep')
    def test_burst_mode_resolves_stabilization(self, mock_sleep):
        """Test that observer retries when vision client reports stabilizing status"""
        
        # Frame 1: Stabilizing
        # Frame 2: Stabilizing
        # Frame 3: Stable
        
        self.mock_vision.analyze_screen.side_effect = [
            {"text": "Wait...", "source": "ocr_temporal_stabilizing", "confidence": 0.5},
            {"text": "Wait...", "source": "ocr_temporal_stabilizing", "confidence": 0.5},
            {"text": "Hello World", "source": "ocr_temporal_stable", "confidence": 0.8}
        ]
        
        obs = Observation(observation_type="vision", context="vision", target="read")
        result = self.observer._observe_vision(obs)
        
        # Should have called analyze_screen 3 times
        self.assertEqual(self.mock_vision.analyze_screen.call_count, 3)
        self.assertIn("Hello World", result.result) # Should contain final stable text

    @patch('time.sleep')
    def test_burst_mode_gives_up(self, mock_sleep):
        """Test that observer returns best effort after max retries"""
        
        # All frames stabilizing
        self.mock_vision.analyze_screen.return_value = {
            "text": "Still waiting...", 
            "source": "ocr_temporal_stabilizing",
            "confidence": 0.5
        }
        
        obs = Observation(observation_type="vision", context="vision", target="read")
        result = self.observer._observe_vision(obs)
        
        # Should have called 3 times
        self.assertEqual(self.mock_vision.analyze_screen.call_count, 3)
        # Result should be the stabilizing message
        self.assertIn("Wait", result.result) # Interpretation might mask it, but raw_ocr is in metadata
        self.assertEqual(result.metadata["raw_ocr"], "Still waiting...")

if __name__ == '__main__':
    unittest.main()
