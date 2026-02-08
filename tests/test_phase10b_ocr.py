import unittest
from PIL import Image
from perception.vision_client import VisionClient

class TestPhase10B_OCR(unittest.TestCase):
    def test_analyze_screen_ocr_fallback(self):
        """
        Verify that analyze_screen returns a structured dictionary
        even when OCR is not fully operational (graceful degradation).
        """
        # Create dummy client - connect check might fail but that's just a log
        client = VisionClient(base_url="http://fake:11434")
        
        # Create dummy image
        img = Image.new('RGB', (100, 100), color='white')
        
        # Execute
        result = client.analyze_screen(img, "test prompt")
        
        # Verify structure
        self.assertIsInstance(result, dict)
        self.assertIn("text", result)
        self.assertIn("confidence", result)
        self.assertIn("source", result)
        self.assertIn("advisory_only", result)
        
        print(f"\n[Test Output] Vision Result: {result}")
        
        # Verify safety constraints
        self.assertLessEqual(result["confidence"], 0.7)
        self.assertTrue(result["advisory_only"])

if __name__ == '__main__':
    unittest.main()
