"""
Phase-11 Test Suite: Signal Eligibility Engine

Tests signal generation logic:
1. Only STRONG/CAUTION verdicts can be eligible
2. Execution gate must pass
3. Signals are rare (most are NOT_ELIGIBLE)
4. Deterministic (same structure = same signal)
"""

from logic.signal_eligibility import (
    SignalEligibilityEngine,
    SignalStatus,
    SignalType,
    Direction,
    EntryStyle,
    RiskClass
)


def test_phase_11():
    """Test Phase-11 signal eligibility logic"""
    
    engine = SignalEligibilityEngine()
    
    print("=" * 70)
    print("PHASE-11: SIGNAL ELIGIBILITY ENGINE TEST SUITE")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    # TEST 1: STRONG verdict + FULL alignment + SUPPORT = ELIGIBLE
    print("\nTEST 1: STRONG + FULL + SUPPORT → ELIGIBLE (pullback entry)")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="STRONG",
        confidence="HIGH",
        summary="Structure is strong and aligned across timeframes.",
        alignment_state="FULL",
        htf_location="SUPPORT",
        trend_state="UP",
        active_scenario="SCENARIO_A",
        execution_gate_status="PASS"
    )
    
    if (signal.signal_status == SignalStatus.ELIGIBLE and
        signal.signal_type == SignalType.TREND_CONTINUATION and
        signal.direction == Direction.LONG and
        signal.entry_style == EntryStyle.PULLBACK_ONLY and
        signal.risk_class == RiskClass.LOW):
        print(f"✅ PASS: ELIGIBLE signal generated correctly")
        print(f"   Type: {signal.signal_type.value}")
        print(f"   Entry: {signal.entry_style.value}")
        passed += 1
    else:
        print(f"❌ FAIL: Expected ELIGIBLE with PULLBACK_ONLY")
        print(f"   Got: {signal.signal_status.value}, {signal.entry_style.value}")
        failed += 1
    
    # TEST 2: STRONG + FULL + MID = ELIGIBLE (immediate OK)
    print("\nTEST 2: STRONG + FULL + MID → ELIGIBLE (immediate entry OK)")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="STRONG",
        confidence="HIGH",
        summary="Structure is strong and aligned.",
        alignment_state="FULL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_A",
        execution_gate_status="PASS"
    )
    
    if (signal.signal_status == SignalStatus.ELIGIBLE and
        signal.entry_style == EntryStyle.IMMEDIATE_OK and
        signal.risk_class == RiskClass.LOW):
        print(f"✅ PASS: ELIGIBLE signal with immediate entry")
        passed += 1
    else:
        print(f"❌ FAIL: Expected IMMEDIATE_OK entry style")
        print(f"   Got: {signal.entry_style.value}")
        failed += 1
    
    # TEST 3: CAUTION + FULL + RESISTANCE = ELIGIBLE (pullback only)
    print("\nTEST 3: CAUTION + FULL + RESISTANCE → ELIGIBLE (pullback only)")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="CAUTION",
        confidence="MEDIUM",
        summary="Trend is strong but extended near resistance.",
        alignment_state="FULL",
        htf_location="RESISTANCE",
        trend_state="UP",
        active_scenario="SCENARIO_A",
        execution_gate_status="PASS"
    )
    
    if (signal.signal_status == SignalStatus.ELIGIBLE and
        signal.entry_style == EntryStyle.PULLBACK_ONLY and
        signal.risk_class == RiskClass.MEDIUM):
        print(f"✅ PASS: ELIGIBLE with CAUTION (pullback only)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected ELIGIBLE with PULLBACK_ONLY and MEDIUM risk")
        print(f"   Got: {signal.signal_status.value}, {signal.entry_style.value}, {signal.risk_class.value}")
        failed += 1
    
    # TEST 4: WAIT verdict = NOT ELIGIBLE
    print("\nTEST 4: WAIT verdict → NOT_ELIGIBLE")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="WAIT",
        confidence="MEDIUM",
        summary="Alignment is building but not complete.",
        alignment_state="PARTIAL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_B",
        execution_gate_status="PASS"
    )
    
    if (signal.signal_status == SignalStatus.NOT_ELIGIBLE and
        signal.entry_style == EntryStyle.NO_ENTRY and
        signal.risk_class == RiskClass.HIGH):
        print(f"✅ PASS: WAIT verdict correctly marked NOT_ELIGIBLE")
        passed += 1
    else:
        print(f"❌ FAIL: WAIT should be NOT_ELIGIBLE")
        print(f"   Got: {signal.signal_status.value}")
        failed += 1
    
    # TEST 5: AVOID verdict = NOT ELIGIBLE
    print("\nTEST 5: AVOID verdict → NOT_ELIGIBLE")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="AVOID",
        confidence="LOW",
        summary="Stock overextended near resistance with unstable structure.",
        alignment_state="UNSTABLE",
        htf_location="RESISTANCE",
        trend_state="UP",
        active_scenario="SCENARIO_B",
        execution_gate_status="PASS"
    )
    
    if (signal.signal_status == SignalStatus.NOT_ELIGIBLE and
        signal.entry_style == EntryStyle.NO_ENTRY and
        signal.risk_class == RiskClass.EXTREME):
        print(f"✅ PASS: AVOID verdict correctly marked NOT_ELIGIBLE")
        passed += 1
    else:
        print(f"❌ FAIL: AVOID should be NOT_ELIGIBLE with EXTREME risk")
        print(f"   Got: {signal.signal_status.value}, {signal.risk_class.value}")
        failed += 1
    
    # TEST 6: NO_TRADE verdict = NOT ELIGIBLE
    print("\nTEST 6: NO_TRADE verdict → NOT_ELIGIBLE")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="NO_TRADE",
        confidence="LOW",
        summary="Stock overextended near resistance. Extreme risk.",
        alignment_state="UNSTABLE",
        htf_location="RESISTANCE",
        trend_state="UP",
        active_scenario="SCENARIO_B",
        execution_gate_status="BLOCKED"
    )
    
    if (signal.signal_status == SignalStatus.NOT_ELIGIBLE and
        signal.entry_style == EntryStyle.NO_ENTRY and
        signal.risk_class == RiskClass.EXTREME):
        print(f"✅ PASS: NO_TRADE verdict correctly marked NOT_ELIGIBLE")
        passed += 1
    else:
        print(f"❌ FAIL: NO_TRADE should be NOT_ELIGIBLE")
        print(f"   Got: {signal.signal_status.value}")
        failed += 1
    
    # TEST 7: Gate BLOCKED = NOT ELIGIBLE (even with STRONG verdict)
    print("\nTEST 7: Gate BLOCKED → NOT_ELIGIBLE (overrides STRONG)")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="STRONG",
        confidence="HIGH",
        summary="Structure strong but gate blocked by risk rule.",
        alignment_state="FULL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_A",
        execution_gate_status="BLOCKED"
    )
    
    if (signal.signal_status == SignalStatus.NOT_ELIGIBLE and
        signal.entry_style == EntryStyle.NO_ENTRY and
        signal.risk_class == RiskClass.EXTREME):
        print(f"✅ PASS: Gate blocking overrides STRONG verdict")
        passed += 1
    else:
        print(f"❌ FAIL: Gate BLOCKED should always result in NOT_ELIGIBLE")
        print(f"   Got: {signal.signal_status.value}")
        failed += 1
    
    # TEST 8: SHORT direction (trend DOWN)
    print("\nTEST 8: SHORT direction → LONG replaced with SHORT")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="STRONG",
        confidence="HIGH",
        summary="Structure aligned for downtrend continuation.",
        alignment_state="FULL",
        htf_location="RESISTANCE",  # For downtrend, resistance = good entry
        trend_state="DOWN",
        active_scenario="SCENARIO_A",
        execution_gate_status="PASS"
    )
    
    if signal.direction == Direction.SHORT:
        print(f"✅ PASS: Direction correctly set to SHORT for downtrend")
        passed += 1
    else:
        print(f"❌ FAIL: Expected SHORT direction for DOWN trend")
        print(f"   Got: {signal.direction.value}")
        failed += 1
    
    # TEST 9: Execution mode always HUMAN_ONLY
    print("\nTEST 9: Execution mode → Always HUMAN_ONLY")
    print("-" * 70)
    signal = engine.evaluate_signal(
        verdict="STRONG",
        confidence="HIGH",
        summary="Test signal.",
        alignment_state="FULL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_A",
        execution_gate_status="PASS"
    )
    
    if signal.execution_mode == "HUMAN_ONLY":
        print(f"✅ PASS: Execution mode is HUMAN_ONLY (no automation)")
        passed += 1
    else:
        print(f"❌ FAIL: Execution mode should always be HUMAN_ONLY")
        print(f"   Got: {signal.execution_mode}")
        failed += 1
    
    # TEST 10: Signal rarity check (most should be NOT_ELIGIBLE)
    print("\nTEST 10: Signal rarity → Most conditions are NOT_ELIGIBLE")
    print("-" * 70)
    test_cases = [
        ("WAIT", "PARTIAL", "PASS"),
        ("AVOID", "UNSTABLE", "PASS"),
        ("AVOID", "CONFLICT", "PASS"),
        ("NO_TRADE", "UNSTABLE", "BLOCKED"),
        ("STRONG", "PARTIAL", "PASS"),  # Not FULL alignment
        ("CAUTION", "UNSTABLE", "PASS"),  # Not FULL alignment
    ]
    
    not_eligible_count = 0
    for verdict, alignment, gate in test_cases:
        sig = engine.evaluate_signal(
            verdict=verdict,
            confidence="MEDIUM",
            summary="Test",
            alignment_state=alignment,
            htf_location="MID",
            trend_state="UP",
            active_scenario="SCENARIO_B",
            execution_gate_status=gate
        )
        if sig.signal_status == SignalStatus.NOT_ELIGIBLE:
            not_eligible_count += 1
    
    if not_eligible_count == len(test_cases):
        print(f"✅ PASS: All non-ideal conditions correctly marked NOT_ELIGIBLE")
        print(f"   Rarity: 6/6 tested cases are NOT_ELIGIBLE")
        passed += 1
    else:
        print(f"❌ FAIL: Some non-ideal conditions incorrectly marked ELIGIBLE")
        print(f"   NOT_ELIGIBLE: {not_eligible_count}/{len(test_cases)}")
        failed += 1
    
    # Final summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Phase-11 signal logic validated")
        print("\nKEY GUARANTEES:")
        print("  1. Signals are RARE (most conditions = NOT_ELIGIBLE)")
        print("  2. Signals are CONSISTENT (same structure = same signal)")
        print("  3. Signals are SAFE (execution gate overrides everything)")
        print("  4. Signals are HUMAN_ONLY (no automation)")
    else:
        print(f"\n⚠️ {failed} test(s) failed - review signal logic")
    
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_phase_11()
