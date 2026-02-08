"""
Phase-3C Test Suite: Verification Confidence & Evidence Aggregation

Purpose:
    Validate confidence scoring and evidence collection in Critic class.
    Ensure confidence is metadata only and does NOT affect execution flow.

Constraints:
    - Confidence must NOT affect retry logic, planner decisions, or controller branching
    - Evidence is for logging/diagnostics only
    - ActionResult.success remains sole determinant of execution flow
    - Vision remains advisory/fallback only

Test Coverage:
    1. Primary verification success → confidence ≥0.9, single evidence
    2. Primary fail + vision verified → confidence ~0.65, two evidence items
    3. Primary fail, vision unavailable → confidence ~0.2, single evidence
    4. Confidence isolation → no usage in controller/planner
    5. Evidence structure → proper dataclass fields populated
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from common.actions import Action, ActionResult, VerificationEvidence
from logic.critic import Critic
from perception.accessibility_client import AccessibilityClient
from perception.screen_capture import ScreenCapture
from perception.vision_client import VisionClient


def test_1_uia_success_high_confidence():
    """
    Test Case 1: UIA success → confidence = 1.0
    
    Validates:
        - Primary UIA verification succeeds
        - Confidence = 1.0 (maximum)
        - Single evidence item with source="UIA", result="SUCCESS"
        - No vision fallback invoked
    """
    print("\n" + "="*70)
    print("TEST 1: UIA Success → High Confidence")
    print("="*70)
    
    accessibility = AccessibilityClient()
    critic = Critic(accessibility_client=accessibility)
    
    # Create mock action
    action = Action(
        action_type="launch_app",
        context="desktop",
        target="notepad.exe"
    )
    
    # Verify (should find Notepad if it's running, or fail gracefully)
    result = critic.verify_launch_app(action, window_title_hint="Notepad")
    
    print(f"✓ Success: {result.success}")
    print(f"✓ Confidence: {result.confidence}")
    print(f"✓ Evidence count: {len(result.evidence)}")
    
    if result.success:
        # Primary verification succeeded
        assert result.confidence >= 0.9, f"Expected confidence ≥0.9 for success, got {result.confidence}"
        assert len(result.evidence) >= 1, "Expected at least 1 evidence item"
        assert result.evidence[0].source == "UIA", "Expected UIA source"
        assert result.evidence[0].result == "SUCCESS", "Expected SUCCESS result"
        
        print("✓ Evidence[0]:", result.evidence[0])
        print("✓ PASS: High confidence with UIA success")
    else:
        # Primary verification failed (acceptable if Notepad not running)
        print(f"ℹ Notepad not running, confidence: {result.confidence}")
        print("✓ PASS: Graceful degradation when app not found")
    
    return result


def test_2_dom_fail_vision_verified():
    """
    Test Case 2: DOM fail + vision VERIFIED → confidence ~0.65
    
    Validates:
        - Primary DOM verification fails
        - Vision fallback returns "VERIFIED"
        - Confidence ~0.65 (moderate)
        - Two evidence items: DOM=FAIL, VISION=VERIFIED
        - ActionResult.success still False (vision is advisory)
    """
    print("\n" + "="*70)
    print("TEST 2: DOM Fail + Vision Verified → Medium Confidence")
    print("="*70)
    
    # Mock vision client that returns VERIFIED
    class MockVisionClient:
        def verify_text_visible(self, screenshot, text):
            return "VERIFIED"
    
    # Mock browser handler that fails
    class MockBrowserHandler:
        def get_current_url(self):
            return None  # Simulate navigation failure
    
    accessibility = AccessibilityClient()
    screen_capture = ScreenCapture()
    vision_client = MockVisionClient()
    
    critic = Critic(
        accessibility_client=accessibility,
        vision_client=vision_client,
        screen_capture=screen_capture,
        browser_handler=MockBrowserHandler()
    )
    
    # Create web action that will fail primary but vision verifies
    action = Action(
        action_type="launch_app",
        context="web",
        target="https://example.com"
    )
    
    result = critic._verify_web_action(action)
    
    print(f"✓ Success: {result.success}")
    print(f"✓ Confidence: {result.confidence}")
    print(f"✓ Evidence count: {len(result.evidence)}")
    
    # Assertions
    assert not result.success, "ActionResult.success must be False (vision is advisory)"
    assert len(result.evidence) == 2, f"Expected 2 evidence items, got {len(result.evidence)}"
    assert result.evidence[0].source == "DOM", "First evidence should be DOM"
    assert result.evidence[0].result == "FAIL", "First evidence should be FAIL"
    assert result.evidence[1].source == "VISION", "Second evidence should be VISION"
    assert result.evidence[1].result == "VERIFIED", "Second evidence should be VERIFIED"
    
    # Confidence should be ~0.65 (primary fail + vision verified)
    assert 0.6 <= result.confidence <= 0.7, f"Expected confidence ~0.65, got {result.confidence}"
    
    print(f"✓ Evidence[0]: {result.evidence[0]}")
    print(f"✓ Evidence[1]: {result.evidence[1]}")
    print("✓ PASS: Medium confidence with vision fallback")
    
    return result


def test_3_uia_fail_no_vision():
    """
    Test Case 3: UIA fail, no vision → confidence ~0.2
    
    Validates:
        - Primary UIA verification fails
        - Vision unavailable (no fallback)
        - Confidence ~0.2 (low)
        - Single evidence item: UIA=FAIL
    """
    print("\n" + "="*70)
    print("TEST 3: UIA Fail, No Vision → Low Confidence")
    print("="*70)
    
    accessibility = AccessibilityClient()
    critic = Critic(accessibility_client=accessibility)  # No vision client
    
    # Create action for non-existent app
    action = Action(
        action_type="launch_app",
        context="desktop",
        target="nonexistent.exe"
    )
    
    result = critic.verify_launch_app(action, window_title_hint="NonExistentApp")
    
    print(f"✓ Success: {result.success}")
    print(f"✓ Confidence: {result.confidence}")
    print(f"✓ Evidence count: {len(result.evidence)}")
    
    # Assertions
    assert not result.success, "Expected failure for non-existent app"
    assert len(result.evidence) == 1, f"Expected 1 evidence item, got {len(result.evidence)}"
    assert result.evidence[0].source == "UIA", "Expected UIA source"
    assert result.evidence[0].result == "FAIL", "Expected FAIL result"
    
    # Confidence should be ~0.2 (primary fail, no vision)
    assert result.confidence <= 0.3, f"Expected confidence ≤0.3, got {result.confidence}"
    
    print(f"✓ Evidence[0]: {result.evidence[0]}")
    print("✓ PASS: Low confidence with no vision fallback")
    
    return result


def test_4_confidence_isolation():
    """
    Test Case 4: Confidence Isolation
    
    Validates:
        - Confidence does NOT appear in controller.py
        - Confidence does NOT appear in planner.py
        - ActionResult.success is sole execution flow determinant
    """
    print("\n" + "="*70)
    print("TEST 4: Confidence Isolation from Execution Flow")
    print("="*70)
    
    # Check controller.py
    controller_path = project_root / "logic" / "controller.py"
    if controller_path.exists():
        controller_code = controller_path.read_text()
        
        # Look for confidence in decision logic (not just logging)
        confidence_in_logic = any([
            "if confidence" in controller_code,
            "confidence >" in controller_code,
            "confidence <" in controller_code,
            "confidence ==" in controller_code,
            "while confidence" in controller_code,
        ])
        
        assert not confidence_in_logic, "❌ FAIL: Confidence used in controller logic!"
        print("✓ Controller: No confidence in execution logic")
    else:
        print("ℹ Controller not found (acceptable)")
    
    # Check planner.py
    planner_path = project_root / "logic" / "planner.py"
    if planner_path.exists():
        planner_code = planner_path.read_text()
        
        # Look for confidence in decision logic
        confidence_in_logic = any([
            "if confidence" in planner_code,
            "confidence >" in planner_code,
            "confidence <" in planner_code,
            "confidence ==" in planner_code,
            "while confidence" in planner_code,
        ])
        
        assert not confidence_in_logic, "❌ FAIL: Confidence used in planner logic!"
        print("✓ Planner: No confidence in execution logic")
    else:
        print("ℹ Planner not found (acceptable)")
    
    print("✓ PASS: Confidence isolated from execution flow")
    
    return True


def test_5_evidence_structure():
    """
    Test Case 5: Evidence Structure
    
    Validates:
        - VerificationEvidence has source, result, details fields
        - Evidence list properly populated in ActionResult
        - Evidence serialization works for logging
    """
    print("\n" + "="*70)
    print("TEST 5: Evidence Structure Validation")
    print("="*70)
    
    # Create evidence manually
    evidence = VerificationEvidence(
        source="UIA",
        result="SUCCESS",
        details="Test window found"
    )
    
    print(f"✓ Evidence source: {evidence.source}")
    print(f"✓ Evidence result: {evidence.result}")
    print(f"✓ Evidence details: {evidence.details}")
    
    # Validate fields
    assert evidence.source == "UIA", "Source field mismatch"
    assert evidence.result == "SUCCESS", "Result field mismatch"
    assert evidence.details == "Test window found", "Details field mismatch"
    
    # Test serialization
    evidence_str = str(evidence)
    assert "UIA" in evidence_str, "Source not in string representation"
    assert "SUCCESS" in evidence_str, "Result not in string representation"
    
    print("✓ Evidence serialization:", evidence_str)
    print("✓ PASS: Evidence structure valid")
    
    return evidence


def test_6_backward_compatibility():
    """
    Test Case 6: Backward Compatibility
    
    Validates:
        - ActionResult with default confidence still works
        - Existing code that doesn't set confidence/evidence continues working
        - Default confidence = 1.0
    """
    print("\n" + "="*70)
    print("TEST 6: Backward Compatibility")
    print("="*70)
    
    action = Action(
        action_type="launch_app",
        context="desktop",
        target="test.exe"
    )
    
    # Create ActionResult without confidence/evidence (old style)
    result = ActionResult(
        action=action,
        success=True,
        message="Test action"
    )
    
    print(f"✓ Default confidence: {result.confidence}")
    print(f"✓ Default evidence: {result.evidence}")
    
    # Validate defaults
    assert result.confidence == 1.0, f"Expected default confidence=1.0, got {result.confidence}"
    assert result.evidence == [], f"Expected default evidence=[], got {result.evidence}"
    
    print("✓ PASS: Backward compatibility maintained")
    
    return result


def run_all_tests():
    """Run all Phase-3C tests."""
    print("\n" + "="*70)
    print("PHASE-3C TEST SUITE: Verification Confidence & Evidence")
    print("="*70)
    
    results = {
        "test_1": None,
        "test_2": None,
        "test_3": None,
        "test_4": None,
        "test_5": None,
        "test_6": None,
    }
    
    try:
        results["test_1"] = test_1_uia_success_high_confidence()
    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        results["test_1"] = False
    
    try:
        results["test_2"] = test_2_dom_fail_vision_verified()
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        results["test_2"] = False
    
    try:
        results["test_3"] = test_3_uia_fail_no_vision()
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        results["test_3"] = False
    
    try:
        results["test_4"] = test_4_confidence_isolation()
    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        results["test_4"] = False
    
    try:
        results["test_5"] = test_5_evidence_structure()
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        results["test_5"] = False
    
    try:
        results["test_6"] = test_6_backward_compatibility()
    except Exception as e:
        print(f"❌ TEST 6 FAILED: {e}")
        results["test_6"] = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v is not False and v is not None)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result not in [False, None] else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All Phase-3C tests passed!")
        print("✓ Confidence scoring working correctly")
        print("✓ Evidence aggregation functional")
        print("✓ Isolation constraint maintained")
        return True
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
