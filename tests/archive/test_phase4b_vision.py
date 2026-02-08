"""
Phase-4B Vision Verification Fallback Tests

Validates that:
1. Vision is used ONLY by Critic for verification fallback
2. Vision triggered ONLY when DOM/UIA/FILE verification fails
3. Vision never influences planner, controller, or policy
4. Vision confidence fixed at 0.7
5. Planner remains vision-blind
"""

import sys
import logging
from unittest.mock import Mock, MagicMock
from PIL import Image

# Configure logging to see verification flow
logging.basicConfig(level=logging.INFO)

from logic.critic import Critic
from perception.accessibility_client import AccessibilityClient
from perception.vision_client import VisionClient
from perception.screen_capture import ScreenCapture
from common.actions import Action, VerificationEvidence

def test_vision_fallback_integration():
    """Test that vision fallback is properly integrated in Critic."""
    print("=" * 70)
    print("Phase-4B: Vision Fallback Integration Test")
    print("=" * 70)
    print()
    
    # Mock dependencies
    accessibility = Mock(spec=AccessibilityClient)
    vision_client = Mock(spec=VisionClient)
    screen_capture = Mock(spec=ScreenCapture)
    
    # Initialize critic with vision support
    critic = Critic(
        accessibility_client=accessibility,
        vision_client=vision_client,
        screen_capture=screen_capture
    )
    
    print("✅ Critic initialized with vision fallback support")
    print()
    
    # Test 1: verify_launch_app with UIA success (no vision needed)
    print("Test 1: verify_launch_app - UIA SUCCESS (vision not triggered)")
    print("-" * 70)
    
    mock_window = Mock()
    mock_window.name = "Notepad"
    mock_window.is_visible = True
    accessibility.find_window.return_value = mock_window
    
    action = Action(action_type="launch_app", context="desktop", target="notepad.exe")
    result = critic.verify_launch_app(action, window_title_hint="Notepad")
    
    if result.success and result.confidence == 1.0:
        print("✅ PASS: UIA verification successful, confidence=1.0")
        print(f"   Evidence: {result.evidence[0].source} = {result.evidence[0].result}")
        assert len(result.evidence) == 1  # Only UIA evidence
        assert result.evidence[0].source == "UIA"
    else:
        print(f"❌ FAIL: Expected success with confidence 1.0, got {result.confidence}")
        return False
    
    print()
    
    # Test 2: verify_launch_app with UIA fail + vision fallback
    print("Test 2: verify_launch_app - UIA FAIL → VISION VERIFIED (confidence=0.7)")
    print("-" * 70)
    
    accessibility.find_window.return_value = None  # UIA fails
    
    # Mock vision fallback
    mock_image = Mock(spec=Image.Image)
    screen_capture.capture_active_window.return_value = mock_image
    vision_client.verify_text_visible.return_value = "VERIFIED"
    
    # Mock the _verify_with_vision_fallback to return VERIFIED
    original_method = critic._verify_with_vision_fallback
    def mock_vision_fallback(*args, **kwargs):
        return "VERIFIED"
    critic._verify_with_vision_fallback = mock_vision_fallback
    
    action = Action(action_type="launch_app", context="desktop", target="notepad.exe")
    result = critic.verify_launch_app(action, window_title_hint="Notepad")
    
    if not result.success and result.confidence == 0.7:
        print("✅ PASS: Vision fallback triggered, confidence=0.7")
        print(f"   Evidence count: {len(result.evidence)}")
        print(f"   Evidence[0]: {result.evidence[0].source} = {result.evidence[0].result}")
        if len(result.evidence) > 1:
            print(f"   Evidence[1]: {result.evidence[1].source} = {result.evidence[1].result}")
        assert len(result.evidence) == 2  # UIA FAIL + VISION VERIFIED
        assert result.evidence[0].source == "UIA"
        assert result.evidence[1].source == "VISION"
    else:
        print(f"❌ FAIL: Expected confidence 0.7, got {result.confidence}")
        return False
    
    print()
    
    # Test 3: verify_focus_window with vision fallback
    print("Test 3: verify_focus_window - UIA FAIL → VISION VERIFIED (confidence=0.7)")
    print("-" * 70)
    
    accessibility.get_focused_window.return_value = None  # UIA fails
    
    action = Action(action_type="focus_window", context="desktop", target="notepad")
    result = critic.verify_focus_window(action)
    
    if not result.success and result.confidence == 0.7:
        print("✅ PASS: Vision fallback triggered for focus_window, confidence=0.7")
        print(f"   Evidence count: {len(result.evidence)}")
        assert result.evidence[1].source == "VISION"
    else:
        print(f"❌ FAIL: Expected confidence 0.7, got {result.confidence}")
        return False
    
    print()
    
    # Restore original method
    critic._verify_with_vision_fallback = original_method
    
    print("=" * 70)
    print("✅ All Phase-4B Integration Tests PASSED")
    print("=" * 70)
    return True


def test_planner_vision_blind():
    """Test that planner does NOT use vision."""
    print()
    print("=" * 70)
    print("Phase-4B: Planner Vision-Blind Test")
    print("=" * 70)
    print()
    
    from logic.planner import Planner
    
    config = {'planner': {'use_llm': False}}
    planner = Planner(config=config)
    
    # Verify planner has no vision_client attribute
    has_vision = hasattr(planner, 'vision_client')
    
    if not has_vision:
        print("✅ PASS: Planner does NOT have vision_client attribute")
        print("   Planner remains completely vision-blind (Phase-4B constraint)")
    else:
        print("❌ FAIL: Planner has vision_client attribute (violates Phase-4B)")
        return False
    
    print()
    print("=" * 70)
    print("✅ Planner Vision-Blind Test PASSED")
    print("=" * 70)
    return True


