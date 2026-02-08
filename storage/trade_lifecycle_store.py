"""
PHASE-8A: TRADE LIFECYCLE DATABASE
Purpose: Persistent storage for trade execution facts

NON-NEGOTIABLE RULES:
1. Store facts only, no opinions
2. No profit labels - structure decides correctness
3. Immutable after creation (updates only for exit/resolution)
4. MAE/MFE tracked for expectancy measurement

Philosophy:
"Facts first. Structure decides. Edge is proven, not assumed."
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class TradeLifecycleStore:
    """
    Persistent storage for trade lifecycle tracking.
    
    Tracks execution facts, resolution, and structural validity.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize trade lifecycle database.
        
        Args:
            db_path: Path to SQLite database (default: trade_lifecycle.db)
        """
        if db_path is None:
            workspace_root = Path(__file__).parent.parent
            db_path = workspace_root / "db" / "trade_lifecycle.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                
                -- Market context
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                market_mode TEXT NOT NULL,  -- INTRADAY | SWING
                
                -- Scenario context
                scenario TEXT NOT NULL,  -- A | B | C
                probability REAL NOT NULL,
                alignment_state TEXT NOT NULL,
                
                -- HTF structure context (for resolution)
                htf_support REAL,
                htf_resistance REAL,
                htf_direction TEXT,  -- BULLISH | BEARISH | NEUTRAL
                
                -- Entry
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                direction TEXT NOT NULL,  -- LONG | SHORT
                
                -- Exit (NULL until closed)
                exit_price REAL,
                exit_time TEXT,
                exit_reason TEXT,  -- TIME | STRUCTURE_BREAK | MANUAL | AUTO_EXIT
                
                -- Excursion tracking
                mae REAL,  -- Max Adverse Excursion (worst point)
                mfe REAL,  -- Max Favorable Excursion (best point)
                
                -- Resolution (NULL until resolved)
                resolved_scenario TEXT,  -- Which scenario actually played out
                structure_respected INTEGER,  -- 1=TRUE, 0=FALSE, NULL=unresolved
                resolution_confidence TEXT,  -- HIGH | MEDIUM | LOW
                resolution_time TEXT,
                resolution_notes TEXT,
                
                -- Metadata
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_symbol 
            ON trades(symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_scenario 
            ON trades(scenario)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_market_mode 
            ON trades(market_mode)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_entry_time 
            ON trades(entry_time)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_structure_respected 
            ON trades(structure_respected)
        """)
        
        conn.commit()
        conn.close()
    
    def create_trade(
        self,
        trade_id: str,
        symbol: str,
        timeframe: str,
        market_mode: str,
        scenario: str,
        probability: float,
        alignment_state: str,
        htf_support: Optional[float],
        htf_resistance: Optional[float],
        htf_direction: str,
        entry_price: float,
        entry_time: datetime,
        direction: str
    ) -> int:
        """
        Create new trade record.
        
        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            timeframe: Chart timeframe
            market_mode: INTRADAY or SWING
            scenario: Active scenario (A/B/C)
            probability: Scenario probability
            alignment_state: Alignment state
            htf_support/resistance: HTF structural levels
            htf_direction: HTF trend direction
            entry_price: Entry price
            entry_time: Entry timestamp
            direction: Trade direction (LONG/SHORT)
        
        Returns:
            Database row ID
        """
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, timeframe, market_mode,
                scenario, probability, alignment_state,
                htf_support, htf_resistance, htf_direction,
                entry_price, entry_time, direction,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id, symbol, timeframe, market_mode,
            scenario, probability, alignment_state,
            htf_support, htf_resistance, htf_direction,
            entry_price, entry_time.isoformat(), direction,
            timestamp, timestamp
        ))
        
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return row_id
    
    def update_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str,
        mae: float,
        mfe: float
    ) -> None:
        """
        Update trade with exit information.
        
        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            exit_time: Exit timestamp
            exit_reason: Reason for exit
            mae: Max Adverse Excursion
            mfe: Max Favorable Excursion
        """
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trades
            SET exit_price = ?, exit_time = ?, exit_reason = ?,
                mae = ?, mfe = ?, updated_at = ?
            WHERE trade_id = ?
        """, (
            exit_price, exit_time.isoformat(), exit_reason,
            mae, mfe, timestamp, trade_id
        ))
        
        conn.commit()
        conn.close()
    
    def update_resolution(
        self,
        trade_id: str,
        resolved_scenario: str,
        structure_respected: bool,
        resolution_confidence: str,
        resolution_notes: Optional[str] = None
    ) -> None:
        """
        Update trade with resolution information.
        
        Args:
            trade_id: Trade identifier
            resolved_scenario: Which scenario actually occurred
            structure_respected: Whether structure was respected
            resolution_confidence: Confidence level (HIGH/MEDIUM/LOW)
            resolution_notes: Optional resolution notes
        """
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trades
            SET resolved_scenario = ?, structure_respected = ?,
                resolution_confidence = ?, resolution_time = ?,
                resolution_notes = ?, updated_at = ?
            WHERE trade_id = ?
        """, (
            resolved_scenario, int(structure_respected),
            resolution_confidence, timestamp,
            resolution_notes, timestamp, trade_id
        ))
        
        conn.commit()
        conn.close()
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_trades(self) -> List[Dict[str, Any]]:
        """Get all trades."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_trades_by_scenario(self, scenario: str) -> List[Dict[str, Any]]:
        """Get trades by scenario."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM trades WHERE scenario = ? ORDER BY entry_time DESC",
            (scenario,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_resolved_trades(self) -> List[Dict[str, Any]]:
        """Get all resolved trades."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trades 
            WHERE resolved_scenario IS NOT NULL
            ORDER BY resolution_time DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_structure_respected_count(self) -> Dict[str, int]:
        """Get count of trades by structure_respected."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT structure_respected, COUNT(*) as count
            FROM trades
            WHERE structure_respected IS NOT NULL
            GROUP BY structure_respected
        """)
        
        results = {
            "respected": 0,
            "violated": 0
        }
        
        for row in cursor.fetchall():
            if row[0] == 1:
                results["respected"] = row[1]
            elif row[0] == 0:
                results["violated"] = row[1]
        
        conn.close()
        return results
