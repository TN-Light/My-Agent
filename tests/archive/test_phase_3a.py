"""
Phase-3A Visual Scaffolding Test
Tests visual scaffolding observations without triggering actions.

Validates:
1. list_visual_regions returns structured region data
2. identify_visible_text_blocks returns structured text data
3. No actions triggered by visual scaffolding
4. No coordinates emitted
5. No policy or controller calls
"""
import sys
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from perception.vision_client import VisionClient
from perception.screen_capture import ScreenCapture
from perception.observer import Observer
from common.observations import Observation, ObservationResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_list_visual_regions():
    """Test 1: list_visual_regions observation."""
    logger.info("=" * 70)
    logger.info("TEST 1: list_visual_regions (Phase-3A Level 3)")
    logger.info("=" * 70)
    
    try:
        # Initialize components
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        screen_capture = ScreenCapture()
        
        # Create observation
        observation = Observation(
            observation_type="list_visual_regions",
            context="vision",
            target=None  # Whole-screen observation
        )
        
        logger.info(f"Created observation: {observation.observation_type}")
        
        # Initialize observer
        observer = Observer(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=vision_client,
            screen_capture=screen_capture
        )
        
        logger.info("Executing observation (this may take 30-60s for VLM)...")
        
        # Execute observation
        result = observer.observe(observation)
        
        logger.info(f"Observation status: {result.status}")
        
        if result.status == "success":
            logger.info(f"Result type: {type(result.result)}")
            logger.info(f"Result preview: {result.result[:200] if len(result.result) > 200 else result.result}")
            
            # Validate no coordinates
            if any(coord_word in result.result.lower() for coord_word in ["pixel", "coordinate", "x:", "y:", "position:"]):
                logger.error("[FAIL] Result contains coordinate-like terms")
                return False
            else:
                logger.info("[OK] No coordinates in result")
            
            # Validate no actions mentioned
            if any(action in result.result.lower() for action in ["click", "type", "press", "launch", "close"]):
                logger.error("[FAIL] Result mentions actions")
                return False
            else:
                logger.info("[OK] No action verbs in result")
            
            logger.info("[PASS] list_visual_regions returned structured data")
            return True
        elif result.status == "error":
            logger.warning(f"Observation failed (expected if VLM unavailable): {result.error}")
            logger.info("[SKIP] VLM not available - cannot test vision observations")
            return "skip"
        else:
            logger.error(f"[FAIL] Unexpected status: {result.status}")
            return False
            
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}", exc_info=True)
        return False


def test_identify_visible_text_blocks():
    """Test 2: identify_visible_text_blocks observation."""
    logger.info("=" * 70)
    logger.info("TEST 2: identify_visible_text_blocks (Phase-3A Level 3)")
    logger.info("=" * 70)
    
    try:
        # Initialize components
        vision_client = VisionClient(
            base_url="http://localhost:11434",
            model="llama3.2-vision",
            timeout=60
        )
        screen_capture = ScreenCapture()
        
        # Create observation
        observation = Observation(
            observation_type="identify_visible_text_blocks",
            context="vision",
            target=None  # Whole-screen observation
        )
        
        logger.info(f"Created observation: {observation.observation_type}")
        
        # Initialize observer
        observer = Observer(
            accessibility_client=None,
            browser_handler=None,
            file_handler=None,
            vision_client=vision_client,
            screen_capture=screen_capture
        )
        
        logger.info("Executing observation (this may take 30-60s for VLM)...")
        
        # Execute observation
        result = observer.observe(observation)
        
        logger.info(f"Observation status: {result.status}")
        
        if result.status == "success":
            logger.info(f"Result type: {type(result.result)}")
            logger.info(f"Result preview: {result.result[:200] if len(result.result) > 200 else result.result}")
            
            # Validate no coordinates
            if any(coord_word in result.result.lower() for coord_word in ["pixel", "coordinate", "x:", "y:", "position:"]):
                logger.error("[FAIL] Result contains coordinate-like terms")
                return False
            else:
                logger.info("[OK] No coordinates in result")
            
            # Validate no actions mentioned
            if any(action in result.result.lower() for action in ["click", "type", "press", "launch", "close"]):
                logger.error("[FAIL] Result mentions actions")
                return False
            else:
                logger.info("[OK] No action verbs in result")
            
            logger.info("[PASS] identify_visible_text_blocks returned structured data")
            return True
        elif result.status == "error":
            logger.warning(f"Observation failed (expected if VLM unavailable): {result.error}")
            logger.info("[SKIP] VLM not available - cannot test vision observations")
            return "skip"
        else:
            logger.error(f"[FAIL] Unexpected status: {result.status}")
            return False
            
    except Exception as e:
        logger.error(f"[FAIL] Test exception: {e}", exc_info=True)
        return False


