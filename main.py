"""
My Agent - Phase-2C/3A/3B Main Entry Point
Local-first desktop AI agent for productivity automation.

Phase-2C Features:
- Vision layer (describe_screen, find_element, read_text via VLM)
- Vision as Level 4 authority - advisory only, never triggers actions

Phase-3A Features:
- Visual Scaffolding (list_visual_regions, identify_visible_text_blocks)
- Structured layout understanding (Level 3 authority)

Phase-3B Features:
- Vision-assisted verification fallback in Critic
- Used only when DOM/UIA verification fails
- Vision is advisory, cannot trigger retries or actions

Perception Hierarchy (03_architecture.md):
- Level 1: Accessibility Tree (UIA) - highest authority
- Level 2: DOM (Playwright) - web only
- Level 3: Visual Scaffolding (VLM) - structured layout
- Level 4: Vision (VLM) - basic descriptions, verification fallback
"""
import sys
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime
import yaml
from PySide6.QtWidgets import QApplication

# Configure UTF-8 output for Windows console (prevents Unicode crashes)
# MUST be done before any logging or print statements
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    # Fallback for older Python or if reconfigure fails
    import codecs
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from perception.accessibility_client import AccessibilityClient
from perception.observer import Observer
from logic.planner import Planner
from logic.critic import Critic
from logic.policy_engine import PolicyEngine
from logic.execution_engine import ExecutionEngine
from execution.controller import Controller
from storage.action_logger import ActionLogger
from storage.observation_logger import ObservationLogger
from storage.plan_logger import PlanLogger
from storage.step_approval_logger import StepApprovalLogger
from replay_engine import ReplayEngine
from interface.chat_ui import ChatUI
from interface.tray_daemon import TrayDaemon
from common.actions import Action
from common.observations import Observation
from common.plan_graph import PlanGraph

# Configure logging with console + rotating file handler
from logging.handlers import RotatingFileHandler
import os

_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs')
os.makedirs(_log_dir, exist_ok=True)

_log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_formatter = logging.Formatter(_log_format)

# Console handler (uses UTF-8 configured stdout)
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(_formatter)

# Rotating file handler: 5 MB max, keep 3 backups
_file_handler = RotatingFileHandler(
    os.path.join(_log_dir, 'agent.log'),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_formatter)

# Apply to root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[_console_handler, _file_handler]
)

logger = logging.getLogger(__name__)


