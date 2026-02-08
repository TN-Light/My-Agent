"""
Test Phase-11.5G Symbol Resolution System
Quick validation of 3-layer resolution with strict Google rules.
"""

import logging
from logic.symbol_resolver import (
    SymbolResolver,
    ResolutionMode,
    ResolutionStatus,
    ResolutionSource,
    ResolutionConfidence
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ticker_detection():
    """Test ticker-like input detection."""
    print("\n" + "="*70)
    print("TEST 1: Ticker Detection")
    print("="*70)
    
    resolver = SymbolResolver()
    
    test_cases = [
        ("YESBANK", True),
        ("SBIN", True),
        ("yes bank", False),  # Has space
        ("tata consumer", False),  # Has space
        ("ktk", True),
        ("123", True),  # Alphanumeric but short
        ("AB", True),
        ("A", False),  # Too short
        ("VERYLONGSYMBOLNAME123", False),  # Too long
    ]
    
    for input_text, expected in test_cases:
        result = resolver._looks_like_ticker(input_text.upper())
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_text}' → {result} (expected: {expected})")


def test_google_rules():
    """Test Google usage rules (STRICT)."""
    print("\n" + "="*70)
    print("TEST 2: Google Usage Rules (STRICT)")
    print("="*70)
    
    resolver = SymbolResolver()
    
    # Test Rule 1: Mode must be SINGLE_ANALYSIS
    test_cases = [
        ("yes bank", ResolutionMode.SINGLE_ANALYSIS, True),
        ("yes bank", ResolutionMode.MARKET_SCAN, False),
        ("tata consumer", ResolutionMode.AUTOMATED_SCAN, False),
        ("YESBANK", ResolutionMode.SINGLE_ANALYSIS, False),  # Looks like ticker
        ("ktk bank", ResolutionMode.SINGLE_ANALYSIS, True),
    ]
    
    for user_input, mode, expected in test_cases:
        result = resolver._is_google_allowed(user_input, mode)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{user_input}' + {mode.value} → {result} (expected: {expected})")
    
    # Test Rule 4: Only one Google attempt per session
    print("\nTesting attempt limit...")
    resolver.google_attempts = 0
    allowed1 = resolver._is_google_allowed("tata consumer", ResolutionMode.SINGLE_ANALYSIS)
    print(f"  Attempt 1: {allowed1} (expected: True)")
    
    resolver.google_attempts = 1
    allowed2 = resolver._is_google_allowed("tata consumer", ResolutionMode.SINGLE_ANALYSIS)
    print(f"  Attempt 2: {allowed2} (expected: False)")


def test_symbol_memory():
    """Test symbol memory caching."""
    print("\n" + "="*70)
    print("TEST 3: Symbol Memory (Cache)")
    print("="*70)
    
    from storage.symbol_memory import SymbolMemory
    
    # Create fresh cache
    import tempfile
    import os
    cache_file = os.path.join(tempfile.gettempdir(), "test_symbol_cache.json")
    
    memory = SymbolMemory(cache_file)
    
    # Test store and lookup
    memory.store(
        user_text="tata consumer",
        nse_symbol="TATACONSUM",
        confidence="HIGH",
        source="GOOGLE"
    )
    
    cached = memory.lookup("tata consumer")
    if cached:
        print(f"✓ Cache HIT: 'tata consumer' → {cached.nse_symbol}")
        print(f"  Confidence: {cached.confidence}")
        print(f"  Source: {cached.source}")
    else:
        print("✗ Cache MISS (unexpected)")
    
    # Test case insensitive
    cached2 = memory.lookup("TATA CONSUMER")
    if cached2:
        print(f"✓ Case insensitive lookup works: '{cached2.nse_symbol}'")
    else:
        print("✗ Case insensitive lookup failed")
    
    # Test stats
    stats = memory.get_stats()
    print(f"\nCache Stats:")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Sources: {stats['sources']}")
    
    # Cleanup
    if os.path.exists(cache_file):
        os.remove(cache_file)


def test_resolution_modes():
    """Test resolution behavior in different modes."""
    print("\n" + "="*70)
    print("TEST 4: Resolution Modes (Without TradingView)")
    print("="*70)
    
    resolver = SymbolResolver()  # No TradingView client
    
    # Test MARKET_SCAN mode (no Google)
    print("\nMARKET_SCAN Mode (no Google fallback):")
    result1 = resolver.resolve("invalid symbol", mode=ResolutionMode.MARKET_SCAN)
    print(f"  Status: {result1.status.value}")
    print(f"  Expected: DATA_UNAVAILABLE")
    print(f"  ✓ Correct" if result1.status == ResolutionStatus.DATA_UNAVAILABLE else "  ✗ Wrong")
    
    # Test SINGLE_ANALYSIS mode (Google allowed but no LLM)
    print("\nSINGLE_ANALYSIS Mode (Google allowed but no LLM):")
    result2 = resolver.resolve("tata consumer", mode=ResolutionMode.SINGLE_ANALYSIS)
    print(f"  Status: {result2.status.value}")
    print(f"  Expected: UNKNOWN (LLM not available)")
    print(f"  ✓ Correct" if result2.status == ResolutionStatus.UNKNOWN else "  ✗ Wrong")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE-11.5G SYMBOL RESOLUTION TESTS")
    print("="*70)
    print("\nThese tests validate the 3-layer resolution system:")
    print("1. Symbol Memory (cache)")
    print("2. TradingView validation")
    print("3. Google search (STRICT rules)")
    print("="*70)
    
    test_ticker_detection()
    test_google_rules()
    test_symbol_memory()
    test_resolution_modes()
    
    print("\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70)
    print("\nNOTE: Full integration test with TradingView requires:")
    print("  python test_phase_11_5_integration.py")
