"""
Action Logger - SQLite Audit Log
Episodic Memory: Records all actions, results, and errors for debugging and learning.

Implements the "COMMIT" phase of the execution loop.
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from common.actions import Action, ActionResult

logger = logging.getLogger(__name__)


class ActionLogger:
    """
    SQLite-based audit logger for action history.
    
    Stores all actions, outcomes, and timestamps for:
    - Debugging failed actions
    - Avoiding repeated mistakes (future: Critic can query this)
    - User transparency (audit trail)
    """
    
    def __init__(self, db_path: str = "db/history.db"):
        """
        Initialize the action logger.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._create_tables()
        self._migrate_schema()
        
        logger.info(f"ActionLogger initialized: {self.db_path}")
    
    def _create_tables(self):
        """Create the action_history table if it doesn't exist."""
        cursor = self.connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                text_content TEXT,
                coordinates TEXT,
                success INTEGER NOT NULL,
                message TEXT,
                error TEXT,
                verification_evidence TEXT
            )
        """)
        
        self.connection.commit()
        logger.info("Database tables initialized")
    
    def _migrate_schema(self):
        """
        Migrate database schema to add new columns if they don't exist.
        
        Phase-3D: Added verification_evidence column.
        Phase-5B: Added plan_id column for linking actions to plans.
        This method safely adds missing columns without dropping data.
        """
        cursor = self.connection.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(action_history)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Phase-3D migration
        if 'verification_evidence' not in columns:
            logger.info("Migrating schema: Adding verification_evidence column...")
            cursor.execute("""
                ALTER TABLE action_history 
                ADD COLUMN verification_evidence TEXT
            """)
            self.connection.commit()
            logger.info("Schema migration complete: verification_evidence column added")
        else:
            logger.debug("Schema up to date: verification_evidence column exists")
        
        # Phase-5B migration
        if 'plan_id' not in columns:
            logger.info("Migrating schema: Adding plan_id column...")
            cursor.execute("""
                ALTER TABLE action_history 
                ADD COLUMN plan_id INTEGER
            """)
            self.connection.commit()
            logger.info("Schema migration complete: plan_id column added")
        else:
            logger.debug("Schema up to date: plan_id column exists")
    
    def log_action(self, result: ActionResult, plan_id: Optional[int] = None):
        """
        Log an action result to the database.
        
        Args:
            result: ActionResult from execution/verification
            plan_id: Optional plan identifier (Phase-5B)
        """
        import json
        
        cursor = self.connection.cursor()
        
        action = result.action
        timestamp = datetime.now().isoformat()
        
        # Convert coordinates tuple to string if present
        coords_str = None
        if action.coordinates:
            coords_str = f"{action.coordinates[0]},{action.coordinates[1]}"
        
        # Phase-3D: Convert verification_evidence to JSON
        evidence_json = None
        if result.verification_evidence:
            try:
                evidence_json = json.dumps(result.verification_evidence)
            except Exception as e:
                logger.warning(f"Failed to serialize verification evidence: {e}")
        
        cursor.execute("""
            INSERT INTO action_history 
            (timestamp, action_type, target, text_content, coordinates, success, message, error, verification_evidence, plan_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            action.action_type,
            action.target,
            action.text,
            coords_str,
            1 if result.success else 0,
            result.message,
            result.error,
            evidence_json,
            plan_id
        ))
        
        self.connection.commit()
        
        status = "[OK]" if result.success else "[FAIL]"
        plan_info = f" [Plan {plan_id}]" if plan_id else ""
        logger.info(f"{status} Logged: {action.action_type} - {result.message}{plan_info}")
    
    def get_recent_actions(self, limit: int = 10) -> List[dict]:
        """
        Get recent action history.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of action dictionaries
        """
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT timestamp, action_type, target, success, message, error
            FROM action_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        return [
            {
                "timestamp": row[0],
                "action_type": row[1],
                "target": row[2],
                "success": bool(row[3]),
                "message": row[4],
                "error": row[5]
            }
            for row in rows
        ]
    
    def get_failed_actions(self, limit: int = 10) -> List[dict]:
        """
        Get recent failed actions for debugging.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of failed action dictionaries
        """
        cursor = self.connection.cursor()
        
        cursor.execute("""
            SELECT timestamp, action_type, target, message, error
            FROM action_history
            WHERE success = 0
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        return [
            {
                "timestamp": row[0],
                "action_type": row[1],
                "target": row[2],
                "message": row[3],
                "error": row[4]
            }
            for row in rows
        ]
    
    def close(self):
        """Close the database connection."""
        self.connection.close()
        logger.info("ActionLogger connection closed")
