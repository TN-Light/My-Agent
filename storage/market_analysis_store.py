"""
Market Analysis Store - Phase-2C
Persistent storage for market analyses using SQLite.

Stores structured analysis data for retrieval, comparison, and trend tracking.
"""
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class MarketAnalysisStore:
    """
    SQLite-based storage for market analyses.
    
    Schema:
    - id: INTEGER PRIMARY KEY
    - symbol: TEXT (e.g., "NSE:RELIANCE")
    - timeframe: TEXT (e.g., "1D", "1H")
    - timestamp: TEXT (ISO 8601)
    - trend: TEXT (bullish/bearish/sideways)
    - support_levels: TEXT (JSON array)
    - resistance_levels: TEXT (JSON array)
    - momentum: TEXT
    - bias: TEXT
    - price: REAL (current price at analysis time)
    - full_analysis: TEXT (complete JSON)
    """
    
    def __init__(self, db_path: str = "db/market_analyses.db"):
        """
        Initialize market analysis store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"MarketAnalysisStore initialized at {db_path}")
    
    def _init_db(self):
        """Create database schema if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                trend TEXT,
                support_levels TEXT,
                resistance_levels TEXT,
                momentum TEXT,
                bias TEXT,
                price REAL,
                full_analysis TEXT,
                UNIQUE(symbol, timeframe, timestamp)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
            ON analyses(symbol, timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON analyses(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("Market analysis database schema initialized")
    
    def store_analysis(self, analysis: Dict[str, Any]) -> int:
        """
        Store a market analysis.
        
        Args:
            analysis: Analysis dictionary from TechnicalAnalyzer
            
        Returns:
            Analysis ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract fields
        symbol = analysis.get("symbol", "Unknown")
        timeframe = analysis.get("timeframe", "Unknown")
        timestamp = analysis.get("timestamp", datetime.now().isoformat())
        trend = analysis.get("trend", "Unknown")
        support = json.dumps(analysis.get("support", []))
        resistance = json.dumps(analysis.get("resistance", []))
        momentum = analysis.get("momentum", "Unknown")
        bias = analysis.get("bias", "")
        price = analysis.get("price")
        full_analysis = json.dumps(analysis)
        
        try:
            cursor.execute("""
                INSERT INTO analyses (
                    symbol, timeframe, timestamp, trend, 
                    support_levels, resistance_levels, 
                    momentum, bias, price, full_analysis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timeframe, timestamp, trend,
                support, resistance, momentum, bias,
                price, full_analysis
            ))
            
            analysis_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Stored analysis for {symbol} ({timeframe}) - ID: {analysis_id}")
            return analysis_id
            
        except sqlite3.IntegrityError:
            # Duplicate entry (same symbol, timeframe, timestamp)
            logger.warning(f"Duplicate analysis for {symbol} ({timeframe}) at {timestamp}")
            return -1
        finally:
            conn.close()
    
    def get_latest_analysis(
        self, 
        symbol: str, 
        timeframe: Optional[str] = None,
        max_age_hours: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent analysis for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "NSE:RELIANCE" or "RELIANCE")
            timeframe: Optional timeframe filter
            max_age_hours: Maximum age in hours (e.g., 24 for same-day, 1 for recent)
            
        Returns:
            Analysis dictionary or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Normalize symbol (add NSE: if missing)
        if not symbol.startswith(("NSE:", "BSE:", "NASDAQ:", "NYSE:")):
            symbol_patterns = [f"NSE:{symbol.upper()}", symbol.upper()]
        else:
            symbol_patterns = [symbol]
        
        try:
            # Calculate cutoff timestamp if max_age_hours specified
            time_filter = ""
            params = list(symbol_patterns)
            
            if max_age_hours is not None:
                from datetime import datetime, timedelta
                cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
                cutoff_iso = cutoff_time.isoformat()
                time_filter = "AND timestamp >= ?"
                params.append(cutoff_iso)
            
            if timeframe:
                query = f"""
                    SELECT full_analysis, timestamp FROM analyses 
                    WHERE symbol IN ({','.join(['?'] * len(symbol_patterns))})
                    AND timeframe = ?
                    {time_filter}
                    ORDER BY timestamp DESC LIMIT 1
                """
                params.append(timeframe)
                cursor.execute(query, params)
            else:
                query = f"""
                    SELECT full_analysis, timestamp FROM analyses 
                    WHERE symbol IN ({','.join(['?'] * len(symbol_patterns))})
                    {time_filter}
                    ORDER BY timestamp DESC LIMIT 1
                """
                cursor.execute(query, params)
            
            row = cursor.fetchone()
            if row:
                analysis = json.loads(row[0])
                # Log data age for transparency
                if max_age_hours:
                    logger.debug(f"Retrieved analysis from {row[1]} (max_age: {max_age_hours}h)")
                return analysis
            return None
            
        finally:
            conn.close()
    
    def get_analyses_by_symbol(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent analyses for a symbol (for trend tracking).
        
        Args:
            symbol: Stock symbol
            limit: Maximum number of analyses to return
            
        Returns:
            List of analysis dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Normalize symbol
        if not symbol.startswith(("NSE:", "BSE:", "NASDAQ:", "NYSE:")):
            symbol_patterns = [f"NSE:{symbol.upper()}", symbol.upper()]
        else:
            symbol_patterns = [symbol]
        
        try:
            query = """
                SELECT full_analysis FROM analyses 
                WHERE symbol IN ({})
                ORDER BY timestamp DESC LIMIT ?
            """.format(','.join(['?'] * len(symbol_patterns)))
            cursor.execute(query, (*symbol_patterns, limit))
            
            rows = cursor.fetchall()
            return [json.loads(row[0]) for row in rows]
            
        finally:
            conn.close()
    
    def get_recent_analyses(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all recent analyses within time window.
        
        Args:
            hours: Time window in hours
            limit: Maximum results
            
        Returns:
            List of analyses
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Calculate cutoff timestamp
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute("""
                SELECT full_analysis FROM analyses 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC LIMIT ?
            """, (cutoff, limit))
            
            rows = cursor.fetchall()
            return [json.loads(row[0]) for row in rows]
            
        finally:
            conn.close()
    
    def get_latest_by_symbols(
        self,
        symbols: List[str],
        timeframe: Optional[str] = None
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get latest analysis for multiple symbols (for comparison).
        
        Args:
            symbols: List of symbols
            timeframe: Optional timeframe filter
            
        Returns:
            Dictionary mapping symbol to analysis (or None)
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_latest_analysis(symbol, timeframe)
        return result
    
    def has_trend_changed(
        self,
        symbol: str,
        current_trend: str,
        lookback: int = 5
    ) -> Dict[str, Any]:
        """
        Check if trend has changed from recent analyses.
        
        Args:
            symbol: Stock symbol
            current_trend: Current trend assessment
            lookback: Number of past analyses to check
            
        Returns:
            Dict with changed (bool), previous_trend, and change_description
        """
        analyses = self.get_analyses_by_symbol(symbol, limit=lookback + 1)
        
        if len(analyses) < 2:
            return {
                "changed": False,
                "previous_trend": None,
                "change_description": "Insufficient data to determine trend change"
            }
        
        # Get most recent previous trend (skip first which is current)
        previous_trends = [a.get("trend", "Unknown") for a in analyses[1:]]
        most_common_previous = max(set(previous_trends), key=previous_trends.count)
        
        changed = current_trend.lower() != most_common_previous.lower()
        
        change_description = ""
        if changed:
            change_description = f"Trend changed from {most_common_previous} to {current_trend}"
        else:
            change_description = f"Trend remains {current_trend}"
        
        return {
            "changed": changed,
            "previous_trend": most_common_previous,
            "change_description": change_description,
            "history": previous_trends
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM analyses")
            total_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT symbol) FROM analyses")
            unique_symbols = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM analyses")
            min_ts, max_ts = cursor.fetchone()
            
            return {
                "total_analyses": total_count,
                "unique_symbols": unique_symbols,
                "oldest_analysis": min_ts,
                "latest_analysis": max_ts
            }
            
        finally:
            conn.close()
