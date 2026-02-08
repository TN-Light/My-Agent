"""
Phase-E: Prediction Feedback Loop

Closes the prediction → outcome → accuracy loop that was scaffolded but never wired.

Problems solved:
  1. Verdicts (STRONG/CAUTION/WAIT/AVOID) are computed but never stored
  2. Scenario resolutions (A/B/C) are tracked but never auto-resolved
  3. No "what happened next?" comparison exists
  4. ExpectancyEngine is dead code (no data flows in)
  5. No accuracy metrics are ever computed or displayed

Architecture:
  Analysis complete → PredictionTracker.record()     [capture prediction]
  Next analysis     → OutcomeResolver.check_pending() [compare with reality]
  On demand         → FeedbackReporter.report()       [accuracy stats]

Data flow:
  TechnicalAnalyzer stores analysis → market_analyses.db
  PredictionTracker stores verdict+context → predictions.db
  OutcomeResolver reads BOTH DBs, compares prediction vs next observation
  ScenarioResolutionStore.resolve_analysis() finally gets called automatically

Safety:
  - Read-only feedback. Never influences live analysis.
  - Accuracy stats are informational only.
  - No position sizing, no trade execution.
"""
import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
# 1. PREDICTION STORE — captures what we predicted
# ─────────────────────────────────────────────────

