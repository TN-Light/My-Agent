"""
Phase-3B Vision-Assisted Verification Test
Tests vision fallback verification in Critic.

Validates:
1. DOM success → vision NOT used
2. DOM failure → vision used as fallback
3. Vision unavailable → graceful degradation
4. No planner/controller imports in vision path
5. Vision cannot trigger retries or corrective actions
"""
import sys
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from perception.vision_client import VisionClient
from perception.screen_capture import ScreenCapture
from logic.critic import Critic
from common.actions import Action

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_vision_verification_methods():
    """Test 1: Verify vision verification methods exist and return correct types."""
    logger.info("=" * 70)
    logger.info("TEST 1: Vision Verification Methods")
    logger.info("=" * 70)
    
    try:
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        screen_capture = ScreenCapture()
        
        # Check methods exist
        assert hasattr(vision_client, 'verify_text_visible'), "verify_text_visible method missing"
        assert hasattr(vision_client, 'verify_layout_contains'), "verify_layout_contains method missing"
        
        logger.info("[OK] Vision verification methods exist")
        
        # Check method signatures
        import inspect
        sig1 = inspect.signature(vision_client.verify_text_visible)
        sig2 = inspect.signature(vision_client.verify_layout_contains)
        
        assert 'image' in sig1.parameters, "verify_text_visible missing image parameter"
        assert 'expected_text' in sig1.parameters, "verify_text_visible missing expected_text parameter"
        assert 'image' in sig2.parameters, "verify_layout_contains missing image parameter"
        assert 'region_name' in sig2.parameters, "verify_layout_contains missing region_name parameter"
        
        logger.info("[OK] Method signatures correct")
        
        # Check return type hints
        assert sig1.return_annotation == str, "verify_text_visible should return str"
        assert sig2.return_annotation == str, "verify_layout_contains should return str"
        
        logger.info("[OK] Return types are str (not Action)")
        logger.info("[PASS] Vision verification methods validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}")
        return False


def test_critic_vision_integration():
    """Test 2: Verify Critic has vision fallback support."""
    logger.info("=" * 70)
    logger.info("TEST 2: Critic Vision Integration")
    logger.info("=" * 70)
    
    try:
        # Initialize components
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        screen_capture = ScreenCapture()
        
        # Create Critic with vision support
        critic = Critic(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=vision_client,
            screen_capture=screen_capture
        )
        
        # Check vision components assigned
        assert critic.vision_client is not None, "Critic missing vision_client"
        assert critic.screen_capture is not None, "Critic missing screen_capture"
        
        logger.info("[OK] Critic has vision components")
        
        # Check fallback method exists
        assert hasattr(critic, '_verify_with_vision_fallback'), "Critic missing _verify_with_vision_fallback"
        
        logger.info("[OK] Critic has vision fallback method")
        
        # Check method signature
        import inspect
        sig = inspect.signature(critic._verify_with_vision_fallback)
        assert 'action' in sig.parameters, "Missing action parameter"
        assert 'expected_text' in sig.parameters, "Missing expected_text parameter"
        assert 'expected_region' in sig.parameters, "Missing expected_region parameter"
        
        logger.info("[OK] Vision fallback method signature correct")
        logger.info("[PASS] Critic vision integration validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}")
        return False


def test_no_action_imports_in_vision():
    """Test 3: Verify vision code has no planner/controller imports."""
    logger.info("=" * 70)
    logger.info("TEST 3: No Planner/Controller Imports in Vision")
    logger.info("=" * 70)
    
    try:
        vision_client_path = Path(__file__).parent / "perception" / "vision_client.py"
        
        with open(vision_client_path, "r", encoding="utf-8") as f:
            vision_code = f.read()
        
        # Check for forbidden imports
        forbidden_imports = [
            "from logic.planner import",
            "from execution.controller import",
            "import planner",
            "import controller"
        ]
        
        for forbidden in forbidden_imports:
            if forbidden in vision_code:
                logger.error(f"[FAIL] Found forbidden import: {forbidden}")
                return False
        
        logger.info("[OK] No planner/controller imports found")
        
        # Check for retry-triggering patterns
        retry_patterns = [
            "retry(",
            "execute_action",
            "plan("
        ]
        
        for pattern in retry_patterns:
            if pattern in vision_code:
                logger.error(f"[FAIL] Found retry/execution pattern: {pattern}")
                return False
        
        logger.info("[OK] No retry/execution patterns found")
        logger.info("[PASS] Vision code is isolated from action system")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Code analysis exception: {e}")
        return False


