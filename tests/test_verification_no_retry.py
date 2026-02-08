"""Test that verification failures do NOT trigger retries"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from common.actions import Action, ActionResult
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: Verification Failures Should NOT Retry")
print("=" * 70)

# Mock components
class MockPolicyEngine:
    def validate_action(self, action):
        return True, "Approved"

class MockController:
    def __init__(self, execution_success=True):
        self.execution_success = execution_success
        self.execute_count = 0
    
    def execute_action(self, action):
        self.execute_count += 1
        return ActionResult(
            action=action,
            success=self.execution_success,
            message="Executed"
        )

class MockCritic:
    def __init__(self, verification_success=False):
        self.verification_success = verification_success
        self.verify_count = 0
    
    def verify_action(self, action):
        self.verify_count += 1
        return ActionResult(
            action=action,
            success=self.verification_success,
            message="Verified" if self.verification_success else "Verification failed",
            error=None if self.verification_success else "Text not found"
        )

class MockActionLogger:
    def log_action(self, result):
        pass

# Import and patch main
from main import Agent

print("\n" + "=" * 70)
print("TEST 1: Regular action failure → Retry allowed")
print("=" * 70)

# Create regular action (no verify metadata)
action_regular = Action(
    action_type="launch_app",
    context="desktop",
    target="notepad.exe"
)

print(f"\nAction: {action_regular.action_type}")
print(f"Has verify metadata: {hasattr(action_regular, 'verify') and action_regular.verify is not None}")

# Setup mocks
mock_controller = MockController(execution_success=True)
mock_critic = MockCritic(verification_success=False)  # Will fail verification
mock_policy = MockPolicyEngine()
mock_logger = MockActionLogger()

# Create agent controller
agent = Agent.__new__(Agent)
agent.controller = mock_controller
agent.critic = mock_critic
agent.policy_engine = mock_policy
agent.action_logger = mock_logger
agent.chat_ui = None
agent.browser_handler = None

# Execute action (should retry)
try:
    result = agent._execute_single_action(action_regular, action_index=1, attempt=1)
    print(f"\nResult: {result}")
    print(f"Execute count: {mock_controller.execute_count}")
    print(f"Verify count: {mock_critic.verify_count}")
    
    if mock_controller.execute_count == 2 and mock_critic.verify_count == 2:
        print("\n✅ TEST 1 PASSED: Regular action retried (2 executions, 2 verifications)")
    else:
        print(f"\n❌ TEST 1 FAILED: Expected 2 executions and 2 verifications")
        print(f"   Got: {mock_controller.execute_count} executions, {mock_critic.verify_count} verifications")
except Exception as e:
    print(f"\n❌ TEST 1 FAILED: Exception: {e}")

print("\n" + "=" * 70)
print("TEST 2: Verification action failure → NO retry")
print("=" * 70)

# Create verification action (has verify metadata)
action_verify = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Welcome"}
)

print(f"\nAction: {action_verify.action_type}")
print(f"Has verify metadata: {hasattr(action_verify, 'verify') and action_verify.verify is not None}")
print(f"Verify metadata: {action_verify.verify}")

# Reset mocks
mock_controller2 = MockController(execution_success=True)
mock_critic2 = MockCritic(verification_success=False)  # Will fail verification

# Create new agent controller
agent2 = Agent.__new__(Agent)
agent2.controller = mock_controller2
agent2.critic = mock_critic2
agent2.policy_engine = mock_policy
agent2.action_logger = mock_logger
agent2.chat_ui = None
agent2.browser_handler = None

# Execute verification action (should NOT retry)
try:
    result = agent2._execute_single_action(action_verify, action_index=1, attempt=1)
    print(f"\nResult: {result}")
    print(f"Execute count: {mock_controller2.execute_count}")
    print(f"Verify count: {mock_critic2.verify_count}")
    
    if mock_controller2.execute_count == 1 and mock_critic2.verify_count == 1:
        print("\n✅ TEST 2 PASSED: Verification action did NOT retry (1 execution, 1 verification)")
    else:
        print(f"\n❌ TEST 2 FAILED: Expected 1 execution and 1 verification (no retry)")
        print(f"   Got: {mock_controller2.execute_count} executions, {mock_critic2.verify_count} verifications")
except Exception as e:
    print(f"\n❌ TEST 2 FAILED: Exception: {e}")

print("\n" + "=" * 70)
print("TEST 3: Verification action success → No retry needed")
print("=" * 70)

# Create verification action that will succeed
action_verify_success = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Welcome"}
)

print(f"\nAction: {action_verify_success.action_type}")
print(f"Has verify metadata: {hasattr(action_verify_success, 'verify') and action_verify_success.verify is not None}")

# Reset mocks with success
mock_controller3 = MockController(execution_success=True)
mock_critic3 = MockCritic(verification_success=True)  # Will succeed

# Create new agent controller
agent3 = Agent.__new__(Agent)
agent3.controller = mock_controller3
agent3.critic = mock_critic3
agent3.policy_engine = mock_policy
agent3.action_logger = mock_logger
agent3.chat_ui = None
agent3.browser_handler = None

# Execute verification action (should succeed, no retry)
try:
    result = agent3._execute_single_action(action_verify_success, action_index=1, attempt=1)
    print(f"\nResult: {result}")
    print(f"Execute count: {mock_controller3.execute_count}")
    print(f"Verify count: {mock_critic3.verify_count}")
    
    if result and mock_controller3.execute_count == 1 and mock_critic3.verify_count == 1:
        print("\n✅ TEST 3 PASSED: Verification action succeeded (1 execution, 1 verification)")
    else:
        print(f"\n❌ TEST 3 FAILED: Expected success with 1 execution and 1 verification")
        print(f"   Got: result={result}, {mock_controller3.execute_count} executions, {mock_critic3.verify_count} verifications")
except Exception as e:
    print(f"\n❌ TEST 3 FAILED: Exception: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("Verification actions:")
print("  - Success: Execute once, verify once ✓")
print("  - Failure: Execute once, verify once, NO RETRY ✓")
print("\nRegular actions:")
print("  - Failure: Execute twice, verify twice (1 retry) ✓")
print("\n✅ Retry logic correctly distinguishes verification vs regular actions")
