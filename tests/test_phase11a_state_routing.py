import unittest
from unittest.mock import MagicMock
from logic.execution_engine import ExecutionEngine
from common.observations import Observation, ObservationResult

class TestPhase11A_StateRouting(unittest.TestCase):
    """
    Test Phase-11A: State Observation Intent Routing
    """
    
    def setUp(self):
        self.mock_observer = MagicMock()
        self.mock_obs_logger = MagicMock()
        
        # Partially mock engine to focus on routing logic
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
            observation_logger=self.mock_obs_logger
        )

    def test_detect_app_state_query(self):
        """Test routing of 'Is there a notepad window open?'"""
        instruction = "Is there a notepad window open?"
        
        # Execute detection
        obs = self.engine._detect_direct_observation(instruction)
        
        self.assertIsNotNone(obs)
        self.assertEqual(obs.observation_type, "check_app_state")
        self.assertEqual(obs.context, "desktop")
        # Target extraction heuristic check
        # "is there a notepad window open?" -> remove "is there a", "window", "open", "?" -> "notepad"
        self.assertIn("notepad", obs.target) 

    def test_routing_bypasses_planner(self):
        """Test execution flow bypasses planner."""
        instruction = "Is Chrome running?"
        
        # Setup mock return
        fake_result = ObservationResult(
            observation=Observation("check_app_state", "desktop", target="chrome"),
            status="success",
            result="Yes, Chrome is running"
        )
        self.mock_observer.observe.return_value = fake_result
        
        # Execute
        self.engine.execute_instruction(instruction)
        
        # Verify planner NOT called
        self.engine.planner.create_plan.assert_not_called()
        self.engine.planner.create_plan_graph.assert_not_called()
        
        # Verify observer called
        self.mock_observer.observe.assert_called_once()
        args = self.mock_observer.observe.call_args[0]
        self.assertEqual(args[0].observation_type, "check_app_state")

    def test_normal_instruction_passes_through(self):
        """Ensure normal commands are NOT routed as state checks."""
        instruction = "Open Notepad"
        obs = self.engine._detect_direct_observation(instruction)
        self.assertIsNone(obs)

if __name__ == '__main__':
    unittest.main()
