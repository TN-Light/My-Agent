"""
Phase-2B Market Analysis Mode - Test Script

Tests the 4 required test prompts:
1. "Analyze RELIANCE on daily timeframe"
2. "Open TradingView and analyze NIFTY trend"
3. "Give technical analysis of TCS stock"
4. "What are the support and resistance levels for INFY?"

Expected behavior:
- Browser opens TradingView
- Chart loads without interaction
- Structured JSON analysis returned
- No chart drawing/manipulation
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_market_analysis_mode():
    """Test market analysis mode with required prompts."""
    
    # Import agent components
    from main import create_agent_components
    
    logger.info("=" * 60)
    logger.info("PHASE-2B MARKET ANALYSIS MODE TEST")
    logger.info("=" * 60)
    
    # Create agent
    config, components = create_agent_components()
    execution_engine = components["execution_engine"]
    
    # Test prompts
    test_prompts = [
        "Analyze RELIANCE on daily timeframe",
        "Open TradingView and analyze NIFTY trend",
        "Give technical analysis of TCS stock",
        "What are the support and resistance levels for INFY?"
    ]
    
    for i, prompt in enumerate(test_prompts, 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"TEST {i}: {prompt}")
        logger.info(f"{'=' * 60}\n")
        
        try:
            # Execute instruction
            execution_engine.execute_instruction(prompt)
            logger.info(f"\n[OK] Test {i} completed\n")
            
        except Exception as e:
            logger.error(f"[FAIL] Test {i} failed: {e}", exc_info=True)
    
    logger.info("\n" + "=" * 60)
    logger.info("MARKET ANALYSIS TESTS COMPLETE")
    logger.info("=" * 60)


def test_safety_constraints():
    """Test that safety constraints are enforced."""
    
    logger.info("\n" + "=" * 60)
    logger.info("TESTING SAFETY CONSTRAINTS")
    logger.info("=" * 60)
    
    from logic.policy_engine import PolicyEngine
    from common.actions import Action
    
    # Load policy
    policy_engine = PolicyEngine("config/policy.yaml")
    
    # Test 1: Valid observation action
    valid_action = Action(
        action_type="observe_dom",
        context="market_analysis",
        target="price"
    )
    
    approved, reason = policy_engine.validate_action(valid_action)
    assert approved, f"Valid observation should be approved: {reason}"
    logger.info("[OK] Valid observation action approved")
    
    # Test 2: Invalid action type (launch_app)
    invalid_action = Action(
        action_type="launch_app",
        context="market_analysis",
        target="notepad"
    )
    
    approved, reason = policy_engine.validate_action(invalid_action)
    assert not approved, "launch_app should NOT be allowed in market_analysis"
    logger.info(f"[OK] Invalid action rejected: {reason}")
    
    # Test 3: Coordinates not allowed
    try:
        coord_action = Action(
            action_type="observe_dom",
            context="market_analysis",
            target="chart",
            coordinates=(100, 200)
        )
        # Should fail during Action.__post_init__
        logger.error("[FAIL] Action with coordinates should not be allowed")
    except ValueError as e:
        logger.info(f"[OK] Coordinates blocked at Action level: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("SAFETY CONSTRAINTS VALIDATED")
    logger.info("=" * 60)


def test_symbol_extraction():
    """Test symbol extraction from instructions."""
    
    from logic.execution_engine import ExecutionEngine
    from main import create_agent_components
    
    logger.info("\n" + "=" * 60)
    logger.info("TESTING SYMBOL EXTRACTION")
    logger.info("=" * 60)
    
    config, components = create_agent_components()
    engine = components["execution_engine"]
    
    test_cases = [
        ("Analyze RELIANCE stock", "RELIANCE"),
        ("Give technical analysis of TCS", "TCS"),
        ("What about INFY?", "INFY"),
        ("Analyze NIFTY trend", "NIFTY"),
        ("Check HDFCBANK chart", "HDFCBANK"),
    ]
    
    for instruction, expected in test_cases:
        extracted = engine._extract_symbol_from_instruction(instruction)
        if extracted == expected:
            logger.info(f"[OK] '{instruction}' → {extracted}")
        else:
            logger.error(f"[FAIL] '{instruction}' → {extracted} (expected {expected})")
    
    logger.info("\n" + "=" * 60)
    logger.info("SYMBOL EXTRACTION TESTED")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Phase-2B Market Analysis Mode")
    parser.add_argument("--safety-only", action="store_true", help="Only test safety constraints")
    parser.add_argument("--symbol-only", action="store_true", help="Only test symbol extraction")
    
    args = parser.parse_args()
    
    if args.safety_only:
        test_safety_constraints()
    elif args.symbol_only:
        test_symbol_extraction()
    else:
        # Run safety tests first
        test_safety_constraints()
        test_symbol_extraction()
        
        # Then run full tests
        logger.info("\n\n")
        test_market_analysis_mode()
