"""
Test Phase-3D: Verification Evidence Collection

Verifies that structured evidence is collected, logged, and stored.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
import sqlite3
from common.actions import Action, ActionResult
from logic.critic import Critic
from perception.accessibility_client import AccessibilityClient

print("=" * 70)
print("TEST: Phase-3D Verification Evidence Collection")
print("=" * 70)

# Mock components
class MockBrowserHandler:
    def get_page_text(self):
        return """
        Welcome to Example Website
        
        This is a test page with some content.
        You can search and verify text here.
        
        Footer: Copyright 2024
        """

class MockAccessibilityClient:
    pass

print("\n" + "=" * 70)
print("TEST 1: DOM Verification Evidence - SUCCESS")
print("=" * 70)

critic = Critic(
    accessibility_client=MockAccessibilityClient(),
    browser_handler=MockBrowserHandler()
)

# Test DOM verification with text found
action = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Example Website"}
)

result = critic._verify_with_metadata(action)

print(f"Success: {result.success}")
print(f"Confidence: {result.confidence}")
print(f"Evidence count: {len(result.evidence)}")

# Check verification_evidence structure
if result.verification_evidence:
    evidence = result.verification_evidence
    print(f"\nVerification Evidence:")
    print(f"  Source: {evidence.get('source')}")
    print(f"  Checked text: {evidence.get('checked_text')}")
    print(f"  Confidence: {evidence.get('confidence')}")
    print(f"  Sample: {evidence.get('sample')[:50]}..." if evidence.get('sample') else "  Sample: None")
    
    # Validate structure
    assert evidence.get('source') == 'DOM', "Expected DOM source"
    assert evidence.get('checked_text') == 'Example Website', "Expected checked_text to match"
    assert evidence.get('confidence') > 0.9, "Expected high confidence"
    assert evidence.get('sample') is not None, "Expected sample text"
    assert 'Example Website' in evidence.get('sample'), "Expected sample to contain searched text"
    
    print("\n[OK] TEST 1 PASSED: DOM evidence collected with correct structure")
else:
    print("\n[FAIL] TEST 1 FAILED: No verification_evidence in result")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 2: DOM Verification Evidence - FAILURE")
print("=" * 70)

# Test DOM verification with text NOT found
action2 = Action(
    action_type="launch_app",
    context="web",
    target="https://example.com",
    verify={"type": "text_visible", "value": "Missing Text"}
)

result2 = critic._verify_with_metadata(action2)

print(f"Success: {result2.success}")
print(f"Confidence: {result2.confidence}")
print(f"Evidence count: {len(result2.evidence)}")

# Check verification_evidence structure for failure
if result2.verification_evidence:
    evidence2 = result2.verification_evidence
    print(f"\nVerification Evidence:")
    print(f"  Source: {evidence2.get('source')}")
    print(f"  Checked text: {evidence2.get('checked_text')}")
    print(f"  Confidence: {evidence2.get('confidence')}")
    
    # Validate structure
    assert evidence2.get('source') == 'NONE', "Expected NONE source when all methods fail"
    assert evidence2.get('checked_text') == 'Missing Text', "Expected checked_text to match"
    assert evidence2.get('confidence') < 0.5, "Expected low confidence for failure"
    
    print("\n[OK] TEST 2 PASSED: Failure evidence collected correctly")
else:
    print("\n[FAIL] TEST 2 FAILED: No verification_evidence in result")
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST 3: Evidence Sample Extraction")
print("=" * 70)

# Test the sample extraction helper
test_text = "The quick brown fox jumps over the lazy dog. This is a longer text to test extraction."
sample = critic._extract_text_sample(test_text, "brown fox", max_length=40)

print(f"Original text: {test_text}")
print(f"Search term: 'brown fox'")
print(f"Extracted sample: {sample}")

assert "brown fox" in sample, "Sample should contain search term"
assert len(sample) <= 50, "Sample should be truncated"  # +/- for ellipsis

print("\n[OK] TEST 3 PASSED: Sample extraction works correctly")

print("\n" + "=" * 70)
print("TEST 4: Evidence Storage in Database")
print("=" * 70)

# Test evidence serialization to database
from storage.action_logger import ActionLogger
import tempfile
import os

# Create temporary database
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db.close()

try:
    logger = ActionLogger(db_path=temp_db.name)
    
    # Log an action with verification evidence
    action3 = Action(
        action_type="launch_app",
        context="web",
        target="https://example.com"
    )
    
    result3 = ActionResult(
        action=action3,
        success=True,
        message="Test action",
        verification_evidence={
            'source': 'DOM',
            'checked_text': 'Test Text',
            'sample': 'Sample excerpt from page',
            'confidence': 0.95
        }
    )
    
    logger.log_action(result3)
    
    # Query database to verify evidence was stored
    conn = sqlite3.connect(temp_db.name)
    cursor = conn.cursor()
    cursor.execute("SELECT verification_evidence FROM action_history ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        stored_evidence = json.loads(row[0])
        print(f"Stored evidence: {stored_evidence}")
        
        assert stored_evidence['source'] == 'DOM', "Evidence source should match"
        assert stored_evidence['checked_text'] == 'Test Text', "Checked text should match"
        assert stored_evidence['confidence'] == 0.95, "Confidence should match"
        
        print("\n[OK] TEST 4 PASSED: Evidence stored and retrieved from database")
    else:
        print("\n[FAIL] TEST 4 FAILED: No evidence in database")
        sys.exit(1)
        
finally:
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except:
        pass

print("\n" + "=" * 70)
print("TEST 5: Evidence in VerificationEvidence Objects")
print("=" * 70)

# Check that VerificationEvidence has the new fields
from common.actions import VerificationEvidence

evidence_obj = VerificationEvidence(
    source="DOM",
    result="SUCCESS",
    details="Test details",
    checked_text="Test text",
    sample="Sample excerpt"
)

print(f"Source: {evidence_obj.source}")
print(f"Result: {evidence_obj.result}")
print(f"Details: {evidence_obj.details}")
print(f"Checked text: {evidence_obj.checked_text}")
print(f"Sample: {evidence_obj.sample}")

assert evidence_obj.checked_text == "Test text", "checked_text field should work"
assert evidence_obj.sample == "Sample excerpt", "sample field should work"

print("\n[OK] TEST 5 PASSED: VerificationEvidence has new fields")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("[OK] All Phase-3D tests passed!")
print("\nVerification evidence collection working:")
print("  1. Structured evidence collected (source, checked_text, sample, confidence)")
print("  2. Evidence attached to ActionResult.verification_evidence")
print("  3. Evidence stored in database as JSON")
print("  4. Sample extraction helper works correctly")
print("  5. VerificationEvidence dataclass enhanced with new fields")
print("\nEvidence is descriptive only - no control flow impact")
