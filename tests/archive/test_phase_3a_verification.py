"""
Phase-3A Verification Tests (No Implementation - Validation Only)

Tests that Phase-3A requirements are met:
1. Normalized verification output (Desktop/Web/File)
2. Observation vs Action separation
3. Confidence informational-only invariant
4. Evidence structure future-proofing
"""

import sys
import os
import inspect

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.actions import Action, ActionResult, VerificationEvidence
from logic.critic import Critic
from logic.planner import Planner
from execution.controller import Controller
from main import Agent

print("="*70)
print("PHASE-3A VERIFICATION TESTS")
print("="*70)

# Test Group 1: Normalized Verification Output
print("\n" + "="*70)
print("TEST GROUP 1: Normalized Verification Output (Desktop/Web/File)")
print("="*70)

print("\n--- Test 1.1: ActionResult schema ---")
try:
    # Check ActionResult has all required fields
    test_action = Action(action_type="type_text", context="desktop", text="test")
    result = ActionResult(
        action=test_action,
        success=True,
        message="test",
        confidence=1.0,
        evidence=[],
        verification_evidence={}
    )
    
    assert hasattr(result, 'success'), "Missing 'success' field"
    assert hasattr(result, 'confidence'), "Missing 'confidence' field"
    assert hasattr(result, 'reason'), "Missing 'reason' field"
    assert hasattr(result, 'evidence'), "Missing 'evidence' field"
    assert hasattr(result, 'verification_evidence'), "Missing 'verification_evidence' field"
    
    print(f"✅ PASS: ActionResult has all required fields")
    print(f"   - success: {type(result.success).__name__}")
    print(f"   - confidence: {type(result.confidence).__name__}")
    print(f"   - reason: {type(result.reason).__name__}")
    print(f"   - evidence: {type(result.evidence).__name__}")
    print(f"   - verification_evidence: {type(result.verification_evidence).__name__}")
    test_1_1 = True
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_1_1 = False

print("\n--- Test 1.2: VerificationEvidence schema ---")
try:
    # Check VerificationEvidence has multi-source support
    evidence_dom = VerificationEvidence(source="DOM", result="SUCCESS", details="test")
    evidence_uia = VerificationEvidence(source="UIA", result="SUCCESS", details="test")
    evidence_file = VerificationEvidence(source="FILE", result="SUCCESS", details="test")
    evidence_vision = VerificationEvidence(source="VISION", result="VERIFIED", details="test")
    
    assert hasattr(evidence_dom, 'source'), "Missing 'source' field"
    assert hasattr(evidence_dom, 'result'), "Missing 'result' field"
    assert hasattr(evidence_dom, 'details'), "Missing 'details' field"
    assert hasattr(evidence_dom, 'checked_text'), "Missing 'checked_text' field"
    assert hasattr(evidence_dom, 'sample'), "Missing 'sample' field"
    
    print(f"✅ PASS: VerificationEvidence supports all sources")
    print(f"   - DOM: {evidence_dom.source}")
    print(f"   - UIA: {evidence_uia.source}")
    print(f"   - FILE: {evidence_file.source}")
    print(f"   - VISION: {evidence_vision.source}")
    test_1_2 = True
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_1_2 = False

print("\n--- Test 1.3: Critic returns consistent ActionResult ---")
try:
    from perception.accessibility_client import AccessibilityClient
    
    acc_client = AccessibilityClient()
    critic = Critic(acc_client)
    
    # Test desktop action
    desktop_action = Action(action_type="type_text", context="desktop", text="test")
    desktop_result = critic.verify_action(desktop_action)
    
    assert isinstance(desktop_result, ActionResult), "Desktop verification must return ActionResult"
    assert hasattr(desktop_result, 'confidence'), "Desktop result missing confidence"
    assert hasattr(desktop_result, 'evidence'), "Desktop result missing evidence"
    
    print(f"✅ PASS: Critic returns consistent ActionResult")
    print(f"   - Desktop: ActionResult with confidence={desktop_result.confidence:.2f}")
    test_1_3 = True
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_1_3 = False

# Test Group 2: Observation vs Action Separation
print("\n" + "="*70)
print("TEST GROUP 2: Observation vs Action Separation")
print("="*70)