class Agent:
    """
    Main agent orchestrator.
    
    Implements the canonical execution loop:
    1. PLAN - Generate action sequence
    2. POLICY CHECK - Validate against safety rules
    3. ACT - Execute via Controller
    4. VERIFY - Confirm success via Critic
    5. COMMIT - Log to database
    """
    
    def __init__(self):
        """Initialize the agent and all modules."""
        logger.info("=" * 60)
        logger.info("Initializing My Agent - Phase-2B")
        logger.info("=" * 60)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize modules
        self.accessibility = AccessibilityClient()
        
        # Initialize LLM client if enabled
        llm_client = None
        self.model_registry = None
        planner_config = self.config.get("planner", {})
        if planner_config.get("use_llm", False):
            try:
                from logic.llm_client import LLMClient
                llm_config = self.config.get("llm", {})
                base_url = llm_config.get("base_url", "http://localhost:11434")
                
                # Phase-D: Auto-detect best available models
                try:
                    from logic.model_registry import ModelRegistry
                    self.model_registry = ModelRegistry(base_url)
                    self.model_registry.discover()
                    
                    best_text = self.model_registry.get_best_text_model()
                    logger.info(f"Phase-D: Auto-selected text model: {best_text.name} (priority={best_text.priority})")
                    
                    # Use auto-detected model, with config override if explicitly set
                    text_model = llm_config.get("model", best_text.name)
                    text_timeout = max(llm_config.get("timeout", 30), 120 if best_text.priority >= 80 else 60)
                    
                    # Show upgrade suggestions in log
                    for suggestion in self.model_registry.get_model_upgrade_suggestions():
                        logger.info(f"Phase-D: {suggestion}")
                except Exception as e:
                    logger.warning(f"Phase-D: Model registry failed, using defaults: {e}")
                    text_model = llm_config.get("model", "llama3.2")
                    text_timeout = llm_config.get("timeout", 30)
                
                llm_client = LLMClient(
                    base_url=base_url,
                    model=text_model,
                    temperature=llm_config.get("temperature", 0.1),
                    timeout=text_timeout
                )
                logger.info(f"LLM client initialized: {text_model}")
                
                # Verify required models are available in Ollama
                self._verify_ollama_models(llm_config)
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")
                logger.warning("Falling back to deterministic planner")
        
        # Phase-2A: Initialize browser handler
        browser_handler = None
        browser_config = self.config.get("browser", {})
        if browser_config.get("enabled", False):
            try:
                from execution.browser_handler import BrowserHandler
                browser_handler = BrowserHandler(self.config)
                logger.info("Browser handler initialized")
            except Exception as e:
                logger.error(f"Failed to initialize browser handler: {e}")
                logger.warning("Browser automation disabled")
        
        # Phase-2A: Initialize file handler
        file_handler = None
        file_config = self.config.get("file", {})
        if file_config.get("enabled", False):
            try:
                from execution.file_handler import FileHandler
                workspace_path = file_config.get("workspace")
                if workspace_path:
                    file_handler = FileHandler(workspace_path)
                    logger.info("File handler initialized")
                else:
                    logger.warning("File handler disabled: no workspace path configured")
            except Exception as e:
                logger.error(f"Failed to initialize file handler: {e}")
                logger.warning("File operations disabled")
        
        self.planner = Planner(config=self.config, llm_client=llm_client, file_handler=file_handler)
        self.policy_engine = PolicyEngine(policy_path="config/policy.yaml")
        self.controller = Controller(
            browser_handler=browser_handler, 
            file_handler=file_handler,
            accessibility_client=self.accessibility
        )
        
        # Phase-2B/2C/3A: Initialize Observer and ObservationLogger
        # Phase-3B: Add vision to Critic for fallback verification
        vision_client = None
        screen_capture = None
        vision_config = self.config.get("vision", {})
        if vision_config.get("enabled", False):
            try:
                from perception.vision_client import VisionClient
                from perception.screen_capture import ScreenCapture
                
                # Phase-D: Auto-detect best vision model
                vision_model = vision_config.get("model", "llama3.2-vision")
                vision_timeout = vision_config.get("timeout", 60)
                try:
                    if self.model_registry:
                        best_vision = self.model_registry.get_best_vision_model()
                        vision_model = vision_config.get("model", best_vision.name)
                        vision_timeout = max(vision_timeout, 90 if best_vision.priority >= 80 else 60)
                        logger.info(f"Phase-D: Auto-selected vision model: {best_vision.name} (priority={best_vision.priority})")
                except Exception as e:
                    logger.warning(f"Phase-D: Vision model auto-detect failed: {e}")
                
                vision_client = VisionClient(
                    base_url=vision_config.get("base_url", "http://localhost:11434"),
                    model=vision_model,
                    timeout=vision_timeout
                )
                screen_capture = ScreenCapture()
                logger.info(f"Vision client initialized: {vision_model} (Phase-D)")
            except Exception as e:
                logger.error(f"Failed to initialize vision client: {e}")
                logger.warning("Vision observations/verification disabled")
        
        # Initialize Critic with vision fallback support (Phase-3B)
        self.critic = Critic(
            self.accessibility, 
            browser_handler=browser_handler, 
            file_handler=file_handler,
            vision_client=vision_client,
            screen_capture=screen_capture
        )
        self.action_logger = ActionLogger(db_path="db/history.db")
        self.plan_logger = PlanLogger(db_path="db/plans.db")  # Phase-5B
        self.step_approval_logger = StepApprovalLogger(db_path="db/plans.db")  # Phase-6A
        
        self.observer = Observer(
            accessibility_client=self.accessibility,
            browser_handler=browser_handler,
            file_handler=file_handler,
            vision_client=vision_client,
            screen_capture=screen_capture,
            action_logger=self.action_logger
        )
        self.observation_logger = ObservationLogger(db_path="db/observations.db")
        
        # Phase-2: Initialize ExecutionEngine (The new Orchestrator)
        self.execution_engine = ExecutionEngine(
            config=self.config,
            planner=self.planner,
            policy_engine=self.policy_engine,
            controller=self.controller,
            critic=self.critic,
            observer=self.observer,
            action_logger=self.action_logger,
            plan_logger=self.plan_logger,
            step_approval_logger=self.step_approval_logger,
            observation_logger=self.observation_logger,
            llm_client=llm_client,
            chat_ui=self.chat_ui if hasattr(self, 'chat_ui') else None
        )
        
        # Phase-12: Inject DialogueState into Observer
        self.observer.dialogue_state = self.execution_engine.dialogue_state
        
        # Phase-7A: Initialize replay engine
        self.replay_engine = ReplayEngine(
            plan_logger=self.plan_logger,
            step_approval_logger=self.step_approval_logger,
            controller=self.controller,
            critic=self.critic,
            policy_engine=self.policy_engine
        )
        
        # Store handlers for cleanup
        self.browser_handler = browser_handler
        self.file_handler = file_handler
        
        # UI will be initialized separately
        self.chat_ui = None
        self.tray_daemon = None
        
        # Track last action failure reason for accurate logging
        self.last_failure_reason = None
        
        logger.info("All modules initialized successfully")
    
    def _verify_ollama_models(self, llm_config: dict):
        """
        Verify required Ollama models are pulled and available.
        Auto-pulls missing models so the agent never fails silently.
        """
        import subprocess
        
        base_url = llm_config.get("base_url", "http://localhost:11434")
        required_models = [
            llm_config.get("model", "llama3.2"),
        ]
        
        # Also check vision model from config
        vision_config = self.config.get("vision", {})
        vision_model = vision_config.get("model", "llava:7b")
        if vision_model:
            required_models.append(vision_model)
        
        try:
            import requests
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            available = {m["name"] for m in resp.json().get("models", [])}
        except Exception as e:
            logger.warning(f"Could not check Ollama models: {e}")
            return
        
        for model in required_models:
            # Check exact name or name:latest
            if model in available or f"{model}:latest" in available:
                logger.info(f"Ollama model '{model}' is available")
                continue
            
            logger.warning(f"Ollama model '{model}' NOT FOUND — pulling now...")
            try:
                result = subprocess.run(
                    ["ollama", "pull", model],
                    capture_output=True, text=True, timeout=600
                )
                if result.returncode == 0:
                    logger.info(f"Successfully pulled '{model}'")
                else:
                    logger.error(f"Failed to pull '{model}': {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout pulling '{model}' (10 min limit)")
            except FileNotFoundError:
                logger.error("'ollama' command not found — is Ollama installed?")
                break

    def _load_config(self) -> dict:
        """
        Load agent configuration from YAML with pydantic validation.
        
        Returns:
            Configuration dictionary
        """
        try:
            from config.config_validator import load_validated_config
            config = load_validated_config("config/agent_config.yaml")
            logger.info("Loaded and validated configuration")
            return config
        except ValueError as e:
            logger.error(f"Config validation error: {e}")
            logger.warning("Using default configuration")
            return {
                "planner": {"use_llm": False, "max_actions_per_plan": 5},
                "llm": {},
                "fallback": {"on_llm_failure": "abort", "notify_user": True}
            }
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.warning("Using default configuration")
            return {
                "planner": {"use_llm": False, "max_actions_per_plan": 5},
                "llm": {},
                "fallback": {"on_llm_failure": "abort", "notify_user": True}
            }
    
    def execute_instruction(self, instruction: str):
        """
        Execute a natural language instruction.
        Delegates to ExecutionEngine.
        """
        if self.execution_engine:
            self.execution_engine.execute_instruction(instruction)
        else:
            logger.error("Execution engine not initialized")

    def replay_plan_by_id(self, plan_id: int):
        """
        Replay a persisted plan from database.
        
        Phase-7A: Loads plan and executes using ReplayEngine.
        Human-controlled, deterministic replay only.
        
        Args:
            plan_id: ID of plan to replay
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"REPLAY REQUEST: Plan {plan_id}")
        logger.info(f"{'='*60}\n")
        
        try:
            success = self.replay_engine.replay_plan(plan_id)
            
            if success:
                logger.info("Replay completed successfully")
                if self.chat_ui:
                    self.chat_ui.append_message("system", "✅ Replay completed successfully")
            else:
                logger.warning("Replay was aborted or failed")
                if self.chat_ui:
                    self.chat_ui.append_message("system", "❌ Replay aborted or failed")
                    
        except Exception as e:
            logger.error(f"Replay error: {e}")
            if self.chat_ui:
                self.chat_ui.append_message("system", f"❌ Replay error: {e}")
    
    def cleanup(self):
        """Cleanup resources before exit."""
        logger.info("Shutting down...")
        try:
            # Close action logger (SQLite)
            if hasattr(self, 'action_logger') and self.action_logger:
                try:
                    self.action_logger.close()
                    logger.info("Action logger closed")
                except Exception as e:
                    logger.error(f"Error closing action logger: {e}")

            # Close browser handler (Playwright threads)
            if hasattr(self, 'browser_handler') and self.browser_handler:
                try:
                    if hasattr(self.browser_handler, 'close'):
                        self.browser_handler.close()
                    elif hasattr(self.browser_handler, 'cleanup'):
                        self.browser_handler.cleanup()
                    logger.info("Browser handler closed")
                except Exception as e:
                    logger.error(f"Error closing browser handler: {e}")

            # Close observation logger
            if hasattr(self, 'observation_logger') and self.observation_logger:
                try:
                    if hasattr(self.observation_logger, 'close'):
                        self.observation_logger.close()
                    logger.info("Observation logger closed")
                except Exception as e:
                    logger.error(f"Error closing observation logger: {e}")

            # Close plan logger
            if hasattr(self, 'plan_logger') and self.plan_logger:
                try:
                    if hasattr(self.plan_logger, 'close'):
                        self.plan_logger.close()
                    logger.info("Plan logger closed")
                except Exception as e:
                    logger.error(f"Error closing plan logger: {e}")

            logger.info("Agent shutdown complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    import atexit

    # Create QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("My Agent")
    
    # Create agent
    agent = Agent()

    # Register atexit handler as a safety net
    atexit.register(agent.cleanup)
    
    try:
        # Create UI
        chat_ui = ChatUI(on_instruction=agent.execute_instruction)
        agent.chat_ui = chat_ui
        if agent.execution_engine:
            agent.execution_engine.chat_ui = chat_ui
        
        # Create tray daemon
        tray_daemon = TrayDaemon(
            app=app,
            chat_window=chat_ui,
            on_exit=agent.cleanup
        )
        agent.tray_daemon = tray_daemon
        
        # Show chat window initially
        chat_ui.show()
        
        logger.info("Agent is running. System tray icon active.")
        
        # Run the application
        exit_code = app.exec()
    finally:
        agent.cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
