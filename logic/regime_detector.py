"""
Market Regime Detector — Phase-B: Market Regime Memory

Classifies market regime from historical analysis data and provides
temporal context that single-snapshot analysis cannot deliver.

Problems solved:
  1. "Is this trend fresh or exhausted?" → trend_duration_days
  2. "How many times did price test this level?" → level_interaction_count
  3. "Is the market trending or ranging?" → regime classification
  4. "Did the regime just change?" → REGIME_CHANGE flag for verdicts
  5. "What happened last time we were in this regime?" → regime history

Architecture:
  MarketAnalysisStore  ──► RegimeDetector  ──► RegimeContext
  (historical snapshots)    (classification)    (injected into LLM prompt + verdict)

Regime Classifications:
  TRENDING_UP    — Consistent bullish trend across analyses, structure intact
  TRENDING_DOWN  — Consistent bearish trend, lower-lows structure
  RANGING        — Sideways, mixed signals, price oscillating between levels
  VOLATILE       — Rapid regime changes, conflicting signals, high uncertainty
  TRANSITIONING  — Recent shift from one regime to another (caution zone)

Safety:
  - Read-only, observation layer only
  - Never triggers trades
  - Flags regime changes for downstream verdict logic
"""
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"


@dataclass
class LevelInteraction:
    """Record of price interaction with a key level."""
    level: float
    level_type: str             # "support" or "resistance"
    first_seen: str             # ISO timestamp
    last_tested: str            # ISO timestamp
    test_count: int             # How many times price reached this level
    held: int                   # How many times the level held
    broken: int                 # How many times the level was broken
    significance: float         # 0.0-1.0 based on test_count and hold rate
    
    def hold_rate(self) -> float:
        total = self.held + self.broken
        return self.held / total if total > 0 else 0.0


@dataclass
class RegimeContext:
    """
    Complete regime context for injection into analysis pipeline.
    
    This replaces the empty `regime_flags_set = set()` in execution_engine.
    """
    # Current regime
    regime: MarketRegime = MarketRegime.UNKNOWN
    regime_confidence: float = 0.0      # 0.0-1.0
    
    # Trend duration
    trend_direction: str = "unknown"     # bullish / bearish / sideways
    trend_duration_days: int = 0         # How many days the current trend has persisted
    trend_consistency: float = 0.0       # 0.0-1.0 (% of analyses agreeing on trend)
    
    # Regime change detection
    regime_changed: bool = False         # True if regime shifted in last N analyses
    previous_regime: MarketRegime = MarketRegime.UNKNOWN
    days_since_regime_change: int = -1   # -1 if no change detected
    
    # Level interaction history
    key_levels: List[LevelInteraction] = field(default_factory=list)
    
    # Historical regime stats
    regime_history: List[Dict[str, Any]] = field(default_factory=list)  # Last N regime changes
    
    # Flags for downstream systems
    regime_flags: Set[str] = field(default_factory=set)
    
    def get_regime_flags(self) -> Set[str]:
        """Get regime flags for HumanSummaryEngine."""
        flags = set(self.regime_flags)
        if self.regime_changed:
            flags.add("REGIME_CHANGE")
        if self.regime == MarketRegime.VOLATILE:
            flags.add("HIGH_VOLATILITY")
        if self.trend_duration_days > 60:
            flags.add("EXTENDED_TREND")
        return flags
    
    def get_prompt_context(self) -> str:
        """Generate regime context string for LLM prompt injection."""
        lines = []
        lines.append("--- MARKET REGIME CONTEXT (Phase-B) ---")
        lines.append(f"Regime: {self.regime.value.upper()} (confidence: {self.regime_confidence:.0%})")
        
        if self.trend_direction != "unknown":
            lines.append(f"Trend: {self.trend_direction} for {self.trend_duration_days} days (consistency: {self.trend_consistency:.0%})")
        
        if self.regime_changed:
            lines.append(f"!! REGIME CHANGE DETECTED: {self.previous_regime.value} → {self.regime.value} ({self.days_since_regime_change} days ago)")
            lines.append("CAUTION: Recent regime change means prior patterns may not apply.")
        
        if self.trend_duration_days > 60:
            lines.append(f"WARNING: Trend extended ({self.trend_duration_days} days). Watch for exhaustion signals.")
        
        # Key levels with interaction history
        if self.key_levels:
            lines.append("")
            lines.append("KEY LEVEL HISTORY:")
            # Sort by significance
            sorted_levels = sorted(self.key_levels, key=lambda l: l.significance, reverse=True)
            for level in sorted_levels[:6]:  # Top 6 most significant
                hold_pct = f"{level.hold_rate()*100:.0f}%"
                lines.append(
                    f"  {level.level_type.capitalize()} @ {level.level:.2f}: "
                    f"tested {level.test_count}x, held {hold_pct} "
                    f"(sig: {level.significance:.2f})"
                )
        
        # Regime history
        if self.regime_history:
            lines.append("")
            lines.append("REGIME HISTORY (recent):")
            for entry in self.regime_history[-3:]:
                lines.append(f"  {entry.get('date', '?')}: {entry.get('regime', '?')} ({entry.get('duration_days', '?')} days)")
        
        lines.append("--- END REGIME CONTEXT ---")
        return "\n".join(lines)


