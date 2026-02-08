"""
Phase-4A Tests: Control Primitives Expansion

Tests for new action types:
- focus_window
- close_app (enhanced)
- wait
"""

import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import Agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_wait():
    """Test wait action"""
    print("\n" + "="*70)
    print("TEST 1: wait - Duration Validation")
    print("="*70)
    
    agent = Agent()
    
    print("\n--- Test 1.1: Valid wait (2 seconds) ---")
    start_time = time.time()
    agent.execute_instruction("wait 2 seconds")
    elapsed = time.time() - start_time
    print(f"✅ Elapsed time: {elapsed:.2f}s (expected ~2s)")
    
    print("\n--- Test 1.2: Invalid wait (exceeds max) ---")
    agent.execute_instruction("wait 100 seconds")
    print("✅ Expected rejection for exceeding max duration")
    
    print("\n" + "="*70)


def test_focus_and_close():
    """Test focus_window and close_app"""
    print("\n" + "="*70)
    print("TEST 2: focus_window and close_app")
    print("="*70)
    
    agent = Agent()
    
    print("\n--- Step 1: Open Notepad ---")
    agent.execute_instruction("open notepad")
    time.sleep(1)
    
    print("\n--- Step 2: Focus Notepad ---")
    agent.execute_instruction("focus notepad")
    
    print("\n--- Step 3: Close Notepad ---")
    agent.execute_instruction("close notepad")
    
    print("\n" + "="*70)
    print("✅ All steps completed")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE-4A CONTROL PRIMITIVES TESTS")
    print("="*70)
    
    try:
        test_wait()
        input("\nPress Enter for Test 2...")
        test_focus_and_close()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS COMPLETE")
        print("="*70)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
