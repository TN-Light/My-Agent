"""
Phase-4B Authority Audit
Verifies the Trust Hierarchy:
1. Ground Truth (UIA/DOM) > Vision
2. Vision (Advisory) only activates on Primary Failure
3. Confidence Scores align with Architecture 03

Scenarios:
- PRIMARY_OVERRIDE: UIA says Success, Vision says Fail -> Confidence 1.0 (Vision ignored)
- VISION_FALLBACK: UIA says Fail, Vision says Verified -> Confidence 0.7 (Max for Vision)
- CONFLICT_LOW: UIA says Fail, Vision says Not_Verified -> Confidence 0.3 (Low)
"""
import unittest
from unittest.mock import MagicMock
from logic.critic import Critic
from common.actions import VerificationEvidence
from perception.accessibility_client import AccessibilityClient

class TestAuthorityAudit(unittest.TestCase):
    
    def setUp(self):
        # Mock dependencies
        self.mock_accessibility = MagicMock(spec=AccessibilityClient)
        # Initialize Critic with mock
        self.critic = Critic(accessibility_client=self.mock_accessibility)
        
    def test_1_primary_override(self):
        """
        Authority Rule #1: Ground Truth trumps Vision.
        If UIA is SUCCESS, Confidence must be 1.0 even if Vision fails.
        """
        print("\n[Audit 1] Primary Override (UIA vs Vision)")
        
        evidence = [
            VerificationEvidence(source="UIA", result="SUCCESS", details="Found window"),
            VerificationEvidence(source="VISION", result="NOT_VERIFIED", details="Ocr failed")
        ]
        
        score = self.critic._compute_confidence(evidence)
        print(f"  Evidence: UIA=SUCCESS, VISION=FAIL -> Score: {score}")
        
        self.assertEqual(score, 1.0, "Critical Failure: UIA did not override Vision")
        print("✓ PASS: Ground Truth accepted as absolute.")

    def test_2_vision_fallback_limit(self):
        """
        Authority Rule #2: Vision is capped.
        If UIA Fails but Vision Succeeds, Confidence is capped at 0.7.
        """
        print("\n[Audit 2] Vision Fallback Cap")
        
        evidence = [
            VerificationEvidence(source="UIA", result="FAIL", details="Window hidden"),
            VerificationEvidence(source="VISION", result="VERIFIED", details="Visual match found")
        ]
        
        score = self.critic._compute_confidence(evidence)
        print(f"  Evidence: UIA=FAIL, VISION=VERIFIED -> Score: {score}")
        
        self.assertEqual(score, 0.7, "Critical Failure: Vision score exceeded safety cap")
        print("✓ PASS: Vision fallback strictly capped.")

    def test_3_conflict_resolution(self):
        """
        Authority Rule #3: Conflicting Negative Evidence.
        If both fail, confidence approaches zero.
        """
        print("\n[Audit 3] Conflict Resolution")
        
        evidence = [
            VerificationEvidence(source="UIA", result="FAIL", details="Not found"),
            VerificationEvidence(source="VISION", result="NOT_VERIFIED", details="Blurry")
        ]
        
        score = self.critic._compute_confidence(evidence)
        print(f"  Evidence: UIA=FAIL, VISION=FAIL -> Score: {score}")
        
        self.assertLess(score, 0.4, "Critical Failure: Confidence too high for total failure")
        print("✓ PASS: Double failure detected correctly.")

    def test_4_no_hallucination(self):
        """
        Authority Rule #4: No Evidence = Zero Confidence.
        """
        print("\n[Audit 4] Zero-Shot/Hallucination Check")
        evidence = []
        score = self.critic._compute_confidence(evidence)
        self.assertEqual(score, 0.0)
        print("✓ PASS: No evidence yields 0.0 confidence.")

if __name__ == '__main__':
    unittest.main()