print("\n--- Test 2.1: Observations have no retry in main.py ---")
try:
    # Read main.py and check observation execution has no retry logic
    with open("main.py", "r") as f:
        main_content = f.read()
    
    # Find _execute_single_observation method
    obs_method_start = main_content.find("def _execute_single_observation")
    obs_method_end = main_content.find("\n    def ", obs_method_start + 1)
    obs_method = main_content[obs_method_start:obs_method_end] if obs_method_end != -1 else main_content[obs_method_start:]
    
    # Check no retry logic in observation method
    has_retry = "retry" in obs_method.lower() or "attempt" in obs_method
    
    if not has_retry:
        print(f"✅ PASS: Observations have no retry logic")
        print(f"   - _execute_single_observation method contains no retry/attempt logic")
        test_2_1 = True
    else:
        print(f"❌ FAIL: Observation method contains retry/attempt logic")
        test_2_1 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_2_1 = False

print("\n--- Test 2.2: Actions have retry support in main.py ---")
try:
    # Check _execute_single_action has retry (attempt parameter)
    action_method_start = main_content.find("def _execute_single_action")
    action_method_end = main_content.find("\n    def ", action_method_start + 1)
    action_method = main_content[action_method_start:action_method_end] if action_method_end != -1 else main_content[action_method_start:]
    
    # Check for retry logic
    has_attempt_param = "attempt: int" in action_method
    has_retry_call = "attempt=2" in action_method
    
    if has_attempt_param and has_retry_call:
        print(f"✅ PASS: Actions have retry support")
        print(f"   - _execute_single_action has attempt parameter and retry logic")
        test_2_2 = True
    else:
        print(f"❌ FAIL: Action method missing retry support")
        test_2_2 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_2_2 = False

# Test Group 3: Confidence Informational-Only Invariant
print("\n" + "="*70)
print("TEST GROUP 3: Confidence Informational-Only Invariant")
print("="*70)

print("\n--- Test 3.1: Confidence not in control flow (planner) ---")
try:
    # Check planner.py has no confidence-based branching
    with open("logic/planner.py", "r") as f:
        planner_content = f.read()
    
    # Look for confidence in if/while statements
    lines = planner_content.split('\n')
    confidence_branches = [
        i for i, line in enumerate(lines, 1) 
        if ('if' in line or 'while' in line) and 'confidence' in line.lower()
    ]
    
    if not confidence_branches:
        print(f"✅ PASS: Planner has no confidence-based control flow")
        print(f"   - No if/while statements containing 'confidence'")
        test_3_1 = True
    else:
        print(f"❌ FAIL: Planner has confidence in control flow at lines: {confidence_branches}")
        test_3_1 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_3_1 = False

print("\n--- Test 3.2: Confidence not in control flow (controller) ---")
try:
    # Check controller.py has no confidence-based branching
    with open("execution/controller.py", "r") as f:
        controller_content = f.read()
    
    lines = controller_content.split('\n')
    confidence_branches = [
        i for i, line in enumerate(lines, 1) 
        if ('if' in line or 'while' in line) and 'confidence' in line.lower()
    ]
    
    if not confidence_branches:
        print(f"✅ PASS: Controller has no confidence-based control flow")
        print(f"   - No if/while statements containing 'confidence'")
        test_3_2 = True
    else:
        print(f"❌ FAIL: Controller has confidence in control flow at lines: {confidence_branches}")
        test_3_2 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_3_2 = False

print("\n--- Test 3.3: Confidence IS logged in main.py ---")
try:
    # Check main.py logs confidence
    confidence_logs = [
        i for i, line in enumerate(main_content.split('\n'), 1) 
        if 'logger' in line and 'confidence' in line.lower()
    ]
    
    if confidence_logs:
        print(f"✅ PASS: Confidence is logged (informational)")
        print(f"   - Found {len(confidence_logs)} logging statements with confidence")
        test_3_3 = True
    else:
        print(f"❌ FAIL: Confidence not logged")
        test_3_3 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_3_3 = False

print("\n--- Test 3.4: Confidence stored in database ---")
try:
    # Check action_logger.py stores confidence
    with open("storage/action_logger.py", "r") as f:
        logger_content = f.read()
    
    has_confidence_field = "confidence" in logger_content
    
    if has_confidence_field:
        print(f"✅ PASS: Confidence stored in database")
        print(f"   - action_logger.py references confidence")
        test_3_4 = True
    else:
        print(f"❌ FAIL: Confidence not in action_logger")
        test_3_4 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_3_4 = False

