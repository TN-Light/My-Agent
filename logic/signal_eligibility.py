"""
Phase-11: Signal Eligibility Layer

Converts Phase-X verdicts into structured trade-eligible signals.
Still READ-ONLY - no execution, no prices, no quantities.

Purpose: Prove signals are consistent, rare, and repeatable.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SignalStatus(Enum):
    """Signal eligibility status"""
    ELIGIBLE = "ELIGIBLE"  # Valid analysis, trade edge exists
    NOT_ELIGIBLE = "NOT_ELIGIBLE"  # Valid analysis, no trade edge
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"  # Analysis skipped due to data failure (Phase-11.5G)


class SignalType(Enum):
    """Type of trading signal"""
    TREND_CONTINUATION = "TREND_CONTINUATION"
    TREND_REVERSAL = "TREND_REVERSAL"
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    RANGE_BOUND = "RANGE_BOUND"


class Direction(Enum):
    """Trade direction"""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class EntryStyle(Enum):
    """Entry execution style"""
    PULLBACK_ONLY = "PULLBACK_ONLY"  # Wait for retracement
    BREAKOUT_ONLY = "BREAKOUT_ONLY"  # Wait for structure break
    IMMEDIATE_OK = "IMMEDIATE_OK"    # Can enter at current level
    NO_ENTRY = "NO_ENTRY"            # Not eligible


class TimeframeClass(Enum):
    """Trading timeframe classification"""
    SWING = "SWING"      # Multi-day holds
    DAY = "DAY"          # Intraday only
    SCALP = "SCALP"      # Minutes to hours
    POSITION = "POSITION"  # Weeks to months


class RiskClass(Enum):
    """Risk classification for signal"""
    LOW = "LOW"          # Full alignment, strong structure
    MEDIUM = "MEDIUM"    # Caution zone, extended
    HIGH = "HIGH"        # Weak structure, avoid
    EXTREME = "EXTREME"  # Never trade


@dataclass
class SignalContract:
    """
    Structured signal contract - defines what is eligible for human execution.
    
    NO PRICES, NO QUANTITIES, NO AUTOMATION.
    Human reads this and decides if/when/how to execute.
    """
    signal_status: SignalStatus
    signal_type: Optional[SignalType]
    direction: Direction
    entry_style: EntryStyle
    timeframe: TimeframeClass
    risk_class: RiskClass
    execution_mode: str  # Always "HUMAN_ONLY"
    
    # Context (for human understanding)
    verdict: str  # From Phase-X: STRONG/CAUTION/WAIT/AVOID/NO_TRADE
    confidence: str  # From Phase-X: HIGH/MEDIUM/LOW
    summary: str  # From Phase-X: Human-readable explanation
    
    # Structural details (for repeatability)
    alignment_state: str  # FULL/PARTIAL/UNSTABLE/CONFLICT
    htf_location: str  # SUPPORT/MID/RESISTANCE
    trend_state: str  # UP/DOWN/RANGE
    active_scenario: str  # SCENARIO_A/B/C
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/display"""
        return {
            "signal_status": self.signal_status.value,
            "signal_type": self.signal_type.value if self.signal_type else None,
            "direction": self.direction.value,
            "entry_style": self.entry_style.value,
            "timeframe": self.timeframe.value,
            "risk_class": self.risk_class.value,
            "execution_mode": self.execution_mode,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "alignment_state": self.alignment_state,
            "htf_location": self.htf_location,
            "trend_state": self.trend_state,
            "active_scenario": self.active_scenario,
        }


