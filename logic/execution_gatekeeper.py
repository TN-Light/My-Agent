"""
PHASE-7C: EXECUTION GATEKEEPER (FINAL WALL)
Purpose: Single point of truth for ALL trade execution decisions

NON-NEGOTIABLE RULES:
1. Analysis suggests → Risk allows → Gatekeeper permits → Execution obeys
2. If any layer fails → execution = 0
3. NO retries, NO second chances, NO partial fills logic here
4. Every attempt (allowed/blocked) is logged
5. Token consumed on ALLOW, preserved on BLOCK

7-STEP PIPELINE (ORDER IS LAW):
STEP 1: Token Validation (reuse, expiry)
STEP 2: Scenario Authority (drift check)
STEP 3: Alignment Hard Stop (structural conflict)
STEP 4: Risk Budget Enforcement (overflow check)
STEP 5: Mode Constraint (time cutoff)
STEP 6: Manual vs Auto Rules (threshold check)
STEP 7: Final Commit (token consumption)

Philosophy:
"Execution is permission-based, not signal-based."
"""

from datetime import datetime, time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from logic.execution_token import ExecutionToken, TokenValidationResult
from storage.execution_audit_log import ExecutionAuditLog


@dataclass
class ExecutionDecision:
    """Result of execution gatekeeper evaluation."""
    
    allowed: bool
    reason: str
    block_gate: Optional[str]
    token_consumed: bool
    log_id: int
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.allowed


