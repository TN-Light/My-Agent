import sys
import unittest
import logging
import time
from unittest.mock import patch
from main import Agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CloseFixTest")

class TestCloseFix(unittest.TestCase):
    def setUp(self):
        # Initialize Agent with real components
        self.agent = Agent()

    @patch('builtins.input')
    def test_launch_and_close_notepad(self, mock_input):
        """
        Scenario:
        1. Open notepad (instruction="open notepad")
        2. Close notepad (instruction="close application notepad.exe")
        
        Expected:
        - Controller tracks window handle after launch.
        - Close uses tracked handle.
        - Success verifying fix.
        """
        print("\n\n>>> RUNNING TEST: Launch and Close Notepad (Fix Verification)")
        
        # Approve plan (y), and execution steps (approve)
        # Plan 1 (open): 1 step -> 'y', 'approve'
        # Plan 2 (close): 1 step -> 'y', 'approve'
        mock_input.side_effect = ['y', 'approve', 'y', 'approve'] 
        
        # 1. Launch Notepad
        print("--- Step 1: Launch ---")
        self.agent.execute_instruction("open notepad")
        
        # Assertions for Launch
        self.assertIn("notepad.exe", self.agent.controller.launched_apps, "Notepad should be tracked in launched_apps")
        track_entry = self.agent.controller.launched_apps["notepad.exe"]
        print(f"Tracked handle: {track_entry.handle}")
        self.assertNotEqual(track_entry.handle, 0, "Handle should be non-zero")
        
        # 2. Close Notepad
        print("--- Step 2: Close ---")
        self.agent.execute_instruction("close application notepad.exe")
        
        # Assertions for Close
        self.assertNotIn("notepad.exe", self.agent.controller.launched_apps, "Notepad should be removed from launched_apps after close")
        print("✅ Test Passed: Notepad closed using tracked handle.")

if __name__ == '__main__':
    unittest.main()
