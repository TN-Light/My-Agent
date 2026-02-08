"""
Phase-X: Human Summary Engine (Final Interpretation Layer)

Purpose: Convert institutional-grade structural output into single human-readable conclusion.

CRITICAL RULES:
- Read-only interpreter (never influences analysis, probability, risk, or execution)
- Deterministic verdict logic (same inputs = same output)
- Template-driven summaries (no creativity, no LLM freedom)
- No dependencies (no TradingView, no vision, no indicators)

Inputs (STRICT):
- alignment_state: FULL / PARTIAL / UNSTABLE / CONFLICT
- active_state: SCENARIO_A / SCENARIO_B / SCENARIO_C / CONFLICT_STATE
- execution_gate_status: PASS / BLOCKED
- regime_flags: set() or list (EDGE_DEGRADATION, REGIME_CHANGE, etc.)
- htf_location: SUPPORT / MID / RESISTANCE
- trend_state: UP / DOWN / RANGE

Output (STRICT):
- verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
- summary: Template-driven text (no variation)
- confidence: HIGH / MEDIUM / LOW
"""

from typing import Dict, Any, Set, List, Union
import logging

logger = logging.getLogger(__name__)


class HumanSummaryEngine:
    """
    Read-only interpreter that translates finalized structural facts into human verdicts.
    
    Guarantees:
    - No accuracy loss
    - No execution leakage
    - No visual dependency
    - Beginner-friendly
    - Institution-compliant
    """
    
    # Template-driven summaries (LOCKED - no variation)
    SUMMARY_TEMPLATES = {
        "STRONG": "Structure is strong and aligned across timeframes. Conditions favor continuation.",
        "CAUTION": "Structure is strong but price is near higher-timeframe resistance. Risk is elevated.",
        "WAIT": "Signals are mixed across timeframes. Waiting for confirmation is safer.",
        "AVOID": "Market structure is unstable or conflicting. Risk is high. Wait for clarity before trading.",
        "NO_TRADE": "Market structure is unstable or conflicting. Risk is high. Wait for clarity before trading."
    }
    
    def __init__(self):
        """Initialize the Human Summary Engine."""
        pass
    
    def generate(
        self,
        *,
        alignment_state: str,
        active_state: str,
        execution_gate_status: str,
        regime_flags: Union[Set[str], List[str]],
        htf_location: str,
        trend_state: str
    ) -> Dict[str, Any]:
        """
        Generate human-readable verdict from finalized structural facts.
        
        Args:
            alignment_state: FULL / PARTIAL / UNSTABLE / CONFLICT
            active_state: SCENARIO_A / SCENARIO_B / SCENARIO_C / CONFLICT_STATE
            execution_gate_status: PASS / BLOCKED
            regime_flags: set() or list (EDGE_DEGRADATION, REGIME_CHANGE, etc.)
            htf_location: SUPPORT / MID / RESISTANCE
            trend_state: UP / DOWN / RANGE
        
        Returns:
            Dict with:
            - verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
            - summary: Template-driven human sentence
            - confidence: HIGH / MEDIUM / LOW
        """
        
        # Step 1: Determine verdict (deterministic rules)
        verdict = self._determine_verdict(
            alignment_state=alignment_state,
            active_state=active_state,
            execution_gate_status=execution_gate_status,
            regime_flags=regime_flags,
            htf_location=htf_location
        )
        
        # Step 2: Map confidence (deterministic)
        confidence = self._map_confidence(verdict)
        
        # Step 3: Get summary text (template-driven with context)
        summary = self._summary_text(
            verdict=verdict,
            alignment_state=alignment_state,
            htf_location=htf_location
        )
        
        return {
            "verdict": verdict,
            "summary": summary,
            "confidence": confidence
        }
    
    def _determine_verdict(
        self,
        alignment_state: str,
        active_state: str,
        execution_gate_status: str,
        regime_flags: Union[Set[str], List[str]],
        htf_location: str
    ) -> str:
        """
        Deterministic verdict logic (checked in priority order).
        
        Priority:
        1. Absolute overrides (BLOCKED, REGIME_CHANGE)
        2. Structural risk states (UNSTABLE, CONFLICT, PARTIAL)
        3. Constructive states (FULL alignment variations)
        4. Fallback (WAIT)
        
        Args:
            alignment_state: FULL / PARTIAL / UNSTABLE / CONFLICT
            active_state: SCENARIO_A / SCENARIO_B / SCENARIO_C / CONFLICT_STATE
            execution_gate_status: PASS / BLOCKED
            regime_flags: set() or list
            htf_location: SUPPORT / MID / RESISTANCE
        
        Returns:
            Verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
        """
        
        # Convert to set if list
        if isinstance(regime_flags, list):
            regime_flags = set(regime_flags)
        
        # PRIORITY 1: ABSOLUTE OVERRIDES
        
        # Rule 1.1: Regime change detected (highest priority)
        if "REGIME_CHANGE" in regime_flags:
            return "AVOID"
        
        # PRIORITY 2: STRUCTURAL RISK STATES
        
        # Rule 2.1: Unstable or conflicting structure
        if alignment_state in ["UNSTABLE", "CONFLICT"]:
            # Use NO_TRADE if gate also blocked (for execution tracking)
            # But summary will describe market condition, not gate
            if execution_gate_status == "BLOCKED":
                return "NO_TRADE"
            return "AVOID"
        
        # Rule 2.2: Partial alignment (mixed signals)
        if alignment_state == "PARTIAL":
            return "WAIT"
        
        # PRIORITY 3: CONSTRUCTIVE STATES
        
        # Rule 3.1: Full alignment + continuation + mid-range
        if (alignment_state == "FULL" and 
            active_state == "SCENARIO_A" and 
            htf_location == "MID"):
            return "STRONG"
        
        # Rule 3.2: Full alignment + continuation + support
        if (alignment_state == "FULL" and 
            active_state == "SCENARIO_A" and 
            htf_location == "SUPPORT"):
            return "STRONG"
        
        # Rule 3.3: Full alignment + continuation + resistance (extended)
        if (alignment_state == "FULL" and 
            active_state == "SCENARIO_A" and 
            htf_location == "RESISTANCE"):
            return "CAUTION"
        
        # Rule 3.4: Full alignment + pullback/reversion
        if (alignment_state == "FULL" and 
            active_state == "SCENARIO_B"):
            return "WAIT"
        
        # Rule 3.5: Full alignment + failure scenario
        if (alignment_state == "FULL" and 
            active_state == "SCENARIO_C"):
            return "AVOID"
        
        # PRIORITY 4: FALLBACK (never silent)
        logger.warning(f"Verdict fallback triggered: alignment={alignment_state}, active={active_state}, gate={execution_gate_status}")
        return "WAIT"
    
    def _map_confidence(self, verdict: str) -> str:
        """
        Map verdict to confidence level (deterministic).
        
        Args:
            verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
        
        Returns:
            Confidence: HIGH / MEDIUM / LOW
        """
        
        if verdict == "STRONG":
            return "HIGH"
        
        if verdict in ["CAUTION", "WAIT"]:
            return "MEDIUM"
        
        if verdict in ["AVOID", "NO_TRADE"]:
            return "LOW"
        
        # Fallback (should never reach)
        return "LOW"
    
    def _summary_text(self, verdict: str, alignment_state: str = None, htf_location: str = None) -> str:
        """
        Get template-driven summary text with context enrichment.
        
        Args:
            verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
            alignment_state: FULL / PARTIAL / UNSTABLE / CONFLICT (optional for context)
            htf_location: SUPPORT / MID / RESISTANCE (optional for context)
        
        Returns:
            Context-enriched template string explaining market condition
        """
        
        base_summary = self.SUMMARY_TEMPLATES.get(verdict, self.SUMMARY_TEMPLATES["WAIT"])
        
        # Context-aware summaries: explain market condition, not system decision
        # Focus on structure, risk, and re-evaluation criteria
        
        if verdict == "NO_TRADE":
            # Gate blocked or regime change - but explain WHY using market context
            if alignment_state == "CONFLICT":
                if htf_location == "RESISTANCE":
                    return "Timeframes conflicting near resistance. High structural risk. Do not trade until alignment improves."
                elif htf_location == "SUPPORT":
                    return "Timeframes conflicting near support. Market lacks clarity. Do not trade until structure stabilizes."
                else:
                    return "Timeframes showing conflicting signals. Market direction unclear. Do not trade - wait for alignment."
            
            elif alignment_state == "UNSTABLE":
                if htf_location == "RESISTANCE":
                    return "Stock overextended near resistance with unstable structure. Extreme risk of reversal. Do not trade."
                elif htf_location == "SUPPORT":
                    return "Stock overextended near support with unstable structure. Risk of breakdown or whipsaw. Do not trade."
                else:
                    return "Market structure highly unstable. Price overextended without support. Do not trade until consolidation."
            
            elif alignment_state == "PARTIAL":
                return "Partial alignment with elevated risk. Market lacks conviction. Do not trade - wait for stronger setup."
            
            else:
                # Fallback if no context available
                return "Market conditions unfavorable for trading. High risk environment. Do not trade until structure improves."
        
        if verdict == "AVOID":
            if alignment_state == "CONFLICT":
                if htf_location == "RESISTANCE":
                    return "Higher timeframes near resistance while lower timeframes show conflicting signals. Stock lacks directional edge. Avoid trading until timeframes align."
                elif htf_location == "SUPPORT":
                    return "Higher timeframes near support while lower timeframes show conflicting signals. No clear bias. Wait for alignment before trading."
                else:
                    return "Timeframes are contradicting each other. Market direction unclear. Avoid trading until structure aligns."
            
            elif alignment_state == "UNSTABLE":
                if htf_location == "RESISTANCE":
                    return "Stock is overextended near higher-timeframe resistance with unstable structure. High risk of pullback. Avoid trading until price stabilizes."
                elif htf_location == "SUPPORT":
                    return "Stock is overextended near higher-timeframe support with unstable structure. Watch for bounce or breakdown. Wait for clarity."
                else:
                    return "Market structure is unstable. Price overextended without clear support from all timeframes. Wait for consolidation before trading."
            
            elif alignment_state == "PARTIAL":
                if htf_location == "RESISTANCE":
                    return "Stock near resistance with partial alignment. Upside continuation is weak. Avoid trading - wait for breakout with full alignment or pullback to support."
                elif htf_location == "SUPPORT":
                    return "Stock near support with partial alignment. Downside risk exists but not confirmed. Wait for either full alignment or breakdown below support."
                else:
                    return "Partial alignment - no dominant trend established. Stock lacks directional conviction. Wait for stronger structural setup."
            
            else:
                # Fallback if no alignment_state provided
                return base_summary
        
        if verdict == "WAIT":
            if alignment_state == "PARTIAL":
                return "Alignment is building but not complete. Trend is forming. Wait for full confirmation across all timeframes before trading."
            else:
                return "Market structure is developing. Wait for clearer signals before taking action."
        
        if verdict == "CAUTION":
            if htf_location == "RESISTANCE":
                return "Trend is strong but stock is extended near higher-timeframe resistance. Consider waiting for pullback to safer entry level."
            elif htf_location == "SUPPORT":
                return "Trend is intact and stock is near higher-timeframe support. Favorable risk/reward but watch for breakdown. Use tight stops."
            else:
                return base_summary
        
        # STRONG verdict - use base template (already good)
        return base_summary
    
    def format_for_display(self, result: Dict[str, Any]) -> str:
        """
        Format verdict result for console display.
        
        Args:
            result: Dict from generate() method
        
        Returns:
            Formatted string for output
        """
        
        verdict = result["verdict"]
        summary = result["summary"]
        confidence = result["confidence"]
        
        # Verdict emoji mapping (ASCII for Windows compatibility)
        emoji_map = {
            "STRONG": "[STRONG]",
            "CAUTION": "[CAUTION]",
            "WAIT": "[WAIT]",
            "AVOID": "[AVOID]",
            "NO_TRADE": "[NO_TRADE]"
        }
        
        emoji = emoji_map.get(verdict, "[INFO]")
        
        lines = []
        lines.append("=" * 70)
        lines.append(f"{emoji} FINAL VERDICT: {verdict}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("SUMMARY:")
        lines.append(f"  {summary}")
        lines.append("")
        lines.append(f"CONFIDENCE: {confidence}")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def get_verdict_color(self, verdict: str) -> str:
        """
        Get color code for verdict display in UI.
        
        Args:
            verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
        
        Returns:
            Color code: SUCCESS / WARNING / INFO / ERROR
        """
        
        color_map = {
            "STRONG": "SUCCESS",
            "CAUTION": "WARNING",
            "WAIT": "INFO",
            "AVOID": "ERROR",
            "NO_TRADE": "ERROR"
        }
        
        return color_map.get(verdict, "INFO")