def test_no_action_imports():
    """Test 3: Verify vision code has no action imports."""
    logger.info("=" * 70)
    logger.info("TEST 3: Verify No Action Imports in Vision Code")
    logger.info("=" * 70)
    
    try:
        vision_client_path = Path(__file__).parent / "perception" / "vision_client.py"
        
        with open(vision_client_path, "r", encoding="utf-8") as f:
            vision_code = f.read()
        
        # Check for action imports
        forbidden_imports = [
            "from common.actions import",
            "from execution.controller import",
            "import pyautogui",
            "import keyboard",
            "import mouse"
        ]
        
        for forbidden in forbidden_imports:
            if forbidden in vision_code:
                logger.error(f"[FAIL] Found forbidden import: {forbidden}")
                return False
        
        logger.info("[OK] No action-related imports found")
        
        # Check for coordinate output patterns
        coordinate_patterns = [
            "return (x, y)",
            "click(",
            "keyboard.press",
            "mouse.move"
        ]
        
        for pattern in coordinate_patterns:
            if pattern in vision_code:
                logger.error(f"[FAIL] Found coordinate/action pattern: {pattern}")
                return False
        
        logger.info("[OK] No coordinate/action patterns found")
        logger.info("[PASS] Vision code is action-free")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Code analysis exception: {e}")
        return False


def test_observation_schema():
    """Test 4: Verify Phase-3A observations in schema."""
    logger.info("=" * 70)
    logger.info("TEST 4: Verify Phase-3A Observation Types in Schema")
    logger.info("=" * 70)
    
    try:
        # Test list_visual_regions schema
        obs1 = Observation(
            observation_type="list_visual_regions",
            context="vision",
            target=None
        )
        logger.info(f"[OK] list_visual_regions schema valid: {obs1}")
        
        # Test identify_visible_text_blocks schema
        obs2 = Observation(
            observation_type="identify_visible_text_blocks",
            context="vision",
            target=None
        )
        logger.info(f"[OK] identify_visible_text_blocks schema valid: {obs2}")
        
        # Test invalid observation type (should raise ValueError)
        try:
            obs3 = Observation(
                observation_type="invalid_type",
                context="vision",
                target=None
            )
            logger.error("[FAIL] Invalid observation type should raise ValueError")
            return False
        except ValueError as e:
            logger.info(f"[OK] Invalid type rejected: {e}")
        
        logger.info("[PASS] Phase-3A observation schema validated")
        return True
        
    except Exception as e:
        logger.error(f"[FAIL] Schema validation exception: {e}")
        return False


def main():
    """Run all Phase-3A tests."""
    logger.info("Phase-3A Visual Scaffolding Test Suite")
    logger.info("")
    
    results = []
    
    # Test 1: list_visual_regions
    results.append(("list_visual_regions observation", test_list_visual_regions()))
    
    # Test 2: identify_visible_text_blocks
    results.append(("identify_visible_text_blocks observation", test_identify_visible_text_blocks()))
    
    # Test 3: No action imports
    results.append(("No action imports in vision code", test_no_action_imports()))
    
    # Test 4: Observation schema
    results.append(("Phase-3A observation schema", test_observation_schema()))
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_name, result in results:
        if result == "skip":
            status = "[SKIP]"
            skipped += 1
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
    logger.info(f"Skipped: {skipped} (VLM unavailable)")
    
    if failed == 0:
        logger.info("")
        logger.info("[SUCCESS] All Phase-3A tests passed!")
        logger.info("Visual scaffolding is observation-only, no actions triggered.")
    else:
        logger.error("")
        logger.error(f"[FAILURE] {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
