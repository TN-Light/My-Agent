"""
Typed Action Schema - Phase-2A/3C
Ensures type-safe action passing between Planner, Policy Engine, and Controller.

Phase-2A: Added context field for authority routing (desktop/web/file).
Phase-3C: Added verification evidence and confidence scoring.
"""
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Action:
    """
    Immutable action representation.
    
    Attributes:
        action_type: Type of action to perform
        context: Execution context (desktop/web/file) for authority routing
        target: Application name, URL, file path, or element selector
        text: Text content for typing actions
        coordinates: MUST be None in Phase-2A (no coordinate clicking yet)
        verify: Optional verification metadata (dict with 'type' and 'value')
    """
    action_type: Literal["launch_app", "type_text", "close_app", "focus_window", "wait", "click_control", "observe_dom", "observe_vision"]
    context: Literal["desktop", "web", "file", "market_analysis"] = "desktop"  # Default to desktop for backward compatibility
    target: Optional[str] = None
    text: Optional[str] = None
    coordinates: Optional[tuple[int, int]] = None
    verify: Optional[dict] = None  # Verification metadata: {"type": "text_visible", "value": "..."}
    
    def __post_init__(self):
        """Validate action has required fields and safety constraints."""
        # Phase-2A: Coordinates must NOT be used
        if self.coordinates is not None:
            raise ValueError("Coordinates not allowed in Phase-2A (no coordinate clicking)")
        
        # Desktop context validation
        if self.context == "desktop":
            if self.action_type == "launch_app" and not self.target:
                raise ValueError("launch_app (desktop) requires 'target' field")
            if self.action_type == "type_text" and not self.text:
                raise ValueError("type_text (desktop) requires 'text' field")
            if self.action_type == "focus_window" and not self.target:
                raise ValueError("focus_window requires 'target' window name/title")
            if self.action_type == "click_control" and not self.target:
                raise ValueError("click_control requires 'target' control name")
            if self.action_type == "wait" and not self.target:
                raise ValueError("wait requires 'target' duration (seconds)")
            if self.action_type == "close_app" and not self.target:
                # Phase-2B: Allow empty target for Planner auto-repair (must be resolved before execution)
                pass
        
        # Web context validation
        elif self.context == "web":
            if self.action_type == "launch_app" and not self.target:
                raise ValueError("launch_app (web) requires 'target' URL")
            if self.action_type == "type_text" and (not self.target or not self.text):
                raise ValueError("type_text (web) requires 'target' selector and 'text'")
            # Phase-4A: focus_window and wait are desktop-only
            if self.action_type in ["focus_window", "wait"]:
                raise ValueError(f"{self.action_type} only supported in desktop context")
        
        # File context validation
        elif self.context == "file":
            if self.action_type == "close_app":
                raise ValueError("close_app not supported in file context")
            # Phase-4A: focus_window and wait are desktop-only
            if self.action_type in ["focus_window", "wait"]:
                raise ValueError(f"{self.action_type} only supported in desktop context")
            if not self.target:
                raise ValueError("File operations require 'target' file path")
            if self.action_type == "type_text" and not self.text:
                raise ValueError("type_text (file create) requires 'text' content")


@dataclass(frozen=True)
class VerificationEvidence:
    """
    Evidence from a verification source.
    
    Phase-3C: Metadata for verification confidence scoring.
    Phase-3D: Enhanced with checked_text and sample fields.
    Used to track which verification methods were used and their results.
    
    Attributes:
        source: Verification source (DOM, UIA, VISION)
        result: Verification outcome
        details: Optional additional context
        checked_text: What text/element was being verified (Phase-3D)
        sample: Optional excerpt from verification source (Phase-3D)
    """
    source: Literal["DOM", "UIA", "FILE", "VISION"]
    result: Literal["SUCCESS", "FAIL", "VERIFIED", "NOT_VERIFIED", "UNKNOWN"]
    details: Optional[str] = None
    checked_text: Optional[str] = None
    sample: Optional[str] = None


@dataclass
class ActionResult:
    """
    Result of action execution.
    
    Phase-3C: Includes confidence score and verification evidence.
    Phase-3D: Enhanced evidence with structured details (source, checked_text, sample, confidence).
    
    Attributes:
        action: The action that was executed
        success: Whether the action succeeded
        message: Human-readable result description
        error: Error message if failed
        reason: Failure reason (e.g., 'verification_failed', 'execution_error', 'policy_denied')
        confidence: Verification confidence (0.0-1.0, Phase-3C)
        evidence: List of verification evidence (Phase-3C)
        verification_evidence: Structured evidence dict (Phase-3D)
    
    Confidence Scoring:
        1.0: Pure DOM/UIA success (high confidence)
        0.7-0.9: DOM/UIA with additional context
        0.5-0.7: DOM fail + vision VERIFIED (medium confidence)
        <0.5: Mixed/UNKNOWN results (low confidence)
    
    Note: Confidence does NOT affect execution flow, retries, or planning.
          It is metadata only for logging and diagnostics.
    
    Failure Reasons:
        'verification_failed': Verification check failed (TERMINAL - no retry)
        'execution_error': Execution failed (may retry)
        'policy_denied': Policy rejected action (TERMINAL - no retry)
    
    Verification Evidence Structure (Phase-3D):
        {
            'source': 'DOM' | 'VISION' | 'UIA' | 'FILE',
            'checked_text': str (what was verified),
            'sample': str (optional excerpt from page/screen),
            'confidence': float (0.0-1.0)
        }
    """
    action: Action
    success: bool
    message: str
    error: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = 1.0
    evidence: list = None
    verification_evidence: Optional[dict] = None
    
    def __post_init__(self):
        """Initialize evidence list if None."""
        if self.evidence is None:
            object.__setattr__(self, 'evidence', [])
