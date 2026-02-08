"""
Phase-7A: Execution Gate Engine

Hard gate that determines whether execution is structurally allowed.
NO scenario, probability, or confidence can trigger execution by itself.

ALL gates must pass. Single failure = EXECUTION_BLOCKED.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ExecutionGate:
    """
    Deterministic gate engine that blocks execution in unfavorable structural conditions.
    
    Philosophy: The agent refuses to act most of the time.
    Capital is exposed only when structure is asymmetric.
    
    Output: EXECUTION_ALLOWED or EXECUTION_BLOCKED (no other states)
    """
    
    def __init__(self):
        logger.info("ExecutionGate initialized (Phase-7A)")
    
    def evaluate(
        self,
        symbol: str,
        alignment: str,
        is_unstable: bool,
        probabilities: Dict[str, float],
        active_state: str,
        current_price: Optional[float],
        monthly_support: List[float],
        monthly_resistance: List[float],
        monthly_trend: str
    ) -> Dict[str, Any]:
        """
        Evaluate all execution gates.
        
        Returns:
            Dict with permission status, reasons, and gate results
        """
        
        gate_results = {}
        blocked_reasons = []
        
        # Extract probabilities
        prob_a = probabilities.get("A_continuation", 0)
        prob_b = probabilities.get("B_pullback", 0)
        prob_c = probabilities.get("C_failure", 0)
        
        # GATE-1: Alignment Gate
        gate1_pass = self._gate_alignment(alignment, is_unstable)
        gate_results["Gate-1_Alignment"] = "PASS" if gate1_pass else "FAIL"
        if not gate1_pass:
            blocked_reasons.append("Gate-1: Alignment UNSTABLE or CONFLICT")
        
        # GATE-2: Probability Dominance Gate
        gate2_pass = self._gate_probability_dominance(prob_a, prob_b, prob_c)
        gate_results["Gate-2_Dominance"] = "PASS" if gate2_pass else "FAIL"
        if not gate2_pass:
            blocked_reasons.append(f"Gate-2: No dominant probability (max={max(prob_a, prob_b, prob_c):.2f} < 0.55)")
        
        # GATE-3: Regime Risk Gate
        gate3_pass = self._gate_regime_risk(prob_c)
        gate_results["Gate-3_RegimeRisk"] = "PASS" if gate3_pass else "FAIL"
        if not gate3_pass:
            blocked_reasons.append(f"Gate-3: Regime change risk too high (prob_c={prob_c:.2f} ≥ 0.30)")
        
        # GATE-4: Structural Location Gate
        gate4_pass = self._gate_structural_location(
            current_price, monthly_resistance, active_state, monthly_trend
        )
        gate_results["Gate-4_StructuralLocation"] = "PASS" if gate4_pass else "FAIL"
        if not gate4_pass:
            blocked_reasons.append("Gate-4: Price in HTF resistance zone with continuation scenario")
        
        # GATE-5: Overconfidence Protection
        gate5_pass = self._gate_overconfidence(prob_a, prob_b, prob_c)
        gate_results["Gate-5_Overconfidence"] = "PASS" if gate5_pass else "FAIL"
        if not gate5_pass:
            blocked_reasons.append(f"Gate-5: Overconfidence detected (probability > 0.70)")
        
        # Final decision: ALL must pass
        all_gates_pass = all([gate1_pass, gate2_pass, gate3_pass, gate4_pass, gate5_pass])
        
        if all_gates_pass:
            permission = {
                "status": "ALLOWED",
                "valid_for": "ONE_DECISION_CYCLE",
                "expires_after": "next_structure_change",
                "granted_at": datetime.utcnow().isoformat()
            }
            logger.info(f"✅ Execution ALLOWED for {symbol}")
        else:
            permission = {
                "status": "BLOCKED",
                "reason": blocked_reasons,
                "blocked_at": datetime.utcnow().isoformat()
            }
            logger.warning(f"🚫 Execution BLOCKED for {symbol}: {', '.join(blocked_reasons)}")
        
        return {
            "execution_permission": permission,
            "gate_results": gate_results,
            "all_gates_pass": all_gates_pass,
            "blocked_reasons": blocked_reasons if not all_gates_pass else []
        }
    
    def _gate_alignment(self, alignment: str, is_unstable: bool) -> bool:
        """
        Gate-1: Alignment Gate
        
        BLOCK if: alignment in {UNSTABLE, CONFLICT, PARTIAL ALIGNMENT}
        PASS only if: FULL ALIGNMENT and stable
        
        Rationale: All timeframes must agree. No cherry picking.
        """
        # Block UNSTABLE, CONFLICT, or PARTIAL
        if alignment in ["UNSTABLE", "CONFLICT", "PARTIAL ALIGNMENT"]:
            return False
        
        # Even FULL ALIGNMENT can be blocked if unstable
        if is_unstable and alignment == "FULL ALIGNMENT":
            return False
        
        # Only FULL ALIGNMENT + stable passes
        return alignment == "FULL ALIGNMENT"
    
    def _gate_probability_dominance(
        self,
        prob_a: float,
        prob_b: float,
        prob_c: float
    ) -> bool:
        """
        Gate-2: Probability Dominance Gate
        
        BLOCK if: max(prob_a, prob_b, prob_c) < 0.55
        
        Rationale: Low-edge environments where no scenario dominates.
        Market is unclear, so we wait.
        """
        max_prob = max(prob_a, prob_b, prob_c)
        return max_prob >= 0.55
    
    def _gate_regime_risk(self, prob_c: float) -> bool:
        """
        Gate-3: Regime Risk Gate
        
        BLOCK if: prob_c >= 0.30
        
        Rationale: Regime change (trend failure) probability too high.
        We don't execute near structural breaks.
        """
        return prob_c < 0.30
    
    def _gate_structural_location(
        self,
        current_price: Optional[float],
        monthly_resistance: List[float],
        active_state: str,
        monthly_trend: str
    ) -> bool:
        """
        Gate-4: Structural Location Gate
        
        BLOCK if: Price in HTF resistance zone AND active_state = SCENARIO_A
        
        Rationale: Prevents buying tops.
        If continuation is active but we're at resistance, we wait for breakout.
        """
        if not current_price or not monthly_resistance:
            return True  # Can't evaluate, pass by default
        
        # Check if price is in resistance zone (within 2% of resistance)
        in_resistance_zone = any(
            abs(current_price - r) / r <= 0.02 for r in monthly_resistance
        )
        
        # Also check if price is ABOVE resistance slightly (early breakout attempts)
        near_resistance = any(
            current_price >= r * 0.98 and current_price <= r * 1.03 
            for r in monthly_resistance
        )
        
        if (in_resistance_zone or near_resistance) and active_state == "SCENARIO_A":
            # Additional check: if trend is bullish and we're testing resistance
            if monthly_trend.lower() == "bullish":
                return False  # BLOCK: Don't buy at resistance
        
        return True
    
    def _gate_overconfidence(
        self,
        prob_a: float,
        prob_b: float,
        prob_c: float
    ) -> bool:
        """
        Gate-5: Overconfidence Protection
        
        BLOCK if: Any probability > 0.70
        
        Rationale: Markets are uncertain. No scenario should have >70% probability.
        This catches any calculation errors and prevents overconfidence.
        """
        return all(p <= 0.70 for p in [prob_a, prob_b, prob_c])
    
    def get_execution_state_label(self, permission: Dict[str, Any]) -> str:
        """
        Get human-readable execution state.
        
        Returns:
            "EXECUTION ALLOWED" or "EXECUTION BLOCKED"
        """
        status = permission.get("status", "UNKNOWN")
        if status == "ALLOWED":
            return "EXECUTION ALLOWED"
        else:
            return "EXECUTION BLOCKED"
    
    def format_blocked_message(self, blocked_reasons: List[str]) -> str:
        """
        Format blocked reasons for display.
        
        Returns:
            Human-readable message explaining why execution is blocked
        """
        if not blocked_reasons:
            return "Execution blocked due to structural conditions."
        
        reasons_text = "\n    - ".join(blocked_reasons)
        return f"Execution blocked:\n    - {reasons_text}"
