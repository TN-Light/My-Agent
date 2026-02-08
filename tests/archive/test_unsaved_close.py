import logging
import time
import sys
from execution.controller import Controller
from perception.accessibility_client import AccessibilityClient
from logic.policy_engine import PolicyEngine
from common.actions import Action

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_unsaved")

def run_test():
    print(">>> INITIALIZING CONTROLLER")
    # Initialize components
    policy = PolicyEngine("config/policy.yaml")
    accessibility = AccessibilityClient()
    controller = Controller(policy, accessibility_client=accessibility)
    
    # 1. Launch Notepad
    print(">>> 1. LAUNCHING NOTEPAD")
    action_launch = Action(action_type="launch_app", target="notepad.exe")
    controller.execute_action(action_launch)
    
    # Wait for full launch
    time.sleep(3.0)
    
    # 2. Touch using a more reliable method (Type many chars to ensure dirty)
    print(">>> 2. CREATING UNSAVED STATE")
    action_focus = Action(action_type="focus_window", target="Notepad")
    controller.execute_action(action_focus)
    time.sleep(1.0)

    # Use a string that definitely triggers dirty state if it lands
    dirty_text = "DIRTY_STATE_TEST_" * 5
    action_type = Action(action_type="type_text", text=dirty_text)
    controller.execute_action(action_type)
    time.sleep(2.0)
    
    # 3. Close App (Should trigger dialog)
    print(">>> 3. CLOSING APP (EXPECT INTERVENTION)")
    action_close = Action(action_type="close_app", target="notepad.exe")
    
    print("\n" + "="*50)
    print("PREPARE TO INTERACT WITH THE TERMINAL")
    print("Select option '2' (Don't Save) when prompted.")
    print("="*50 + "\n")
    
    start_time = time.time()
    result = controller.execute_action(action_close)
    end_time = time.time()
    
    print(f"\n>>> RESULT:")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Error: {result.error}")
    print(f"Duration: {end_time - start_time:.2f}s")
    
    # Verify it's actually closed
    is_open = accessibility.is_window_visible("Notepad")
    print(f"Notepad Visible: {is_open}")
    
    if not is_open and result.success:
        if end_time - start_time < 0.5:
             print("❌ TEST FAILED: Closed too quickly. Likely clean close (no dialog).")
        else:
             print("✅ TEST PASSED: Closed successfully after handling dialog.")
    else:
        print("❌ TEST FAILED: Notepad still open or result failed.")

if __name__ == "__main__":
    run_test()
