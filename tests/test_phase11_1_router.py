import unittest
from unittest.mock import MagicMock, patch
from logic.execution_engine import ExecutionEngine
from common.observations import Observation, ObservationResult

class TestPhase11_1_Router(unittest.TestCase):
    """
    Phase-11.1 Validation Tests: Observation Routing
    
    Verifies that pure observation queries bypass the planner.
    """

    def setUp(self):
        self.mock_planner = MagicMock()
        self.mock_observer = MagicMock()
        self.mock_obs_logger = MagicMock()
        
        # Minimal mock setup for ExecutionEngine dependencies
        self.engine = ExecutionEngine(
            config={},
            planner=self.mock_planner,
            policy_engine=MagicMock(),
            controller=MagicMock(),
            critic=MagicMock(),
            observer=self.mock_observer,
            action_logger=MagicMock(),
            plan_logger=MagicMock(),
            step_approval_logger=MagicMock(),
            observation_logger=self.mock_obs_logger
        )

    def test_direct_vision_routing(self):
        """
        Test that 'What do you see on my screen?' is routed directly to Observer,
        bypassing the Planner.
        """
        instruction = "What do you see on my screen?"
        
        # Mock Observer response
        fake_result = ObservationResult(
            observation=Observation("vision", "vision", target=instruction),
            status="success",
            result="I see a coding environment.",
            metadata={"confidence": 0.8}
        )
        self.mock_observer.observe.return_value = fake_result
        
        # Execute
        self.engine.execute_instruction(instruction)
        
        # Verify:
        # 1. Planner was NOT called
        self.mock_planner.create_plan_graph.assert_not_called()
        self.mock_planner.create_plan.assert_not_called()
        
        # 2. Observer WAS called with correct observation type
        self.mock_observer.observe.assert_called_once()
        args = self.mock_observer.observe.call_args[0]
        obs = args[0]
        self.assertIsInstance(obs, Observation)
        self.assertEqual(obs.observation_type, "vision")
        self.assertEqual(obs.target, instruction)
        
        # 3. Logger was called
        self.mock_obs_logger.log_observation.assert_called_once_with(fake_result)

    def test_normal_action_instruction(self):
        """
        Test that normal action instructions still use the planner.
        """
        instruction = "Open Notepad"
        
        # Execute
        self.engine.execute_instruction(instruction)
        
        # Verify:
        # 1. Planner WAS called
        self.mock_planner.create_plan_graph.assert_called_once()

if __name__ == '__main__':
    unittest.main()
