"""
Execution Diff - Phase-7B Deterministic Execution Comparison

Compares two executions of the same PlanGraph (e.g., original vs replay).
Read-only analysis tool for understanding differences between executions.
"""

import logging
import sqlite3
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StepDiff:
    """Difference for a single step between two executions."""
    step_id: int
    dimension: str  # "approval" | "execution" | "verification"
    original_value: Any
    replay_value: Any
    description: str


@dataclass
class DiffResult:
    """
    Complete comparison result between two plan executions.
    
    Phase-7B: Structured diff with human-readable output.
    """
    original_plan_id: int
    replay_plan_id: int
    instruction: str
    differences: List[StepDiff] = field(default_factory=list)
    timing_delta_seconds: Optional[float] = None
    
    @property
    def has_differences(self) -> bool:
        """Check if any differences exist."""
        return len(self.differences) > 0
    
    @property
    def approval_diffs(self) -> List[StepDiff]:
        """Get only approval-related differences."""
        return [d for d in self.differences if d.dimension == "approval"]
    
    @property
    def execution_diffs(self) -> List[StepDiff]:
        """Get only execution-related differences."""
        return [d for d in self.differences if d.dimension == "execution"]
    
    @property
    def verification_diffs(self) -> List[StepDiff]:
        """Get only verification-related differences."""
        return [d for d in self.differences if d.dimension == "verification"]
    
    def to_text(self) -> str:
        """
        Generate human-readable text report.
        
        Returns:
            Multi-line string with comparison details
        """
        lines = []
        lines.append("="*70)
        lines.append("EXECUTION COMPARISON REPORT")
        lines.append("="*70)
        lines.append(f"Original Plan: {self.original_plan_id}")
        lines.append(f"Replay Plan: {self.replay_plan_id}")
        lines.append(f"Instruction: {self.instruction}")
        lines.append("")
        
        if not self.has_differences:
            lines.append("✅ NO DIFFERENCES DETECTED")
            lines.append("Both executions produced identical results.")
        else:
            lines.append(f"⚠️  {len(self.differences)} DIFFERENCE(S) DETECTED")
            lines.append("")
            
            # Group by dimension
            if self.approval_diffs:
                lines.append(f"Approval Differences ({len(self.approval_diffs)}):")
                lines.append("-" * 70)
                for diff in self.approval_diffs:
                    lines.append(f"  Step {diff.step_id}: {diff.description}")
                    lines.append(f"    Original: {diff.original_value}")
                    lines.append(f"    Replay:   {diff.replay_value}")
                    lines.append("")
            
            if self.execution_diffs:
                lines.append(f"Execution Differences ({len(self.execution_diffs)}):")
                lines.append("-" * 70)
                for diff in self.execution_diffs:
                    lines.append(f"  Step {diff.step_id}: {diff.description}")
                    lines.append(f"    Original: {diff.original_value}")
                    lines.append(f"    Replay:   {diff.replay_value}")
                    lines.append("")
            
            if self.verification_diffs:
                lines.append(f"Verification Differences ({len(self.verification_diffs)}):")
                lines.append("-" * 70)
                for diff in self.verification_diffs:
                    lines.append(f"  Step {diff.step_id}: {diff.description}")
                    lines.append(f"    Original: {diff.original_value}")
                    lines.append(f"    Replay:   {diff.replay_value}")
                    lines.append("")
        
        if self.timing_delta_seconds is not None:
            lines.append(f"Timing Delta: {self.timing_delta_seconds:.2f} seconds")
        
        lines.append("="*70)
        
        return "\n".join(lines)


