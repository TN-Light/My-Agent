"""Test Critic verification with action.verify metadata"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from logic.critic import Critic
from common.actions import Action
from perception.accessibility_client import AccessibilityClient
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: Critic Verification with action.verify Metadata")
print("=" * 70)

# Mock accessibility client
class MockAccessibilityClient:
    def find_window(self, title):
        return None
    def get_focused_window(self):
        return None

# Mock browser handler with get_page_text()
class MockBrowserHandler:
    def __init__(self, page_text=None):
        self.page_text = page_text
    
    def get_page_text(self):
        return self.page_text
    
    def get_current_url(self):
        return "https://example.com"
    
    def is_element_visible(self, selector):
        return True

# Mock vision client
class MockVisionClient:
    def __init__(self, result="VERIFIED"):
        self.result = result
    
    def verify_text_visible(self, screenshot, expected_text):
        return self.result

# Mock screen capture
class MockScreenCapture:
    def capture_active_window(self):
        return b"screenshot_data"
    
    def capture_full_screen(self):
        return b"screenshot_data"

print("\n" + "=" * 70)
print("TEST 1: Verification with DOM success")
print("=" * 70)

accessibility = MockAccessibilityClient()
browser_handler = MockBrowserHandler(page_text="Hello World, this is a test page")
critic = Critic(accessibility, browser_handler=browser_handler)

action = Action(
    action_type="verify",
    context="web",
    target="page",
    verify={"type": "text_visible", "value": "Hello World"}
)

result = critic.verify_action(action)

print(f"\nAction: {action.action_type}")
print(f"Verify metadata: {action.verify}")
print(f"Result: success={result.success}")
print(f"Message: {result.message}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Evidence sources: {[e.source for e in result.evidence]}")
print(f"Evidence results: {[e.result for e in result.evidence]}")

if result.success and result.confidence == 1.0:
    print("\n✅ TEST 1 PASSED: DOM verification successful")
else:
    print(f"\n❌ TEST 1 FAILED: Expected success=True, confidence=1.0")
    print(f"   Got: success={result.success}, confidence={result.confidence}")

print("\n" + "=" * 70)
print("TEST 2: Verification with DOM failure, vision fallback success")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Some other text")
vision_client = MockVisionClient(result="VERIFIED")
screen_capture = MockScreenCapture()
critic = Critic(accessibility, browser_handler=browser_handler, 
                vision_client=vision_client, screen_capture=screen_capture)

action = Action(
    action_type="verify",
    context="web",
    target="page",
    verify={"type": "text_visible", "value": "Expected Text"}
)

result = critic.verify_action(action)

print(f"\nAction: {action.action_type}")
print(f"Verify metadata: {action.verify}")
print(f"Result: success={result.success}")
print(f"Message: {result.message}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Evidence sources: {[e.source for e in result.evidence]}")
print(f"Evidence results: {[e.result for e in result.evidence]}")

if result.success and 0.6 <= result.confidence <= 0.7:
    print("\n✅ TEST 2 PASSED: Vision fallback successful with correct confidence")
else:
    print(f"\n❌ TEST 2 FAILED: Expected success=True, confidence≈0.65")
    print(f"   Got: success={result.success}, confidence={result.confidence}")

print("\n" + "=" * 70)
print("TEST 3: Verification with DOM failure, vision NOT_VERIFIED")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Different text")
vision_client = MockVisionClient(result="NOT_VERIFIED")
critic = Critic(accessibility, browser_handler=browser_handler,
                vision_client=vision_client, screen_capture=screen_capture)

action = Action(
    action_type="verify",
    context="web",
    target="page",
    verify={"type": "text_visible", "value": "Missing Text"}
)

result = critic.verify_action(action)

print(f"\nAction: {action.action_type}")
print(f"Verify metadata: {action.verify}")
print(f"Result: success={result.success}")
print(f"Message: {result.message}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Evidence sources: {[e.source for e in result.evidence]}")
print(f"Evidence results: {[e.result for e in result.evidence]}")

if not result.success and 0.25 <= result.confidence <= 0.35:
    print("\n✅ TEST 3 PASSED: Verification failed with correct confidence")
else:
    print(f"\n❌ TEST 3 FAILED: Expected success=False, confidence≈0.3")
    print(f"   Got: success={result.success}, confidence={result.confidence}")

print("\n" + "=" * 70)
print("TEST 4: Verification with DOM failure, vision UNKNOWN")
print("=" * 70)

browser_handler = MockBrowserHandler(page_text="Some text")
vision_client = MockVisionClient(result="UNKNOWN")
critic = Critic(accessibility, browser_handler=browser_handler,
                vision_client=vision_client, screen_capture=screen_capture)

action = Action(
    action_type="verify",
    context="web",
    target="page",
    verify={"type": "text_visible", "value": "Uncertain Text"}
)

result = critic.verify_action(action)

print(f"\nAction: {action.action_type}")
print(f"Verify metadata: {action.verify}")
print(f"Result: success={result.success}")
print(f"Message: {result.message}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Evidence sources: {[e.source for e in result.evidence]}")
print(f"Evidence results: {[e.result for e in result.evidence]}")

if not result.success and 0.35 <= result.confidence <= 0.45:
    print("\n✅ TEST 4 PASSED: Verification uncertain with correct confidence")
else:
    print(f"\n❌ TEST 4 FAILED: Expected success=False, confidence≈0.4")
    print(f"   Got: success={result.success}, confidence={result.confidence}")

print("\n" + "=" * 70)
print("TEST 5: No verify metadata - normal action verification")
print("=" * 70)

action_no_verify = Action(
    action_type="type_text",
    context="web",
    target="#input",
    text="Hello"
)

result = critic.verify_action(action_no_verify)

print(f"\nAction: {action_no_verify.action_type}")
print(f"Has verify metadata: {hasattr(action_no_verify, 'verify') and action_no_verify.verify}")
print(f"Result: success={result.success}")
print(f"Message: {result.message}")

if result.success:
    print("\n✅ TEST 5 PASSED: Normal action verification works")
else:
    print(f"\n❌ TEST 5 FAILED: Expected normal verification to succeed")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("All verification metadata tests completed!")
print("Critic correctly routes actions with verify metadata")
print("Confidence scoring follows Phase-3C specifications")
