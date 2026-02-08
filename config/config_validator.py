"""
Config Validator — Pydantic models for agent_config.yaml
Catches typos and missing fields at startup instead of silent None failures.
"""

from typing import Optional, List, Literal
try:
    from pydantic import BaseModel, Field, validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


if PYDANTIC_AVAILABLE:

    class PlannerConfig(BaseModel):
        use_llm: bool = True
        mode: Literal["deterministic", "llm"] = "llm"
        max_actions_per_plan: int = Field(default=15, ge=1, le=100)

    class LLMConfig(BaseModel):
        provider: Literal["ollama"] = "ollama"
        base_url: str = "http://localhost:11434"
        model: str = "llama3.2"
        temperature: float = Field(default=0.1, ge=0.0, le=2.0)
        timeout: int = Field(default=30, ge=5, le=300)
        max_tokens: int = Field(default=500, ge=50, le=10000)
        strict_parsing: bool = True

    class FallbackConfig(BaseModel):
        on_llm_failure: Literal["abort", "deterministic"] = "abort"
        notify_user: bool = True

    class BrowserConfig(BaseModel):
        enabled: bool = True
        headless: bool = False
        default_timeout: int = Field(default=30000, ge=1000, le=120000)
        use_existing_browser: bool = False
        cdp_url: str = "http://localhost:9222"
        use_personal_profile: bool = True
        profile_path: str = "C:/Users/amanu/AppData/Local/AgentBrowser"

    class FileConfig(BaseModel):
        enabled: bool = True
        workspace: str = "C:/Users/amanu/OneDrive/Documents/AgentWorkspace"
        max_file_size_kb: int = Field(default=1024, ge=1, le=102400)

    class ControlConfig(BaseModel):
        max_wait_duration: int = Field(default=30, ge=1, le=300)

    class PlanApprovalConfig(BaseModel):
        enabled: bool = True
        require_approval_for: List[str] = ["launch_app", "close_app"]
        approval_mode: Literal["batch"] = "batch"
        show_preview: bool = True
        preview_format: Literal["tree"] = "tree"

    class UnsavedChangesConfig(BaseModel):
        default_action: Literal["ask", "save", "discard", "fail"] = "ask"
        require_confirmation: bool = True

    class ObservationConfig(BaseModel):
        enabled: bool = True
        types: List[str] = ["read_text", "query_element", "observe_dom", "observe_vision"]

    class TradingViewConfig(BaseModel):
        base_url: str = "https://www.tradingview.com"
        default_timeframe: str = "1D"
        chart_load_timeout: int = Field(default=15, ge=5, le=60)

    class AuthorityConfig(BaseModel):
        primary: Literal["DOM", "VISION"] = "DOM"
        fallback: Literal["DOM", "VISION"] = "VISION"

    class SafetyConfig(BaseModel):
        allow_chart_drawing: bool = False
        allow_trading: bool = False
        allow_coordinate_clicks: bool = False
        allow_chart_manipulation: bool = False

        @validator("allow_trading")
        def trading_must_be_false(cls, v):
            if v:
                raise ValueError("allow_trading must NEVER be True — safety invariant")
            return v

    class OutputConfig(BaseModel):
        format: Literal["json"] = "json"
        include_disclaimer: bool = True

    class MarketAnalysisConfig(BaseModel):
        enabled: bool = True
        mode: Literal["read_only"] = "read_only"
        tradingview: TradingViewConfig = TradingViewConfig()
        authority: AuthorityConfig = AuthorityConfig()
        safety: SafetyConfig = SafetyConfig()
        output: OutputConfig = OutputConfig()

    class VisionConfig(BaseModel):
        enabled: bool = True
        provider: Literal["ollama"] = "ollama"
        base_url: str = "http://localhost:11434"
        model: str = "llava:7b"
        timeout: int = Field(default=60, ge=10, le=300)
        verification_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
        authority_level: int = 4
        observation_only: bool = True
        fallback_only: bool = True
        types: List[str] = ["describe_screen", "find_element", "read_text"]

    class AgentConfig(BaseModel):
        """Top-level validated config model matching agent_config.yaml."""
        version: float = 2.2
        agent_id: str = "local_desktop_agent_01"
        planner: PlannerConfig = PlannerConfig()
        llm: LLMConfig = LLMConfig()
        fallback: FallbackConfig = FallbackConfig()
        browser: BrowserConfig = BrowserConfig()
        file: FileConfig = FileConfig()
        control: ControlConfig = ControlConfig()
        plan_approval: PlanApprovalConfig = PlanApprovalConfig()
        observation: ObservationConfig = ObservationConfig()
        market_analysis: MarketAnalysisConfig = MarketAnalysisConfig()
        vision: VisionConfig = VisionConfig()

        class Config:
            extra = "allow"  # Allow unknown keys for forward compatibility


def load_validated_config(config_path: str = "config/agent_config.yaml") -> dict:
    """
    Load and validate the agent config. Falls back to raw dict if pydantic is unavailable.
    
    Returns:
        Validated config as dict.
    
    Raises:
        ValueError on validation failure (with human-readable details).
    """
    path = Path(config_path)
    
    if not path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        if PYDANTIC_AVAILABLE:
            return AgentConfig().dict()
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    
    if not PYDANTIC_AVAILABLE:
        logger.warning("pydantic not installed — config validation skipped. Install with: pip install pydantic")
        return raw
    
    try:
        validated = AgentConfig(**raw)
        logger.info("Config validated successfully")
        return validated.dict()
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        raise ValueError(f"Invalid config at {config_path}: {e}") from e
