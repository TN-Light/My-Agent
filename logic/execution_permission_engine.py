"""
PHASE-9: EXECUTION PERMISSION ENGINE
Purpose: Final authority before ANY order can exist

NON-NEGOTIABLE RULES:
1. 6 mandatory gates for AUTONOMOUS mode (ALL must pass)
2. Fail one → NO TRADE
3. ASSISTED mode requires human confirmation
4. ANALYSIS mode never executes

6 MANDATORY GATES FOR AUTONOMOUS:
1. Edge: Phase-8 expectancy > 0
2. Stability: Alignment ≠ UNSTABLE
3. Probability: Active scenario prob ≥ threshold
4. Risk: Phase-7B allows allocation
5. Regime: No REGIME_CHANGE warning
6. User: Explicit AUTO consent

Philosophy:
"Under what exact conditions is the system ALLOWED to act?"
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from logic.intent_classifier import UserIntent


class ExecutionMode(Enum):
    """Execution mode."""
    
    ANALYSIS = "ANALYSIS"
    ASSISTED = "ASSISTED"
    AUTONOMOUS = "AUTONOMOUS"


@dataclass
class PermissionResult:
    """Result of permission evaluation."""
    
    allowed: bool
    mode: ExecutionMode
    reason: str
    blocked_gate: Optional[str] = None
    requires_confirmation: bool = False
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.allowed


class ExecutionPermissionEngine:
    """
    Final authority before any order can exist.
    
    Determines if system is ALLOWED to act (not if it CAN act).
    """
    
    # Minimum probability threshold for AUTONOMOUS mode
    AUTO_PROBABILITY_THRESHOLD = 0.55
    
    def __init__(self):
        """Initialize permission engine."""
        pass
    
    def evaluate_permission(
        self,
        user_intent: UserIntent,
        expectancy: float,
        alignment_state: str,
        scenario_active: str,
        probability_active: float,
        risk_allowed: bool,
        regime_warning: bool,
        explicit_consent: bool
    ) -> PermissionResult:
        """
        Evaluate execution permission.
        
        6 MANDATORY GATES FOR AUTONOMOUS:
        1. Edge: expectancy > 0
        2. Stability: alignment ≠ UNSTABLE
        3. Probability: probability_active ≥ threshold
        4. Risk: risk_allowed = True
        5. Regime: regime_warning = False
        6. User: explicit_consent = True
        
        Args:
            user_intent: Classified user intent
            expectancy: Phase-8 expectancy value
            alignment_state: Current alignment state
            scenario_active: Active scenario
            probability_active: Probability of active scenario
            risk_allowed: Whether Phase-7B allows risk
            regime_warning: Whether regime shift warning active
            explicit_consent: Whether user gave explicit AUTO consent
        
        Returns:
            PermissionResult
        """
        # ========================================
        # INTENT-BASED MODE DETERMINATION
        # ========================================
        
        if user_intent == UserIntent.ANALYSIS_ONLY:
            return PermissionResult(
                allowed=False,
                mode=ExecutionMode.ANALYSIS,
                reason="ANALYSIS mode - execution disabled",
                blocked_gate=None,
                requires_confirmation=False
            )
        
        if user_intent == UserIntent.ASSISTED_EXECUTION:
            return PermissionResult(
                allowed=False,
                mode=ExecutionMode.ASSISTED,
                reason="ASSISTED mode - human confirmation required",
                blocked_gate=None,
                requires_confirmation=True
            )
        
        # ========================================
        # AUTONOMOUS MODE: 6 MANDATORY GATES
        # ========================================
        
        if user_intent == UserIntent.AUTONOMOUS_EXECUTION:
            # GATE 1: Edge (expectancy > 0)
            if expectancy <= 0:
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ANALYSIS,
                    reason=f"GATE_1_FAILED: Expectancy={expectancy:.2f}R ≤ 0 (no proven edge)",
                    blocked_gate="GATE_1_EDGE",
                    requires_confirmation=False
                )
            
            # GATE 2: Stability (alignment ≠ UNSTABLE)
            if alignment_state in ["UNSTABLE", "CONFLICT", "PARTIAL ALIGNMENT"]:
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ANALYSIS,
                    reason=f"GATE_2_FAILED: Alignment={alignment_state} (structural instability)",
                    blocked_gate="GATE_2_STABILITY",
                    requires_confirmation=False
                )
            
            # GATE 3: Probability (prob_active ≥ threshold)
            if probability_active < self.AUTO_PROBABILITY_THRESHOLD:
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ANALYSIS,
                    reason=f"GATE_3_FAILED: Probability={probability_active:.2f} < {self.AUTO_PROBABILITY_THRESHOLD} (low confidence)",
                    blocked_gate="GATE_3_PROBABILITY",
                    requires_confirmation=False
                )
            
            # GATE 4: Risk (risk_allowed = True)
            if not risk_allowed:
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ANALYSIS,
                    reason="GATE_4_FAILED: Risk budget does not allow execution",
                    blocked_gate="GATE_4_RISK",
                    requires_confirmation=False
                )
            
            # GATE 5: Regime (no regime warning)
            if regime_warning:
                # DOWNGRADE TO ASSISTED
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ASSISTED,
                    reason="GATE_5_FAILED: Regime shift detected → DOWNGRADED to ASSISTED",
                    blocked_gate="GATE_5_REGIME",
                    requires_confirmation=True
                )
            
            # GATE 6: User consent (explicit_consent = True)
            if not explicit_consent:
                return PermissionResult(
                    allowed=False,
                    mode=ExecutionMode.ANALYSIS,
                    reason="GATE_6_FAILED: No explicit AUTONOMOUS consent",
                    blocked_gate="GATE_6_USER_CONSENT",
                    requires_confirmation=False
                )
            
            # ALL GATES PASSED → AUTONOMOUS EXECUTION ALLOWED
            return PermissionResult(
                allowed=True,
                mode=ExecutionMode.AUTONOMOUS,
                reason="ALL_GATES_PASSED: Autonomous execution authorized",
                blocked_gate=None,
                requires_confirmation=False
            )
        
        # ========================================
        # FALLBACK: ANALYSIS ONLY
        # ========================================
        return PermissionResult(
            allowed=False,
            mode=ExecutionMode.ANALYSIS,
            reason="Unknown intent → ANALYSIS mode (safety first)",
            blocked_gate=None,
            requires_confirmation=False
        )
    
    def evaluate_permission_simple(
        self,
        mode: str,
        expectancy: float,
        alignment_state: str,
        probability_active: float,
        risk_allowed: bool,
        regime_warning: bool,
        explicit_consent: bool
    ) -> PermissionResult:
        """
        Simplified permission evaluation (mode as string).
        
        Args:
            mode: "ANALYSIS" | "ASSISTED" | "AUTO"
            (other args same as evaluate_permission)
        
        Returns:
            PermissionResult
        """
        # Convert mode to intent
        mode_upper = mode.upper()
        
        if mode_upper == "ANALYSIS":
            user_intent = UserIntent.ANALYSIS_ONLY
        elif mode_upper == "ASSISTED":
            user_intent = UserIntent.ASSISTED_EXECUTION
        elif mode_upper in ["AUTO", "AUTONOMOUS"]:
            user_intent = UserIntent.AUTONOMOUS_EXECUTION
        else:
            user_intent = UserIntent.ANALYSIS_ONLY
        
        return self.evaluate_permission(
            user_intent=user_intent,
            expectancy=expectancy,
            alignment_state=alignment_state,
            scenario_active="A",  # Not used in current logic
            probability_active=probability_active,
            risk_allowed=risk_allowed,
            regime_warning=regime_warning,
            explicit_consent=explicit_consent
        )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"ExecutionPermissionEngine(auto_threshold={self.AUTO_PROBABILITY_THRESHOLD})"
