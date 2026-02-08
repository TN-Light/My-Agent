from typing import Optional, Callable
from storage.execution_diff import ExecutionDiff
from storage.debug_reporter import DebugReporter
from logic.recommendation_engine import RecommendationEngine
from logic.plan_repair_engine import PlanRepairEngine
from common.plan_graph import PlanGraph

class CLIRepairLoop:
    """
    Phase-9B: Interactive Repair Mode.
    Orchestrates the flow: Compare -> Recommend -> User Approve -> Repair.
    """
    def __init__(self, db_client=None):
        self.diff_tool = ExecutionDiff()
        self.reporter = DebugReporter()
        self.recommender = RecommendationEngine(self.diff_tool, self.reporter)
        self.repair_engine = PlanRepairEngine()

    def propose_repairs(self, 
                       plan: PlanGraph, 
                       original_run_id: int, 
                       replay_run_id: int, 
                       input_func: Callable[[str], str] = input) -> Optional[PlanGraph]:
        """
        Analyzes differences, suggests fixes, and interactively applies them.
        Returns a new PlanGraph if a repair was applied, or None if no repairs were made.
        """
        # 1. Compare executions (For visual feedback if needed, but Recommender does it internally)
        print(f"\nAnalyzing difference between Run {original_run_id} and Replay {replay_run_id}...")
        
        # 2. Generate recommendations
        recommendations = self.recommender.generate_recommendations(original_run_id, replay_run_id)

        if not recommendations:
            print("No repair recommendations found.")
            return None

        print(f"\nFound {len(recommendations)} potential repair(s):")

        # 3. Interactive Selection
        # For MVP, we process recommendations sequentially and return after the first applied fix
        # to ensure state consistency.
        for i, rec in enumerate(recommendations, 1):
            print(f"\nRECOMMENDATION #{i}")
            print(f"Type:       {rec.category}")
            print(f"Action:     {rec.description}")
            print(f"Confidence: {rec.confidence:.2f}")
            print(f"Reasoning:  {', '.join(rec.evidence)}")
            
            response = input_func(f"Apply this repair? [y/N]: ").strip().lower()
            
            if response == 'y':
                try:
                    print(f"Applying {rec.category} repair...")
                    new_plan = self.repair_engine.apply_recommendation(plan, rec)
                    print("✅ Repair applied successfully. A new plan reference has been created.")
                    return new_plan
                except Exception as e:
                    print(f"❌ Failed to apply repair: {e}")
                    return None
            else:
                print("Skipped.")

        print("No repairs applied.")
        return None
