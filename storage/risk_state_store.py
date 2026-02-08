"""
Phase-7B: Risk State Database

Persistent storage for risk tracking, loss streaks, and system state.
"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class RiskStateStore:
    """
    Database for tracking risk state across sessions.
    
    Tables:
    1. risk_sessions - Session metadata
    2. risk_events - Individual risk decisions
    3. loss_tracking - Daily loss tracking
    """
    
    def __init__(self, db_path: str = "db/risk_state.db"):
        """Initialize risk state database"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_database()
        logger.info(f"RiskStateStore initialized: {db_path}")
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table 1: Risk Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_sessions (
                session_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                starting_equity REAL NOT NULL,
                date TEXT NOT NULL,
                final_equity REAL,
                total_decisions INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                max_loss_streak INTEGER DEFAULT 0,
                final_state TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 2: Risk Events (Individual Decisions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                scenario TEXT NOT NULL,
                alignment TEXT NOT NULL,
                active_probability REAL NOT NULL,
                allowed INTEGER NOT NULL,
                max_risk_amount REAL,
                max_risk_percent REAL,
                block_reason TEXT,
                loss_streak_at_decision INTEGER,
                system_state TEXT,
                FOREIGN KEY (session_id) REFERENCES risk_sessions(session_id)
            )
        """)
        
        # Table 3: Loss Tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS loss_tracking (
                tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                realized_pnl REAL NOT NULL,
                risk_used REAL NOT NULL,
                loss_count INTEGER NOT NULL,
                loss_streak INTEGER NOT NULL,
                drawdown_pct REAL NOT NULL,
                halted INTEGER NOT NULL,
                system_state TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES risk_sessions(session_id)
            )
        """)
        
        # Table 4: Token Registry (Prevent reuse)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_registry (
                token_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                consumed_at TEXT,
                symbol TEXT NOT NULL,
                max_risk_amount REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES risk_sessions(session_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_session(
        self,
        session_id: str,
        mode: str,
        starting_equity: float,
        date: str
    ) -> None:
        """Create new risk tracking session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO risk_sessions (session_id, mode, starting_equity, date)
            VALUES (?, ?, ?, ?)
        """, (session_id, mode, starting_equity, date))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Risk session created: {session_id} ({mode}, ₹{starting_equity:,.2f})")
    
    def log_risk_event(
        self,
        session_id: str,
        symbol: str,
        scenario: str,
        alignment: str,
        active_probability: float,
        allowed: bool,
        max_risk_amount: float,
        max_risk_percent: float,
        block_reason: Optional[str],
        loss_streak: int,
        system_state: str
    ) -> None:
        """Log individual risk decision"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO risk_events (
                session_id, timestamp, symbol, scenario, alignment,
                active_probability, allowed, max_risk_amount, max_risk_percent,
                block_reason, loss_streak_at_decision, system_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.utcnow().isoformat(),
            symbol,
            scenario,
            alignment,
            active_probability,
            1 if allowed else 0,
            max_risk_amount,
            max_risk_percent,
            block_reason,
            loss_streak,
            system_state
        ))
        
        conn.commit()
        conn.close()
    
    def record_outcome(
        self,
        symbol: str,
        realized_pnl: float,
        risk_used: float,
        loss_streak: int,
        daily_drawdown_pct: float,
        system_state: str,
        session_id: str = "default"
    ) -> None:
        """Record trade outcome"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        loss_count = 1 if realized_pnl < 0 else 0
        halted = 1 if system_state in ["HALTED_TODAY", "LOCKDOWN"] else 0
        
        cursor.execute("""
            INSERT INTO loss_tracking (
                session_id, date, symbol, realized_pnl, risk_used,
                loss_count, loss_streak, drawdown_pct, halted, system_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.utcnow().date().isoformat(),
            symbol,
            realized_pnl,
            risk_used,
            loss_count,
            loss_streak,
            daily_drawdown_pct,
            halted,
            system_state
        ))
        
        # Update session stats
        cursor.execute("""
            UPDATE risk_sessions
            SET total_decisions = total_decisions + 1,
                wins = wins + ?,
                losses = losses + ?,
                max_loss_streak = MAX(max_loss_streak, ?),
                final_state = ?
            WHERE session_id = ?
        """, (
            1 if realized_pnl > 0 else 0,
            loss_count,
            loss_streak,
            system_state,
            session_id
        ))
        
        conn.commit()
        conn.close()
    
    def register_token(
        self,
        token_id: str,
        session_id: str,
        symbol: str,
        max_risk_amount: float
    ) -> None:
        """Register issued token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO token_registry (token_id, session_id, issued_at, symbol, max_risk_amount)
            VALUES (?, ?, ?, ?, ?)
        """, (
            token_id,
            session_id,
            datetime.utcnow().isoformat(),
            symbol,
            max_risk_amount
        ))
        
        conn.commit()
        conn.close()
    
    def consume_token(self, token_id: str) -> bool:
        """
        Mark token as consumed (atomic operation).
        
        Uses a single UPDATE with a WHERE guard to prevent TOCTOU races.
        
        Returns:
            True if token was valid and consumed, False if already used or doesn't exist
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Atomic check-and-update: only succeeds if token exists AND is unconsumed
        cursor.execute("""
            UPDATE token_registry
            SET consumed_at = ?
            WHERE token_id = ? AND consumed_at IS NULL
        """, (datetime.utcnow().isoformat(), token_id))
        
        consumed = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return consumed
    
    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        """Get session statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT mode, starting_equity, final_equity, total_decisions,
                   wins, losses, max_loss_streak, final_state
            FROM risk_sessions
            WHERE session_id = ?
        """, (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        return {
            "mode": result[0],
            "starting_equity": result[1],
            "final_equity": result[2],
            "total_decisions": result[3],
            "wins": result[4],
            "losses": result[5],
            "max_loss_streak": result[6],
            "final_state": result[7],
            "win_rate": result[4] / result[3] if result[3] > 0 else 0
        }
    
    def get_blocked_decisions_today(self, session_id: str) -> List[Dict]:
        """Get all blocked decisions today"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.utcnow().date().isoformat()
        
        cursor.execute("""
            SELECT timestamp, symbol, scenario, block_reason, system_state
            FROM risk_events
            WHERE session_id = ?
            AND DATE(timestamp) = ?
            AND allowed = 0
            ORDER BY timestamp DESC
        """, (session_id, today))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                "timestamp": r[0],
                "symbol": r[1],
                "scenario": r[2],
                "block_reason": r[3],
                "system_state": r[4]
            }
            for r in results
        ]
    
    def get_loss_streak_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get recent loss streak history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, symbol, realized_pnl, loss_streak, system_state
            FROM loss_tracking
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                "timestamp": r[0],
                "symbol": r[1],
                "realized_pnl": r[2],
                "loss_streak": r[3],
                "system_state": r[4]
            }
            for r in results
        ]
    
    def get_daily_drawdown(self, session_id: str, date: str) -> float:
        """Get total daily drawdown"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT SUM(realized_pnl)
            FROM loss_tracking
            WHERE session_id = ?
            AND date = ?
        """, (session_id, date))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] is not None else 0.0
    
    def close(self):
        """Close database connection"""
        # SQLite connections are created per-operation
        pass
