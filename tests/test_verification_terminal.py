"""Test that verification failures are properly marked as terminal with reason='verification_failed'"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from common.actions import Action, ActionResult
from logic.critic import Critic
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: Verification Failures Marked as Terminal")
print("=" * 70)

# Mock components
class MockAccessibilityClient:
    def find_window(self, title):
        return None
    def get_focused_window(self):
        return None

class MockBrowserHandler:
    def __init__(self, page_text=None):
        self.page_text = page_text
    
    def get_page_text(self):
        return self.page_text

class MockVisionClient:
    def __init__(self, result="NOT_VERIFIED"):
        self.result = result
    
    def verify_text_visible(self, screenshot, expected_text):
        return self.result

class MockScreenCapture:
    def capture_active_window(self):
        return b"screenshot_data"
    
    def capture_full_screen(self):
        return b"screenshot_data"

print("\n" + "=" * 70)
print("TEST 1: DOM Failure -> reason='verification_failed'")
print("=" * 70)

accessibility = MockAccessibilityClient()
browser_handler = MockBrowserHandler(page_text="Different content")
critic = Critic(accessibility, browser_handler=browser_handler)

action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Expected Text"}
)

result = critic.verify_action(action)

print(f"\nAction: verify text_visible")
print(f"Expected text: 'Expected Text'")
print(f"Page content: 'Different content'")
print(f"Result success: {result.success}")
print(f"Result reason: {result.reason}")
print(f"Result message: {result.message}")

if not result.success and result.reason == "verification_failed":
    print("\n[OK] TEST 1 PASSED: Verification failure has reason='verification_failed'")
else:
    print(f"\n[FAIL] TEST 1 FAILED: Expected reason='verification_failed', got '{result.reason}'")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 2: Vision NOT_VERIFIED -> reason='verification_failed'")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Other content")
vision_client = MockVisionClient(result="NOT_VERIFIED")
screen_capture = MockScreenCapture()
critic = Critic(accessibility, browser_handler=browser_handler,
                vision_client=vision_client, screen_capture=screen_capture)

action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Missing Text"}
)

result = critic.verify_action(action)

print(f"\nAction: verify text_visible")
print(f"Expected text: 'Missing Text'")
print(f"Vision result: NOT_VERIFIED")
print(f"Result success: {result.success}")
print(f"Result reason: {result.reason}")
print(f"Result message: {result.message}")

if not result.success and result.reason == "verification_failed":
    print("\n[OK] TEST 2 PASSED: Vision NOT_VERIFIED has reason='verification_failed'")
else:
    print(f"\n[FAIL] TEST 2 FAILED: Expected reason='verification_failed', got '{result.reason}'")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 3: Vision UNKNOWN -> reason='verification_failed'")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Some content")
vision_client = MockVisionClient(result="UNKNOWN")
critic = Critic(accessibility, browser_handler=browser_handler,
                vision_client=vision_client, screen_capture=screen_capture)

action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Uncertain Text"}
)

result = critic.verify_action(action)

print(f"\nAction: verify text_visible")
print(f"Expected text: 'Uncertain Text'")
print(f"Vision result: UNKNOWN")
print(f"Result success: {result.success}")
print(f"Result reason: {result.reason}")
print(f"Result message: {result.message}")

if not result.success and result.reason == "verification_failed":
    print("\n[OK] TEST 3 PASSED: Vision UNKNOWN has reason='verification_failed'")
else:
    print(f"\n[FAIL] TEST 3 FAILED: Expected reason='verification_failed', got '{result.reason}'")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 4: Verification Success -> reason=None")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Welcome to our site")
critic = Critic(accessibility, browser_handler=browser_handler)

action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Welcome"}
)

result = critic.verify_action(action)

print(f"\nAction: verify text_visible")
print(f"Expected text: 'Welcome'")
print(f"Page content: 'Welcome to our site'")
print(f"Result success: {result.success}")
print(f"Result reason: {result.reason}")
print(f"Result message: {result.message}")

if result.success and result.reason is None:
    print("\n[OK] TEST 4 PASSED: Verification success has reason=None")
else:
    print(f"\n[FAIL] TEST 4 FAILED: Expected success with reason=None, got success={result.success}, reason='{result.reason}'")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 5: Main.py treats reason='verification_failed' as terminal")
print("=" * 70)

from main import Agent

# Mock components for Agent
class MockPolicyEngine:
    def validate_action(self, action):
        return True, None

class MockController:
    def __init__(self):
        self.execute_count = 0
    
    def execute_action(self, action):
        self.execute_count += 1
        return ActionResult(
            action=action,
            success=True,
            message="Executed"
        )

class MockCriticWithReason:
    def __init__(self):
        self.verify_count = 0
    
    def verify_action(self, action):
        self.verify_count += 1
        return ActionResult(
            action=action,
            success=False,
            message="Verification failed",
            error="Text not found",
            reason="verification_failed"  # TERMINAL
        )

class MockActionLogger:
    def log_action(self, result):
        pass

# Create verification action
action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Test"}
)

# Setup agent
agent = Agent.__new__(Agent)
agent.controller = MockController()
agent.critic = MockCriticWithReason()
agent.policy_engine = MockPolicyEngine()
agent.action_logger = MockActionLogger()
agent.chat_ui = None
agent.browser_handler = None

# Execute action
result = agent._execute_single_action(action, action_index=1, attempt=1)

print(f"\nAction: verification action with verify metadata")
print(f"Critic returns: reason='verification_failed'")
print(f"Execute count: {agent.controller.execute_count}")
print(f"Verify count: {agent.critic.verify_count}")
print(f"Result: {result}")

if agent.controller.execute_count == 1 and agent.critic.verify_count == 1 and not result:
    print("\n[OK] TEST 5 PASSED: reason='verification_failed' prevents retry (1 exec, 1 verify)")
else:
    print(f"\n[FAIL] TEST 5 FAILED: Expected 1 exec, 1 verify, False result")
    print(f"   Got: {agent.controller.execute_count} exec, {agent.critic.verify_count} verify, result={result}")
    sys.exit(1)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("[OK] All tests passed!")
print("\nVerification failures properly marked:")
print("  - reason='verification_failed' set on all NOT_VERIFIED results")
print("  - reason='verification_failed' set on all UNKNOWN results")
print("  - reason=None on successful verifications")
print("  - Main.py checks reason field and treats as terminal")
print("  - No retries for verification_failed actions")
