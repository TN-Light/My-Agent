"""
Phase-4A Policy Enforcement Tests
Tests that focus_window and close_app properly enforce whitelist restrictions.
"""

import sys
from logic.planner import Planner
from logic.policy_engine import PolicyEngine

def run_tests():
    # Initialize with deterministic planner
    config = {'planner': {'use_llm': False}}
    planner = Planner(config=config)
    policy = PolicyEngine('config/policy.yaml')
    
    print('=' * 70)
    print('Phase-4A Policy Enforcement Tests')
    print('=' * 70)
    print()
    
    all_passed = True
    
    # Test 1: focus_window on non-whitelisted app
    print('Test 1: focus_window on non-whitelisted app (firefox)')
    plan = planner.parse_instruction('focus firefox')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if not approved and 'not in the whitelist' in reason:
        print('  ✅ PASS: Correctly DENIED')
        print(f'     Reason: {reason}')
    else:
        print(f'  ❌ FAIL: Expected DENIED, got approved={approved}')
        all_passed = False
    print()
    
    # Test 2: focus_window on whitelisted app
    print('Test 2: focus_window on whitelisted app (notepad)')
    plan = planner.parse_instruction('focus notepad')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if approved:
        print('  ✅ PASS: Correctly APPROVED')
    else:
        print(f'  ❌ FAIL: Expected APPROVED, got reason={reason}')
        all_passed = False
    print()
    
    # Test 3: close_app on non-whitelisted app
    print('Test 3: close_app on non-whitelisted app (firefox)')
    plan = planner.parse_instruction('close firefox')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if not approved and 'not in the whitelist' in reason:
        print('  ✅ PASS: Correctly DENIED')
        print(f'     Reason: {reason}')
    else:
        print(f'  ❌ FAIL: Expected DENIED, got approved={approved}')
        all_passed = False
    print()
    
    # Test 4: close_app on whitelisted app
    print('Test 4: close_app on whitelisted app (notepad)')
    plan = planner.parse_instruction('close notepad')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if approved:
        print('  ✅ PASS: Correctly APPROVED')
    else:
        print(f'  ❌ FAIL: Expected APPROVED, got reason={reason}')
        all_passed = False
    print()
    
    # Test 5: close_app on blacklisted app
    print('Test 5: close_app on blacklisted app (regedit)')
    plan = planner.parse_instruction('close regedit')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if not approved and 'blacklisted' in reason:
        print('  ✅ PASS: Correctly DENIED (blacklisted)')
        print(f'     Reason: {reason}')
    else:
        print(f'  ❌ FAIL: Expected DENIED for blacklisted app, got approved={approved}')
        all_passed = False
    print()
    
    # Test 6: wait action (always allowed)
    print('Test 6: wait action (always allowed)')
    plan = planner.parse_instruction('wait 5 seconds')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if approved:
        print('  ✅ PASS: Correctly APPROVED')
    else:
        print(f'  ❌ FAIL: Expected APPROVED, got reason={reason}')
        all_passed = False
    print()
    
    # Test 7: Verify .exe suffix normalization
    print('Test 7: .exe suffix normalization (focus "code" matches "code.exe")')
    plan = planner.parse_instruction('focus code')
    action = plan[0]
    approved, reason = policy.validate_action(action)
    if approved:
        print('  ✅ PASS: Correctly APPROVED (normalized "code" → "code.exe")')
    else:
        print(f'  ❌ FAIL: Expected APPROVED, got reason={reason}')
        all_passed = False
    print()
    
    print('=' * 70)
    if all_passed:
        print('✅ ALL TESTS PASSED')
        print('=' * 70)
        return 0
    else:
        print('❌ SOME TESTS FAILED')
        print('=' * 70)
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
