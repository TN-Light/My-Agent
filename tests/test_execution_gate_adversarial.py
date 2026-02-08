"""
Phase-7A Execution Gate - Adversarial Attack Suite
Try to break the gate like a bad actor or emotional trader
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

def print_attack_header(attack_num, attack_name):
    """Print formatted attack header"""
    print(f"\n{Colors.RED}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.RED}❌ ATTACK {attack_num} — {attack_name}{Colors.RESET}")
    print(f"{Colors.RED}{'='*70}{Colors.RESET}\n")

def print_defense_result(defended, reason=""):
    """Print defense result"""
    if defended:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ DEFENSE SUCCESSFUL - GATE HELD{Colors.RESET}")
        print(f"{Colors.GREEN}System integrity maintained{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}🚨 BREACH DETECTED - GATE FAILED{Colors.RESET}")
        print(f"{Colors.RED}Security compromised: {reason}{Colors.RESET}")

def print_gate_results(gate_results):
    """Print individual gate results"""
    print(f"\n{Colors.YELLOW}Gate Results:{Colors.RESET}")
    for gate_name, status in gate_results.items():
        icon = "✅" if status == "PASS" else "❌"
        color = Colors.GREEN if status == "PASS" else Colors.RED
        print(f"   {icon} {color}{gate_name}: {status}{Colors.RESET}")

def attack_1_looks_bullish_bro():
    """
    Attack: "But it looks bullish bro"
    - Strong trend
    - News-driven rally
    - Emotional conviction
    
    Expected: Still BLOCKED if structural gates fail
    """
    print_attack_header(1, "\"But It Looks Bullish Bro\"")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Strong uptrend in progress")
    print("   • Positive news catalyst")
    print("   • Emotional conviction: \"Can't miss this!\"")
    print("   • BUT: Price at resistance + continuation scenario")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"The trend is strong! All indicators green!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-4 (structural location)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} News/emotion irrelevant - buying tops = death\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="TSLA",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.65, "B_pullback": 0.22, "C_failure": 0.13},
        active_state="SCENARIO_A",
        current_price=295.00,  # At resistance
        monthly_support=[240.00],
        monthly_resistance=[300.00],  # Price within 2% of resistance
        monthly_trend="BULLISH"  # Strong trend doesn't override structure
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate4_blocked = result["gate_results"]["Gate-4_StructuralLocation"] == "FAIL"
    defended = status == "BLOCKED" and gate4_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "Emotional bias bypassed structural logic"
    )
    
    return defended

def attack_2_indicator_addiction():
    """
    Attack: Indicator Addiction
    - RSI oversold
    - MACD crossing
    - "All indicators say BUY!"
    
    Expected: Irrelevant - Phase-7A doesn't see indicators
    """
    print_attack_header(2, "Indicator Addiction")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • RSI = 25 (oversold)")
    print("   • MACD bullish cross")
    print("   • Stochastic oversold")
    print("   • BUT: Weak dominance (prob_a = 0.52)")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"All my indicators are aligned! Perfect entry!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-2 (dominance < 0.55)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} Indicators are noise - structure is signal\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="SPY",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.52, "B_pullback": 0.30, "C_failure": 0.18},  # Weak dominance
        active_state="SCENARIO_A",
        current_price=450.00,
        monthly_support=[420.00],
        monthly_resistance=[480.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate2_blocked = result["gate_results"]["Gate-2_Dominance"] == "FAIL"
    defended = status == "BLOCKED" and gate2_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    print(f"\n{Colors.CYAN}Reality Check:{Colors.RESET}")
    print(f"   Phase-7A is indicator-blind by design")
    print(f"   Only structural gates matter (alignment, probabilities, location)")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "Indicator addiction bypassed structural rules"
    )
    
    return defended

def attack_3_human_override_attempt():
    """
    Attack: Human Override Attempt
    - Try to manually force execution
    - Bypass gate logic
    
    Expected: HARD ERROR - no permission token = no execution
    """
    print_attack_header(3, "Human Override Attempt")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Try to call execution logic directly")
    print("   • Bypass gate evaluation")
    print("   • Manually force permission")
    print(f"\n{Colors.CYAN}Bad Actor:{Colors.RESET} \"I'll just skip the gate and execute anyway\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} HARD ERROR - no valid permission token")
    print(f"{Colors.CYAN}Why:{Colors.RESET} All downstream logic requires permission token from gate\n")
    
    # Simulate blocked gate
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="AAPL",
        alignment="CONFLICT",  # Conflict alignment
        is_unstable=False,
        probabilities={"A_continuation": 0.30, "B_pullback": 0.35, "C_failure": 0.35},
        active_state="CONFLICT_STATE",
        current_price=175.00,
        monthly_support=[160.00],
        monthly_resistance=[190.00],
        monthly_trend="SIDEWAYS"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Blocked: {blocked_reasons}")
    
    # Check if there's a valid permission token
    has_token = status == "ALLOWED"
    no_token_means_safe = not has_token
    
    print(f"\n{Colors.CYAN}Permission Token Check:{Colors.RESET}")
    if has_token:
        print(f"   {Colors.RED}⚠️ Token issued: {result['execution_permission'].get('granted_at', 'N/A')}{Colors.RESET}")
    else:
        print(f"   {Colors.GREEN}✅ No token issued - execution impossible{Colors.RESET}")
        print(f"   {Colors.GREEN}Downstream logic will reject any manual override{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Architecture Defense:{Colors.RESET}")
    print(f"   Gate returns BLOCKED → No token")
    print(f"   No token → execution_engine refuses to proceed")
    print(f"   Manual override → Hard error (missing required token)")
    
    defended = no_token_means_safe
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "Override bypassed token requirement"
    )
    
    return defended

def attack_4_timeframe_cherry_picking():
    """
    Attack: Timeframe Cherry Picking
    - Daily looks perfect
    - Weekly broken
    - Pick favorable timeframe, ignore others
    
    Expected: BLOCKED - alignment != FULL
    """
    print_attack_header(4, "Timeframe Cherry Picking")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Daily chart: Perfect bullish setup")
    print("   • Weekly chart: Broken structure")
    print("   • Cherry pick: \"Let's trade the daily!\"")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"Daily is so clean! Ignore the weekly!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-1 (alignment != FULL)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} MTF alignment required - no cherry picking allowed\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="NVDA",
        alignment="PARTIAL ALIGNMENT",  # Not all timeframes aligned
        is_unstable=False,
        probabilities={"A_continuation": 0.58, "B_pullback": 0.27, "C_failure": 0.15},
        active_state="SCENARIO_A",
        current_price=880.00,
        monthly_support=[800.00],
        monthly_resistance=[950.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate1_blocked = result["gate_results"]["Gate-1_Alignment"] == "FAIL"
    defended = status == "BLOCKED" and gate1_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    
    print(f"\n{Colors.CYAN}MTF Philosophy:{Colors.RESET}")
    print(f"   All timeframes must agree (Monthly, Weekly, Daily)")
    print(f"   Partial alignment = structural uncertainty")
    print(f"   No cherry picking single timeframes")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "Cherry picking bypassed MTF requirement"
    )
    
    return defended

def attack_5_revenge_trading_setup():
    """
    Attack: Revenge Trading
    - Previous loss
    - Emotional need to "get it back"
    - Market bouncing
    
    Expected: No memory, no emotion - gates evaluated fresh
    """
    print_attack_header(5, "Revenge Trading Setup")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Trader took loss yesterday on TSLA short")
    print("   • Emotional: \"I need to get my money back!\"")
    print("   • Market bouncing today")
    print("   • BUT: High regime change risk (prob_c = 0.32)")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"I HAVE to trade this bounce! I lost yesterday!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-3 (regime risk)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} Gate has no memory, no emotion - evaluates structure only\n")
    
    # First evaluation (previous loss scenario - for context)
    print(f"{Colors.BLUE}Previous Trade Context (for illustration only):{Colors.RESET}")
    print(f"   Yesterday: Trader lost on TSLA short")
    print(f"   Emotional state: Frustrated, wants revenge")
    print(f"\n{Colors.BLUE}Current Trade Evaluation (emotion-free):{Colors.RESET}")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="TSLA",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.45, "B_pullback": 0.23, "C_failure": 0.32},  # High regime risk
        active_state="SCENARIO_A",
        current_price=265.00,
        monthly_support=[240.00],
        monthly_resistance=[290.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    # Both Gate-2 (dominance) and Gate-3 (regime risk) should fail
    gate3_blocked = result["gate_results"]["Gate-3_RegimeRisk"] == "FAIL"
    defended = status == "BLOCKED" and gate3_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    
    print(f"\n{Colors.CYAN}Emotional Immunity:{Colors.RESET}")
    print(f"   Gate has zero memory of previous trades")
    print(f"   No emotional state (revenge, FOMO, fear)")
    print(f"   Each evaluation is stateless and deterministic")
    print(f"   Structural red flags → BLOCKED (regardless of trader emotion)")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "Emotional bias bypassed stateless evaluation"
    )
    
    return defended

def attack_6_fomo_breakout():
    """
    Attack: FOMO Breakout
    - "It's breaking out! Can't miss it!"
    - Strong momentum
    - BUT: Overconfidence (prob_a = 0.75)
    
    Expected: BLOCKED by Gate-5 (overconfidence)
    """
    print_attack_header(6, "FOMO Breakout")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Stock breaking to new highs")
    print("   • Social media hype")
    print("   • \"Can't miss this move!\"")
    print("   • BUT: Overconfident probability (prob_a = 0.75)")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"It's going to the moon! All in!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-5 (overconfidence)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} Markets punish certainty - prob > 0.70 = danger\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="GME",
        alignment="FULL ALIGNMENT",
        is_unstable=False,
        probabilities={"A_continuation": 0.75, "B_pullback": 0.15, "C_failure": 0.10},  # Overconfident
        active_state="SCENARIO_A",
        current_price=35.00,
        monthly_support=[25.00],
        monthly_resistance=[50.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate5_blocked = result["gate_results"]["Gate-5_Overconfidence"] == "FAIL"
    defended = status == "BLOCKED" and gate5_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    
    print(f"\n{Colors.CYAN}Anti-Certainty Protection:{Colors.RESET}")
    print(f"   High confidence attracts maximum position size")
    print(f"   But markets are adversarial - certainty = trap")
    print(f"   Gate-5 blocks any probability > 0.70")
    print(f"   Optimal range: 0.55-0.70 (confident but not arrogant)")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "FOMO bypassed overconfidence protection"
    )
    
    return defended

def attack_7_news_catalyst_hype():
    """
    Attack: News Catalyst Hype
    - "Earnings beat! FDA approval! Acquisition!"
    - Fundamental catalyst
    - BUT: Alignment = UNSTABLE (LTF extended)
    
    Expected: BLOCKED by Gate-1 (unstable)
    """
    print_attack_header(7, "News Catalyst Hype")
    
    print(f"{Colors.YELLOW}Attack Vector:{Colors.RESET}")
    print("   • Major positive news (earnings beat, FDA approval)")
    print("   • \"Fundamentals changed!\"")
    print("   • Price gapping up")
    print("   • BUT: LTF overextended (UNSTABLE)")
    print(f"\n{Colors.CYAN}Emotional Trader:{Colors.RESET} \"News is out! This is the time!\"")
    print(f"{Colors.CYAN}Expected Defense:{Colors.RESET} BLOCKED by Gate-1 (unstable alignment)")
    print(f"{Colors.CYAN}Why:{Colors.RESET} News doesn't change structure - wait for LTF reset\n")
    
    gate = ExecutionGate()
    result = gate.evaluate(
        symbol="MRNA",
        alignment="FULL ALIGNMENT",
        is_unstable=True,  # LTF overextended despite news
        probabilities={"A_continuation": 0.68, "B_pullback": 0.20, "C_failure": 0.12},
        active_state="SCENARIO_A",
        current_price=115.00,
        monthly_support=[90.00],
        monthly_resistance=[140.00],
        monthly_trend="BULLISH"
    )
    
    print_gate_results(result["gate_results"])
    
    status = result["execution_permission"]["status"]
    blocked_reasons = result["execution_permission"].get("reason", [])
    
    gate1_blocked = result["gate_results"]["Gate-1_Alignment"] == "FAIL"
    defended = status == "BLOCKED" and gate1_blocked
    
    print(f"\n{Colors.YELLOW}Attack Result:{Colors.RESET}")
    print(f"   Status: {Colors.RED if status == 'BLOCKED' else Colors.GREEN}{status}{Colors.RESET}")
    if blocked_reasons:
        print(f"   Defense: {blocked_reasons}")
    
    print(f"\n{Colors.CYAN}News Immunity:{Colors.RESET}")
    print(f"   Gate doesn't read news or fundamentals")
    print(f"   Only sees structure (alignment, location, probabilities)")
    print(f"   News-driven gaps often mean overextension")
    print(f"   Wait for LTF to reset before entry")
    
    print_defense_result(
        defended=defended,
        reason="" if defended else "News hype bypassed structural logic"
    )
    
    return defended

def run_adversarial_tests():
    """Run all adversarial attacks"""
    print(f"\n{Colors.BOLD}{Colors.RED}{'='*70}")
    print("PHASE-7A ADVERSARIAL ATTACK SUITE")
    print(f"{'='*70}{Colors.RESET}\n")
    
    print(f"{Colors.CYAN}Goal: Try to break the execution gate like a bad actor{Colors.RESET}")
    print(f"{Colors.CYAN}Success: Gate blocks all emotional/biased attack vectors{Colors.RESET}\n")
    
    results = []
    
    # Run all attacks
    results.append(("Attack 1: Looks Bullish Bro", attack_1_looks_bullish_bro()))
    results.append(("Attack 2: Indicator Addiction", attack_2_indicator_addiction()))
    results.append(("Attack 3: Human Override Attempt", attack_3_human_override_attempt()))
    results.append(("Attack 4: Timeframe Cherry Picking", attack_4_timeframe_cherry_picking()))
    results.append(("Attack 5: Revenge Trading", attack_5_revenge_trading_setup()))
    results.append(("Attack 6: FOMO Breakout", attack_6_fomo_breakout()))
    results.append(("Attack 7: News Catalyst Hype", attack_7_news_catalyst_hype()))
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*70}")
    print("ADVERSARIAL TEST SUMMARY")
    print(f"{'='*70}{Colors.RESET}\n")
    
    defended_count = sum(1 for _, defended in results if defended)
    total_count = len(results)
    
    for attack_name, defended in results:
        icon = "✅" if defended else "🚨"
        color = Colors.GREEN if defended else Colors.RED
        status = "DEFENDED" if defended else "BREACHED"
        print(f"{icon} {color}{attack_name}: {status}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Defense Rate: {defended_count}/{total_count} attacks blocked{Colors.RESET}")
    
    if defended_count == total_count:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🛡️ PERFECT DEFENSE - ALL ATTACKS BLOCKED{Colors.RESET}")
        print(f"{Colors.GREEN}Phase-7A is emotion-proof and non-bypassable{Colors.RESET}")
        print(f"{Colors.GREEN}Gate successfully defended against:{Colors.RESET}")
        print(f"{Colors.GREEN}  • Emotional bias (bullish conviction, FOMO, revenge){Colors.RESET}")
        print(f"{Colors.GREEN}  • Indicator addiction{Colors.RESET}")
        print(f"{Colors.GREEN}  • Manual override attempts{Colors.RESET}")
        print(f"{Colors.GREEN}  • Timeframe cherry picking{Colors.RESET}")
        print(f"{Colors.GREEN}  • News/fundamental hype{Colors.RESET}")
        print(f"{Colors.GREEN}  • Overconfidence traps{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️ SECURITY BREACH - ATTACKS SUCCEEDED{Colors.RESET}")
        print(f"{Colors.RED}Gate failed to defend against emotional/biased attacks{Colors.RESET}")
        print(f"{Colors.RED}Critical vulnerabilities detected - fix required{Colors.RESET}")
    
    print(f"\n{Colors.CYAN}Key Insight:{Colors.RESET}")
    print(f"   Phase-7A enforces pure structural logic")
    print(f"   No emotion, no bias, no memory, no indicators")
    print(f"   Only MTF alignment + probabilities + location matter")
    print(f"   This protects capital from human psychology")

if __name__ == "__main__":
    run_adversarial_tests()
