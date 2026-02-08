"""
Step Approval Logger - Phase-6A Step-Level Approval Persistence

Logs individual step approval decisions during plan execution.
"""

import logging
import sqlite3
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class StepApprovalLogger:
    """
    Persists step-level approval decisions.
    
    Phase-6A: Records approve/skip/reject decisions for each step during execution.
    """
    
    def __init__(self, db_path: str = "db/plans.db"):
        """
        Initialize step approval logger with database.
        
        Args:
            db_path: Path to SQLite database (shared with plan_logger)
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_tables()
        logger.info(f"StepApprovalLogger initialized: {db_path}")
    
    def _initialize_tables(self):
        """Create plan_step_approvals table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_step_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                step_id INTEGER NOT NULL,
                decision TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                reason TEXT
            )
        """)
        
        self.conn.commit()
        logger.debug("plan_step_approvals table initialized")
    
    def log_step_decision(
        self, 
        plan_id: int, 
        step_id: int, 
        decision: str, 
        timestamp: str,
        reason: Optional[str] = None
    ):
        """
        Record a step approval decision.
        
        Args:
            plan_id: Plan identifier
            step_id: Step identifier within the plan
            decision: 'approved' | 'skipped' | 'rejected'
            timestamp: ISO format timestamp
            reason: Optional explanation for the decision
        """
        # Validate decision
        valid_decisions = ['approved', 'skipped', 'rejected']
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision: {decision}. Must be one of {valid_decisions}")
        
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO plan_step_approvals (
                plan_id,
                step_id,
                decision,
                timestamp,
                reason
            ) VALUES (?, ?, ?, ?, ?)
        """, (plan_id, step_id, decision, timestamp, reason))
        
        self.conn.commit()
        
        logger.info(f"[STEP APPROVAL] Plan {plan_id}, Step {step_id}: {decision}")
        if reason:
            logger.debug(f"  Reason: {reason}")
    
    def get_decisions_for_plan(self, plan_id: int) -> List[dict]:
        """
        Retrieve all step decisions for a plan.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            List of decision records (most recent first)
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM plan_step_approvals
            WHERE plan_id = ?
            ORDER BY timestamp DESC
        """, (plan_id,))
        
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("StepApprovalLogger connection closed")
