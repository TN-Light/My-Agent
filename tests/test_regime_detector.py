"""Phase-B: Regime Detector Tests"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.regime_detector import (
    RegimeDetector, RegimeMemoryStore, RegimeContext,
    MarketRegime, LevelInteraction
)


def test_regime_store():
    """Test RegimeMemoryStore CRUD operations."""
    store = RegimeMemoryStore(db_path="db/test_regime.db")
    
    # Store regimes
    r1 = store.store_regime("RELIANCE", MarketRegime.TRENDING_UP, 0.85, "bullish", "Initial")
    assert r1 > 0, f"Expected positive ID, got {r1}"
    
    r2 = store.store_regime("RELIANCE", MarketRegime.RANGING, 0.60, "sideways", "Trend break")
    assert r2 > 0
    
    # Current regime should be RANGING
    current = store.get_current_regime("RELIANCE")
    assert current is not None
    assert current["regime"] == "ranging"
    print(f"  Current regime: {current['regime']} (OK)")
    
    # History should have 2 entries
    history = store.get_regime_history("RELIANCE")
    assert len(history) == 2
    print(f"  History entries: {len(history)} (OK)")
    
    # First entry should be closed (ended != active)
    assert history[1]["ended"] != "active"  # Oldest first when desc
    print(f"  Previous regime closed: OK")
    
    # Level interactions
    store.upsert_level_interaction("RELIANCE", 2500.0, "support", held=True)
    store.upsert_level_interaction("RELIANCE", 2500.0, "support", held=True)
    store.upsert_level_interaction("RELIANCE", 2500.0, "support", held=False)
    
    levels = store.get_level_interactions("RELIANCE")
    assert len(levels) == 1
    assert levels[0].test_count == 3
    assert levels[0].held == 2
    assert levels[0].broken == 1
    hold_rate = levels[0].hold_rate()
    assert abs(hold_rate - 0.667) < 0.01
    print(f"  Level tracking: 3 tests, {hold_rate:.0%} hold rate (OK)")
    
    # Cleanup
    os.remove("db/test_regime.db")
    print("  PASS: RegimeMemoryStore")


def test_regime_context():
    """Test RegimeContext flag generation and prompt output."""
    ctx = RegimeContext(
        regime=MarketRegime.TRENDING_UP,
        regime_confidence=0.85,
        trend_direction="bullish",
        trend_duration_days=45,
        trend_consistency=0.80,
        regime_changed=True,
        previous_regime=MarketRegime.RANGING,
        days_since_regime_change=2,
        key_levels=[
            LevelInteraction(
                level=2500.0, level_type="support",
                first_seen="2024-01-01", last_tested="2024-03-01",
                test_count=5, held=4, broken=1, significance=0.9
            )
        ]
    )
    
    # Check flags
    flags = ctx.get_regime_flags()
    assert "REGIME_CHANGE" in flags, f"Expected REGIME_CHANGE, got {flags}"
    print(f"  Flags: {flags} (OK)")
    
    # Check prompt context
    prompt = ctx.get_prompt_context()
    assert "REGIME CHANGE DETECTED" in prompt
    assert "trending_up" in prompt.lower() or "TRENDING_UP" in prompt
    assert "2500" in prompt
    print(f"  Prompt context generated: {len(prompt)} chars (OK)")
    
    # Test extended trend flag
    ctx2 = RegimeContext(
        regime=MarketRegime.TRENDING_UP,
        trend_duration_days=90
    )
    flags2 = ctx2.get_regime_flags()
    assert "EXTENDED_TREND" in flags2
    print(f"  Extended trend flag: OK")
    
    # Test volatile flag
    ctx3 = RegimeContext(regime=MarketRegime.VOLATILE)
    flags3 = ctx3.get_regime_flags()
    assert "HIGH_VOLATILITY" in flags3
    print(f"  Volatility flag: OK")
    
    print("  PASS: RegimeContext")


def test_regime_classification():
    """Test regime classification from mock analysis data."""
    store = RegimeMemoryStore(db_path="db/test_regime2.db")
    
    # Mock analysis store with a db_path attribute
    class MockAnalysisStore:
        def __init__(self):
            self.db_path = "db/market_analyses.db"
    
    # We can't fully test without real DB, but we can test the classifier logic
    detector = RegimeDetector(MockAnalysisStore(), store)
    
    # Test _classify_regime with mock analyses
    # All bullish → TRENDING_UP
    mock_analyses = [{"trend": "bullish"} for _ in range(10)]
    regime, conf = detector._classify_regime(mock_analyses)
    assert regime == MarketRegime.TRENDING_UP
    assert conf > 0.8
    print(f"  All bullish → {regime.value} ({conf:.0%}) (OK)")
    
    # All bearish → TRENDING_DOWN
    mock_analyses = [{"trend": "bearish"} for _ in range(10)]
    regime, conf = detector._classify_regime(mock_analyses)
    assert regime == MarketRegime.TRENDING_DOWN
    print(f"  All bearish → {regime.value} ({conf:.0%}) (OK)")
    
    # Mixed sideways → RANGING
    mock_analyses = [{"trend": "sideways"} for _ in range(7)] + [{"trend": "bullish"} for _ in range(3)]
    regime, conf = detector._classify_regime(mock_analyses)
    assert regime == MarketRegime.RANGING
    print(f"  Mostly sideways → {regime.value} ({conf:.0%}) (OK)")
    
    # Recent flip → TRANSITIONING
    mock_analyses = [{"trend": "bullish"} for _ in range(8)] + [{"trend": "bearish"} for _ in range(2)]
    regime, conf = detector._classify_regime(mock_analyses)
    assert regime == MarketRegime.TRANSITIONING
    print(f"  Bull→Bear flip → {regime.value} ({conf:.0%}) (OK)")
    
    # Recent mixed → VOLATILE
    mock_analyses = [
        {"trend": "bullish"}, {"trend": "bearish"},
        {"trend": "bullish"}, {"trend": "bearish"},
        {"trend": "bullish"}, {"trend": "bearish"},
    ]
    regime, conf = detector._classify_regime(mock_analyses)
    assert regime == MarketRegime.VOLATILE
    print(f"  Alternating → {regime.value} ({conf:.0%}) (OK)")
    
    # Test trend duration
    mock_with_ts = [
        {"trend": "bearish", "timestamp": "2024-01-01T00:00:00"},
        {"trend": "bearish", "timestamp": "2024-01-10T00:00:00"},
        {"trend": "bullish", "timestamp": "2024-01-20T00:00:00"},
        {"trend": "bullish", "timestamp": "2024-02-15T00:00:00"},
        {"trend": "bullish", "timestamp": "2024-03-01T00:00:00"},
    ]
    direction, duration, consistency = detector._calculate_trend_duration(mock_with_ts)
    assert direction == "bullish"
    assert duration > 0
    assert 0.5 < consistency < 0.7  # 3/5 = 60%
    print(f"  Trend duration: {direction} {duration}d, {consistency:.0%} consistent (OK)")
    
    # Cleanup
    os.remove("db/test_regime2.db")
    print("  PASS: RegimeClassification")


if __name__ == "__main__":
    print("Phase-B: Regime Detector Tests")
    print("=" * 50)
    test_regime_store()
    test_regime_context()
    test_regime_classification()
    print("=" * 50)
    print("ALL TESTS PASSED")
