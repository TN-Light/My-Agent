"""
Plan Logger - Phase-5B Plan Persistence and Audit Trail

Persists PlanGraphs, tracks approval decisions, and maintains execution audit trail.
"""

import logging
import sqlite3
import json
from typing import Optional, List
from datetime import datetime
from common.plan_graph import PlanGraph

logger = logging.getLogger(__name__)


class PlanLogger:
    """
    Persists plan graphs and tracks their lifecycle.
    
    Phase-5B: Maintains complete audit trail from plan → approval → execution.
    """
    
    def __init__(self, db_path: str = "db/plans.db"):
        """
        Initialize plan logger with database.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_tables()
        logger.info(f"PlanLogger initialized: {db_path}")
    
    def _initialize_tables(self):
        """Create plans table if it doesn't exist."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                instruction TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                total_steps INTEGER,
                total_actions INTEGER,
                total_observations INTEGER,
                approval_required BOOLEAN,
                approval_status TEXT,
                approval_actor TEXT,
                approval_timestamp TEXT,
                created_at TEXT NOT NULL,
                execution_started_at TEXT,
                execution_completed_at TEXT,
                execution_status TEXT
            )
        """)
        
        self.conn.commit()
        logger.debug("Plans table initialized")
    
    def log_plan(self, plan_graph: PlanGraph, approval_required: bool) -> int:
        """
        Save plan to database before execution.
        
        Args:
            plan_graph: PlanGraph to persist
            approval_required: Whether approval is required
            
        Returns:
            plan_id for linking to action_history
        """
        cursor = self.conn.cursor()
        
        # Serialize plan to JSON
        plan_json = plan_graph.to_json()
        
        # Determine initial approval status
        if approval_required:
            approval_status = "pending"
        else:
            approval_status = "not_required"
        
        cursor.execute("""
            INSERT INTO plans (
                instruction,
                plan_json,
                total_steps,
                total_actions,
                total_observations,
                approval_required,
                approval_status,
                created_at,
                execution_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_graph.instruction,
            plan_json,
            len(plan_graph.steps),
            plan_graph.total_actions,
            plan_graph.total_observations,
            approval_required,
            approval_status,
            datetime.now().isoformat(),
            "pending"
        ))
        
        self.conn.commit()
        plan_id = cursor.lastrowid
        
        logger.info(f"[PLAN] Logged plan {plan_id}: {plan_graph.instruction}")
        logger.debug(f"  Steps: {len(plan_graph.steps)}, Approval: {approval_required}")
        
        return plan_id
    
    def update_approval(self, plan_id: int, approved: bool, actor: str, timestamp: str):
        """
        Record approval decision.
        
        Args:
            plan_id: Plan identifier
            approved: True if approved, False if rejected
            actor: Who made the decision (e.g., "local_user")
            timestamp: ISO format timestamp
        """
        cursor = self.conn.cursor()
        
        approval_status = "approved" if approved else "rejected"
        
        cursor.execute("""
            UPDATE plans
            SET approval_status = ?,
                approval_actor = ?,
                approval_timestamp = ?
            WHERE plan_id = ?
        """, (approval_status, actor, timestamp, plan_id))
        
        self.conn.commit()
        
        logger.info(f"[PLAN] Plan {plan_id} approval: {approval_status} by {actor}")
    
    def mark_execution_started(self, plan_id: int, timestamp: str):
        """
        Mark plan execution as started.
        
        Args:
            plan_id: Plan identifier
            timestamp: ISO format timestamp
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE plans
            SET execution_started_at = ?,
                execution_status = ?
            WHERE plan_id = ?
        """, (timestamp, "in_progress", plan_id))
        
        self.conn.commit()
        
        logger.info(f"[PLAN] Plan {plan_id} execution started at {timestamp}")
    
    def mark_execution_completed(self, plan_id: int, timestamp: str, status: str):
        """
        Mark plan execution as completed.
        
        Args:
            plan_id: Plan identifier
            timestamp: ISO format timestamp
            status: "completed", "failed", or "cancelled"
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE plans
            SET execution_completed_at = ?,
                execution_status = ?
            WHERE plan_id = ?
        """, (timestamp, status, plan_id))
        
        self.conn.commit()
        
        logger.info(f"[PLAN] Plan {plan_id} execution completed: {status} at {timestamp}")
    
    def get_plan(self, plan_id: int) -> Optional[dict]:
        """
        Retrieve plan by ID.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Plan record as dict or None if not found
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM plans WHERE plan_id = ?
        """, (plan_id,))
        
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def get_recent_plans(self, limit: int = 10) -> List[dict]:
        """
        Get recent plans for audit.
        
        Args:
            limit: Maximum number of plans to return
            
        Returns:
            List of plan records (most recent first)
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT * FROM plans
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("PlanLogger connection closed")
