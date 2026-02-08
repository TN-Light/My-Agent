"""
Phase-10 Test Suite: Structural Visualization Layer
==================================================

PURPOSE:
-------
Validate that structural visualization logic is correct.
Tests coordinate calculation, color assignment, zone rendering, and consistency.

CRITICAL:
--------
These are LOGIC tests, NOT visual tests.
We validate data structures and calculations, not rendered pixels.

Author: Phase-10 Implementation
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from visualization.structural_chart_overlay import (
    StructuralChartOverlay,
    StructuralVisualizationInput
)


class TestLogger:
    """Structured test output."""
    
    @staticmethod
    def test_header(test_id: str, description: str):
        print(f"\n{'='*70}")
        print(f"TEST {test_id}: {description}")
        print(f"{'='*70}")
    
    @staticmethod
    def log_input(label: str, value):
        print(f"  INPUT: {label} = {value}")
    
    @staticmethod
    def log_expected(label: str, value):
        print(f"  EXPECT: {label} = {value}")
    
    @staticmethod
    def log_actual(label: str, value):
        print(f"  ACTUAL: {label} = {value}")
    
    @staticmethod
    def test_result(passed: bool, message: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n  RESULT: {status}")
        if message:
            print(f"  {message}")
        print(f"{'-'*70}\n")
        return passed


def test_htf_zone_rendering():
    """
    TC-10-01: HTF Zone Coordinate Calculation
    Test that HTF support/resistance zones calculate coordinates correctly.
    """
    logger = TestLogger()
    logger.test_header("TC-10-01", "HTF Zone Coordinate Calculation")
    
    # Create test zones
    support = HTFZone(
        zone_type="SUPPORT",
        upper_bound=19500.0,
        lower_bound=19450.0,
        strength=ZoneStrength.STRONG,
        touches=5
    )
    
    resistance = HTFZone(
        zone_type="RESISTANCE",
        upper_bound=19800.0,
        lower_bound=19750.0,
        strength=ZoneStrength.MODERATE,
        touches=3
    )
    
    logger.log_input("Support zone", f"{support.lower_bound}-{support.upper_bound}")
    logger.log_input("Resistance zone", f"{resistance.lower_bound}-{resistance.upper_bound}")
    logger.log_input("Current price", 19600.0)
    
    # Test calculations
    logger.log_expected("Support center", 19475.0)
    logger.log_actual("Support center", support.center)
    assert support.center == 19475.0, "Support center incorrect"
    
    logger.log_expected("Support thickness", 50.0)
    logger.log_actual("Support thickness", support.thickness)
    assert support.thickness == 50.0, "Support thickness incorrect"
    
    logger.log_expected("Distance from 19600 to support", 100.0)
    actual_distance = support.distance_to(19600.0)
    logger.log_actual("Distance", actual_distance)
    assert actual_distance == 100.0, "Distance calculation incorrect"
    
    logger.log_expected("19475 in support zone", True)
    logger.log_actual("Contains 19475", support.contains(19475.0))
    assert support.contains(19475.0), "Contains check failed"
    
    # Render
    renderer = HTFStructureRenderer()
    viz = renderer.render(
        support_zones=[support],
        resistance_zones=[resistance],
        current_price=19600.0,
        htf_direction="BULLISH"
    )
    
    chart_data = renderer.to_chart_data(viz)
    
    logger.log_expected("1 support box, 1 resistance box", None)
    logger.log_actual("Support boxes", len(chart_data["supports"]))
    logger.log_actual("Resistance boxes", len(chart_data["resistances"]))
    
    assert len(chart_data["supports"]) == 1, "Support count incorrect"
    assert len(chart_data["resistances"]) == 1, "Resistance count incorrect"
    assert chart_data["supports"][0]["opacity"] == 0.25, "Strong support opacity incorrect"
    
    return logger.test_result(True, "HTF zone calculations validated")


def test_scenario_zone_rendering():
    """
    TC-10-02: Scenario Zone Color Assignment
    Test that scenario zones get correct colors and active highlighting.
    """
    logger = TestLogger()
    logger.test_header("TC-10-02", "Scenario Zone Color Assignment")
    
    # Create scenario zones
    zone_a = ScenarioZone(
        scenario=ScenarioType.A,
        upper_bound=19900.0,
        lower_bound=19700.0,
        probability=0.35,
        description="Continuation to 19900"
    )
    
    zone_b = ScenarioZone(
        scenario=ScenarioType.B,
        upper_bound=19700.0,
        lower_bound=19500.0,
        probability=0.54,
        description="Reversion from 19600"
    )
    
    zone_c = ScenarioZone(
        scenario=ScenarioType.C,
        upper_bound=19500.0,
        lower_bound=19300.0,
        probability=0.11,
        description="Breakdown below 19450"
    )
    
    logger.log_input("Active scenario", "B")
    logger.log_input("Current price", 19600.0)
    
    renderer = ScenarioZoneRenderer()
    viz = renderer.render(
        scenario_a_zone=zone_a,
        scenario_b_zone=zone_b,
        scenario_c_zone=zone_c,
        current_price=19600.0,
        active_scenario=ScenarioType.B,
        htf_direction="BULLISH"
    )
    
    chart_data = renderer.to_chart_data(viz)
    
    logger.log_expected("3 scenario zones", None)
    logger.log_actual("Zone count", len(chart_data["zones"]))
    assert len(chart_data["zones"]) == 3, "Zone count incorrect"
    
    # Find zones by scenario
    zones_by_scenario = {z["scenario"]: z for z in chart_data["zones"]}
    
    logger.log_expected("Scenario B is_active", True)
    logger.log_actual("Scenario B is_active", zones_by_scenario["B"]["is_active"])
    assert zones_by_scenario["B"]["is_active"], "Active scenario not marked"
    
    logger.log_expected("Scenario A is_active", False)
    logger.log_actual("Scenario A is_active", zones_by_scenario["A"]["is_active"])
    assert not zones_by_scenario["A"]["is_active"], "Inactive scenario marked active"
    
    logger.log_expected("Active opacity > Inactive opacity", None)
    active_opacity = zones_by_scenario["B"]["opacity"]
    inactive_opacity = zones_by_scenario["A"]["opacity"]
    logger.log_actual("Active opacity", active_opacity)
    logger.log_actual("Inactive opacity", inactive_opacity)
    assert active_opacity > inactive_opacity, "Active zone not more visible"
    
    # Check color assignment
    logger.log_expected("Scenario A color", "#90EE90 (light green)")
    logger.log_actual("Scenario A color", zones_by_scenario["A"]["color"])
    assert zones_by_scenario["A"]["color"] == "#90EE90", "Scenario A color incorrect"
    
    logger.log_expected("Scenario C color", "#FFB6C1 (light red)")
    logger.log_actual("Scenario C color", zones_by_scenario["C"]["color"])
    assert zones_by_scenario["C"]["color"] == "#FFB6C1", "Scenario C color incorrect"
    
    # Check current zone detection
    logger.log_expected("Current zone", "Scenario B (19600 in 19500-19700)")
    logger.log_actual("Current zone", chart_data["current_zone"]["scenario"])
    assert chart_data["current_zone"]["scenario"] == "B", "Current zone detection failed"
    
    return logger.test_result(True, "Scenario zone colors and highlighting validated")


def test_risk_box_r_calculation():
    """
    TC-10-03: Risk Box R-Multiple Calculation
    Test that R-multiples calculate correctly for LONG and SHORT.
    """
    logger = TestLogger()
    logger.test_header("TC-10-03", "Risk Box R-Multiple Calculation")
    
    # LONG setup
    logger.log_input("Direction", "LONG")
    logger.log_input("Entry", 19600.0)
    logger.log_input("Invalidation", 19450.0)
    logger.log_input("Current price", 19750.0)
    
    renderer = RiskBoxRenderer()
    viz_long = renderer.render(
        entry_price=19600.0,
        invalidation_price=19450.0,
        direction="LONG",
        max_risk_r=0.25,
        scenario="B",
        invalidation_reason="HTF support break",
        current_price=19750.0
    )
    
    risk_box = viz_long.risk_box
    
    logger.log_expected("Risk distance (1R)", 150.0)
    logger.log_actual("Risk distance", risk_box.risk_distance)
    assert risk_box.risk_distance == 150.0, "Risk distance incorrect"
    
    logger.log_expected("2R level (LONG)", "19600 + 2*150 = 19900")
    r2_level = risk_box.calculate_r_level(2.0)
    logger.log_actual("2R level", r2_level)
    assert r2_level == 19900.0, "2R calculation incorrect for LONG"
    
    logger.log_expected("Current R (19750)", "(19750-19600)/150 = 1.0R")
    current_r = risk_box.calculate_current_r(19750.0)
    logger.log_actual("Current R", f"{current_r:.2f}R")
    assert abs(current_r - 1.0) < 0.01, "Current R calculation incorrect"
    
    # SHORT setup
    logger.log_input("Direction", "SHORT")
    logger.log_input("Entry", 19600.0)
    logger.log_input("Invalidation", 19750.0)
    logger.log_input("Current price", 19450.0)
    
    viz_short = renderer.render(
        entry_price=19600.0,
        invalidation_price=19750.0,
        direction="SHORT",
        max_risk_r=0.25,
        scenario="B",
        invalidation_reason="HTF resistance break",
        current_price=19450.0
    )
    
    risk_box_short = viz_short.risk_box
    
    logger.log_expected("2R level (SHORT)", "19600 - 2*150 = 19300")
    r2_level_short = risk_box_short.calculate_r_level(2.0)
    logger.log_actual("2R level", r2_level_short)
    assert r2_level_short == 19300.0, "2R calculation incorrect for SHORT"
    
    logger.log_expected("Current R (19450)", "(19600-19450)/150 = 1.0R")
    current_r_short = risk_box_short.calculate_current_r(19450.0)
    logger.log_actual("Current R", f"{current_r_short:.2f}R")
    assert abs(current_r_short - 1.0) < 0.01, "Current R calculation incorrect for SHORT"
    
    # Test chart data generation
    chart_data = renderer.to_chart_data(viz_long)
    
    logger.log_expected("Entry line, invalidation line, risk box, R-lines", None)
    logger.log_actual("Entry line present", "entry_line" in chart_data)
    logger.log_actual("Invalidation line present", "invalidation_line" in chart_data)
    logger.log_actual("Risk box present", "risk_box" in chart_data)
    logger.log_actual("R-lines count", len(chart_data["r_lines"]))
    
    assert "entry_line" in chart_data, "Entry line missing"
    assert "invalidation_line" in chart_data, "Invalidation line missing"
    assert len(chart_data["r_lines"]) == 3, "R-lines count incorrect (should be 3: 1R, 2R, 3R)"
    
    return logger.test_result(True, "Risk box R-multiple calculations validated")


def test_invalidation_detection():
    """
    TC-10-04: Invalidation Level Detection
    Test that invalidation correctly detects structure breaks.
    """
    logger = TestLogger()
    logger.test_header("TC-10-04", "Invalidation Level Detection")
    
    renderer = InvalidationMarker()
    
    # LONG setup - price ABOVE invalidation (safe)
    logger.log_input("Setup", "LONG at 19600, invalidation at 19450")
    logger.log_input("Current price", 19550.0)
    
    viz_safe = renderer.render(
        htf_invalidation_price=19450.0,
        invalidation_type="HTF_SUPPORT_BREAK",
        description="HTF support break",
        current_price=19550.0,
        scenario="B",
        direction="LONG"
    )
    
    is_invalidated_safe = renderer.is_invalidated(viz_safe)
    logger.log_expected("Is invalidated", False)
    logger.log_actual("Is invalidated", is_invalidated_safe)
    assert not is_invalidated_safe, "False invalidation detected"
    
    # LONG setup - price BELOW invalidation (broken)
    logger.log_input("Current price", 19400.0)
    
    viz_broken = renderer.render(
        htf_invalidation_price=19450.0,
        invalidation_type="HTF_SUPPORT_BREAK",
        description="HTF support break",
        current_price=19400.0,
        scenario="B",
        direction="LONG"
    )
    
    is_invalidated_broken = renderer.is_invalidated(viz_broken)
    logger.log_expected("Is invalidated", True)
    logger.log_actual("Is invalidated", is_invalidated_broken)
    assert is_invalidated_broken, "Invalidation not detected"
    
    # SHORT setup - price BELOW invalidation (safe)
    logger.log_input("Setup", "SHORT at 19600, invalidation at 19750")
    logger.log_input("Current price", 19650.0)
    
    viz_short_safe = renderer.render(
        htf_invalidation_price=19750.0,
        invalidation_type="HTF_RESISTANCE_BREAK",
        description="HTF resistance break",
        current_price=19650.0,
        scenario="B",
        direction="SHORT"
    )
    
    is_invalidated_short_safe = renderer.is_invalidated(viz_short_safe)
    logger.log_expected("Is invalidated", False)
    logger.log_actual("Is invalidated", is_invalidated_short_safe)
    assert not is_invalidated_short_safe, "False invalidation detected for SHORT"
    
    # SHORT setup - price ABOVE invalidation (broken)
    logger.log_input("Current price", 19800.0)
    
    viz_short_broken = renderer.render(
        htf_invalidation_price=19750.0,
        invalidation_type="HTF_RESISTANCE_BREAK",
        description="HTF resistance break",
        current_price=19800.0,
        scenario="B",
        direction="SHORT"
    )
    
    is_invalidated_short_broken = renderer.is_invalidated(viz_short_broken)
    logger.log_expected("Is invalidated", True)
    logger.log_actual("Is invalidated", is_invalidated_short_broken)
    assert is_invalidated_short_broken, "Invalidation not detected for SHORT"
    
    # Test chart data
    chart_data_safe = renderer.to_chart_data(viz_safe)
    chart_data_broken = renderer.to_chart_data(viz_broken)
    
    logger.log_expected("Safe setup: is_invalidated=False in chart data", None)
    logger.log_actual("Safe is_invalidated", chart_data_safe["is_invalidated"])
    assert not chart_data_safe["is_invalidated"], "Chart data invalidation flag incorrect"
    
    logger.log_expected("Broken setup: is_invalidated=True in chart data", None)
    logger.log_actual("Broken is_invalidated", chart_data_broken["is_invalidated"])
    assert chart_data_broken["is_invalidated"], "Chart data invalidation flag incorrect"
    
    return logger.test_result(True, "Invalidation detection logic validated")


def test_complete_overlay_integration():
    """
    TC-10-05: Complete Overlay Integration
    Test that all renderers work together through StructuralChartOverlay.
    """
    logger = TestLogger()
    logger.test_header("TC-10-05", "Complete Overlay Integration")
    
    # Create complete input data
    logger.log_input("Symbol", "NIFTY")
    logger.log_input("Timeframe", "5min")
    logger.log_input("Current price", 19600.0)
    logger.log_input("Active scenario", "B")
    
    input_data = StructuralVisualizationInput(
        symbol="NIFTY",
        current_price=19600.0,
        timeframe="5min",
        htf_support_zones=[
            {
                "zone_type": "SUPPORT",
                "upper_bound": 19500.0,
                "lower_bound": 19450.0,
                "strength": "STRONG",
                "touches": 5
            }
        ],
        htf_resistance_zones=[
            {
                "zone_type": "RESISTANCE",
                "upper_bound": 19800.0,
                "lower_bound": 19750.0,
                "strength": "MODERATE",
                "touches": 3
            }
        ],
        htf_direction="BULLISH",
        scenario_a_zone={
            "upper_bound": 19900.0,
            "lower_bound": 19700.0,
            "probability": 0.35,
            "description": "Continuation"
        },
        scenario_b_zone={
            "upper_bound": 19700.0,
            "lower_bound": 19500.0,
            "probability": 0.54,
            "description": "Reversion"
        },
        scenario_c_zone={
            "upper_bound": 19500.0,
            "lower_bound": 19300.0,
            "probability": 0.11,
            "description": "Breakdown"
        },
        active_scenario="B",
        entry_price=19600.0,
        invalidation_price=19450.0,
        direction="LONG",
        max_risk_r=0.25,
        invalidation_reason="HTF support break"
    )
    
    # Create overlay
    overlay = StructuralChartOverlay()
    viz = overlay.create_visualization(input_data)
    
    logger.log_expected("Complete visualization with all components", None)
    logger.log_actual("Symbol", viz.symbol)
    logger.log_actual("Current price", viz.current_price)
    assert viz.symbol == "NIFTY", "Symbol incorrect"
    assert viz.current_price == 19600.0, "Current price incorrect"
    
    # Check HTF structure
    logger.log_expected("1 support zone, 1 resistance zone", None)
    logger.log_actual("Support zones", len(viz.htf_structure["supports"]))
    logger.log_actual("Resistance zones", len(viz.htf_structure["resistances"]))
    assert len(viz.htf_structure["supports"]) == 1, "Support count incorrect"
    assert len(viz.htf_structure["resistances"]) == 1, "Resistance count incorrect"
    
    # Check scenario zones
    logger.log_expected("3 scenario zones", None)
    logger.log_actual("Scenario zones", len(viz.scenario_zones["zones"]))
    assert len(viz.scenario_zones["zones"]) == 3, "Scenario count incorrect"
    
    # Check risk box
    logger.log_expected("Risk box present", True)
    logger.log_actual("Risk box present", viz.risk_box is not None)
    assert viz.risk_box is not None, "Risk box missing"
    
    # Check invalidation
    logger.log_expected("Invalidation markers present", True)
    logger.log_actual("Invalidation lines count", len(viz.invalidation_markers["invalidation_lines"]))
    assert len(viz.invalidation_markers["invalidation_lines"]) > 0, "Invalidation markers missing"
    
    # Check summary
    logger.log_expected("Summary with key metrics", None)
    logger.log_actual("Has risk setup", viz.summary["has_risk_setup"])
    logger.log_actual("Is invalidated", viz.summary["is_invalidated"])
    assert viz.summary["has_risk_setup"], "Risk setup flag incorrect"
    assert not viz.summary["is_invalidated"], "Invalidation flag incorrect"
    
    # Test JSON export
    json_str = viz.to_json()
    logger.log_expected("Valid JSON output", None)
    logger.log_actual("JSON length", f"{len(json_str)} chars")
    assert len(json_str) > 100, "JSON output too short"
    assert '"symbol": "NIFTY"' in json_str, "JSON missing symbol"
    
    # Validate visualization
    validation = overlay.validate_visualization(viz)
    logger.log_expected("Validation passed", True)
    logger.log_actual("Is valid", validation["is_valid"])
    logger.log_actual("Errors", validation["errors"])
    logger.log_actual("Warnings", validation["warnings"])
    assert validation["is_valid"], f"Validation failed: {validation['errors']}"
    
    return logger.test_result(True, "Complete overlay integration validated")


def test_visualization_validation():
    """
    TC-10-06: Visualization Validation Logic
    Test that validator catches structural inconsistencies.
    """
    logger = TestLogger()
    logger.test_header("TC-10-06", "Visualization Validation Logic")
    
    overlay = StructuralChartOverlay()
    
    # Valid setup
    logger.log_input("Test case", "Valid LONG setup")
    valid_input = StructuralVisualizationInput(
        symbol="NIFTY",
        current_price=19600.0,
        timeframe="5min",
        htf_support_zones=[{
            "zone_type": "SUPPORT",
            "upper_bound": 19500.0,
            "lower_bound": 19450.0,
            "strength": "STRONG",
            "touches": 3
        }],
        htf_resistance_zones=[],
        htf_direction="BULLISH",
        scenario_a_zone=None,
        scenario_b_zone={
            "upper_bound": 19700.0,
            "lower_bound": 19500.0,
            "probability": 0.70,
            "description": "Reversion"
        },
        scenario_c_zone={
            "upper_bound": 19500.0,
            "lower_bound": 19300.0,
            "probability": 0.30,
            "description": "Breakdown"
        },
        active_scenario="B",
        entry_price=19600.0,
        invalidation_price=19450.0,
        direction="LONG",
        max_risk_r=0.25,
        invalidation_reason="HTF support break"
    )
    
    viz_valid = overlay.create_visualization(valid_input)
    validation_valid = overlay.validate_visualization(viz_valid)
    
    logger.log_expected("Valid setup: no errors", None)
    logger.log_actual("Is valid", validation_valid["is_valid"])
    logger.log_actual("Errors", validation_valid["errors"])
    assert validation_valid["is_valid"], "Valid setup flagged as invalid"
    assert len(validation_valid["errors"]) == 0, "Errors on valid setup"
    
    # Invalid setup (LONG with invalidation ABOVE entry - structurally impossible)
    logger.log_input("Test case", "Invalid LONG setup (invalidation above entry)")
    try:
        invalid_input = StructuralVisualizationInput(
            symbol="NIFTY",
            current_price=19600.0,
            timeframe="5min",
            htf_support_zones=[],
            htf_resistance_zones=[],
            htf_direction="BULLISH",
            scenario_a_zone=None,
            scenario_b_zone={
                "upper_bound": 19700.0,
                "lower_bound": 19500.0,
                "probability": 1.0,
                "description": "Only scenario"
            },
            scenario_c_zone=None,
            active_scenario="B",
            entry_price=19600.0,
            invalidation_price=19750.0,  # ABOVE entry for LONG - wrong!
            direction="LONG",
            max_risk_r=0.25,
            invalidation_reason="Invalid structure"
        )
        
        # This should raise ValueError during RiskBox creation
        viz_invalid = overlay.create_visualization(invalid_input)
        logger.log_actual("Exception raised", False)
        assert False, "Invalid structure not caught"
    except ValueError as e:
        logger.log_expected("ValueError raised", None)
        logger.log_actual("Exception", str(e))
        assert "LONG invalidation must be below entry" in str(e), "Wrong error message"
    
    return logger.test_result(True, "Visualization validation logic working correctly")


def main():
    """Run all Phase-10 tests."""
    print("\n" + "="*70)
    print("PHASE-10 TEST SUITE: STRUCTURAL VISUALIZATION LAYER")
    print("="*70)
    print("\nPHILOSOPHY: The system knows. Humans need to see.")
    print("TESTING: Logic validation, NOT pixel rendering")
    print("="*70)
    
    results = []
    
    # Run all tests
    results.append(("TC-10-01", test_htf_zone_rendering()))
    results.append(("TC-10-02", test_scenario_zone_rendering()))
    results.append(("TC-10-03", test_risk_box_r_calculation()))
    results.append(("TC-10-04", test_invalidation_detection()))
    results.append(("TC-10-05", test_complete_overlay_integration()))
    results.append(("TC-10-06", test_visualization_validation()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_id, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_id}: {status}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "="*70)
        print("✓ PHASE-10 VALIDATED FOR PRODUCTION")
        print("="*70)
        print("\nSYSTEM CAPABILITIES ACHIEVED:")
        print("  • HTF structure visible (support/resistance zones)")
        print("  • Scenario zones color-coded (A/B/C outcomes)")
        print("  • Risk measured in R (structure-based, not money)")
        print("  • Invalidation levels marked (binary: holds or breaks)")
        print("  • Complete integration (all renderers coordinated)")
        print("  • Validation logic (catches structural inconsistencies)")
        print("\nREADY: Phase-11 (Order Construction) can proceed")
        print("NEXT: Wire Phase-10 → TradingView via Playwright")
        print("="*70)
        return 0
    else:
        print("\n" + "="*70)
        print("✗ TESTS FAILED - PHASE-10 NOT VALIDATED")
        print("="*70)
        return 1


if __name__ == "__main__":
    exit(main())
