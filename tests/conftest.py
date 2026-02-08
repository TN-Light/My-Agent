"""
Shared pytest configuration and fixtures for the My Agent test suite.
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so that imports like
# ``from logic.xxx import ...`` work regardless of how pytest is invoked.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Custom markers
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Register custom markers to avoid warnings."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks integration tests that need external services")
    config.addinivalue_line("markers", "windows_only: marks tests that only run on Windows")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_dir(tmp_path):
    """
    Provide a temporary directory that is automatically cleaned up.

    Yields:
        pathlib.Path: A fresh temporary directory unique to the test.
    """
    yield tmp_path


@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary database path for testing storage modules."""
    db_path = tmp_path / "test.db"
    yield str(db_path)


@pytest.fixture
def mock_llm_client():
    """
    Return a MagicMock that stands in for ``logic.llm_client.LLMClient``.

    The mock pre-configures ``generate()`` and ``generate_completion()`` to
    return canned responses so tests don't need a live Ollama server.
    """
    client = MagicMock()
    client.generate.return_value = '{"action": "none", "reason": "mock response"}'
    client.generate_completion.return_value = '{"action": "none", "reason": "mock response"}'
    client.health_check.return_value = True
    client.model = "mock-model"
    client.base_url = "http://localhost:11434"
    return client


@pytest.fixture
def mock_chat_ui():
    """Return a MagicMock standing in for ChatUI."""
    ui = MagicMock()
    ui.log = MagicMock()
    ui.set_status = MagicMock()
    return ui


@pytest.fixture
def sample_market_data():
    """
    Return a minimal market-data dict useful for testing analysis flows.
    """
    return {
        "symbol": "NIFTY",
        "timeframe": "daily",
        "timestamp": datetime.now().isoformat(),
        "trend": "bullish",
        "key_levels": {"support": 22000, "resistance": 23000},
        "confidence": 0.75,
    }


@pytest.fixture
def sample_mtf_data():
    """Return sample multi-timeframe analysis data for display tests."""
    def _make_tf_data(trend, support, resistance):
        return {
            "analysis": {
                "trend": trend,
                "support": support,
                "resistance": resistance,
                "momentum": "positive" if trend == "bullish" else "negative",
            }
        }
    return {
        "monthly": _make_tf_data("bullish", [22000, 21500], [24000, 24500]),
        "weekly": _make_tf_data("bullish", [22500, 22200], [23500, 23800]),
        "daily": _make_tf_data("sideways", [22800], [23200]),
    }


@pytest.fixture
def mock_observation_result():
    """
    Return a lightweight ``ObservationResult``-like dict for tests that
    exercise observation handling without importing the full module.
    """
    return {
        "success": True,
        "data": {"raw_text": "mock screen content", "elements": []},
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_config():
    """Return a minimal agent config dict for testing."""
    return {
        "planner": {"use_llm": True, "mode": "llm", "max_actions_per_plan": 15},
        "llm": {
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model": "llama3.2",
            "temperature": 0.1,
            "timeout": 30,
        },
        "fallback": {"on_llm_failure": "abort", "notify_user": True},
        "browser": {"enabled": True, "headless": False},
        "vision": {"enabled": True, "verification_confidence": 0.7},
        "market_analysis": {
            "safety": {
                "allow_trading": False,
                "allow_chart_drawing": False,
            }
        },
    }