class SignalEligibilityEngine:
    """
    Phase-11: Convert Phase-X verdicts into structured signals.
    
    Design Principles:
    1. Read-only - no execution, no prices, no quantities
    2. Rare signals - most verdicts are NOT_ELIGIBLE
    3. Structure-based - same structure = same signal
    4. Consistent - deterministic logic
    5. Human-first - signals guide human decisions
    """
    
    def __init__(self):
        """Initialize Signal Eligibility Engine"""
        logger.info("SignalEligibilityEngine initialized (Phase-11)")
    
    def evaluate_signal(
        self,
        verdict: str,
        confidence: str,
        summary: str,
        alignment_state: str,
        htf_location: str,
        trend_state: str,
        active_scenario: str,
        execution_gate_status: str
    ) -> SignalContract:
        """
        Convert Phase-X verdict into structured signal.
        
        Args:
            verdict: STRONG / CAUTION / WAIT / AVOID / NO_TRADE
            confidence: HIGH / MEDIUM / LOW
            summary: Human-readable explanation from Phase-X
            alignment_state: FULL / PARTIAL / UNSTABLE / CONFLICT
            htf_location: SUPPORT / MID / RESISTANCE
            trend_state: UP / DOWN / RANGE
            active_scenario: SCENARIO_A / SCENARIO_B / SCENARIO_C
            execution_gate_status: PASS / BLOCKED
        
        Returns:
            SignalContract with eligibility and execution details
        """
        
        # Default: NOT ELIGIBLE (most cases)
        signal_status = SignalStatus.NOT_ELIGIBLE
        signal_type = None
        direction = Direction.NEUTRAL
        entry_style = EntryStyle.NO_ENTRY
        timeframe = TimeframeClass.SWING  # Default assumption
        risk_class = RiskClass.HIGH  # Default conservative
        
        # Determine trend direction for signal
        if trend_state == "UP":
            direction = Direction.LONG
        elif trend_state == "DOWN":
            direction = Direction.SHORT
        else:
            direction = Direction.NEUTRAL
        
        # RULE 1: Only STRONG or CAUTION verdicts can be eligible
        if verdict not in ["STRONG", "CAUTION"]:
            risk_class = self._map_verdict_to_risk(verdict)
            return SignalContract(
                signal_status=SignalStatus.NOT_ELIGIBLE,
                signal_type=None,
                direction=direction,
                entry_style=EntryStyle.NO_ENTRY,
                timeframe=timeframe,
                risk_class=risk_class,
                execution_mode="HUMAN_ONLY",
                verdict=verdict,
                confidence=confidence,
                summary=summary,
                alignment_state=alignment_state,
                htf_location=htf_location,
                trend_state=trend_state,
                active_scenario=active_scenario,
            )
        
        # RULE 2: Execution gate must pass
        if execution_gate_status == "BLOCKED":
            return SignalContract(
                signal_status=SignalStatus.NOT_ELIGIBLE,
                signal_type=None,
                direction=direction,
                entry_style=EntryStyle.NO_ENTRY,
                timeframe=timeframe,
                risk_class=RiskClass.EXTREME,
                execution_mode="HUMAN_ONLY",
                verdict=verdict,
                confidence=confidence,
                summary=summary,
                alignment_state=alignment_state,
                htf_location=htf_location,
                trend_state=trend_state,
                active_scenario=active_scenario,
            )
        
        # RULE 3: STRONG verdict with FULL alignment = ELIGIBLE
        if verdict == "STRONG" and alignment_state == "FULL":
            signal_status = SignalStatus.ELIGIBLE
            risk_class = RiskClass.LOW
            
            # Determine signal type based on scenario and location
            if active_scenario == "SCENARIO_A":
                if htf_location == "SUPPORT":
                    signal_type = SignalType.TREND_CONTINUATION
                    entry_style = EntryStyle.PULLBACK_ONLY
                elif htf_location == "MID":
                    signal_type = SignalType.TREND_CONTINUATION
                    entry_style = EntryStyle.IMMEDIATE_OK
                else:  # RESISTANCE
                    # This shouldn't happen with STRONG, but safety check
                    signal_status = SignalStatus.NOT_ELIGIBLE
                    entry_style = EntryStyle.NO_ENTRY
                    risk_class = RiskClass.MEDIUM
        
        # RULE 4: CAUTION verdict = ELIGIBLE but with restrictions
        elif verdict == "CAUTION" and alignment_state == "FULL":
            signal_status = SignalStatus.ELIGIBLE
            risk_class = RiskClass.MEDIUM
            signal_type = SignalType.TREND_CONTINUATION
            
            if htf_location == "RESISTANCE":
                # Extended near resistance - wait for pullback only
                entry_style = EntryStyle.PULLBACK_ONLY
            else:
                # Should be safer area, but still caution
                entry_style = EntryStyle.PULLBACK_ONLY
        
        return SignalContract(
            signal_status=signal_status,
            signal_type=signal_type,
            direction=direction,
            entry_style=entry_style,
            timeframe=timeframe,
            risk_class=risk_class,
            execution_mode="HUMAN_ONLY",
            verdict=verdict,
            confidence=confidence,
            summary=summary,
            alignment_state=alignment_state,
            htf_location=htf_location,
            trend_state=trend_state,
            active_scenario=active_scenario,
        )
    
    def _map_verdict_to_risk(self, verdict: str) -> RiskClass:
        """Map Phase-X verdict to risk class"""
        if verdict == "STRONG":
            return RiskClass.LOW
        elif verdict == "CAUTION":
            return RiskClass.MEDIUM
        elif verdict == "WAIT":
            return RiskClass.HIGH
        elif verdict in ["AVOID", "NO_TRADE"]:
            return RiskClass.EXTREME
        else:
            return RiskClass.HIGH
    
    def format_signal(self, signal: SignalContract) -> str:
        """
        Format signal for display.
        
        Args:
            signal: SignalContract to format
        
        Returns:
            Formatted string for console/UI display
        """
        lines = []
        lines.append("=" * 70)
        lines.append("PHASE-11: SIGNAL ELIGIBILITY")
        lines.append("=" * 70)
        
        # Main signal status
        status_emoji = "✅" if signal.signal_status == SignalStatus.ELIGIBLE else "❌"
        lines.append(f"{status_emoji} SIGNAL_STATUS: {signal.signal_status.value}")
        
        if signal.signal_status == SignalStatus.ELIGIBLE:
            lines.append(f"   SIGNAL_TYPE: {signal.signal_type.value}")
            lines.append(f"   DIRECTION: {signal.direction.value}")
            lines.append(f"   ENTRY_STYLE: {signal.entry_style.value}")
            lines.append(f"   TIMEFRAME: {signal.timeframe.value}")
            lines.append(f"   RISK_CLASS: {signal.risk_class.value}")
            lines.append(f"   EXECUTION: {signal.execution_mode}")
        else:
            lines.append(f"   REASON: {signal.verdict} verdict - {signal.summary[:100]}")
            lines.append(f"   DIRECTION: {signal.direction.value}")
            lines.append(f"   RISK_CLASS: {signal.risk_class.value}")
        
        lines.append("")
        lines.append("STRUCTURAL CONTEXT:")
        lines.append(f"   Verdict: {signal.verdict} ({signal.confidence} confidence)")
        lines.append(f"   Alignment: {signal.alignment_state}")
        lines.append(f"   HTF Location: {signal.htf_location}")
        lines.append(f"   Trend: {signal.trend_state}")
        lines.append(f"   Scenario: {signal.active_scenario}")
        
        lines.append("")
        lines.append("HUMAN SUMMARY:")
        lines.append(f"   {signal.summary}")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
