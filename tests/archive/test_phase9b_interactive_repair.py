import unittest
from unittest.mock import MagicMock, patch
from logic.cli_repair_loop import CLIRepairLoop
from logic.recommendation_engine import Recommendation
from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action

class TestPhase9BInteractiveRepair(unittest.TestCase):
    def setUp(self):
        # Patch dependencies to avoid real DB connections
        with patch('logic.cli_repair_loop.ExecutionDiff'), \
             patch('logic.cli_repair_loop.DebugReporter'), \
             patch('logic.cli_repair_loop.RecommendationEngine'), \
             patch('logic.cli_repair_loop.PlanRepairEngine'):
            self.cli_loop = CLIRepairLoop()
        
        # Manually mock the recommendation engine and repair engine for tests
        self.cli_loop.recommender = MagicMock()
        self.cli_loop.repair_engine = MagicMock()
        self.cli_loop.diff_tool = MagicMock()
        self.cli_loop.reporter = MagicMock()
        
        # Create a dummy plan using PlanGraph
        self.plan = PlanGraph(
            instruction="test",
            steps=[
                PlanStep(
                    step_id=1, 
                    item=Action(action_type="launch_app", target="calc"),
                    intent="launch calc",
                    expected_outcome="calc opens"
                ),
                PlanStep(
                    step_id=2, 
                    item=Action(action_type="type_text", text="123"),
                    intent="type numbers",
                    expected_outcome="numbers appear"
                )
            ]
        )

    def test_no_recommendations(self):
        self.cli_loop.recommender.generate_recommendations.return_value = []
        result = self.cli_loop.propose_repairs(self.plan, 1, 2)
        self.assertIsNone(result)

    def test_user_rejects_repair(self):
        rec = Recommendation(
            category="TIMING",
            description="Add wait",
            confidence=0.8,
            evidence=["Too fast"],
            step_id=2
        )
        self.cli_loop.recommender.generate_recommendations.return_value = [rec]
        
        mock_input = MagicMock(return_value="n")
        
        result = self.cli_loop.propose_repairs(self.plan, 1, 2, input_func=mock_input)
        
        self.assertIsNone(result)
        self.cli_loop.repair_engine.apply_recommendation.assert_not_called()

    def test_user_accepts_repair(self):
        rec = Recommendation(
            category="TIMING",
            description="Add wait",
            confidence=0.8,
            evidence=["Too fast"],
            step_id=2
        )
        self.cli_loop.recommender.generate_recommendations.return_value = [rec]
        
        repaired_plan = PlanGraph(instruction="fixed", steps=[])
        self.cli_loop.repair_engine.apply_recommendation.return_value = repaired_plan
        
        mock_input = MagicMock(return_value="y")
        
        result = self.cli_loop.propose_repairs(self.plan, 1, 2, input_func=mock_input)
        
        self.assertEqual(result, repaired_plan)
        self.cli_loop.repair_engine.apply_recommendation.assert_called_once_with(self.plan, rec)

if __name__ == '__main__':
    unittest.main()
