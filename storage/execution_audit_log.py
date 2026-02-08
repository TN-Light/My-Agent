"""
PHASE-7C: EXECUTION AUDIT LOG
Purpose: Immutable audit trail of ALL execution attempts (allowed/blocked)

NON-NEGOTIABLE RULES:
1. Every execution attempt MUST be logged
2. Logs are immutable (no updates, no deletes)
3. Log before execution, never after
4. Blocked attempts are as important as allowed attempts

Philosophy:
"What gets measured gets managed. What gets logged gets trusted."
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class ExecutionAuditLog:
    """
    Immutable audit log for all execution attempts.
    
    Logs both ALLOWED and BLOCKED attempts with full context.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize audit log database.
        
        Args:
            db_path: Path to SQLite database (default: execution_audit.db)
        """
        if db_path is None:
            # Default to db/ directory
            workspace_root = Path(__file__).parent.parent
            db_path = workspace_root / "db" / "execution_audit.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                
                -- Token information
                token_id TEXT,
                token_status TEXT,  -- VALID | REUSED | EXPIRED | MISSING
                
                -- Market context
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                market_mode TEXT NOT NULL,  -- INTRADAY | SWING
                
                -- Analysis context
                scenario_active TEXT NOT NULL,  -- A | B | C
                probability_a REAL NOT NULL,
                probability_b REAL NOT NULL,
                probability_c REAL NOT NULL,
                alignment_state TEXT NOT NULL,
                
                -- Risk context
                risk_requested REAL NOT NULL,
                risk_allowed REAL NOT NULL,
                risk_budget_status TEXT NOT NULL,  -- ALLOWED | BLOCKED
                
                -- Execution context
                execution_type TEXT NOT NULL,  -- MANUAL | AUTO
                execution_attempted INTEGER NOT NULL,  -- 0 or 1
                execution_result TEXT NOT NULL,  -- ALLOWED | BLOCKED
                
                -- Block information
                block_reason TEXT,  -- NULL if allowed
                block_gate TEXT,  -- Which gate blocked (STEP_1, STEP_2, etc.)
                
                -- Metadata
                created_at TEXT NOT NULL
            )
        """)
        
        # Index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_timestamp 
            ON execution_audit(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_symbol 
            ON execution_audit(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_execution_result 
            ON execution_audit(execution_result)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_id 
            ON execution_audit(token_id)
        """)
        
        conn.commit()
        conn.close()
    
    def log_execution_attempt(
        self,
        token_id: Optional[str],
        token_status: str,
        symbol: str,
        timeframe: str,
        market_mode: str,
        scenario_active: str,
        probability_a: float,
        probability_b: float,
        probability_c: float,
        alignment_state: str,
        risk_requested: float,
        risk_allowed: float,
        risk_budget_status: str,
        execution_type: str,
        execution_attempted: bool,
        execution_result: str,
        block_reason: Optional[str] = None,
        block_gate: Optional[str] = None
    ) -> int:
        """
        Log execution attempt.
        
        Args:
            token_id: Token identifier (None if no token)
            token_status: Token validation status
            symbol: Trading symbol
            timeframe: Chart timeframe
            market_mode: INTRADAY or SWING
            scenario_active: Active scenario (A/B/C)
            probability_a/b/c: Scenario probabilities
            alignment_state: Alignment state
            risk_requested: Risk amount requested
            risk_allowed: Risk amount allowed by budget
            risk_budget_status: Risk budget result
            execution_type: MANUAL or AUTO
            execution_attempted: Whether execution was attempted
            execution_result: ALLOWED or BLOCKED
            block_reason: Reason for blocking (if blocked)
            block_gate: Which gate blocked (if blocked)
        
        Returns:
            Log entry ID
        """
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO execution_audit (
                timestamp, token_id, token_status,
                symbol, timeframe, market_mode,
                scenario_active, probability_a, probability_b, probability_c,
                alignment_state, risk_requested, risk_allowed, risk_budget_status,
                execution_type, execution_attempted, execution_result,
                block_reason, block_gate, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, token_id, token_status,
            symbol, timeframe, market_mode,
            scenario_active, probability_a, probability_b, probability_c,
            alignment_state, risk_requested, risk_allowed, risk_budget_status,
            execution_type, int(execution_attempted), execution_result,
            block_reason, block_gate, timestamp
        ))
        
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return log_id
    
    def get_execution_count(self, result: Optional[str] = None) -> int:
        """
        Get count of execution attempts.
        
        Args:
            result: Filter by result (ALLOWED/BLOCKED), None for all
        
        Returns:
            Count of attempts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if result:
            cursor.execute(
                "SELECT COUNT(*) FROM execution_audit WHERE execution_result = ?",
                (result,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM execution_audit")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def get_block_reasons(self) -> Dict[str, int]:
        """
        Get distribution of block reasons.
        
        Returns:
            Dictionary mapping block_reason -> count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT block_reason, COUNT(*) as count
            FROM execution_audit
            WHERE execution_result = 'BLOCKED'
            GROUP BY block_reason
            ORDER BY count DESC
        """)
        
        results = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        return results
    
    def get_recent_attempts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent execution attempts.
        
        Args:
            limit: Maximum number of attempts to return
        
        Returns:
            List of attempt dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM execution_audit
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_symbol_history(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get execution history for a specific symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            List of attempt dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM execution_audit
            WHERE symbol = ?
            ORDER BY timestamp DESC
        """, (symbol,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_token_attempts(self, token_id: str) -> List[Dict[str, Any]]:
        """
        Get all attempts using a specific token.
        
        Args:
            token_id: Token identifier
        
        Returns:
            List of attempt dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM execution_audit
            WHERE token_id = ?
            ORDER BY timestamp ASC
        """, (token_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_selectivity_ratio(self) -> float:
        """
        Calculate execution selectivity ratio.
        
        Returns:
            Ratio of ALLOWED / TOTAL (0.0 - 1.0)
        """
        total = self.get_execution_count()
        if total == 0:
            return 0.0
        
        allowed = self.get_execution_count("ALLOWED")
        return allowed / total
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get audit log statistics.
        
        Returns:
            Dictionary with statistics
        """
        total = self.get_execution_count()
        allowed = self.get_execution_count("ALLOWED")
        blocked = self.get_execution_count("BLOCKED")
        
        selectivity = self.get_selectivity_ratio()
        block_reasons = self.get_block_reasons()
        
        return {
            "total_attempts": total,
            "allowed": allowed,
            "blocked": blocked,
            "selectivity_ratio": selectivity,
            "block_reasons": block_reasons
        }
