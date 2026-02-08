"""
Phase-7A: Execution Gate Logger

Persistent storage for execution gate decisions.
Tracks when execution is allowed/blocked and reasons.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class ExecutionGateLogger:
    """
    Logs all execution gate evaluations for accountability and analysis.
    """
    
    def __init__(self, db_path: str = "db/execution_gate_log.db"):
        self.db_path = db_path
        self._init_database()
        logger.info(f"ExecutionGateLogger initialized: {db_path}")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gate_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    
                    -- Input State
                    alignment TEXT NOT NULL,
                    is_unstable BOOLEAN NOT NULL,
                    prob_a_continuation REAL NOT NULL,
                    prob_b_pullback REAL NOT NULL,
                    prob_c_failure REAL NOT NULL,
                    active_state TEXT NOT NULL,
                    current_price REAL,
                    
                    -- Gate Results
                    gate1_alignment TEXT NOT NULL,
                    gate2_dominance TEXT NOT NULL,
                    gate3_regime_risk TEXT NOT NULL,
                    gate4_structural_location TEXT NOT NULL,
                    gate5_overconfidence TEXT NOT NULL,
                    
                    -- Final Decision
                    execution_status TEXT NOT NULL,
                    blocked_reasons TEXT,
                    permission_granted BOOLEAN NOT NULL,
                    
                    -- Metadata
                    monthly_trend TEXT,
                    monthly_support_levels TEXT,
                    monthly_resistance_levels TEXT
                )
            """)
            
            # Index for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
                ON gate_evaluations(symbol, timestamp DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_execution_status
                ON gate_evaluations(execution_status, timestamp DESC)
            """)
            
            conn.commit()
            logger.info("Execution gate log database schema initialized")
    
    def log_evaluation(
        self,
        symbol: str,
        alignment: str,
        is_unstable: bool,
        probabilities: Dict[str, float],
        active_state: str,
        current_price: Optional[float],
        gate_results: Dict[str, str],
        execution_permission: Dict[str, Any],
        monthly_trend: str,
        monthly_support: List[float],
        monthly_resistance: List[float]
    ) -> int:
        """
        Log an execution gate evaluation.
        
        Returns:
            log_id: Database ID for this evaluation
        """
        
        timestamp = datetime.utcnow().isoformat()
        
        # Extract gate results
        gate1 = gate_results.get("Gate-1_Alignment", "UNKNOWN")
        gate2 = gate_results.get("Gate-2_Dominance", "UNKNOWN")
        gate3 = gate_results.get("Gate-3_RegimeRisk", "UNKNOWN")
        gate4 = gate_results.get("Gate-4_StructuralLocation", "UNKNOWN")
        gate5 = gate_results.get("Gate-5_Overconfidence", "UNKNOWN")
        
        # Extract probabilities
        prob_a = probabilities.get("A_continuation", 0)
        prob_b = probabilities.get("B_pullback", 0)
        prob_c = probabilities.get("C_failure", 0)
        
        # Extract execution permission
        execution_status = execution_permission.get("status", "UNKNOWN")
        blocked_reasons = json.dumps(execution_permission.get("reason", []))
        permission_granted = execution_status == "ALLOWED"
        
        # Serialize S/R levels
        monthly_support_json = json.dumps(monthly_support)
        monthly_resistance_json = json.dumps(monthly_resistance)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO gate_evaluations (
                    symbol, timestamp,
                    alignment, is_unstable,
                    prob_a_continuation, prob_b_pullback, prob_c_failure,
                    active_state, current_price,
                    gate1_alignment, gate2_dominance, gate3_regime_risk,
                    gate4_structural_location, gate5_overconfidence,
                    execution_status, blocked_reasons, permission_granted,
                    monthly_trend, monthly_support_levels, monthly_resistance_levels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timestamp,
                alignment, is_unstable,
                prob_a, prob_b, prob_c,
                active_state, current_price,
                gate1, gate2, gate3, gate4, gate5,
                execution_status, blocked_reasons, permission_granted,
                monthly_trend, monthly_support_json, monthly_resistance_json
            ))
            
            log_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Logged gate evaluation: {symbol} (ID: {log_id}, Status: {execution_status})")
            
            return log_id
    
    def get_allowed_count(self, symbol: Optional[str] = None, days: int = 30) -> int:
        """
        Count how many times execution was ALLOWED in the last N days.
        
        This shows how selective the gate is.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT COUNT(*) FROM gate_evaluations
                    WHERE symbol = ?
                    AND permission_granted = 1
                    AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
                """, (symbol, days))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM gate_evaluations
                    WHERE permission_granted = 1
                    AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
                """, (days,))
            
            return cursor.fetchone()[0]
    
    def get_blocked_count(self, symbol: Optional[str] = None, days: int = 30) -> int:
        """
        Count how many times execution was BLOCKED in the last N days.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT COUNT(*) FROM gate_evaluations
                    WHERE symbol = ?
                    AND permission_granted = 0
                    AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
                """, (symbol, days))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM gate_evaluations
                    WHERE permission_granted = 0
                    AND datetime(timestamp) >= datetime('now', '-' || ? || ' days')
                """, (days,))
            
            return cursor.fetchone()[0]
    
    def get_gate_failure_stats(self, days: int = 30) -> Dict[str, int]:
        """
        Get statistics on which gates fail most often.
        
        This identifies the most common blocking reasons.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN gate1_alignment = 'FAIL' THEN 1 ELSE 0 END) as gate1_fails,
                    SUM(CASE WHEN gate2_dominance = 'FAIL' THEN 1 ELSE 0 END) as gate2_fails,
                    SUM(CASE WHEN gate3_regime_risk = 'FAIL' THEN 1 ELSE 0 END) as gate3_fails,
                    SUM(CASE WHEN gate4_structural_location = 'FAIL' THEN 1 ELSE 0 END) as gate4_fails,
                    SUM(CASE WHEN gate5_overconfidence = 'FAIL' THEN 1 ELSE 0 END) as gate5_fails
                FROM gate_evaluations
                WHERE datetime(timestamp) >= datetime('now', '-' || ? || ' days')
            """, (days,))
            
            row = cursor.fetchone()
            
            return {
                "Gate-1 (Alignment)": row[0] if row else 0,
                "Gate-2 (Dominance)": row[1] if row else 0,
                "Gate-3 (Regime Risk)": row[2] if row else 0,
                "Gate-4 (Structural Location)": row[3] if row else 0,
                "Gate-5 (Overconfidence)": row[4] if row else 0
            }
    
    def get_selectivity_ratio(self, symbol: Optional[str] = None, days: int = 30) -> float:
        """
        Calculate selectivity ratio: allowed / total evaluations
        
        Lower is better - means the gate is highly selective.
        Target: < 0.20 (only 20% of opportunities pass)
        """
        allowed = self.get_allowed_count(symbol, days)
        blocked = self.get_blocked_count(symbol, days)
        total = allowed + blocked
        
        if total == 0:
            return 0.0
        
        return round(allowed / total, 3)
