"""
PHASE-8B: SCENARIO RESOLUTION ENGINE
Purpose: Determine which scenario actually played out (STRUCTURE-BASED)

NON-NEGOTIABLE RULES:
1. Structure decides, not price alone
2. HTF structure is the authority
3. Resolution confidence must be tracked
4. Profit/loss is irrelevant to resolution

Resolution Rules (STRUCTURAL):
- Scenario A: HTF structure held AND continuation level reached
- Scenario B: Price reversed but HTF not broken
- Scenario C: HTF support/resistance violated

Philosophy:
"Price alone is insufficient. Structure decides."
"""

from typing import Optional, Tuple
from datetime import datetime

from storage.trade_lifecycle_store import TradeLifecycleStore


class ScenarioResolutionEngine:
    """
    Determine which scenario actually occurred.
    
    Structure-based resolution - price alone is insufficient.
    """
    
    def __init__(self, store: Optional[TradeLifecycleStore] = None):
        """
        Initialize resolution engine.
        
        Args:
            store: Database store (creates new if None)
        """
        self.store = store or TradeLifecycleStore()
    
    def resolve_trade(
        self,
        trade_id: str,
        actual_htf_support: Optional[float],
        actual_htf_resistance: Optional[float],
        htf_structure_broken: bool,
        continuation_level_reached: bool,
        price_reversed: bool
    ) -> Tuple[str, bool, str]:
        """
        Resolve trade scenario.
        
        Args:
            trade_id: Trade identifier
            actual_htf_support/resistance: Actual HTF levels (may differ from entry)
            htf_structure_broken: Whether HTF S/R was violated
            continuation_level_reached: Whether continuation target hit
            price_reversed: Whether price reversed (but HTF held)
        
        Returns:
            (resolved_scenario, structure_respected, confidence)
        """
        # Get original trade
        trade = self.store.get_trade(trade_id)
        if not trade:
            raise ValueError(f"Trade {trade_id} not found")
        
        original_scenario = trade["scenario"]
        direction = trade["direction"]
        
        # ========================================
        # RESOLUTION LOGIC (STRUCTURAL)
        # ========================================
        
        resolved_scenario = None
        structure_respected = False
        confidence = "LOW"
        notes = ""
        
        # Scenario C: HTF structure violated
        if htf_structure_broken:
            resolved_scenario = "C"
            
            # Check if original scenario was C
            if original_scenario == "C":
                structure_respected = True
                confidence = "HIGH"
                notes = "HTF structure broken as expected (Scenario C)"
            else:
                structure_respected = False
                confidence = "HIGH"
                notes = f"HTF structure broken unexpectedly (was {original_scenario}, became C)"
        
        # Scenario A: HTF held AND continuation
        elif continuation_level_reached and not htf_structure_broken:
            resolved_scenario = "A"
            
            if original_scenario == "A":
                structure_respected = True
                confidence = "HIGH"
                notes = "HTF held and continuation reached (Scenario A)"
            else:
                structure_respected = False
                confidence = "HIGH"
                notes = f"Continuation occurred unexpectedly (was {original_scenario}, became A)"
        
        # Scenario B: Price reversed but HTF not broken
        elif price_reversed and not htf_structure_broken:
            resolved_scenario = "B"
            
            if original_scenario == "B":
                structure_respected = True
                confidence = "HIGH"
                notes = "Price reversed but HTF held (Scenario B)"
            else:
                structure_respected = False
                confidence = "MEDIUM"
                notes = f"Price reversed (was {original_scenario}, became B)"
        
        # Unclear/incomplete data
        else:
            # Default to partial continuation (if no clear break or reversal)
            if not htf_structure_broken and not price_reversed:
                resolved_scenario = "A"
                confidence = "LOW"
                notes = "Insufficient data - defaulting to partial continuation"
                
                if original_scenario == "A":
                    structure_respected = True
                else:
                    structure_respected = False
            else:
                # Unclear case
                resolved_scenario = original_scenario
                structure_respected = False
                confidence = "LOW"
                notes = "Unclear resolution - insufficient structural data"
        
        # ========================================
        # STORE RESOLUTION
        # ========================================
        self.store.update_resolution(
            trade_id=trade_id,
            resolved_scenario=resolved_scenario,
            structure_respected=structure_respected,
            resolution_confidence=confidence,
            resolution_notes=notes
        )
        
        return resolved_scenario, structure_respected, confidence
    
    def resolve_trade_simple(
        self,
        trade_id: str,
        resolved_scenario: str,
        structure_respected: bool,
        confidence: str = "HIGH",
        notes: Optional[str] = None
    ) -> None:
        """
        Manually resolve trade (for testing or manual review).
        
        Args:
            trade_id: Trade identifier
            resolved_scenario: A/B/C
            structure_respected: Whether structure was respected
            confidence: HIGH/MEDIUM/LOW
            notes: Optional notes
        """
        if resolved_scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid resolved_scenario: {resolved_scenario}")
        
        if confidence not in ["HIGH", "MEDIUM", "LOW"]:
            raise ValueError(f"Invalid confidence: {confidence}")
        
        self.store.update_resolution(
            trade_id=trade_id,
            resolved_scenario=resolved_scenario,
            structure_respected=structure_respected,
            resolution_confidence=confidence,
            resolution_notes=notes
        )
    
    def get_resolution_stats(self) -> dict:
        """
        Get resolution statistics.
        
        Returns:
            Dictionary with resolution stats
        """
        resolved_trades = self.store.get_resolved_trades()
        
        if not resolved_trades:
            return {
                "total_resolved": 0,
                "structure_respected": 0,
                "structure_violated": 0,
                "respect_rate": 0.0,
                "scenario_distribution": {"A": 0, "B": 0, "C": 0}
            }
        
        structure_counts = self.store.get_structure_respected_count()
        
        # Scenario distribution
        scenario_dist = {"A": 0, "B": 0, "C": 0}
        for trade in resolved_trades:
            scenario = trade["resolved_scenario"]
            if scenario in scenario_dist:
                scenario_dist[scenario] += 1
        
        respect_rate = (
            structure_counts["respected"] / len(resolved_trades)
            if len(resolved_trades) > 0 else 0.0
        )
        
        return {
            "total_resolved": len(resolved_trades),
            "structure_respected": structure_counts["respected"],
            "structure_violated": structure_counts["violated"],
            "respect_rate": respect_rate,
            "scenario_distribution": scenario_dist
        }
    
    def get_scenario_accuracy(self, scenario: str) -> float:
        """
        Get accuracy for a specific scenario.
        
        Args:
            scenario: A/B/C
        
        Returns:
            Accuracy (0.0 - 1.0)
        """
        resolved_trades = self.store.get_resolved_trades()
        
        # Filter trades where this scenario was predicted
        scenario_trades = [t for t in resolved_trades if t["scenario"] == scenario]
        
        if not scenario_trades:
            return 0.0
        
        # Count correct predictions
        correct = sum(
            1 for t in scenario_trades
            if t["resolved_scenario"] == scenario and t["structure_respected"] == 1
        )
        
        return correct / len(scenario_trades)
    
    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_resolution_stats()
        return (
            f"ScenarioResolutionEngine("
            f"resolved={stats['total_resolved']}, "
            f"respect_rate={stats['respect_rate']:.2%})"
        )
