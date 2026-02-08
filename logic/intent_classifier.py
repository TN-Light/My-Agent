"""
PHASE-9: INTENT CLASSIFIER
Purpose: Classify USER intent, not market intent

NON-NEGOTIABLE RULES:
1. Any ambiguity → ANALYSIS_ONLY
2. No guessing. Ever.
3. Explicit mode required for execution
4. "what do you think" → ANALYSIS_ONLY

Philosophy:
"Phase-9 does not add intelligence. It adds permission."
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class UserIntent(Enum):
    """User intent classification."""
    
    ANALYSIS_ONLY = "ANALYSIS_ONLY"
    ASSISTED_EXECUTION = "ASSISTED_EXECUTION"
    AUTONOMOUS_EXECUTION = "AUTONOMOUS_EXECUTION"


@dataclass
class IntentClassificationResult:
    """Result of intent classification."""
    
    intent: UserIntent
    confidence: str  # HIGH | MEDIUM | LOW
    reasoning: str
    explicit_mode: Optional[str] = None  # ANALYSIS | ASSISTED | AUTO


class IntentClassifier:
    """
    Classify user intent.
    
    Classifies what the user wants the system to DO, not what the market is doing.
    """
    
    # Keywords for analysis-only intent
    ANALYSIS_KEYWORDS = [
        "what do you think",
        "analyze",
        "look at",
        "check",
        "review",
        "opinion",
        "view",
        "assessment",
        "tell me",
        "show me"
    ]
    
    # Keywords for assisted execution intent
    ASSISTED_KEYWORDS = [
        "should i",
        "confirm",
        "approve",
        "review trade",
        "check setup"
    ]
    
    # Keywords for autonomous execution intent
    AUTONOMOUS_KEYWORDS = [
        "auto",
        "automatic",
        "autonomous",
        "execute automatically",
        "trade automatically"
    ]
    
    def __init__(self):
        """Initialize intent classifier."""
        pass
    
    def classify(
        self,
        user_input: str,
        explicit_mode: Optional[str] = None
    ) -> IntentClassificationResult:
        """
        Classify user intent.
        
        Args:
            user_input: User's message/command
            explicit_mode: Explicitly set mode (ANALYSIS | ASSISTED | AUTO)
        
        Returns:
            IntentClassificationResult
        """
        user_input_lower = user_input.lower().strip()
        
        # ========================================
        # EXPLICIT MODE OVERRIDES EVERYTHING
        # ========================================
        if explicit_mode:
            mode_upper = explicit_mode.upper()
            
            if mode_upper == "ANALYSIS":
                return IntentClassificationResult(
                    intent=UserIntent.ANALYSIS_ONLY,
                    confidence="HIGH",
                    reasoning="Explicit ANALYSIS mode set",
                    explicit_mode=mode_upper
                )
            elif mode_upper == "ASSISTED":
                return IntentClassificationResult(
                    intent=UserIntent.ASSISTED_EXECUTION,
                    confidence="HIGH",
                    reasoning="Explicit ASSISTED mode set",
                    explicit_mode=mode_upper
                )
            elif mode_upper == "AUTO" or mode_upper == "AUTONOMOUS":
                return IntentClassificationResult(
                    intent=UserIntent.AUTONOMOUS_EXECUTION,
                    confidence="HIGH",
                    reasoning="Explicit AUTONOMOUS mode set",
                    explicit_mode=mode_upper
                )
        
        # ========================================
        # KEYWORD-BASED CLASSIFICATION
        # ========================================
        
        # Check for analysis keywords
        for keyword in self.ANALYSIS_KEYWORDS:
            if keyword in user_input_lower:
                return IntentClassificationResult(
                    intent=UserIntent.ANALYSIS_ONLY,
                    confidence="HIGH",
                    reasoning=f"Analysis keyword detected: '{keyword}'",
                    explicit_mode=None
                )
        
        # Check for assisted keywords
        for keyword in self.ASSISTED_KEYWORDS:
            if keyword in user_input_lower:
                return IntentClassificationResult(
                    intent=UserIntent.ASSISTED_EXECUTION,
                    confidence="MEDIUM",
                    reasoning=f"Assisted keyword detected: '{keyword}'",
                    explicit_mode=None
                )
        
        # Check for autonomous keywords
        for keyword in self.AUTONOMOUS_KEYWORDS:
            if keyword in user_input_lower:
                return IntentClassificationResult(
                    intent=UserIntent.AUTONOMOUS_EXECUTION,
                    confidence="MEDIUM",
                    reasoning=f"Autonomous keyword detected: '{keyword}'",
                    explicit_mode=None
                )
        
        # ========================================
        # DEFAULT: ANY AMBIGUITY → ANALYSIS_ONLY
        # ========================================
        return IntentClassificationResult(
            intent=UserIntent.ANALYSIS_ONLY,
            confidence="HIGH",
            reasoning="Default: ambiguous input → ANALYSIS_ONLY (safety first)",
            explicit_mode=None
        )
    
    def is_execution_intent(self, intent: UserIntent) -> bool:
        """
        Check if intent involves execution.
        
        Args:
            intent: User intent
        
        Returns:
            True if execution intent (ASSISTED or AUTONOMOUS)
        """
        return intent in [
            UserIntent.ASSISTED_EXECUTION,
            UserIntent.AUTONOMOUS_EXECUTION
        ]
    
    def requires_confirmation(self, intent: UserIntent) -> bool:
        """
        Check if intent requires human confirmation.
        
        Args:
            intent: User intent
        
        Returns:
            True if confirmation required (ASSISTED mode)
        """
        return intent == UserIntent.ASSISTED_EXECUTION
    
    def __repr__(self) -> str:
        """String representation."""
        return "IntentClassifier(default=ANALYSIS_ONLY)"
