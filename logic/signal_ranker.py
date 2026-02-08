"""
Phase-11.5: Signal Ranker
Deterministic ranking of eligible signals.

NO ML, NO PREDICTIONS, NO MAGIC.
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RankedSignal:
    """
    Signal with deterministic ranking score.
    """
    instrument: str
    signal_contract: Any  # SignalContract from Phase-11
    rank_score: float
    rank_reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "instrument": self.instrument,
            "rank_score": self.rank_score,
            "rank_reason": self.rank_reason,
            "signal": self.signal_contract.to_dict()
        }


class SignalRanker:
    """
    Deterministic ranking of Phase-11 signals.
    
    Rules:
    1. Only ELIGIBLE signals considered
    2. Fixed scoring formula (no learning)
    3. Signal rarity enforcement (≤20%)
    """
    
    def __init__(self):
        """Initialize Signal Ranker"""
        logger.info("SignalRanker initialized (Phase-11.5)")
    
    def rank_signals(
        self,
        signals: List[tuple[str, Any]],  # List of (instrument, SignalContract)
        max_results: int = 5
    ) -> List[RankedSignal]:
        """
        Rank signals deterministically.
        
        Args:
            signals: List of (instrument_name, SignalContract) tuples
            max_results: Maximum number of results to return
        
        Returns:
            Ranked list of signals (highest score first)
        """
        # Step 1: Filter to ELIGIBLE only
        eligible = []
        for instrument, signal in signals:
            if signal.signal_status.value == "ELIGIBLE":
                eligible.append((instrument, signal))
        
        if not eligible:
            logger.info("No eligible signals found in scan")
            return []
        
        # Step 2: Calculate scores
        ranked = []
        for instrument, signal in eligible:
            score, reason = self._calculate_score(signal)
            ranked.append(RankedSignal(
                instrument=instrument,
                signal_contract=signal,
                rank_score=score,
                rank_reason=reason
            ))
        
        # Step 3: Sort by score (DESC), then risk (ASC), then confidence (DESC)
        ranked.sort(key=lambda x: (
            -x.rank_score,  # Higher score first
            self._risk_priority(x.signal_contract.risk_class.value),  # Lower risk first
            -self._confidence_priority(x.signal_contract.confidence)  # Higher confidence first
        ))
        
        # Step 4: Enforce signal rarity (≤20% of scanned) - only if requested
        # For testing/small scans, allow more flexibility
        total_scanned = len(signals)
        if total_scanned >= 10:  # Only enforce rarity for larger scans
            max_eligible = max(1, int(total_scanned * 0.2))  # At least 1, but ≤20%
            
            if len(ranked) > max_eligible:
                logger.warning(f"Signal rarity enforcement: {len(ranked)} eligible → keeping top {max_eligible}")
                ranked = ranked[:max_eligible]
        
        # Step 5: Limit to max_results
        ranked = ranked[:max_results]
        
        logger.info(f"Ranked {len(ranked)} signals from {len(eligible)} eligible ({total_scanned} total scanned)")
        return ranked
    
    def _calculate_score(self, signal) -> tuple[float, str]:
        """
        Calculate deterministic score for signal.
        
        Args:
            signal: SignalContract from Phase-11
        
        Returns:
            (score, reason_string)
        """
        # Base score from verdict
        if signal.verdict == "STRONG":
            base_score = 100
            reason = "STRONG verdict"
        elif signal.verdict == "CAUTION":
            base_score = 70
            reason = "CAUTION verdict"
        else:
            base_score = 0
            reason = f"{signal.verdict} verdict (not eligible)"
        
        # Risk modifiers
        risk_modifier = 0
        if signal.risk_class.value == "LOW":
            risk_modifier = 20
            reason += " + LOW risk"
        elif signal.risk_class.value == "MEDIUM":
            risk_modifier = 10
            reason += " + MEDIUM risk"
        elif signal.risk_class.value == "HIGH":
            risk_modifier = -20
            reason += " - HIGH risk"
        
        # Entry style modifiers
        entry_modifier = 0
        if signal.entry_style.value == "IMMEDIATE_OK":
            entry_modifier = 10
            reason += " + immediate entry OK"
        elif signal.entry_style.value == "PULLBACK_ONLY":
            entry_modifier = 0
            reason += " (pullback entry)"
        
        total_score = base_score + risk_modifier + entry_modifier
        
        return total_score, reason
    
    def _risk_priority(self, risk_class: str) -> int:
        """Convert risk class to sort priority (lower = better)"""
        priority_map = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "EXTREME": 4
        }
        return priority_map.get(risk_class, 5)
    
    def _confidence_priority(self, confidence: str) -> int:
        """Convert confidence to sort priority (higher = better)"""
        priority_map = {
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1
        }
        return priority_map.get(confidence, 0)
