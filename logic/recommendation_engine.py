"""
Recommendation Engine - Phase-8A
Generates deterministic, human-readable execution recommendations based on
execution history and diff analysis.

Scope: Read-only analysis of Original vs Replay executions.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from storage.execution_diff import ExecutionDiff, DiffResult
from storage.debug_reporter import DebugReporter
from storage.plan_logger import PlanLogger
from storage.action_logger import ActionLogger

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """
    Structured recommendation for plan improvement.
    """
    category: str  # e.g., "TIMING", "FOCUS", "APPROVAL", "STRUCTURE", "MANUAL"
    description: str
    evidence: List[str]
    confidence: float # Fixed values: 0.5 (Low), 0.7 (Medium), 0.9 (High)
    step_id: Optional[int] = None

    def __str__(self) -> str:
        return f"[{self.category}] {self.description} (Confidence: {self.confidence})"


class RecommendationEngine:
    """
    Analyzes execution differences to produce deterministic recommendations.
    """

    def __init__(
        self,
        execution_diff: ExecutionDiff,
        debug_reporter: DebugReporter
    ):
        """
        Initialize with analytical tools.

        Args:
            execution_diff: Tool for comparing executions
            debug_reporter: Tool for analyzing single execution failures
        """
        self.diff_tool = execution_diff
        self.reporter = debug_reporter
        logger.info("RecommendationEngine initialized")

    def generate_recommendations(
        self,
        original_plan_id: int,
        replay_plan_id: int
    ) -> List[Recommendation]:
        """
        Generate list of recommendations by analyzing history.

        Args:
            original_plan_id: ID of the base execution
            replay_plan_id: ID of the comparison execution (replay)

        Returns:
            List of Recommendation objects (deterministic)
        """
        # 1. Get Diff Result
        diff_result = self.diff_tool.diff_plans(original_plan_id, replay_plan_id)

        # 2. Get Failure Analysis (Dicts)
        original_info = self.reporter.get_failure_root_cause(original_plan_id)
        replay_info = self.reporter.get_failure_root_cause(replay_plan_id)

        recommendations = []

        # Analyze: Did Replay succeed where Original failed?
        original_failed = original_info.get("status") == "failed"
        replay_succeeded = replay_info.get("status") in ["completed", "success"]
        
        # Scenario A: Original Failed, Replay Succeeded
        if original_failed and replay_succeeded:
            self._analyze_recovery(
                diff_result, 
                original_info, 
                recommendations
            )
        
        # Scenario B: Both Failed
        elif original_failed and (replay_info.get("status") == "failed"):
             recommendations.append(Recommendation(
                category="MANUAL",
                description="Manual intervention required. Replay also failed.",
                evidence=[
                    f"Original status: {original_info.get('status')}",
                    f"Replay status: {replay_info.get('status')}",
                    f"Root cause: {original_info.get('root_cause')}"
                ],
                confidence=0.9
            ))
        
        # Scenario C: Step Skipped in Replay
        # Check for skipped steps in approval diffs
        for approval_diff in diff_result.approval_diffs:
            if approval_diff.original_value == "approved" and approval_diff.replay_value == "skipped":
                step_id = approval_diff.step_id
                recommendations.append(Recommendation(
                    category="STRUCTURE",
                    description=f"Consider removing or modifying Step {step_id}",
                    evidence=[
                        f"Step {step_id} was skipped in replay",
                        "Execution succeeded without this step" if replay_succeeded else "Execution state changed"
                    ],
                    confidence=0.7,
                    step_id=step_id
                ))

        return recommendations

    def _analyze_recovery(
        self,
        diff_result: DiffResult,
        original_info: dict,
        recommendations: List[Recommendation]
    ):
        """
        Analyze why replay succeeded when original failed.
        """
        # Find the specific step that failed in original but succeeded in replay
        # We look for execution diffs
        failure_step_id = None
        
        for diff in diff_result.execution_diffs:
            if diff.original_value == "failure" and diff.replay_value == "success":
                failure_step_id = diff.step_id
                break
        
        if not failure_step_id:
            return

        # Get error details from original_info
        error_msg = original_info.get("error") or ""
        message = original_info.get("message") or ""
        text_context = (str(error_msg) + " " + str(message)).lower()

        # 1. Timing Analysis
        # Heuristic: "found", "timeout", "visible" -> Timing
        is_timing_related = any(x in text_context for x in ["found", "timeout", "visible", "appear"])
        
        if is_timing_related:
            recommendations.append(Recommendation(
                category="TIMING",
                description=f"Insert wait before Step {failure_step_id}",
                evidence=[
                    f"Original failed at Step {failure_step_id}",
                    f"Error: {original_info.get('error', 'Unknown error')}",
                    "Replay succeeded (likely due to human pacing)"
                ],
                confidence=0.7,
                step_id=failure_step_id
            ))

        # 2. Focus Analysis
        # Heuristic: "focus", "window", "foreground" -> Focus
        is_focus_related = any(x in text_context for x in ["focus", "window", "foreground", "active"])
        if is_focus_related:
            recommendations.append(Recommendation(
                category="FOCUS",
                description=f"Add focus_window before Step {failure_step_id}",
                evidence=[
                    f"Original failed at Step {failure_step_id}",
                    f"Error: {original_info.get('error', 'Focus error')}",
                    "Replay succeeded"
                ],
                confidence=0.7,
                step_id=failure_step_id
            ))
        
        # 3. Approval Recommendation
        # If we have a recovery, it implies the step needs attention.
        if not is_timing_related and not is_focus_related:
             recommendations.append(Recommendation(
                category="APPROVAL",
                description=f"Require approval for Step {failure_step_id}",
                evidence=[
                    f"Step {failure_step_id} is prone to failure",
                    f"Error: {original_info.get('error', 'Unknown')}",
                    "Human verification recommended"
                ],
                confidence=0.5,
                step_id=failure_step_id
            ))

    def to_text_report(self, recommendations: List[Recommendation]) -> str:
        """
        Convert recommendations to human-readable text.
        """
        if not recommendations:
            return "NO RECOMMENDATIONS GENERATED"

        lines = []
        lines.append("="*70)
        lines.append("EXECUTION RECOMMENDATIONS")
        lines.append("="*70)
        
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec.category}: {rec.description}")
            lines.append(f"   Confidence: {rec.confidence:.2f}")
            lines.append("   Evidence:")
            for note in rec.evidence:
                lines.append(f"   - {note}")
            lines.append("")
            
        return "\n".join(lines)
