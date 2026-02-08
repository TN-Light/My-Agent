"""
Common Constants — Centralized magic numbers and thresholds.
All tunable parameters in one place for easy adjustment.
"""

# ── Timing Constants ──────────────────────────────────────────────────
BROWSER_PAGE_LOAD_TIMEOUT_MS = 30000
BROWSER_ELEMENT_TIMEOUT_MS = 2000
BROWSER_SEARCH_TIMEOUT_MS = 15000
CHART_RENDER_WAIT_SECS = 2.0
CHART_REDRAW_WAIT_SECS = 1.0
FOCUS_SETTLE_DELAY_SECS = 0.3
MODAL_POLL_DELAY_SECS = 0.5
OCR_DELAY_SECS = 0.3
GOOGLE_SEARCH_TIMEOUT_SECS = 20
GOOGLE_PAGE_TIMEOUT_MS = 15000

# ── LLM / Ollama ─────────────────────────────────────────────────────
LLM_DEFAULT_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECS = 1.0
LLM_REQUEST_TIMEOUT_SECS = 30

# ── Execution Tokens ─────────────────────────────────────────────────
TOKEN_LIFETIME_MINUTES = 15

# ── Risk / Trading Thresholds ────────────────────────────────────────
SCENARIO_PROBABILITY_HIGH = 0.50
SCENARIO_PROBABILITY_MODERATE = 0.35
SCENARIO_PROBABILITY_LOW = 0.25
EXPECTANCY_EDGE_DEGRADATION_THRESHOLD = 0.45
EXPECTANCY_MINIMUM_SAMPLE_SIZE = 50
EXPECTANCY_REGIME_SHIFT_MULTIPLIER = 1.5
VISION_VERIFICATION_CONFIDENCE = 0.7

# ── Scenario Base Probabilities ──────────────────────────────────────
SCENARIO_BASE_CONTINUATION = 0.33
SCENARIO_BASE_PULLBACK = 0.33
SCENARIO_BASE_FAILURE = 0.34

# ── Screen Capture ───────────────────────────────────────────────────
MIN_WINDOW_AREA_PX = 100_000
FULLSCREEN_THRESHOLD_RATIO = 0.95
DEFAULT_SCREEN_AREA = 1920 * 1080

# ── File Operations ──────────────────────────────────────────────────
MAX_FILE_SIZE_KB = 1024

# ── Database Paths (centralized) ─────────────────────────────────────
DB_DIR = "db"
DATA_DIR = "data"
LOG_DIR = "data/logs"

DB_PATH_HISTORY = f"{DB_DIR}/history.db"
DB_PATH_PLANS = f"{DB_DIR}/plans.db"
DB_PATH_OBSERVATIONS = f"{DB_DIR}/observations.db"
DB_PATH_EXECUTION_GATE_LOG = f"{DB_DIR}/execution_gate_log.db"
DB_PATH_MARKET_ANALYSES = f"{DB_DIR}/market_analyses.db"
DB_PATH_SCENARIO_RESOLUTIONS = f"{DB_DIR}/scenario_resolutions.db"
DB_PATH_EXECUTION_AUDIT = f"{DB_DIR}/execution_audit.db"
DB_PATH_RISK_STATE = f"{DB_DIR}/risk_state.db"
DB_PATH_TRADE_LIFECYCLE = f"{DB_DIR}/trade_lifecycle.db"

# ── Logging ──────────────────────────────────────────────────────────
LOG_FILE_PATH = f"{LOG_DIR}/agent.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 3

# ── Google Search Rate Limiting ──────────────────────────────────────
GOOGLE_MIN_INTERVAL_SECS = 30.0
GOOGLE_MAX_RETRIES = 2