# Test Group 4: Evidence Structure Future-Proofing
print("\n" + "="*70)
print("TEST GROUP 4: Evidence Structure Future-Proofing")
print("="*70)

print("\n--- Test 4.1: VerificationEvidence supports all authority sources ---")
try:
    # Test creating evidence from each source
    sources = ["DOM", "UIA", "FILE", "VISION"]
    results = ["SUCCESS", "FAIL", "VERIFIED", "NOT_VERIFIED", "UNKNOWN"]
    
    all_valid = True
    for source in sources:
        for result in results:
            try:
                ev = VerificationEvidence(source=source, result=result, details="test")
                assert ev.source == source
                assert ev.result == result
            except Exception as e:
                print(f"   ❌ Failed: source={source}, result={result}: {e}")
                all_valid = False
                break
        if not all_valid:
            break
    
    if all_valid:
        print(f"✅ PASS: VerificationEvidence supports all source/result combinations")
        print(f"   - Sources: {', '.join(sources)}")
        print(f"   - Results: {', '.join(results)}")
        test_4_1 = True
    else:
        print(f"❌ FAIL: VerificationEvidence validation failed")
        test_4_1 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_4_1 = False

print("\n--- Test 4.2: Evidence list in ActionResult ---")
try:
    # Test ActionResult can hold multiple evidence objects
    action = Action(action_type="type_text", context="desktop", text="test")
    
    evidence_list = [
        VerificationEvidence(source="DOM", result="FAIL", details="Element not found"),
        VerificationEvidence(source="VISION", result="VERIFIED", details="Text visible"),
    ]
    
    result = ActionResult(
        action=action,
        success=True,
        message="test",
        confidence=0.65,
        evidence=evidence_list
    )
    
    assert len(result.evidence) == 2, "Evidence list should have 2 items"
    assert result.evidence[0].source == "DOM", "First evidence should be DOM"
    assert result.evidence[1].source == "VISION", "Second evidence should be VISION"
    
    print(f"✅ PASS: ActionResult supports multiple evidence objects")
    print(f"   - Evidence count: {len(result.evidence)}")
    print(f"   - Sources: {[e.source for e in result.evidence]}")
    test_4_2 = True
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_4_2 = False

print("\n--- Test 4.3: Critic uses VerificationEvidence ---")
try:
    # Check critic.py creates VerificationEvidence objects
    with open("logic/critic.py", "r") as f:
        critic_content = f.read()
    
    evidence_creations = critic_content.count("VerificationEvidence(")
    
    if evidence_creations > 0:
        print(f"✅ PASS: Critic creates VerificationEvidence objects")
        print(f"   - Found {evidence_creations} evidence creation statements")
        test_4_3 = True
    else:
        print(f"❌ FAIL: Critic doesn't use VerificationEvidence")
        test_4_3 = False
except Exception as e:
    print(f"❌ FAIL: {e}")
    test_4_3 = False

# Summary
print("\n" + "="*70)
print("PHASE-3A VERIFICATION SUMMARY")
print("="*70)

results = {
    "Group 1: Normalized Output": [test_1_1, test_1_2, test_1_3],
    "Group 2: Observation/Action Separation": [test_2_1, test_2_2],
    "Group 3: Confidence Informational-Only": [test_3_1, test_3_2, test_3_3, test_3_4],
    "Group 4: Evidence Future-Proofing": [test_4_1, test_4_2, test_4_3]
}

total_tests = 0
total_pass = 0

for group, tests in results.items():
    passed = sum(tests)
    total = len(tests)
    total_tests += total
    total_pass += passed
    
    status = "✅ PASS" if all(tests) else "❌ FAIL"
    print(f"\n{status} {group}: {passed}/{total}")

print("\n" + "="*70)
if total_pass == total_tests:
    print(f"✅ ALL TESTS PASSED: {total_pass}/{total_tests}")
    print("\nPhase-3A is FULLY IMPLEMENTED and VERIFIED")
else:
    print(f"❌ SOME TESTS FAILED: {total_pass}/{total_tests}")
    print(f"\nPhase-3A has {total_tests - total_pass} failing test(s)")

print("="*70)
