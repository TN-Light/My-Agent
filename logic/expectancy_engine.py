"""
PHASE-8C: EXPECTANCY ENGINE
Purpose: Measure edge through structural accuracy (NOT P&L)

NON-NEGOTIABLE RULES:
1. Wins = structure respected, Losses = structure violated
2. Money is secondary, structure is primary
3. Edge degradation must be detected
4. Overconfidence bias must be flagged

Expectancy Formula:
Expectancy = (WinRate × AvgWin) - (LossRate × AvgLoss)

But: Wins/Losses based on STRUCTURE, not profit.

Philosophy:
"Proof of edge. Losses explained logically. Long-term survivability."
"""

from typing import Optional, Dict, List, Any
from statistics import mean, stdev
from storage.trade_lifecycle_store import TradeLifecycleStore


class ExpectancyEngine:
    """
    Measure edge through structural accuracy.
    
    Structure > P&L. Edge is proven, not assumed.
    """
    
    # Thresholds for warnings
    EDGE_DEGRADATION_THRESHOLD = 0.45  # < 45% accuracy = edge degradation
    MINIMUM_SAMPLE_SIZE = 50  # Minimum trades for drift detection
    REGIME_SHIFT_MULTIPLIER = 1.5  # Scenario C frequency > 1.5× baseline
    
    def __init__(self, store: Optional[TradeLifecycleStore] = None):
        """
        Initialize expectancy engine.
        
        Args:
            store: Database store (creates new if None)
        """
        self.store = store or TradeLifecycleStore()
    
    def calculate_scenario_accuracy(self, scenario: str) -> Dict[str, Any]:
        """
        Calculate accuracy for a specific scenario.
        
        Args:
            scenario: A/B/C
        
        Returns:
            Dictionary with accuracy metrics
        """
        resolved_trades = self.store.get_resolved_trades()
        
        # Filter trades for this scenario
        scenario_trades = [t for t in resolved_trades if t["scenario"] == scenario]
        
        if not scenario_trades:
            return {
                "scenario": scenario,
                "total_trades": 0,
                "correct": 0,
                "incorrect": 0,
                "accuracy": 0.0,
                "status": "NO_DATA"
            }
        
        # Count correct (structure respected + scenario matched)
        correct = sum(
            1 for t in scenario_trades
            if t["resolved_scenario"] == scenario and t["structure_respected"] == 1
        )
        
        incorrect = len(scenario_trades) - correct
        accuracy = correct / len(scenario_trades)
        
        # Determine status
        if len(scenario_trades) < 10:
            status = "INSUFFICIENT_DATA"
        elif accuracy < self.EDGE_DEGRADATION_THRESHOLD:
            status = "EDGE_DEGRADATION"
        elif accuracy > 0.60:
            status = "EDGE_VALID"
        else:
            status = "MARGINAL"
        
        return {
            "scenario": scenario,
            "total_trades": len(scenario_trades),
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy,
            "status": status
        }
    
    def calculate_conditional_accuracy(self, alignment_state: str) -> Dict[str, Any]:
        """
        Calculate accuracy by alignment state.
        
        Args:
            alignment_state: Alignment state to filter by
        
        Returns:
            Dictionary with conditional accuracy
        """
        resolved_trades = self.store.get_resolved_trades()
        
        # Filter by alignment
        filtered = [t for t in resolved_trades if t["alignment_state"] == alignment_state]
        
        if not filtered:
            return {
                "alignment_state": alignment_state,
                "total_trades": 0,
                "accuracy": 0.0
            }
        
        correct = sum(1 for t in filtered if t["structure_respected"] == 1)
        accuracy = correct / len(filtered)
        
        return {
            "alignment_state": alignment_state,
            "total_trades": len(filtered),
            "correct": correct,
            "accuracy": accuracy
        }
    
    def calculate_expectancy(self) -> Dict[str, Any]:
        """
        Calculate structural expectancy.
        
        Wins = structure respected
        Losses = structure violated
        
        Returns:
            Dictionary with expectancy metrics
        """
        resolved_trades = self.store.get_resolved_trades()
        
        if not resolved_trades:
            return {
                "total_trades": 0,
                "expectancy": 0.0,
                "win_rate": 0.0,
                "avg_mfe": 0.0,
                "avg_mae": 0.0,
                "status": "NO_DATA"
            }
        
        # Separate wins (structure respected) and losses (structure violated)
        wins = [t for t in resolved_trades if t["structure_respected"] == 1]
        losses = [t for t in resolved_trades if t["structure_respected"] == 0]
        
        win_rate = len(wins) / len(resolved_trades) if resolved_trades else 0.0
        loss_rate = 1.0 - win_rate
        
        # Calculate average MFE (wins) and MAE (losses)
        avg_mfe = mean([t["mfe"] for t in wins]) if wins else 0.0
        avg_mae = mean([abs(t["mae"]) for t in losses]) if losses else 0.0
        
        # Expectancy formula
        expectancy = (win_rate * avg_mfe) - (loss_rate * avg_mae)
        
        # Determine status
        if len(resolved_trades) < 20:
            status = "INSUFFICIENT_DATA"
        elif expectancy > 0:
            status = "POSITIVE_EXPECTANCY"
        elif expectancy < 0:
            status = "NEGATIVE_EXPECTANCY"
        else:
            status = "BREAKEVEN"
        
        return {
            "total_trades": len(resolved_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "avg_mfe": avg_mfe,
            "avg_mae": avg_mae,
            "expectancy": expectancy,
            "status": status
        }
    
    def calculate_false_positive_rate(self) -> float:
        """
        Calculate false positive rate.
        
        False positive = trade taken but structure violated
        
        Returns:
            False positive rate (0.0 - 1.0)
        """
        resolved_trades = self.store.get_resolved_trades()
        
        if not resolved_trades:
            return 0.0
        
        false_positives = sum(1 for t in resolved_trades if t["structure_respected"] == 0)
        return false_positives / len(resolved_trades)
    
    def calculate_structural_failure_rate(self) -> float:
        """
        Calculate structural failure rate.
        
        Same as false positive rate (structure violated).
        
        Returns:
            Structural failure rate (0.0 - 1.0)
        """
        return self.calculate_false_positive_rate()
    
    def detect_edge_degradation(self, scenario: str) -> Dict[str, Any]:
        """
        Detect edge degradation for a scenario.
        
        Args:
            scenario: A/B/C
        
        Returns:
            Dictionary with degradation analysis
        """
        resolved_trades = self.store.get_resolved_trades()
        scenario_trades = [t for t in resolved_trades if t["scenario"] == scenario]
        
        if len(scenario_trades) < self.MINIMUM_SAMPLE_SIZE:
            return {
                "scenario": scenario,
                "degradation_detected": False,
                "reason": "INSUFFICIENT_SAMPLE_SIZE",
                "sample_size": len(scenario_trades),
                "required_size": self.MINIMUM_SAMPLE_SIZE
            }
        
        # Calculate accuracy
        accuracy_data = self.calculate_scenario_accuracy(scenario)
        accuracy = accuracy_data["accuracy"]
        
        if accuracy < self.EDGE_DEGRADATION_THRESHOLD:
            return {
                "scenario": scenario,
                "degradation_detected": True,
                "reason": "LOW_ACCURACY",
                "accuracy": accuracy,
                "threshold": self.EDGE_DEGRADATION_THRESHOLD,
                "sample_size": len(scenario_trades),
                "recommendation": "Review Phase-6A weights for this scenario"
            }
        
        return {
            "scenario": scenario,
            "degradation_detected": False,
            "reason": "EDGE_VALID",
            "accuracy": accuracy,
            "sample_size": len(scenario_trades)
        }
    
    def detect_overconfidence_bias(self) -> Dict[str, Any]:
        """
        Detect overconfidence bias.
        
        High probability trades failing disproportionately = overconfidence.
        
        Returns:
            Dictionary with overconfidence analysis
        """
        resolved_trades = self.store.get_resolved_trades()
        
        if not resolved_trades:
            return {
                "overconfidence_detected": False,
                "reason": "NO_DATA"
            }
        
        # Split into high-prob (>0.60) and low-prob (<=0.60) trades
        high_prob = [t for t in resolved_trades if t["probability"] > 0.60]
        low_prob = [t for t in resolved_trades if t["probability"] <= 0.60]
        
        if not high_prob or not low_prob:
            return {
                "overconfidence_detected": False,
                "reason": "INSUFFICIENT_SEGMENTATION"
            }
        
        # Calculate failure rates
        high_prob_failures = sum(1 for t in high_prob if t["structure_respected"] == 0)
        low_prob_failures = sum(1 for t in low_prob if t["structure_respected"] == 0)
        
        high_prob_failure_rate = high_prob_failures / len(high_prob)
        low_prob_failure_rate = low_prob_failures / len(low_prob)
        
        # Overconfidence = high-prob trades fail MORE than low-prob
        if high_prob_failure_rate > low_prob_failure_rate * 1.2:
            return {
                "overconfidence_detected": True,
                "reason": "HIGH_PROB_TRADES_FAIL_MORE",
                "high_prob_failure_rate": high_prob_failure_rate,
                "low_prob_failure_rate": low_prob_failure_rate,
                "high_prob_count": len(high_prob),
                "low_prob_count": len(low_prob),
                "recommendation": "Reduce overconfidence cap in Phase-7A Gate-5"
            }
        
        return {
            "overconfidence_detected": False,
            "reason": "NO_BIAS_DETECTED",
            "high_prob_failure_rate": high_prob_failure_rate,
            "low_prob_failure_rate": low_prob_failure_rate
        }
    
    def detect_regime_shift(self) -> Dict[str, Any]:
        """
        Detect market regime shift.
        
        Scenario C frequency > baseline + threshold = regime change.
        
        Returns:
            Dictionary with regime shift analysis
        """
        resolved_trades = self.store.get_resolved_trades()
        
        if not resolved_trades:
            return {
                "regime_shift_detected": False,
                "reason": "NO_DATA"
            }
        
        # Count scenario distribution
        scenario_counts = {"A": 0, "B": 0, "C": 0}
        for trade in resolved_trades:
            scenario = trade["resolved_scenario"]
            if scenario in scenario_counts:
                scenario_counts[scenario] += 1
        
        # Calculate Scenario C frequency
        c_frequency = scenario_counts["C"] / len(resolved_trades)
        
        # Baseline: Scenario C should be ~20-25% in normal markets
        baseline_c_frequency = 0.25
        
        # Regime shift if C frequency > 1.5× baseline
        threshold = baseline_c_frequency * self.REGIME_SHIFT_MULTIPLIER
        
        if c_frequency > threshold:
            return {
                "regime_shift_detected": True,
                "reason": "HIGH_SCENARIO_C_FREQUENCY",
                "scenario_c_frequency": c_frequency,
                "baseline": baseline_c_frequency,
                "threshold": threshold,
                "scenario_distribution": scenario_counts,
                "recommendation": "Market may be in high-volatility regime. Consider reducing position sizes."
            }
        
        return {
            "regime_shift_detected": False,
            "reason": "NORMAL_DISTRIBUTION",
            "scenario_c_frequency": c_frequency,
            "baseline": baseline_c_frequency,
            "threshold": threshold,
            "scenario_distribution": scenario_counts
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive expectancy report.
        
        Returns:
            Dictionary with all metrics
        """
        # Scenario accuracies
        scenario_a = self.calculate_scenario_accuracy("A")
        scenario_b = self.calculate_scenario_accuracy("B")
        scenario_c = self.calculate_scenario_accuracy("C")
        
        # Conditional accuracies
        full_alignment = self.calculate_conditional_accuracy("FULL ALIGNMENT")
        
        # Expectancy
        expectancy = self.calculate_expectancy()
        
        # False positive rate
        false_positive_rate = self.calculate_false_positive_rate()
        structural_failure_rate = self.calculate_structural_failure_rate()
        
        # Edge degradation
        edge_degradation_a = self.detect_edge_degradation("A")
        edge_degradation_b = self.detect_edge_degradation("B")
        edge_degradation_c = self.detect_edge_degradation("C")
        
        # Overconfidence bias
        overconfidence = self.detect_overconfidence_bias()
        
        # Regime shift
        regime_shift = self.detect_regime_shift()
        
        return {
            "scenario_accuracies": {
                "A": scenario_a,
                "B": scenario_b,
                "C": scenario_c
            },
            "conditional_accuracy": {
                "FULL_ALIGNMENT": full_alignment
            },
            "expectancy": expectancy,
            "false_positive_rate": false_positive_rate,
            "structural_failure_rate": structural_failure_rate,
            "edge_degradation": {
                "A": edge_degradation_a,
                "B": edge_degradation_b,
                "C": edge_degradation_c
            },
            "overconfidence_bias": overconfidence,
            "regime_shift": regime_shift
        }
    
    def __repr__(self) -> str:
        """String representation."""
        expectancy = self.calculate_expectancy()
        return (
            f"ExpectancyEngine("
            f"trades={expectancy['total_trades']}, "
            f"expectancy={expectancy['expectancy']:.2f}R, "
            f"win_rate={expectancy['win_rate']:.2%})"
        )
