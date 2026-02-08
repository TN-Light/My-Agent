import unittest
from unittest.mock import MagicMock
from logic.execution_engine import ExecutionEngine
from common.observations import Observation, ObservationResult

class TestPhaseUIA_Rendering(unittest.TestCase):
    """
    Test Phase-UI-A: Observation Rendering in Chat UI
    """
    
    def setUp(self):
        self.mock_chat_ui = MagicMock()
        self.mock_observer = MagicMock()
        self.mock_obs_logger = MagicMock()
        
        self.engine = ExecutionEngine(
            config={},
            planner=MagicMock(),
            policy_engine=MagicMock(),
            controller=MagicMock(),
            critic=MagicMock(),
            observer=self.mock_observer,
            action_logger=MagicMock(),
            plan_logger=MagicMock(),
            step_approval_logger=MagicMock(),
            observation_logger=self.mock_obs_logger,
            chat_ui=self.mock_chat_ui # Inject mock UI
        )
        
    def test_observation_rendering_with_metadata(self):
        """Verify that observations are sent to UI with correct formatting."""
        instruction = "What do you see?"
        
        # Mock result
        result = ObservationResult(
            observation=Observation("vision", "vision", target=instruction),
            status="success",
            result="Detected text: Hello World",
            metadata={
                "confidence": 0.7,
                "source": "ocr",
                "advisory_only": True
            }
        )
        self.mock_observer.observe.return_value = result
        
        # Execute
        self.engine.execute_instruction(instruction)
        
        # Verify UI call
        self.mock_chat_ui.log.assert_called_once()
        args = self.mock_chat_ui.log.call_args
        message = args[0][0]
        level = args[0][1]
        
        self.assertEqual(level, "OBSERVATION")
        self.assertIn("Detected text: Hello World", message)
        self.assertIn("Confidence: 0.7", message)
        self.assertIn("Source: ocr", message)
        self.assertIn("Advisory", message)
        
    def test_observation_error_rendering(self):
        """Verify errors are shown in UI."""
        instruction = "What do you see?"
        self.mock_observer.observe.side_effect = Exception("Vision failure")
        
        self.engine.execute_instruction(instruction)
        
        self.mock_chat_ui.log.assert_called_with("Observation failed: Vision failure", "ERROR")

if __name__ == '__main__':
    unittest.main()
