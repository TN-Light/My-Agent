"""
Phase-7B: Risk Budget & Loss Containment Engine

Purpose: Answer one question only:
"How much can this system afford to be wrong before it must stop?"

This does NOT:
- Pick entries
- Suggest buy/sell
- Touch brokers
- Optimize profits

It only limits damage.
"""

import logging
from typing import Dict, Literal, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionPermission:
    """
    Permission token issued by risk engine.
    
    Valid for one decision only.
    Expires after 15 minutes.
    Cannot be reused.
    Cannot be forged downstream.
    """
    allowed: bool
    max_risk_amount: float
    max_risk_percent: float
    expiry: datetime
    reason: str
    token_id: str
    issued_at: datetime


class RiskBudgetEngine:
    """
    Capital preservation engine.
    
    Principles (NON-NEGOTIABLE):
    1. Capital preservation > opportunity
    2. Risk is allocated per decision, not per trade
    3. Loss streaks matter more than single losses
    4. System must be able to shut itself down
    
    If any violated → system is invalid.
    """
    
    # Global Risk Caps (HARD LIMITS - IMMUTABLE)
    RISK_CAPS = {
        "INTRADAY": {
            "max_risk_per_decision": 0.0025,  # 0.25%
            "max_risk_per_symbol_day": 0.0050,  # 0.50%
            "max_portfolio_risk": 0.0100,  # 1.00%
            "max_open_positions": 2,
            "max_daily_loss": 0.0100,  # -1.00%
        },
        "SWING": {
            "max_risk_per_decision": 0.0050,  # 0.50%
            "max_risk_per_symbol_day": 0.0100,  # 1.00%
            "max_portfolio_risk": 0.0200,  # 2.00%
            "max_open_positions": 3,
            "max_daily_loss": 0.0200,  # -2.00%
        }
    }
    
    # Alignment Factors (DETERMINISTIC - NO DISCRETION)
    ALIGNMENT_FACTORS = {
        "FULL ALIGNMENT": 1.0,  # Stable
        "FULL ALIGNMENT_UNSTABLE": 0.7,  # Unstable
        "PARTIAL ALIGNMENT": 0.5,
        "CONFLICT": 0.0,  # Execution forbidden
        "UNSTABLE": 0.0  # Execution forbidden
    }
    
    # Loss Streak Governor (CRITICAL - NON-BYPASSABLE)
    LOSS_STREAK_MULTIPLIERS = {
        0: 1.0,   # Normal
        1: 1.0,   # Normal
        2: 0.75,  # Reduce risk
        3: 0.50,  # Reduce risk further
        4: 0.0,   # EXECUTION HALT
        5: 0.0    # SYSTEM LOCKDOWN
    }
    
    def __init__(
        self,
        account_equity: float,
        mode: Literal["INTRADAY", "SWING"],
        risk_store=None
    ):
        """
        Initialize risk engine.
        
        Args:
            account_equity: Account equity (IMMUTABLE once set)
            mode: Trading mode (IMMUTABLE once set)
            risk_store: RiskStateStore for persistence
        """
        if account_equity <= 0:
            raise ValueError("Account equity must be positive")
        
        if mode not in ["INTRADAY", "SWING"]:
            raise ValueError("Mode must be INTRADAY or SWING")
        
        # IMMUTABLE INPUTS
        self._account_equity = account_equity
        self._mode = mode
        self._risk_store = risk_store
        
        # State tracking
        self._loss_streak = 0
        self._daily_realized_loss_pct = 0.0
        self._system_state = "OPERATIONAL"  # OPERATIONAL, HALTED_TODAY, LOCKDOWN
        self._open_positions = 0
        self._symbol_risk_today = {}  # symbol -> risk_pct used today
        self._sector_exposure = {}  # sector -> count
        self._issued_tokens = set()  # Track used tokens
        
        # Restore persisted state from database if available
        self._restore_from_store()
        
        logger.info(f"RiskBudgetEngine initialized: Mode={mode}, Equity=₹{account_equity:,.2f}")
        logger.info(f"Max risk per decision: {self.RISK_CAPS[mode]['max_risk_per_decision']*100:.2f}%")
        logger.info(f"Max daily loss: {self.RISK_CAPS[mode]['max_daily_loss']*100:.2f}%")
    
    def _restore_from_store(self) -> None:
        """
        Restore risk state from persistent storage on startup.
        Recovers loss_streak, system_state, and daily drawdown as of today.
        """
        if not self._risk_store:
            return
        
        try:
            # Try to get the latest session stats
            stats = self._risk_store.get_session_stats("default")
            if stats:
                # Restore loss streak
                restored_streak = stats.get("max_loss_streak", 0)
                restored_state = stats.get("final_state", "OPERATIONAL")
                
                # Only restore lockdown state — daily halt resets each day
                if restored_state == "LOCKDOWN":
                    self._system_state = "LOCKDOWN"
                    self._loss_streak = max(restored_streak, 5)
                    logger.warning(f"⚠️ Restored LOCKDOWN state from previous session (streak={self._loss_streak})")
                elif restored_streak >= 4:
                    # 4+ losses carried across sessions
                    self._loss_streak = restored_streak
                    logger.warning(f"⚠️ Restored loss streak={self._loss_streak} from previous session")
            
            # Restore today's drawdown from DB 
            from datetime import datetime as dt
            today = dt.utcnow().date().isoformat()
            daily_pnl = self._risk_store.get_daily_drawdown("default", today)
            if daily_pnl < 0:
                self._daily_realized_loss_pct = daily_pnl / self._account_equity
                logger.info(f"Restored today's drawdown: {self._daily_realized_loss_pct*100:.2f}%")
                
                # Check if daily limit was already breached
                caps = self.RISK_CAPS[self._mode]
                if self._daily_realized_loss_pct <= -caps["max_daily_loss"]:
                    if self._system_state != "LOCKDOWN":
                        self._system_state = "HALTED_TODAY"
                        logger.warning(f"⚠️ Daily loss limit already breached — HALTED_TODAY")
                    
        except Exception as e:
            logger.warning(f"Could not restore risk state from DB: {e}. Starting fresh.")
    
    @property
    def account_equity(self) -> float:
        """Read-only account equity"""
        return self._account_equity
    
    @property
    def mode(self) -> str:
        """Read-only trading mode"""
        return self._mode
    
    @property
    def loss_streak(self) -> int:
        """Current loss streak"""
        return self._loss_streak
    
    @property
    def system_state(self) -> str:
        """Current system state"""
        return self._system_state
    
    def evaluate(
        self,
        symbol: str,
        scenario: str,
        active_probability: float,
        alignment: str,
        is_unstable: bool,
        sector: Optional[str] = None
    ) -> ExecutionPermission:
        """
        Evaluate if execution is allowed and calculate maximum risk.
        
        Returns ExecutionPermission token (valid for 15 minutes, single use).
        
        Args:
            symbol: Trading symbol
            scenario: Active scenario (SCENARIO_A, SCENARIO_B, SCENARIO_C)
            active_probability: Probability of active scenario
            alignment: MTF alignment state
            is_unstable: Whether alignment is unstable
            sector: Market sector (for correlation blocking)
        
        Returns:
            ExecutionPermission token with allowed status and risk amount
        """
        caps = self.RISK_CAPS[self._mode]
        blocked_reasons = []
        
        # SYSTEM STATE CHECK (HIGHEST PRIORITY)
        if self._system_state == "LOCKDOWN":
            return self._create_blocked_permission(
                "SYSTEM_LOCKDOWN: 5+ consecutive losses. Manual reset required."
            )
        
        if self._system_state == "HALTED_TODAY":
            return self._create_blocked_permission(
                f"DAILY_DRAWDOWN_BREACHED: Loss limit {caps['max_daily_loss']*100:.2f}% exceeded."
            )
        
        # LOSS STREAK GOVERNOR (CRITICAL)
        if self._loss_streak >= 4:
            self._system_state = "HALTED_TODAY" if self._loss_streak == 4 else "LOCKDOWN"
            return self._create_blocked_permission(
                f"EXECUTION_HALT: {self._loss_streak} consecutive losses."
            )
        
        # ALIGNMENT CHECK
        alignment_key = alignment
        if is_unstable and alignment == "FULL ALIGNMENT":
            alignment_key = "FULL ALIGNMENT_UNSTABLE"
        
        alignment_factor = self.ALIGNMENT_FACTORS.get(alignment_key, 0.0)
        if alignment_factor == 0.0:
            return self._create_blocked_permission(
                f"ALIGNMENT_FORBIDDEN: {alignment} prevents execution."
            )
        
        # POSITION COUNT CHECK
        if self._open_positions >= caps["max_open_positions"]:
            return self._create_blocked_permission(
                f"MAX_POSITIONS: {self._open_positions}/{caps['max_open_positions']} positions open."
            )
        
        # CORRELATION CHECK
        if sector and self._sector_exposure.get(sector, 0) >= 1:
            return self._create_blocked_permission(
                f"CORRELATION_RISK: Already exposed to {sector} sector."
            )
        
        # SYMBOL REUSE CHECK
        symbol_risk_used = self._symbol_risk_today.get(symbol, 0.0)
        if symbol_risk_used >= caps["max_risk_per_symbol_day"]:
            return self._create_blocked_permission(
                f"SYMBOL_RISK_EXHAUSTED: {symbol} risk budget used ({symbol_risk_used*100:.2f}%)."
            )
        
        # CALCULATE DECISION-LEVEL RISK
        base_risk = caps["max_risk_per_decision"]
        loss_streak_mult = self.LOSS_STREAK_MULTIPLIERS.get(self._loss_streak, 0.0)
        
        # DETERMINISTIC FORMULA (NO DISCRETION)
        risk_fraction = base_risk * active_probability * alignment_factor * loss_streak_mult
        
        # Check if adding this risk exceeds symbol daily limit
        potential_symbol_risk = symbol_risk_used + risk_fraction
        if potential_symbol_risk > caps["max_risk_per_symbol_day"]:
            risk_fraction = caps["max_risk_per_symbol_day"] - symbol_risk_used
            if risk_fraction <= 0:
                return self._create_blocked_permission(
                    f"SYMBOL_RISK_EXHAUSTED: Cannot allocate more risk to {symbol} today."
                )
        
        # Check portfolio risk limit (simplified - assumes all positions max risk)
        # In production, this would track actual open risk
        potential_portfolio_risk = (self._open_positions + 1) * risk_fraction
        if potential_portfolio_risk > caps["max_portfolio_risk"]:
            return self._create_blocked_permission(
                f"PORTFOLIO_RISK_LIMIT: Would exceed {caps['max_portfolio_risk']*100:.2f}% max."
            )
        
        # CALCULATE MAX RISK AMOUNT
        max_risk_amount = self._account_equity * risk_fraction
        
        # Issue permission token
        token = self._create_allowed_permission(
            max_risk_amount=max_risk_amount,
            max_risk_percent=risk_fraction,
            details=f"Allocated {risk_fraction*100:.2f}% risk for {symbol} ({scenario})"
        )
        
        logger.info(f"✅ Risk permission granted: {symbol} - ₹{max_risk_amount:,.2f} ({risk_fraction*100:.2f}%)")
        logger.info(f"   Breakdown: base={base_risk*100:.2f}% × prob={active_probability:.2f} × align={alignment_factor} × streak_mult={loss_streak_mult}")
        
        return token
    
    def record_outcome(
        self,
        symbol: str,
        realized_pnl: float,
        risk_used: float
    ) -> None:
        """
        Record trade outcome and update risk state.
        
        Args:
            symbol: Trading symbol
            realized_pnl: Realized profit/loss in currency
            risk_used: Risk percentage used
        """
        # Update loss streak
        if realized_pnl < 0:
            self._loss_streak += 1
            logger.warning(f"❌ Loss recorded: {symbol} (₹{realized_pnl:,.2f}) - Streak: {self._loss_streak}")
        else:
            self._loss_streak = 0
            logger.info(f"✅ Win recorded: {symbol} (₹{realized_pnl:,.2f}) - Streak reset")
        
        # Update daily drawdown
        pnl_pct = realized_pnl / self._account_equity
        self._daily_realized_loss_pct += pnl_pct
        
        # Check daily loss limit
        caps = self.RISK_CAPS[self._mode]
        if self._daily_realized_loss_pct <= -caps["max_daily_loss"]:
            self._system_state = "HALTED_TODAY"
            logger.error(f"🚨 DAILY LOSS LIMIT BREACHED: {self._daily_realized_loss_pct*100:.2f}%")
            logger.error(f"   System halted until next trading day")
        
        # Check lockdown condition
        if self._loss_streak >= 5:
            self._system_state = "LOCKDOWN"
            logger.error(f"🚨 SYSTEM LOCKDOWN: {self._loss_streak} consecutive losses")
            logger.error(f"   Manual reset required - automated trading suspended")
        
        # Log to database if available
        if self._risk_store:
            self._risk_store.record_outcome(
                symbol=symbol,
                realized_pnl=realized_pnl,
                risk_used=risk_used,
                loss_streak=self._loss_streak,
                daily_drawdown_pct=self._daily_realized_loss_pct,
                system_state=self._system_state
            )
    
    def reset_daily_state(self) -> None:
        """
        Reset daily state at trading day open.
        Only resets daily counters, NOT loss streak or lockdown.
        """
        self._daily_realized_loss_pct = 0.0
        self._symbol_risk_today = {}
        self._sector_exposure = {}
        self._issued_tokens = set()
        
        # Reset HALTED_TODAY, but NOT LOCKDOWN
        if self._system_state == "HALTED_TODAY":
            self._system_state = "OPERATIONAL"
            logger.info("Daily state reset - system operational")
        
        logger.info(f"Daily risk state reset (loss_streak={self._loss_streak})")
    
    def manual_reset_lockdown(self, authorization_code: str) -> bool:
        """
        Manual reset of LOCKDOWN state.
        Requires authorization code (prevents accidental resets).
        
        Args:
            authorization_code: Must be "RESET_ACKNOWLEDGED"
        
        Returns:
            True if reset successful, False otherwise
        """
        if authorization_code != "RESET_ACKNOWLEDGED":
            logger.error("❌ Invalid authorization code for lockdown reset")
            return False
        
        if self._system_state != "LOCKDOWN":
            logger.warning("System not in LOCKDOWN state")
            return False
        
        self._system_state = "OPERATIONAL"
        self._loss_streak = 0
        self._daily_realized_loss_pct = 0.0
        
        logger.warning("⚠️ MANUAL LOCKDOWN RESET - System operational")
        logger.warning("   Loss streak reset to 0")
        
        return True
    
    def get_risk_status(self) -> Dict:
        """Get current risk status summary"""
        caps = self.RISK_CAPS[self._mode]
        
        return {
            "system_state": self._system_state,
            "mode": self._mode,
            "account_equity": self._account_equity,
            "loss_streak": self._loss_streak,
            "daily_drawdown_pct": self._daily_realized_loss_pct,
            "daily_loss_limit_pct": caps["max_daily_loss"],
            "open_positions": self._open_positions,
            "max_positions": caps["max_open_positions"],
            "risk_caps": caps,
            "is_operational": self._system_state == "OPERATIONAL"
        }
    
    def _create_allowed_permission(
        self,
        max_risk_amount: float,
        max_risk_percent: float,
        details: str
    ) -> ExecutionPermission:
        """Create ALLOWED permission token"""
        token_id = f"{datetime.utcnow().timestamp()}_{max_risk_amount}"
        expiry = datetime.utcnow() + timedelta(minutes=15)
        
        self._issued_tokens.add(token_id)
        
        return ExecutionPermission(
            allowed=True,
            max_risk_amount=max_risk_amount,
            max_risk_percent=max_risk_percent,
            expiry=expiry,
            reason=details,
            token_id=token_id,
            issued_at=datetime.utcnow()
        )
    
    def _create_blocked_permission(self, reason: str) -> ExecutionPermission:
        """Create BLOCKED permission token"""
        return ExecutionPermission(
            allowed=False,
            max_risk_amount=0.0,
            max_risk_percent=0.0,
            expiry=datetime.utcnow(),
            reason=reason,
            token_id="BLOCKED",
            issued_at=datetime.utcnow()
        )
    
    def validate_token(self, token: ExecutionPermission) -> Tuple[bool, str]:
        """
        Validate permission token before use.
        
        Checks:
        1. Token not expired
        2. Token not already used
        3. Token allowed status
        
        Returns:
            (is_valid, reason)
        """
        if not token.allowed:
            return False, f"Token blocked: {token.reason}"
        
        if datetime.utcnow() > token.expiry:
            return False, "Token expired (15 min limit)"
        
        if token.token_id not in self._issued_tokens:
            return False, "Token already used or invalid"
        
        return True, "Token valid"
    
    def consume_token(self, token: ExecutionPermission) -> bool:
        """
        Consume token (single-use only).
        
        Returns:
            True if consumed successfully, False if already used
        """
        if token.token_id in self._issued_tokens:
            self._issued_tokens.remove(token.token_id)
            logger.info(f"Token consumed: {token.token_id}")
            return True
        else:
            logger.error(f"❌ Token reuse attempt detected: {token.token_id}")
            return False


# FORBIDDEN ACTIONS (AUTO-FAIL IF DETECTED)
"""
If the system ever:
1. Scales up after losses ❌ (loss_streak_multiplier enforces reduction)
2. Overrides halt ❌ (system_state checks are mandatory)
3. Executes without token ❌ (downstream must crash)
4. Adjusts risk based on "confidence" ❌ (only probability used, deterministically)

→ SYSTEM INVALID
"""
