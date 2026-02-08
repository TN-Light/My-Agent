"""
PHASE-7C: EXECUTION TOKEN
Purpose: Permission token for trade execution - single-use, time-bound, immutable

NON-NEGOTIABLE RULES:
1. Token can only be used ONCE
2. Token expires after 15 minutes
3. Token is bound to: symbol, scenario, risk limit
4. Token cannot be modified after creation
5. Token reuse or expiry = HARD BLOCK

Philosophy:
"Execution is permission-based, not signal-based."
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional


class ExecutionToken:
    """
    Permission token for trade execution.
    
    Immutable after creation. Single-use only. Time-bound.
    """
    
    # Token lifetime (minutes)
    TOKEN_LIFETIME_MINUTES = 15
    
    def __init__(
        self,
        symbol: str,
        scenario: str,
        max_risk: float,
        market_mode: str,
        alignment_state: str,
        probability_active: float
    ):
        """
        Create execution token.
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY", "BANKNIFTY")
            scenario: Active scenario ("A", "B", "C")
            max_risk: Maximum risk allowed (INR)
            market_mode: Trading mode ("INTRADAY", "SWING")
            alignment_state: Alignment at token creation ("FULL ALIGNMENT", "UNSTABLE", etc.)
            probability_active: Probability of active scenario (0.0-1.0)
        """
        # Immutable fields (read-only after init)
        self._token_id = str(uuid.uuid4())
        self._symbol = symbol
        self._scenario = scenario
        self._max_risk = max_risk
        self._market_mode = market_mode
        self._alignment_state = alignment_state
        self._probability_active = probability_active
        self._created_at = datetime.now()
        self._expires_at = self._created_at + timedelta(minutes=self.TOKEN_LIFETIME_MINUTES)
        
        # Mutable state (single-use enforcement)
        self._used = False
        self._used_at: Optional[datetime] = None
        
        # Validation
        if max_risk <= 0:
            raise ValueError(f"Invalid max_risk: {max_risk}. Must be > 0.")
        if scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid scenario: {scenario}. Must be A, B, or C.")
        if market_mode not in ["INTRADAY", "SWING"]:
            raise ValueError(f"Invalid market_mode: {market_mode}. Must be INTRADAY or SWING.")
        if not (0.0 <= probability_active <= 1.0):
            raise ValueError(f"Invalid probability: {probability_active}. Must be 0.0-1.0.")
    
    @property
    def token_id(self) -> str:
        """Unique token identifier."""
        return self._token_id
    
    @property
    def symbol(self) -> str:
        """Trading symbol."""
        return self._symbol
    
    @property
    def scenario(self) -> str:
        """Active scenario (A/B/C)."""
        return self._scenario
    
    @property
    def max_risk(self) -> float:
        """Maximum risk allowed (INR)."""
        return self._max_risk
    
    @property
    def market_mode(self) -> str:
        """Trading mode (INTRADAY/SWING)."""
        return self._market_mode
    
    @property
    def alignment_state(self) -> str:
        """Alignment at token creation."""
        return self._alignment_state
    
    @property
    def probability_active(self) -> float:
        """Probability of active scenario."""
        return self._probability_active
    
    @property
    def created_at(self) -> datetime:
        """Token creation timestamp."""
        return self._created_at
    
    @property
    def expires_at(self) -> datetime:
        """Token expiry timestamp."""
        return self._expires_at
    
    @property
    def used(self) -> bool:
        """Whether token has been used."""
        return self._used
    
    @property
    def used_at(self) -> Optional[datetime]:
        """Timestamp when token was used."""
        return self._used_at
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now() > self._expires_at
    
    def time_remaining(self) -> float:
        """
        Get time remaining before expiry (seconds).
        
        Returns:
            Seconds remaining (negative if expired)
        """
        delta = self._expires_at - datetime.now()
        return delta.total_seconds()
    
    def consume(self) -> None:
        """
        Mark token as used.
        
        Raises:
            RuntimeError: If token already used or expired
        """
        if self._used:
            raise RuntimeError(
                f"TOKEN_REUSE: Token {self._token_id} already used at {self._used_at}"
            )
        
        if self.is_expired():
            raise RuntimeError(
                f"TOKEN_EXPIRED: Token {self._token_id} expired at {self._expires_at}"
            )
        
        # Consume token (irreversible)
        self._used = True
        self._used_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert token to dictionary for logging."""
        return {
            "token_id": self._token_id,
            "symbol": self._symbol,
            "scenario": self._scenario,
            "max_risk": self._max_risk,
            "market_mode": self._market_mode,
            "alignment_state": self._alignment_state,
            "probability_active": self._probability_active,
            "created_at": self._created_at.isoformat(),
            "expires_at": self._expires_at.isoformat(),
            "used": self._used,
            "used_at": self._used_at.isoformat() if self._used_at else None,
            "time_remaining_seconds": self.time_remaining()
        }
    
    def __repr__(self) -> str:
        """String representation."""
        status = "CONSUMED" if self._used else ("EXPIRED" if self.is_expired() else "ACTIVE")
        return (
            f"ExecutionToken(id={self._token_id[:8]}, "
            f"symbol={self._symbol}, scenario={self._scenario}, "
            f"risk={self._max_risk:.2f}, status={status})"
        )


# Token validation results
class TokenValidationResult:
    """Result of token validation."""
    
    def __init__(self, valid: bool, reason: Optional[str] = None):
        self.valid = valid
        self.reason = reason
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.valid
    
    def __repr__(self) -> str:
        """String representation."""
        if self.valid:
            return "TokenValidationResult(VALID)"
        else:
            return f"TokenValidationResult(INVALID: {self.reason})"
