"""
PHASE-9: EXECUTION AUTHORIZATION & HUMAN-INTENT LAYER TEST SUITE
Purpose: Validate that human remains sovereign, automation is optional

MANDATORY TEST CASES (6 TESTS):
TC-9-01: Positive Edge, No Consent → BLOCKED
TC-9-02: Consent Given, Edge Negative → BLOCKED
TC-9-03: Assisted Mode → No Confirmation → NO ORDER
TC-9-04: AUTO mode + REGIME_CHANGE → DOWNGRADED TO ASSISTED
TC-9-05: API Failure Mid-Decision → SAFE ABORT
TC-9-06: Repeated Rapid Requests → THROTTLE + ALERT

Philosophy:
"Phase-9 does not add intelligence. It adds permission.
Human remains sovereign. Automation is optional, not default."
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from logic.intent_classifier import IntentClassifier, UserIntent
from logic.execution_permission_engine import ExecutionPermissionEngine, ExecutionMode
from logic.human_confirmation_protocol import HumanConfirmationProtocol
from logic.execution_firewall import ExecutionFirewall


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
            print(f"\n🔐 PHASE-9 VALIDATED FOR PRODUCTION")
            print(f"\nSYSTEM CAPABILITIES:")
            print(f"  ✔ Human remains sovereign")
            print(f"  ✔ Automation is optional, not default")
            print(f"  ✔ Legal & ethical safety")
            print(f"  ✔ Zero surprise trades")
            print(f"  ✔ Institutional-grade control flow")
            print(f"\n🎯 THIS IS HOW REAL DESKS ALLOW MACHINES TO ACT")
        else:
            print(f"\n❌ TESTS FAILED - FIX PHASE-9 BEFORE PRODUCTION")
            print(f"\n⚠️  This phase is dangerous if done wrong")
            print(f"⚠️  This is where retail systems turn into gambling bots")
            print(f"⚠️  We will NOT cross any line until guardrails are absolute")
        
        print(f"{'='*80}\n")


def run_tests():
    """Run all Phase-9 tests."""
    
    logger = TestLogger()
    
    # Create clean instances
    intent_classifier = IntentClassifier()
    permission_engine = ExecutionPermissionEngine()
    confirmation_protocol = HumanConfirmationProtocol()
    firewall = ExecutionFirewall()
    
    # ========================================
    # TC-9-01: Positive Edge, No Consent
    # ========================================
    logger.test_start("TC-9-01", "Positive Edge, No Consent → BLOCKED")
    
    logger.log_input(
        mode="AUTO",
        expectancy="+0.42R (positive)",
        alignment="FULL ALIGNMENT",
        probability="0.60",
        risk_allowed="TRUE",
        regime_warning="FALSE",
        explicit_consent="FALSE"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="GATE_6_FAILED: No explicit consent",
        blocked_gate="GATE_6_USER_CONSENT"
    )
    
    # Evaluate permission
    permission = permission_engine.evaluate_permission_simple(
        mode="AUTO",
        expectancy=0.42,
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60,
        risk_allowed=True,
        regime_warning=False,
        explicit_consent=False  # NO CONSENT
    )
    
    logger.log_actual(
        result="BLOCKED" if not permission.allowed else "ALLOWED",
        reason=permission.reason,
        blocked_gate=permission.blocked_gate,
        mode=permission.mode.value
    )
    
    passed = (
        not permission.allowed and
        "GATE_6" in permission.reason and
        "consent" in permission.reason.lower()
    )
    logger.test_result(passed, "Consent requirement not enforced" if not passed else "")
    
    # ========================================
    # TC-9-02: Consent Given, Edge Negative
    # ========================================
    logger.test_start("TC-9-02", "Consent Given, Edge Negative → BLOCKED")
    
    logger.log_input(
        mode="AUTO",
        expectancy="-0.15R (negative)",
        alignment="FULL ALIGNMENT",
        probability="0.60",
        risk_allowed="TRUE",
        regime_warning="FALSE",
        explicit_consent="TRUE"
    )
    
    logger.log_expected(
        result="BLOCKED",
        reason="GATE_1_FAILED: No proven edge",
        blocked_gate="GATE_1_EDGE"
    )
    
    # Evaluate permission
    permission = permission_engine.evaluate_permission_simple(
        mode="AUTO",
        expectancy=-0.15,  # NEGATIVE
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60,
        risk_allowed=True,
        regime_warning=False,
        explicit_consent=True
    )
    
    logger.log_actual(
        result="BLOCKED" if not permission.allowed else "ALLOWED",
        reason=permission.reason,
        blocked_gate=permission.blocked_gate,
        mode=permission.mode.value
    )
    
    passed = (
        not permission.allowed and
        "GATE_1" in permission.reason and
        "expectancy" in permission.reason.lower()
    )
    logger.test_result(passed, "Negative edge not blocked" if not passed else "")
    
    # ========================================
    # TC-9-03: Assisted Mode → No Confirmation
    # ========================================
    logger.test_start("TC-9-03", "Assisted Mode, No Confirmation → NO ORDER")
    
    logger.log_input(
        mode="ASSISTED",
        confirmation_required="TRUE",
        confirmation_received="FALSE"
    )
    
    logger.log_expected(
        permission_result="REQUIRES_CONFIRMATION",
        firewall_result="BLOCKED",
        reason="CONFIRMATION_MISSING"
    )
    
    # Evaluate permission (ASSISTED always requires confirmation)
    permission = permission_engine.evaluate_permission_simple(
        mode="ASSISTED",
        expectancy=0.42,
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60,
        risk_allowed=True,
        regime_warning=False,
        explicit_consent=True
    )
    
    # Check firewall (confirmation not received)
    firewall_result = firewall.check(
        overconfidence_flag=False,
        expectancy_resolved=True,
        expectancy_value=0.42,
        confirmation_required=True,
        confirmation_received=False,  # NO CONFIRMATION
        api_healthy=True,
        latency_ms=100
    )
    
    logger.log_actual(
        permission_requires_confirmation=permission.requires_confirmation,
        firewall_passed=firewall_result.passed,
        firewall_reason=firewall_result.reason,
        blocked_category=firewall_result.blocked_category
    )
    
    passed = (
        permission.requires_confirmation and
        not firewall_result.passed and
        "CONFIRMATION" in firewall_result.reason
    )
    logger.test_result(passed, "Confirmation requirement not enforced" if not passed else "")
    
    # ========================================
    # TC-9-04: AUTO mode + REGIME_CHANGE
    # ========================================
    logger.test_start("TC-9-04", "AUTO Mode + REGIME_CHANGE → DOWNGRADED TO ASSISTED")
    
    logger.log_input(
        mode="AUTO",
        expectancy="+0.42R",
        alignment="FULL ALIGNMENT",
        probability="0.60",
        risk_allowed="TRUE",
        regime_warning="TRUE (regime shift detected)",
        explicit_consent="TRUE"
    )
    
    logger.log_expected(
        result="DOWNGRADED",
        mode="ASSISTED",
        reason="GATE_5_FAILED: Regime shift → ASSISTED"
    )
    
    # Evaluate permission
    permission = permission_engine.evaluate_permission_simple(
        mode="AUTO",
        expectancy=0.42,
        alignment_state="FULL ALIGNMENT",
        probability_active=0.60,
        risk_allowed=True,
        regime_warning=True,  # REGIME SHIFT!
        explicit_consent=True
    )
    
    logger.log_actual(
        result="DOWNGRADED" if permission.mode == ExecutionMode.ASSISTED else "NOT_DOWNGRADED",
        mode=permission.mode.value,
        reason=permission.reason,
        requires_confirmation=permission.requires_confirmation
    )
    
    passed = (
        permission.mode == ExecutionMode.ASSISTED and
        permission.requires_confirmation and
        "GATE_5" in permission.reason
    )
    logger.test_result(passed, "Regime shift downgrade not triggered" if not passed else "")
    
    # ========================================
    # TC-9-05: API Failure Mid-Decision
    # ========================================
    logger.test_start("TC-9-05", "API Failure Mid-Decision → SAFE ABORT")
    
    logger.log_input(
        expectancy="+0.42R",
        confirmation_required="FALSE",
        confirmation_received="FALSE",
        api_healthy="FALSE (connection failed)"
    )
    
    logger.log_expected(
        firewall_result="BLOCKED",
        reason="API_UNHEALTHY",
        blocked_category="API"
    )
    
    # Check firewall with API failure
    firewall_result = firewall.check(
        overconfidence_flag=False,
        expectancy_resolved=True,
        expectancy_value=0.42,
        confirmation_required=False,
        confirmation_received=False,
        api_healthy=False,  # API FAILURE!
        latency_ms=100
    )
    
    logger.log_actual(
        firewall_passed=firewall_result.passed,
        reason=firewall_result.reason,
        blocked_category=firewall_result.blocked_category
    )
    
    passed = (
        not firewall_result.passed and
        firewall_result.blocked_category == "API"
    )
    logger.test_result(passed, "API failure not caught" if not passed else "")
    
    # ========================================
    # TC-9-06: Repeated Rapid Requests
    # ========================================
    logger.test_start("TC-9-06", "Repeated Rapid Requests → THROTTLE + ALERT")
    
    logger.log_input(
        requests_per_minute=f">{firewall.MAX_REQUESTS_PER_MINUTE}",
        throttle_limit=firewall.MAX_REQUESTS_PER_MINUTE
    )
    
    logger.log_expected(
        firewall_result="BLOCKED",
        reason="THROTTLE_MINUTE",
        blocked_category="THROTTLE"
    )
    
    # Create new firewall for clean test
    firewall_throttle = ExecutionFirewall()
    
    # Simulate rapid requests (11 requests, limit is 10)
    results = []
    for i in range(11):
        result = firewall_throttle.check(
            overconfidence_flag=False,
            expectancy_resolved=True,
            expectancy_value=0.42,
            confirmation_required=False,
            confirmation_received=False,
            api_healthy=True,
            latency_ms=100
        )
        results.append(result)
    
    # Last request should be throttled
    last_result = results[-1]
    
    logger.log_actual(
        total_requests=11,
        first_10_passed=all(r.passed for r in results[:10]),
        last_request_passed=last_result.passed,
        reason=last_result.reason,
        blocked_category=last_result.blocked_category
    )
    
    passed = (
        all(r.passed for r in results[:10]) and
        not last_result.passed and
        last_result.blocked_category == "THROTTLE"
    )
    logger.test_result(passed, "Throttle limit not enforced" if not passed else "")
    
    # ========================================
    # FINAL SUMMARY
    # ========================================
    logger.summary()
    
    # Return exit code
    return 0 if logger.tests_failed == 0 else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