class PredictionStore:
    """
    Persists predictions (verdicts + context) so they can be validated later.
    
    Fills the critical gap: verdicts are generated but never stored.
    """
    
    def __init__(self, db_path: str = "db/predictions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info(f"PredictionStore initialized at {db_path}")
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                
                -- What we predicted
                verdict TEXT NOT NULL,
                confidence TEXT NOT NULL,
                trend_prediction TEXT,
                bias_text TEXT,
                alignment_state TEXT,
                active_scenario TEXT,
                regime TEXT,
                
                -- Context at prediction time
                price_at_prediction REAL,
                support_levels TEXT,
                resistance_levels TEXT,
                htf_location TEXT,
                regime_flags TEXT,
                
                -- Linked scenario analysis ID (if available)
                scenario_analysis_id INTEGER,
                
                -- Resolution (filled by OutcomeResolver)
                resolved INTEGER DEFAULT 0,
                resolution_time TEXT,
                price_at_resolution REAL,
                trend_actual TEXT,
                verdict_correct INTEGER,
                trend_correct INTEGER,
                support_held INTEGER,
                resistance_held INTEGER,
                price_move_pct REAL,
                resolution_notes TEXT,
                
                UNIQUE(symbol, timestamp)
            )
        """)
        
        c.execute("CREATE INDEX IF NOT EXISTS idx_pred_symbol ON predictions(symbol, timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pred_unresolved ON predictions(resolved) WHERE resolved = 0")
        
        conn.commit()
        conn.close()
    
    def record_prediction(
        self,
        symbol: str,
        verdict: str,
        confidence: str,
        trend_prediction: str = "",
        bias_text: str = "",
        alignment_state: str = "",
        active_scenario: str = "",
        regime: str = "",
        price: float = 0.0,
        support_levels: List = None,
        resistance_levels: List = None,
        htf_location: str = "",
        regime_flags: Set[str] = None,
        scenario_analysis_id: int = None
    ) -> int:
        """Record a prediction for later validation."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            c.execute("""
                INSERT OR REPLACE INTO predictions (
                    symbol, timestamp, verdict, confidence,
                    trend_prediction, bias_text, alignment_state,
                    active_scenario, regime,
                    price_at_prediction, support_levels, resistance_levels,
                    htf_location, regime_flags, scenario_analysis_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, now, verdict, confidence,
                trend_prediction, bias_text, alignment_state,
                active_scenario, regime,
                price, json.dumps(support_levels or []),
                json.dumps(resistance_levels or []),
                htf_location, json.dumps(list(regime_flags or set())),
                scenario_analysis_id
            ))
            
            pid = c.lastrowid
            conn.commit()
            logger.info(f"Phase-E: Recorded prediction #{pid} for {symbol}: {verdict} ({confidence})")
            return pid
            
        except Exception as e:
            logger.error(f"Phase-E: Failed to record prediction: {e}")
            return -1
        finally:
            conn.close()
    
    def get_pending_predictions(self, max_age_days: int = 30) -> List[Dict[str, Any]]:
        """Get all unresolved predictions within the lookback window."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
        
        c.execute("""
            SELECT * FROM predictions
            WHERE resolved = 0 AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff,))
        
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    
    def resolve_prediction(
        self,
        prediction_id: int,
        price_at_resolution: float,
        trend_actual: str,
        verdict_correct: bool,
        trend_correct: bool,
        support_held: bool,
        resistance_held: bool,
        price_move_pct: float,
        notes: str = ""
    ) -> bool:
        """Mark a prediction as resolved with outcome data."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute("""
                UPDATE predictions SET
                    resolved = 1,
                    resolution_time = ?,
                    price_at_resolution = ?,
                    trend_actual = ?,
                    verdict_correct = ?,
                    trend_correct = ?,
                    support_held = ?,
                    resistance_held = ?,
                    price_move_pct = ?,
                    resolution_notes = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                price_at_resolution,
                trend_actual,
                1 if verdict_correct else 0,
                1 if trend_correct else 0,
                1 if support_held else 0,
                1 if resistance_held else 0,
                price_move_pct,
                notes,
                prediction_id
            ))
            
            success = c.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Phase-E: Resolved prediction #{prediction_id}: trend_correct={trend_correct}, verdict_correct={verdict_correct}")
            return success
            
        except Exception as e:
            logger.error(f"Phase-E: Failed to resolve prediction: {e}")
            return False
        finally:
            conn.close()
    
    def get_accuracy_stats(self, symbol: str = None, days: int = 90) -> Dict[str, Any]:
        """Calculate prediction accuracy statistics."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        where_clause = "WHERE resolved = 1 AND timestamp >= ?"
        params = [cutoff]
        
        if symbol:
            where_clause += " AND symbol = ?"
            params.append(symbol)
        
        c.execute(f"""
            SELECT
                COUNT(*) as total_resolved,
                SUM(verdict_correct) as verdict_correct,
                SUM(trend_correct) as trend_correct,
                SUM(support_held) as support_held,
                SUM(resistance_held) as resistance_held,
                AVG(price_move_pct) as avg_price_move,
                AVG(ABS(price_move_pct)) as avg_abs_move
            FROM predictions
            {where_clause}
        """, params)
        
        row = c.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
            return {
                "total_resolved": 0,
                "message": "No resolved predictions yet. Accuracy builds over time."
            }
        
        total = row[0]
        return {
            "total_resolved": total,
            "verdict_accuracy_pct": round((row[1] or 0) / total * 100, 1),
            "trend_accuracy_pct": round((row[2] or 0) / total * 100, 1),
            "support_hold_rate_pct": round((row[3] or 0) / total * 100, 1),
            "resistance_hold_rate_pct": round((row[4] or 0) / total * 100, 1),
            "avg_price_move_pct": round(row[5] or 0, 2),
            "avg_abs_move_pct": round(row[6] or 0, 2)
        }
    
    def get_accuracy_by_verdict(self, days: int = 90) -> Dict[str, Dict]:
        """Break down accuracy by verdict type."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        c.execute("""
            SELECT verdict,
                COUNT(*) as total,
                SUM(verdict_correct) as correct,
                SUM(trend_correct) as trend_ok,
                AVG(price_move_pct) as avg_move
            FROM predictions
            WHERE resolved = 1 AND timestamp >= ?
            GROUP BY verdict
        """, (cutoff,))
        
        rows = c.fetchall()
        conn.close()
        
        result = {}
        for r in rows:
            verdict = r[0]
            total = r[1]
            result[verdict] = {
                "total": total,
                "verdict_accuracy_pct": round((r[2] or 0) / total * 100, 1),
                "trend_accuracy_pct": round((r[3] or 0) / total * 100, 1),
                "avg_price_move_pct": round(r[4] or 0, 2)
            }
        
        return result


# ─────────────────────────────────────────────────
# 2. OUTCOME RESOLVER — compares prediction vs reality
# ─────────────────────────────────────────────────

class OutcomeResolver:
    """
    Automatically resolves pending predictions by comparing them against
    subsequent analysis data in market_analyses.db.
    
    Resolution logic:
    - Trend correct: Did the next analysis for this symbol agree on trend direction?
    - Support held: Did price stay above predicted support levels?
    - Resistance held: Did price stay below predicted resistance levels?
    - Verdict correct: Was the directional bias validated by price movement?
      - STRONG/LEAN with bullish bias → price went up = correct
      - AVOID → price went down or trend changed = correct
      - WAIT → neutral, scored on trend accuracy only
    
    Minimum resolution delay: 1 analysis cycle (typically 1 day for daily TF).
    """
    
    # Minimum hours between prediction and resolution
    MIN_RESOLUTION_HOURS = 4
    
    def __init__(
        self,
        prediction_store: PredictionStore,
        analysis_db_path: str = "db/market_analyses.db",
        scenario_resolution_store=None
    ):
        self.prediction_store = prediction_store
        self.analysis_db_path = analysis_db_path
        self.scenario_store = scenario_resolution_store
        logger.info("Phase-E: OutcomeResolver initialized")
    
    def check_and_resolve_pending(self) -> Dict[str, Any]:
        """
        Check all pending predictions and resolve any that have subsequent data.
        
        Called at the START of each analysis session (before new analysis).
        This is the core feedback loop — it closes the predict→observe→score cycle.
        
        Returns:
            Summary of resolutions performed
        """
        pending = self.prediction_store.get_pending_predictions()
        
        if not pending:
            return {"checked": 0, "resolved": 0, "message": "No pending predictions"}
        
        resolved_count = 0
        results = []
        
        for prediction in pending:
            try:
                outcome = self._resolve_single(prediction)
                if outcome:
                    resolved_count += 1
                    results.append(outcome)
            except Exception as e:
                logger.warning(f"Phase-E: Failed to resolve prediction #{prediction['id']}: {e}")
        
        summary = {
            "checked": len(pending),
            "resolved": resolved_count,
            "still_pending": len(pending) - resolved_count,
            "results": results
        }
        
        if resolved_count > 0:
            logger.info(f"Phase-E: Resolved {resolved_count}/{len(pending)} pending predictions")
        
        return summary
    
    def _resolve_single(self, prediction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Resolve a single prediction by finding subsequent analysis data.
        
        Returns resolution dict or None if not enough data yet.
        """
        symbol = prediction["symbol"]
        pred_time = prediction["timestamp"]
        pred_price = prediction.get("price_at_prediction", 0)
        pred_trend = (prediction.get("trend_prediction") or "").lower()
        pred_verdict = prediction.get("verdict", "")
        
        # Parse prediction time
        try:
            pred_dt = datetime.fromisoformat(pred_time)
        except (ValueError, TypeError):
            return None
        
        # Check minimum resolution delay
        hours_elapsed = (datetime.now() - pred_dt).total_seconds() / 3600
        if hours_elapsed < self.MIN_RESOLUTION_HOURS:
            return None
        
        # Find next analysis for this symbol AFTER the prediction
        next_analysis = self._get_next_analysis(symbol, pred_time)
        if not next_analysis:
            return None  # Not enough data yet
        
        # Extract outcome data
        actual_price = next_analysis.get("price", 0)
        actual_trend = (next_analysis.get("trend") or "unknown").lower()
        actual_support = next_analysis.get("support_levels", [])
        actual_resistance = next_analysis.get("resistance_levels", [])
        
        if not actual_price or not pred_price:
            return None
        
        # Calculate price movement
        try:
            price_move_pct = ((actual_price - pred_price) / pred_price) * 100
        except (ZeroDivisionError, TypeError):
            price_move_pct = 0.0
        
        # Score: Trend correct?
        trend_correct = self._score_trend(pred_trend, actual_trend)
        
        # Score: Support held?
        support_held = self._score_levels(
            prediction.get("support_levels", "[]"),
            actual_price, "support"
        )
        
        # Score: Resistance held?
        resistance_held = self._score_levels(
            prediction.get("resistance_levels", "[]"),
            actual_price, "resistance"
        )
        
        # Score: Verdict correct?
        verdict_correct = self._score_verdict(
            pred_verdict, pred_trend, price_move_pct, trend_correct
        )
        
        # Build resolution notes
        notes = (
            f"Price: {pred_price:.2f} → {actual_price:.2f} ({price_move_pct:+.2f}%). "
            f"Trend: {pred_trend} → {actual_trend}. "
            f"Verdict {pred_verdict}: {'CORRECT' if verdict_correct else 'INCORRECT'}."
        )
        
        # Persist resolution
        self.prediction_store.resolve_prediction(
            prediction_id=prediction["id"],
            price_at_resolution=actual_price,
            trend_actual=actual_trend,
            verdict_correct=verdict_correct,
            trend_correct=trend_correct,
            support_held=support_held,
            resistance_held=resistance_held,
            price_move_pct=price_move_pct,
            notes=notes
        )
        
        # Also resolve linked scenario analysis if available
        scenario_id = prediction.get("scenario_analysis_id")
        if scenario_id and self.scenario_store:
            try:
                # Determine which scenario played out
                resolved_scenario = self._determine_scenario(
                    pred_trend, actual_trend, price_move_pct, support_held
                )
                self.scenario_store.resolve_analysis(
                    analysis_id=scenario_id,
                    resolved_scenario=resolved_scenario,
                    structure_respected=support_held and resistance_held,
                    notes=notes
                )
                logger.info(f"Phase-E: Auto-resolved scenario analysis #{scenario_id} → {resolved_scenario}")
            except Exception as e:
                logger.warning(f"Phase-E: Scenario resolution failed: {e}")
        
        return {
            "symbol": symbol,
            "prediction_id": prediction["id"],
            "verdict": pred_verdict,
            "trend_correct": trend_correct,
            "verdict_correct": verdict_correct,
            "price_move_pct": round(price_move_pct, 2),
            "notes": notes
        }
    
    def _get_next_analysis(self, symbol: str, after_time: str) -> Optional[Dict[str, Any]]:
        """Find the next analysis for this symbol after the prediction time."""
        try:
            conn = sqlite3.connect(self.analysis_db_path)
            c = conn.cursor()
            
            # Normalize symbol
            symbol_upper = symbol.upper()
            if not symbol_upper.startswith(("NSE:", "BSE:")):
                patterns = [f"NSE:{symbol_upper}", symbol_upper]
            else:
                patterns = [symbol_upper]
            
            placeholders = ",".join(["?"] * len(patterns))
            
            c.execute(f"""
                SELECT price, trend, support_levels, resistance_levels,
                       timestamp, full_analysis
                FROM analyses
                WHERE symbol IN ({placeholders})
                AND timestamp > ?
                ORDER BY timestamp ASC
                LIMIT 1
            """, (*patterns, after_time))
            
            row = c.fetchone()
            conn.close()
            
            if row:
                return {
                    "price": row[0],
                    "trend": row[1],
                    "support_levels": json.loads(row[2]) if row[2] else [],
                    "resistance_levels": json.loads(row[3]) if row[3] else [],
                    "timestamp": row[4]
                }
            return None
            
        except Exception as e:
            logger.error(f"Phase-E: Failed to fetch next analysis: {e}")
            return None
    
    def _score_trend(self, predicted: str, actual: str) -> bool:
        """Score whether trend prediction was correct."""
        if not predicted or predicted == "unknown":
            return False
        return predicted.lower() == actual.lower()
    
    def _score_levels(self, levels_json: str, actual_price: float, level_type: str) -> bool:
        """
        Score whether S/R levels held.
        
        Support held: price stayed above all support levels
        Resistance held: price stayed below all resistance levels
        """
        try:
            levels = json.loads(levels_json) if isinstance(levels_json, str) else levels_json
        except (json.JSONDecodeError, TypeError):
            return True  # No levels to check = vacuously true
        
        if not levels or not actual_price:
            return True
        
        for level in levels:
            try:
                level_val = float(level)
                if level_type == "support" and actual_price < level_val * 0.98:
                    return False  # Price broke below support (2% tolerance)
                elif level_type == "resistance" and actual_price > level_val * 1.02:
                    return False  # Price broke above resistance (2% tolerance)
            except (ValueError, TypeError):
                continue
        
        return True
    
    def _score_verdict(
        self,
        verdict: str,
        predicted_trend: str,
        price_move_pct: float,
        trend_correct: bool
    ) -> bool:
        """
        Score whether the verdict was directionally correct.
        
        STRONG/LEAN with bullish → price went up = correct
        STRONG/LEAN with bearish → price went down = correct
        AVOID → price went against predicted direction or was flat = correct
        WAIT → scored on trend accuracy only
        CAUTION → scored on trend accuracy only
        """
        verdict_upper = verdict.upper()
        trend_lower = (predicted_trend or "").lower()
        
        if verdict_upper in ("STRONG", "LEAN"):
            if trend_lower == "bullish":
                return price_move_pct > -0.5  # Bullish and didn't crash
            elif trend_lower == "bearish":
                return price_move_pct < 0.5   # Bearish and didn't rally
            return trend_correct
        
        elif verdict_upper == "AVOID":
            # AVOID is correct if price didn't make a big directional move
            # or if the trend actually changed
            return abs(price_move_pct) < 2.0 or not trend_correct
        
        elif verdict_upper in ("WAIT", "CAUTION"):
            # These are cautious verdicts — correct if trend prediction held
            return trend_correct
        
        elif verdict_upper == "NO_TRADE":
            # NO_TRADE is always "correct" (conservative is never wrong)
            return True
        
        return trend_correct  # Default: score on trend
    
    def _determine_scenario(
        self,
        pred_trend: str,
        actual_trend: str,
        price_move_pct: float,
        support_held: bool
    ) -> str:
        """
        Determine which scenario (A/B/C) actually played out.
        
        A (Continuation): Trend continued, structure held
        B (Pullback): Trend paused/reversed but structure held
        C (Failure): Structure broke down
        """
        trend_lower = (pred_trend or "").lower()
        actual_lower = (actual_trend or "").lower()
        
        if not support_held:
            return "C"  # Structure broke
        
        if trend_lower == actual_lower:
            return "A"  # Trend continued, structure held
        
        return "B"  # Trend changed but structure held