class RegimeMemoryStore:
    """
    SQLite store for regime classification history and level interactions.
    
    Separate from market_analyses.db to keep concerns clean.
    """
    
    def __init__(self, db_path: str = "db/regime_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"RegimeMemoryStore initialized at {db_path}")
    
    def _init_db(self):
        """Create schema."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Regime history per symbol
        c.execute("""
            CREATE TABLE IF NOT EXISTS regime_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                regime TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_days INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                trend_direction TEXT,
                trigger_reason TEXT,
                UNIQUE(symbol, started_at)
            )
        """)
        
        # Level interaction tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS level_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                level REAL NOT NULL,
                level_type TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_tested TEXT NOT NULL,
                test_count INTEGER DEFAULT 1,
                held_count INTEGER DEFAULT 0,
                broken_count INTEGER DEFAULT 0,
                timeframe TEXT DEFAULT '1D',
                UNIQUE(symbol, level_type, level, timeframe)
            )
        """)
        
        # Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_regime_symbol ON regime_history(symbol, started_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_levels_symbol ON level_interactions(symbol, level_type)")
        
        conn.commit()
        conn.close()
    
    def store_regime(
        self,
        symbol: str,
        regime: MarketRegime,
        confidence: float,
        trend_direction: str = "unknown",
        trigger_reason: str = ""
    ) -> int:
        """Store a new regime classification. Closes the previous regime if any."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            # Close previous open regime
            c.execute("""
                SELECT id, started_at FROM regime_history
                WHERE symbol = ? AND ended_at IS NULL
                ORDER BY started_at DESC LIMIT 1
            """, (symbol,))
            prev = c.fetchone()
            
            if prev:
                prev_start = datetime.fromisoformat(prev[1])
                duration = (datetime.now() - prev_start).days
                c.execute("""
                    UPDATE regime_history SET ended_at = ?, duration_days = ?
                    WHERE id = ?
                """, (now, duration, prev[0]))
            
            # Insert new regime
            c.execute("""
                INSERT OR REPLACE INTO regime_history
                (symbol, regime, started_at, confidence, trend_direction, trigger_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, regime.value, now, confidence, trend_direction, trigger_reason))
            
            rid = c.lastrowid
            conn.commit()
            logger.info(f"Phase-B: Stored regime {regime.value} for {symbol} (conf={confidence:.2f})")
            return rid
            
        except Exception as e:
            logger.error(f"Phase-B: Failed to store regime: {e}")
            return -1
        finally:
            conn.close()
    
    def get_current_regime(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the current (open) regime for a symbol."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT regime, started_at, confidence, trend_direction, trigger_reason
            FROM regime_history
            WHERE symbol = ? AND ended_at IS NULL
            ORDER BY started_at DESC LIMIT 1
        """, (symbol,))
        row = c.fetchone()
        conn.close()
        
        if row:
            started = datetime.fromisoformat(row[1])
            duration = (datetime.now() - started).days
            return {
                "regime": row[0],
                "started_at": row[1],
                "duration_days": duration,
                "confidence": row[2],
                "trend_direction": row[3],
                "trigger_reason": row[4]
            }
        return None
    
    def get_regime_history(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get regime change history for a symbol."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            SELECT regime, started_at, ended_at, duration_days, confidence, trend_direction
            FROM regime_history
            WHERE symbol = ?
            ORDER BY started_at DESC
            LIMIT ?
        """, (symbol, limit))
        
        rows = c.fetchall()
        conn.close()
        
        return [
            {
                "regime": r[0], "date": r[1][:10],
                "ended": r[2][:10] if r[2] else "active",
                "duration_days": r[3] or 0,
                "confidence": r[4], "trend": r[5]
            }
            for r in rows
        ]
    
    def upsert_level_interaction(
        self,
        symbol: str,
        level: float,
        level_type: str,
        held: bool,
        timeframe: str = "1D"
    ):
        """Record a price interaction with a key level."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        # Round level to 2 decimal places for matching
        level = round(level, 2)
        
        # Check if level exists (within 0.5% tolerance)
        c.execute("""
            SELECT id, level, test_count, held_count, broken_count
            FROM level_interactions
            WHERE symbol = ? AND level_type = ? AND timeframe = ?
            AND ABS(level - ?) / level < 0.005
            ORDER BY test_count DESC LIMIT 1
        """, (symbol, level_type, timeframe, level))
        
        existing = c.fetchone()
        
        if existing:
            new_test = existing[2] + 1
            new_held = existing[3] + (1 if held else 0)
            new_broken = existing[4] + (0 if held else 1)
            c.execute("""
                UPDATE level_interactions
                SET test_count = ?, held_count = ?, broken_count = ?,
                    last_tested = ?
                WHERE id = ?
            """, (new_test, new_held, new_broken, now, existing[0]))
        else:
            c.execute("""
                INSERT INTO level_interactions
                (symbol, level, level_type, first_seen, last_tested,
                 test_count, held_count, broken_count, timeframe)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (symbol, level, level_type, now, now,
                  1 if held else 0, 0 if held else 1, timeframe))
        
        conn.commit()
        conn.close()
    
    def get_level_interactions(
        self,
        symbol: str,
        level_type: Optional[str] = None,
        min_tests: int = 1
    ) -> List[LevelInteraction]:
        """Get level interaction history for a symbol."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query = """
            SELECT level, level_type, first_seen, last_tested,
                   test_count, held_count, broken_count
            FROM level_interactions
            WHERE symbol = ? AND test_count >= ?
        """
        params = [symbol, min_tests]
        
        if level_type:
            query += " AND level_type = ?"
            params.append(level_type)
        
        query += " ORDER BY test_count DESC"
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        interactions = []
        for r in rows:
            total_tests = r[4]
            hold_rate = r[5] / total_tests if total_tests > 0 else 0
            # Significance = test_count weight + hold_rate weight
            significance = min(1.0, (total_tests / 5) * 0.5 + hold_rate * 0.5)
            
            interactions.append(LevelInteraction(
                level=r[0], level_type=r[1],
                first_seen=r[2], last_tested=r[3],
                test_count=r[4], held=r[5], broken=r[6],
                significance=significance
            ))
        
        return interactions


class RegimeDetector:
    """
    Detects market regime from historical analysis data.
    
    Uses the last N analyses for a symbol to classify the current regime
    and detect regime transitions.
    
    Usage:
        detector = RegimeDetector(analysis_store, regime_store)
        context = detector.detect(symbol)
        # context.regime → MarketRegime
        # context.get_regime_flags() → set for HumanSummaryEngine
        # context.get_prompt_context() → string for LLM prompt
    """
    
    # Minimum analyses needed for regime detection
    MIN_ANALYSES_FOR_DETECTION = 3
    
    # Lookback window for trend consistency
    LOOKBACK_DAYS = 90
    
    # Regime change detection: if trend flipped in last N analyses
    REGIME_CHANGE_WINDOW = 5
    
    def __init__(
        self,
        analysis_store,          # MarketAnalysisStore
        regime_store: RegimeMemoryStore
    ):
        self.analysis_store = analysis_store
        self.regime_store = regime_store
        logger.info("Phase-B: RegimeDetector initialized")
    
    def detect(self, symbol: str, timeframe: str = "1D") -> RegimeContext:
        """
        Detect current market regime for a symbol.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe to analyze regime on
            
        Returns:
            RegimeContext with full regime classification and history
        """
        context = RegimeContext()
        
        try:
            # Step 1: Fetch historical analyses
            analyses = self._get_historical_analyses(symbol, timeframe)
            
            if len(analyses) < self.MIN_ANALYSES_FOR_DETECTION:
                logger.info(f"Phase-B: Not enough history for {symbol} ({len(analyses)} analyses, need {self.MIN_ANALYSES_FOR_DETECTION})")
                context.regime = MarketRegime.UNKNOWN
                return context
            
            # Step 2: Classify regime from trend history
            context.regime, context.regime_confidence = self._classify_regime(analyses)
            
            # Step 3: Calculate trend duration and consistency
            context.trend_direction, context.trend_duration_days, context.trend_consistency = \
                self._calculate_trend_duration(analyses)
            
            # Step 4: Detect regime change
            stored_regime = self.regime_store.get_current_regime(symbol)
            if stored_regime:
                prev_regime_str = stored_regime["regime"]
                try:
                    prev_regime = MarketRegime(prev_regime_str)
                except ValueError:
                    prev_regime = MarketRegime.UNKNOWN
                
                if prev_regime != context.regime and context.regime != MarketRegime.UNKNOWN:
                    context.regime_changed = True
                    context.previous_regime = prev_regime
                    context.days_since_regime_change = 0
                    
                    # Store the new regime
                    self.regime_store.store_regime(
                        symbol=symbol,
                        regime=context.regime,
                        confidence=context.regime_confidence,
                        trend_direction=context.trend_direction,
                        trigger_reason=f"Shift from {prev_regime.value} to {context.regime.value}"
                    )
                else:
                    context.days_since_regime_change = stored_regime.get("duration_days", 0)
            else:
                # First regime detection for this symbol
                if context.regime != MarketRegime.UNKNOWN:
                    self.regime_store.store_regime(
                        symbol=symbol,
                        regime=context.regime,
                        confidence=context.regime_confidence,
                        trend_direction=context.trend_direction,
                        trigger_reason="Initial regime classification"
                    )
            
            # Step 5: Track level interactions from analyses
            self._track_level_interactions(symbol, analyses)
            
            # Step 6: Load level history
            context.key_levels = self.regime_store.get_level_interactions(
                symbol, min_tests=1
            )
            
            # Step 7: Load regime history
            context.regime_history = self.regime_store.get_regime_history(symbol, limit=5)
            
            logger.info(
                f"Phase-B: {symbol} regime={context.regime.value}, "
                f"trend={context.trend_direction} ({context.trend_duration_days}d), "
                f"changed={context.regime_changed}, "
                f"levels={len(context.key_levels)}, "
                f"flags={context.get_regime_flags()}"
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Phase-B: Regime detection failed for {symbol}: {e}", exc_info=True)
            return context
    
    def _get_historical_analyses(
        self,
        symbol: str,
        timeframe: str
    ) -> List[Dict[str, Any]]:
        """Fetch historical analyses from the store, sorted oldest-first."""
        try:
            # Use the store's method to get analyses within the lookback window
            conn = sqlite3.connect(self.analysis_store.db_path)
            c = conn.cursor()
            
            cutoff = (datetime.now() - timedelta(days=self.LOOKBACK_DAYS)).isoformat()
            
            # Normalize symbol for matching
            symbol_upper = symbol.upper()
            if not symbol_upper.startswith(("NSE:", "BSE:")):
                patterns = [f"NSE:{symbol_upper}", symbol_upper]
            else:
                patterns = [symbol_upper]
            
            placeholders = ",".join(["?"] * len(patterns))
            
            c.execute(f"""
                SELECT timestamp, trend, support_levels, resistance_levels,
                       momentum, price, full_analysis
                FROM analyses
                WHERE symbol IN ({placeholders})
                AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (*patterns, cutoff))
            
            rows = c.fetchall()
            conn.close()
            
            analyses = []
            for r in rows:
                analysis = {
                    "timestamp": r[0],
                    "trend": r[1],
                    "support_levels": json.loads(r[2]) if r[2] else [],
                    "resistance_levels": json.loads(r[3]) if r[3] else [],
                    "momentum": r[4],
                    "price": r[5]
                }
                # Merge full_analysis for additional fields
                if r[6]:
                    try:
                        full = json.loads(r[6])
                        analysis["momentum_condition"] = full.get("momentum_condition", "")
                        analysis["volume_trend"] = full.get("volume_trend", "")
                        analysis["structure"] = full.get("structure", "")
                    except json.JSONDecodeError:
                        pass
                analyses.append(analysis)
            
            return analyses
            
        except Exception as e:
            logger.error(f"Phase-B: Failed to fetch history for {symbol}: {e}")
            return []
    
    def _classify_regime(
        self,
        analyses: List[Dict[str, Any]]
    ) -> Tuple[MarketRegime, float]:
        """
        Classify regime from trend history.
        
        Uses voting: count bullish/bearish/sideways across analyses.
        """
        if not analyses:
            return MarketRegime.UNKNOWN, 0.0
        
        # Count trend votes
        bull_count = 0
        bear_count = 0
        side_count = 0
        
        for a in analyses:
            trend = (a.get("trend") or "").lower()
            if trend == "bullish":
                bull_count += 1
            elif trend == "bearish":
                bear_count += 1
            elif trend == "sideways":
                side_count += 1
        
        total = len(analyses)
        bull_pct = bull_count / total
        bear_pct = bear_count / total
        side_pct = side_count / total
        
        # Check for recent flip (regime change detection)
        recent = analyses[-min(self.REGIME_CHANGE_WINDOW, len(analyses)):]
        recent_trends = [(a.get("trend") or "").lower() for a in recent]
        
        # If recent trends include both bullish and bearish → volatile/transitioning
        has_bull_recent = "bullish" in recent_trends
        has_bear_recent = "bearish" in recent_trends
        
        if has_bull_recent and has_bear_recent:
            # Check if this is a new shift vs. established volatility
            # If majority of history was one direction and recent flipped → TRANSITIONING
            if bull_pct > 0.6 and "bearish" in recent_trends[-2:]:
                return MarketRegime.TRANSITIONING, 0.65
            elif bear_pct > 0.6 and "bullish" in recent_trends[-2:]:
                return MarketRegime.TRANSITIONING, 0.65
            else:
                return MarketRegime.VOLATILE, 0.55
        
        # Strong consensus
        if bull_pct >= 0.7:
            return MarketRegime.TRENDING_UP, min(0.95, 0.5 + bull_pct * 0.5)
        elif bear_pct >= 0.7:
            return MarketRegime.TRENDING_DOWN, min(0.95, 0.5 + bear_pct * 0.5)
        elif side_pct >= 0.5:
            return MarketRegime.RANGING, min(0.85, 0.4 + side_pct * 0.5)
        
        # Moderate consensus
        if bull_pct >= 0.5:
            return MarketRegime.TRENDING_UP, 0.55 + bull_pct * 0.2
        elif bear_pct >= 0.5:
            return MarketRegime.TRENDING_DOWN, 0.55 + bear_pct * 0.2
        
        # No clear regime
        return MarketRegime.RANGING, 0.40
    
    def _calculate_trend_duration(
        self,
        analyses: List[Dict[str, Any]]
    ) -> Tuple[str, int, float]:
        """
        Calculate how long the current trend has been in place.
        
        Returns:
            (trend_direction, duration_days, consistency)
        """
        if not analyses:
            return "unknown", 0, 0.0
        
        # Current trend = most recent analysis
        current_trend = (analyses[-1].get("trend") or "unknown").lower()
        
        if current_trend == "unknown":
            return "unknown", 0, 0.0
        
        # Walk backwards to find when trend started
        streak_start_idx = len(analyses) - 1
        for i in range(len(analyses) - 2, -1, -1):
            trend = (analyses[i].get("trend") or "").lower()
            if trend == current_trend:
                streak_start_idx = i
            else:
                break
        
        # Duration in days
        streak_analyses = analyses[streak_start_idx:]
        if len(streak_analyses) >= 2:
            try:
                start_time = datetime.fromisoformat(streak_analyses[0]["timestamp"])
                end_time = datetime.fromisoformat(streak_analyses[-1]["timestamp"])
                duration_days = max(1, (end_time - start_time).days)
            except (ValueError, KeyError):
                duration_days = len(streak_analyses)
        else:
            duration_days = 1
        
        # Consistency = what % of ALL analyses agree with current trend
        total = len(analyses)
        agreeing = sum(1 for a in analyses if (a.get("trend") or "").lower() == current_trend)
        consistency = agreeing / total if total > 0 else 0.0
        
        return current_trend, duration_days, consistency
    
    def _track_level_interactions(
        self,
        symbol: str,
        analyses: List[Dict[str, Any]]
    ):
        """
        Track support/resistance level interactions across historical analyses.
        
        Compares price vs S/R levels to determine if levels held or broke.
        """
        for analysis in analyses:
            price = analysis.get("price")
            if not price:
                continue
            
            try:
                price_val = float(str(price).replace(",", ""))
            except (ValueError, TypeError):
                continue
            
            # Track support levels
            for level in analysis.get("support_levels", []):
                try:
                    level_val = float(str(level).replace(",", ""))
                    if level_val <= 0:
                        continue
                    
                    # Price near support (within 2%) = test
                    distance_pct = abs(price_val - level_val) / level_val * 100
                    if distance_pct < 2:
                        # At support: did it hold? (price still above → held)
                        held = price_val >= level_val
                        self.regime_store.upsert_level_interaction(
                            symbol=symbol,
                            level=level_val,
                            level_type="support",
                            held=held
                        )
                except (ValueError, TypeError):
                    continue
            
            # Track resistance levels
            for level in analysis.get("resistance_levels", []):
                try:
                    level_val = float(str(level).replace(",", ""))
                    if level_val <= 0:
                        continue
                    
                    # Price near resistance (within 2%) = test
                    distance_pct = abs(price_val - level_val) / level_val * 100
                    if distance_pct < 2:
                        # At resistance: did it hold? (price still below → held)
                        held = price_val <= level_val
                        self.regime_store.upsert_level_interaction(
                            symbol=symbol,
                            level=level_val,
                            level_type="resistance",
                            held=held
                        )
                except (ValueError, TypeError):
                    continue
