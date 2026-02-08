"""
Risk Box Renderer
================

PURPOSE:
-------
Draw R-based risk visualization on charts.
Shows entry, invalidation, and risk multiples - NOT money amounts.

PHILOSOPHY:
----------
"Risk is measured in R, not rupees. Structure defines invalidation, not fear."

WHAT THIS DRAWS:
---------------
✓ Entry level (horizontal line)
✓ Invalidation level (red horizontal line)
✓ Risk box (entry to invalidation zone)
✓ R-multiple labels (1R, 2R, 3R lines above/below entry)
✓ Current R-position indicator

WHAT THIS DOES NOT DRAW:
------------------------
✗ Profit targets (that's Phase-11, not Phase-10)
✗ INR/USD amounts (money-agnostic visualization)
✗ Win rate statistics (that's for reports)
✗ Position size suggestions (that's Phase-7B)

CRITICAL:
--------
Invalidation is STRUCTURE-BASED (HTF break), not arbitrary stop loss.
R is defined by structure, not by trader's pain tolerance.

Author: Phase-10 Implementation
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class RiskBox:
    """Represents risk visualization for a potential trade setup."""
    entry_price: float
    invalidation_price: float
    direction: Direction
    max_risk_r: float  # Maximum risk in R-multiples (from Phase-7B)
    scenario: str  # Which scenario this setup belongs to (A/B/C)
    invalidation_reason: str  # Why this level invalidates (e.g., "HTF support break")
    
    def __post_init__(self):
        """Validation."""
        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive: {self.entry_price}")
        if self.invalidation_price <= 0:
            raise ValueError(f"Invalidation price must be positive: {self.invalidation_price}")
        if self.max_risk_r <= 0:
            raise ValueError(f"Max risk R must be positive: {self.max_risk_r}")
        if self.scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid scenario: {self.scenario}")
        
        # Direction consistency check
        if self.direction == Direction.LONG and self.invalidation_price >= self.entry_price:
            raise ValueError("LONG invalidation must be below entry")
        if self.direction == Direction.SHORT and self.invalidation_price <= self.entry_price:
            raise ValueError("SHORT invalidation must be above entry")
    
    @property
    def risk_distance(self) -> float:
        """Distance from entry to invalidation (1R)."""
        return abs(self.entry_price - self.invalidation_price)
    
    @property
    def risk_percentage(self) -> float:
        """Risk as percentage of entry price."""
        return (self.risk_distance / self.entry_price) * 100
    
    def calculate_r_level(self, r_multiple: float) -> float:
        """
        Calculate price level for given R-multiple.
        
        For LONG: R levels are above entry (higher prices)
        For SHORT: R levels are below entry (lower prices)
        """
        if self.direction == Direction.LONG:
            return self.entry_price + (r_multiple * self.risk_distance)
        else:  # SHORT
            return self.entry_price - (r_multiple * self.risk_distance)
    
    def calculate_current_r(self, current_price: float) -> float:
        """
        Calculate current R-position relative to entry.
        
        Positive R = in profit direction
        Negative R = against position (toward invalidation)
        """
        if self.direction == Direction.LONG:
            return (current_price - self.entry_price) / self.risk_distance
        else:  # SHORT
            return (self.entry_price - current_price) / self.risk_distance
    
    def is_invalidated(self, current_price: float) -> bool:
        """Check if current price has hit invalidation level."""
        if self.direction == Direction.LONG:
            return current_price <= self.invalidation_price
        else:  # SHORT
            return current_price >= self.invalidation_price


@dataclass
class RiskBoxVisualization:
    """Complete risk box visualization data."""
    risk_box: RiskBox
    current_price: float
    r_levels_to_show: List[float]  # Which R-multiples to draw (e.g., [1, 2, 3])
    
    def __post_init__(self):
        """Validation."""
        if self.current_price <= 0:
            raise ValueError(f"Current price must be positive: {self.current_price}")
        if not self.r_levels_to_show:
            raise ValueError("Must specify at least one R-level to show")
        for r in self.r_levels_to_show:
            if r <= 0:
                raise ValueError(f"R-levels must be positive: {r}")


class RiskBoxRenderer:
    """
    Renders risk visualization on charts.
    
    This shows WHERE structure invalidates and HOW to measure outcomes.
    It does NOT suggest position sizes or predict outcomes.
    """
    
    # Color scheme (neutral, structural)
    ENTRY_COLOR = "#4169E1"        # Royal blue - entry reference
    INVALIDATION_COLOR = "#DC143C"  # Crimson red - structure violation
    RISK_BOX_COLOR = "#FFE4B5"      # Light amber - risk zone
    R_LEVEL_COLOR = "#696969"       # Dim gray - measurement lines
    
    # Opacity settings
    RISK_BOX_OPACITY = 0.15
    LINE_OPACITY = 0.80
    R_LINE_OPACITY = 0.40
    
    # Default R-levels to show
    DEFAULT_R_LEVELS = [1.0, 2.0, 3.0]
    
    def __init__(self):
        """Initialize renderer."""
        pass
    
    def render(
        self,
        entry_price: float,
        invalidation_price: float,
        direction: str,
        max_risk_r: float,
        scenario: str,
        invalidation_reason: str,
        current_price: float,
        r_levels: Optional[List[float]] = None
    ) -> RiskBoxVisualization:
        """
        Create risk box visualization data.
        
        Args:
            entry_price: Proposed entry level
            invalidation_price: Structure-based invalidation level
            direction: Trade direction ("LONG" or "SHORT")
            max_risk_r: Maximum risk from Phase-7B (e.g., 0.25)
            scenario: Which scenario this belongs to (A/B/C)
            invalidation_reason: Why this level invalidates
            current_price: Current market price
            r_levels: Which R-multiples to show (defaults to [1, 2, 3])
        
        Returns:
            RiskBoxVisualization object ready for chart overlay
        """
        direction_enum = Direction[direction]
        
        risk_box = RiskBox(
            entry_price=entry_price,
            invalidation_price=invalidation_price,
            direction=direction_enum,
            max_risk_r=max_risk_r,
            scenario=scenario,
            invalidation_reason=invalidation_reason
        )
        
        if r_levels is None:
            r_levels = self.DEFAULT_R_LEVELS
        
        return RiskBoxVisualization(
            risk_box=risk_box,
            current_price=current_price,
            r_levels_to_show=r_levels
        )
    
    def to_chart_data(self, viz: RiskBoxVisualization) -> Dict:
        """
        Convert visualization object to chart overlay data structure.
        
        Returns dictionary suitable for TradingView/Playwright overlay.
        """
        risk_box = viz.risk_box
        
        # Entry line
        entry_line = {
            "type": "horizontal_line",
            "price": risk_box.entry_price,
            "color": self.ENTRY_COLOR,
            "opacity": self.LINE_OPACITY,
            "label": f"Entry: {risk_box.entry_price:.2f}",
            "style": "solid",
            "width": 2
        }
        
        # Invalidation line
        invalidation_line = {
            "type": "horizontal_line",
            "price": risk_box.invalidation_price,
            "color": self.INVALIDATION_COLOR,
            "opacity": self.LINE_OPACITY,
            "label": f"Invalid: {risk_box.invalidation_price:.2f} ({risk_box.invalidation_reason})",
            "style": "solid",
            "width": 2
        }
        
        # Risk box (shaded area between entry and invalidation)
        risk_box_area = {
            "type": "box",
            "y1": risk_box.entry_price,
            "y2": risk_box.invalidation_price,
            "color": self.RISK_BOX_COLOR,
            "opacity": self.RISK_BOX_OPACITY,
            "label": f"1R = {risk_box.risk_distance:.2f} ({risk_box.risk_percentage:.2f}%)"
        }
        
        # R-multiple levels
        r_lines = []
        for r_multiple in viz.r_levels_to_show:
            r_price = risk_box.calculate_r_level(r_multiple)
            r_lines.append({
                "type": "horizontal_line",
                "price": r_price,
                "color": self.R_LEVEL_COLOR,
                "opacity": self.R_LINE_OPACITY,
                "label": f"{r_multiple:.1f}R",
                "style": "dashed",
                "width": 1
            })
        
        # Current R-position
        current_r = risk_box.calculate_current_r(viz.current_price)
        is_invalidated = risk_box.is_invalidated(viz.current_price)
        
        current_position = {
            "current_price": viz.current_price,
            "current_r": current_r,
            "is_invalidated": is_invalidated,
            "direction": risk_box.direction.value
        }
        
        return {
            "entry_line": entry_line,
            "invalidation_line": invalidation_line,
            "risk_box": risk_box_area,
            "r_lines": r_lines,
            "current_position": current_position,
            "scenario": risk_box.scenario,
            "max_risk_r": risk_box.max_risk_r
        }
    
    def create_from_phase7_output(
        self,
        entry_price: float,
        htf_invalidation_level: float,
        direction: str,
        risk_budget_output: Dict,
        scenario: str,
        current_price: float
    ) -> RiskBoxVisualization:
        """
        Helper to create RiskBox from Phase-7 (execution gate + risk budget) output.
        
        This bridges Phase-7 → Phase-10.
        
        Args:
            entry_price: Entry from Phase-5 analysis
            htf_invalidation_level: Structure violation level from Phase-5
            direction: LONG or SHORT
            risk_budget_output: Output from Phase-7B RiskBudgetEngine
            scenario: Active scenario (A/B/C)
            current_price: Current market price
        
        Returns:
            RiskBoxVisualization ready for rendering
        """
        return self.render(
            entry_price=entry_price,
            invalidation_price=htf_invalidation_level,
            direction=direction,
            max_risk_r=risk_budget_output.get("max_risk_this_trade", 0.25),
            scenario=scenario,
            invalidation_reason="HTF structure break",
            current_price=current_price
        )
    
    def validate_risk_structure(self, viz: RiskBoxVisualization) -> bool:
        """
        Validate that risk visualization makes structural sense.
        
        Checks:
        - Entry and invalidation are properly positioned
        - Current price is reasonable
        - R-levels are logical
        
        Returns True if valid, False otherwise.
        """
        risk_box = viz.risk_box
        
        # Check direction consistency (already done in RiskBox.__post_init__)
        # Check that current price isn't absurdly far from setup
        max_reasonable_r = 10.0  # More than 10R away is likely data error
        current_r = abs(risk_box.calculate_current_r(viz.current_price))
        if current_r > max_reasonable_r:
            return False
        
        return True
