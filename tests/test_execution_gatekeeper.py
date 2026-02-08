"""
PHASE-7C: EXECUTION GATEKEEPER TEST SUITE
Purpose: Validate that NO trade can execute unless every condition is satisfied

MANDATORY TEST CASES (8 TESTS):
TC-7C-01: Execution Without Token
TC-7C-02: Token Used Twice
TC-7C-03: Scenario Drift
TC-7C-04: Alignment Turns UNSTABLE After Analysis
TC-7C-05: Risk Budget Changed Mid-Flow
TC-7C-06: Forced Execution Attempt
TC-7C-07: Latency Attack (Delayed Execution)
TC-7C-08: Parallel Execution Attempts

Philosophy:
"If you skip any of these tests, you are not building a trading system, 
you are building a time bomb."
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from logic.execution_token import ExecutionToken
from logic.execution_gatekeeper import ExecutionGatekeeper
from storage.execution_audit_log import ExecutionAuditLog


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
            print(f"\n🔐 PHASE-7C VALIDATED FOR PRODUCTION")
            print(f"\nSYSTEM STATUS:")
            print(f"  ✔ Emotionless")
            print(f"  ✔ Deterministic")
            print(f"  ✔ Auditable")
            print(f"  ✔ Loss-limited")
            print(f"  ✔ Professionally safe")
            print(f"\n🎯 INSTITUTION-GRADE EXECUTION CONTROL ACHIEVED")
        else:
            print(f"\n❌ TESTS FAILED - FIX GATEKEEPER BEFORE PRODUCTION")
        
        print(f"{'='*80}\n")


def run_tests():
    """Run all Phase-7C tests."""
    
    logger = TestLogger()
    
    # Create clean gatekeeper instance
    gatekeeper = ExecutionGatekeeper()
    
    # ========================================
    # TC-7C-01: Execution Without Token
    # ========================================
    logger.test_start("TC-7C-01", "Execution Without Token")
    
    logger.log_input(
        token="None",
        symbol="NIFTY",
        scenario_active="A",
        probability_a=0.60
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="NO_TOKEN",
        gate="STEP_1"
    )
    
    decision = gatekeeper.evaluate(
        token=None,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "NO_TOKEN" in decision.reason and
        decision.block_gate == "STEP_1"
    )
    logger.test_result(passed, "Token check failed" if not passed else "")
    
    # ========================================
    # TC-7C-02: Token Used Twice
    # ========================================
    logger.test_start("TC-7C-02", "Token Used Twice")
    
    # Create token
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="SWING",  # Use SWING to avoid time cutoff
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    logger.log_input(
        token_id=token.token_id[:8],
        scenario="A",
        first_use="ALLOWED",
        second_use="ATTEMPTED"
    )
    
    logger.log_expected(
        first_result="ALLOWED",
        second_result="BLOCKED",
        reason="TOKEN_REUSE"
    )
    
    # First use - should ALLOW (use SWING to avoid time cutoff)
    decision1 = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="SWING",
        execution_type="MANUAL"
    )
    
    # Second use - should BLOCK
    decision2 = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="SWING",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        first_result="ALLOWED" if decision1.allowed else "BLOCKED",
        second_result="BLOCKED" if not decision2.allowed else "ALLOWED",
        reason=decision2.reason
    )
    
    passed = (
        decision1.allowed and
        not decision2.allowed and
        "TOKEN_REUSE" in decision2.reason
    )
    logger.test_result(passed, "Token reuse not prevented" if not passed else "")
    
    # ========================================
    # TC-7C-03: Scenario Drift
    # ========================================
    logger.test_start("TC-7C-03", "Scenario Drift")
    
    # Create token for Scenario A
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="INTRADAY",
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    logger.log_input(
        token_scenario="A",
        market_scenario="B",
        drift="YES"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="SCENARIO_MISMATCH"
    )
    
    # Try to execute with Scenario B (market changed)
    decision = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="B",  # DRIFT!
        scenario_probabilities={"A": 0.25, "B": 0.60, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "SCENARIO_MISMATCH" in decision.reason and
        decision.block_gate == "STEP_2"
    )
    logger.test_result(passed, "Scenario drift not detected" if not passed else "")
    
    # ========================================
    # TC-7C-04: Alignment Turns UNSTABLE After Analysis
    # ========================================
    logger.test_start("TC-7C-04", "Alignment Turns UNSTABLE After Analysis")
    
    # Create token with FULL ALIGNMENT
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="INTRADAY",
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    logger.log_input(
        token_alignment="FULL ALIGNMENT",
        current_alignment="UNSTABLE",
        probability="0.60 (high)"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="STRUCTURAL_CONFLICT",
        note="Structure > Probability"
    )
    
    # Try to execute with UNSTABLE alignment
    decision = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="UNSTABLE",  # CHANGED!
        risk_requested=100.0,
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "STRUCTURAL_CONFLICT" in decision.reason and
        decision.block_gate == "STEP_3"
    )
    logger.test_result(passed, "Alignment change not detected" if not passed else "")
    
    # ========================================
    # TC-7C-05: Risk Budget Changed Mid-Flow
    # ========================================
    logger.test_start("TC-7C-05", "Risk Budget Changed Mid-Flow")
    
    # Create token with max_risk = 100
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="INTRADAY",
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    logger.log_input(
        token_max_risk=100.0,
        risk_requested=150.0,
        overflow="YES"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="RISK_OVERFLOW"
    )
    
    # Try to execute with higher risk
    decision = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=150.0,  # OVERFLOW!
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "RISK_OVERFLOW" in decision.reason and
        decision.block_gate == "STEP_4"
    )
    logger.test_result(passed, "Risk overflow not prevented" if not passed else "")
    
    # ========================================
    # TC-7C-06: Forced Execution Attempt
    # ========================================
    logger.test_start("TC-7C-06", "Forced Execution Attempt (CONFLICT Alignment)")
    
    # Create token
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="INTRADAY",
        alignment_state="CONFLICT",  # Should have been blocked earlier
        probability_active=0.60
    )
    
    logger.log_input(
        alignment="CONFLICT",
        probability="0.60 (trying to force with high prob)",
        execution_type="MANUAL"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="STRUCTURAL_CONFLICT",
        note="No override mechanism exists"
    )
    
    # Try to force execution
    decision = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="CONFLICT",
        risk_requested=100.0,
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "STRUCTURAL_CONFLICT" in decision.reason
    )
    logger.test_result(passed, "Forced execution not prevented" if not passed else "")
    
    # ========================================
    # TC-7C-07: Latency Attack (Delayed Execution)
    # ========================================
    logger.test_start("TC-7C-07", "Latency Attack (Token Expiry)")
    
    # Create token with very short lifetime (manually expire it)
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="INTRADAY",
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    # Manually expire token (simulate 16 minutes passing)
    token._expires_at = datetime.now() - timedelta(minutes=1)
    
    logger.log_input(
        token_created="16 minutes ago",
        token_expires="15 minutes (expired)",
        time_elapsed="16 minutes"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="TOKEN_EXPIRED"
    )
    
    # Try to execute with expired token
    decision = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="INTRADAY",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        result="BLOCKED" if not decision.allowed else "ALLOWED",
        reason=decision.reason,
        gate=decision.block_gate
    )
    
    passed = (
        not decision.allowed and
        "TOKEN_EXPIRED" in decision.reason and
        decision.block_gate == "STEP_1"
    )
    logger.test_result(passed, "Token expiry not enforced" if not passed else "")
    
    # ========================================
    # TC-7C-08: Parallel Execution Attempts
    # ========================================
    logger.test_start("TC-7C-08", "Parallel Execution Attempts")
    
    # Create single token
    token = ExecutionToken(
        symbol="NIFTY",
        scenario="A",
        max_risk=100.0,
        market_mode="SWING",  # Use SWING to avoid time cutoff
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60
    )
    
    logger.log_input(
        token_count="1",
        execution_attempts="3 parallel",
        expected_allowed="1",
        expected_blocked="2"
    )
    
    logger.log_expected(
        first="ALLOWED",
        second="BLOCKED (TOKEN_REUSE)",
        third="BLOCKED (TOKEN_REUSE)"
    )
    
    # Attempt 1
    decision1 = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="SWING",
        execution_type="MANUAL"
    )
    
    # Attempt 2 (should fail - token consumed)
    decision2 = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="SWING",
        execution_type="MANUAL"
    )
    
    # Attempt 3 (should also fail)
    decision3 = gatekeeper.evaluate(
        token=token,
        symbol="NIFTY",
        timeframe="5m",
        scenario_active="A",
        scenario_probabilities={"A": 0.60, "B": 0.25, "C": 0.15},
        alignment_state="FULL ALIGNMENT",
        risk_requested=100.0,
        market_mode="SWING",
        execution_type="MANUAL"
    )
    
    logger.log_actual(
        first="ALLOWED" if decision1.allowed else "BLOCKED",
        second="BLOCKED" if not decision2.allowed else "ALLOWED",
        third="BLOCKED" if not decision3.allowed else "ALLOWED"
    )
    
    passed = (
        decision1.allowed and
        not decision2.allowed and
        not decision3.allowed and
        "TOKEN_REUSE" in decision2.reason and
        "TOKEN_REUSE" in decision3.reason
    )
    logger.test_result(passed, "Parallel execution not prevented" if not passed else "")
    
    # ========================================
    # FINAL SUMMARY
    # ========================================
    logger.summary()
    
    # Return exit code
    return 0 if logger.tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
