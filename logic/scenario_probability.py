"""
Phase-6A: Deterministic Scenario Probability Calculator

Rule-based probability assignment for market scenarios.
NO predictions, NO indicators, NO machine learning.
Pure structural logic.
"""

import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class ScenarioProbabilityCalculator:
    """
    Calculates deterministic probabilities for market scenarios based on:
    - HTF trend
    - HTF location (near support/resistance/mid-range)
    - LTF extension (mean reversion risk)
    - Alignment status
    
    All probabilities are rule-based and sum to exactly 1.00
    """
    
    def __init__(self):
        logger.info("ScenarioProbabilityCalculator initialized (Phase-6A)")
    
    def calculate_probabilities(
        self,
        alignment: str,
        is_unstable: bool,
        monthly_trend: str,
        htf_location: str,
        current_price: Optional[float],
        monthly_support: list,
        monthly_resistance: list
    ) -> Dict[str, any]:
        """
        Calculate scenario probabilities using deterministic rules.
        
        Args:
            alignment: FULL ALIGNMENT / PARTIAL ALIGNMENT / UNSTABLE / CONFLICT
            is_unstable: Whether price is overextended
            monthly_trend: bullish / bearish / sideways
            htf_location: Near resistance / Near support / Mid-range
            current_price: Current market price
            monthly_support: HTF support levels
            monthly_resistance: HTF resistance levels
        
        Returns:
            Dict with probabilities, reasoning, and active state
        """
        
        # Base probabilities (starting point)
        prob_a = 0.33  # Continuation
        prob_b = 0.33  # Pullback/Mean Reversion
        prob_c = 0.34  # Failure/Regime Change
        
        # Rule 1: Alignment State
        if alignment == "FULL ALIGNMENT" and not is_unstable:
            # Strong continuation probability when aligned and stable
            prob_a = 0.50
            prob_b = 0.30
            prob_c = 0.20
        elif alignment == "FULL ALIGNMENT" and is_unstable:
            # Overextension increases mean reversion risk
            prob_a = 0.30
            prob_b = 0.50
            prob_c = 0.20
        elif alignment == "PARTIAL ALIGNMENT":
            # Mixed signals, higher pullback probability
            prob_a = 0.35
            prob_b = 0.45
            prob_c = 0.20
        elif alignment == "UNSTABLE":
            # High mean reversion risk
            prob_a = 0.25
            prob_b = 0.55
            prob_c = 0.20
        elif alignment == "CONFLICT":
            # Conflicting timeframes, regime change risk elevated
            prob_a = 0.25
            prob_b = 0.35
            prob_c = 0.40
        
        # Rule 2: HTF Location Adjustment
        if "Near HTF resistance" in htf_location:
            # Near resistance: reduce continuation, increase pullback/failure
            prob_a *= 0.85
            prob_b *= 1.15
            prob_c *= 1.05
        elif "Near HTF support" in htf_location:
            # Near support: depends on trend
            if monthly_trend.lower() == "bullish":
                # Support in uptrend: potential bounce
                prob_a *= 1.05
                prob_b *= 1.10
                prob_c *= 0.90
            else:
                # Support in downtrend: breakdown risk
                prob_a *= 0.90
                prob_b *= 0.95
                prob_c *= 1.15
        
        # Rule 3: Mean Reversion Check (if overextended)
        if is_unstable:
            # Overextension always increases pullback probability
            prob_b *= 1.20
            prob_a *= 0.85
        
        # Rule 4: Trend Strength Adjustment
        if monthly_trend.lower() == "sideways":
            # Range-bound: breakout/breakdown scenarios elevated
            prob_a *= 0.80  # Continuation less likely in range
            prob_c *= 1.25  # Breakout/breakdown more likely
        
        # Normalize to sum to 1.00 (MANDATORY)
        total = prob_a + prob_b + prob_c
        prob_a /= total
        prob_b /= total
        prob_c /= total
        
        # Round to 2 decimal places
        prob_a = round(prob_a, 2)
        prob_b = round(prob_b, 2)
        prob_c = round(1.0 - prob_a - prob_b, 2)  # Ensure exact sum
        
        # Validate (consistency check)
        if abs((prob_a + prob_b + prob_c) - 1.0) > 0.01:
            logger.error(f"Probability sum validation failed: {prob_a + prob_b + prob_c}")
            # Force correction
            prob_c = round(1.0 - prob_a - prob_b, 2)
        
        # Determine ACTIVE scenario
        active_state = self._determine_active_state(
            prob_a, prob_b, prob_c, alignment, is_unstable
        )
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            alignment, is_unstable, monthly_trend, htf_location,
            prob_a, prob_b, prob_c
        )
        
        return {
            "scenario_probabilities": {
                "A_continuation": prob_a,
                "B_pullback": prob_b,
                "C_failure": prob_c
            },
            "active_state": active_state,
            "reasoning": reasoning,
            "validation": {
                "sum_check": round(prob_a + prob_b + prob_c, 2),
                "consistency": "PASS" if abs((prob_a + prob_b + prob_c) - 1.0) <= 0.01 else "FAIL"
            }
        }
    
    def _determine_active_state(
        self,
        prob_a: float,
        prob_b: float,
        prob_c: float,
        alignment: str,
        is_unstable: bool
    ) -> str:
        """
        Determine which scenario is ACTIVE based on strict rules.
        
        Rule: If UNSTABLE alignment → CONFLICT_STATE
        Otherwise → Highest probability scenario
        """
        if alignment == "CONFLICT":
            return "CONFLICT_STATE"
        
        if is_unstable and alignment == "UNSTABLE":
            return "CONFLICT_STATE"
        
        # Find highest probability
        probs = {
            "SCENARIO_A": prob_a,
            "SCENARIO_B": prob_b,
            "SCENARIO_C": prob_c
        }
        
        return max(probs, key=probs.get)
    
    def _generate_reasoning(
        self,
        alignment: str,
        is_unstable: bool,
        monthly_trend: str,
        htf_location: str,
        prob_a: float,
        prob_b: float,
        prob_c: float
    ) -> Dict[str, str]:
        """
        Generate structural justification for each probability.
        NO predictions, NO opinions - only facts.
        """
        
        # Scenario A reasoning
        if prob_a >= 0.45:
            a_reason = f"HTF trend {monthly_trend} and aligned; no structural break signaled"
        elif prob_a >= 0.30:
            a_reason = f"HTF trend {monthly_trend} intact but alignment weakening"
        else:
            a_reason = f"Continuation probability reduced due to {alignment.lower()} state"
        
        # Scenario B reasoning
        if is_unstable:
            b_reason = f"Price overextended near boundary; mean reversion risk elevated"
        elif "Near HTF resistance" in htf_location:
            b_reason = f"Price near HTF resistance; pullback zone approaching"
        elif prob_b >= 0.45:
            b_reason = f"Alignment {alignment.lower()} suggests rotation likely"
        else:
            b_reason = f"Standard pullback probability within {monthly_trend} structure"
        
        # Scenario C reasoning
        if prob_c >= 0.40:
            c_reason = f"Conflicting timeframes elevate regime change risk"
        elif "Near HTF support" in htf_location and monthly_trend.lower() == "bearish":
            c_reason = f"HTF support test increases breakdown probability"
        elif monthly_trend.lower() == "sideways":
            c_reason = f"Range boundaries create breakout/breakdown potential"
        else:
            c_reason = f"No HTF breakdown signaled; failure probability remains baseline"
        
        return {
            "A_reason": a_reason,
            "B_reason": b_reason,
            "C_reason": c_reason
        }
    
    def validate_logic_consistency(
        self,
        probabilities: Dict[str, float],
        alignment: str,
        monthly_trend: str,
        monthly_support: list,
        monthly_resistance: list,
        current_price: Optional[float]
    ) -> Dict[str, any]:
        """
        Validate that probability assignments don't contradict structure.
        
        Flags:
        - High continuation probability while below HTF support (contradiction)
        - High failure probability in perfect alignment (contradiction)
        - Any logical impossibilities
        """
        
        flags = []
        
        prob_a = probabilities.get("A_continuation", 0)
        prob_c = probabilities.get("C_failure", 0)
        
        # Check 1: Continuation probability vs structure
        if prob_a > 0.60 and current_price and monthly_support:
            if monthly_trend.lower() == "bullish" and current_price < monthly_support[0]:
                flags.append({
                    "type": "CONTRADICTION",
                    "message": f"High continuation probability ({prob_a:.2f}) but price below HTF support"
                })
        
        # Check 2: Failure probability vs alignment
        if prob_c > 0.50 and alignment == "FULL ALIGNMENT":
            flags.append({
                "type": "WARNING",
                "message": f"High failure probability ({prob_c:.2f}) despite full alignment"
            })
        
        # Check 3: Probability caps (no scenario should exceed 0.70 in healthy market)
        if prob_a > 0.70:
            flags.append({
                "type": "OVERCONFIDENCE",
                "message": f"Scenario A probability too high ({prob_a:.2f}) - markets are uncertain"
            })
        
        return {
            "consistency_check": "PASS" if not flags else "WARNING",
            "flags": flags
        }
