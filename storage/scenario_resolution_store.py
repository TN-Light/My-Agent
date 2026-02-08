"""
Phase-6A: Scenario Resolution Tracker

Persistent storage for scenario probability assignments and post-fact resolution outcomes.
Enables long-term accuracy measurement without predictions.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional, Any
import json

logger = logging.getLogger(__name__)


class ScenarioResolutionStore:
    """
    Tracks scenario probability assignments and eventual resolutions.
    This is NOT for prediction - it's for measuring structural accuracy over time.
    """
    
    def __init__(self, db_path: str = "db/scenario_resolutions.db"):
        self.db_path = db_path
        self._init_database()
        logger.info(f"ScenarioResolutionStore initialized: {db_path}")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Main scenario tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scenario_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    timeframes TEXT NOT NULL,
                    
                    -- Market State
                    alignment TEXT NOT NULL,
                    is_unstable BOOLEAN NOT NULL,
                    monthly_trend TEXT NOT NULL,
                    htf_location TEXT NOT NULL,
                    current_price REAL,
                    
                    -- Scenario Probabilities
                    prob_a_continuation REAL NOT NULL,
                    prob_b_pullback REAL NOT NULL,
                    prob_c_failure REAL NOT NULL,
                    
                    -- Reasoning
                    reason_a TEXT,
                    reason_b TEXT,
                    reason_c TEXT,
                    
                    -- Active State
                    active_state TEXT NOT NULL,
                    
                    -- Structural Levels
                    monthly_support_levels TEXT,
                    monthly_resistance_levels TEXT,
                    weekly_support_levels TEXT,
                    weekly_resistance_levels TEXT,
                    
                    -- Validation
                    probability_sum_check REAL NOT NULL,
                    consistency_status TEXT NOT NULL,
                    consistency_flags TEXT,
                    
                    -- Resolution (filled later, manually or by policy)
                    resolved_scenario TEXT,
                    resolution_time TEXT,
                    structure_respected BOOLEAN,
                    resolution_notes TEXT
                )
            """)
            
            # Index for fast lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
                ON scenario_analyses(symbol, timestamp DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_unresolved
                ON scenario_analyses(symbol, resolved_scenario)
                WHERE resolved_scenario IS NULL
            """)
            
            conn.commit()
            logger.info("Scenario resolution database schema initialized")
    
    def store_analysis(
        self,
        symbol: str,
        timeframes: str,
        alignment: str,
        is_unstable: bool,
        monthly_trend: str,
        htf_location: str,
        current_price: Optional[float],
        probabilities: Dict[str, float],
        reasoning: Dict[str, str],
        active_state: str,
        support_resistance: Dict[str, Any],
        validation: Dict[str, Any]
    ) -> int:
        """
        Store a new scenario analysis record.
        
        Returns:
            analysis_id: Database ID for this analysis
        """
        
        timestamp = datetime.utcnow().isoformat()
        
        # Extract probability values
        prob_a = probabilities.get("A_continuation", 0)
        prob_b = probabilities.get("B_pullback", 0)
        prob_c = probabilities.get("C_failure", 0)
        
        # Extract reasoning
        reason_a = reasoning.get("A_reason", "")
        reason_b = reasoning.get("B_reason", "")
        reason_c = reasoning.get("C_reason", "")
        
        # Serialize S/R levels
        monthly_support = json.dumps(support_resistance.get("monthly_support", []))
        monthly_resistance = json.dumps(support_resistance.get("monthly_resistance", []))
        weekly_support = json.dumps(support_resistance.get("weekly_support", []))
        weekly_resistance = json.dumps(support_resistance.get("weekly_resistance", []))
        
        # Validation data
        prob_sum = validation.get("sum_check", 0)
        consistency_status = validation.get("consistency", "UNKNOWN")
        consistency_flags = json.dumps(validation.get("flags", []))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scenario_analyses (
                    symbol, timestamp, timeframes,
                    alignment, is_unstable, monthly_trend, htf_location, current_price,
                    prob_a_continuation, prob_b_pullback, prob_c_failure,
                    reason_a, reason_b, reason_c,
                    active_state,
                    monthly_support_levels, monthly_resistance_levels,
                    weekly_support_levels, weekly_resistance_levels,
                    probability_sum_check, consistency_status, consistency_flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timestamp, timeframes,
                alignment, is_unstable, monthly_trend, htf_location, current_price,
                prob_a, prob_b, prob_c,
                reason_a, reason_b, reason_c,
                active_state,
                monthly_support, monthly_resistance,
                weekly_support, weekly_resistance,
                prob_sum, consistency_status, consistency_flags
            ))
            
            analysis_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Stored scenario analysis: {symbol} (ID: {analysis_id}, Active: {active_state})")
            
            return analysis_id
    
    def resolve_analysis(
        self,
        analysis_id: int,
        resolved_scenario: str,
        structure_respected: bool,
        notes: Optional[str] = None
    ) -> bool:
        """
        Mark an analysis as resolved with outcome.
        
        This is NEVER automated - always manual or policy-driven.
        
        Args:
            analysis_id: Database ID of the analysis
            resolved_scenario: "A" | "B" | "C" | "UNRESOLVED"
            structure_respected: Did the market respect structural levels?
            notes: Optional explanation
        
        Returns:
            Success status
        """
        
        resolution_time = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE scenario_analyses
                SET resolved_scenario = ?,
                    resolution_time = ?,
                    structure_respected = ?,
                    resolution_notes = ?
                WHERE id = ?
            """, (resolved_scenario, resolution_time, structure_respected, notes, analysis_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                logger.info(f"Resolved analysis {analysis_id}: Scenario {resolved_scenario}")
                return True
            else:
                logger.warning(f"Analysis {analysis_id} not found for resolution")
                return False
    
    def get_unresolved_analyses(self, symbol: Optional[str] = None) -> list:
        """
        Get all analyses that haven't been resolved yet.
        
        Args:
            symbol: Optional filter by symbol
        
        Returns:
            List of unresolved analysis records
        """
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute("""
                    SELECT * FROM scenario_analyses
                    WHERE symbol = ? AND resolved_scenario IS NULL
                    ORDER BY timestamp DESC
                """, (symbol,))
            else:
                cursor.execute("""
                    SELECT * FROM scenario_analyses
                    WHERE resolved_scenario IS NULL
                    ORDER BY timestamp DESC
                """)
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_accuracy_stats(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate accuracy statistics for resolved scenarios.
        
        This measures how often the highest-probability scenario actually occurred.
        
        Returns:
            Dict with accuracy metrics
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Base query
            query = """
                SELECT 
                    COUNT(*) as total_resolved,
                    SUM(CASE WHEN active_state = 'SCENARIO_A' AND resolved_scenario = 'A' THEN 1 ELSE 0 END) as a_correct,
                    SUM(CASE WHEN active_state = 'SCENARIO_B' AND resolved_scenario = 'B' THEN 1 ELSE 0 END) as b_correct,
                    SUM(CASE WHEN active_state = 'SCENARIO_C' AND resolved_scenario = 'C' THEN 1 ELSE 0 END) as c_correct,
                    SUM(CASE WHEN active_state LIKE 'SCENARIO_%' THEN 1 ELSE 0 END) as total_scenario_predictions,
                    SUM(CASE WHEN structure_respected = 1 THEN 1 ELSE 0 END) as structure_respected_count,
                    AVG(prob_a_continuation) as avg_prob_a,
                    AVG(prob_b_pullback) as avg_prob_b,
                    AVG(prob_c_failure) as avg_prob_c
                FROM scenario_analyses
                WHERE resolved_scenario IS NOT NULL
            """
            
            if symbol:
                query += " AND symbol = ?"
                cursor.execute(query, (symbol,))
            else:
                cursor.execute(query)
            
            row = cursor.fetchone()
            
            if not row or row[0] == 0:
                return {
                    "total_resolved": 0,
                    "accuracy": 0.0,
                    "structure_respect_rate": 0.0,
                    "message": "No resolved analyses yet"
                }
            
            total = row[0]
            correct = row[1] + row[2] + row[3]
            scenario_predictions = row[4]
            structure_respected = row[5]
            
            accuracy = (correct / scenario_predictions * 100) if scenario_predictions > 0 else 0
            structure_rate = (structure_respected / total * 100) if total > 0 else 0
            
            return {
                "total_resolved": total,
                "correct_predictions": correct,
                "accuracy_pct": round(accuracy, 1),
                "structure_respect_rate_pct": round(structure_rate, 1),
                "avg_probabilities": {
                    "A": round(row[6], 2) if row[6] else 0,
                    "B": round(row[7], 2) if row[7] else 0,
                    "C": round(row[8], 2) if row[8] else 0
                }
            }