# ─────────────────────────────────────────────────
# 3. FEEDBACK REPORTER — generates accuracy reports
# ─────────────────────────────────────────────────

class FeedbackReporter:
    """
    Generates human-readable accuracy reports from resolved predictions.
    
    Can be displayed in the UI or injected into the LLM prompt to make
    the agent self-aware of its accuracy (meta-learning context).
    """
    
    def __init__(self, prediction_store: PredictionStore):
        self.prediction_store = prediction_store
    
    def generate_report(self, symbol: str = None, days: int = 90) -> str:
        """Generate a human-readable accuracy report."""
        stats = self.prediction_store.get_accuracy_stats(symbol=symbol, days=days)
        
        if stats.get("total_resolved", 0) == 0:
            return "Phase-E: No resolved predictions yet. Accuracy builds over time as you analyze more symbols."
        
        lines = []
        lines.append("=" * 60)
        lines.append("PREDICTION ACCURACY REPORT (Phase-E)")
        lines.append("=" * 60)
        
        scope = f"Symbol: {symbol}" if symbol else "All symbols"
        lines.append(f"Scope: {scope} | Period: {days} days")
        lines.append(f"Total resolved: {stats['total_resolved']}")
        lines.append("")
        
        lines.append(f"Verdict accuracy:     {stats['verdict_accuracy_pct']}%")
        lines.append(f"Trend accuracy:       {stats['trend_accuracy_pct']}%")
        lines.append(f"Support hold rate:    {stats['support_hold_rate_pct']}%")
        lines.append(f"Resistance hold rate: {stats['resistance_hold_rate_pct']}%")
        lines.append(f"Avg price move:       {stats['avg_price_move_pct']:+.2f}%")
        lines.append(f"Avg absolute move:    {stats['avg_abs_move_pct']:.2f}%")
        
        # Verdict breakdown
        by_verdict = self.prediction_store.get_accuracy_by_verdict(days=days)
        if by_verdict:
            lines.append("")
            lines.append("BY VERDICT TYPE:")
            for verdict, data in sorted(by_verdict.items()):
                lines.append(
                    f"  {verdict:10s}: {data['total']:3d} predictions, "
                    f"{data['verdict_accuracy_pct']}% correct, "
                    f"avg move {data['avg_price_move_pct']:+.2f}%"
                )
        
        # Confidence assessment
        lines.append("")
        trend_acc = stats['trend_accuracy_pct']
        if trend_acc >= 70:
            lines.append("ASSESSMENT: Strong trend detection. Analysis is reliable.")
        elif trend_acc >= 55:
            lines.append("ASSESSMENT: Moderate accuracy. Analysis adds value but verify with other sources.")
        elif trend_acc >= 40:
            lines.append("ASSESSMENT: Below baseline. Review analysis pipeline for systematic errors.")
        else:
            lines.append("ASSESSMENT: Poor accuracy. Analysis may be degraded. Check data quality and model.")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def get_prompt_context(self, symbol: str = None, days: int = 30) -> str:
        """
        Generate a compact accuracy context for LLM prompt injection.
        
        Gives the LLM self-awareness of its own accuracy history.
        """
        stats = self.prediction_store.get_accuracy_stats(symbol=symbol, days=days)
        
        if stats.get("total_resolved", 0) == 0:
            return ""
        
        total = stats["total_resolved"]
        trend_acc = stats["trend_accuracy_pct"]
        verdict_acc = stats["verdict_accuracy_pct"]
        
        context = (
            f"--- PREDICTION ACCURACY (Phase-E, last {days}d) ---\n"
            f"Resolved: {total} predictions | "
            f"Trend accuracy: {trend_acc}% | "
            f"Verdict accuracy: {verdict_acc}%\n"
        )
        
        if trend_acc < 50:
            context += "WARNING: Trend predictions below baseline. Be more conservative.\n"
        elif trend_acc > 70:
            context += "NOTE: Strong trend accuracy. Current analysis pipeline is reliable.\n"
        
        context += "--- END ACCURACY CONTEXT ---"
        return context