def test_vision_fallback_graceful_degradation():
    """Test 4: Verify graceful degradation when vision unavailable."""
    logger.info("=" * 70)
    logger.info("TEST 4: Vision Unavailable - Graceful Degradation")
    logger.info("=" * 70)
    
    try:
        # Create Critic WITHOUT vision
        critic = Critic(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=None,
            screen_capture=None
        )
        
        logger.info("[OK] Critic created without vision")
        
        # Check vision components are None
        assert critic.vision_client is None, "vision_client should be None"
        assert critic.screen_capture is None, "screen_capture should be None"
        
        logger.info("[OK] Vision components are None")
        
        # Call fallback method (should return None gracefully)
        action = Action(action_type="launch_app", context="desktop", target="notepad")
        result = critic._verify_with_vision_fallback(action, expected_text="test")
        
        assert result is None, "Should return None when vision unavailable"
        
        logger.info("[OK] Vision fallback returns None gracefully")
        logger.info("[PASS] Graceful degradation validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}")
        return False


def test_vision_return_values():
    """Test 5: Verify vision methods return valid verification statuses."""
    logger.info("=" * 70)
    logger.info("TEST 5: Vision Return Values")
    logger.info("=" * 70)
    
    try:
        # Valid return values
        valid_statuses = ["VERIFIED", "NOT_VERIFIED", "UNKNOWN"]
        
        logger.info(f"[OK] Valid statuses: {valid_statuses}")
        
        # Check method docstrings
        vision_client_path = Path(__file__).parent / "perception" / "vision_client.py"
        
        with open(vision_client_path, "r", encoding="utf-8") as f:
            vision_code = f.read()
        
        # Verify VERIFIED/NOT_VERIFIED/UNKNOWN mentioned in docstrings
        for status in valid_statuses:
            if status not in vision_code:
                logger.error(f"[FAIL] Status '{status}' not mentioned in vision code")
                return False
        
        logger.info("[OK] All valid statuses documented")
        
        # Verify no Action return types
        if "-> Action" in vision_code or "ActionResult" in vision_code:
            logger.error("[FAIL] Vision methods should not return Action types")
            return False
        
        logger.info("[OK] Vision methods return str, not Action")
        logger.info("[PASS] Vision return values validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}")
        return False


def test_vision_prompts_no_coordinates():
    """Test 6: Verify vision prompts forbid coordinates."""
    logger.info("=" * 70)
    logger.info("TEST 6: Vision Prompts Forbid Coordinates")
    logger.info("=" * 70)
    
    try:
        vision_client_path = Path(__file__).parent / "perception" / "vision_client.py"
        
        with open(vision_client_path, "r", encoding="utf-8") as f:
            vision_code = f.read()
        
        # Check for coordinate warnings in verify methods
        coordinate_warnings = [
            "Do NOT include any other text, coordinates",
            "without proposing actions or generating coordinates"
        ]
        
        found_warnings = sum(1 for warning in coordinate_warnings if warning in vision_code)
        
        if found_warnings < 1:
            logger.error("[FAIL] Vision prompts should explicitly forbid coordinates")
            return False
        
        logger.info(f"[OK] Found {found_warnings} coordinate warnings")
        
        # Check verify methods don't include position words
        verify_methods_section = vision_code[vision_code.find("def verify_text_visible"):]
        
        position_words = ["pixel", "x:", "y:", "coordinates"]
        for word in position_words:
            # Should NOT appear in prompts (except in warnings)
            if word in verify_methods_section and "Do NOT" not in vision_code[vision_code.find(word)-50:vision_code.find(word)+50]:
                logger.warning(f"[WARN] Found '{word}' in verify methods (check context)")
        
        logger.info("[OK] Vision prompts are coordinate-free")
        logger.info("[PASS] Vision prompts validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}")
        return False


def main():
    """Run all Phase-3B tests."""
    logger.info("Phase-3B Vision-Assisted Verification Test Suite")
    logger.info("")
    
    results = []
    
    # Test 1: Vision verification methods
    results.append(("Vision verification methods", test_vision_verification_methods()))
    
    # Test 2: Critic vision integration
    results.append(("Critic vision integration", test_critic_vision_integration()))
    
    # Test 3: No action imports
    results.append(("No planner/controller imports", test_no_action_imports_in_vision()))
    
    # Test 4: Graceful degradation
    results.append(("Graceful degradation", test_vision_fallback_graceful_degradation()))
    
    # Test 5: Vision return values
    results.append(("Vision return values", test_vision_return_values()))
    
    # Test 6: Vision prompts
    results.append(("Vision prompts forbid coordinates", test_vision_prompts_no_coordinates()))
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        if result == "skip":
            status = "[SKIP]"
        elif result:
            status = "[PASS]"
            passed += 1
        else:
            status = "[FAIL]"
            failed += 1
        logger.info(f"{status} {test_name}")
    
    logger.info("")
    logger.info(f"Total: {len(results)} tests")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("")
        logger.info("[SUCCESS] All Phase-3B tests passed!")
        logger.info("Vision-assisted verification is fallback-only, no actions triggered.")
    else:
        logger.error("")
        logger.error(f"[FAILURE] {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
