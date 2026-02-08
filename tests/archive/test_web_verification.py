"""
Test Group 4: Web Verification Tests (Phase-2A)

Tests browser handler lifecycle and critic web verification logic.
Specifically Test 4.3 validates httpbin form typing with retry support.
"""

import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import Agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_web_form_typing():
    """
    Test 4.3: httpbin form typing with proper lifecycle and verification.
    
    Validates:
    1. Browser remains open across multiple actions
    2. Retry doesn't close event loop
    3. Web verification checks element.value, not visibility
    """
    logger.info("\n" + "="*70)
    logger.info("TEST 4.3: httpbin Form Typing (Web Verification)")
    logger.info("="*70)
    
    # Initialize agent
    agent = Agent()
    
    # Test: Navigate to httpbin form and type text
    logger.info("\n--- Step 1: Navigate to httpbin forms ---")
    instruction1 = "Navigate to https://httpbin.org/forms/post"
    agent.execute_instruction(instruction1)
    
    logger.info("\n--- Step 2: Type customer name ---")
    instruction2 = "Type 'John Smith' into input[name='custname']"
    agent.execute_instruction(instruction2)
    
    logger.info("\n--- Step 3: Type telephone ---")
    instruction3 = "Type '555-1234' into input[name='custtel']"
    agent.execute_instruction(instruction3)
    
    logger.info("\n" + "="*70)
    logger.info("TEST 4.3 COMPLETE")
    logger.info("="*70)
    logger.info("\nManual Verification Required:")
    logger.info("1. Check that all 3 instructions completed successfully")
    logger.info("2. Verify browser remained open between actions")
    logger.info("3. Confirm no 'Event loop is closed' errors")
    logger.info("4. Verify web verification checked element.value, not visibility")
    logger.info("5. Check logs show '[OK] Verified: Element ... value = ...'")


if __name__ == "__main__":
    test_web_form_typing()
