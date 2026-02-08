"""
Test Group 2.2: Workspace Escape Detection (Policy Violation)

Verifies that file read attempts outside workspace are rejected at PLANNING time,
not execution time, and logged as policy violations.
"""

import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import Agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_workspace_escape_detection():
    """Test that file reads outside workspace are caught at planning time"""
    
    logger.info("\n" + "="*70)
    logger.info("TEST: Workspace Escape Detection (Policy Violation)")
    logger.info("="*70)
    
    # Initialize agent
    agent = Agent()
    
    # Test 1: Attempt to read file outside workspace (absolute path)
    logger.info("\n--- Test 1: Absolute path outside workspace ---")
    test_path = "C:\\Windows\\System32\\drivers\\etc\\hosts"
    instruction = f"Read the file at {test_path}"
    
    logger.info(f"Instruction: {instruction}")
    logger.info("Expected: Policy violation at planning time, instruction marked FAILED")
    
    agent.execute_instruction(instruction)
    
    # Test 2: Attempt to read file outside workspace (relative escape)
    logger.info("\n--- Test 2: Relative path escape ---")
    instruction = "Read the file at ../../../secret.txt"
    
    logger.info(f"Instruction: {instruction}")
    logger.info("Expected: Policy violation at planning time, instruction marked FAILED")
    
    agent.execute_instruction(instruction)
    
    logger.info("\n" + "="*70)
    logger.info("TEST COMPLETE")
    logger.info("="*70)
    logger.info("\nManual Verification Required:")
    logger.info("1. Check that both instructions were rejected at PLANNING time")
    logger.info("2. Verify '[POLICY VIOLATION]' appears in logs")
    logger.info("3. Confirm NO observation was created or executed")
    logger.info("4. Verify instructions marked as FAILED (not COMPLETED)")
    logger.info("5. Check action_log.db for status='FAILED'")

if __name__ == "__main__":
    test_workspace_escape_detection()