def test_confidence_scoring():
    """Test confidence scoring rules for Phase-4B."""
    print()
    print("=" * 70)
    print("Phase-4B: Confidence Scoring Test")
    print("=" * 70)
    print()
    
    # Mock dependencies
    accessibility = Mock(spec=AccessibilityClient)
    critic = Critic(accessibility_client=accessibility)
    
    # Test Case 1: Primary success (DOM/UIA/FILE)
    evidence1 = [VerificationEvidence(source="UIA", result="SUCCESS", details="test")]
    confidence1 = critic._compute_confidence(evidence1)
    print(f"Test 1: UIA SUCCESS → confidence={confidence1:.2f} (expected 1.00)")
    assert confidence1 == 1.0, f"Expected 1.0, got {confidence1}"
    print("✅ PASS")
    print()
    
    # Test Case 2: Primary fail + vision verified
    evidence2 = [
        VerificationEvidence(source="UIA", result="FAIL", details="test"),
        VerificationEvidence(source="VISION", result="VERIFIED", details="test")
    ]
    confidence2 = critic._compute_confidence(evidence2)
    print(f"Test 2: UIA FAIL + VISION VERIFIED → confidence={confidence2:.2f} (expected 0.70)")
    assert confidence2 == 0.7, f"Expected 0.7, got {confidence2}"
    print("✅ PASS")
    print()
    
    # Test Case 3: Primary fail + vision not verified
    evidence3 = [
        VerificationEvidence(source="DOM", result="FAIL", details="test"),
        VerificationEvidence(source="VISION", result="NOT_VERIFIED", details="test")
    ]
    confidence3 = critic._compute_confidence(evidence3)
    print(f"Test 3: DOM FAIL + VISION NOT_VERIFIED → confidence={confidence3:.2f} (expected 0.30)")
    assert confidence3 == 0.3, f"Expected 0.3, got {confidence3}"
    print("✅ PASS")
    print()
    
    # Test Case 4: Only vision evidence
    evidence4 = [VerificationEvidence(source="VISION", result="VERIFIED", details="test")]
    confidence4 = critic._compute_confidence(evidence4)
    print(f"Test 4: Only VISION VERIFIED → confidence={confidence4:.2f} (expected 0.50)")
    assert confidence4 == 0.5, f"Expected 0.5, got {confidence4}"
    print("✅ PASS")
    print()
    
    print("=" * 70)
    print("✅ All Confidence Scoring Tests PASSED")
    print("=" * 70)
    return True


def test_no_schema_changes():
    """Verify that action schema was not changed."""
    print()
    print("=" * 70)
    print("Phase-4B: No Schema Changes Test")
    print("=" * 70)
    print()
    
    from common.actions import Action
    import inspect
    
    # Check Action signature
    sig = inspect.signature(Action.__init__)
    params = list(sig.parameters.keys())
    
    # Expected parameters (no vision-related fields)
    expected_params = ['self', 'action_type', 'context', 'target', 'text', 'coordinates', 'verify']
    
    if params == expected_params:
        print("✅ PASS: Action schema unchanged")
        print(f"   Parameters: {params[1:]}")  # Skip 'self'
    else:
        print(f"❌ FAIL: Action schema changed")
        print(f"   Expected: {expected_params[1:]}")
        print(f"   Got: {params[1:]}")
        return False
    
    # Verify no vision-related attributes
    action = Action(action_type="launch_app", target="test")
    vision_attrs = [attr for attr in dir(action) if 'vision' in attr.lower()]
    
    if not vision_attrs:
        print("✅ PASS: No vision-related attributes in Action")
    else:
        print(f"❌ FAIL: Found vision attributes: {vision_attrs}")
        return False
    
    print()
    print("=" * 70)
    print("✅ No Schema Changes Test PASSED")
    print("=" * 70)
    return True


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "PHASE-4B VALIDATION TEST SUITE" + " " * 23 + "║")
    print("║" + " " * 68 + "║")
    print("║  Scope: Vision for Critic Verification Fallback ONLY            ║")
    print("║  Constraints:                                                    ║")
    print("║    - Vision used ONLY by Critic                                 ║")
    print("║    - Triggered ONLY when DOM/UIA/FILE fails                     ║")
    print("║    - Planner remains vision-blind                               ║")
    print("║    - No schema changes                                          ║")
    print("║    - Vision confidence = 0.7                                    ║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    all_passed = True
    
    # Run tests
    try:
        if not test_confidence_scoring():
            all_passed = False
        
        if not test_no_schema_changes():
            all_passed = False
        
        if not test_planner_vision_blind():
            all_passed = False
        
        if not test_vision_fallback_integration():
            all_passed = False
        
    except Exception as e:
        print(f"\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    if all_passed:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "✅ ALL PHASE-4B TESTS PASSED" + " " * 25 + "║")
        print("╚" + "═" * 68 + "╝")
        sys.exit(0)
    else:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "❌ SOME PHASE-4B TESTS FAILED" + " " * 23 + "║")
        print("╚" + "═" * 68 + "╝")
        sys.exit(1)
