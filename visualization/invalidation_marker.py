"""
Invalidation Marker
==================

PURPOSE:
-------
Draw red lines where structure breaks (HTF support/resistance violations).
This shows the exact price where the structural thesis is WRONG.

PHILOSOPHY:
----------
"Invalidation is binary. Either structure holds or it doesn't. There is no maybe."

WHAT THIS DRAWS:
---------------
✓ HTF support invalidation line (red, below price for LONG)
✓ HTF resistance invalidation line (red, above price for SHORT)
✓ Clear labels: "HTF Support Break" or "HTF Resistance Break"
✓ Distance from current price to invalidation

WHAT THIS DOES NOT DRAW:
------------------------
✗ Arbitrary stop losses (invalidation is structural, not arbitrary)
✗ Mental stops or time-based exits (those are trading tactics, not structure)
✗ Trailing stops (invalidation doesn't move with price)
✗ Multiple invalidation levels (structure breaks at ONE level)

CRITICAL:
--------
Invalidation is NOT a "stop loss suggestion".
It is the price where STRUCTURE says "you were wrong".
If price hits invalidation, the setup is DEAD, regardless of account balance.

Author: Phase-10 Implementation
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum


class InvalidationType(Enum):
    """Type of structural invalidation."""
    HTF_SUPPORT_BREAK = "HTF_SUPPORT_BREAK"
    HTF_RESISTANCE_BREAK = "HTF_RESISTANCE_BREAK"
    LTF_STRUCTURE_BREAK = "LTF_STRUCTURE_BREAK"  # For tighter setups


@dataclass
class InvalidationLevel:
    """Represents a structural invalidation level."""
    price: float
    invalidation_type: InvalidationType
    description: str
    htf_level: bool = True  # Is this HTF or LTF invalidation?
    
    def __post_init__(self):
        """Validation."""
        if self.price <= 0:
            raise ValueError(f"Invalidation price must be positive: {self.price}")
        if not self.description:
            raise ValueError("Description cannot be empty")


@dataclass
class InvalidationVisualization:
    """Complete invalidation marker visualization data."""
    invalidation_levels: List[InvalidationLevel]
    current_price: float
    scenario: str  # Which scenario these invalidations apply to
    direction: str  # LONG or SHORT (determines which side to check)
    
    def __post_init__(self):
        """Validation."""
        if self.current_price <= 0:
            raise ValueError(f"Current price must be positive: {self.current_price}")
        if not self.invalidation_levels:
            raise ValueError("Must have at least one invalidation level")
        if self.scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid scenario: {self.scenario}")
        if self.direction not in ["LONG", "SHORT"]:
            raise ValueError(f"Invalid direction: {self.direction}")


class InvalidationMarker:
    """
    Renders invalidation levels on charts.
    
    This marks the EXACT price where structure says "thesis failed".
    No ambiguity. No interpretation. Just structure.
    """
    
    # Color scheme (red for danger/violation)
    HTF_INVALIDATION_COLOR = "#DC143C"  # Crimson red - HTF structure break
    LTF_INVALIDATION_COLOR = "#FF6347"  # Tomato red - LTF structure break (lighter)
    
    # Line style
    LINE_WIDTH = 2
    LINE_STYLE = "solid"
    LINE_OPACITY = 0.90
    
    # Label settings
    LABEL_BACKGROUND = "#000000"
    LABEL_TEXT_COLOR = "#FFFFFF"
    
    def __init__(self):
        """Initialize marker."""
        pass
    
    def render(
        self,
        htf_invalidation_price: float,
        invalidation_type: str,
        description: str,
        current_price: float,
        scenario: str,
        direction: str,
        ltf_invalidation_price: Optional[float] = None
    ) -> InvalidationVisualization:
        """
        Create invalidation marker visualization data.
        
        Args:
            htf_invalidation_price: HTF structure break level
            invalidation_type: Type of invalidation (HTF_SUPPORT_BREAK or HTF_RESISTANCE_BREAK)
            description: Human-readable description
            current_price: Current market price
            scenario: Active scenario (A/B/C)
            direction: Trade direction (LONG/SHORT)
            ltf_invalidation_price: Optional LTF structure break (tighter stop)
        
        Returns:
            InvalidationVisualization object ready for chart overlay
        """
        levels = []
        
        # HTF invalidation (primary)
        inv_type = InvalidationType[invalidation_type]
        levels.append(InvalidationLevel(
            price=htf_invalidation_price,
            invalidation_type=inv_type,
            description=description,
            htf_level=True
        ))
        
        # LTF invalidation (if provided)
        if ltf_invalidation_price is not None:
            levels.append(InvalidationLevel(
                price=ltf_invalidation_price,
                invalidation_type=InvalidationType.LTF_STRUCTURE_BREAK,
                description="LTF structure break (tighter)",
                htf_level=False
            ))
        
        return InvalidationVisualization(
            invalidation_levels=levels,
            current_price=current_price,
            scenario=scenario,
            direction=direction
        )
    
    def is_invalidated(self, viz: InvalidationVisualization) -> bool:
        """
        Check if any invalidation level has been hit.
        
        Returns True if structure is broken, False otherwise.
        """
        for level in viz.invalidation_levels:
            if viz.direction == "LONG":
                # For LONG, invalidation is below entry (price falling through support)
                if viz.current_price <= level.price:
                    return True
            else:  # SHORT
                # For SHORT, invalidation is above entry (price rising through resistance)
                if viz.current_price >= level.price:
                    return True
        return False
    
    def get_closest_invalidation(self, viz: InvalidationVisualization) -> InvalidationLevel:
        """Get the invalidation level closest to current price."""
        return min(
            viz.invalidation_levels,
            key=lambda lvl: abs(viz.current_price - lvl.price)
        )
    
    def calculate_distance_to_invalidation(
        self,
        viz: InvalidationVisualization,
        level: InvalidationLevel
    ) -> Dict:
        """
        Calculate distance from current price to invalidation level.
        
        Returns:
            Dict with absolute distance, percentage distance, and points
        """
        distance = abs(viz.current_price - level.price)
        distance_pct = (distance / viz.current_price) * 100
        
        # Points away (positive if price is safe, negative if already broken)
        if viz.direction == "LONG":
            points_away = viz.current_price - level.price
        else:  # SHORT
            points_away = level.price - viz.current_price
        
        return {
            "absolute_distance": distance,
            "percentage_distance": distance_pct,
            "points_away": points_away,
            "is_safe": points_away > 0
        }
    
    def to_chart_data(self, viz: InvalidationVisualization) -> Dict:
        """
        Convert visualization object to chart overlay data structure.
        
        Returns dictionary suitable for TradingView/Playwright overlay.
        """
        lines = []
        
        for level in viz.invalidation_levels:
            # Choose color based on HTF vs LTF
            color = self.HTF_INVALIDATION_COLOR if level.htf_level else self.LTF_INVALIDATION_COLOR
            
            # Calculate distance
            distance_info = self.calculate_distance_to_invalidation(viz, level)
            
            # Label text
            label_text = f"⚠ {level.description}"
            if not distance_info["is_safe"]:
                label_text = f"❌ INVALIDATED: {level.description}"
            
            lines.append({
                "type": "horizontal_line",
                "price": level.price,
                "color": color,
                "opacity": self.LINE_OPACITY,
                "style": self.LINE_STYLE,
                "width": self.LINE_WIDTH,
                "label": label_text,
                "is_htf": level.htf_level,
                "is_broken": not distance_info["is_safe"],
                "distance": distance_info
            })
        
        # Overall invalidation status
        is_invalidated = self.is_invalidated(viz)
        closest = self.get_closest_invalidation(viz)
        
        return {
            "invalidation_lines": lines,
            "is_invalidated": is_invalidated,
            "closest_invalidation": {
                "price": closest.price,
                "type": closest.invalidation_type.value,
                "description": closest.description,
                "is_htf": closest.htf_level
            },
            "current_price": viz.current_price,
            "scenario": viz.scenario,
            "direction": viz.direction
        }
    
    def create_from_htf_structure(
        self,
        htf_support: Optional[float],
        htf_resistance: Optional[float],
        current_price: float,
        scenario: str,
        direction: str
    ) -> InvalidationVisualization:
        """
        Helper to create invalidation markers from HTF structure analysis.
        
        This bridges Phase-5 (structure analysis) → Phase-10 (visualization).
        
        Args:
            htf_support: HTF support level (if exists)
            htf_resistance: HTF resistance level (if exists)
            current_price: Current market price
            scenario: Active scenario
            direction: Trade direction
        
        Returns:
            InvalidationVisualization ready for rendering
        """
        # Determine which level is the invalidation based on direction
        if direction == "LONG":
            if htf_support is None:
                raise ValueError("LONG setup requires HTF support for invalidation")
            return self.render(
                htf_invalidation_price=htf_support,
                invalidation_type="HTF_SUPPORT_BREAK",
                description="HTF support break",
                current_price=current_price,
                scenario=scenario,
                direction=direction
            )
        else:  # SHORT
            if htf_resistance is None:
                raise ValueError("SHORT setup requires HTF resistance for invalidation")
            return self.render(
                htf_invalidation_price=htf_resistance,
                invalidation_type="HTF_RESISTANCE_BREAK",
                description="HTF resistance break",
                current_price=current_price,
                scenario=scenario,
                direction=direction
            )
    
    def validate_invalidation_structure(
        self,
        viz: InvalidationVisualization
    ) -> bool:
        """
        Validate that invalidation levels make structural sense.
        
        For LONG: Invalidation must be below current price
        For SHORT: Invalidation must be above current price
        
        Returns True if valid, False otherwise.
        """
        for level in viz.invalidation_levels:
            if viz.direction == "LONG":
                if level.price >= viz.current_price:
                    return False  # Invalidation must be below for LONG
            else:  # SHORT
                if level.price <= viz.current_price:
                    return False  # Invalidation must be above for SHORT
        return True
