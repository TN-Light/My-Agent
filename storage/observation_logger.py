"""
Observation Logger - Phase-2B
Separate SQLite logging for non-actional observations.

Phase-2B: Observations logged independently from actions for audit trail.
"""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional
from common.observations import ObservationResult

logger = logging.getLogger(__name__)


class ObservationLogger:
    """
    SQLite-based observation logger.
    
    Maintains separate audit trail for observations (read-only queries)
    distinct from action history. Observations never cause retries or
    verifications, so their logging is simpler than actions.
    
    Schema:
    - id: Auto-increment primary key
    - timestamp: ISO 8601 timestamp
    - observation_type: "read_text" | "query_element"
    - context: "desktop" | "web" | "file"
    - target: CSS selector, element name, or file path
    - result: Extracted text, attribute value, etc.
    - status: "success" | "not_found" | "error"
    - error: Error message (if status == "error")
    """
    
    def __init__(self, db_path: str = "db/observations.db"):
        """
        Initialize the observation logger.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()
        logger.info(f"ObservationLogger initialized: {db_path}")
    
    def _init_db(self):
        """Create observations table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                observation_type TEXT NOT NULL,
                context TEXT NOT NULL,
                target TEXT,
                result TEXT,
                status TEXT NOT NULL,
                error TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Observations table initialized")
    
    def log_observation(self, observation_result: ObservationResult) -> int:
        """
        Log an observation result.
        
        Args:
            observation_result: ObservationResult to log
            
        Returns:
            Row ID of inserted observation
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract fields from observation result
        obs = observation_result.observation
        timestamp = observation_result.timestamp or datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO observations (
                timestamp, observation_type, context, target, result, status, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            obs.observation_type,
            obs.context,
            obs.target,
            observation_result.result,
            observation_result.status,
            observation_result.error
        ))
        
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(
            f"Observation logged (id={row_id}): {obs.observation_type} "
            f"[{observation_result.status}]"
        )
        
        return row_id
    
    def get_recent_observations(self, limit: int = 10) -> list:
        """
        Get recent observations.
        
        Args:
            limit: Maximum number of observations to retrieve
            
        Returns:
            List of observation dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM observations
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_observations_by_context(self, context: str, limit: int = 10) -> list:
        """
        Get observations filtered by context.
        
        Args:
            context: Context to filter by ("desktop", "web", or "file")
            limit: Maximum number of observations to retrieve
            
        Returns:
            List of observation dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM observations
            WHERE context = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (context, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def clear_all_observations(self):
        """
        Clear all observations from the database.
        
        Use with caution - this permanently deletes all observation history.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM observations")
        
        conn.commit()
        conn.close()
        
        logger.warning("All observations cleared from database")
