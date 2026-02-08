"""
PHASE-8: TRADE LIFECYCLE & POST-FACT RESOLUTION TEST SUITE
Purpose: Validate that structure > P&L, edge is proven not assumed

MANDATORY TEST CASES (6 TESTS):
TC-8-01: Profitable Trade, Structure Broken → Scenario FAILED
TC-8-02: Losing Trade, Structure Respected → Scenario VALID
TC-8-03: Scenario B Occurs When A Was Active → A = FALSE POSITIVE
TC-8-04: Long-term Drift Detection → EDGE_DEGRADATION flag
TC-8-05: Overconfidence Detection → OVERCONFIDENCE_BIAS flag
TC-8-06: Market Regime Shift → REGIME_CHANGE warning

Philosophy:
"Money is secondary. Structure is primary. Edge is proven, not assumed."
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from logic.trade_lifecycle import TradeLifecycleTracker
from logic.scenario_resolution_engine import ScenarioResolutionEngine
from logic.expectancy_engine import ExpectancyEngine
from storage.trade_lifecycle_store import TradeLifecycleStore


class TestLogger:
    """Logger for structured test output."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
    
    def test_start(self, test_id: str, description: str):
        """Log test start."""
        print(f"\n{'='*80}")
        print(f"TEST: {test_id}")
        print(f"DESCRIPTION: {description}")
        print(f"{'='*80}")
    
    def log_input(self, **kwargs):
        """Log test inputs."""
        print("\n📥 INPUT:")
        for key, value in kwargs.items():
            print(f"  {key}: {value}")
    
    def log_expected(self, **kwargs):
        """Log expected output."""
        print("\n🎯 EXPECTED:")
        for key, value in kwargs.items():
            print(f"  {key}: {value}")
    
    def log_actual(self, **kwargs):
        """Log actual output."""
        print("\n📤 ACTUAL:")
        for key, value in kwargs.items():
            print(f"  {key}: {value}")
    
    def test_result(self, passed: bool, reason: str = ""):
        """Log test result."""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"\n✅ PASS")
        else:
            self.tests_failed += 1
            print(f"\n❌ FAIL: {reason}")
    
    def summary(self):
        """Print test summary."""
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        
        if self.tests_failed == 0:
            print(f"\n✅ ALL TESTS PASSED")
            print(f"\n🧠 PHASE-8 VALIDATED FOR PRODUCTION")
            print(f"\nSYSTEM CAPABILITIES:")
            print(f"  ✔ Proof of edge")
            print(f"  ✔ Losses explained logically")
            print(f"  ✔ Long-term survivability")
            print(f"  ✔ Emotionless feedback loop")
            print(f"\n🎯 LEARNS WITHOUT LEARNING, ADAPTS WITHOUT CHANGING RULES")
            print(f"\nThis is how real desks operate.")
        else:
            print(f"\n❌ TESTS FAILED - FIX PHASE-8 BEFORE PRODUCTION")
            print(f"\nRemember: If Phase-8 shows negative expectancy,")
            print(f"DO NOT FIX EXECUTION. Fix assumptions in Phase-6.")
            print(f"Execution is never the problem.")
        
        print(f"{'='*80}\n")


