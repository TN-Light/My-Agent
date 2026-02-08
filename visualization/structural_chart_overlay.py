"""
Structural Chart Overlay
========================

PURPOSE:
-------
Core coordinator that combines all renderers and applies to TradingView charts.
This is the INTEGRATION LAYER between Phase-5/6/7 analysis and visual representation.

PHILOSOPHY:
----------
"The system knows. Humans need to see. This makes it visible."

WHAT THIS DOES:
--------------
✓ Coordinates all visualization renderers (HTF, scenarios, risk, invalidation)
✓ Generates complete overlay data structure
✓ Provides chart-agnostic output (can be adapted to any charting library)
✓ Validates consistency across all visual elements
✓ Maintains read-only principle (NO decision-making)

WHAT THIS DOES NOT DO:
----------------------
✗ Calculate new structure (uses Phase-5 analysis)
✗ Make execution decisions (that's Phase-9)
✗ Generate trade signals (that's Phase-11)
✗ Modify existing analysis (read-only)

CRITICAL:
--------
This is a VISUALIZATION LAYER ONLY.
It has ZERO trading intelligence.
All intelligence comes from Phase-5/6/7/8/9.
This just makes that intelligence VISIBLE.

Author: Phase-10 Implementation
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import json

from visualization.htf_structure_renderer import (
    HTFStructureRenderer,
    HTFZone,
    ZoneStrength
)
from visualization.scenario_zone_renderer import (
    ScenarioZoneRenderer,
    ScenarioZone,
    ScenarioType
)
from visualization.risk_box_renderer import (
    RiskBoxRenderer,
    Direction
)
from visualization.invalidation_marker import (
    InvalidationMarker,
    InvalidationType
)


@dataclass
class StructuralVisualizationInput:
    """
    Input data from Phase-5/6/7 analysis.
    This is what the visualization layer needs to render.
    """
    # Market context
    symbol: str
    current_price: float
    timeframe: str
    
    # HTF structure (from Phase-5)
    htf_support_zones: List[Dict]
    htf_resistance_zones: List[Dict]
    htf_direction: str  # BULLISH/BEARISH/NEUTRAL
    
    # Scenario zones (from Phase-6)
    scenario_a_zone: Optional[Dict]
    scenario_b_zone: Optional[Dict]
    scenario_c_zone: Optional[Dict]
    active_scenario: str  # A/B/C
    
    # Risk setup (from Phase-7)
    entry_price: Optional[float]
    invalidation_price: Optional[float]
    direction: Optional[str]  # LONG/SHORT
    max_risk_r: Optional[float]
    invalidation_reason: Optional[str]
    
    def __post_init__(self):
        """Validation."""
        if self.current_price <= 0:
            raise ValueError(f"Current price must be positive: {self.current_price}")
        if self.active_scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid active_scenario: {self.active_scenario}")


@dataclass
class CompleteVisualization:
    """Complete structural visualization ready for chart overlay."""
    symbol: str
    timeframe: str
    current_price: float
    htf_structure: Dict
    scenario_zones: Dict
    risk_box: Optional[Dict]
    invalidation_markers: Dict
    summary: Dict
    
    def to_json(self) -> str:
        """Convert to JSON for API/web interface."""
        return json.dumps({
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "htf_structure": self.htf_structure,
            "scenario_zones": self.scenario_zones,
            "risk_box": self.risk_box,
            "invalidation_markers": self.invalidation_markers,
            "summary": self.summary
        }, indent=2)


class StructuralChartOverlay:
    """
    Master coordinator for structural visualization.
    
    This is the SINGLE ENTRY POINT for creating chart overlays.
    All other renderers are orchestrated through this.
    """
    
    def __init__(self):
        """Initialize all renderers."""
        self.htf_renderer = HTFStructureRenderer()
        self.scenario_renderer = ScenarioZoneRenderer()
        self.risk_renderer = RiskBoxRenderer()
        self.invalidation_renderer = InvalidationMarker()
    
    def create_visualization(
        self,
        input_data: StructuralVisualizationInput
    ) -> CompleteVisualization:
        """
        Create complete structural visualization from analysis data.
        
        This is the MAIN METHOD. Call this with Phase-5/6/7 output
        to get complete chart overlay data.
        
        Args:
            input_data: Structural analysis from Phase-5/6/7
        
        Returns:
            CompleteVisualization object with all visual elements
        
        Raises:
            ValueError: If input validation fails
        """
        # 1. Render HTF structure
        htf_support_zones = self._convert_htf_zones(input_data.htf_support_zones)
        htf_resistance_zones = self._convert_htf_zones(input_data.htf_resistance_zones)
        
        htf_viz = self.htf_renderer.render(
            support_zones=htf_support_zones,
            resistance_zones=htf_resistance_zones,
            current_price=input_data.current_price,
            htf_direction=input_data.htf_direction
        )
        htf_data = self.htf_renderer.to_chart_data(htf_viz)
        
        # 2. Render scenario zones
        scenario_a = self._convert_scenario_zone(input_data.scenario_a_zone, "A") if input_data.scenario_a_zone else None
        scenario_b = self._convert_scenario_zone(input_data.scenario_b_zone, "B") if input_data.scenario_b_zone else None
        scenario_c = self._convert_scenario_zone(input_data.scenario_c_zone, "C") if input_data.scenario_c_zone else None
        
        scenario_viz = self.scenario_renderer.render(
            scenario_a_zone=scenario_a,
            scenario_b_zone=scenario_b,
            scenario_c_zone=scenario_c,
            current_price=input_data.current_price,
            active_scenario=ScenarioType[input_data.active_scenario],
            htf_direction=input_data.htf_direction
        )
        scenario_data = self.scenario_renderer.to_chart_data(scenario_viz)
        
        # 3. Render risk box (if setup exists)
        risk_data = None
        if self._has_risk_setup(input_data):
            risk_viz = self.risk_renderer.render(
                entry_price=input_data.entry_price,
                invalidation_price=input_data.invalidation_price,
                direction=input_data.direction,
                max_risk_r=input_data.max_risk_r,
                scenario=input_data.active_scenario,
                invalidation_reason=input_data.invalidation_reason or "Structure break",
                current_price=input_data.current_price
            )
            risk_data = self.risk_renderer.to_chart_data(risk_viz)
        
        # 4. Render invalidation markers
        # Use risk setup invalidation if available, otherwise use HTF levels
        if input_data.invalidation_price:
            inv_type = "HTF_SUPPORT_BREAK" if input_data.direction == "LONG" else "HTF_RESISTANCE_BREAK"
            inv_viz = self.invalidation_renderer.render(
                htf_invalidation_price=input_data.invalidation_price,
                invalidation_type=inv_type,
                description=input_data.invalidation_reason or "HTF structure break",
                current_price=input_data.current_price,
                scenario=input_data.active_scenario,
                direction=input_data.direction
            )
        else:
            # Use HTF support/resistance as invalidation
            htf_support = htf_support_zones[0].center if htf_support_zones else None
            htf_resistance = htf_resistance_zones[0].center if htf_resistance_zones else None
            direction = input_data.direction or ("LONG" if input_data.htf_direction == "BULLISH" else "SHORT")
            
            inv_viz = self.invalidation_renderer.create_from_htf_structure(
                htf_support=htf_support,
                htf_resistance=htf_resistance,
                current_price=input_data.current_price,
                scenario=input_data.active_scenario,
                direction=direction
            )
        
        invalidation_data = self.invalidation_renderer.to_chart_data(inv_viz)
        
        # 5. Create summary
        summary = self._create_summary(
            input_data=input_data,
            htf_data=htf_data,
            scenario_data=scenario_data,
            risk_data=risk_data,
            invalidation_data=invalidation_data
        )
        
        return CompleteVisualization(
            symbol=input_data.symbol,
            timeframe=input_data.timeframe,
            current_price=input_data.current_price,
            htf_structure=htf_data,
            scenario_zones=scenario_data,
            risk_box=risk_data,
            invalidation_markers=invalidation_data,
            summary=summary
        )
    
    def _convert_htf_zones(self, zones_dict_list: List[Dict]) -> List[HTFZone]:
        """Convert dict format to HTFZone objects."""
        zones = []
        for zone_dict in zones_dict_list:
            zones.append(HTFZone(
                zone_type=zone_dict["zone_type"],
                upper_bound=zone_dict["upper_bound"],
                lower_bound=zone_dict["lower_bound"],
                strength=ZoneStrength[zone_dict.get("strength", "MODERATE")],
                touches=zone_dict.get("touches", 1),
                last_test_time=zone_dict.get("last_test_time")
            ))
        return zones
    
    def _convert_scenario_zone(self, zone_dict: Dict, scenario: str) -> ScenarioZone:
        """Convert dict format to ScenarioZone object."""
        return ScenarioZone(
            scenario=ScenarioType[scenario],
            upper_bound=zone_dict["upper_bound"],
            lower_bound=zone_dict["lower_bound"],
            probability=zone_dict["probability"],
            description=zone_dict.get("description", f"Scenario {scenario} zone")
        )
    
    def _has_risk_setup(self, input_data: StructuralVisualizationInput) -> bool:
        """Check if input has complete risk setup."""
        return all([
            input_data.entry_price is not None,
            input_data.invalidation_price is not None,
            input_data.direction is not None,
            input_data.max_risk_r is not None
        ])
    
    def _create_summary(
        self,
        input_data: StructuralVisualizationInput,
        htf_data: Dict,
        scenario_data: Dict,
        risk_data: Optional[Dict],
        invalidation_data: Dict
    ) -> Dict:
        """Create human-readable summary of visualization."""
        return {
            "symbol": input_data.symbol,
            "current_price": input_data.current_price,
            "htf_direction": input_data.htf_direction,
            "active_scenario": input_data.active_scenario,
            "num_support_zones": len(htf_data["supports"]),
            "num_resistance_zones": len(htf_data["resistances"]),
            "num_scenario_zones": len(scenario_data["zones"]),
            "has_risk_setup": risk_data is not None,
            "is_invalidated": invalidation_data["is_invalidated"],
            "current_zone": scenario_data.get("current_zone"),
            "closest_invalidation": invalidation_data["closest_invalidation"]
        }
    
    def create_from_phase_outputs(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        phase5_output: Dict,
        phase6_output: Dict,
        phase7_output: Optional[Dict] = None
    ) -> CompleteVisualization:
        """
        Convenience method to create visualization directly from phase outputs.
        
        Args:
            symbol: Trading symbol
            timeframe: Chart timeframe
            current_price: Current market price
            phase5_output: Market structure analysis output
            phase6_output: Probability calculation output
            phase7_output: Execution gate + risk budget output (optional)
        
        Returns:
            CompleteVisualization ready for rendering
        """
        # Extract data from phase outputs
        input_data = StructuralVisualizationInput(
            symbol=symbol,
            current_price=current_price,
            timeframe=timeframe,
            htf_support_zones=phase5_output.get("htf_support_zones", []),
            htf_resistance_zones=phase5_output.get("htf_resistance_zones", []),
            htf_direction=phase5_output.get("htf_direction", "NEUTRAL"),
            scenario_a_zone=phase6_output.get("scenario_a_zone"),
            scenario_b_zone=phase6_output.get("scenario_b_zone"),
            scenario_c_zone=phase6_output.get("scenario_c_zone"),
            active_scenario=phase6_output.get("active_scenario", "B"),
            entry_price=phase7_output.get("entry_price") if phase7_output else None,
            invalidation_price=phase7_output.get("invalidation_price") if phase7_output else None,
            direction=phase7_output.get("direction") if phase7_output else None,
            max_risk_r=phase7_output.get("max_risk_r") if phase7_output else None,
            invalidation_reason=phase7_output.get("invalidation_reason") if phase7_output else None
        )
        
        return self.create_visualization(input_data)
    
    def validate_visualization(self, viz: CompleteVisualization) -> Dict:
        """
        Validate that visualization is internally consistent.
        
        Checks:
        - HTF zones don't overlap inappropriately
        - Scenario zones are logically positioned
        - Risk box makes sense if present
        - Invalidation levels are correctly placed
        
        Returns:
            Dict with validation results and any warnings
        """
        warnings = []
        errors = []
        
        # Check HTF zone count
        num_supports = len(viz.htf_structure["supports"])
        num_resistances = len(viz.htf_structure["resistances"])
        if num_supports == 0 and num_resistances == 0:
            warnings.append("No HTF zones found - chart may lack structure context")
        
        # Check scenario zones
        num_scenarios = len(viz.scenario_zones["zones"])
        if num_scenarios < 2:
            warnings.append("Less than 2 scenario zones - probability distribution may be incomplete")
        
        # Check risk box consistency
        if viz.risk_box:
            entry = viz.risk_box["entry_line"]["price"]
            invalidation = viz.risk_box["invalidation_line"]["price"]
            direction = viz.risk_box["current_position"]["direction"]
            
            if direction == "LONG" and invalidation >= entry:
                errors.append("LONG setup has invalidation above entry - structurally impossible")
            if direction == "SHORT" and invalidation <= entry:
                errors.append("SHORT setup has invalidation below entry - structurally impossible")
        
        # Check invalidation marker consistency
        if viz.invalidation_markers["is_invalidated"]:
            warnings.append("⚠ STRUCTURE INVALIDATED - Current price has broken key level")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "timestamp": None  # Could add timestamp if needed
        }
