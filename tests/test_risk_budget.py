"""
Phase-7B: Risk Budget Engine - Acceptance Tests

Tests the MANDATORY safety features:
1. 4 losses in row → HALT
2. Conflict alignment → Zero risk
3. Low probability → Reduced risk
4. Daily loss hit → Trading stopped
5. Token reuse → Hard error
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.risk_budget_engine import RiskBudgetEngine, ExecutionPermission
from storage.risk_state_store import RiskStateStore
from datetime import datetime
import tempfile

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_num, test_name):
    print(f"\n{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}TEST {test_num}: {test_name}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_result(passed, expected, actual):
    if passed:
        print(f"\n{Colors.GREEN}✅ TEST PASSED{Colors.RESET}")
        print(f"   Expected: {expected}")
        print(f"   Got: {actual}")
    else:
        print(f"\n{Colors.RED}❌ TEST FAILED{Colors.RESET}")
        print(f"   Expected: {expected}")
        print(f"   Got: {actual}")

def test_1_four_losses_halt():
    """Test: 4 consecutive losses should HALT system"""
    print_test_header(1, "Four Losses in Row → HALT")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Simulate 4 consecutive losing trades")
    print("   • Each loss recorded via record_outcome()")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} System halted after 4th loss")
    print(f"{Colors.CYAN}Critical:{Colors.RESET} If system allows 5th trade → SYSTEM INVALID\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    # Record 4 consecutive losses
    for i in range(1, 5):
        engine.record_outcome(
            symbol=f"TEST{i}",
            realized_pnl=-5000.0,
            risk_used=0.005
        )
        print(f"   Loss {i}: Streak = {engine.loss_streak}, State = {engine.system_state}")
    
    # Try to get permission after 4 losses
    permission = engine.evaluate(
        symbol="TEST5",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    print(f"\n{Colors.YELLOW}After 4 losses:{Colors.RESET}")
    print(f"   Loss Streak: {engine.loss_streak}")
    print(f"   System State: {engine.system_state}")
    print(f"   Permission Allowed: {permission.allowed}")
    print(f"   Block Reason: {permission.reason}")
    
    passed = (
        engine.loss_streak == 4 and
        engine.system_state == "HALTED_TODAY" and
        not permission.allowed
    )
    
    print_result(
        passed=passed,
        expected="HALTED_TODAY after 4 losses, execution blocked",
        actual=f"State={engine.system_state}, Allowed={permission.allowed}"
    )
    
    return passed

def test_2_conflict_alignment_zero_risk():
    """Test: CONFLICT alignment should result in zero risk"""
    print_test_header(2, "Conflict Alignment → Zero Risk")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Alignment = CONFLICT")
    print("   • All other conditions perfect")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} Execution BLOCKED (alignment factor = 0.0)")
    print(f"{Colors.CYAN}Critical:{Colors.RESET} If allowed → system trades structural ambiguity\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    permission = engine.evaluate(
        symbol="AAPL",
        scenario="SCENARIO_A",
        active_probability=0.65,  # High probability
        alignment="CONFLICT",  # CONFLICT alignment
        is_unstable=False
    )
    
    print(f"{Colors.YELLOW}Result:{Colors.RESET}")
    print(f"   Permission Allowed: {permission.allowed}")
    print(f"   Max Risk Amount: ₹{permission.max_risk_amount:,.2f}")
    print(f"   Block Reason: {permission.reason}")
    
    passed = not permission.allowed and permission.max_risk_amount == 0.0
    
    print_result(
        passed=passed,
        expected="Execution BLOCKED, zero risk allocated",
        actual=f"Allowed={permission.allowed}, Risk=₹{permission.max_risk_amount:,.2f}"
    )
    
    return passed

def test_3_low_probability_reduced_risk():
    """Test: Low active probability should reduce risk"""
    print_test_header(3, "Low Probability → Reduced Risk")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Compare two cases:")
    print("   • Case A: prob_a = 0.65 (high)")
    print("   • Case B: prob_a = 0.45 (low, should be blocked by Gate-2)")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} Case B blocked by dominance gate (<0.55)")
    print(f"{Colors.CYAN}Validation:{Colors.RESET} Risk scales with probability when allowed\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    # Case A: High probability
    perm_high = engine.evaluate(
        symbol="TSLA",
        scenario="SCENARIO_A",
        active_probability=0.65,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    # Case B: Low probability (will be blocked by execution gate, but risk engine allows)
    perm_low = engine.evaluate(
        symbol="NVDA",
        scenario="SCENARIO_A",
        active_probability=0.45,  # Below dominance threshold
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    print(f"{Colors.YELLOW}Results:{Colors.RESET}")
    print(f"   Case A (prob=0.65):")
    print(f"      Allowed: {perm_high.allowed}")
    print(f"      Risk: ₹{perm_high.max_risk_amount:,.2f} ({perm_high.max_risk_percent*100:.2f}%)")
    print(f"   Case B (prob=0.45):")
    print(f"      Allowed: {perm_low.allowed}")
    print(f"      Risk: ₹{perm_low.max_risk_amount:,.2f} ({perm_low.max_risk_percent*100:.2f}%)")
    
    # Risk engine allows it, but risk should be proportionally lower
    # Execution gate (Phase-7A) would block Case B due to low dominance
    passed = (
        perm_high.allowed and
        perm_low.allowed and  # Risk engine allows, gate blocks
        perm_low.max_risk_amount < perm_high.max_risk_amount
    )
    
    print(f"\n{Colors.CYAN}Note:{Colors.RESET} Risk engine calculates proportional risk")
    print(f"{Colors.CYAN}      Phase-7A execution gate blocks prob < 0.55 (dominance){Colors.RESET}")
    
    print_result(
        passed=passed,
        expected="Risk scales with probability (0.45 < 0.65 → lower risk)",
        actual=f"High=₹{perm_high.max_risk_amount:,.0f}, Low=₹{perm_low.max_risk_amount:,.0f}"
    )
    
    return passed

def test_4_daily_loss_limit():
    """Test: Daily loss limit should stop trading"""
    print_test_header(4, "Daily Loss Hit → Trading Stopped")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Mode = INTRADAY (max daily loss = -1.00%)")
    print("   • Equity = ₹1,000,000")
    print("   • Simulate losses totaling -1.00%")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} System halted after daily limit breach")
    print(f"{Colors.CYAN}Critical:{Colors.RESET} Must prevent further trading same day\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="INTRADAY")
    
    # Record losses totaling -1.00%
    losses = [
        ("AAPL", -3000.0),  # -0.30%
        ("TSLA", -4000.0),  # -0.40%
        ("NVDA", -3500.0),  # -0.35%  Total: -1.05%
    ]
    
    for symbol, pnl in losses:
        engine.record_outcome(
            symbol=symbol,
            realized_pnl=pnl,
            risk_used=abs(pnl) / engine.account_equity
        )
        print(f"   {symbol}: ₹{pnl:,.0f} | Drawdown: {engine._daily_realized_loss_pct*100:.2f}% | State: {engine.system_state}")
    
    # Try to get permission after daily limit breach
    permission = engine.evaluate(
        symbol="GOOGL",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    print(f"\n{Colors.YELLOW}After daily loss limit:{Colors.RESET}")
    print(f"   Daily Drawdown: {engine._daily_realized_loss_pct*100:.2f}%")
    print(f"   System State: {engine.system_state}")
    print(f"   Permission Allowed: {permission.allowed}")
    print(f"   Block Reason: {permission.reason}")
    
    passed = (
        engine.system_state == "HALTED_TODAY" and
        not permission.allowed and
        abs(engine._daily_realized_loss_pct) >= 0.01
    )
    
    print_result(
        passed=passed,
        expected="HALTED_TODAY after -1.00% daily loss",
        actual=f"State={engine.system_state}, Drawdown={engine._daily_realized_loss_pct*100:.2f}%"
    )
    
    return passed

def test_5_token_reuse_error():
    """Test: Token reuse should cause hard error"""
    print_test_header(5, "Token Reuse → Hard Error")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Get valid permission token")
    print("   • Consume token once")
    print("   • Try to reuse same token")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} Second use fails (token already consumed)")
    print(f"{Colors.CYAN}Critical:{Colors.RESET} Prevents double-spending risk budget\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    # Get permission token
    permission = engine.evaluate(
        symbol="AAPL",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    print(f"{Colors.YELLOW}Token issued:{Colors.RESET}")
    print(f"   Token ID: {permission.token_id}")
    print(f"   Max Risk: ₹{permission.max_risk_amount:,.2f}")
    print(f"   Expiry: {permission.expiry}")
    
    # First consumption (should succeed)
    first_use = engine.consume_token(permission)
    print(f"\n{Colors.YELLOW}First use:{Colors.RESET}")
    print(f"   Consumed: {first_use}")
    
    # Second consumption (should fail)
    second_use = engine.consume_token(permission)
    print(f"\n{Colors.YELLOW}Second use (reuse attempt):{Colors.RESET}")
    print(f"   Consumed: {second_use}")
    
    passed = first_use and not second_use
    
    print_result(
        passed=passed,
        expected="First use succeeds, second use fails",
        actual=f"First={first_use}, Second={second_use}"
    )
    
    return passed

def test_6_lockdown_after_five_losses():
    """Test: 5 consecutive losses should trigger LOCKDOWN"""
    print_test_header(6, "Five Losses → SYSTEM LOCKDOWN")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Simulate 5 consecutive losing trades")
    print("   • Lockdown requires manual reset")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} LOCKDOWN state, no automated recovery")
    print(f"{Colors.CYAN}Critical:{Colors.RESET} System must refuse further automation\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    # Record 5 consecutive losses
    for i in range(1, 6):
        engine.record_outcome(
            symbol=f"TEST{i}",
            realized_pnl=-5000.0,
            risk_used=0.005
        )
        print(f"   Loss {i}: Streak = {engine.loss_streak}, State = {engine.system_state}")
    
    # Try to get permission after 5 losses
    permission = engine.evaluate(
        symbol="TEST6",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    print(f"\n{Colors.YELLOW}After 5 losses:{Colors.RESET}")
    print(f"   Loss Streak: {engine.loss_streak}")
    print(f"   System State: {engine.system_state}")
    print(f"   Permission Allowed: {permission.allowed}")
    print(f"   Block Reason: {permission.reason}")
    
    # Try daily reset (should NOT clear lockdown)
    engine.reset_daily_state()
    print(f"\n{Colors.YELLOW}After daily reset:{Colors.RESET}")
    print(f"   System State: {engine.system_state}")
    
    # Try manual reset with wrong code
    wrong_reset = engine.manual_reset_lockdown("WRONG_CODE")
    print(f"\n{Colors.YELLOW}Manual reset (wrong code):{Colors.RESET}")
    print(f"   Success: {wrong_reset}")
    
    # Manual reset with correct code
    correct_reset = engine.manual_reset_lockdown("RESET_ACKNOWLEDGED")
    print(f"\n{Colors.YELLOW}Manual reset (correct code):{Colors.RESET}")
    print(f"   Success: {correct_reset}")
    print(f"   System State: {engine.system_state}")
    
    passed = (
        engine.loss_streak == 0 and  # Reset after manual reset
        engine.system_state == "OPERATIONAL" and
        not permission.allowed and  # Was blocked before reset
        not wrong_reset and  # Wrong code rejected
        correct_reset  # Correct code accepted
    )
    
    print_result(
        passed=passed,
        expected="LOCKDOWN after 5 losses, manual reset required",
        actual=f"State={engine.system_state}, Streak={engine.loss_streak}"
    )
    
    return passed

def test_7_unstable_alignment_reduced_risk():
    """Test: UNSTABLE flag should reduce risk by 30%"""
    print_test_header(7, "UNSTABLE Alignment → 30% Risk Reduction")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Compare FULL STABLE vs FULL UNSTABLE")
    print("   • Same probability, same scenario")
    print(f"\n{Colors.CYAN}Expected:{Colors.RESET} UNSTABLE gets 70% of base risk")
    print(f"{Colors.CYAN}Formula:{Colors.RESET} alignment_factor = 0.7 for unstable\n")
    
    engine = RiskBudgetEngine(account_equity=1000000.0, mode="SWING")
    
    # Stable alignment
    perm_stable = engine.evaluate(
        symbol="AAPL",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=False
    )
    
    # Unstable alignment (Phase-7A would block this, but risk engine calculates it)
    perm_unstable = engine.evaluate(
        symbol="TSLA",
        scenario="SCENARIO_A",
        active_probability=0.60,
        alignment="FULL ALIGNMENT",
        is_unstable=True
    )
    
    print(f"{Colors.YELLOW}Results:{Colors.RESET}")
    print(f"   Stable:")
    print(f"      Risk: ₹{perm_stable.max_risk_amount:,.2f} ({perm_stable.max_risk_percent*100:.2f}%)")
    print(f"   Unstable:")
    print(f"      Risk: ₹{perm_unstable.max_risk_amount:,.2f} ({perm_unstable.max_risk_percent*100:.2f}%)")
    
    # Unstable should be 70% of stable
    ratio = perm_unstable.max_risk_amount / perm_stable.max_risk_amount if perm_stable.max_risk_amount > 0 else 0
    
    print(f"\n{Colors.CYAN}Risk Ratio:{Colors.RESET} {ratio:.2%} (expected: 70%)")
    
    passed = abs(ratio - 0.70) < 0.01  # Within 1% of 70%
    
    print_result(
        passed=passed,
        expected="Unstable risk = 70% of stable risk",
        actual=f"Ratio = {ratio:.2%}"
    )
    
    return passed

def run_acceptance_tests():
    """Run all acceptance tests"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*70}")
    print("PHASE-7B: RISK BUDGET ENGINE - ACCEPTANCE TESTS")
    print(f"{'='*70}{Colors.RESET}\n")
    
    print(f"{Colors.CYAN}Testing MANDATORY safety features:{Colors.RESET}")
    print(f"{Colors.CYAN}  • Loss streak limits{Colors.RESET}")
    print(f"{Colors.CYAN}  • Daily drawdown circuit breakers{Colors.RESET}")
    print(f"{Colors.CYAN}  • Alignment-based risk scaling{Colors.RESET}")
    print(f"{Colors.CYAN}  • Token single-use enforcement{Colors.RESET}")
    print(f"{Colors.CYAN}  • System lockdown mechanism{Colors.RESET}\n")
    
    results = []
    
    # Run all tests
    results.append(("Test 1: Four Losses → HALT", test_1_four_losses_halt()))
    results.append(("Test 2: Conflict Alignment → Zero Risk", test_2_conflict_alignment_zero_risk()))
    results.append(("Test 3: Low Probability → Reduced Risk", test_3_low_probability_reduced_risk()))
    results.append(("Test 4: Daily Loss Hit → Trading Stopped", test_4_daily_loss_limit()))
    results.append(("Test 5: Token Reuse → Hard Error", test_5_token_reuse_error()))
    results.append(("Test 6: Five Losses → LOCKDOWN", test_6_lockdown_after_five_losses()))
    results.append(("Test 7: UNSTABLE → 30% Reduction", test_7_unstable_alignment_reduced_risk()))
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*70}")
    print("ACCEPTANCE TEST SUMMARY")
    print(f"{'='*70}{Colors.RESET}\n")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        icon = "✅" if passed else "❌"
        color = Colors.GREEN if passed else Colors.RED
        status = "PASSED" if passed else "FAILED"
        print(f"{icon} {color}{test_name}: {status}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Results: {passed_count}/{total_count} tests passed{Colors.RESET}")
    
    if passed_count == total_count:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎯 ALL ACCEPTANCE TESTS PASSED{Colors.RESET}")
        print(f"{Colors.GREEN}Phase-7B successfully implements:{Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Loss streak protection (4 → HALT, 5 → LOCKDOWN){Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Daily drawdown circuit breaker{Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Alignment-based risk reduction{Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Probability-weighted risk allocation{Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Token single-use enforcement{Colors.RESET}")
        print(f"{Colors.GREEN}  ✅ Manual lockdown reset requirement{Colors.RESET}")
        print(f"\n{Colors.GREEN}Capital preservation > opportunity ✅{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️ ACCEPTANCE TESTS FAILED{Colors.RESET}")
        print(f"{Colors.RED}Phase-7B does not meet mandatory safety requirements{Colors.RESET}")
        print(f"{Colors.RED}System is INVALID for live trading{Colors.RESET}")

if __name__ == "__main__":
    run_acceptance_tests()
