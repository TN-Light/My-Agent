"""
HTF Structure Renderer
=====================

PURPOSE:
-------
Draw Higher Timeframe (HTF) support and resistance zones as gray bands on charts.
This makes the structural skeleton visible to humans.

PHILOSOPHY:
----------
"The system knows where structure lives. Humans need to see it."

WHAT THIS DRAWS:
---------------
✓ HTF support zones (gray bands below price)
✓ HTF resistance zones (gray bands above price)
✓ Zone thickness based on structure strength
✓ Current price position relative to zones

WHAT THIS DOES NOT DRAW:
------------------------
✗ Trendlines (interpretation, not structure)
✗ Fibonacci levels (calculation-derived, not observable)
✗ Moving averages (lagging indicators)
✗ Pattern names ("Head and Shoulders", etc.)

CRITICAL:
--------
This is READ-ONLY visualization of EXISTING Phase-5 analysis.
It does NOT calculate new structure. It ONLY renders what was already decided.

Author: Phase-10 Implementation
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ZoneStrength(Enum):
    """Strength classification for HTF zones."""
    STRONG = "STRONG"      # Multiple touches, clean bounces
    MODERATE = "MODERATE"  # Some touches, mostly respected
    WEAK = "WEAK"          # Few touches, occasionally violated


@dataclass
class HTFZone:
    """Represents a Higher Timeframe support or resistance zone."""
    zone_type: str  # "SUPPORT" or "RESISTANCE"
    upper_bound: float
    lower_bound: float
    strength: ZoneStrength
    touches: int  # Number of times price tested this zone
    last_test_time: Optional[str] = None
    
    def __post_init__(self):
        """Validation."""
        if self.zone_type not in ["SUPPORT", "RESISTANCE"]:
            raise ValueError(f"Invalid zone_type: {self.zone_type}. Must be SUPPORT or RESISTANCE.")
        if self.upper_bound <= self.lower_bound:
            raise ValueError(f"Upper bound ({self.upper_bound}) must be > lower bound ({self.lower_bound}).")
        if self.touches < 0:
            raise ValueError(f"Touches cannot be negative: {self.touches}")
    
    @property
    def center(self) -> float:
        """Center price of the zone."""
        return (self.upper_bound + self.lower_bound) / 2
    
    @property
    def thickness(self) -> float:
        """Zone thickness in price units."""
        return self.upper_bound - self.lower_bound
    
    def contains(self, price: float) -> bool:
        """Check if price is within this zone."""
        return self.lower_bound <= price <= self.upper_bound
    
    def distance_to(self, price: float) -> float:
        """Calculate distance from price to zone (negative if inside)."""
        if price > self.upper_bound:
            return price - self.upper_bound
        elif price < self.lower_bound:
            return self.lower_bound - price
        else:
            return 0.0  # Inside zone


@dataclass
class HTFStructureVisualization:
    """Complete HTF structure visualization data."""
    support_zones: List[HTFZone]
    resistance_zones: List[HTFZone]
    current_price: float
    htf_direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    
    def __post_init__(self):
        """Validation."""
        if self.htf_direction not in ["BULLISH", "BEARISH", "NEUTRAL"]:
            raise ValueError(f"Invalid htf_direction: {self.htf_direction}")
        if self.current_price <= 0:
            raise ValueError(f"Current price must be positive: {self.current_price}")


class HTFStructureRenderer:
    """
    Renders Higher Timeframe structure zones on charts.
    
    This is a DUMB renderer. It does NOT analyze. It ONLY draws.
    All analysis must be complete BEFORE calling this.
    """
    
    # Color scheme (grayscale - neutral, non-emotional)
    SUPPORT_COLOR = "#808080"      # Gray
    RESISTANCE_COLOR = "#808080"   # Gray (same as support - structure is structure)
    SUPPORT_OPACITY = 0.15         # Translucent
    RESISTANCE_OPACITY = 0.15      # Translucent
    
    # Opacity varies by strength
    OPACITY_STRONG = 0.25
    OPACITY_MODERATE = 0.15
    OPACITY_WEAK = 0.10
    
    def __init__(self):
        """Initialize renderer."""
        pass
    
    def render(
        self,
        support_zones: List[HTFZone],
        resistance_zones: List[HTFZone],
        current_price: float,
        htf_direction: str
    ) -> HTFStructureVisualization:
        """
        Create HTF structure visualization data.
        
        This method VALIDATES and PACKAGES the structure data.
        It does NOT calculate new zones.
        
        Args:
            support_zones: List of HTF support zones
            resistance_zones: List of HTF resistance zones
            current_price: Current market price
            htf_direction: HTF trend direction
        
        Returns:
            HTFStructureVisualization object ready for chart overlay
        
        Raises:
            ValueError: If data validation fails
        """
        # Validation (structure must make sense)
        if current_price <= 0:
            raise ValueError(f"Current price must be positive: {current_price}")
        
        # Sort zones by distance from current price (closest first)
        support_zones_sorted = sorted(
            support_zones,
            key=lambda z: abs(z.center - current_price)
        )
        resistance_zones_sorted = sorted(
            resistance_zones,
            key=lambda z: abs(z.center - current_price)
        )
        
        return HTFStructureVisualization(
            support_zones=support_zones_sorted,
            resistance_zones=resistance_zones_sorted,
            current_price=current_price,
            htf_direction=htf_direction
        )
    
    def get_zone_opacity(self, zone: HTFZone) -> float:
        """
        Calculate opacity based on zone strength.
        Stronger zones are more visible.
        """
        if zone.strength == ZoneStrength.STRONG:
            return self.OPACITY_STRONG
        elif zone.strength == ZoneStrength.MODERATE:
            return self.OPACITY_MODERATE
        else:
            return self.OPACITY_WEAK
    
    def get_closest_support(self, zones: List[HTFZone], price: float) -> Optional[HTFZone]:
        """Find closest support zone below current price."""
        supports_below = [z for z in zones if z.upper_bound < price]
        if not supports_below:
            return None
        return min(supports_below, key=lambda z: price - z.upper_bound)
    
    def get_closest_resistance(self, zones: List[HTFZone], price: float) -> Optional[HTFZone]:
        """Find closest resistance zone above current price."""
        resistances_above = [z for z in zones if z.lower_bound > price]
        if not resistances_above:
            return None
        return min(resistances_above, key=lambda z: z.lower_bound - price)
    
    def get_current_zone(self, zones: List[HTFZone], price: float) -> Optional[HTFZone]:
        """Check if price is currently inside any zone."""
        for zone in zones:
            if zone.contains(price):
                return zone
        return None
    
    def to_chart_data(self, viz: HTFStructureVisualization) -> Dict:
        """
        Convert visualization object to chart overlay data structure.
        
        This returns a dictionary suitable for passing to TradingView/Playwright.
        Format matches what the chart library expects.
        """
        support_data = []
        for zone in viz.support_zones:
            support_data.append({
                "type": "box",
                "y1": zone.upper_bound,
                "y2": zone.lower_bound,
                "color": self.SUPPORT_COLOR,
                "opacity": self.get_zone_opacity(zone),
                "label": f"S ({zone.touches} touches)",
                "strength": zone.strength.value
            })
        
        resistance_data = []
        for zone in viz.resistance_zones:
            resistance_data.append({
                "type": "box",
                "y1": zone.upper_bound,
                "y2": zone.lower_bound,
                "color": self.RESISTANCE_COLOR,
                "opacity": self.get_zone_opacity(zone),
                "label": f"R ({zone.touches} touches)",
                "strength": zone.strength.value
            })
        
        return {
            "supports": support_data,
            "resistances": resistance_data,
            "current_price": viz.current_price,
            "htf_direction": viz.htf_direction
        }
