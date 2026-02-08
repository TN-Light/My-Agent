"""
Phase-7A Execution Gate Test Suite
Tests all 5 gates with intentional failure scenarios + 1 clean allow case
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.execution_gate import ExecutionGate

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_num, test_name):
    """Print formatted test header"""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}🔹 TEST {test_num} — {test_name}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def print_test_result(passed, expected, actual, reason=""):
    """Print test result with color coding"""
    if passed:
        print(f"{Colors.GREEN}✅ TEST PASSED{Colors.RESET}")
        print(f"   Expected: {expected}")
        print(f"   Got: {actual}")
    else:
        print(f"{Colors.RED}❌ TEST FAILED - SYSTEM BREACH{Colors.RESET}")
        print(f"   Expected: {expected}")
        print(f"   Got: {actual}")
        if reason:
            print(f"   Reason: {reason}")

def print_gate_results(gate_results):
    """Print individual gate results"""
    print(f"\n{Colors.YELLOW}Gate Results:{Colors.RESET}")
    for gate_name, status in gate_results.items():
        icon = "✅" if status == "PASS" else "❌"
        color = Colors.GREEN if status == "PASS" else Colors.RED
        print(f"   {icon} {color}{gate_name}: {status}{Colors.RESET}")

def test_1_unstable_alignment_trap():
    """Test Gate-1: UNSTABLE alignment should BLOCK"""
    print_test_header(1, "UNSTABLE Alignment Trap")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • LTF overextended in sharp rally")
    print("   • HTF near resistance")
    print("   • Alignment = UNSTABLE")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_BLOCKED (Gate-1)")
    print(f"{Colors.YELLOW}Risk:{Colors.RESET} If execution allowed → SYSTEM FAILED\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="TSLA",
        alignment="FULL ALIGNMENT",
        is_unstable=True,  # CRITICAL: UNSTABLE flag
        probabilities={"A_continuation": 0.60, "B_pullback": 0.25, "C_failure": 0.15},
        active_state="SCENARIO_A",
        current_price=250.00,
        monthly_support=[200.00],
        monthly_resistance=[280.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate1_failed = result["gate_results"]["Gate-1_Alignment"] == "FAIL"
    passed = status == "BLOCKED" and gate1_failed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Reasons: {blocked_reasons}")
    
    print_test_result(
        passed=passed,
        expected="BLOCKED (Gate-1 fails on UNSTABLE)",
        actual=f"{status} (Gate-1: {result['gate_results']['Gate-1_Alignment']})",
        reason="" if passed else "DANGER: Execution allowed in unstable structure"
    )
    
    return passed

def test_2_high_probability_illusion():
    """Test Gate-2: Dominance < 0.55 should BLOCK"""
    print_test_header(2, "High Probability Illusion")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • prob_a = 0.54 (just below threshold)")
    print("   • prob_b = 0.28")
    print("   • prob_c = 0.18")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_BLOCKED (Gate-2)")
    print(f"{Colors.YELLOW}Risk:{Colors.RESET} False confidence kills accounts\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="NVDA",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.54, "B_pullback": 0.28, "C_failure": 0.18},  # Max = 0.54 < 0.55
        active_state="SCENARIO_A",
        current_price=800.00,
        monthly_support=[700.00],
        monthly_resistance=[900.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate2_failed = result["gate_results"]["Gate-2_Dominance"] == "FAIL"
    passed = status == "BLOCKED" and gate2_failed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Reasons: {blocked_reasons}")
    
    print_test_result(
        passed=passed,
        expected="BLOCKED (Gate-2 fails on dominance < 0.55)",
        actual=f"{status} (Gate-2: {result['gate_results']['Gate-2_Dominance']})",
        reason="" if passed else "DANGER: Weak dominance allowed"
    )
    
    return passed

def test_3_regime_change_ambush():
    """Test Gate-3: prob_c >= 0.30 should BLOCK"""
    print_test_header(3, "Regime Change Ambush")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • FULL alignment (looks clean)")
    print("   • prob_c = 0.31 (regime risk elevated)")
    print("   • prob_a = 0.48, prob_b = 0.21")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_BLOCKED (Gate-3)")
    print(f"{Colors.YELLOW}Risk:{Colors.RESET} Where most traders get wiped out\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="AAPL",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.48, "B_pullback": 0.21, "C_failure": 0.31},  # prob_c >= 0.30
        active_state="SCENARIO_A",
        current_price=180.00,
        monthly_support=[160.00],
        monthly_resistance=[200.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate3_failed = result["gate_results"]["Gate-3_RegimeRisk"] == "FAIL"
    passed = status == "BLOCKED" and gate3_failed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Reasons: {blocked_reasons}")
    
    print_test_result(
        passed=passed,
        expected="BLOCKED (Gate-3 fails on regime risk >= 0.30)",
        actual=f"{status} (Gate-3: {result['gate_results']['Gate-3_RegimeRisk']})",
        reason="" if passed else "DANGER: Regime change risk ignored"
    )
    
    return passed

def test_4_buying_the_top_trap():
    """Test Gate-4: Buying resistance should BLOCK"""
    print_test_header(4, "Buying the Top Psychological Trap")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • Scenario A ACTIVE (continuation bias)")
    print("   • Price inside HTF resistance band")
    print("   • Resistance = 300.00, Price = 298.00")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_BLOCKED (Gate-4)")
    print(f"{Colors.YELLOW}Risk:{Colors.RESET} If this passes → system will eventually blow up\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="MSFT",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.60, "B_pullback": 0.25, "C_failure": 0.15},
        active_state="SCENARIO_A",
        current_price=298.00,  # Near resistance
        monthly_support=[250.00],
        monthly_resistance=[300.00],  # Price within 2% of resistance
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate4_failed = result["gate_results"]["Gate-4_StructuralLocation"] == "FAIL"
    passed = status == "BLOCKED" and gate4_failed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Reasons: {blocked_reasons}")
    
    print_test_result(
        passed=passed,
        expected="BLOCKED (Gate-4 fails on buying resistance)",
        actual=f"{status} (Gate-4: {result['gate_results']['Gate-4_StructuralLocation']})",
        reason="" if passed else "DANGER: Buying tops allowed - account will blow up"
    )
    
    return passed

def test_5_overconfidence_poison():
    """Test Gate-5: prob > 0.70 should BLOCK"""
    print_test_header(5, "Overconfidence Poison")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • prob_a artificially at 0.72")
    print("   • Everything else looks perfect")
    print("   • But certainty = danger")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_BLOCKED (Gate-5)")
    print(f"{Colors.YELLOW}Risk:{Colors.RESET} Markets punish certainty\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="GOOGL",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.72, "B_pullback": 0.18, "C_failure": 0.10},  # prob_a > 0.70
        active_state="SCENARIO_A",
        current_price=140.00,
        monthly_support=[120.00],
        monthly_resistance=[160.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate5_failed = result["gate_results"]["Gate-5_Overconfidence"] == "FAIL"
    passed = status == "BLOCKED" and gate5_failed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Reasons: {blocked_reasons}")
    
    print_test_result(
        passed=passed,
        expected="BLOCKED (Gate-5 fails on overconfidence > 0.70)",
        actual=f"{status} (Gate-5: {result['gate_results']['Gate-5_Overconfidence']})",
        reason="" if passed else "DANGER: Overconfidence allowed"
    )
    
    return passed

def test_6_clean_allow_case():
    """Test clean case: All gates should PASS (RARE)"""
    print_test_header(6, "Clean Allow Case (RARE)")
    
    print(f"{Colors.YELLOW}Scenario:{Colors.RESET}")
    print("   • FULL stable alignment")
    print("   • prob_a = 0.62 (strong dominance)")
    print("   • prob_c = 0.18 (low regime risk)")
    print("   • Price NOT at resistance")
    print(f"\n{Colors.YELLOW}Expected:{Colors.RESET} EXECUTION_ALLOWED")
    print(f"{Colors.YELLOW}Note:{Colors.RESET} Should happen 10-20% of analyses max\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="AMZN",
        alignment="FULL ALIGNMENT",
        is_unstable=False,  # Stable
        probabilities={"A_continuation": 0.62, "B_pullback": 0.20, "C_failure": 0.18},  # Good dominance, low regime risk
        active_state="SCENARIO_A",
        current_price=140.00,  # Mid-range
        monthly_support=[120.00],
        monthly_resistance=[180.00],  # Well below resistance
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    token_info = result["execution_permission"]
    
    all_gates_passed = all(v == "PASS" for v in result["gate_results"].values())
    passed = status == "ALLOWED" and all_gates_passed
    
    print(f"\n{Colors.YELLOW}Decision:{Colors.RESET}")
    print(f"   Status: {Colors.GREEN if status == 'ALLOWED' else Colors.RED}{status}{Colors.RESET}")
    if status == "ALLOWED":
        print(f"   Valid for: {token_info.get('valid_for', 'N/A')}")
        print(f"   Expires: {token_info.get('expires_after', 'N/A')}")
        print(f"   Token issued: {token_info.get('token', 'N/A')}")
    
    print_test_result(
        passed=passed,
        expected="ALLOWED (all gates pass)",
        actual=f"{status} (All gates: {all_gates_passed})",
        reason="" if passed else "Should allow in clean conditions"
    )
    
    return passed

def run_all_tests():
    """Run all 6 tests and report summary"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*70}")
    print("PHASE-7A EXECUTION GATE TEST SUITE")
    print(f"{'='*70}{Colors.RESET}\n")
    
    print(f"{Colors.CYAN}Testing 5 failure scenarios + 1 clean allow case{Colors.RESET}")
    print(f"{Colors.CYAN}All gates must be non-bypassable for system integrity{Colors.RESET}\n")
    
    results = []
    
    # Run all tests
    results.append(("Test 1: UNSTABLE Alignment Trap", test_1_unstable_alignment_trap()))
    results.append(("Test 2: High Probability Illusion", test_2_high_probability_illusion()))
    results.append(("Test 3: Regime Change Ambush", test_3_regime_change_ambush()))
    results.append(("Test 4: Buying the Top Trap", test_4_buying_the_top_trap()))
    results.append(("Test 5: Overconfidence Poison", test_5_overconfidence_poison()))
    results.append(("Test 6: Clean Allow Case", test_6_clean_allow_case()))
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{Colors.RESET}\n")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        icon = "✅" if passed else "❌"
        color = Colors.GREEN if passed else Colors.RED
        print(f"{icon} {color}{test_name}: {'PASSED' if passed else 'FAILED'}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Results: {passed_count}/{total_count} tests passed{Colors.RESET}")
    
    if passed_count == total_count:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎯 ALL TESTS PASSED - SYSTEM INTEGRITY VERIFIED{Colors.RESET}")
        print(f"{Colors.GREEN}Execution gate is non-bypassable and highly selective{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️ SYSTEM BREACH - FAILED TESTS MUST BE FIXED{Colors.RESET}")
        print(f"{Colors.RED}Gate bypasses detected - system cannot be trusted{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Expected behavior:{Colors.RESET}")
    print(f"   • Tests 1-5 should BLOCK (structural red flags)")
    print(f"   • Test 6 should ALLOW (clean structure)")
    print(f"   • In live trading: ALLOW rate should be <20%")

if __name__ == "__main__":
    run_all_tests()