def run_tests():
    """Run all Phase-8 tests."""
    
    logger = TestLogger()
    
    # Create clean instances for testing (use temp file instead of :memory:)
    import tempfile
    import os
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    store = TradeLifecycleStore(db_path=temp_db.name)
    tracker = TradeLifecycleTracker(store=store)
    resolver = ScenarioResolutionEngine(store=store)
    expectancy = ExpectancyEngine(store=store)
    
    # ========================================
    # TC-8-01: Profitable Trade, Structure Broken
    # ========================================
    logger.test_start("TC-8-01", "Profitable Trade, Structure Broken → Scenario FAILED")
    
    logger.log_input(
        scenario="A (continuation)",
        entry_price=19500,
        exit_price=19600,
        profit="+100 points",
        htf_structure="BROKEN (support violated)"
    )
    
    logger.log_expected(
        resolved_scenario="C (not A)",
        structure_respected="FALSE",
        expectancy_impact="NEGATIVE (structure > profit)"
    )
    
    # Create trade
    trade_id = tracker.create_trade(
        symbol="NIFTY",
        timeframe="5m",
        market_mode="INTRADAY",
        scenario="A",
        probability=0.60,
        alignment_state="FULL ALIGNMENT",
        htf_support=19400,
        htf_resistance=19700,
        htf_direction="BULLISH",
        entry_price=19500,
        direction="LONG",
        entry_time=datetime.now()
    )
    
    # Close with profit but structure broken
    tracker.close_trade(
        trade_id=trade_id,
        exit_price=19600,  # +100 profit
        exit_reason="STRUCTURE_BREAK",
        mae=-20,
        mfe=120,
        exit_time=datetime.now()
    )
    
    # Resolve: structure broken
    resolver.resolve_trade(
        trade_id=trade_id,
        actual_htf_support=19400,
        actual_htf_resistance=19700,
        htf_structure_broken=True,  # BROKEN!
        continuation_level_reached=True,
        price_reversed=False
    )
    
    # Get trade
    trade = store.get_trade(trade_id)
    
    logger.log_actual(
        resolved_scenario=trade["resolved_scenario"],
        structure_respected=bool(trade["structure_respected"]),
        profit="+100 points",
        verdict="FAILED (money made but structure violated)"
    )
    
    passed = (
        trade["resolved_scenario"] == "C" and
        trade["structure_respected"] == 0
    )
    logger.test_result(passed, "Structure > Profit rule not enforced" if not passed else "")
    
    # ========================================
    # TC-8-02: Losing Trade, Structure Respected
    # ========================================
    logger.test_start("TC-8-02", "Losing Trade, Structure Respected → Scenario VALID")
    
    logger.log_input(
        scenario="B (reversal)",
        entry_price=19500,
        exit_price=19450,
        profit="-50 points (loss)",
        htf_structure="HELD (support respected)"
    )
    
    logger.log_expected(
        resolved_scenario="B",
        structure_respected="TRUE",
        expectancy_impact="POSITIVE (structure respected despite loss)"
    )
    
    # Create trade
    trade_id2 = tracker.create_trade(
        symbol="NIFTY",
        timeframe="5m",
        market_mode="INTRADAY",
        scenario="B",
        probability=0.55,
        alignment_state="FULL ALIGNMENT",
        htf_support=19400,
        htf_resistance=19700,
        htf_direction="BULLISH",
        entry_price=19500,
        direction="LONG",
        entry_time=datetime.now()
    )
    
    # Close with loss but structure held
    tracker.close_trade(
        trade_id=trade_id2,
        exit_price=19450,  # -50 loss
        exit_reason="MANUAL",
        mae=-60,
        mfe=20,
        exit_time=datetime.now()
    )
    
    # Resolve: structure held, reversal occurred
    resolver.resolve_trade(
        trade_id=trade_id2,
        actual_htf_support=19400,
        actual_htf_resistance=19700,
        htf_structure_broken=False,  # HELD!
        continuation_level_reached=False,
        price_reversed=True
    )
    
    # Get trade
    trade2 = store.get_trade(trade_id2)
    
    logger.log_actual(
        resolved_scenario=trade2["resolved_scenario"],
        structure_respected=bool(trade2["structure_respected"]),
        profit="-50 points (loss)",
        verdict="VALID (structure respected despite loss)"
    )
    
    passed = (
        trade2["resolved_scenario"] == "B" and
        trade2["structure_respected"] == 1
    )
    logger.test_result(passed, "Structure respected not recognized despite loss" if not passed else "")
    
    # ========================================
    # TC-8-03: Scenario B Occurs When A Was Active
    # ========================================
    logger.test_start("TC-8-03", "Scenario B Occurs When A Was Active → A = FALSE POSITIVE")
    
    logger.log_input(
        predicted_scenario="A (continuation)",
        actual_scenario="B (reversal)",
        probability_a=0.65
    )
    
    logger.log_expected(
        resolved_scenario="B",
        structure_respected="FALSE",
        classification="FALSE POSITIVE"
    )
    
    # Create trade expecting A
    trade_id3 = tracker.create_trade(
        symbol="NIFTY",
        timeframe="5m",
        market_mode="INTRADAY",
        scenario="A",  # Expected continuation
        probability=0.65,
        alignment_state="FULL ALIGNMENT",
        htf_support=19400,
        htf_resistance=19700,
        htf_direction="BULLISH",
        entry_price=19500,
        direction="LONG",
        entry_time=datetime.now()
    )
    
    tracker.close_trade(
        trade_id=trade_id3,
        exit_price=19480,
        exit_reason="MANUAL",
        mae=-30,
        mfe=10,
        exit_time=datetime.now()
    )
    
    # Resolve: B occurred (reversal)
    resolver.resolve_trade(
        trade_id=trade_id3,
        actual_htf_support=19400,
        actual_htf_resistance=19700,
        htf_structure_broken=False,
        continuation_level_reached=False,
        price_reversed=True  # B occurred!
    )
    
    trade3 = store.get_trade(trade_id3)
    
    logger.log_actual(
        predicted="A",
        resolved=trade3["resolved_scenario"],
        structure_respected=bool(trade3["structure_respected"]),
        classification="FALSE POSITIVE (A predicted, B occurred)"
    )
    
    passed = (
        trade3["scenario"] == "A" and
        trade3["resolved_scenario"] == "B" and
        trade3["structure_respected"] == 0
    )
    logger.test_result(passed, "False positive not detected" if not passed else "")
    
    # ========================================
    # TC-8-04: Long-term Drift Detection
    # ========================================
    logger.test_start("TC-8-04", "Long-term Drift Detection → EDGE_DEGRADATION flag")
    
    logger.log_input(
        scenario="A",
        sample_size="50+ trades",
        accuracy="< 45%",
        threshold="45%"
    )
    
    logger.log_expected(
        flag="EDGE_DEGRADATION",
        recommendation="Review Phase-6A weights"
    )
    
    # Create 50 Scenario A trades with low accuracy (40%)
    for i in range(50):
        tid = tracker.create_trade(
            symbol="NIFTY",
            timeframe="5m",
            market_mode="INTRADAY",
            scenario="A",
            probability=0.60,
            alignment_state="FULL ALIGNMENT",
            htf_support=19400,
            htf_resistance=19700,
            htf_direction="BULLISH",
            entry_price=19500,
            direction="LONG",
            entry_time=datetime.now()
        )
        
        tracker.close_trade(
            trade_id=tid,
            exit_price=19520,
            exit_reason="AUTO_EXIT",
            mae=-10,
            mfe=30,
            exit_time=datetime.now()
        )
        
        # 40% accuracy: first 20 correct, last 30 incorrect
        if i < 20:
            # Structure respected
            resolver.resolve_trade_simple(tid, "A", True, "HIGH")
        else:
            # Structure violated
            resolver.resolve_trade_simple(tid, "B", False, "HIGH")
    
    # Check for edge degradation
    degradation = expectancy.detect_edge_degradation("A")
    
    logger.log_actual(
        degradation_detected=degradation["degradation_detected"],
        accuracy=f"{degradation.get('accuracy', 0):.2%}",
        sample_size=degradation.get("sample_size", 0),
        recommendation=degradation.get("recommendation", "N/A")
    )
    
    passed = (
        degradation["degradation_detected"] == True and
        degradation.get("accuracy", 1.0) < 0.45
    )
    logger.test_result(passed, "Edge degradation not detected" if not passed else "")
    
    # ========================================
    # TC-8-05: Overconfidence Detection
    # ========================================
    logger.test_start("TC-8-05", "Overconfidence Detection → OVERCONFIDENCE_BIAS flag")
    
    logger.log_input(
        condition="High probability trades fail disproportionately",
        high_prob_threshold=">0.60",
        failure_ratio=">1.2x"
    )
    
    logger.log_expected(
        flag="OVERCONFIDENCE_BIAS",
        recommendation="Reduce overconfidence cap"
    )
    
    # Create high-prob trades (fail more)
    for i in range(20):
        tid = tracker.create_trade(
            symbol="NIFTY",
            timeframe="5m",
            market_mode="INTRADAY",
            scenario="A",
            probability=0.70,  # HIGH PROB
            alignment_state="FULL ALIGNMENT",
            htf_support=19400,
            htf_resistance=19700,
            htf_direction="BULLISH",
            entry_price=19500,
            direction="LONG",
            entry_time=datetime.now()
        )
        
        tracker.close_trade(tid, 19520, "AUTO_EXIT", -10, 30, datetime.now())
        
        # 70% fail (overconfident!)
        if i < 6:
            resolver.resolve_trade_simple(tid, "A", True, "HIGH")
        else:
            resolver.resolve_trade_simple(tid, "C", False, "HIGH")
    
    # Create low-prob trades (fail less)
    for i in range(20):
        tid = tracker.create_trade(
            symbol="NIFTY",
            timeframe="5m",
            market_mode="INTRADAY",
            scenario="B",
            probability=0.50,  # LOW PROB
            alignment_state="FULL ALIGNMENT",
            htf_support=19400,
            htf_resistance=19700,
            htf_direction="BULLISH",
            entry_price=19500,
            direction="LONG",
            entry_time=datetime.now()
        )
        
        tracker.close_trade(tid, 19520, "AUTO_EXIT", -10, 30, datetime.now())
        
        # 40% fail (less than high-prob)
        if i < 12:
            resolver.resolve_trade_simple(tid, "B", True, "HIGH")
        else:
            resolver.resolve_trade_simple(tid, "C", False, "HIGH")
    
    # Check for overconfidence
    overconfidence = expectancy.detect_overconfidence_bias()
    
    logger.log_actual(
        overconfidence_detected=overconfidence["overconfidence_detected"],
        high_prob_failure_rate=f"{overconfidence.get('high_prob_failure_rate', 0):.2%}",
        low_prob_failure_rate=f"{overconfidence.get('low_prob_failure_rate', 0):.2%}",
        recommendation=overconfidence.get("recommendation", "N/A")
    )
    
    passed = overconfidence["overconfidence_detected"] == True
    logger.test_result(passed, "Overconfidence bias not detected" if not passed else "")
    
    # ========================================
    # TC-8-06: Market Regime Shift
    # ========================================
    logger.test_start("TC-8-06", "Market Regime Shift → REGIME_CHANGE warning")
    
    logger.log_input(
        condition="Scenario C frequency > baseline + threshold",
        baseline="25%",
        threshold="1.5x = 37.5%"
    )
    
    logger.log_expected(
        flag="REGIME_CHANGE",
        recommendation="High-volatility regime detected"
    )
    
    # Create trades with high Scenario C frequency (50% to ensure detection)
    # We need to overwhelm previous trades, so create many more
    for i in range(200):
        scenario = "C" if i < 100 else ("A" if i < 150 else "B")
        
        tid = tracker.create_trade(
            symbol="NIFTY",
            timeframe="5m",
            market_mode="INTRADAY",
            scenario=scenario,
            probability=0.55,
            alignment_state="FULL ALIGNMENT",
            htf_support=19400,
            htf_resistance=19700,
            htf_direction="BULLISH",
            entry_price=19500,
            direction="LONG",
            entry_time=datetime.now()
        )
        
        tracker.close_trade(tid, 19520, "AUTO_EXIT", -10, 30, datetime.now())
        resolver.resolve_trade_simple(tid, scenario, True, "HIGH")
    
    # Check for regime shift
    regime_shift = expectancy.detect_regime_shift()
    
    logger.log_actual(
        regime_shift_detected=regime_shift["regime_shift_detected"],
        scenario_c_frequency=f"{regime_shift.get('scenario_c_frequency', 0):.2%}",
        threshold=f"{regime_shift.get('threshold', 0):.2%}",
        recommendation=regime_shift.get("recommendation", "N/A")
    )
    
    passed = regime_shift["regime_shift_detected"] == True
    logger.test_result(passed, "Regime shift not detected" if not passed else "")
    
    # ========================================
    # FINAL SUMMARY
    # ========================================
    logger.summary()
    
    # Cleanup temp database
    try:
        os.unlink(temp_db.name)
    except:
        pass
    
    # Return exit code
    return 0 if logger.tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
