import unittest
from unittest.mock import MagicMock, patch
from logic.planner import Planner
from logic.llm_planner import LLMPlanner
from logic.llm_client import LLMClient
from common.observations import Observation, ObservationResult
from common.actions import Action
from common.plan_graph import PlanGraph

class TestPhase11Reasoning(unittest.TestCase):
    """
    Phase-11 Validation Tests: Vision-Aware Reasoning (No Execution)
    """

    def setUp(self):
        self.mock_llm_client = MagicMock(spec=LLMClient)
        self.planner = Planner(
            config={"planner": {"use_llm": True}},
            llm_client=self.mock_llm_client
        )
        # Ensure LLMPlanner is using the mock client
        self.planner.llm_planner.llm = self.mock_llm_client

    def test_vision_low_confidence_triggers_approval(self):
        """
        Scenario 1: Vision-only input (confidence <= 0.7) -> Planner asks for confirmation.
        """
        instruction = "Click the Submit button"
        
        # Context: Low confidence vision
        context = [
            ObservationResult(
                observation=Observation("vision", "desktop", target="Describe submit button"),
                status="success",
                result="There is a button labeled Submit at 100,200",
                metadata={"confidence": 0.6, "source": "vision_llm"}
            )
        ]
        
        # Mock LLM Output: Includes 'verify' field due to low confidence instructions
        mock_response = """
        [
            {
                "action_type": "click_control",
                "context": "desktop",
                "target": "Submit",
                "verify": {
                    "requires_approval": true,
                    "reason": "Action based on low-confidence vision: 0.6"
                }
            }
        ]
        """
        self.mock_llm_client.generate_completion.return_value = mock_response
        
        # Execute
        plan_graphs = self.planner.create_plan_graph(instruction, context=context)
        
        # Verify
        self.assertEqual(len(plan_graphs), 1)
        step = plan_graphs[0].steps[0]
        self.assertTrue(step.requires_approval, "Step should require approval due to low vision confidence")
        self.assertIn("Action based on low-confidence vision", step.intent)
        
        # Verify prompt included context
        args, _ = self.mock_llm_client.generate_completion.call_args
        user_prompt = args[1]
        self.assertIn("CONTEXT FROM OBSERVATIONS", user_prompt)
        self.assertIn("[VISION (Confidence: 0.6)]", user_prompt)

    def test_high_confidence_standard_plan(self):
        """
        Scenario 2: High confidence evidence (simulated or DOM) -> No special approval.
        """
        instruction = "Click the Save button"
        
        # Context: High confidence or no vision dependency marked
        # (Assuming LLM reasons it's safe)
        context = [] 
        
        mock_response = """
        [
            {
                "action_type": "click_control",
                "context": "desktop",
                "target": "Save"
            }
        ]
        """
        self.mock_llm_client.generate_completion.return_value = mock_response
        
        plan_graphs = self.planner.create_plan_graph(instruction, context=context)
        
        step = plan_graphs[0].steps[0]
        self.assertFalse(step.requires_approval)
        self.assertNotIn("low-confidence", step.intent)

    def test_conflicting_evidence_downgrades_confidence(self):
        """
        Scenario 3: Conflicting evidence -> Planner refuses action or asks for help.
        """
        instruction = "Click the OK button"
        
        context = [
             ObservationResult(
                observation=Observation("vision", "desktop", target="Locate OK button"),
                status="success", 
                result="OK button is verified visible",
                metadata={"confidence": 0.6, "source": "vision_llm"}
            ),
             ObservationResult(
                observation=Observation("read_text", "desktop", target="screen"),
                status="success", 
                result="No text found on screen" # Conflict
            )
        ]
        
        # LLM decides to ask for clarification/approval due to conflict
        mock_response = """
        [
            {
                "action_type": "wait",
                "context": "desktop",
                "target": "1",
                "verify": {
                    "requires_approval": true, 
                    "reason": "Conflicting evidence: Vision sees button but Text search does not."
                }
            }
        ]
        """
        self.mock_llm_client.generate_completion.return_value = mock_response
        
        plan_graphs = self.planner.create_plan_graph(instruction, context=context)
        
        step = plan_graphs[0].steps[0]
        self.assertTrue(step.requires_approval)
        self.assertIn("Conflicting evidence", step.intent)

if __name__ == '__main__':
    unittest.main()
