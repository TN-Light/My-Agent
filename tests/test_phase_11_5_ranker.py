"""
Phase-11.5 Test Suite: Signal Ranker

Tests deterministic signal ranking and rarity enforcement.
"""

from logic.signal_ranker import SignalRanker, RankedSignal
from logic.signal_eligibility import (
    SignalContract, SignalStatus, SignalType, Direction,
    EntryStyle, TimeframeClass, RiskClass
)


def test_signal_ranker():
    """Test signal ranking logic"""
    
    ranker = SignalRanker()
    
    print("=" * 80)
    print("PHASE-11.5: SIGNAL RANKER TEST SUITE")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # Create test signals
    signal_strong_low = SignalContract(
        signal_status=SignalStatus.ELIGIBLE,
        signal_type=SignalType.TREND_CONTINUATION,
        direction=Direction.LONG,
        entry_style=EntryStyle.IMMEDIATE_OK,
        timeframe=TimeframeClass.SWING,
        risk_class=RiskClass.LOW,
        execution_mode="HUMAN_ONLY",
        verdict="STRONG",
        confidence="HIGH",
        summary="Perfect setup",
        alignment_state="FULL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_A"
    )
    
    signal_caution_medium = SignalContract(
        signal_status=SignalStatus.ELIGIBLE,
        signal_type=SignalType.TREND_CONTINUATION,
        direction=Direction.LONG,
        entry_style=EntryStyle.PULLBACK_ONLY,
        timeframe=TimeframeClass.SWING,
        risk_class=RiskClass.MEDIUM,
        execution_mode="HUMAN_ONLY",
        verdict="CAUTION",
        confidence="MEDIUM",
        summary="Extended setup",
        alignment_state="FULL",
        htf_location="RESISTANCE",
        trend_state="UP",
        active_scenario="SCENARIO_A"
    )
    
    signal_not_eligible = SignalContract(
        signal_status=SignalStatus.NOT_ELIGIBLE,
        signal_type=None,
        direction=Direction.LONG,
        entry_style=EntryStyle.NO_ENTRY,
        timeframe=TimeframeClass.SWING,
        risk_class=RiskClass.HIGH,
        execution_mode="HUMAN_ONLY",
        verdict="WAIT",
        confidence="MEDIUM",
        summary="Not ready",
        alignment_state="PARTIAL",
        htf_location="MID",
        trend_state="UP",
        active_scenario="SCENARIO_B"
    )
    
    # TEST 1: Only ELIGIBLE signals ranked
    print("\nTEST 1: Filtering → Only ELIGIBLE signals considered")
    print("-" * 80)
    signals = [
        ("STOCK1", signal_strong_low),
        ("STOCK2", signal_not_eligible),
        ("STOCK3", signal_caution_medium)
    ]
    
    ranked = ranker.rank_signals(signals, max_results=10)
    
    if len(ranked) == 2 and all(rs.signal_contract.signal_status == SignalStatus.ELIGIBLE for rs in ranked):
        print(f"✅ PASS: Filtered to {len(ranked)} ELIGIBLE signals (from 3 total)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected 2 ELIGIBLE signals")
        print(f"   Got: {len(ranked)}")
        failed += 1
    
    # TEST 2: STRONG scores higher than CAUTION
    print("\nTEST 2: Ranking → STRONG > CAUTION")
    print("-" * 80)
    signals = [
        ("STOCK_CAUTION", signal_caution_medium),
        ("STOCK_STRONG", signal_strong_low)
    ]
    
    ranked = ranker.rank_signals(signals, max_results=10)
    
    if ranked[0].instrument == "STOCK_STRONG" and ranked[0].rank_score > ranked[1].rank_score:
        print(f"✅ PASS: STRONG ranked first (score={ranked[0].rank_score:.0f})")
        print(f"   CAUTION ranked second (score={ranked[1].rank_score:.0f})")
        passed += 1
    else:
        print(f"❌ FAIL: Expected STRONG > CAUTION")
        print(f"   Got: {ranked[0].instrument} (score={ranked[0].rank_score:.0f})")
        failed += 1
    
    # TEST 3: LOW risk adds bonus
    print("\nTEST 3: Risk modifier → LOW risk adds +20 points")
    print("-" * 80)
    score_low, _ = ranker._calculate_score(signal_strong_low)
    score_medium, _ = ranker._calculate_score(signal_caution_medium)
    
    # STRONG base=100, LOW risk=+20, IMMEDIATE_OK=+10 = 130
    # CAUTION base=70, MEDIUM risk=+10, PULLBACK_ONLY=0 = 80
    if score_low == 130 and score_medium == 80:
        print(f"✅ PASS: LOW risk signal scores {score_low:.0f}")
        print(f"   MEDIUM risk signal scores {score_medium:.0f}")
        passed += 1
    else:
        print(f"❌ FAIL: Expected scores 130 and 80")
        print(f"   Got: {score_low:.0f} and {score_medium:.0f}")
        failed += 1
    
    # TEST 4: IMMEDIATE_OK adds bonus
    print("\nTEST 4: Entry style → IMMEDIATE_OK adds +10 points")
    print("-" * 80)
    # Already tested above, verify the bonus
    if signal_strong_low.entry_style == EntryStyle.IMMEDIATE_OK:
        score, reason = ranker._calculate_score(signal_strong_low)
        if "immediate entry OK" in reason:
            print(f"✅ PASS: IMMEDIATE_OK entry style adds bonus")
            print(f"   Reason: {reason}")
            passed += 1
        else:
            print(f"❌ FAIL: IMMEDIATE_OK bonus not reflected in reason")
            failed += 1
    else:
        print(f"❌ FAIL: Test signal not configured correctly")
        failed += 1
    
    # TEST 5: Signal rarity enforcement (≤20%)
    print("\nTEST 5: Rarity enforcement → Max 20% of scanned")
    print("-" * 80)
    
    # Create 10 ELIGIBLE signals (100% eligible)
    many_signals = [(f"STOCK{i}", signal_strong_low) for i in range(10)]
    
    ranked = ranker.rank_signals(many_signals, max_results=10)
    
    expected_max = max(1, int(len(many_signals) * 0.2))  # 20% of 10 = 2
    if len(ranked) <= expected_max:
        print(f"✅ PASS: Enforced rarity - kept {len(ranked)} of {len(many_signals)} (≤20%)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected max {expected_max}, got {len(ranked)}")
        failed += 1
    
    # TEST 6: max_results limit
    print("\nTEST 6: Result limit → Respects max_results parameter")
    print("-" * 80)
    signals = [(f"STOCK{i}", signal_strong_low) for i in range(5)]
    
    ranked = ranker.rank_signals(signals, max_results=2)
    
    if len(ranked) <= 2:
        print(f"✅ PASS: Limited to {len(ranked)} results (max_results=2)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected max 2 results, got {len(ranked)}")
        failed += 1
    
    # TEST 7: Sorting by risk (LOW before MEDIUM)
    print("\nTEST 7: Secondary sort → LOW risk before MEDIUM risk")
    print("-" * 80)
    
    # Same verdict, different risk
    signal_strong_medium = SignalContract(
        signal_status=SignalStatus.ELIGIBLE,
        signal_type=SignalType.TREND_CONTINUATION,
        direction=Direction.LONG,
        entry_style=EntryStyle.IMMEDIATE_OK,
        timeframe=TimeframeClass.SWING,
        risk_class=RiskClass.MEDIUM,  # Changed to MEDIUM
        execution_mode="HUMAN_ONLY",
        verdict="STRONG",
        confidence="HIGH",
        summary="Strong but medium risk",
        alignment_state="FULL",
        htf_location="RESISTANCE",
        trend_state="UP",
        active_scenario="SCENARIO_A"
    )
    
    signals = [
        ("STOCK_MED_RISK", signal_strong_medium),
        ("STOCK_LOW_RISK", signal_strong_low)
    ]
    
    ranked = ranker.rank_signals(signals, max_results=10)
    
    if ranked[0].instrument == "STOCK_LOW_RISK":
        print(f"✅ PASS: LOW risk ranked before MEDIUM risk (same verdict)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected LOW risk first")
        print(f"   Got: {ranked[0].instrument}")
        failed += 1
    
    # TEST 8: Deterministic scoring
    print("\nTEST 8: Determinism → Same signal = same score")
    print("-" * 80)
    
    score1, _ = ranker._calculate_score(signal_strong_low)
    score2, _ = ranker._calculate_score(signal_strong_low)
    
    if score1 == score2:
        print(f"✅ PASS: Deterministic scoring (score={score1:.0f})")
        passed += 1
    else:
        print(f"❌ FAIL: Scores differ: {score1:.0f} vs {score2:.0f}")
        failed += 1
    
    # TEST 9: Confidence priority (tertiary sort)
    print("\nTEST 9: Tertiary sort → HIGH confidence before MEDIUM")
    print("-" * 80)
    priority_high = ranker._confidence_priority("HIGH")
    priority_medium = ranker._confidence_priority("MEDIUM")
    priority_low = ranker._confidence_priority("LOW")
    
    if priority_high > priority_medium > priority_low:
        print(f"✅ PASS: Confidence priority correct (HIGH={priority_high}, MED={priority_medium}, LOW={priority_low})")
        passed += 1
    else:
        print(f"❌ FAIL: Confidence priority incorrect")
        failed += 1
    
    # TEST 10: Empty input handling
    print("\nTEST 10: Edge case → Empty input returns empty list")
    print("-" * 80)
    
    ranked = ranker.rank_signals([], max_results=10)
    
    if len(ranked) == 0:
        print(f"✅ PASS: Empty input handled correctly")
        passed += 1
    else:
        print(f"❌ FAIL: Expected empty list, got {len(ranked)} items")
        failed += 1
    
    # Final summary
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Signal ranker validated")
        print("\nKEY FEATURES:")
        print("  1. Deterministic scoring (no randomness)")
        print("  2. Signal rarity enforcement (≤20%)")
        print("  3. Multi-level sorting (score → risk → confidence)")
        print("  4. STRONG > CAUTION > others")
    else:
        print(f"\n⚠️ {failed} test(s) failed - review ranker logic")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_signal_ranker()
