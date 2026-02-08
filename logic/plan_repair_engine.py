"""
Plan Repair Engine - Phase-9A
Applies execution recommendations to create repaired PlanGraphs.

Scope:
- Deterministic application of fixes (Timing, Focus, Approval, Structure)
- Creates NEW PlanGraph objects (never mutates original)
- No autonomous execution or logging
"""

import logging
import copy
from typing import Optional, List
from common.plan_graph import PlanGraph, PlanStep
from common.actions import Action
from logic.recommendation_engine import Recommendation

logger = logging.getLogger(__name__)


class PlanRepairEngine:
    """
    Applies recommendations to repair execution plans.
    """

    def __init__(self):
        logger.info("PlanRepairEngine initialized")

    def apply_recommendation(
        self,
        original_plan: PlanGraph,
        recommendation: Recommendation
    ) -> Optional[PlanGraph]:
        """
        Apply a single recommendation to create a repaired plan.

        Args:
            original_plan: The failing plan
            recommendation: The fix to apply

        Returns:
            New PlanGraph with fix applied, or None if category not supported
        """
        # Create deep copy to ensure immutability of original
        new_plan = self._deep_copy_plan(original_plan)
        
        # Dispatch based on category
        if recommendation.category == "TIMING":
            return self._apply_timing_fix(new_plan, recommendation)
        
        elif recommendation.category == "FOCUS":
            return self._apply_focus_fix(new_plan, recommendation)
        
        elif recommendation.category == "APPROVAL":
            return self._apply_approval_fix(new_plan, recommendation)
            
        elif recommendation.category == "STRUCTURE":
            return self._apply_structure_fix(new_plan, recommendation)
            
        else:
            logger.warning(f"Unsupported recommendation category: {recommendation.category}")
            return None

    def _deep_copy_plan(self, plan: PlanGraph) -> PlanGraph:
        """Create a full independent copy of a PlanGraph."""
        # PlanGraph might not be fully picklable/copyable if it has complex objects,
        # but Action/PlanStep are dataclasses, so this should be fine.
        # However, for safety and control, we can reconstruct it.
        # Using deepcopy for now as dataclasses support it well.
        return copy.deepcopy(plan)

    def _reindex_steps(self, plan: PlanGraph):
        """
        Reassign step IDs to be sequential (1, 2, 3...)
        and update dependencies if necessary (Phase-5A dependencies are list of ints).
        
        Note: Currently dependencies are simple ID lists. 
        If we insert/remove, deep dependency logic might break if not careful.
        For MVP, we just reindex the linear list.
        """
        for i, step in enumerate(plan.steps):
            step.step_id = i + 1

    def _apply_timing_fix(self, plan: PlanGraph, rec: Recommendation) -> PlanGraph:
        """Insert 'wait' action before target step."""
        target_id = rec.step_id
        if target_id is None:
            return plan

        new_steps = []
        inserted = False
        
        for step in plan.steps:
            if step.step_id == target_id and not inserted:
                # Insert Wait
                wait_step = PlanStep(
                    step_id=0, # Will be reindexed
                    item=Action(action_type="wait", target="2", verify=False), # Default 2s wait
                    intent=f"Wait before Step {target_id} (Repair)",
                    expected_outcome="System stabilizes",
                    requires_approval=False
                )
                new_steps.append(wait_step)
                inserted = True
            
            new_steps.append(step)
        
        plan.steps = new_steps
        self._reindex_steps(plan)
        plan.instruction = f"{plan.instruction} (Repaired: Wait added)"
        return plan

    def _apply_focus_fix(self, plan: PlanGraph, rec: Recommendation) -> PlanGraph:
        """Insert 'focus_window' action before target step."""
        target_id = rec.step_id
        if target_id is None:
            return plan

        # We need a target for focus. 
        # Recommendation doesn't strictly carry the target name yet (it's in evidence or description).
        # For Phase-9A MVP, we'll try to extract from description or fail safe.
        # Or, we look at the failing step's target if it's an app interaction.
        
        # Heuristic: If description says "Add focus_window" we assume the user/planner 
        # needs to fill details, OR we infer from the NEXT step's target if possible.
        # But `focus_window` needs a valid app name.
        
        # Let's peek at the target step to see if we can guess the app.
        target_step = next((s for s in plan.steps if s.step_id == target_id), None)
        focus_target = "???"
        if target_step and isinstance(target_step.item, Action) and target_step.item.target:
             # Basic guess: if next step impacts "notepad.exe", focus "notepad"
             # This is imperfect but works for MVP repair.
             focus_target = target_step.item.target.replace(".exe", "")

        new_steps = []
        inserted = False
        
        for step in plan.steps:
            if step.step_id == target_id and not inserted:
                # Insert Focus
                focus_step = PlanStep(
                    step_id=0,
                    item=Action(action_type="focus_window", target=focus_target, verify=True),
                    intent=f"Focus window '{focus_target}' (Repair)",
                    expected_outcome="Window focused",
                    requires_approval=False
                )
                new_steps.append(focus_step)
                inserted = True
            
            new_steps.append(step)
        
        plan.steps = new_steps
        self._reindex_steps(plan)
        plan.instruction = f"{plan.instruction} (Repaired: Focus added)"
        return plan

    def _apply_approval_fix(self, plan: PlanGraph, rec: Recommendation) -> PlanGraph:
        """Set requires_approval=True for target step."""
        target_id = rec.step_id
        if target_id is None:
            return plan

        for step in plan.steps:
            if step.step_id == target_id:
                step.requires_approval = True
        
        plan.instruction = f"{plan.instruction} (Repaired: Approval added)"
        return plan

    def _apply_structure_fix(self, plan: PlanGraph, rec: Recommendation) -> PlanGraph:
        """
        Handle structure changes. 
        For "Consider removing... Step X", we remove it.
        """
        target_id = rec.step_id
        if target_id is None:
            return plan
            
        if "remove" in rec.description.lower() or "removing" in rec.description.lower():
            # Remove the step
            plan.steps = [s for s in plan.steps if s.step_id != target_id]
            self._reindex_steps(plan)
            plan.instruction = f"{plan.instruction} (Repaired: Step removed)"
            
        return plan
