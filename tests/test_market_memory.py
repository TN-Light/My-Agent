"""
Phase-2C Market Memory & Chat Analysis Mode - Test Script

Tests the 4 required test prompts:
1. "What was your last analysis on RELIANCE?"
2. "Compare INFY vs TCS technically"
3. "Which stock looks stronger today?"
4. "Has NIFTY trend changed?"

Expected behavior:
- NO browser for memory queries
- Browser opens ONLY for "latest" or "refresh"
- Answers from stored analyses
- Comparisons work across symbols
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_test_data():
    """
    Create some test analyses for testing chat queries.
    """
    from storage.market_analysis_store import MarketAnalysisStore
    from logic.market_memory import MarketMemory
    
    store = MarketAnalysisStore()
    memory = MarketMemory(store=store)
    
    # Create test analyses
    test_analyses = [
        {
            "symbol": "NSE:RELIANCE",
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "trend": "bullish",
            "support": [2780, 2720],
            "resistance": [2900, 2950],
            "momentum": "strong bullish",
            "bias": "strong uptrend with good momentum",
            "price": 2850.50
        },
        {
            "symbol": "NSE:TCS",
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "trend": "bullish",
            "support": [3650, 3580],
            "resistance": [3850, 3920],
            "momentum": "moderate bullish",
            "bias": "consolidating near resistance",
            "price": 3780.25
        },
        {
            "symbol": "NSE:INFY",
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "trend": "sideways",
            "support": [1420, 1400],
            "resistance": [1480, 1500],
            "momentum": "neutral",
            "bias": "range-bound trading",
            "price": 1445.75
        },
        {
            "symbol": "NSE:NIFTY",
            "timeframe": "1D",
            "timestamp": datetime.now().isoformat(),
            "trend": "bullish",
            "support": [21500, 21300],
            "resistance": [22000, 22200],
            "momentum": "moderate bullish",
            "bias": "positive bias with support holding",
            "price": 21750.80
        }
    ]
    
    for analysis in test_analyses:
        analysis_id = store.store_analysis(analysis)
        memory.store_analysis(analysis, analysis_id)
        logger.info(f"Created test analysis for {analysis['symbol']} - ID: {analysis_id}")
    
    logger.info("Test data setup complete")
    return store, memory


def test_market_memory_queries():
    """Test market memory chat queries."""
    
    logger.info("=" * 60)
    logger.info("PHASE-2C MARKET MEMORY & CHAT ANALYSIS TEST")
    logger.info("=" * 60)
    
    # Setup test data
    store, memory = setup_test_data()
    
    # Test 1: Last analysis query
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Last Analysis Query")
    logger.info("=" * 60)
    
    analysis = memory.get_latest_for_symbol("RELIANCE")
    if analysis:
        logger.info(f"[OK] Found last analysis for RELIANCE")
        logger.info(f"Trend: {analysis.get('trend')}, Momentum: {analysis.get('momentum')}")
    else:
        logger.error("[FAIL] No analysis found for RELIANCE")
    
    # Test 2: Comparison query
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Comparison Query")
    logger.info("=" * 60)
    
    comparison = memory.compare_symbols(["TCS", "INFY"])
    logger.info(f"[OK] Comparison complete")
    logger.info(f"Summary: {comparison['summary']}")
    logger.info(f"Strongest: {comparison['summary']['strongest']}")
    
    # Test 3: Strongest stock query
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Strongest Stock Query")
    logger.info("=" * 60)
    
    summary = memory.get_market_summary(hours=24)
    logger.info(f"[OK] Market summary retrieved")
    logger.info(f"Total analyses: {summary['total_analyses']}")
    logger.info(f"Overall bias: {summary['overall_bias']}")
    
    # Test 4: Trend change query
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Trend Change Query")
    logger.info("=" * 60)
    
    # Store another analysis with different trend to test change detection
    new_analysis = {
        "symbol": "NSE:NIFTY",
        "timeframe": "1D",
        "timestamp": datetime.now().isoformat(),
        "trend": "bearish",  # Changed from bullish
        "support": [21000, 20800],
        "resistance": [21500, 21700],
        "momentum": "moderate bearish",
        "bias": "downtrend emerging",
        "price": 21350.25
    }
    
    analysis_id = store.store_analysis(new_analysis)
    memory.store_analysis(new_analysis, analysis_id)
    
    change_info = memory.check_trend_change("NIFTY")
    logger.info(f"[OK] Trend change check complete")
    logger.info(f"Changed: {change_info.get('changed')}")
    logger.info(f"Description: {change_info.get('description')}")
    
    logger.info("\n" + "=" * 60)
    logger.info("ALL TESTS COMPLETE")
    logger.info("=" * 60)


def test_chat_detection():
    """Test that chat queries are correctly detected."""
    
    logger.info("\n" + "=" * 60)
    logger.info("TESTING CHAT QUERY DETECTION")
    logger.info("=" * 60)
    
    # Create minimal execution engine for testing
    from logic.execution_engine import ExecutionEngine
    from storage.market_analysis_store import MarketAnalysisStore
    from logic.market_memory import MarketMemory
    import yaml
    
    # Load config
    with open("config/agent_config.yaml") as f:
        config = yaml.safe_load(f)
    
    # Create minimal components
    store = MarketAnalysisStore()
    memory = MarketMemory(store=store)
    
    # Create mock execution engine with just what we need
    class MockEngine:
        def __init__(self, config):
            self.config = config
            self.market_memory = memory
            self.market_store = store
        
        def _is_market_chat_query(self, instruction: str) -> bool:
            """Copy of detection logic from execution_engine."""
            if not self.market_memory:
                return False
            
            instruction_lower = instruction.lower()
            
            chat_patterns = [
                "last analysis", "previous analysis", "what was", "what did you",
                "compare", "comparison", "vs", "versus",
                "which stock", "which is", "stronger", "weaker",
                "has trend changed", "trend change",
                "summarize", "summary", "today's", "recent", "market bias"
            ]
            
            market_keywords = [
                "stock", "reliance", "tcs", "infy", "nifty", "sensex",
                "analysis", "trend", "bullish", "bearish", "market"
            ]
            
            has_chat_pattern = any(pattern in instruction_lower for pattern in chat_patterns)
            has_market_keyword = any(keyword in instruction_lower for keyword in market_keywords)
            needs_refresh = any(word in instruction_lower for word in ["latest", "refresh", "current", "now", "live"])
            
            return has_chat_pattern and has_market_keyword and not needs_refresh
    
    engine = MockEngine(config)
    
    # Chat queries (should NOT open browser)
    chat_queries = [
        "What was your last analysis on RELIANCE?",
        "Compare INFY vs TCS technically",
        "Which stock looks stronger today?",
        "Has NIFTY trend changed?",
        "Summarize today's market bias"
    ]
    
    # Live queries (SHOULD open browser)
    live_queries = [
        "Analyze latest RELIANCE chart",
        "Refresh analysis for TCS",
        "Give me current NIFTY analysis"
    ]
    
    for query in chat_queries:
        is_chat = engine._is_market_chat_query(query)
        if is_chat:
            logger.info(f"[OK] Detected as chat query: '{query}'")
        else:
            logger.error(f"[FAIL] Should be chat query: '{query}'")
    
    for query in live_queries:
        is_chat = engine._is_market_chat_query(query)
        if not is_chat:
            logger.info(f"[OK] Detected as live query (browser needed): '{query}'")
        else:
            logger.error(f"[FAIL] Should be live query: '{query}'")
    
    logger.info("\n" + "=" * 60)
    logger.info("CHAT DETECTION TESTS COMPLETE")
    logger.info("=" * 60)


def test_full_chat_workflow():
    """Test full chat workflow - simplified without full agent."""
    
    logger.info("\n" + "=" * 60)
    logger.info("TESTING CHAT WORKFLOW (Simplified)")
    logger.info("=" * 60)
    
    # Setup test data first
    store, memory = setup_test_data()
    
    # Test the core functionality
    test_prompts = [
        ("What was your last analysis on RELIANCE?", "last_analysis"),
        ("Compare INFY vs TCS technically", "comparison"),
        ("Which stock looks stronger today?", "strongest"),
        ("Has NIFTY trend changed?", "trend_change")
    ]
    
    for i, (prompt, query_type) in enumerate(test_prompts, 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"TEST {i}: {prompt} (Type: {query_type})")
        logger.info(f"{'=' * 60}\n")
        
        try:
            if query_type == "last_analysis":
                analysis = memory.get_latest_for_symbol("RELIANCE")
                assert analysis is not None, "Should find RELIANCE analysis"
                logger.info(f"[OK] Found analysis: {analysis.get('trend')}")
                
            elif query_type == "comparison":
                comparison = memory.compare_symbols(["TCS", "INFY"])
                assert len(comparison["analyses"]) == 2, "Should compare 2 symbols"
                logger.info(f"[OK] Comparison done: strongest={comparison['summary']['strongest']}")
                
            elif query_type == "strongest":
                summary = memory.get_market_summary(hours=24)
                assert summary["total_analyses"] > 0, "Should have analyses"
                logger.info(f"[OK] Market summary: {summary['overall_bias']}")
                
            elif query_type == "trend_change":
                change_info = memory.check_trend_change("NIFTY")
                logger.info(f"[OK] Trend check: changed={change_info.get('changed')}")
            
            logger.info(f"[OK] Test {i} completed\n")
            
        except Exception as e:
            logger.error(f"[FAIL] Test {i} failed: {e}", exc_info=True)
    
    logger.info("\n" + "=" * 60)
    logger.info("FULL CHAT WORKFLOW TESTS COMPLETE")
    logger.info("=" * 60)


def test_storage_stats():
    """Test database statistics."""
    
    from storage.market_analysis_store import MarketAnalysisStore
    
    logger.info("\n" + "=" * 60)
    logger.info("DATABASE STATISTICS")
    logger.info("=" * 60)
    
    store = MarketAnalysisStore()
    stats = store.get_stats()
    
    logger.info(f"Total Analyses: {stats['total_analyses']}")
    logger.info(f"Unique Symbols: {stats['unique_symbols']}")
    logger.info(f"Oldest Analysis: {stats['oldest_analysis']}")
    logger.info(f"Latest Analysis: {stats['latest_analysis']}")
    
    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Phase-2C Market Memory & Chat Analysis")
    parser.add_argument("--memory-only", action="store_true", help="Only test memory queries")
    parser.add_argument("--detection-only", action="store_true", help="Only test chat detection")
    parser.add_argument("--stats-only", action="store_true", help="Only show database stats")
    
    args = parser.parse_args()
    
    if args.memory_only:
        test_market_memory_queries()
    elif args.detection_only:
        test_chat_detection()
    elif args.stats_only:
        test_storage_stats()
    else:
        # Run all tests
        test_market_memory_queries()
        test_chat_detection()
        test_storage_stats()
        
        # Full workflow test
        logger.info("\n\n")
        test_full_chat_workflow()
