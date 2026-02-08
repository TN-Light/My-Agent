"""
Phase-11 Demo: Show signal evaluation for different market conditions
"""

from logic.signal_eligibility import SignalEligibilityEngine

def demo_phase_11():
    """Demonstrate Phase-11 signal evaluation"""
    
    engine = SignalEligibilityEngine()
    
    scenarios = [
        {
            "name": "Perfect Setup (STRONG + FULL + SUPPORT)",
            "params": {
                "verdict": "STRONG",
                "confidence": "HIGH",
                "summary": "Structure is strong and aligned across timeframes. Conditions favor continuation.",
                "alignment_state": "FULL",
                "htf_location": "SUPPORT",
                "trend_state": "UP",
                "active_scenario": "SCENARIO_A",
                "execution_gate_status": "PASS"
            }
        },
        {
            "name": "Extended Setup (CAUTION + FULL + RESISTANCE)",
            "params": {
                "verdict": "CAUTION",
                "confidence": "MEDIUM",
                "summary": "Trend is strong but stock is extended near higher-timeframe resistance.",
                "alignment_state": "FULL",
                "htf_location": "RESISTANCE",
                "trend_state": "UP",
                "active_scenario": "SCENARIO_A",
                "execution_gate_status": "PASS"
            }
        },
        {
            "name": "Building Structure (WAIT + PARTIAL)",
            "params": {
                "verdict": "WAIT",
                "confidence": "MEDIUM",
                "summary": "Alignment is building but not complete. Trend is forming.",
                "alignment_state": "PARTIAL",
                "htf_location": "MID",
                "trend_state": "UP",
                "active_scenario": "SCENARIO_B",
                "execution_gate_status": "PASS"
            }
        },
        {
            "name": "Unstable Structure (AVOID + UNSTABLE + RESISTANCE)",
            "params": {
                "verdict": "AVOID",
                "confidence": "LOW",
                "summary": "Stock is overextended near higher-timeframe resistance with unstable structure.",
                "alignment_state": "UNSTABLE",
                "htf_location": "RESISTANCE",
                "trend_state": "UP",
                "active_scenario": "SCENARIO_B",
                "execution_gate_status": "PASS"
            }
        },
        {
            "name": "Gate Blocked (NO_TRADE despite structure)",
            "params": {
                "verdict": "NO_TRADE",
                "confidence": "LOW",
                "summary": "Stock overextended near resistance with unstable structure. Extreme risk of reversal.",
                "alignment_state": "UNSTABLE",
                "htf_location": "RESISTANCE",
                "trend_state": "UP",
                "active_scenario": "SCENARIO_B",
                "execution_gate_status": "BLOCKED"
            }
        },
        {
            "name": "Short Signal (Downtrend continuation)",
            "params": {
                "verdict": "STRONG",
                "confidence": "HIGH",
                "summary": "Structure aligned for downtrend continuation.",
                "alignment_state": "FULL",
                "htf_location": "RESISTANCE",
                "trend_state": "DOWN",
                "active_scenario": "SCENARIO_A",
                "execution_gate_status": "PASS"
            }
        },
    ]
    
    print("\n" + "🔥" * 35)
    print("PHASE-11: SIGNAL ELIGIBILITY DEMO")
    print("🔥" * 35 + "\n")
    
    eligible_count = 0
    not_eligible_count = 0
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'=' * 70}")
        print(f"SCENARIO {i}: {scenario['name']}")
        print('=' * 70)
        
        signal = engine.evaluate_signal(**scenario['params'])
        
        if signal.signal_status.value == "ELIGIBLE":
            eligible_count += 1
        else:
            not_eligible_count += 1
        
        # Display signal
        formatted = engine.format_signal(signal)
        print(formatted)
        
        input("\n[Press Enter for next scenario...]")
    
    # Summary
    print("\n" + "=" * 70)
    print("DEMO SUMMARY")
    print("=" * 70)
    print(f"Total scenarios tested: {len(scenarios)}")
    print(f"✅ ELIGIBLE signals: {eligible_count}")
    print(f"❌ NOT_ELIGIBLE signals: {not_eligible_count}")
    print(f"Signal rarity: {eligible_count}/{len(scenarios)} = {eligible_count/len(scenarios)*100:.1f}%")
    print("\n💡 Key Insight: Signals are RARE by design")
    print("   Most market conditions are NOT trade-eligible")
    print("   This protects capital and ensures quality over quantity")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    demo_phase_11()
