"""
Phase-2C Vision Initialization Test
Tests that VisionClient and ScreenCapture can be initialized when enabled.
"""
import sys
from pathlib import Path
import yaml
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_vision_disabled():
    """Test 1: Verify vision is disabled by default."""
    logger.info("=" * 70)
    logger.info("TEST 1: Vision Disabled by Default")
    logger.info("=" * 70)
    
    with open("config/agent_config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    vision_config = config.get("vision", {})
    enabled = vision_config.get("enabled", False)
    
    logger.info(f"vision.enabled = {enabled}")
    
    if not enabled:
        logger.info("[PASS] Vision is disabled by default")
        return True
    else:
        logger.error("[FAIL] Vision should be disabled by default")
        return False


def test_vision_initialization():
    """Test 2: Verify VisionClient and ScreenCapture can initialize."""
    logger.info("=" * 70)
    logger.info("TEST 2: Vision Component Initialization")
    logger.info("=" * 70)
    
    try:
        from perception.vision_client import VisionClient
        from perception.screen_capture import ScreenCapture
        
        # Test ScreenCapture
        screen_capture = ScreenCapture()
        logger.info("[OK] ScreenCapture initialized")
        
        # Test VisionClient (without calling Ollama)
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        logger.info("[OK] VisionClient initialized")
        
        logger.info("[PASS] Vision components can initialize")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Vision initialization failed: {e}")
        return False


def test_observer_vision_disabled():
    """Test 3: Verify Observer initializes without vision when disabled."""
    logger.info("=" * 70)
    logger.info("TEST 3: Observer Without Vision")
    logger.info("=" * 70)
    
    try:
        from perception.observer import Observer
        
        observer = Observer(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=None,
            screen_capture=None
        )
        
        logger.info("[OK] Observer initialized without vision")
        
        # Check observer doesn't have vision
        has_vision = observer.vision_client is not None
        if not has_vision:
            logger.info("[PASS] Observer has no vision client (as expected)")
            return True
        else:
            logger.error("[FAIL] Observer should not have vision client")
            return False
            
    except Exception as e:
        logger.error(f"[FAIL] Observer initialization failed: {e}")
        return False


def test_observer_with_vision():
    """Test 4: Verify Observer can accept vision components."""
    logger.info("=" * 70)
    logger.info("TEST 4: Observer With Vision")
    logger.info("=" * 70)
    
    try:
        from perception.observer import Observer
        from perception.vision_client import VisionClient
        from perception.screen_capture import ScreenCapture
        
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        screen_capture = ScreenCapture()
        
        observer = Observer(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=vision_client,
            screen_capture=screen_capture
        )
        
        logger.info("[OK] Observer initialized with vision")
        
        # Check observer has vision
        has_vision = observer.vision_client is not None
        has_capture = observer.screen_capture is not None
        
        if has_vision and has_capture:
            logger.info("[PASS] Observer has vision components")
            return True
        else:
            logger.error("[FAIL] Observer missing vision components")
            return False
            
    except Exception as e:
        logger.error(f"[FAIL] Observer with vision failed: {e}")
        return False


def main():
    """Run all vision initialization tests."""
    logger.info("Phase-2C Vision Initialization Test Suite")
    logger.info("")
    
    results = []
    
    # Test 1: Vision disabled by default
    results.append(("Vision disabled by default", test_vision_disabled()))
    
    # Test 2: Vision components can initialize
    results.append(("Vision components initialize", test_vision_initialization()))
    
    # Test 3: Observer without vision
    results.append(("Observer without vision", test_observer_vision_disabled()))
    
    # Test 4: Observer with vision
    results.append(("Observer with vision", test_observer_with_vision()))
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        logger.info(f"{status} {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    logger.info(f"Total: {len(results)} tests")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("")
        logger.info("[SUCCESS] All vision initialization tests passed!")
        logger.info("Phase-2C vision layer is ready for behavioral validation.")
    else:
        logger.error("")
        logger.error(f"[FAILURE] {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