class ExecutionDiff:
    """
    Deterministic execution comparison tool.
    
    Phase-7B: Compares two executions of the same PlanGraph.
    Read-only analysis with no side effects.
    """
    
    def __init__(
        self,
        plans_db_path: str = "db/plans.db",
        history_db_path: str = "db/history.db",
        observations_db_path: str = "db/observations.db"
    ):
        """
        Initialize execution diff tool.
        
        Args:
            plans_db_path: Path to plans database
            history_db_path: Path to action history database
            observations_db_path: Path to observations database
        """
        self.plans_db_path = plans_db_path
        self.history_db_path = history_db_path
        self.observations_db_path = observations_db_path
        
        logger.info("ExecutionDiff initialized (read-only)")
    
    def diff_plans(self, original_plan_id: int, replay_plan_id: int) -> DiffResult:
        """
        Compare two plan executions.
        
        Phase-7B: Generates complete diff across all dimensions.
        
        Args:
            original_plan_id: ID of original plan execution
            replay_plan_id: ID of replay plan execution
            
        Returns:
            DiffResult with all detected differences
        """
        # Connect to databases (read-only)
        plans_conn = sqlite3.connect(self.plans_db_path)
        plans_conn.row_factory = sqlite3.Row
        
        history_conn = sqlite3.connect(self.history_db_path)
        history_conn.row_factory = sqlite3.Row
        
        observations_conn = sqlite3.connect(self.observations_db_path)
        observations_conn.row_factory = sqlite3.Row
        
        try:
            # Load plan metadata
            original_plan = self._get_plan(plans_conn, original_plan_id)
            replay_plan = self._get_plan(plans_conn, replay_plan_id)
            
            if not original_plan:
                logger.error(f"Original plan {original_plan_id} not found")
                return DiffResult(
                    original_plan_id=original_plan_id,
                    replay_plan_id=replay_plan_id,
                    instruction="ERROR: Original plan not found",
                    differences=[]
                )
            
            if not replay_plan:
                logger.error(f"Replay plan {replay_plan_id} not found")
                return DiffResult(
                    original_plan_id=original_plan_id,
                    replay_plan_id=replay_plan_id,
                    instruction=original_plan["instruction"],
                    differences=[]
                )
            
            # Initialize result
            result = DiffResult(
                original_plan_id=original_plan_id,
                replay_plan_id=replay_plan_id,
                instruction=original_plan["instruction"]
            )
            
            # Calculate timing delta
            if original_plan["execution_started_at"] and replay_plan["execution_started_at"]:
                try:
                    original_start = datetime.fromisoformat(original_plan["execution_started_at"])
                    replay_start = datetime.fromisoformat(replay_plan["execution_started_at"])
                    
                    if original_plan["execution_completed_at"] and replay_plan["execution_completed_at"]:
                        original_end = datetime.fromisoformat(original_plan["execution_completed_at"])
                        replay_end = datetime.fromisoformat(replay_plan["execution_completed_at"])
                        
                        original_duration = (original_end - original_start).total_seconds()
                        replay_duration = (replay_end - replay_start).total_seconds()
                        
                        result.timing_delta_seconds = replay_duration - original_duration
                except Exception as e:
                    logger.warning(f"Could not calculate timing delta: {e}")
            
            # Compare approvals
            approval_diffs = self.compare_approvals(
                plans_conn,
                original_plan_id,
                replay_plan_id
            )
            result.differences.extend(approval_diffs)
            
            # Compare actions
            action_diffs = self.compare_actions(
                history_conn,
                original_plan_id,
                replay_plan_id
            )
            result.differences.extend(action_diffs)
            
            # Compare verifications
            verification_diffs = self.compare_verifications(
                observations_conn,
                original_plan_id,
                replay_plan_id
            )
            result.differences.extend(verification_diffs)
            
            # Compare execution status
            if original_plan["execution_status"] != replay_plan["execution_status"]:
                result.differences.append(StepDiff(
                    step_id=0,  # Plan-level
                    dimension="execution",
                    original_value=original_plan["execution_status"],
                    replay_value=replay_plan["execution_status"],
                    description="Overall execution status differs"
                ))
            
            logger.info(f"[DIFF] Compared plans {original_plan_id} vs {replay_plan_id}: {len(result.differences)} differences")
            
            return result
            
        finally:
            plans_conn.close()
            history_conn.close()
            observations_conn.close()
    
    def compare_approvals(
        self,
        plans_conn: sqlite3.Connection,
        original_plan_id: int,
        replay_plan_id: int
    ) -> List[StepDiff]:
        """
        Compare step approval decisions between two executions.
        
        Args:
            plans_conn: Connection to plans database
            original_plan_id: Original plan ID
            replay_plan_id: Replay plan ID
            
        Returns:
            List of StepDiff for approval differences
        """
        diffs = []
        
        try:
            cursor = plans_conn.cursor()
            
            # Get approvals for original plan
            cursor.execute("""
                SELECT step_id, decision
                FROM plan_step_approvals
                WHERE plan_id = ?
                ORDER BY step_id
            """, (original_plan_id,))
            
            original_approvals = {row["step_id"]: row["decision"] for row in cursor.fetchall()}
            
            # Get approvals for replay plan
            cursor.execute("""
                SELECT step_id, decision
                FROM plan_step_approvals
                WHERE plan_id = ?
                ORDER BY step_id
            """, (replay_plan_id,))
            
            replay_approvals = {row["step_id"]: row["decision"] for row in cursor.fetchall()}
            
            # Find differences
            all_step_ids = set(original_approvals.keys()) | set(replay_approvals.keys())
            
            for step_id in sorted(all_step_ids):
                original_decision = original_approvals.get(step_id, "not_recorded")
                replay_decision = replay_approvals.get(step_id, "not_recorded")
                
                if original_decision != replay_decision:
                    diffs.append(StepDiff(
                        step_id=step_id,
                        dimension="approval",
                        original_value=original_decision,
                        replay_value=replay_decision,
                        description=f"Approval decision changed"
                    ))
        
        except sqlite3.OperationalError:
            # Table doesn't exist (Phase-6A not enabled)
            logger.debug("plan_step_approvals table not found - skipping approval comparison")
        
        return diffs
    
    def compare_actions(
        self,
        history_conn: sqlite3.Connection,
        original_plan_id: int,
        replay_plan_id: int
    ) -> List[StepDiff]:
        """
        Compare action execution results between two executions.
        
        Args:
            history_conn: Connection to history database
            original_plan_id: Original plan ID
            replay_plan_id: Replay plan ID
            
        Returns:
            List of StepDiff for action execution differences
        """
        diffs = []
        
        cursor = history_conn.cursor()
        
        # Get actions for original plan
        cursor.execute("""
            SELECT *
            FROM action_history
            WHERE plan_id = ?
            ORDER BY timestamp
        """, (original_plan_id,))
        
        original_actions = [dict(row) for row in cursor.fetchall()]
        
        # Get actions for replay plan
        cursor.execute("""
            SELECT *
            FROM action_history
            WHERE plan_id = ?
            ORDER BY timestamp
        """, (replay_plan_id,))
        
        replay_actions = [dict(row) for row in cursor.fetchall()]
        
        # Compare action counts
        if len(original_actions) != len(replay_actions):
            diffs.append(StepDiff(
                step_id=0,  # Plan-level
                dimension="execution",
                original_value=f"{len(original_actions)} actions",
                replay_value=f"{len(replay_actions)} actions",
                description="Different number of actions executed"
            ))
        
        # Compare each action
        for idx in range(min(len(original_actions), len(replay_actions))):
            original_action = original_actions[idx]
            replay_action = replay_actions[idx]
            
            # Compare action type
            if original_action["action_type"] != replay_action["action_type"]:
                diffs.append(StepDiff(
                    step_id=idx + 1,
                    dimension="execution",
                    original_value=original_action["action_type"],
                    replay_value=replay_action["action_type"],
                    description="Action type differs"
                ))
            
            # Compare success/failure
            if original_action["success"] != replay_action["success"]:
                diffs.append(StepDiff(
                    step_id=idx + 1,
                    dimension="execution",
                    original_value="success" if original_action["success"] else "failure",
                    replay_value="success" if replay_action["success"] else "failure",
                    description="Action execution result differs"
                ))
        
        return diffs
    
    def compare_verifications(
        self,
        observations_conn: sqlite3.Connection,
        original_plan_id: int,
        replay_plan_id: int
    ) -> List[StepDiff]:
        """
        Compare verification results between two executions.
        
        Args:
            observations_conn: Connection to observations database
            original_plan_id: Original plan ID
            replay_plan_id: Replay plan ID
            
        Returns:
            List of StepDiff for verification differences
        """
        diffs = []
        
        try:
            cursor = observations_conn.cursor()
            
            # Get verification evidence for original plan
            cursor.execute("""
                SELECT *
                FROM verification_evidence
                WHERE plan_id = ?
                ORDER BY timestamp
            """, (original_plan_id,))
            
            original_verifications = [dict(row) for row in cursor.fetchall()]
            
            # Get verification evidence for replay plan
            cursor.execute("""
                SELECT *
                FROM verification_evidence
                WHERE plan_id = ?
                ORDER BY timestamp
            """, (replay_plan_id,))
            
            replay_verifications = [dict(row) for row in cursor.fetchall()]
            
            # Compare verification counts
            if len(original_verifications) != len(replay_verifications):
                diffs.append(StepDiff(
                    step_id=0,  # Plan-level
                    dimension="verification",
                    original_value=f"{len(original_verifications)} verifications",
                    replay_value=f"{len(replay_verifications)} verifications",
                    description="Different number of verifications"
                ))
            
            # Compare each verification
            for idx in range(min(len(original_verifications), len(replay_verifications))):
                original_ver = original_verifications[idx]
                replay_ver = replay_verifications[idx]
                
                # Compare verified status
                if original_ver["verified"] != replay_ver["verified"]:
                    diffs.append(StepDiff(
                        step_id=idx + 1,
                        dimension="verification",
                        original_value="verified" if original_ver["verified"] else "not_verified",
                        replay_value="verified" if replay_ver["verified"] else "not_verified",
                        description="Verification status differs"
                    ))
                
                # Compare confidence (if available)
                if "confidence" in original_ver and "confidence" in replay_ver:
                    original_conf = original_ver["confidence"]
                    replay_conf = replay_ver["confidence"]
                    
                    # Only report if difference is significant (>0.1)
                    if abs(original_conf - replay_conf) > 0.1:
                        diffs.append(StepDiff(
                            step_id=idx + 1,
                            dimension="verification",
                            original_value=f"confidence={original_conf:.2f}",
                            replay_value=f"confidence={replay_conf:.2f}",
                            description="Verification confidence differs"
                        ))
        
        except sqlite3.OperationalError:
            # Table doesn't exist
            logger.debug("verification_evidence table not found - skipping verification comparison")
        
        return diffs
    
    def _get_plan(self, conn: sqlite3.Connection, plan_id: int) -> Optional[Dict]:
        """Get plan metadata from database."""
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
