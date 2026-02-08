"""
Phase-C: Entry Logic Engine

Purpose: Convert a SignalContract (Phase-11 output) + structural data into
a concrete TradeSetupPlan with entry price, stop loss, targets, position size,
and risk/reward ratio.

This is the BRIDGE between the live analysis pipeline (Phases 1-16) and the
dead execution/tracking infrastructure (Phases 7B, 8A, 8B, 8C, 9).

Pipeline position:
  SignalEligibilityEngine (Phase-11) → [THIS MODULE] → HumanConfirmationProtocol (Phase-9)
                                                      → TradeLifecycleTracker (Phase-8A)
                                                      → RiskBudgetEngine (Phase-7B)

NON-NEGOTIABLE RULES:
1. Only generates setups for ELIGIBLE signals — never forces an entry
2. Stops are ALWAYS structural — never arbitrary percentages
3. Position sizing comes ONLY from RiskBudgetEngine — no overrides
4. Every setup has explicit invalidation conditions
5. Human confirmation is ALWAYS required (execution_mode = HUMAN_ONLY)
6. Risk/reward minimum is 1.5:1 — setups below this are rejected
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────
# DATA TYPES
# ─────────────────────────────────────────────────

@dataclass
class TradeSetupPlan:
    """
    Concrete trade setup with all execution parameters.
    
    This is what gets presented to the human via HumanConfirmationProtocol,
    and what gets recorded in TradeLifecycleTracker if confirmed.
    """
    # Identity
    symbol: str
    direction: str                  # "LONG" / "SHORT"
    setup_time: str                 # ISO timestamp
    
    # Signal context (from Phase-11)
    verdict: str                    # STRONG / CAUTION / WAIT
    confidence: str                 # HIGH / MEDIUM / LOW
    signal_type: str                # TREND_CONTINUATION / PULLBACK / BREAKOUT
    entry_style: str                # PULLBACK_ONLY / BREAKOUT_ONLY / IMMEDIATE_OK
    active_scenario: str            # SCENARIO_A / B / C
    scenario_probability: float     # Probability of active scenario
    alignment_state: str            # FULL / PARTIAL / etc.
    
    # Entry zone
    entry_price: float              # Primary entry level
    entry_zone_low: float           # Entry zone lower bound
    entry_zone_high: float          # Entry zone upper bound
    entry_rationale: str            # "Pullback to weekly support at X"
    
    # Risk management
    stop_loss: float                # Hard stop (structural)
    stop_loss_reason: str           # "Below weekly support at X with 1% buffer"
    risk_per_share: float           # |entry_price - stop_loss|
    
    # Targets
    target_1: float                 # Conservative target (~1.5R)
    target_1_reason: str            # "Weekly resistance at X"
    
    # Risk/reward
    risk_reward_t1: float           # R:R to target 1
    
    # --- Fields with defaults below this line ---
    
    # Optional targets
    target_2: Optional[float] = None  # Extended target (~2.5R)
    target_2_reason: str = ""
    target_3: Optional[float] = None  # Full extension (~4R)
    target_3_reason: str = ""
    
    risk_reward_t2: Optional[float] = None  # R:R to target 2
    
    # Position sizing (from RiskBudgetEngine)
    max_risk_amount: float = 0.0    # ₹ amount from risk engine
    position_size: int = 0          # Shares/lots
    position_value: float = 0.0     # position_size × entry_price
    
    # Invalidation
    invalidation_condition: str = ""   # "HTF support break below X"
    time_invalidation: str = ""        # "Setup invalid after 5 trading days"
    
    # Regime context
    regime: str = ""                   # Current market regime
    htf_location: str = ""             # SUPPORT / MID / RESISTANCE
    trend_state: str = ""              # UP / DOWN / RANGE
    
    # Flags
    requires_human_confirmation: bool = True  # ALWAYS True
    risk_budget_approved: bool = False        # Whether RiskBudgetEngine approved
    risk_budget_reason: str = ""              # Reason if rejected
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization/logging."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "setup_time": self.setup_time,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "signal_type": self.signal_type,
            "entry_style": self.entry_style,
            "active_scenario": self.active_scenario,
            "scenario_probability": self.scenario_probability,
            "alignment_state": self.alignment_state,
            "entry_price": self.entry_price,
            "entry_zone": f"{self.entry_zone_low:.2f} - {self.entry_zone_high:.2f}",
            "entry_rationale": self.entry_rationale,
            "stop_loss": self.stop_loss,
            "stop_loss_reason": self.stop_loss_reason,
            "risk_per_share": self.risk_per_share,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "target_3": self.target_3,
            "risk_reward_t1": self.risk_reward_t1,
            "risk_reward_t2": self.risk_reward_t2,
            "max_risk_amount": self.max_risk_amount,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "invalidation_condition": self.invalidation_condition,
            "time_invalidation": self.time_invalidation,
            "risk_budget_approved": self.risk_budget_approved,
        }


# ─────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────

# Minimum risk/reward ratio to accept a setup
MIN_RISK_REWARD = 1.5

# Buffer percentages for structural levels
STOP_BUFFER_PCT = 0.01       # 1% below/above structural level
ENTRY_ZONE_PCT = 0.005       # 0.5% entry zone width
BREAKOUT_BUFFER_PCT = 0.003  # 0.3% above/below breakout level

# Too-close threshold: if stop is within this % of price, widen to next level
MIN_STOP_DISTANCE_PCT = 0.015  # 1.5% minimum stop distance

# Time invalidation by setup type
TIME_INVALIDATION = {
    "PULLBACK_ONLY": "5 trading days",
    "BREAKOUT_ONLY": "3 trading days",
    "IMMEDIATE_OK": "2 trading days",
}

# Target R-multiples
TARGET_1_R = 1.5   # Conservative
TARGET_2_R = 2.5   # Extended
TARGET_3_R = 4.0   # Full extension


# ─────────────────────────────────────────────────
# ENTRY LOGIC ENGINE
# ─────────────────────────────────────────────────

class EntryLogicEngine:
    """
    Converts structural analysis + signal eligibility into concrete trade plans.
    
    Inputs (all from live modules):
    - SignalContract from SignalEligibilityEngine (Phase-11)
    - Structural levels (support/resistance) from TechnicalAnalyzer (Phase-3)
    - Scenario probabilities from ScenarioProbabilityCalculator (Phase-6A)
    - Risk budget from RiskBudgetEngine (Phase-7B)
    
    Output:
    - TradeSetupPlan with entry, stop, targets, position size
    
    Design philosophy:
    - Entry logic is DETERMINISTIC — same inputs always produce same output
    - Stops are STRUCTURAL — derived from HTF support/resistance, never arbitrary
    - Position sizing is CONSTRAINED — RiskBudgetEngine has final say
    - Bad setups are REJECTED — if R:R < 1.5, no plan is generated
    """
    
    def __init__(self, risk_budget_engine=None):
        """
        Initialize entry logic engine.
        
        Args:
            risk_budget_engine: RiskBudgetEngine instance for position sizing.
                               If None, position sizing is skipped but setup
                               is still generated for analysis purposes.
        """
        self.risk_engine = risk_budget_engine
        logger.info("Phase-C: Entry Logic Engine initialized")
    
    def generate_setup(
        self,
        signal,  # SignalContract from signal_eligibility.py
        symbol: str,
        current_price: float,
        monthly_support: List[float],
        monthly_resistance: List[float],
        weekly_support: List[float],
        weekly_resistance: List[float],
        scenario_probabilities: Dict[str, float],
        alignment: str = "",
        is_unstable: bool = False,
        regime: str = "",
        account_equity: float = 0.0,
        mode: str = "SWING"
    ) -> Optional[TradeSetupPlan]:
        """
        Generate a concrete trade setup plan from a signal.
        
        Only produces a plan if:
        1. Signal status is ELIGIBLE
        2. Entry style is not NO_ENTRY
        3. Structural levels are available for stop placement
        4. Risk/reward ratio meets minimum threshold (1.5:1)
        
        Args:
            signal: SignalContract from Phase-11
            symbol: Trading symbol
            current_price: Current market price
            monthly_support: Monthly support levels (descending)
            monthly_resistance: Monthly resistance levels (ascending)
            weekly_support: Weekly support levels (descending)
            weekly_resistance: Weekly resistance levels (ascending)
            scenario_probabilities: Dict with A_continuation, B_pullback, C_failure
            alignment: MTF alignment state string
            is_unstable: Whether alignment is unstable
            regime: Current market regime string
            account_equity: Account equity for position sizing (0 = skip sizing)
            mode: Trading mode (INTRADAY/SWING)
        
        Returns:
            TradeSetupPlan if setup meets all criteria, None otherwise
        """
        # Gate 1: Signal must be ELIGIBLE
        if not signal or signal.signal_status.value != "ELIGIBLE":
            logger.info(f"Phase-C: {symbol} — no setup (signal not eligible)")
            return None
        
        # Gate 2: Entry style must allow entry
        if signal.entry_style.value == "NO_ENTRY":
            logger.info(f"Phase-C: {symbol} — no setup (entry style = NO_ENTRY)")
            return None
        
        # Gate 3: Must have structural levels
        all_support = self._sort_levels(monthly_support + weekly_support)
        all_resistance = self._sort_levels(monthly_resistance + weekly_resistance)
        
        if not all_support and not all_resistance:
            logger.warning(f"Phase-C: {symbol} — no setup (no structural levels)")
            return None
        
        # Gate 4: Must have a valid price
        if current_price <= 0:
            logger.warning(f"Phase-C: {symbol} — no setup (invalid price)")
            return None
        
        direction = signal.direction.value  # "LONG" / "SHORT" / "NEUTRAL"
        entry_style = signal.entry_style.value
        
        if direction == "NEUTRAL":
            logger.info(f"Phase-C: {symbol} — no setup (neutral direction)")
            return None
        
        try:
            # Step 1: Calculate entry price and zone
            entry_price, zone_low, zone_high, entry_rationale = self._calculate_entry(
                direction=direction,
                entry_style=entry_style,
                current_price=current_price,
                support_levels=all_support,
                resistance_levels=all_resistance
            )
            
            # Step 2: Calculate stop loss
            stop_loss, stop_reason = self._calculate_stop(
                direction=direction,
                entry_price=entry_price,
                current_price=current_price,
                support_levels=all_support,
                resistance_levels=all_resistance
            )
            
            # Step 3: Risk per share
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share < 0.01:
                logger.warning(f"Phase-C: {symbol} — no setup (risk per share too small)")
                return None
            
            # Step 4: Calculate targets
            t1, t1_reason, t2, t2_reason, t3, t3_reason = self._calculate_targets(
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_per_share=risk_per_share,
                support_levels=all_support,
                resistance_levels=all_resistance
            )
            
            # Step 5: Risk/reward check
            rr_t1 = abs(t1 - entry_price) / risk_per_share if risk_per_share > 0 else 0
            rr_t2 = abs(t2 - entry_price) / risk_per_share if t2 and risk_per_share > 0 else None
            
            if rr_t1 < MIN_RISK_REWARD:
                logger.info(f"Phase-C: {symbol} — no setup (R:R {rr_t1:.2f} < {MIN_RISK_REWARD})")
                return None
            
            # Step 6: Position sizing via RiskBudgetEngine
            max_risk_amount = 0.0
            position_size = 0
            position_value = 0.0
            risk_approved = False
            risk_reason = "No risk engine configured"
            
            if self.risk_engine:
                try:
                    # Get active scenario label
                    active_scenario = signal.active_scenario
                    active_prob = max(
                        scenario_probabilities.get("A_continuation", 0),
                        scenario_probabilities.get("B_pullback", 0),
                        scenario_probabilities.get("C_failure", 0)
                    )
                    
                    permission = self.risk_engine.evaluate(
                        symbol=symbol,
                        scenario=active_scenario,
                        active_probability=active_prob,
                        alignment=alignment or signal.alignment_state,
                        is_unstable=is_unstable
                    )
                    
                    if permission.allowed:
                        max_risk_amount = permission.max_risk_amount
                        position_size = int(max_risk_amount / risk_per_share) if risk_per_share > 0 else 0
                        position_value = position_size * entry_price
                        risk_approved = True
                        risk_reason = "Approved"
                        logger.info(f"Phase-C: {symbol} — risk approved: ₹{max_risk_amount:.2f}, "
                                    f"{position_size} shares")
                    else:
                        risk_reason = permission.reason
                        logger.info(f"Phase-C: {symbol} — risk denied: {risk_reason}")
                except Exception as risk_err:
                    risk_reason = f"Risk evaluation error: {risk_err}"
                    logger.warning(f"Phase-C: {symbol} — {risk_reason}")
            elif account_equity > 0:
                # Fallback: simple 1% risk calculation if no RiskBudgetEngine
                max_risk_amount = account_equity * 0.005  # 0.5% default
                position_size = int(max_risk_amount / risk_per_share) if risk_per_share > 0 else 0
                position_value = position_size * entry_price
                risk_approved = True
                risk_reason = "Fallback sizing (no risk engine)"
            
            # Step 7: Invalidation conditions
            invalidation, time_inv = self._calculate_invalidation(
                direction=direction,
                entry_style=entry_style,
                stop_loss=stop_loss,
                support_levels=all_support,
                resistance_levels=all_resistance
            )
            
            # Step 8: Build the plan
            setup = TradeSetupPlan(
                symbol=symbol,
                direction=direction,
                setup_time=datetime.now().isoformat(),
                verdict=signal.verdict,
                confidence=signal.confidence,
                signal_type=signal.signal_type.value if signal.signal_type else "UNKNOWN",
                entry_style=entry_style,
                active_scenario=signal.active_scenario,
                scenario_probability=max(
                    scenario_probabilities.get("A_continuation", 0),
                    scenario_probabilities.get("B_pullback", 0),
                    scenario_probabilities.get("C_failure", 0)
                ),
                alignment_state=alignment or signal.alignment_state,
                entry_price=round(entry_price, 2),
                entry_zone_low=round(zone_low, 2),
                entry_zone_high=round(zone_high, 2),
                entry_rationale=entry_rationale,
                stop_loss=round(stop_loss, 2),
                stop_loss_reason=stop_reason,
                risk_per_share=round(risk_per_share, 2),
                target_1=round(t1, 2),
                target_1_reason=t1_reason,
                target_2=round(t2, 2) if t2 else None,
                target_2_reason=t2_reason,
                target_3=round(t3, 2) if t3 else None,
                target_3_reason=t3_reason,
                risk_reward_t1=round(rr_t1, 2),
                risk_reward_t2=round(rr_t2, 2) if rr_t2 else None,
                max_risk_amount=round(max_risk_amount, 2),
                position_size=position_size,
                position_value=round(position_value, 2),
                invalidation_condition=invalidation,
                time_invalidation=time_inv,
                regime=regime,
                htf_location=signal.htf_location,
                trend_state=signal.trend_state,
                requires_human_confirmation=True,
                risk_budget_approved=risk_approved,
                risk_budget_reason=risk_reason,
            )
            
            logger.info(
                f"Phase-C: {symbol} setup generated — "
                f"{direction} @ {entry_price:.2f}, "
                f"stop {stop_loss:.2f}, "
                f"T1 {t1:.2f} (R:R {rr_t1:.1f}), "
                f"size {position_size} shares"
            )
            
            return setup
            
        except Exception as e:
            logger.error(f"Phase-C: {symbol} setup generation failed: {e}", exc_info=True)
            return None
    
    # ─────────────────────────────────────────────
    # ENTRY CALCULATION
    # ─────────────────────────────────────────────
    
    def _calculate_entry(
        self,
        direction: str,
        entry_style: str,
        current_price: float,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> Tuple[float, float, float, str]:
        """
        Calculate entry price and zone based on entry style.
        
        Returns:
            (entry_price, zone_low, zone_high, rationale)
        """
        if entry_style == "PULLBACK_ONLY":
            return self._entry_pullback(direction, current_price, support_levels, resistance_levels)
        elif entry_style == "BREAKOUT_ONLY":
            return self._entry_breakout(direction, current_price, support_levels, resistance_levels)
        else:  # IMMEDIATE_OK
            return self._entry_immediate(direction, current_price)
    
    def _entry_pullback(
        self, direction: str, price: float,
        support: List[float], resistance: List[float]
    ) -> Tuple[float, float, float, str]:
        """
        PULLBACK entry: Wait for price to pull back to nearest structural level.
        
        LONG: Look for nearest support BELOW current price
        SHORT: Look for nearest resistance ABOVE current price
        """
        if direction == "LONG":
            # Find nearest support below current price
            candidates = [s for s in support if s < price]
            if candidates:
                level = max(candidates)  # Nearest support below
                zone_mid = level
                zone_low = level * (1 - ENTRY_ZONE_PCT)
                zone_high = level * (1 + ENTRY_ZONE_PCT)
                return zone_mid, zone_low, zone_high, f"Pullback to support at {level:.2f}"
            else:
                # No support below — fall back to immediate with discount
                entry = price * (1 - ENTRY_ZONE_PCT * 2)
                return entry, entry * 0.995, price, "No pullback level — entry near current price"
        else:  # SHORT
            # Find nearest resistance above current price
            candidates = [r for r in resistance if r > price]
            if candidates:
                level = min(candidates)  # Nearest resistance above
                zone_mid = level
                zone_low = level * (1 - ENTRY_ZONE_PCT)
                zone_high = level * (1 + ENTRY_ZONE_PCT)
                return zone_mid, zone_low, zone_high, f"Pullback to resistance at {level:.2f}"
            else:
                entry = price * (1 + ENTRY_ZONE_PCT * 2)
                return entry, price, entry * 1.005, "No pullback level — entry near current price"
    
    def _entry_breakout(
        self, direction: str, price: float,
        support: List[float], resistance: List[float]
    ) -> Tuple[float, float, float, str]:
        """
        BREAKOUT entry: Enter on confirmed break of structural level.
        
        LONG: Above nearest resistance (breakout confirmation)
        SHORT: Below nearest support (breakdown confirmation)
        """
        if direction == "LONG":
            # Find nearest resistance above or near current price
            candidates = [r for r in resistance if r >= price * 0.98]
            if candidates:
                level = min(candidates)
                entry = level * (1 + BREAKOUT_BUFFER_PCT)
                zone_low = level
                zone_high = entry * (1 + ENTRY_ZONE_PCT)
                return entry, zone_low, zone_high, f"Breakout above resistance at {level:.2f}"
            else:
                entry = price * (1 + BREAKOUT_BUFFER_PCT)
                return entry, price, entry * 1.005, "No breakout level — entry above current price"
        else:  # SHORT
            candidates = [s for s in support if s <= price * 1.02]
            if candidates:
                level = max(candidates)
                entry = level * (1 - BREAKOUT_BUFFER_PCT)
                zone_low = entry * (1 - ENTRY_ZONE_PCT)
                zone_high = level
                return entry, zone_low, zone_high, f"Breakdown below support at {level:.2f}"
            else:
                entry = price * (1 - BREAKOUT_BUFFER_PCT)
                return entry, entry * 0.995, price, "No breakdown level — entry below current price"
    
    def _entry_immediate(
        self, direction: str, price: float
    ) -> Tuple[float, float, float, str]:
        """IMMEDIATE entry: Enter at or near current price."""
        zone_low = price * (1 - ENTRY_ZONE_PCT)
        zone_high = price * (1 + ENTRY_ZONE_PCT)
        return price, zone_low, zone_high, f"Immediate entry at current price {price:.2f}"
    
    # ─────────────────────────────────────────────
    # STOP LOSS CALCULATION
    # ─────────────────────────────────────────────
    
    def _calculate_stop(
        self,
        direction: str,
        entry_price: float,
        current_price: float,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> Tuple[float, str]:
        """
        Calculate structural stop loss.
        
        Stops are ALWAYS placed beyond a structural level — never at
        arbitrary percentages. If the nearest level is too close,
        we widen to the next level.
        
        Returns:
            (stop_price, reason)
        """
        if direction == "LONG":
            return self._stop_long(entry_price, current_price, support_levels)
        else:
            return self._stop_short(entry_price, current_price, resistance_levels)
    
    def _stop_long(
        self, entry: float, price: float, support: List[float]
    ) -> Tuple[float, str]:
        """
        LONG stop: Below nearest structural support.
        
        Logic:
        1. Find all support levels below the entry price
        2. Start with nearest support
        3. If too close (< 1.5%), move to next support level
        4. Apply 1% buffer below the chosen support
        5. Fallback: 3% below entry if no structural levels
        """
        ref_price = min(entry, price)  # Use lower of entry/current
        candidates = sorted([s for s in support if s < ref_price], reverse=True)
        
        for level in candidates:
            stop = level * (1 - STOP_BUFFER_PCT)
            distance_pct = (ref_price - stop) / ref_price
            
            if distance_pct >= MIN_STOP_DISTANCE_PCT:
                return stop, f"Below support at {level:.2f} with {STOP_BUFFER_PCT*100:.0f}% buffer"
        
        # Fallback: If we have candidates but all too close, use the furthest
        if candidates:
            level = candidates[-1]  # Furthest support
            stop = level * (1 - STOP_BUFFER_PCT)
            distance_pct = (ref_price - stop) / ref_price
            if distance_pct >= 0.005:  # At least 0.5%
                return stop, f"Below distant support at {level:.2f}"
        
        # Ultimate fallback: 3% below entry
        stop = entry * (1 - 0.03)
        return stop, "No structural support — default 3% stop"
    
    def _stop_short(
        self, entry: float, price: float, resistance: List[float]
    ) -> Tuple[float, str]:
        """
        SHORT stop: Above nearest structural resistance.
        Same logic as _stop_long but inverted.
        """
        ref_price = max(entry, price)
        candidates = sorted([r for r in resistance if r > ref_price])
        
        for level in candidates:
            stop = level * (1 + STOP_BUFFER_PCT)
            distance_pct = (stop - ref_price) / ref_price
            
            if distance_pct >= MIN_STOP_DISTANCE_PCT:
                return stop, f"Above resistance at {level:.2f} with {STOP_BUFFER_PCT*100:.0f}% buffer"
        
        if candidates:
            level = candidates[-1]
            stop = level * (1 + STOP_BUFFER_PCT)
            distance_pct = (stop - ref_price) / ref_price
            if distance_pct >= 0.005:
                return stop, f"Above distant resistance at {level:.2f}"
        
        stop = entry * (1 + 0.03)
        return stop, "No structural resistance — default 3% stop"
    
    # ─────────────────────────────────────────────
    # TARGET CALCULATION
    # ─────────────────────────────────────────────
    
    def _calculate_targets(
        self,
        direction: str,
        entry_price: float,
        stop_loss: float,
        risk_per_share: float,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> Tuple[float, str, Optional[float], str, Optional[float], str]:
        """
        Calculate targets using R-multiples and structural levels.
        
        Strategy:
        - T1: Use structural level if it gives ≥ 1.5R, otherwise use 1.5R
        - T2: Use structural level if it gives ≥ 2.5R, otherwise use 2.5R
        - T3: Full extension at 4R (or next major structural level)
        
        Returns:
            (t1, t1_reason, t2, t2_reason, t3, t3_reason)
        """
        if direction == "LONG":
            return self._targets_long(entry_price, risk_per_share, resistance_levels)
        else:
            return self._targets_short(entry_price, risk_per_share, support_levels)
    
    def _targets_long(
        self, entry: float, risk: float, resistance: List[float]
    ) -> Tuple[float, str, Optional[float], str, Optional[float], str]:
        """LONG targets: resistance levels above entry, or R-multiples."""
        
        # R-multiple targets
        r_t1 = entry + (risk * TARGET_1_R)
        r_t2 = entry + (risk * TARGET_2_R)
        r_t3 = entry + (risk * TARGET_3_R)
        
        # Structural targets (resistance levels above entry)
        struct_targets = sorted([r for r in resistance if r > entry * 1.005])
        
        # T1: nearest structural level ≥ 1.5R, or 1.5R
        t1, t1_reason = r_t1, f"{TARGET_1_R}R target at {r_t1:.2f}"
        for level in struct_targets:
            if level >= r_t1 * 0.95:  # Within 5% of R target
                t1 = level
                t1_reason = f"Resistance at {level:.2f} (~{abs(level - entry) / risk:.1f}R)"
                break
        
        # T2: next structural level ≥ 2.5R, or 2.5R
        t2, t2_reason = r_t2, f"{TARGET_2_R}R target at {r_t2:.2f}"
        for level in struct_targets:
            if level > t1 * 1.01 and level >= r_t2 * 0.90:
                t2 = level
                t2_reason = f"Resistance at {level:.2f} (~{abs(level - entry) / risk:.1f}R)"
                break
        
        # T3: extended — use structural if available, else 4R
        t3, t3_reason = r_t3, f"{TARGET_3_R}R extension at {r_t3:.2f}"
        for level in struct_targets:
            if level > t2 * 1.01 and level >= r_t3 * 0.85:
                t3 = level
                t3_reason = f"Major resistance at {level:.2f} (~{abs(level - entry) / risk:.1f}R)"
                break
        
        return t1, t1_reason, t2, t2_reason, t3, t3_reason
    
    def _targets_short(
        self, entry: float, risk: float, support: List[float]
    ) -> Tuple[float, str, Optional[float], str, Optional[float], str]:
        """SHORT targets: support levels below entry, or R-multiples."""
        
        r_t1 = entry - (risk * TARGET_1_R)
        r_t2 = entry - (risk * TARGET_2_R)
        r_t3 = entry - (risk * TARGET_3_R)
        
        struct_targets = sorted([s for s in support if s < entry * 0.995], reverse=True)
        
        t1, t1_reason = r_t1, f"{TARGET_1_R}R target at {r_t1:.2f}"
        for level in struct_targets:
            if level <= r_t1 * 1.05:
                t1 = level
                t1_reason = f"Support at {level:.2f} (~{abs(entry - level) / risk:.1f}R)"
                break
        
        t2, t2_reason = r_t2, f"{TARGET_2_R}R target at {r_t2:.2f}"
        for level in struct_targets:
            if level < t1 * 0.99 and level <= r_t2 * 1.10:
                t2 = level
                t2_reason = f"Support at {level:.2f} (~{abs(entry - level) / risk:.1f}R)"
                break
        
        t3, t3_reason = r_t3, f"{TARGET_3_R}R extension at {r_t3:.2f}"
        for level in struct_targets:
            if level < t2 * 0.99 and level <= r_t3 * 1.15:
                t3 = level
                t3_reason = f"Major support at {level:.2f} (~{abs(entry - level) / risk:.1f}R)"
                break
        
        return t1, t1_reason, t2, t2_reason, t3, t3_reason
    
    # ─────────────────────────────────────────────
    # INVALIDATION
    # ─────────────────────────────────────────────
    
    def _calculate_invalidation(
        self,
        direction: str,
        entry_style: str,
        stop_loss: float,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> Tuple[str, str]:
        """
        Generate invalidation conditions.
        
        Returns:
            (structural_condition, time_condition)
        """
        time_inv = TIME_INVALIDATION.get(entry_style, "3 trading days")
        
        if direction == "LONG":
            if support_levels:
                key_support = min(support_levels)
                condition = (
                    f"Close below {stop_loss:.2f} invalidates setup. "
                    f"Major structure break below {key_support:.2f} invalidates thesis."
                )
            else:
                condition = f"Close below {stop_loss:.2f} invalidates setup."
        else:
            if resistance_levels:
                key_resistance = max(resistance_levels)
                condition = (
                    f"Close above {stop_loss:.2f} invalidates setup. "
                    f"Major structure break above {key_resistance:.2f} invalidates thesis."
                )
            else:
                condition = f"Close above {stop_loss:.2f} invalidates setup."
        
        return condition, time_inv
    
    # ─────────────────────────────────────────────
    # DISPLAY
    # ─────────────────────────────────────────────
    
    def format_setup(self, setup: TradeSetupPlan) -> str:
        """
        Format a trade setup plan for console/chat display.
        
        Returns:
            Multi-line formatted string
        """
        if not setup:
            return ""
        
        lines = [
            "",
            "╔" + "═" * 68 + "╗",
            "║" + "  TRADE SETUP PLAN".center(68) + "║",
            "╚" + "═" * 68 + "╝",
            "",
            f"  Symbol:     {setup.symbol}",
            f"  Direction:  {setup.direction}",
            f"  Verdict:    {setup.verdict} ({setup.confidence})",
            f"  Scenario:   {setup.active_scenario} (P={setup.scenario_probability:.0%})",
            f"  Alignment:  {setup.alignment_state}",
            "",
            "  ─── ENTRY ───────────────────────────────────────────",
            f"  Entry Price:  {setup.entry_price:.2f}",
            f"  Entry Zone:   {setup.entry_zone_low:.2f} — {setup.entry_zone_high:.2f}",
            f"  Style:        {setup.entry_style}",
            f"  Rationale:    {setup.entry_rationale}",
            "",
            "  ─── RISK ────────────────────────────────────────────",
            f"  Stop Loss:    {setup.stop_loss:.2f}",
            f"  Stop Reason:  {setup.stop_loss_reason}",
            f"  Risk/Share:   ₹{setup.risk_per_share:.2f}",
            "",
            "  ─── TARGETS ─────────────────────────────────────────",
            f"  Target 1:     {setup.target_1:.2f}  (R:R {setup.risk_reward_t1:.1f})  {setup.target_1_reason}",
        ]
        
        if setup.target_2:
            rr2_str = f"  (R:R {setup.risk_reward_t2:.1f})" if setup.risk_reward_t2 else ""
            lines.append(f"  Target 2:     {setup.target_2:.2f}{rr2_str}  {setup.target_2_reason}")
        if setup.target_3:
            lines.append(f"  Target 3:     {setup.target_3:.2f}  {setup.target_3_reason}")
        
        lines.extend([
            "",
            "  ─── POSITION ────────────────────────────────────────",
        ])
        
        if setup.risk_budget_approved:
            lines.extend([
                f"  Max Risk:     ₹{setup.max_risk_amount:.2f}",
                f"  Size:         {setup.position_size} shares",
                f"  Value:        ₹{setup.position_value:.2f}",
            ])
        else:
            lines.append(f"  ⚠ Risk Budget: {setup.risk_budget_reason}")
        
        lines.extend([
            "",
            "  ─── INVALIDATION ────────────────────────────────────",
            f"  Condition:    {setup.invalidation_condition}",
            f"  Time Limit:   {setup.time_invalidation}",
            "",
            "  ═══════════════════════════════════════════════════════",
            f"  ⚠ HUMAN CONFIRMATION REQUIRED — execution_mode = HUMAN_ONLY",
            "  ═══════════════════════════════════════════════════════",
            "",
        ])
        
        return "\n".join(lines)
    
    # ─────────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────────
    
    @staticmethod
    def _sort_levels(levels: List[float]) -> List[float]:
        """Sort and deduplicate structural levels, removing zeros/negatives."""
        seen = set()
        result = []
        for lvl in levels:
            if lvl and lvl > 0 and lvl not in seen:
                seen.add(lvl)
                result.append(lvl)
        return sorted(result)
