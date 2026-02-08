
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from perception.vision_client import VisionClient
from perception.temporal_buffer import TemporalTextBuffer

class TestTemporalChain(unittest.TestCase):
    def setUp(self):
        # Mock pytesseract to prevent actual OCR attempts
        self.pytesseract_patcher = patch('perception.vision_client.pytesseract')
        self.mock_pytesseract = self.pytesseract_patcher.start()
        # Ensure it appears installed
        self.mock_pytesseract.get_tesseract_version.return_value = "5.0.0"
        
        self.client = VisionClient()
        # Mock empty image
        self.mock_image = Image.new('RGB', (100, 100))
        
    def tearDown(self):
        self.pytesseract_patcher.stop()
        
    def test_end_to_end_buffering(self):
        """Test that VisionClient correctly buffers frame inputs"""
        context_key = "Test Window - Notepad"
        
        # Frame 1: "Hello World"
        self.mock_pytesseract.image_to_string.return_value = "Hello World\nLine A"
        result1 = self.client.analyze_screen(self.mock_image, "read", context_key=context_key)
        
        # Frame 1 should be unstable (first appearance)
        print(f"Frame 1 Result: {result1['text']}")
        self.assertIn("stable readable content", result1['text'])
        self.assertEqual(result1['source'], "ocr_temporal_stabilizing")
        
        # Frame 2: "Hello World" (Line A flickers out)
        self.mock_pytesseract.image_to_string.return_value = "Hello World"
        result2 = self.client.analyze_screen(self.mock_image, "read", context_key=context_key)
        
        # Frame 2: "Hello World" seen twice -> Stable
        print(f"Frame 2 Result: {result2['text']}")
        self.assertEqual(result2['text'], "Hello World")
        self.assertEqual(result2['source'], "ocr_temporal_stable")
        
        # Frame 3: "Hello World\nLine B"
        self.mock_pytesseract.image_to_string.return_value = "Hello World\nLine B"
        result3 = self.client.analyze_screen(self.mock_image, "read", context_key=context_key)
        
        # Frame 3: "Hello World" still stable. "Line B" is new (unstable).
        print(f"Frame 3 Result: {result3['text']}")
        self.assertEqual(result3['text'], "Hello World")

if __name__ == '__main__':
    unittest.main()
