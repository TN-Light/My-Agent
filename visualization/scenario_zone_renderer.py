"""
Scenario Zone Renderer
=====================

PURPOSE:
-------
Draw Scenario A/B/C regions on charts with color-coding.
This shows which structural outcome is expected in each price zone.

PHILOSOPHY:
----------
"Structure creates probability zones. Humans need to see the boundaries."

WHAT THIS DRAWS:
---------------
✓ Scenario A zone (continuation) - Green tint
✓ Scenario B zone (reversion) - Yellow/amber tint
✓ Scenario C zone (breakdown) - Red tint
✓ Active scenario highlight (stronger color)
✓ Probability labels per zone

WHAT THIS DOES NOT DRAW:
------------------------
✗ Future price predictions (we show zones, not targets)
✗ Entry signals (that's Phase-11, not Phase-10)
✗ Profit targets (money comes after structure)
✗ Win rate percentages (that's for reports, not charts)

CRITICAL:
--------
Colors are NEUTRAL structure indicators, NOT emotional buy/sell signals.
Green ≠ "BUY". It means "continuation structure zone".
Red ≠ "SELL". It means "breakdown structure zone".

Author: Phase-10 Implementation
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ScenarioType(Enum):
    """The three structural scenarios."""
    A = "A"  # Continuation (HTF holds, LTF extends)
    B = "B"  # Reversion (Price reverses before HTF break)
    C = "C"  # Breakdown (HTF structure violated)


@dataclass
class ScenarioZone:
    """Represents a price zone where a specific scenario is expected."""
    scenario: ScenarioType
    upper_bound: float
    lower_bound: float
    probability: float  # 0.0 to 1.0
    description: str
    is_active: bool = False  # Is this the currently expected scenario?
    
    def __post_init__(self):
        """Validation."""
        if self.upper_bound <= self.lower_bound:
            raise ValueError(f"Upper bound ({self.upper_bound}) must be > lower bound ({self.lower_bound}).")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"Probability must be 0.0-1.0: {self.probability}")
    
    @property
    def center(self) -> float:
        """Center price of the zone."""
        return (self.upper_bound + self.lower_bound) / 2
    
    @property
    def height(self) -> float:
        """Zone height in price units."""
        return self.upper_bound - self.lower_bound
    
    def contains(self, price: float) -> bool:
        """Check if price is within this zone."""
        return self.lower_bound <= price <= self.upper_bound


@dataclass
class ScenarioZoneVisualization:
    """Complete scenario zone visualization data."""
    zones: List[ScenarioZone]
    current_price: float
    active_scenario: ScenarioType
    htf_direction: str  # Context for zone interpretation
    
    def __post_init__(self):
        """Validation."""
        if self.current_price <= 0:
            raise ValueError(f"Current price must be positive: {self.current_price}")
        if not self.zones:
            raise ValueError("Must have at least one scenario zone")
        
        # Verify active scenario matches one of the zones
        active_found = False
        for zone in self.zones:
            if zone.is_active and zone.scenario == self.active_scenario:
                active_found = True
                break
        if not active_found:
            raise ValueError(f"Active scenario {self.active_scenario} not found in zones")


class ScenarioZoneRenderer:
    """
    Renders Scenario A/B/C zones on charts.
    
    This is a VISUALIZATION renderer. It does NOT predict outcomes.
    It ONLY shows where each structural scenario applies.
    """
    
    # Color scheme (neutral structure indicators, NOT emotional signals)
    # Using subtle tints, not bright colors
    SCENARIO_A_COLOR = "#90EE90"  # Light green - continuation zone
    SCENARIO_B_COLOR = "#FFE4B5"  # Light amber - reversion zone
    SCENARIO_C_COLOR = "#FFB6C1"  # Light red - breakdown zone
    
    # Opacity settings
    INACTIVE_OPACITY = 0.10  # Very subtle for inactive zones
    ACTIVE_OPACITY = 0.20    # Slightly stronger for active scenario
    
    def __init__(self):
        """Initialize renderer."""
        pass
    
    def render(
        self,
        scenario_a_zone: Optional[ScenarioZone],
        scenario_b_zone: Optional[ScenarioZone],
        scenario_c_zone: Optional[ScenarioZone],
        current_price: float,
        active_scenario: ScenarioType,
        htf_direction: str
    ) -> ScenarioZoneVisualization:
        """
        Create scenario zone visualization data.
        
        Args:
            scenario_a_zone: Continuation zone (if applicable)
            scenario_b_zone: Reversion zone (if applicable)
            scenario_c_zone: Breakdown zone (if applicable)
            current_price: Current market price
            active_scenario: Which scenario is currently expected
            htf_direction: HTF trend direction for context
        
        Returns:
            ScenarioZoneVisualization object ready for chart overlay
        
        Raises:
            ValueError: If validation fails
        """
        zones = []
        
        # Add zones that exist
        if scenario_a_zone:
            scenario_a_zone.is_active = (active_scenario == ScenarioType.A)
            zones.append(scenario_a_zone)
        
        if scenario_b_zone:
            scenario_b_zone.is_active = (active_scenario == ScenarioType.B)
            zones.append(scenario_b_zone)
        
        if scenario_c_zone:
            scenario_c_zone.is_active = (active_scenario == ScenarioType.C)
            zones.append(scenario_c_zone)
        
        if not zones:
            raise ValueError("At least one scenario zone must be provided")
        
        return ScenarioZoneVisualization(
            zones=zones,
            current_price=current_price,
            active_scenario=active_scenario,
            htf_direction=htf_direction
        )
    
    def get_zone_color(self, scenario: ScenarioType) -> str:
        """Get color for scenario zone."""
        if scenario == ScenarioType.A:
            return self.SCENARIO_A_COLOR
        elif scenario == ScenarioType.B:
            return self.SCENARIO_B_COLOR
        else:  # Scenario C
            return self.SCENARIO_C_COLOR
    
    def get_zone_opacity(self, is_active: bool) -> float:
        """Get opacity based on whether zone is active."""
        return self.ACTIVE_OPACITY if is_active else self.INACTIVE_OPACITY
    
    def get_current_zone(self, viz: ScenarioZoneVisualization) -> Optional[ScenarioZone]:
        """Find which zone current price is in."""
        for zone in viz.zones:
            if zone.contains(viz.current_price):
                return zone
        return None
    
    def to_chart_data(self, viz: ScenarioZoneVisualization) -> Dict:
        """
        Convert visualization object to chart overlay data structure.
        
        Returns dictionary suitable for TradingView/Playwright overlay.
        """
        zone_data = []
        
        for zone in viz.zones:
            zone_data.append({
                "type": "box",
                "y1": zone.upper_bound,
                "y2": zone.lower_bound,
                "color": self.get_zone_color(zone.scenario),
                "opacity": self.get_zone_opacity(zone.is_active),
                "label": f"Scenario {zone.scenario.value} ({zone.probability:.0%})",
                "is_active": zone.is_active,
                "scenario": zone.scenario.value,
                "probability": zone.probability,
                "description": zone.description
            })
        
        # Find current zone for context
        current_zone = self.get_current_zone(viz)
        current_zone_info = None
        if current_zone:
            current_zone_info = {
                "scenario": current_zone.scenario.value,
                "probability": current_zone.probability,
                "description": current_zone.description
            }
        
        return {
            "zones": zone_data,
            "current_price": viz.current_price,
            "active_scenario": viz.active_scenario.value,
            "current_zone": current_zone_info,
            "htf_direction": viz.htf_direction
        }
    
    def create_zone_from_analysis(
        self,
        scenario: str,
        upper_bound: float,
        lower_bound: float,
        probability: float,
        description: str
    ) -> ScenarioZone:
        """
        Helper to create ScenarioZone from Phase-6 probability analysis output.
        
        This bridges Phase-6 (probability calculator) → Phase-10 (visualization).
        """
        scenario_type = ScenarioType[scenario]  # Convert "A" string to ScenarioType.A
        
        return ScenarioZone(
            scenario=scenario_type,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            probability=probability,
            description=description,
            is_active=False  # Will be set by render() method
        )
    
    def validate_zone_consistency(self, zones: List[ScenarioZone]) -> bool:
        """
        Validate that zones don't overlap inappropriately.
        
        Zones can share boundaries but shouldn't fully overlap.
        Returns True if valid, False otherwise.
        """
        for i, zone1 in enumerate(zones):
            for zone2 in zones[i+1:]:
                # Check for full overlap (one zone completely inside another)
                if (zone1.lower_bound <= zone2.lower_bound <= zone1.upper_bound and
                    zone1.lower_bound <= zone2.upper_bound <= zone1.upper_bound):
                    return False
                if (zone2.lower_bound <= zone1.lower_bound <= zone2.upper_bound and
                    zone2.lower_bound <= zone1.upper_bound <= zone2.upper_bound):
                    return False
        return True
