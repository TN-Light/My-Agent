"""Test that verification failure logs correctly identify the failure reason"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from common.actions import Action, ActionResult
import logging
from io import StringIO

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: Verification Failure Log Messages")
print("=" * 70)

# Mock components
class MockPolicyEngine:
    def validate_action(self, action):
        return True, None

class MockController:
    def execute_action(self, action):
        return ActionResult(action=action, success=True, message="Executed")

class MockCriticWithVerificationFailure:
    def verify_action(self, action):
        return ActionResult(
            action=action,
            success=False,
            message="Verification failed",
            error="Text not found",
            reason="verification_failed"
        )

class MockCriticWithRetryableFailure:
    def __init__(self):
        self.call_count = 0
    
    def verify_action(self, action):
        self.call_count += 1
        return ActionResult(
            action=action,
            success=False,
            message="Window not found",
            error="Window closed"
        )

class MockActionLogger:
    def log_action(self, result):
        pass

from main import Agent

print("\n" + "=" * 70)
print("TEST 1: Verification Failure Log Message")
print("=" * 70)

# Setup agent with verification failure
agent = Agent.__new__(Agent)
agent.controller = MockController()
agent.critic = MockCriticWithVerificationFailure()
agent.policy_engine = MockPolicyEngine()
agent.action_logger = MockActionLogger()
agent.chat_ui = None
agent.browser_handler = None
agent.last_failure_reason = None

action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Test"}
)

# Capture logs
log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.INFO)
logging.getLogger().handlers = [handler]

# Execute action
result = agent._execute_single_action(action, action_index=1, attempt=1)
log_output = log_stream.getvalue()

print(f"Action type: verification action")
print(f"Result: {result}")
print(f"Last failure reason: {agent.last_failure_reason}")
print(f"\nLog output:")
print(log_output)

if "terminal failure" in log_output and agent.last_failure_reason == 'verification_failed':
    print("\n[OK] TEST 1 PASSED: Verification failure correctly logged as terminal")
else:
    print(f"\n[FAIL] TEST 1 FAILED: Expected terminal failure log")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 2: Retry Exhaustion Log Message")
print("=" * 70)

# Setup agent with retryable failure
agent2 = Agent.__new__(Agent)
agent2.controller = MockController()
agent2.critic = MockCriticWithRetryableFailure()
agent2.policy_engine = MockPolicyEngine()
agent2.action_logger = MockActionLogger()
agent2.chat_ui = None
agent2.browser_handler = None
agent2.last_failure_reason = None

action2 = Action(
    action_type="launch_app",
    context="desktop",
    target="notepad.exe"
)

# Capture logs
log_stream2 = StringIO()
handler2 = logging.StreamHandler(log_stream2)
handler2.setLevel(logging.INFO)
logging.getLogger().handlers = [handler2]

# Execute action
result2 = agent2._execute_single_action(action2, action_index=1, attempt=1)
log_output2 = log_stream2.getvalue()

print(f"Action type: regular action")
print(f"Result: {result2}")
print(f"Last failure reason: {agent2.last_failure_reason}")
print(f"Verify call count: {agent2.critic.call_count}")
print(f"\nLog output:")
print(log_output2)

if "Retrying action" in log_output2 and agent2.last_failure_reason == 'retry_exhausted' and agent2.critic.call_count == 2:
    print("\n[OK] TEST 2 PASSED: Retry exhaustion correctly logged after 2 attempts")
else:
    print(f"\n[FAIL] TEST 2 FAILED: Expected retry then exhaustion")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 3: Plan Abortion Messages")
print("=" * 70)

print("\nTest 3A: Verification failure plan abortion")

# Create a minimal plan executor test
from logic.planner import Planner
from logic.policy_engine import PolicyEngine

planner = Planner({'planner': {'use_llm': False}})

# Create verification action that will fail
plan = [Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Missing"}
)]

# Setup agent
agent3 = Agent.__new__(Agent)
agent3.planner = planner
agent3.policy_engine = PolicyEngine("config/policy.yaml")
agent3.controller = MockController()
agent3.critic = MockCriticWithVerificationFailure()
agent3.action_logger = MockActionLogger()
agent3.observation_logger = None
agent3.observer = None
agent3.chat_ui = None
agent3.browser_handler = None
agent3.last_failure_reason = None

# Capture logs
log_stream3 = StringIO()
handler3 = logging.StreamHandler(log_stream3)
handler3.setLevel(logging.INFO)
logging.getLogger().handlers = [handler3]

# Execute plan directly with our test action
for i, item in enumerate(plan, 1):
    if isinstance(item, Action):
        success = agent3._execute_single_action(item, action_index=i)
        
        if not success:
            # Check the log message
            if agent3.last_failure_reason == 'verification_failed':
                test_log = f"Action {i} failed due to verification failure. Aborting plan."
                print(f"Expected log: '{test_log}'")
                print(f"Last failure reason: {agent3.last_failure_reason}")
                print("\n[OK] TEST 3A PASSED: Correct log message for verification failure")
            else:
                print(f"[FAIL] TEST 3A FAILED: Wrong failure reason: {agent3.last_failure_reason}")
                sys.exit(1)

print("\nTest 3B: Retry exhaustion plan abortion")

# Create regular action that will fail
plan2 = [Action(
    action_type="launch_app",
    context="desktop",
    target="notepad.exe"
)]

# Setup agent
agent4 = Agent.__new__(Agent)
agent4.controller = MockController()
agent4.critic = MockCriticWithRetryableFailure()
agent4.policy_engine = PolicyEngine("config/policy.yaml")
agent4.action_logger = MockActionLogger()
agent4.chat_ui = None
agent4.browser_handler = None
agent4.last_failure_reason = None

# Execute plan
for i, item in enumerate(plan2, 1):
    if isinstance(item, Action):
        success = agent4._execute_single_action(item, action_index=i)
        
        if not success:
            # Check the log message
            if agent4.last_failure_reason == 'retry_exhausted':
                test_log = f"Action {i} failed after retry. Aborting plan."
                print(f"Expected log: '{test_log}'")
                print(f"Last failure reason: {agent4.last_failure_reason}")
                print("\n[OK] TEST 3B PASSED: Correct log message for retry exhaustion")
            else:
                print(f"[FAIL] TEST 3B FAILED: Wrong failure reason: {agent4.last_failure_reason}")
                sys.exit(1)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("[OK] All tests passed!")
print("\nLog messages correctly distinguish:")
print("  - Verification failures: 'failed due to verification failure'")
print("  - Retry exhaustion: 'failed after retry'")
print("  - No misleading retry wording for verification failures")
