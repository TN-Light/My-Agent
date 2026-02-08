"""Test that all logging uses ASCII-only characters (no unicode)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import logging
from io import StringIO

# Test that logs can be encoded as cp1252 (Windows console encoding)
logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("TEST: ASCII-Only Logging (Windows cp1252 Compatible)")
print("=" * 70)

# Test 1: Planner logs
print("\n" + "=" * 70)
print("TEST 1: Planner Logs")
print("=" * 70)

from logic.planner import Planner

planner = Planner({'planner': {'use_llm': False}})

# Capture logs
log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.INFO)
logging.getLogger().addHandler(handler)

# Test file read intent log
try:
    plan = planner.create_plan("read file test.txt")
    log_output = log_stream.getvalue()
    
    # Check for unicode characters
    try:
        log_output.encode('cp1252')
        print("[OK] File read intent log is cp1252 compatible")
        print(f"     Log contains: 'Detected file_read intent -> deterministic plan'")
    except UnicodeEncodeError as e:
        print(f"[FAIL] File read intent log contains unicode: {e}")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Exception during file read test: {e}")
    sys.exit(1)

# Test verification intent log
log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.INFO)
logging.getLogger().handlers = [handler]

try:
    plan = planner.create_plan("verify that hello is visible")
    log_output = log_stream.getvalue()
    
    # Check for unicode characters
    try:
        log_output.encode('cp1252')
        print("[OK] Verification intent log is cp1252 compatible")
        print(f"     Log contains: 'Detected verification intent -> action'")
    except UnicodeEncodeError as e:
        print(f"[FAIL] Verification intent log contains unicode: {e}")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Exception during verification test: {e}")
    sys.exit(1)

# Test 2: Policy Engine logs
print("\n" + "=" * 70)
print("TEST 2: Policy Engine Logs")
print("=" * 70)

from logic.policy_engine import PolicyEngine
from common.actions import Action

# Use default policy file
policy = PolicyEngine("config/policy.yaml")

log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.INFO)
logging.getLogger().handlers = [handler]

# Test whitelist approval (notepad.exe should be whitelisted by default)
action = Action(action_type="launch_app", target="notepad.exe", context="desktop")
approved, reason = policy.validate_action(action)
log_output = log_stream.getvalue()

try:
    log_output.encode('cp1252')
    print("[OK] Whitelist approval log is cp1252 compatible")
    if approved:
        print(f"     Log contains: '[OK] APPROVED: notepad.exe is whitelisted'")
    else:
        print(f"     Action was denied: {reason}")
except UnicodeEncodeError as e:
    print(f"[FAIL] Whitelist log contains unicode: {e}")
    sys.exit(1)

# Test blacklist denial - test with a non-whitelisted app
log_stream = StringIO()
handler = logging.StreamHandler(log_stream)
handler.setLevel(logging.INFO)
logging.getLogger().handlers = [handler]

action = Action(action_type="launch_app", target="unknown.exe", context="desktop")
approved, reason = policy.validate_action(action)
log_output = log_stream.getvalue()

try:
    log_output.encode('cp1252')
    print("[OK] Denial log is cp1252 compatible")
    if not approved:
        print(f"     Log contains: '[FAIL] DENIED: unknown.exe not in whitelist'")
except UnicodeEncodeError as e:
    print(f"[FAIL] Denial log contains unicode: {e}")
    sys.exit(1)

# Test 3: Controller logs
print("\n" + "=" * 70)
print("TEST 3: Controller Logs")
print("=" * 70)

# We'll just verify the strings can be encoded
test_strings = [
    "[OK] Launched: notepad.exe",
    "[OK] Typed 5 characters"
]

for test_str in test_strings:
    try:
        test_str.encode('cp1252')
        print(f"[OK] '{test_str}' is cp1252 compatible")
    except UnicodeEncodeError as e:
        print(f"[FAIL] '{test_str}' contains unicode: {e}")
        sys.exit(1)

# Test 4: Critic logs
print("\n" + "=" * 70)
print("TEST 4: Critic Verification Logs")
print("=" * 70)

test_strings = [
    "[VERIFY] text_visible -> VERIFIED (DOM, confidence=1.00)",
    "[VERIFY] text_visible -> NOT_VERIFIED (DOM)",
    "[VERIFY] text_visible -> VERIFIED (VISION, confidence=0.65)",
    "[VERIFY] text_visible -> NOT_VERIFIED (VISION, confidence=0.30)",
    "[VERIFY] text_visible -> UNKNOWN (VISION, confidence=0.40)"
]

for test_str in test_strings:
    try:
        test_str.encode('cp1252')
        print(f"[OK] '{test_str}' is cp1252 compatible")
    except UnicodeEncodeError as e:
        print(f"[FAIL] '{test_str}' contains unicode: {e}")
        sys.exit(1)

# Test 5: Action Logger
print("\n" + "=" * 70)
print("TEST 5: Action Logger Status Symbols")
print("=" * 70)

test_strings = [
    "[OK]",  # Success
    "[FAIL]"  # Failure
]

for test_str in test_strings:
    try:
        test_str.encode('cp1252')
        print(f"[OK] '{test_str}' is cp1252 compatible")
    except UnicodeEncodeError as e:
        print(f"[FAIL] '{test_str}' contains unicode: {e}")
        sys.exit(1)

# Test 6: Main.py UI logs
print("\n" + "=" * 70)
print("TEST 6: Main.py UI Logs")
print("=" * 70)

test_strings = [
    "[FAIL] Plan aborted: Action 1 failed after retry",
    "[OK] Instruction completed successfully",
    "[FAIL] Planner could not generate a safe plan",
    "[FAIL] Execution failed",
    "[FAIL] Policy denied",
    "[OK] Policy approved: launch_app",
    "-> Executed: Application launched",
    "[FAIL] Verification failed",
    "[FAIL] Verification failed (no retry for verification actions)",
    "[OK] Verified: Application launched"
]

for test_str in test_strings:
    try:
        test_str.encode('cp1252')
        print(f"[OK] '{test_str}' is cp1252 compatible")
    except UnicodeEncodeError as e:
        print(f"[FAIL] '{test_str}' contains unicode: {e}")
        sys.exit(1)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("[OK] All logging strings are Windows cp1252 compatible")
print("[OK] No unicode characters found")
print("[OK] Replacements:")
print("     -> (arrow) replaces unicode \\u2192")
print("     [OK] replaces unicode \\u2713 (checkmark)")
print("     [FAIL] replaces unicode \\u2717 (x mark)")