class ExecutionGatekeeper:
    """
    Final wall before trade execution.
    
    Single point of truth. Permission-based, not signal-based.
    """
    
    # Intraday cutoff time (3:15 PM IST)
    INTRADAY_CUTOFF = time(15, 15, 0)
    
    # Auto-execution minimum probability threshold
    AUTO_PROBABILITY_THRESHOLD = 0.55
    
    def __init__(self, audit_log: Optional[ExecutionAuditLog] = None):
        """
        Initialize execution gatekeeper.
        
        Args:
            audit_log: Audit log instance (creates new if None)
        """
        self.audit_log = audit_log or ExecutionAuditLog()
    
    def evaluate(
        self,
        token: Optional[ExecutionToken],
        symbol: str,
        timeframe: str,
        scenario_active: str,
        scenario_probabilities: Dict[str, float],
        alignment_state: str,
        risk_requested: float,
        market_mode: str,
        execution_type: str
    ) -> ExecutionDecision:
        """
        Evaluate execution permission.
        
        7-STEP PIPELINE (ORDER IS LAW):
        1. Token Validation
        2. Scenario Authority Check
        3. Alignment Hard Stop
        4. Risk Budget Enforcement
        5. Mode Constraint
        6. Manual vs Auto Rules
        7. Final Commit
        
        Args:
            token: Execution token (None = no token)
            symbol: Trading symbol
            timeframe: Chart timeframe
            scenario_active: Active scenario ("A", "B", "C")
            scenario_probabilities: Dict with keys "A", "B", "C"
            alignment_state: Alignment state ("FULL ALIGNMENT", "UNSTABLE", etc.)
            risk_requested: Risk amount requested (INR)
            market_mode: Trading mode ("INTRADAY", "SWING")
            execution_type: Execution type ("MANUAL", "AUTO")
        
        Returns:
            ExecutionDecision (allowed=True/False with reason)
        """
        # Extract probabilities
        prob_a = scenario_probabilities.get("A", 0.0)
        prob_b = scenario_probabilities.get("B", 0.0)
        prob_c = scenario_probabilities.get("C", 0.0)
        
        prob_active = scenario_probabilities.get(scenario_active, 0.0)
        
        # Default values for audit log
        token_id = token.token_id if token else None
        token_status = "MISSING"
        risk_allowed = 0.0
        risk_budget_status = "BLOCKED"
        
        # ========================================
        # STEP 1: TOKEN VALIDATION
        # ========================================
        if token is None:
            decision = self._block(
                token_id=None,
                token_status="MISSING",
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=0.0,
                risk_budget_status="BLOCKED",
                execution_type=execution_type,
                reason="NO_TOKEN",
                gate="STEP_1"
            )
            return decision
        
        # Check token reuse
        if token.used:
            decision = self._block(
                token_id=token.token_id,
                token_status="REUSED",
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=token.max_risk,
                risk_budget_status="BLOCKED",
                execution_type=execution_type,
                reason="TOKEN_REUSE",
                gate="STEP_1"
            )
            return decision
        
        # Check token expiry
        if token.is_expired():
            decision = self._block(
                token_id=token.token_id,
                token_status="EXPIRED",
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=token.max_risk,
                risk_budget_status="BLOCKED",
                execution_type=execution_type,
                reason="TOKEN_EXPIRED",
                gate="STEP_1"
            )
            return decision
        
        # Token is valid
        token_status = "VALID"
        risk_allowed = token.max_risk
        risk_budget_status = "ALLOWED"
        
        # ========================================
        # STEP 2: SCENARIO AUTHORITY CHECK
        # ========================================
        if scenario_active != token.scenario:
            decision = self._block(
                token_id=token.token_id,
                token_status=token_status,
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=risk_allowed,
                risk_budget_status=risk_budget_status,
                execution_type=execution_type,
                reason=f"SCENARIO_MISMATCH: Token={token.scenario}, Current={scenario_active}",
                gate="STEP_2"
            )
            return decision
        
        # ========================================
        # STEP 3: ALIGNMENT HARD STOP
        # ========================================
        if alignment_state in ["CONFLICT", "UNSTABLE", "PARTIAL ALIGNMENT"]:
            decision = self._block(
                token_id=token.token_id,
                token_status=token_status,
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=risk_allowed,
                risk_budget_status=risk_budget_status,
                execution_type=execution_type,
                reason=f"STRUCTURAL_CONFLICT: Alignment={alignment_state}",
                gate="STEP_3"
            )
            return decision
        
        # ========================================
        # STEP 4: RISK BUDGET ENFORCEMENT
        # ========================================
        if risk_requested > risk_allowed:
            decision = self._block(
                token_id=token.token_id,
                token_status=token_status,
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=risk_allowed,
                risk_budget_status="BLOCKED",
                execution_type=execution_type,
                reason=f"RISK_OVERFLOW: Requested={risk_requested:.2f}, Allowed={risk_allowed:.2f}",
                gate="STEP_4"
            )
            return decision
        
        # ========================================
        # STEP 5: MODE CONSTRAINT
        # ========================================
        if market_mode == "INTRADAY":
            current_time = datetime.now().time()
            if current_time > self.INTRADAY_CUTOFF:
                decision = self._block(
                    token_id=token.token_id,
                    token_status=token_status,
                    symbol=symbol,
                    timeframe=timeframe,
                    market_mode=market_mode,
                    scenario_active=scenario_active,
                    prob_a=prob_a,
                    prob_b=prob_b,
                    prob_c=prob_c,
                    alignment_state=alignment_state,
                    risk_requested=risk_requested,
                    risk_allowed=risk_allowed,
                    risk_budget_status=risk_budget_status,
                    execution_type=execution_type,
                    reason=f"TIME_CUTOFF: Current={current_time}, Cutoff={self.INTRADAY_CUTOFF}",
                    gate="STEP_5"
                )
                return decision
        
        # ========================================
        # STEP 6: MANUAL vs AUTO RULES
        # ========================================
        if execution_type == "AUTO":
            # Auto-execution requires higher probability threshold
            if prob_active < self.AUTO_PROBABILITY_THRESHOLD:
                decision = self._block(
                    token_id=token.token_id,
                    token_status=token_status,
                    symbol=symbol,
                    timeframe=timeframe,
                    market_mode=market_mode,
                    scenario_active=scenario_active,
                    prob_a=prob_a,
                    prob_b=prob_b,
                    prob_c=prob_c,
                    alignment_state=alignment_state,
                    risk_requested=risk_requested,
                    risk_allowed=risk_allowed,
                    risk_budget_status=risk_budget_status,
                    execution_type=execution_type,
                    reason=f"AUTO_THRESHOLD: Probability={prob_active:.2f} < {self.AUTO_PROBABILITY_THRESHOLD}",
                    gate="STEP_6"
                )
                return decision
        
        # ========================================
        # STEP 7: FINAL COMMIT
        # ========================================
        # All checks passed - consume token and allow execution
        try:
            token.consume()
        except RuntimeError as e:
            # Should not happen (we checked earlier), but defensive
            decision = self._block(
                token_id=token.token_id,
                token_status="ERROR",
                symbol=symbol,
                timeframe=timeframe,
                market_mode=market_mode,
                scenario_active=scenario_active,
                prob_a=prob_a,
                prob_b=prob_b,
                prob_c=prob_c,
                alignment_state=alignment_state,
                risk_requested=risk_requested,
                risk_allowed=risk_allowed,
                risk_budget_status=risk_budget_status,
                execution_type=execution_type,
                reason=f"TOKEN_CONSUMPTION_ERROR: {str(e)}",
                gate="STEP_7"
            )
            return decision
        
        # EXECUTION ALLOWED
        log_id = self.audit_log.log_execution_attempt(
            token_id=token.token_id,
            token_status=token_status,
            symbol=symbol,
            timeframe=timeframe,
            market_mode=market_mode,
            scenario_active=scenario_active,
            probability_a=prob_a,
            probability_b=prob_b,
            probability_c=prob_c,
            alignment_state=alignment_state,
            risk_requested=risk_requested,
            risk_allowed=risk_allowed,
            risk_budget_status=risk_budget_status,
            execution_type=execution_type,
            execution_attempted=True,
            execution_result="ALLOWED",
            block_reason=None,
            block_gate=None
        )
        
        return ExecutionDecision(
            allowed=True,
            reason="ALL_CHECKS_PASSED",
            block_gate=None,
            token_consumed=True,
            log_id=log_id
        )
    
    def _block(
        self,
        token_id: Optional[str],
        token_status: str,
        symbol: str,
        timeframe: str,
        market_mode: str,
        scenario_active: str,
        prob_a: float,
        prob_b: float,
        prob_c: float,
        alignment_state: str,
        risk_requested: float,
        risk_allowed: float,
        risk_budget_status: str,
        execution_type: str,
        reason: str,
        gate: str
    ) -> ExecutionDecision:
        """
        Block execution and log.
        
        Args:
            (various context parameters)
            reason: Block reason
            gate: Which gate blocked (STEP_1, STEP_2, etc.)
        
        Returns:
            ExecutionDecision with allowed=False
        """
        log_id = self.audit_log.log_execution_attempt(
            token_id=token_id,
            token_status=token_status,
            symbol=symbol,
            timeframe=timeframe,
            market_mode=market_mode,
            scenario_active=scenario_active,
            probability_a=prob_a,
            probability_b=prob_b,
            probability_c=prob_c,
            alignment_state=alignment_state,
            risk_requested=risk_requested,
            risk_allowed=risk_allowed,
            risk_budget_status=risk_budget_status,
            execution_type=execution_type,
            execution_attempted=False,
            execution_result="BLOCKED",
            block_reason=reason,
            block_gate=gate
        )
        
        return ExecutionDecision(
            allowed=False,
            reason=reason,
            block_gate=gate,
            token_consumed=False,
            log_id=log_id
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get gatekeeper statistics.
        
        Returns:
            Dictionary with stats
        """
        return self.audit_log.get_stats()
