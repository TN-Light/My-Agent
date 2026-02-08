"""
Phase-X Human Summary Engine - Context-Aware Demo
Demonstrates market-focused summaries for different structural conditions
"""

from logic.human_summary_engine import HumanSummaryEngine

def demo():
    hse = HumanSummaryEngine()
    
    print("=" * 80)
    print("PHASE-X HUMAN SUMMARY ENGINE - CONTEXT-AWARE OUTPUT")
    print("=" * 80)
    
    scenarios = [
        {
            "name": "Stock near resistance, timeframes conflicting",
            "params": {
                "alignment_state": "CONFLICT",
                "active_state": "SCENARIO_B",
                "execution_gate_status": "PASS",
                "regime_flags": set(),
                "htf_location": "RESISTANCE",
                "trend_state": "UP"
            }
        },
        {
            "name": "Stock overextended near resistance, unstable",
            "params": {
                "alignment_state": "UNSTABLE",
                "active_state": "SCENARIO_B",
                "execution_gate_status": "PASS",
                "regime_flags": set(),
                "htf_location": "RESISTANCE",
                "trend_state": "UP"
            }
        },
        {
            "name": "Strong trend but near resistance (caution zone)",
            "params": {
                "alignment_state": "FULL",
                "active_state": "SCENARIO_A",
                "execution_gate_status": "PASS",
                "regime_flags": set(),
                "htf_location": "RESISTANCE",
                "trend_state": "UP"
            }
        },
        {
            "name": "Full alignment at support (continuation setup)",
            "params": {
                "alignment_state": "FULL",
                "active_state": "SCENARIO_A",
                "execution_gate_status": "PASS",
                "regime_flags": set(),
                "htf_location": "SUPPORT",
                "trend_state": "UP"
            }
        },
        {
            "name": "Partial alignment mid-range (trend forming)",
            "params": {
                "alignment_state": "PARTIAL",
                "active_state": "SCENARIO_B",
                "execution_gate_status": "PASS",
                "regime_flags": set(),
                "htf_location": "MID",
                "trend_state": "UP"
            }
        },
        {
            "name": "Gate blocked + unstable structure (extreme risk)",
            "params": {
                "alignment_state": "UNSTABLE",
                "active_state": "SCENARIO_B",
                "execution_gate_status": "BLOCKED",
                "regime_flags": set(),
                "htf_location": "RESISTANCE",
                "trend_state": "UP"
            }
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n--- SCENARIO {i}: {scenario['name']} ---")
        result = hse.generate(**scenario['params'])
        print(f"Verdict: {result['verdict']} ({result['confidence']} confidence)")
        print(f"Summary: {result['summary']}")
    
    print("\n" + "=" * 80)
    print("✅ All summaries explain MARKET CONDITION, not system logic")
    print("✅ Context-specific details based on alignment + location")
    print("✅ Structure-only (no price, no indicators)")
    print("=" * 80)

if __name__ == "__main__":
    demo()
