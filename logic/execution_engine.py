"""
Execution Engine - Phase-2 Refactor
Encapsulates the canonical execution loop (PLAN -> POLICY -> ACT -> VERIFY).

Responsible for:
- Orchestrating the execution of plans
- Managing the PLAN -> POLICY CHECKS -> ACT -> VERIFY state machine
- Handling action execution, retries, and verification
- Managing plan approval flows
- Logging execution state
"""
import logging
import re
import json
from typing import Optional, List, Union, Callable, Dict, Any
from datetime import datetime

from common.actions import Action, ActionResult
from common.observations import Observation, ObservationResult
from common.plan_graph import PlanGraph
from logic.dialogue_state import DialogueState, CLARIFICATION_REQUIRED
from logic.intent_resolver import IntentResolver
from logic.intent_types import CanonicalIntent
from logic.response_composer import ResponseComposer
from logic.vision_semantic_interpreter import VisionSemanticInterpreter

logger = logging.getLogger(__name__)

from interface.response_formatter import ResponseFormatter

def safe_log(msg: str) -> str:
    """Sanitize log messages for Windows console (removes unicode that crashes cp1252)."""
    try:
        return msg.encode("cp1252", errors="ignore").decode("cp1252")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return msg.encode("ascii", errors="ignore").decode("ascii")

class ExecutionEngine:
    """
    Core execution engine implementing the reliable agent loop.
    """
    
    def __init__(
        self,
        config: dict,
        planner,
        policy_engine,
        controller,
        critic,
        observer,
        action_logger,
        plan_logger,
        step_approval_logger,
        observation_logger,
        llm_client=None,
        chat_ui=None
    ):
        """
        Initialize the Execution Engine.
        """
        self.config = config
        self.planner = planner
        self.policy_engine = policy_engine
        self.controller = controller
        self.critic = critic
        self.observer = observer
        self.llm_client = llm_client
        
        # Loggers
        self.action_logger = action_logger
        self.plan_logger = plan_logger
        self.step_approval_logger = step_approval_logger
        self.observation_logger = observation_logger
        
        # UI
        self.chat_ui = chat_ui
        
        # State
        self.last_failure_reason = None
        
        # Phase-12: CIL (Conversational Intelligence Layer)
        self.dialogue_state = DialogueState()
        self.intent_resolver = IntentResolver(self.dialogue_state)
        self.response_composer = ResponseComposer()
        self.semantic_interpreter = VisionSemanticInterpreter()
        
        # Extracted modules for cleaner separation
        from logic.market_query_handler import MarketQueryHandler
        from logic.market_display import MarketDisplayEngine
        self.market_display = MarketDisplayEngine(chat_ui=self.chat_ui)
        
        # Phase-2C: Market Memory
        self.market_memory = None
        self.market_store = None
        try:
            from storage.market_analysis_store import MarketAnalysisStore
            from logic.market_memory import MarketMemory
            self.market_store = MarketAnalysisStore()
            self.market_memory = MarketMemory(store=self.market_store)
            logger.info("Market memory initialized")
        except Exception as e:
            logger.warning(f"Market memory initialization failed: {e}")
        
        # Market query handler (uses market_memory)
        self.market_query_handler = MarketQueryHandler(
            market_memory=self.market_memory,
            chat_ui=self.chat_ui,
            llm_client=self.llm_client,
            config=self.config
        ) if self.market_memory else None
        
        # Phase-6A: Scenario Probability Calculator and Resolution Tracker
        self.probability_calculator = None
        self.resolution_store = None
        try:
            from logic.scenario_probability import ScenarioProbabilityCalculator
            from storage.scenario_resolution_store import ScenarioResolutionStore
            self.probability_calculator = ScenarioProbabilityCalculator()
            self.resolution_store = ScenarioResolutionStore()
            logger.info("Phase-6A: Probability calculator and resolution tracker initialized")
        except Exception as e:
            logger.warning(f"Phase-6A initialization failed: {e}")
        
        # Phase-7A: Execution Gate and Logger
        self.execution_gate = None
        self.gate_logger = None
        try:
            from logic.execution_gate import ExecutionGate
            from storage.execution_gate_logger import ExecutionGateLogger
            self.execution_gate = ExecutionGate()
            self.gate_logger = ExecutionGateLogger()
            logger.info("Phase-7A: Execution gate and logger initialized")
        except Exception as e:
            logger.warning(f"Phase-7A initialization failed: {e}")
        
        # Phase-X: Human Summary Engine (Translation Layer)
        self.human_summary = None
        try:
            from logic.human_summary_engine import HumanSummaryEngine
            self.human_summary = HumanSummaryEngine()
            logger.info("Phase-X: Human Summary Engine initialized")
        except Exception as e:
            logger.warning(f"Phase-X initialization failed: {e}")
        
        # Phase-11: Signal Eligibility Engine (Read-Only Signals)
        self.signal_eligibility = None
        try:
            from logic.signal_eligibility import SignalEligibilityEngine
            self.signal_eligibility = SignalEligibilityEngine()
            logger.info("Phase-11: Signal Eligibility Engine initialized")
        except Exception as e:
            logger.warning(f"Phase-11 initialization failed: {e}")
        
        # Phase-11.5G: Symbol Resolver (3-layer resolution system)
        self.symbol_resolver = None
        try:
            from logic.symbol_resolver import SymbolResolver
            self.symbol_resolver = SymbolResolver(
                tradingview_client=None,  # Will be set lazily
                llm_client=self.llm_client
            )
            logger.info("Phase-11.5G: Symbol Resolver initialized")
        except Exception as e:
            logger.warning(f"Symbol Resolver initialization failed: {e}")
        
        # Phase-14: News/Catalyst Intelligence
        self.news_client = None
        try:
            from perception.news_client import NewsClient
            _browser = getattr(self.controller, 'browser_handler', None) if self.controller else None
            self.news_client = NewsClient(
                browser_handler=_browser,
                llm_client=self.llm_client
            )
            logger.info("Phase-14: News/Catalyst client initialized")
        except Exception as e:
            logger.warning(f"News client initialization failed: {e}")
        
        # Phase-2B: TradingView client (singleton per agent lifetime)
        self.tradingview_client = None
        
        # Backward compatibility / Injection for Observer if needed
        # We allow Observer to pull from DialogueState if we wire it up correctly later.
        if hasattr(self.observer, 'followup_resolver'):
             # Replace the old resolver reference in Observer with our DialogueState shim if compatible
             # OR just keep it None and rely on passed arguments.
             if hasattr(self.observer, 'set_dialogue_state'):
                 self.observer.set_dialogue_state(self.dialogue_state)
        
        logger.info("ExecutionEngine initialized")

    def _handle_observation_intent(self, instruction: str):
        """Shielded execution for OBSERVE_SCREEN intent."""
        logger.info("Handling Shielded Observation Intent")
        
        # Phase-2C: Check if it's a market chat query (no browser needed)
        if self._is_market_chat_query(instruction):
            self._handle_market_chat_query(instruction)
            return
        
        # Check if it's a market analysis request (needs browser)
        observation = self._detect_direct_observation(instruction)
        if observation and observation.context == "vision" and "chart" in instruction.lower():
            # Handle market analysis specially
            self._handle_market_analysis_intent(instruction)
            return
        
        # Determine observation type (Phase-11 logic maps to 'vision' or 'check_app')
        # We can reuse the logic from _detect_direct_observation but simplify it
        obs_type = "vision"
        if "check if" in instruction or "is " in instruction:
             # Very simple heuristic for app state check reuse
             # But for now, let's default to vision for "what do you see"
             pass

        # Create Observation Object
        if not observation:
            observation = Observation(
                observation_type=obs_type,
                context="vision", # Default to vision for CIL
                target=instruction
            )
        
        try:
            result = self.observer.observe(observation)
            
            # Phase-12: Update Dialogue State
            if result.status == "success":
                self.dialogue_state.update_observation(result)

            # Phase-UI-A/C: Use ResponseComposer
            formatted_response = self.response_composer.compose_observation_response(result)
            
            # Log to observation db
            self.observation_logger.log_observation(result)
            
            # Send to UI if available
            if self.chat_ui:
                self.chat_ui.log(formatted_response, "OBSERVATION")
            else:
                logger.info(f"Observation Result: {formatted_response}")
                
        except Exception as e:
            logger.error(f"Shielded observation failed: {e}")
            if self.chat_ui:
                self.chat_ui.log(f"Observation failed: {e}", "ERROR")
    
    def _handle_market_analysis_intent(self, instruction: str):
        """
        Phase-2B: Handle market analysis workflow.
        
        Supports both single timeframe and multi-timeframe analysis (MTF).
        
        MTF Workflow (if "multi-timeframe" or "MTF" detected):
        1. Analyze Monthly (1M) → Weekly (1W) → Daily (1D) sequentially
        2. Each timeframe gets independent assessment
        3. Display consolidated results
        
        Single Timeframe Workflow:
        1. Extract symbol and timeframe from instruction
        2. Navigate to TradingView chart
        3. Extract DOM data + vision observation
        4. Synthesize with LLM
        5. Display formatted analysis
        """
        logger.info("Handling Market Analysis Intent")
        
        if self.chat_ui:
            self.chat_ui.log("Starting market analysis...", "INFO")
            self.chat_ui.set_status("Analyzing")
        
        try:
            # Import here to avoid circular dependencies
            from perception.tradingview_client import TradingViewClient
            from logic.technical_analyzer import TechnicalAnalyzer
            
            # Validate safety constraints
            ma_config = self.config.get("market_analysis", {})
            if not ma_config.get("enabled", False):
                raise ValueError("Market analysis is disabled in config")
            
            safety = ma_config.get("safety", {})
            if safety.get("allow_trading", False):
                raise ValueError("SAFETY VIOLATION: Trading is not allowed in read-only mode")
            
            # Extract symbol from instruction
            symbol = self._extract_symbol_from_instruction(instruction)
            if not symbol:
                # No clear symbol found - search Google to understand what user is asking about
                logger.info(f"No clear symbol in instruction. Searching for: {instruction}")
                if self.chat_ui:
                    self.chat_ui.log(f"Searching for stock symbol in: {instruction}", "INFO")
                
                symbol = self._search_correct_symbol(instruction)
                
                if not symbol:
                    if self.chat_ui:
                        self.chat_ui.log("Could not identify stock symbol. Please specify a symbol (e.g., TCS, RELIANCE, NIFTY)", "ERROR")
                    return
                
                logger.info(f"Found symbol from search: {symbol}")
                if self.chat_ui:
                    self.chat_ui.log(f"Identified symbol: {symbol}", "SUCCESS")
            
            logger.info(f"Analyzing symbol: {symbol}")
            
            # Validate symbol upfront with Google search if needed
            # Use full instruction context for better search results
            validated_symbol = self._validate_and_correct_symbol(symbol, instruction)
            if not validated_symbol:
                if self.chat_ui:
                    self.chat_ui.log(f"Could not find valid symbol for '{symbol}'", "ERROR")
                    self.chat_ui.set_status("Idle")
                return
            
            # Use validated symbol for all analysis
            symbol = validated_symbol
            logger.info(f"Using validated symbol: {symbol}")
            
            # Detect reasoning-only synthesis (Phase-3 from stored data)
            instruction_lower = instruction.lower()
            is_reasoning = any(keyword in instruction_lower for keyword in ["reasoning", "synthesize", "synthesis", "phase-3", "stored"])
            
            if is_reasoning:
                # Reasoning-only: Use stored data without new observations
                self._synthesize_mtf_from_stored(symbol)
                return
            
            # Detect single-timeframe request (explicit keyword)
            is_single_tf = any(keyword in instruction_lower for keyword in ["single", "single-timeframe", "only daily", "only weekly", "only monthly", "phase-3"])
            
            if is_single_tf:
                # Single timeframe analysis (Phase-3 only)
                timeframe = self._extract_timeframe_from_instruction(instruction)
                logger.info(f"Single timeframe analysis: {timeframe}")
                
                if self.chat_ui:
                    self.chat_ui.log(f"Analyzing {symbol} ({timeframe} timeframe only)...", "INFO")
                
                # Perform single timeframe analysis
                self._analyze_single_timeframe_and_display(symbol, timeframe)
                return
            
            # DEFAULT: Multi-timeframe analysis (Phase-4 + Phase-5)
            # This runs for ALL "analyze [SYMBOL]" requests
            logger.info(f"Executing multi-timeframe analysis (Phase-4 + Phase-5)")
            if self.chat_ui:
                self.chat_ui.log(f"Starting multi-timeframe analysis: {symbol}", "INFO")
            
            self._perform_mtf_analysis(symbol)
            
        except Exception as e:
            logger.error(f"Market analysis failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"Market analysis failed: {e}", "ERROR")
                self.chat_ui.set_status("Idle")
    
    def _perform_mtf_analysis(self, symbol: str):
        """
        Perform multi-timeframe analysis: Monthly → Weekly → Daily.
        
        Args:
            symbol: Stock symbol to analyze
        """
        logger.info(f"Starting multi-timeframe analysis for {symbol}")
        
        if self.chat_ui:
            self.chat_ui.log(f"🔄 **Multi-Timeframe Analysis: {symbol}**", "INFO")
            self.chat_ui.log("Analyzing across Monthly → Weekly → Daily timeframes...", "INFO")
        
        # Timeframes to analyze in order
        timeframes = [
            ("1M", "monthly"),
            ("1W", "weekly"),
            ("1D", "daily")
        ]
        
        mtf_results = []
        
        for tf_code, tf_name in timeframes:
            try:
                logger.info(f"Analyzing {symbol} on {tf_name} timeframe ({tf_code})")
                
                if self.chat_ui:
                    self.chat_ui.log(f"\n📊 **Analyzing {tf_name.upper()} timeframe...**", "INFO")
                
                # Perform single timeframe analysis
                analysis_result = self._analyze_single_timeframe(symbol, tf_code)
                
                if analysis_result:
                    mtf_results.append({
                        "timeframe": tf_name,
                        "code": tf_code,
                        "analysis": analysis_result
                    })
                    
                    if self.chat_ui:
                        self.chat_ui.log(f"✅ {tf_name.capitalize()} analysis complete", "SUCCESS")
                else:
                    if self.chat_ui:
                        self.chat_ui.log(f"⚠️ {tf_name.capitalize()} analysis failed", "WARNING")
                
            except Exception as e:
                logger.error(f"Failed to analyze {tf_name} timeframe: {e}", exc_info=True)
                if self.chat_ui:
                    self.chat_ui.log(f"❌ {tf_name.capitalize()} analysis error: {e}", "ERROR")
        
        # Display consolidated MTF summary
        if mtf_results:
            self._display_mtf_summary(symbol, mtf_results)
        
        if self.chat_ui:
            self.chat_ui.set_status("Idle")
    
    def _handle_market_scan_intent(self, instruction: str):
        """
        Phase-11.5: Handle market scanner workflow.
        
        Supports multi-instrument scanning with Phase-4→11 pipeline per instrument.
        
        Examples:
        - "scan bank nifty" -> 12 bank stocks
        - "scan nifty 50 stocks" -> 50 stocks
        - "scan bank nifty ce pe" -> 10 option contracts
        - "scan yesbank,kotakbank,sbin" -> 3 specific stocks
        """
        logger.info("Handling Market Scan Intent (Phase-11.5)")
        
        if self.chat_ui:
            self.chat_ui.log("Starting market scan...", "INFO")
            self.chat_ui.set_status("Scanning")
        
        try:
            from logic.market_scanner import MarketScanner, ScanRequest
            from logic.scan_scheduler import ScanMode
            
            # Initialize scanner (singleton pattern)
            if not hasattr(self, 'market_scanner'):
                self.market_scanner = MarketScanner(self)
                logger.info("Phase-11.5: Market Scanner initialized")
            
            # Parse scan request from instruction
            # Extract scope (everything except timeframe keywords)
            instruction_lower = instruction.lower()
            
            # Determine timeframe mode
            scan_mode = ScanMode.SWING  # Default
            if any(kw in instruction_lower for kw in ["intraday", "15m", "1h", "4h"]):
                scan_mode = ScanMode.INTRADAY
            elif any(kw in instruction_lower for kw in ["positional", "monthly", "long term"]):
                scan_mode = ScanMode.POSITIONAL
            
            # Extract scope (remove common command words)
            scope = instruction
            for remove_word in ["scan", "market", "intraday", "swing", "positional"]:
                scope = re.sub(rf"\\b{remove_word}\\b", "", scope, flags=re.IGNORECASE)
            scope = scope.strip()
            
            if not scope:
                if self.chat_ui:
                    self.chat_ui.log("Please specify what to scan (e.g., 'scan bank nifty', 'scan nifty 50')", "ERROR")
                    self.chat_ui.set_status("Idle")
                return
            
            logger.info(f"Scan scope: {scope}, mode: {scan_mode.value}")
            
            # CRITICAL: Initialize TradingView client before health check
            if not self.tradingview_client:
                # Ensure browser is available
                if not hasattr(self.controller, 'browser_handler') or not self.controller.browser_handler:
                    if self.chat_ui:
                        self.chat_ui.log("Browser not available for scan", "ERROR")
                        self.chat_ui.set_status("Idle")
                    logger.error("Browser handler not available, aborting scan")
                    return
                
                browser_handler = self.controller.browser_handler
                browser_handler._ensure_browser()
                
                from perception.tradingview_client import TradingViewClient
                self.tradingview_client = TradingViewClient(self.config, browser_handler)
                logger.info("TradingView client initialized for scan")
            
            # CRITICAL: TradingView health check before scan
            if self.symbol_resolver:
                if self.chat_ui:
                    self.chat_ui.log("Checking market data source...", "INFO")
                
                # Set TradingView client in resolver
                self.symbol_resolver.tradingview_client = self.tradingview_client
                
                if not self.symbol_resolver.health_check():
                    if self.chat_ui:
                        self.chat_ui.log("❌ Market data source unavailable. Scan aborted.", "ERROR")
                        self.chat_ui.set_status("Idle")
                    logger.error("TradingView health check failed, aborting scan")
                    return
                
                if self.chat_ui:
                    self.chat_ui.log("✓ Market data source available", "SUCCESS")
            
            # Create scan request
            scan_request = ScanRequest(
                scope=scope,
                timeframe=scan_mode,
                max_results=5,  # Top 5 signals
                strict_mode=True  # Enforce signal rarity
            )
            
            # Execute scan
            if self.chat_ui:
                self.chat_ui.log(f"\\n🔍 **Scanning: {scope}**", "INFO")
                self.chat_ui.log(f"Mode: {scan_mode.value}", "INFO")
                self.chat_ui.log("Running Phase-4→11 pipeline per instrument...", "INFO")
                self.chat_ui.log("(This may take several minutes)\\n", "WARNING")
            
            results = self.market_scanner.scan_market(scan_request)
            
            # Display results
            if results["success"]:
                if self.chat_ui:
                    # Display formatted report
                    for line in results["report"].split('\\n'):
                        if line.startswith("====") or line.startswith("----"):
                            self.chat_ui.log(line, "INFO")
                        elif "✅" in line or "PASS" in line:
                            self.chat_ui.log(line, "SUCCESS")
                        elif "⚠️" in line or "WARNING" in line:
                            self.chat_ui.log(line, "WARNING")
                        elif "❌" in line or "ERROR" in line or "FAILED" in line:
                            self.chat_ui.log(line, "ERROR")
                        else:
                            self.chat_ui.log(line, "INFO")
                    
                    # Summary
                    self.chat_ui.log("\\n" + "="*70, "INFO")
                    self.chat_ui.log(f"✓ Scan completed: {results['total_scanned']} instruments", "SUCCESS")
                    self.chat_ui.log(f"✓ Eligible signals: {results['eligible_count']}", "SUCCESS")
                    self.chat_ui.log(f"✓ Top signals: {results['top_signals_count']}", "SUCCESS")
                    self.chat_ui.log("="*70, "INFO")
                    
                    self.chat_ui.set_status("Idle")
            else:
                error_msg = results.get("error", "Unknown error")
                if self.chat_ui:
                    self.chat_ui.log(f"❌ Scan failed: {error_msg}", "ERROR")
                    self.chat_ui.set_status("Idle")
                logger.error(f"Market scan failed: {error_msg}")
        
        except Exception as e:
            logger.error(f"Market scan failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"Market scan failed: {e}", "ERROR")
                self.chat_ui.set_status("Idle")
    
    def _synthesize_mtf_from_stored(self, symbol: str):
        """
        Phase-3 Reasoning Task: Synthesize MTF analysis from stored data.
        
        Retrieves most recent Monthly, Weekly, Daily analyses from database
        and performs reasoning synthesis without new observations.
        
        Args:
            symbol: Stock symbol to synthesize
        """
        logger.info(f"[REASONING] Synthesizing MTF analysis from stored data for {symbol}")
        
        if self.chat_ui:
            self.chat_ui.log(f"🧠 **Phase-3 Reasoning: {symbol}**", "INFO")
            self.chat_ui.log("Synthesizing multi-timeframe analysis from stored data...", "INFO")
            self.chat_ui.log("(No new charts fetched, reasoning-only)", "WARNING")
        
        try:
            if not self.market_store:
                raise ValueError("MarketAnalysisStore not available")
            
            # Retrieve stored analyses (only from last 24 hours - same day data only)
            # For intraday: use 1 hour; for daily: use 24 hours
            MAX_AGE_HOURS = 24  # Same-day data only
            
            monthly_analysis = self.market_store.get_latest_analysis(symbol, "1M", max_age_hours=MAX_AGE_HOURS)
            weekly_analysis = self.market_store.get_latest_analysis(symbol, "1W", max_age_hours=MAX_AGE_HOURS)
            daily_analysis = self.market_store.get_latest_analysis(symbol, "1D", max_age_hours=MAX_AGE_HOURS)
            
            if not all([monthly_analysis, weekly_analysis, daily_analysis]):
                missing = []
                if not monthly_analysis:
                    missing.append("Monthly (1M)")
                if not weekly_analysis:
                    missing.append("Weekly (1W)")
                if not daily_analysis:
                    missing.append("Daily (1D)")
                
                msg = f"Insufficient stored data from last {MAX_AGE_HOURS} hours. Missing: {', '.join(missing)}"
                if self.chat_ui:
                    self.chat_ui.log(msg, "ERROR")
                    self.chat_ui.log(f"Data must be from same day (within {MAX_AGE_HOURS} hours).", "WARNING")
                    self.chat_ui.log("Run full MTF analysis first: 'Analyze [SYMBOL] multi-timeframe'", "INFO")
                logger.warning(msg)
                return
            
            # Validate and log retrieval timestamps
            from datetime import datetime, timedelta
            
            if self.chat_ui:
                now = datetime.now()
                
                for analysis, tf_name in [(monthly_analysis, "Monthly"), (weekly_analysis, "Weekly"), (daily_analysis, "Daily")]:
                    timestamp_str = analysis.get('timestamp', 'N/A')
                    if timestamp_str != 'N/A':
                        analysis_time = datetime.fromisoformat(timestamp_str)
                        age_hours = (now - analysis_time).total_seconds() / 3600
                        age_str = f"{age_hours:.1f}h ago" if age_hours < 24 else f"{age_hours/24:.1f} days ago"
                        self.chat_ui.log(f"✓ Retrieved {tf_name} analysis from {timestamp_str} ({age_str})", "SUCCESS")
                    else:
                        self.chat_ui.log(f"✓ Retrieved {tf_name} analysis from {timestamp_str}", "SUCCESS")
                
                self.chat_ui.log(f"✓ All data is from last {MAX_AGE_HOURS} hours (same-day requirement)", "SUCCESS")
                self.chat_ui.log("", "INFO")
            
            # Build MTF results structure
            mtf_results = [
                {"timeframe": "monthly", "code": "1M", "analysis": monthly_analysis},
                {"timeframe": "weekly", "code": "1W", "analysis": weekly_analysis},
                {"timeframe": "daily", "code": "1D", "analysis": daily_analysis}
            ]
            
            # Display synthesized MTF summary
            self._display_mtf_summary(symbol, mtf_results)
            
            if self.chat_ui:
                self.chat_ui.log("\n✓ Reasoning synthesis complete", "SUCCESS")
        
        except Exception as e:
            logger.error(f"MTF reasoning synthesis failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"Synthesis failed: {e}", "ERROR")
    
    def _analyze_single_timeframe(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single timeframe (reusable for both single and MTF analysis).
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe code (1M, 1W, 1D, etc.)
            
        Returns:
            Analysis dictionary or None if failed
        """
        try:
            from perception.tradingview_client import TradingViewClient
            from logic.technical_analyzer import TechnicalAnalyzer
            
            # Check browser availability
            if not hasattr(self.controller, 'browser_handler') or not self.controller.browser_handler:
                logger.error("Browser handler not available")
                return None
            
            browser_handler = self.controller.browser_handler
            browser_handler._ensure_browser()
            
            # Initialize TradingViewClient if needed
            if not self.tradingview_client:
                self.tradingview_client = TradingViewClient(self.config, browser_handler)
                logger.info("TradingViewClient initialized (singleton)")
            
            tv_client = self.tradingview_client
            
            # Navigate to chart with specific timeframe
            nav_result = tv_client.navigate_to_chart(symbol, timeframe=timeframe)
            if nav_result.get("status") != "success":
                logger.error(f"Chart navigation failed: {nav_result.get('error')}")
                return None
            
            # Extract DOM data
            dom_data = tv_client.extract_chart_data()
            
            # Symbol should already be validated, but check data extraction
            if dom_data.get('symbol') is None and dom_data.get('price') is None:
                logger.error(f"Chart data extraction failed for {symbol} ({timeframe})")
                return None
            
            # Get vision observation
            # Pass timeframe into observation target so VLM prompt can reference it
            tf_label_map = {"1M": "Monthly", "1W": "Weekly", "1D": "Daily", "60": "Hourly", "4h": "4-Hour", "15": "15-Minute"}
            tf_label = tf_label_map.get(timeframe, timeframe)
            observation = Observation(
                observation_type="vision",
                context="vision",
                target=f"Analyze {symbol} {tf_label} chart for trend, support/resistance, momentum, volume, and candlestick patterns"
            )
            
            vision_result = self.observer.observe(observation)
            vision_observation = None
            if vision_result.status == "success":
                vision_observation = vision_result.result
            
            # Synthesize analysis
            if not self.llm_client:
                logger.error("LLM client not available")
                return None
            
            analyzer = TechnicalAnalyzer(self.config, self.llm_client, market_store=self.market_store)
            analysis = analyzer.analyze(dom_data, vision_observation)
            
            # Validate safety
            if not analyzer.validate_analysis(analysis):
                logger.warning("Analysis failed safety validation")
                return None
            
            return analysis
            
        except Exception as e:
            logger.error(f"Single timeframe analysis failed: {e}", exc_info=True)
            return None
    
    def analyze_instrument_for_scan(self, symbol: str, timeframe_mode: str = "SWING") -> Optional[Any]:
        """
        Phase-11.5: Analyze single instrument for market scanner.
        Runs Phase-4→5→6A→7A→X→11 pipeline for one symbol.
        
        READ-ONLY. No UI display. Returns SignalContract only.
        
        Args:
            symbol: Stock symbol to analyze
            timeframe_mode: INTRADAY / SWING / POSITIONAL
        
        Returns:
            SignalContract from Phase-11 (or None if failed)
        """
        logger.info(f"[SCANNER] Analyzing {symbol} (mode={timeframe_mode})")
        
        try:
            # Map timeframe mode to actual timeframes
            if timeframe_mode == "INTRADAY":
                timeframes = [("1h", "hourly"), ("15", "15min"), ("4h", "4hour")]
            elif timeframe_mode == "POSITIONAL":
                timeframes = [("1M", "monthly"), ("1W", "weekly")]
            else:  # SWING (default)
                timeframes = [("1M", "monthly"), ("1W", "weekly"), ("1D", "daily")]
            
            # Step 1: Validate symbol (MARKET_SCAN mode - no Google)
            if self.symbol_resolver:
                # Ensure TradingView client is available
                if not self.symbol_resolver.tradingview_client and self.tradingview_client:
                    self.symbol_resolver.tradingview_client = self.tradingview_client
                
                from logic.symbol_resolver import ResolutionMode, ResolutionStatus
                
                result = self.symbol_resolver.resolve(
                    user_input=symbol,
                    mode=ResolutionMode.MARKET_SCAN,  # Scanner mode - NO GOOGLE
                    context=None
                )
                
                if result.status == ResolutionStatus.DATA_UNAVAILABLE:
                    logger.warning(f"[SCANNER] TradingView data unavailable for {symbol}")
                    return None  # Return None but scanner continues
                elif result.status in [ResolutionStatus.VALID, ResolutionStatus.RESOLVED]:
                    symbol = result.symbol
                else:
                    logger.warning(f"[SCANNER] Symbol resolution failed: {symbol}")
                    return None
            else:
                logger.warning(f"[SCANNER] Symbol resolver not available for {symbol}")
            
            # Step 2: Fetch data for each timeframe (Phase-4)
            mtf_results = []
            for tf_code, tf_name in timeframes:
                try:
                    analysis_result = self._analyze_single_timeframe(symbol, tf_code)
                    if analysis_result:
                        mtf_results.append({
                            "timeframe": tf_name,
                            "code": tf_code,
                            "analysis": analysis_result
                        })
                except Exception as tf_err:
                    logger.warning(f"[SCANNER] {symbol} {tf_name} failed: {tf_err}")
                    # Continue to next timeframe
            
            if not mtf_results:
                logger.warning(f"[SCANNER] No valid timeframes for {symbol}")
                return None
            
            # Step 3: Extract analysis data
            monthly_data = next((r for r in mtf_results if r["code"] == "1M"), None)
            weekly_data = next((r for r in mtf_results if r["code"] == "1W"), None)
            daily_data = next((r for r in mtf_results if r["code"] == "1D"), None)
            
            # Use available data (may not have all three for INTRADAY mode)
            monthly_analysis = monthly_data["analysis"] if monthly_data else {}
            weekly_analysis = weekly_data["analysis"] if weekly_data else {}
            daily_analysis = daily_data["analysis"] if daily_data else {}
            
            monthly_trend = monthly_analysis.get("trend", "unknown")
            weekly_trend = weekly_analysis.get("trend", "unknown")
            daily_trend = daily_analysis.get("trend", "unknown")
            
            monthly_momentum = monthly_analysis.get("momentum", "unknown")
            weekly_momentum = weekly_analysis.get("momentum", "unknown")
            daily_momentum = daily_analysis.get("momentum", "unknown")
            
            # Step 4: Classify alignment (Phase-5)
            alignment, dominant_tf, conflicts, is_unstable = self._classify_mtf_alignment(
                monthly_trend.lower(), weekly_trend.lower(), daily_trend.lower(),
                monthly_momentum.lower(), weekly_momentum.lower(), daily_momentum.lower(),
                monthly_data, daily_data
            )
            
            # Extract support/resistance
            monthly_support = monthly_analysis.get("support_levels", [])
            monthly_resistance = monthly_analysis.get("resistance_levels", [])
            weekly_support = weekly_analysis.get("support_levels", [])
            weekly_resistance = weekly_analysis.get("resistance_levels", [])
            current_price = daily_analysis.get("price", 0) or monthly_analysis.get("price", 0)
            
            # Determine HTF location
            htf_location = "MID"
            if monthly_resistance and current_price >= monthly_resistance[0] * 0.98:
                htf_location = "RESISTANCE"
            elif monthly_support and current_price <= monthly_support[0] * 1.02:
                htf_location = "SUPPORT"
            
            # Step 5: Calculate probabilities (Phase-6A)
            probability_result = None
            active_state = "Unknown"
            gate_status = "UNKNOWN"
            
            if self.probability_calculator:
                try:
                    probability_result = self.probability_calculator.calculate_scenario_probabilities(
                        alignment=alignment,
                        is_unstable=is_unstable,
                        monthly_trend=monthly_trend,
                        htf_location=htf_location,
                        current_price=current_price,
                        monthly_support=monthly_support,
                        monthly_resistance=monthly_resistance
                    )
                    active_state = probability_result.get("active_state", "Unknown")
                except Exception as prob_err:
                    logger.warning(f"[SCANNER] {symbol} probability calculation failed: {prob_err}")
            
            # Step 6: Evaluate execution gate (Phase-7A)
            gate_evaluation = None
            if self.execution_gate and probability_result:
                try:
                    gate_evaluation = self.execution_gate.evaluate(
                        symbol=symbol,
                        alignment=alignment,
                        is_unstable=is_unstable,
                        probabilities=probability_result["scenario_probabilities"],
                        active_state=active_state,
                        current_price=current_price,
                        monthly_support=monthly_support,
                        monthly_resistance=monthly_resistance,
                        monthly_trend=monthly_trend
                    )
                    gate_status = gate_evaluation["execution_permission"].get("status", "BLOCKED")
                except Exception as gate_err:
                    logger.warning(f"[SCANNER] {symbol} gate evaluation failed: {gate_err}")
            
            # Step 7: Generate human summary (Phase-X)
            summary = None
            if self.human_summary:
                try:
                    # Map to strict API format
                    alignment_map = {
                        "FULL ALIGNMENT": "FULL",
                        "PARTIAL ALIGNMENT": "PARTIAL",
                        "UNSTABLE": "UNSTABLE",
                        "CONFLICT": "CONFLICT"
                    }
                    strict_alignment = alignment_map.get(alignment, "CONFLICT")
                    
                    # Map active state
                    active_state_str = active_state.replace(" ", "_").upper()
                    if active_state_str not in ["CONTINUATION", "PULLBACK", "REVERSAL"]:
                        active_state_str = "CONTINUATION"  # Default
                    
                    # Map gate status
                    gate_status_str = "BLOCKED"
                    if gate_evaluation and gate_evaluation["execution_permission"].get("status") == "ALLOWED":
                        gate_status_str = "PASS"
                    
                    # Map HTF location
                    htf_location_str = "MID"
                    if "resistance" in htf_location.lower():
                        htf_location_str = "RESISTANCE"
                    elif "support" in htf_location.lower():
                        htf_location_str = "SUPPORT"
                    
                    # Map trend
                    trend_mapping = {
                        "bullish": "UP",
                        "bearish": "DOWN",
                        "sideways": "RANGE",
                        "unknown": "RANGE"
                    }
                    trend_str = trend_mapping.get(monthly_trend.lower(), "RANGE")
                    
                    regime_flags_set = set()
                    
                    summary = self.human_summary.generate(
                        alignment_state=strict_alignment,
                        active_state=active_state_str,
                        execution_gate_status=gate_status_str,
                        regime_flags=regime_flags_set,
                        htf_location=htf_location_str,
                        trend_state=trend_str
                    )
                except Exception as summary_err:
                    logger.warning(f"[SCANNER] {symbol} human summary failed: {summary_err}")
            
            # Step 8: Evaluate signal eligibility (Phase-11)
            signal = None
            if self.signal_eligibility and summary:
                try:
                    signal = self.signal_eligibility.evaluate_signal(
                        verdict=summary["verdict"],
                        confidence=summary["confidence"],
                        summary=summary["summary"],
                        alignment_state=alignment,
                        htf_location=htf_location,
                        trend_state=monthly_trend,
                        active_scenario=active_state,
                        execution_gate_status=gate_status
                    )
                    logger.info(f"[SCANNER] {symbol} → {signal.signal_status.value}")
                except Exception as signal_err:
                    logger.warning(f"[SCANNER] {symbol} signal evaluation failed: {signal_err}")
            
            return signal
            
        except Exception as e:
            logger.error(f"[SCANNER] {symbol} analysis failed: {e}", exc_info=True)
            return None
    
    def _display_mtf_summary(self, symbol: str, mtf_results: List[Dict[str, Any]]):
        """
        Display consolidated multi-timeframe analysis in structured report format.
        
        Args:
            symbol: Stock symbol
            mtf_results: List of analysis results per timeframe
        """
        if not self.chat_ui:
            return
        
        try:
            # Initialize variables to prevent UnboundLocalError (Phase-6A deterministic requirement)
            htf_location = "UNKNOWN"
            ltf_extension = "UNKNOWN"
            alignment = "UNKNOWN"
            trend = "UNKNOWN"
            gate_evaluation = None
            
            # Extract timeframe data
            monthly_data = next((r for r in mtf_results if r["code"] == "1M"), None)
            weekly_data = next((r for r in mtf_results if r["code"] == "1W"), None)
            daily_data = next((r for r in mtf_results if r["code"] == "1D"), None)
            
            monthly_analysis = monthly_data["analysis"] if monthly_data else {}
            weekly_analysis = weekly_data["analysis"] if weekly_data else {}
            daily_analysis = daily_data["analysis"] if daily_data else {}
            
            monthly_trend = monthly_analysis.get("trend", "unknown")
            monthly_structure = monthly_analysis.get("structure", "unknown")
            monthly_momentum = monthly_analysis.get("momentum", "unknown")
            
            weekly_trend = weekly_analysis.get("trend", "unknown")
            weekly_structure = weekly_analysis.get("structure", "unknown")
            weekly_momentum = weekly_analysis.get("momentum", "unknown")
            
            daily_trend = daily_analysis.get("trend", "unknown")
            daily_structure = daily_analysis.get("structure", "unknown")
            daily_momentum = daily_analysis.get("momentum", "unknown")
            
            # Classify alignment
            alignment, dominant_tf, conflicts, is_unstable = self._classify_mtf_alignment(
                monthly_trend.lower(), weekly_trend.lower(), daily_trend.lower(),
                monthly_momentum.lower(), weekly_momentum.lower(), daily_momentum.lower(),
                monthly_data, daily_data
            )
            
            # HEADER
            self.chat_ui.log(f"\n{'='*70}", "SUCCESS")
            self.chat_ui.log(f"MARKET: {symbol}", "SUCCESS")
            self.chat_ui.log(f"MODE: Multi-Timeframe Scenario Analysis", "SUCCESS")
            self.chat_ui.log(f"TIMEFRAMES ANALYZED: Monthly, Weekly, Daily", "SUCCESS")
            self.chat_ui.log(f"{'='*70}\n", "SUCCESS")
            
            # 1. TIMEFRAME SUMMARY
            self.chat_ui.log("**1. TIMEFRAME SUMMARY**\n", "INFO")
            
            # Phase-15: Enhanced display with volume and candlestick info
            for tf_label, tf_analysis in [("Monthly", monthly_analysis), ("Weekly", weekly_analysis), ("Daily", daily_analysis)]:
                trend_val = tf_analysis.get("trend", "unknown")
                struct_val = tf_analysis.get("structure", "unknown")
                mom_val = tf_analysis.get("momentum", "unknown")
                mom_cond = tf_analysis.get("momentum_condition", "")
                vol_trend = tf_analysis.get("volume_trend", "")
                candle_pat = tf_analysis.get("candlestick_pattern", "")
                
                line = f"  * **{tf_label}:** {trend_val} / {struct_val} / {mom_val}"
                if mom_cond and mom_cond != "neutral":
                    line += f" ({mom_cond})"
                if vol_trend and vol_trend not in ("unavailable", ""):
                    line += f" | Vol: {vol_trend}"
                if candle_pat and candle_pat.lower() not in ("none", ""):
                    line += f" | Pattern: {candle_pat}"
                
                # Phase-16: Show perception confidence and conflicts
                p_conf = tf_analysis.get("_perception_confidence")
                p_conflicts = tf_analysis.get("_perception_conflicts", 0)
                if p_conf is not None:
                    conf_label = "HIGH" if p_conf >= 0.75 else "MED" if p_conf >= 0.50 else "LOW"
                    line += f" [P:{conf_label}]"
                    if p_conflicts > 0:
                        line += f" [{p_conflicts} conflict{'s' if p_conflicts > 1 else ''}]"
                
                self.chat_ui.log(line, "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # 2. ALIGNMENT STATUS
            self.chat_ui.log("**2. ALIGNMENT STATUS**\n", "INFO")
            self.chat_ui.log(f"  • **Dominant Trend:** {dominant_tf}", "INFO")
            self.chat_ui.log(f"  • **Alignment:** {alignment}", "WARNING" if alignment in ["CONFLICT", "UNSTABLE"] else "SUCCESS")
            
            if conflicts:
                self.chat_ui.log(f"  • **Key Conflicts:**", "WARNING")
                for conflict in conflicts:
                    self.chat_ui.log(f"      - {conflict}", "WARNING")
            else:
                self.chat_ui.log(f"  • **Key Conflict:** None - timeframes aligned", "SUCCESS")
            
            self.chat_ui.log("", "INFO")
            
            # 3. KEY ZONES (NON-ACTIONABLE)
            self.chat_ui.log("**3. KEY ZONES (NON-ACTIONABLE)**\n", "INFO")
            
            # Collect all support/resistance
            monthly_support = monthly_analysis.get("support", [])
            monthly_resistance = monthly_analysis.get("resistance", [])
            weekly_support = weekly_analysis.get("support", [])
            weekly_resistance = weekly_analysis.get("resistance", [])
            daily_support = daily_analysis.get("support", [])
            daily_resistance = daily_analysis.get("resistance", [])
            
            # DEBUG: Log what we got
            logger.info(f"MTF Summary - Monthly S/R: {monthly_support} / {monthly_resistance}")
            logger.info(f"MTF Summary - Weekly S/R: {weekly_support} / {weekly_resistance}")
            logger.info(f"MTF Summary - Daily S/R: {daily_support} / {daily_resistance}")
            
            # Get current price for context
            current_price = None
            try:
                if monthly_analysis.get("price"):
                    current_price = float(monthly_analysis.get("price"))
                elif weekly_analysis.get("price"):
                    current_price = float(weekly_analysis.get("price"))
                elif daily_analysis.get("price"):
                    current_price = float(daily_analysis.get("price"))
            except (ValueError, TypeError):
                pass
            
            # Validate support/resistance data (defensive)
            def safe_levels(levels, price_context=None):
                """Filter out invalid levels (non-numeric, negative, or unreasonable)"""
                if not levels:
                    return []
                valid = []
                for level in levels:
                    try:
                        level_float = float(level)
                        # Reject if: negative, too large, or more than 3x away from current price
                        if level_float <= 0 or level_float > 100000:
                            logger.warning(f"Invalid level filtered (range): {level}")
                            continue
                        if price_context and (level_float > price_context * 3 or level_float < price_context / 3):
                            logger.warning(f"Invalid level filtered (3x from price {price_context}): {level}")
                            continue
                        valid.append(level)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid level filtered (not numeric): {level}")
                        continue
                return valid
            
            monthly_support = safe_levels(monthly_support, current_price)
            monthly_resistance = safe_levels(monthly_resistance, current_price)
            weekly_support = safe_levels(weekly_support, current_price)
            weekly_resistance = safe_levels(weekly_resistance, current_price)
            daily_support = safe_levels(daily_support, current_price)
            daily_resistance = safe_levels(daily_resistance, current_price)
            
            logger.info(f"MTF Summary - After validation - Monthly S/R: {monthly_support} / {monthly_resistance}")
            
            # Major Support Zones
            self.chat_ui.log("  • **Major Support Zones:**", "INFO")
            if monthly_support:
                self.chat_ui.log(f"      - Monthly: Rs {monthly_support[0]}" + (f", Rs {monthly_support[1]}" if len(monthly_support) > 1 else ""), "INFO")
            if weekly_support:
                self.chat_ui.log(f"      - Weekly: Rs {weekly_support[0]}" + (f", Rs {weekly_support[1]}" if len(weekly_support) > 1 else ""), "INFO")
            
            # Major Resistance Zones
            self.chat_ui.log("  • **Major Resistance Zones:**", "INFO")
            if monthly_resistance:
                self.chat_ui.log(f"      - Monthly: Rs {monthly_resistance[0]}" + (f", Rs {monthly_resistance[1]}" if len(monthly_resistance) > 1 else ""), "INFO")
            if weekly_resistance:
                self.chat_ui.log(f"      - Weekly: Rs {weekly_resistance[0]}" + (f", Rs {weekly_resistance[1]}" if len(weekly_resistance) > 1 else ""), "INFO")
            
            # Structural Boundaries
            self.chat_ui.log("  • **Structural Boundaries:**", "INFO")
            if monthly_support and monthly_trend.lower() == "bullish":
                self.chat_ui.log(f"      - Uptrend invalidation below Rs {monthly_support[0]}", "WARNING")
            elif monthly_resistance and monthly_trend.lower() == "bearish":
                self.chat_ui.log(f"      - Downtrend invalidation above Rs {monthly_resistance[0]}", "WARNING")
            else:
                self.chat_ui.log(f"      - Range boundaries: Monitor for breakout", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # PHASE-6A: CALCULATE DETERMINISTIC SCENARIO PROBABILITIES
            probability_result = None
            if self.probability_calculator:
                try:
                    probability_result = self.probability_calculator.calculate_probabilities(
                        alignment=alignment,
                        is_unstable=is_unstable,
                        monthly_trend=monthly_trend,
                        htf_location=htf_location,
                        current_price=current_price,
                        monthly_support=monthly_support,
                        monthly_resistance=monthly_resistance
                    )
                    
                    # Validate logic consistency
                    consistency_check = self.probability_calculator.validate_logic_consistency(
                        probabilities=probability_result["scenario_probabilities"],
                        alignment=alignment,
                        monthly_trend=monthly_trend,
                        monthly_support=monthly_support,
                        monthly_resistance=monthly_resistance,
                        current_price=current_price
                    )
                    
                    probability_result["validation"]["flags"] = consistency_check.get("flags", [])
                    
                    # PHASE-7A: EVALUATE EXECUTION GATE
                    if self.execution_gate:
                        try:
                            gate_evaluation = self.execution_gate.evaluate(
                                symbol=symbol,
                                alignment=alignment,
                                is_unstable=is_unstable,
                                probabilities=probability_result["scenario_probabilities"],
                                active_state=probability_result["active_state"],
                                current_price=current_price,
                                monthly_support=monthly_support,
                                monthly_resistance=monthly_resistance,
                                monthly_trend=monthly_trend
                            )
                            
                            # Log the gate decision
                            if self.gate_logger:
                                self.gate_logger.log_evaluation(
                                    symbol=symbol,
                                    alignment=alignment,
                                    is_unstable=is_unstable,
                                    probabilities=probability_result["scenario_probabilities"],
                                    active_state=probability_result["active_state"],
                                    current_price=current_price,
                                    gate_results=gate_evaluation["gate_results"],
                                    execution_permission=gate_evaluation["execution_permission"],
                                    monthly_trend=monthly_trend,
                                    monthly_support=monthly_support,
                                    monthly_resistance=monthly_resistance
                                )
                            
                            logger.info(f"Phase-7A: Gate evaluation complete - {gate_evaluation['execution_permission']['status']}")
                        except Exception as gate_err:
                            logger.error(f"Phase-7A gate evaluation failed: {gate_err}", exc_info=True)
                    
                    # Store in resolution tracker
                    if self.resolution_store:
                        analysis_id = self.resolution_store.store_analysis(
                            symbol=symbol,
                            timeframes="Monthly/Weekly/Daily",
                            alignment=alignment,
                            is_unstable=is_unstable,
                            monthly_trend=monthly_trend,
                            htf_location=htf_location,
                            current_price=current_price,
                            probabilities=probability_result["scenario_probabilities"],
                            reasoning=probability_result["reasoning"],
                            active_state=probability_result["active_state"],
                            support_resistance={
                                "monthly_support": monthly_support,
                                "monthly_resistance": monthly_resistance,
                                "weekly_support": weekly_support,
                                "weekly_resistance": weekly_resistance
                            },
                            validation=probability_result["validation"]
                        )
                        logger.info(f"Phase-6A: Stored analysis ID {analysis_id} for {symbol}")
                    
                except Exception as prob_err:
                    logger.error(f"Phase-6A probability calculation failed: {prob_err}", exc_info=True)
            
            # 4. SCENARIO SYNTHESIS (Probability-Weighted)
            self.chat_ui.log("**4. SCENARIO SYNTHESIS**\n", "INFO")
            
            # Use Phase-6A probabilities if available, otherwise fallback to simple status
            if probability_result:
                probs = probability_result["scenario_probabilities"]
                prob_a = probs["A_continuation"]
                prob_b = probs["B_pullback"]
                prob_c = probs["C_failure"]
                active_state = probability_result["active_state"]
                reasoning = probability_result["reasoning"]
                
                # Map probabilities to status labels
                def prob_to_status(prob):
                    if prob >= 0.50:
                        return "ACTIVE"
                    elif prob >= 0.35:
                        return "MONITOR"
                    elif prob >= 0.25:
                        return "WEAK"
                    else:
                        return "LOW PROBABILITY"
                
                scenario_a_status = prob_to_status(prob_a)
                scenario_b_status = prob_to_status(prob_b)
                scenario_c_status = prob_to_status(prob_c)
            else:
                # Fallback to simple status (old logic)
                scenario_a_status = "MONITOR"
                scenario_b_status = "MONITOR"
                scenario_c_status = "LOW PROBABILITY"
                
                if alignment == "FULL ALIGNMENT":
                    if not is_unstable:
                        scenario_a_status = "ACTIVE"
                        scenario_b_status = "MONITOR"
                        scenario_c_status = "LOW PROBABILITY"
                    else:
                        scenario_a_status = "WEAK"
                        scenario_b_status = "ACTIVE"
                        scenario_c_status = "MONITOR"
                elif alignment == "PARTIAL ALIGNMENT":
                    scenario_a_status = "WEAK"
                    scenario_b_status = "ACTIVE"
                    scenario_c_status = "MONITOR"
                elif alignment == "UNSTABLE":
                    scenario_a_status = "CONDITIONAL"
                    scenario_b_status = "ACTIVE"
                    scenario_c_status = "MONITOR"
                else:  # CONFLICT
                    scenario_a_status = "WEAK"
                    scenario_b_status = "MONITOR"
                    scenario_c_status = "ACTIVE"
            
            # Scenario A - CONTINUATION
            logger.info("Rendering Scenario A...")
            try:
                self.chat_ui.log("", "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                self.chat_ui.log(f"  • **Scenario A (Continuation): [{scenario_a_status}]**", "SUCCESS" if scenario_a_status == "ACTIVE" else "WARNING" if scenario_a_status in ["WEAK", "CONDITIONAL"] else "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"      Bullish trend continues with higher highs", "INFO")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    if monthly_support:
                        self.chat_ui.log(f"        - Price holds above Rs {monthly_support[0]} (Monthly support)", "INFO")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Break above Rs {monthly_resistance[0]} confirms strength", "INFO")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"      Bearish trend continues with lower lows", "INFO")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Price stays below Rs {monthly_resistance[0]} (Monthly resistance)", "INFO")
                    if monthly_support:
                        self.chat_ui.log(f"        - Break below Rs {monthly_support[0]} confirms weakness", "INFO")
                else:
                    self.chat_ui.log(f"      Consolidation continues within range", "INFO")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    if monthly_support and monthly_resistance:
                        self.chat_ui.log(f"        - Range: Rs {monthly_support[0]} to Rs {monthly_resistance[0]}", "INFO")
                    if weekly_support and weekly_resistance:
                        self.chat_ui.log(f"        - Weekly range: Rs {weekly_support[0]} to Rs {weekly_resistance[0]}", "INFO")
                    self.chat_ui.log(f"        - Wait for breakout confirmation", "INFO")
                logger.info("Scenario A rendered successfully")
            except Exception as sc_a_err:
                logger.error(f"Scenario A rendering failed: {sc_a_err}")
                self.chat_ui.log("⚠️ Scenario A encountered an error", "WARNING")
            
            # Scenario B - PULLBACK / MEAN REVERSION
            logger.info("Rendering Scenario B...")
            try:
                self.chat_ui.log("", "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                self.chat_ui.log(f"  • **Scenario B (Pullback / Mean Reversion): [{scenario_b_status}]**", "WARNING" if scenario_b_status == "ACTIVE" else "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"      Pullback within uptrend to retest support", "INFO")
                    self.chat_ui.log(f"      **Trigger Timeframe:** Daily or Weekly", "WARNING")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    self.chat_ui.log(f"        - Daily shows weakness, profit-taking, or RSI overbought", "INFO")
                    if weekly_support:
                        self.chat_ui.log(f"        - Target pullback zone: Rs {weekly_support[0]} (Weekly support)", "INFO")
                    if monthly_support:
                        self.chat_ui.log(f"        - Maximum pullback depth: Rs {monthly_support[0]} (Monthly support)", "WARNING")
                    self.chat_ui.log(f"      **Continuation Valid If:**", "SUCCESS")
                    if weekly_support:
                        self.chat_ui.log(f"        - Price holds above Rs {weekly_support[0]}", "SUCCESS")
                    self.chat_ui.log(f"        - Weekly structure remains intact (no lower-low)", "SUCCESS")
                    self.chat_ui.log(f"      **Invalidates Continuation If:**", "ERROR")
                    if monthly_support:
                        self.chat_ui.log(f"        - Break below Rs {monthly_support[0]} (HTF support failure)", "ERROR")
                    self.chat_ui.log(f"        - Weekly closes with lower-low structure", "ERROR")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"      Bounce within downtrend to test resistance", "INFO")
                    self.chat_ui.log(f"      **Trigger Timeframe:** Daily or Weekly", "WARNING")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    self.chat_ui.log(f"        - Daily shows strength, short-covering, or RSI oversold bounce", "INFO")
                    if weekly_resistance:
                        self.chat_ui.log(f"        - Target bounce zone: Rs {weekly_resistance[0]} (Weekly resistance)", "INFO")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Maximum bounce limit: Rs {monthly_resistance[0]} (Monthly resistance)", "WARNING")
                    self.chat_ui.log(f"      **Continuation Valid If:**", "SUCCESS")
                    if weekly_resistance:
                        self.chat_ui.log(f"        - Price rejected below Rs {weekly_resistance[0]}", "SUCCESS")
                    self.chat_ui.log(f"        - Weekly structure remains intact (no higher-high)", "SUCCESS")
                    self.chat_ui.log(f"      **Invalidates Continuation If:**", "ERROR")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Break above Rs {monthly_resistance[0]} (HTF resistance failure)", "ERROR")
                    self.chat_ui.log(f"        - Weekly closes with higher-high structure", "ERROR")
                else:
                    self.chat_ui.log(f"      Continued range-bound trading", "INFO")
                    self.chat_ui.log(f"      **Trigger Timeframe:** Daily", "WARNING")
                    self.chat_ui.log(f"      **Conditions:**", "INFO")
                    if daily_support:
                        self.chat_ui.log(f"        - Buy near Rs {daily_support[0]} (Daily support)", "INFO")
                    if daily_resistance:
                        self.chat_ui.log(f"        - Sell near Rs {daily_resistance[0]} (Daily resistance)", "INFO")
                    self.chat_ui.log(f"        - Expect choppiness until breakout", "INFO")
                    self.chat_ui.log(f"      **Invalidates Range If:**", "ERROR")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Breakout above Rs {monthly_resistance[0]}", "ERROR")
                    if monthly_support:
                        self.chat_ui.log(f"        - Breakdown below Rs {monthly_support[0]}", "ERROR")
                logger.info("Scenario B rendered successfully")
            except Exception as sc_b_err:
                logger.error(f"Scenario B rendering failed: {sc_b_err}")
                self.chat_ui.log("⚠️ Scenario B encountered an error", "WARNING")
            
            # Scenario C - TREND FAILURE
            logger.info("Rendering Scenario C...")
            try:
                self.chat_ui.log("", "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                self.chat_ui.log(f"  • **Scenario C (Trend Failure / Breakdown): [{scenario_c_status}]**", "ERROR" if scenario_c_status == "ACTIVE" else "WARNING" if scenario_c_status == "MONITOR" else "INFO")
                self.chat_ui.log(f"{'='*60}", "INFO")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"      Uptrend fails, structure shifts bearish", "INFO")
                    self.chat_ui.log(f"      **HTF Invalidation Level:**", "ERROR")
                    if monthly_support:
                        self.chat_ui.log(f"        - Rs {monthly_support[0]} (Monthly support) ← Critical level", "ERROR")
                    self.chat_ui.log(f"      **Trend Failure Conditions:**", "ERROR")
                    if monthly_support:
                        self.chat_ui.log(f"        - Daily close below Rs {monthly_support[0]}", "ERROR")
                    self.chat_ui.log(f"        - Weekly confirms with lower-low structure", "ERROR")
                    self.chat_ui.log(f"        - Monthly candle closes below support zone", "ERROR")
                    self.chat_ui.log(f"      **Structural Break Logic:**", "ERROR")
                    self.chat_ui.log(f"        - HTF higher-low pattern broken", "ERROR")
                    self.chat_ui.log(f"        - Momentum shifts from bullish to bearish", "ERROR")
                    self.chat_ui.log(f"        - All timeframes realign bearish", "ERROR")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"      Downtrend fails, structure shifts bullish", "INFO")
                    self.chat_ui.log(f"      **HTF Invalidation Level:**", "ERROR")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Rs {monthly_resistance[0]} (Monthly resistance) ← Critical level", "ERROR")
                    self.chat_ui.log(f"      **Trend Failure Conditions:**", "ERROR")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Daily close above Rs {monthly_resistance[0]}", "ERROR")
                    self.chat_ui.log(f"        - Weekly confirms with higher-high structure", "ERROR")
                    self.chat_ui.log(f"        - Monthly candle closes above resistance zone", "ERROR")
                    self.chat_ui.log(f"      **Structural Break Logic:**", "ERROR")
                    self.chat_ui.log(f"        - HTF lower-high pattern broken", "ERROR")
                    self.chat_ui.log(f"        - Momentum shifts from bearish to bullish", "ERROR")
                    self.chat_ui.log(f"        - All timeframes realign bullish", "ERROR")
                else:
                    self.chat_ui.log(f"      Range breaks decisively (structure change)", "INFO")
                    self.chat_ui.log(f"      **HTF Invalidation Levels:**", "ERROR")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Bullish: Rs {monthly_resistance[0]} (Monthly resistance)", "ERROR")
                    if monthly_support:
                        self.chat_ui.log(f"        - Bearish: Rs {monthly_support[0]} (Monthly support)", "ERROR")
                    self.chat_ui.log(f"      **Breakout Conditions:**", "ERROR")
                    self.chat_ui.log(f"        - Daily close outside range boundaries", "ERROR")
                    self.chat_ui.log(f"        - Weekly confirms direction with momentum", "ERROR")
                    self.chat_ui.log(f"        - Volume expansion on breakout", "ERROR")
                    self.chat_ui.log(f"      **Structural Break Logic:**", "ERROR")
                    self.chat_ui.log(f"        - Range structure abandoned", "ERROR")
                    self.chat_ui.log(f"        - New trend establishes in breakout direction", "ERROR")
                logger.info("Scenario C rendered successfully")
            except Exception as sc_c_err:
                logger.error(f"Scenario C rendering failed: {sc_c_err}")
                self.chat_ui.log("⚠️ Scenario C encountered an error", "WARNING")
            
            self.chat_ui.log("", "INFO")
            
            # 5. CONFIRMATION & INVALIDATION (Phase-5)
            self.chat_ui.log("**5. CONFIRMATION & INVALIDATION**\n", "INFO")
            
            # ALIGNMENT CLASSIFICATION (New: explicit verdict)
            self.chat_ui.log("  • **ALIGNMENT STATUS:**", "INFO")
            if alignment == "FULL ALIGNMENT":
                self.chat_ui.log(f"      **{alignment}** ✅", "SUCCESS")
            elif alignment == "PARTIAL ALIGNMENT":
                self.chat_ui.log(f"      **{alignment}** ⚠️", "WARNING")
            elif alignment == "UNSTABLE":
                self.chat_ui.log(f"      **{alignment}** 🔶", "WARNING")
            else:  # CONFLICT
                self.chat_ui.log(f"      **{alignment}** ❌", "ERROR")
            
            self.chat_ui.log("", "INFO")
            
            # MEAN REVERSION CHECK (Enhanced with HTF location, LTF distance, ATR logic)
            self.chat_ui.log("  • **Mean Reversion Check:**", "INFO")
            
            # Calculate HTF Location
            htf_location = "Unknown"
            if monthly_trend.lower() == "bullish" and monthly_resistance:
                if current_price and current_price >= monthly_resistance[0] * 0.95:
                    htf_location = f"Near HTF resistance (Rs {monthly_resistance[0]})"
                elif monthly_support and current_price <= monthly_support[0] * 1.05:
                    htf_location = f"Near HTF support (Rs {monthly_support[0]})"
                else:
                    htf_location = "Mid-range"
            elif monthly_trend.lower() == "bearish" and monthly_support:
                if current_price and current_price <= monthly_support[0] * 1.05:
                    htf_location = f"Near HTF support (Rs {monthly_support[0]})"
                elif monthly_resistance and current_price >= monthly_resistance[0] * 0.95:
                    htf_location = f"Near HTF resistance (Rs {monthly_resistance[0]})"
                else:
                    htf_location = "Mid-range"
            else:
                if monthly_support and monthly_resistance and current_price:
                    htf_location = f"Range-bound (Rs {monthly_support[0]} - Rs {monthly_resistance[0]})"
                else:
                    htf_location = "Mid-range"
            
            # Display Mean Reversion Analysis
            if is_unstable:
                self.chat_ui.log(f"      **HTF Trend:** {monthly_trend}", "INFO")
                self.chat_ui.log(f"      **HTF Location:** {htf_location}", "WARNING")
                self.chat_ui.log(f"      **LTF Extension:** Overextended (price near/beyond HTF boundary)", "WARNING")
                self.chat_ui.log(f"      **LTF Distance:** > 1.2 ATR from mean (estimated)", "WARNING")
                self.chat_ui.log(f"      **Verdict:** UNSTABLE - High mean reversion risk", "WARNING")
            elif alignment == "CONFLICT":
                self.chat_ui.log(f"      **HTF Trend:** {monthly_trend}", "INFO")
                self.chat_ui.log(f"      **HTF Location:** {htf_location}", "INFO")
                self.chat_ui.log(f"      **LTF Behavior:** Contradicting HTF direction", "WARNING")
                self.chat_ui.log(f"      **LTF Distance:** Diverging from HTF mean", "WARNING")
                self.chat_ui.log(f"      **Verdict:** CONFLICT - No clear alignment, reversion uncertain", "ERROR")
            elif alignment == "PARTIAL ALIGNMENT":
                self.chat_ui.log(f"      **HTF Trend:** {monthly_trend}", "INFO")
                self.chat_ui.log(f"      **HTF Location:** {htf_location}", "INFO")
                self.chat_ui.log(f"      **LTF Extension:** Moderate (mixed timeframes)", "INFO")
                self.chat_ui.log(f"      **LTF Distance:** 0.8-1.2 ATR from mean (estimated)", "INFO")
                self.chat_ui.log(f"      **Verdict:** PARTIAL - Moderate stability, watch for shift", "INFO")
            else:  # FULL ALIGNMENT
                self.chat_ui.log(f"      **HTF Trend:** {monthly_trend}", "INFO")
                self.chat_ui.log(f"      **HTF Location:** {htf_location}", "SUCCESS")
                self.chat_ui.log(f"      **LTF Extension:** Aligned (no overextension)", "SUCCESS")
                self.chat_ui.log(f"      **LTF Distance:** < 1.0 ATR from mean (estimated)", "SUCCESS")
                self.chat_ui.log(f"      **Verdict:** STABLE - All timeframes in sync, low reversion risk", "SUCCESS")
            
            self.chat_ui.log("", "INFO")
            
            # Current State
            self.chat_ui.log("  • **Current State:**", "INFO")
            self.chat_ui.log(f"      - Alignment: {alignment}", "INFO")
            if alignment == "UNSTABLE":
                self.chat_ui.log(f"      - Reason: LTF overextension near HTF resistance/support", "WARNING")
            elif alignment == "CONFLICT":
                self.chat_ui.log(f"      - Reason: Timeframes contradicting each other", "WARNING")
            elif alignment == "PARTIAL ALIGNMENT":
                self.chat_ui.log(f"      - Reason: Mixed timeframe directions", "INFO")
            else:
                self.chat_ui.log(f"      - Reason: All timeframes aligned in same direction", "SUCCESS")
            
            self.chat_ui.log("", "INFO")
            
            # Confirmation Conditions (What would make it stable/better)
            self.chat_ui.log("  • **Confirmation Conditions (Stability):**", "SUCCESS")
            if alignment == "UNSTABLE":
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"      **For Bullish Stability:**", "INFO")
                    self.chat_ui.log(f"        - Daily consolidation without breaking support", "INFO")
                    if weekly_support:
                        self.chat_ui.log(f"        - Weekly close holding above Rs {weekly_support[0]}", "INFO")
                    self.chat_ui.log(f"        - Momentum cooling without price damage", "INFO")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"      **For Bearish Stability:**", "INFO")
                    self.chat_ui.log(f"        - Daily consolidation without breaking resistance", "INFO")
                    if weekly_resistance:
                        self.chat_ui.log(f"        - Weekly close staying below Rs {weekly_resistance[0]}", "INFO")
                    self.chat_ui.log(f"        - Momentum stabilizing without reversal signs", "INFO")
                else:
                    self.chat_ui.log(f"      **For Range Stability:**", "INFO")
                    self.chat_ui.log(f"        - Daily consolidation within range boundaries", "INFO")
                    if daily_support and daily_resistance:
                        self.chat_ui.log(f"        - Price stays between Rs {daily_support[0]} and Rs {daily_resistance[0]}", "INFO")
                    self.chat_ui.log(f"        - Volatility decreases, preparing for breakout", "INFO")
            elif alignment == "CONFLICT":
                self.chat_ui.log(f"      **For Resolution:**", "INFO")
                self.chat_ui.log(f"        - Monthly direction takes control (higher timeframe precedence)", "INFO")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"        - Daily and Weekly shift to align with bullish Monthly", "INFO")
                    if monthly_support:
                        self.chat_ui.log(f"        - Price finds support above Rs {monthly_support[0]}", "INFO")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"        - Daily and Weekly shift to align with bearish Monthly", "INFO")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Price finds resistance below Rs {monthly_resistance[0]}", "INFO")
                else:
                    self.chat_ui.log(f"        - Market chooses direction (range breakout)", "INFO")
                    if monthly_resistance:
                        self.chat_ui.log(f"        - Bullish if breaks above Rs {monthly_resistance[0]}", "INFO")
                    if monthly_support:
                        self.chat_ui.log(f"        - Bearish if breaks below Rs {monthly_support[0]}", "INFO")
            elif alignment == "PARTIAL ALIGNMENT":
                self.chat_ui.log(f"      **For Full Alignment:**", "INFO")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"        - Lower timeframes align with bullish Monthly", "INFO")
                    if weekly_support:
                        self.chat_ui.log(f"        - Weekly holds above Rs {weekly_support[0]}", "INFO")
                elif monthly_trend.lower() == "bearish":
                    self.chat_ui.log(f"        - Lower timeframes align with bearish Monthly", "INFO")
                    if weekly_resistance:
                        self.chat_ui.log(f"        - Weekly stays below Rs {weekly_resistance[0]}", "INFO")
                else:
                    self.chat_ui.log(f"        - All timeframes consolidate in range", "INFO")
                    if weekly_support and weekly_resistance:
                        self.chat_ui.log(f"        - Weekly range: Rs {weekly_support[0]} to Rs {weekly_resistance[0]}", "INFO")
                    self.chat_ui.log(f"        - Wait for clear directional breakout", "INFO")
            else:  # FULL ALIGNMENT
                self.chat_ui.log(f"      **Maintain Alignment:**", "INFO")
                self.chat_ui.log(f"        - Price respects timeframe structure", "INFO")
                if monthly_trend.lower() == "bullish":
                    if monthly_support:
                        self.chat_ui.log(f"        - No break below Rs {monthly_support[0]} (Monthly support)", "INFO")
                elif monthly_trend.lower() == "bearish":
                    if monthly_resistance:
                        self.chat_ui.log(f"        - No break above Rs {monthly_resistance[0]} (Monthly resistance)", "INFO")
                else:
                    if monthly_support and monthly_resistance:
                        self.chat_ui.log(f"        - Range holds between Rs {monthly_support[0]} and Rs {monthly_resistance[0]}", "INFO")
                    self.chat_ui.log(f"        - Watch for volume expansion on breakout", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # Invalidation Conditions (What would prove structure wrong)
            self.chat_ui.log("  • **Invalidation Conditions:**", "ERROR")
            if monthly_trend.lower() == "bullish":
                self.chat_ui.log(f"      **Bullish Structure Fails If:**", "ERROR")
                if monthly_support:
                    self.chat_ui.log(f"        - Daily close below Rs {monthly_support[0]} (HTF support)", "ERROR")
                self.chat_ui.log(f"        - Weekly trend loss (lower-low formation)", "ERROR")
                self.chat_ui.log(f"        - Monthly structure breaks down", "ERROR")
            elif monthly_trend.lower() == "bearish":
                self.chat_ui.log(f"      **Bearish Structure Fails If:**", "ERROR")
                if monthly_resistance:
                    self.chat_ui.log(f"        - Daily close above Rs {monthly_resistance[0]} (HTF resistance)", "ERROR")
                self.chat_ui.log(f"        - Weekly trend reversal (higher-high formation)", "ERROR")
                self.chat_ui.log(f"        - Monthly structure breaks out", "ERROR")
            else:
                self.chat_ui.log(f"      **Range Structure Fails If:**", "ERROR")
                if monthly_support:
                    self.chat_ui.log(f"        - Breakdown below Rs {monthly_support[0]}", "ERROR")
                if monthly_resistance:
                    self.chat_ui.log(f"        - Breakout above Rs {monthly_resistance[0]}", "ERROR")
            
            self.chat_ui.log("", "INFO")
            
            # Failure Scenario (What would shift market state completely)
            self.chat_ui.log("  • **Failure Scenario:**", "WARNING")
            if alignment == "UNSTABLE":
                self.chat_ui.log(f"      **UNSTABLE → CONFLICT:**", "WARNING")
                self.chat_ui.log(f"        - HTF rejection at resistance", "WARNING")
                self.chat_ui.log(f"        - LTF breakdown without recovery", "WARNING")
                self.chat_ui.log(f"        - Would shift to conflicting timeframes", "WARNING")
            elif alignment in ["FULL ALIGNMENT", "PARTIAL ALIGNMENT"]:
                self.chat_ui.log(f"      **ALIGNED → CONFLICT:**", "WARNING")
                if monthly_trend.lower() == "bullish":
                    self.chat_ui.log(f"        - Failed break above key resistance", "WARNING")
                    self.chat_ui.log(f"        - Daily/Weekly shift bearish while Monthly bullish", "WARNING")
                else:
                    self.chat_ui.log(f"        - Failed break below key support", "WARNING")
                    self.chat_ui.log(f"        - Daily/Weekly shift bullish while Monthly bearish", "WARNING")
            else:  # CONFLICT
                self.chat_ui.log(f"      **CONFLICT → REVERSAL:**", "WARNING")
                self.chat_ui.log(f"        - HTF structure completely fails", "WARNING")
                self.chat_ui.log(f"        - All timeframes realign in opposite direction", "WARNING")
            
            self.chat_ui.log("", "INFO")
            
            # What to Monitor
            self.chat_ui.log("  • **What to Monitor:**", "INFO")
            self.chat_ui.log(f"      - Price behavior at key levels (not indicators)", "INFO")
            self.chat_ui.log(f"      - Structure and reaction (not prediction)", "INFO")
            if monthly_trend.lower() == "bullish" and monthly_support:
                self.chat_ui.log(f"      - Watch Rs {monthly_support[0]} for support test", "INFO")
            elif monthly_trend.lower() == "bearish" and monthly_resistance:
                self.chat_ui.log(f"      - Watch Rs {monthly_resistance[0]} for resistance test", "INFO")
            if alignment == "UNSTABLE":
                self.chat_ui.log(f"      - Daily closes for consolidation vs breakdown", "INFO")
            elif alignment == "CONFLICT":
                self.chat_ui.log(f"      - Which timeframe takes control", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # 6. RISK CONTEXT
            self.chat_ui.log("**6. RISK CONTEXT (NON-TRADING)**\n", "INFO")
            
            self.chat_ui.log("  • **Structural Invalidation:**", "WARNING")
            if monthly_trend.lower() == "bullish" and monthly_support:
                self.chat_ui.log(f"      - Bullish structure invalidated below Rs {monthly_support[0]}", "WARNING")
            elif monthly_trend.lower() == "bearish" and monthly_resistance:
                self.chat_ui.log(f"      - Bearish structure invalidated above Rs {monthly_resistance[0]}", "WARNING")
            
            self.chat_ui.log("  • **Highest Uncertainty:**", "WARNING")
            if alignment == "CONFLICT":
                self.chat_ui.log(f"      - Conflicting timeframes create low-conviction setup", "WARNING")
            elif alignment == "UNSTABLE":
                self.chat_ui.log(f"      - Overextended price near key resistance/support", "WARNING")
            elif daily_trend.lower() != monthly_trend.lower():
                self.chat_ui.log(f"      - Daily diverging from Monthly increases pullback risk", "WARNING")
            else:
                self.chat_ui.log(f"      - Timeframes aligned, uncertainty at key zones only", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # SCENARIO PROBABILITY SUMMARY (PHASE-6A)
            self.chat_ui.log(f"{'─'*70}", "INFO")
            self.chat_ui.log("**PHASE-6A: SCENARIO PROBABILITY ANALYSIS**\n", "INFO")
            
            if probability_result:
                # Display deterministic probabilities
                probs = probability_result["scenario_probabilities"]
                self.chat_ui.log(f"  Scenario A (Continuation):      {probs['A_continuation']:.2f}  [{scenario_a_status}]", "SUCCESS" if scenario_a_status == "ACTIVE" else "WARNING" if scenario_a_status in ["WEAK", "CONDITIONAL"] else "INFO")
                self.chat_ui.log(f"  Scenario B (Pullback):          {probs['B_pullback']:.2f}  [{scenario_b_status}]", "WARNING" if scenario_b_status == "ACTIVE" else "INFO")
                self.chat_ui.log(f"  Scenario C (Trend Failure):     {probs['C_failure']:.2f}  [{scenario_c_status}]", "ERROR" if scenario_c_status == "ACTIVE" else "WARNING" if scenario_c_status == "MONITOR" else "INFO")
                self.chat_ui.log("", "INFO")
                
                # Display active state
                active_state = probability_result["active_state"]
                if active_state == "CONFLICT_STATE":
                    self.chat_ui.log(f"  **ACTIVE STATE:** {active_state}", "ERROR")
                    self.chat_ui.log(f"  Reason: Market in conflict - no clear dominant scenario", "WARNING")
                else:
                    self.chat_ui.log(f"  **ACTIVE STATE:** {active_state}", "SUCCESS")
                
                self.chat_ui.log("", "INFO")
                
                # Display reasoning
                self.chat_ui.log("  **Structural Reasoning:**", "INFO")
                reasoning = probability_result["reasoning"]
                self.chat_ui.log(f"    A: {reasoning['A_reason']}", "INFO")
                self.chat_ui.log(f"    B: {reasoning['B_reason']}", "INFO")
                self.chat_ui.log(f"    C: {reasoning['C_reason']}", "INFO")
                
                # Validation check
                validation = probability_result["validation"]
                self.chat_ui.log("", "INFO")
                self.chat_ui.log(f"  **Validation:** Sum={validation['sum_check']:.2f}, Status={validation['consistency']}", "SUCCESS" if validation['consistency'] == "PASS" else "WARNING")
                
                # Display any consistency flags
                if validation.get("flags"):
                    self.chat_ui.log("  **Consistency Warnings:**", "WARNING")
                    for flag in validation["flags"]:
                        self.chat_ui.log(f"    - {flag.get('message', 'Unknown warning')}", "WARNING")
            else:
                # Fallback display (no Phase-6A)
                self.chat_ui.log(f"  Scenario A (Continuation):      [{scenario_a_status}]", "SUCCESS" if scenario_a_status == "ACTIVE" else "WARNING" if scenario_a_status in ["WEAK", "CONDITIONAL"] else "INFO")
                self.chat_ui.log(f"  Scenario B (Pullback):          [{scenario_b_status}]", "WARNING" if scenario_b_status == "ACTIVE" else "INFO")
                self.chat_ui.log(f"  Scenario C (Trend Failure):     [{scenario_c_status}]", "ERROR" if scenario_c_status == "ACTIVE" else "WARNING" if scenario_c_status == "MONITOR" else "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # PHASE-7A: EXECUTION GATE RESULTS
            if gate_evaluation:
                self.chat_ui.log(f"{'─'*70}", "INFO")
                self.chat_ui.log("**PHASE-7A: EXECUTION GATE**\n", "INFO")
                
                permission = gate_evaluation["execution_permission"]
                exec_status = permission.get("status", "UNKNOWN")
                
                if exec_status == "ALLOWED":
                    self.chat_ui.log("  ✅ **EXECUTION ALLOWED**", "SUCCESS")
                    self.chat_ui.log(f"  Valid for: {permission.get('valid_for', 'ONE_DECISION_CYCLE')}", "SUCCESS")
                    self.chat_ui.log(f"  Expires: {permission.get('expires_after', 'next_structure_change')}", "INFO")
                    self.chat_ui.log("", "INFO")
                    self.chat_ui.log("  All structural gates passed:", "SUCCESS")
                else:
                    self.chat_ui.log("  🚫 **EXECUTION BLOCKED**", "ERROR")
                    self.chat_ui.log("  Observation only - no action permitted", "WARNING")
                    self.chat_ui.log("", "INFO")
                    
                    blocked_reasons = permission.get("reason", [])
                    if blocked_reasons:
                        self.chat_ui.log("  Blocking Reasons:", "ERROR")
                        for reason in blocked_reasons:
                            self.chat_ui.log(f"    • {reason}", "ERROR")
                
                # Display gate results
                self.chat_ui.log("", "INFO")
                self.chat_ui.log("  Gate Results:", "INFO")
                gate_results = gate_evaluation["gate_results"]
                for gate_name, gate_status in gate_results.items():
                    status_icon = "✅" if gate_status == "PASS" else "❌"
                    log_level = "SUCCESS" if gate_status == "PASS" else "ERROR"
                    self.chat_ui.log(f"    {status_icon} {gate_name}: {gate_status}", log_level)
                
                # Add warning if execution blocked
                if exec_status == "BLOCKED":
                    self.chat_ui.log("", "INFO")
                    self.chat_ui.log("  ⚠️ Capital exposure not permitted in current structure", "WARNING")
                    self.chat_ui.log("  Wait for favorable structural alignment", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # Determine if execution is blocked
            is_execution_blocked = False
            if gate_evaluation:
                is_execution_blocked = gate_evaluation["execution_permission"].get("status") == "BLOCKED"
            
            if is_execution_blocked:
                self.chat_ui.log("Status Key (Observation Mode - No Action):", "WARNING")
            else:
                self.chat_ui.log("Status Key:", "INFO")
            self.chat_ui.log("  ACTIVE = Highest probability given current structure", "SUCCESS")
            self.chat_ui.log("  MONITOR = Moderate probability, watch for development", "INFO")
            self.chat_ui.log("  WEAK = Lower probability, conditions weakening", "WARNING")
            self.chat_ui.log("  LOW PROBABILITY = Unlikely unless structure breaks", "INFO")
            
            self.chat_ui.log("", "INFO")
            
            # DISCLAIMER
            self.chat_ui.log(f"{'─'*70}", "INFO")
            self.chat_ui.log("**DISCLAIMER:**", "ERROR")
            self.chat_ui.log("Probabilistic structural analysis only. No trading instructions.", "ERROR")
            self.chat_ui.log(f"{'='*70}", "INFO")
            
            # PHASE-X: HUMAN SUMMARY (Translation Layer)
            if self.human_summary:
                try:
                    self.chat_ui.log("", "INFO")
                    self.chat_ui.log("", "INFO")
                    
                    # Map alignment to strict format
                    alignment_mapping = {
                        "FULL ALIGNMENT": "FULL",
                        "PARTIAL ALIGNMENT": "PARTIAL",
                        "UNSTABLE": "UNSTABLE",
                        "CONFLICT": "CONFLICT"
                    }
                    strict_alignment = alignment_mapping.get(alignment, "CONFLICT")
                    
                    # Map active state to strict format
                    active_state_str = probability_result.get("active_state", "CONFLICT_STATE") if probability_result else "CONFLICT_STATE"
                    
                    # Map gate status to strict format (PASS / BLOCKED)
                    gate_status_str = "BLOCKED"  # Default to blocked (safe)
                    if gate_evaluation:
                        if gate_evaluation["execution_permission"].get("status") == "ALLOWED":
                            gate_status_str = "PASS"
                    
                    # Map HTF location to strict format (SUPPORT / MID / RESISTANCE)
                    htf_location_str = "MID"  # Default
                    if "resistance" in htf_location.lower():
                        htf_location_str = "RESISTANCE"
                    elif "support" in htf_location.lower():
                        htf_location_str = "SUPPORT"
                    
                    # Map trend to strict format (UP / DOWN / RANGE)
                    trend_mapping = {
                        "bullish": "UP",
                        "bearish": "DOWN",
                        "sideways": "RANGE",
                        "unknown": "RANGE"
                    }
                    trend_str = trend_mapping.get(monthly_trend.lower(), "RANGE")
                    
                    # Regime flags (currently empty, wire from market memory later)
                    regime_flags_set = set()
                    # TODO: Add regime_flags_set.add("REGIME_CHANGE") when market memory detects it
                    # TODO: Add regime_flags_set.add("EDGE_DEGRADATION") when edge tracking detects it
                    
                    # Phase-14: Fetch news/catalysts before final verdict
                    catalyst_report = None
                    if self.news_client:
                        try:
                            # Ensure browser_handler is current (lazy init)
                            if not self.news_client.browser_handler and self.controller:
                                self.news_client.browser_handler = getattr(self.controller, 'browser_handler', None)
                            if self.chat_ui:
                                self.chat_ui.log("", "INFO")
                                self.chat_ui.log("Fetching news & catalysts...", "INFO")
                            catalyst_report = self.news_client.get_catalyst_report(symbol)
                            if catalyst_report and catalyst_report.news_items:
                                display_text = self.news_client.format_for_display(catalyst_report)
                                if self.chat_ui:
                                    for line in display_text.split('\n'):
                                        if any(kw in line for kw in ("BULLISH", "OPPORTUNITY", "++", "strong")):
                                            self.chat_ui.log(line, "SUCCESS")
                                        elif any(kw in line for kw in ("BEARISH", "RISK", "--", "weak", "deteriorating")):
                                            self.chat_ui.log(line, "ERROR")
                                        elif any(kw in line for kw in ("===", "---", "NEWS &")):
                                            self.chat_ui.log(line, "INFO")
                                        else:
                                            self.chat_ui.log(line, "INFO")
                                print(display_text)
                                logger.info(f"Phase-14: Catalyst report for {symbol}: sentiment={catalyst_report.overall_sentiment}")
                            else:
                                if self.chat_ui:
                                    self.chat_ui.log("No significant news catalysts found.", "INFO")
                        except Exception as news_err:
                            logger.warning(f"Phase-14 news fetch failed: {news_err}")
                    
                    # Generate human-friendly summary (STRICT API)
                    summary = self.human_summary.generate(
                        alignment_state=strict_alignment,
                        active_state=active_state_str,
                        execution_gate_status=gate_status_str,
                        regime_flags=regime_flags_set,
                        htf_location=htf_location_str,
                        trend_state=trend_str
                    )
                    
                    # Display formatted summary
                    verdict_color = self.human_summary.get_verdict_color(summary["verdict"])
                    
                    # Display via chat UI (may fail if UI not ready)
                    try:
                        self.chat_ui.log("", "INFO")
                        self.chat_ui.log("=" * 70, verdict_color)
                        self.chat_ui.log(f"FINAL VERDICT: {summary['verdict']}", verdict_color)
                        self.chat_ui.log("=" * 70, verdict_color)
                        self.chat_ui.log("", "INFO")
                        self.chat_ui.log("SUMMARY:", "INFO")
                        self.chat_ui.log(f"  {summary['summary']}", "INFO")
                        self.chat_ui.log("", "INFO")
                        self.chat_ui.log(f"CONFIDENCE: {summary['confidence']}", "INFO")
                        self.chat_ui.log("=" * 70, verdict_color)
                    except Exception as ui_err:
                        logger.warning(f"Phase-X UI display failed, using fallback: {ui_err}")
                    
                    logger.info(f"Phase-X: Human summary generated - Verdict={summary['verdict']}, Confidence={summary['confidence']}")
                    
                    # Phase-11: Evaluate signal eligibility
                    if self.signal_eligibility:
                        try:
                            signal = self.signal_eligibility.evaluate_signal(
                                verdict=summary["verdict"],
                                confidence=summary["confidence"],
                                summary=summary["summary"],
                                alignment_state=strict_alignment,
                                htf_location=htf_location_str,
                                trend_state=trend_str,
                                active_scenario=active_state_str,
                                execution_gate_status=gate_status_str
                            )
                            
                            # Display signal
                            signal_display = self.signal_eligibility.format_signal(signal)
                            logger.info(f"Phase-11: Signal evaluated - Status={signal.signal_status.value}")
                            
                            # Display via chat UI
                            try:
                                self.chat_ui.log("", "INFO")
                                for line in signal_display.split('\n'):
                                    if line.startswith("✅"):
                                        self.chat_ui.log(line, "SUCCESS")
                                    elif line.startswith("❌"):
                                        self.chat_ui.log(line, "ERROR")
                                    else:
                                        self.chat_ui.log(line, "INFO")
                            except Exception as ui_err:
                                logger.warning(f"Phase-11 UI display failed: {ui_err}")
                            
                            # Always log to console
                            print(signal_display)
                            
                        except Exception as signal_err:
                            logger.error(f"Phase-11 signal evaluation failed: {signal_err}", exc_info=True)
                    
                    # CRITICAL: Always display summary (separate from execution permission)
                    try:
                        # Log to console explicitly
                        print("\n" + "=" * 70)
                        print(f"[{summary['verdict']}] FINAL VERDICT: {summary['verdict']}")
                        print("=" * 70)
                        print("\nSUMMARY:")
                        print(f"  {summary['summary']}")
                        print(f"\nCONFIDENCE: {summary['confidence']}")
                        print("=" * 70 + "\n")
                    except Exception as display_err:
                        logger.error(f"Phase-X console display failed: {display_err}", exc_info=True)
                        
                except Exception as summary_err:
                    logger.error(f"Phase-X human summary failed: {summary_err}", exc_info=True)
                    # Fail silently - technical analysis already displayed
        
        except Exception as e:
            logger.error(f"Phase-5 display failed: {e}", exc_info=True)
            self.chat_ui.log(f"\n❌ **Phase-5 Output Error:** {str(e)}", "ERROR")
            self.chat_ui.log("Phase-3 and Phase-4 completed successfully. Phase-5 display encountered an error.", "WARNING")
    
    def _classify_mtf_alignment(
        self,
        monthly_trend: str,
        weekly_trend: str,
        daily_trend: str,
        monthly_momentum: str,
        weekly_momentum: str,
        daily_momentum: str,
        monthly_data: Optional[Dict],
        daily_data: Optional[Dict]
    ) -> tuple:
        """
        Classify multi-timeframe alignment with top-down precedence.
        
        Hierarchy: Monthly > Weekly > Daily
        
        Returns:
            (alignment_status, dominant_timeframe, conflicts_list, is_unstable)
        """
        trends = [monthly_trend, weekly_trend, daily_trend]
        conflicts = []
        is_unstable = False
        
        # Determine dominant timeframe (highest available)
        if monthly_trend != "unknown":
            dominant_tf = "MONTHLY (1M)"
            dominant_trend = monthly_trend
        elif weekly_trend != "unknown":
            dominant_tf = "WEEKLY (1W)"
            dominant_trend = weekly_trend
        elif daily_trend != "unknown":
            dominant_tf = "DAILY (1D)"
            dominant_trend = daily_trend
        else:
            return "INSUFFICIENT DATA", "UNKNOWN", [], False
        
        # Check for full alignment
        valid_trends = [t for t in trends if t != "unknown"]
        if len(valid_trends) >= 2 and all(t == valid_trends[0] for t in valid_trends):
            alignment = "FULL ALIGNMENT"
        
        # Check for conflicts
        else:
            # Monthly vs Weekly conflict
            if monthly_trend != "unknown" and weekly_trend != "unknown" and monthly_trend != weekly_trend:
                conflicts.append(f"Weekly ({weekly_trend}) conflicts with Monthly ({monthly_trend})")
                alignment = "CONFLICT"
            
            # Monthly vs Daily conflict
            elif monthly_trend != "unknown" and daily_trend != "unknown" and monthly_trend != daily_trend:
                conflicts.append(f"Daily ({daily_trend}) conflicts with Monthly ({monthly_trend})")
                alignment = "CONFLICT"
            
            # Weekly vs Daily conflict (less severe)
            elif weekly_trend != "unknown" and daily_trend != "unknown" and weekly_trend != daily_trend:
                conflicts.append(f"Daily ({daily_trend}) diverges from Weekly ({weekly_trend})")
                alignment = "PARTIAL ALIGNMENT"
            
            else:
                alignment = "PARTIAL ALIGNMENT"
        
        # Mean reversion check: Extreme extension + price near resistance = UNSTABLE
        if daily_data and monthly_data:
            daily_analysis = daily_data.get("analysis", {})
            monthly_analysis = monthly_data.get("analysis", {})
            
            # Check if daily shows extreme momentum (overbought/oversold)
            is_extreme_bullish = any(keyword in daily_momentum for keyword in ["strong bullish", "extreme", "overbought"])
            is_extreme_bearish = any(keyword in daily_momentum for keyword in ["strong bearish", "extreme", "oversold"])
            
            # Get current price and resistance/support levels
            try:
                # Extract price from DOM data (stored in analysis or separate field)
                price_str = None
                
                # Try to get price from the analysis metadata
                if "price" in monthly_analysis:
                    price_str = monthly_analysis["price"]
                elif "price" in daily_analysis:
                    price_str = daily_analysis["price"]
                
                if price_str:
                    # Clean price string and convert to float
                    current_price = float(str(price_str).replace(",", "").replace("₹", "").strip())
                    
                    # Check resistance proximity for bullish extension
                    if is_extreme_bullish:
                        monthly_resistance = monthly_analysis.get("resistance", [])
                        if monthly_resistance:
                            # Check if price is within 3% of any resistance level
                            for resistance_level in monthly_resistance[:2]:  # Check first 2 levels
                                try:
                                    resistance_price = float(resistance_level)
                                    distance_pct = ((resistance_price - current_price) / current_price) * 100
                                    
                                    # If price is within 3% below resistance
                                    if 0 <= distance_pct <= 3:
                                        if alignment == "FULL ALIGNMENT":
                                            alignment = "UNSTABLE"
                                        is_unstable = True
                                        conflicts.append(f"Daily overbought ({daily_momentum}) while price near Monthly resistance (Rs {resistance_price:.2f})")
                                        break
                                except (ValueError, TypeError):
                                    continue
                    
                    # Check support proximity for bearish extension
                    elif is_extreme_bearish:
                        monthly_support = monthly_analysis.get("support", [])
                        if monthly_support:
                            # Check if price is within 3% of any support level
                            for support_level in monthly_support[:2]:  # Check first 2 levels
                                try:
                                    support_price = float(support_level)
                                    distance_pct = ((current_price - support_price) / current_price) * 100
                                    
                                    # If price is within 3% above support
                                    if 0 <= distance_pct <= 3:
                                        if alignment == "FULL ALIGNMENT":
                                            alignment = "UNSTABLE"
                                        is_unstable = True
                                        conflicts.append(f"Daily oversold ({daily_momentum}) while price near Monthly support (Rs {support_price:.2f})")
                                        break
                                except (ValueError, TypeError):
                                    continue
            
            except (ValueError, TypeError, AttributeError) as e:
                # Price extraction failed, skip mean reversion check
                logger.debug(f"Could not perform mean reversion check: {e}")
                pass
        
        return alignment, dominant_tf, conflicts, is_unstable
    
    def _validate_and_correct_symbol(self, symbol: str, original_instruction: str) -> Optional[str]:
        """
        Phase-11.5G: Validate symbol using unified 3-layer resolver.
        
        Args:
            symbol: Extracted symbol to validate
            original_instruction: Full user instruction (for Google search context)
            
        Returns:
            Validated/corrected symbol or None if unable to find valid symbol
        """
        if not self.symbol_resolver:
            logger.warning("Symbol resolver not available, using fallback validation")
            return symbol
        
        try:
            # Ensure TradingView client is available for resolver
            if not self.symbol_resolver.tradingview_client:
                if not self.tradingview_client:
                    if not hasattr(self.controller, 'browser_handler') or not self.controller.browser_handler:
                        logger.warning("Browser not available, assuming symbol is correct")
                        return symbol
                    
                    browser_handler = self.controller.browser_handler
                    browser_handler._ensure_browser()
                    
                    from perception.tradingview_client import TradingViewClient
                    self.tradingview_client = TradingViewClient(self.config, browser_handler)
                
                self.symbol_resolver.tradingview_client = self.tradingview_client
            
            # Use SINGLE_ANALYSIS mode (allows Google search)
            from logic.symbol_resolver import ResolutionMode, ResolutionStatus
            
            # CRITICAL: Use original_instruction (e.g., "tata consumer") instead of extracted symbol (e.g., "TATA")
            # This ensures non-ticker text like "tata consumer" allows Google search
            # If we pass "TATA", resolver sees it as ticker and blocks Google
            search_input = original_instruction if original_instruction else symbol
            
            result = self.symbol_resolver.resolve(
                user_input=search_input,
                mode=ResolutionMode.SINGLE_ANALYSIS,
                context=original_instruction
            )
            
            if result.status in [ResolutionStatus.VALID, ResolutionStatus.RESOLVED]:
                if result.symbol != symbol:
                    logger.info(f"Symbol resolved: {symbol} → {result.symbol} (source: {result.source.value})")
                    if self.chat_ui:
                        self.chat_ui.log(f"Symbol resolved: {result.symbol} (confidence: {result.confidence.value})", "SUCCESS")
                return result.symbol
            elif result.status == ResolutionStatus.DATA_UNAVAILABLE:
                logger.error(f"TradingView data unavailable for {symbol}")
                if self.chat_ui:
                    self.chat_ui.log(f"Market data unavailable for {symbol}", "ERROR")
                return None
            else:  # UNKNOWN
                logger.error(f"Could not resolve symbol: {symbol}")
                if self.chat_ui:
                    self.chat_ui.log(f"Could not resolve symbol: {symbol}", "ERROR")
                return None
        
        except Exception as e:
            logger.error(f"Symbol resolution failed: {e}", exc_info=True)
            return symbol  # Fallback to original
    
    def _extract_symbol_from_instruction(self, instruction: str) -> Optional[str]:
        """
        Extract stock symbol from instruction.
        
        Args:
            instruction: User instruction
            
        Returns:
            Symbol string or None
        """
        instruction_upper = instruction.upper()
        
        # Try to extract quoted symbol
        import re
        quoted = re.search(r'["\']([A-Z]+)["\']', instruction_upper)
        if quoted:
            return quoted.group(1)
        
        # Try to extract single uppercase word
        words = instruction_upper.split()
        for word in words:
            # Must be 2-15 chars, all uppercase, no numbers
            if len(word) >= 2 and len(word) <= 15 and word.isalpha() and word.isupper():
                # Skip common words and articles
                skip_words = ["ANALYZE", "ANALYSE", "ANALYSES", "STOCK", "CHART", "TREND", "DAILY", "WEEKLY", "MONTHLY", "TECHNICAL", "ANALYSIS", "OPEN", "TRADINGVIEW", "ON", "PHASE", "REASONING", "SYNTHESIS", "SYNTHESIZE", "MTF", "MULTI", "TIMEFRAME", "SCENARIO", "SCENARIOS", "USE", "IDENTIFY", "ASSESS", "APPLY", "CLASSIFY", "GENERATE", "WITHOUT", "GIVING", "TRADE", "INSTRUCTIONS", "THE", "A", "AN", "TO", "FOR", "AND", "OR", "OF", "IN", "AT", "BY", "WITH", "FROM", "AS", "IS", "ARE", "WAS", "WERE", "BE", "BEEN", "HAVE", "HAS", "HAD", "DO", "DOES", "DID", "WILL", "WOULD", "CAN", "COULD", "SHOULD", "MAY", "MIGHT", "MUST"]
                if word not in skip_words:
                    return word
        
        return None
    
    def _search_correct_symbol(self, query: str) -> Optional[str]:
        """
        Search for correct stock symbol using Google AI mode.
        Always searches Google - no hardcoded mappings.
        
        Args:
            query: User's query (e.g., "KTK", "some company name")
            
        Returns:
            Correct NSE/BSE symbol or None
        """
        import re
        
        # Known symbol mappings - used as FALLBACK if Google search fails
        KNOWN_SYMBOLS = {
            # Banks - exact matches and common variations
            "yes bank": "YESBANK",
            "yesbank": "YESBANK",
            "yes": "YESBANK",
            "kotak bank": "KOTAKBANK",
            "kotak mahindra": "KOTAKBANK",
            "kotak mahindra bank": "KOTAKBANK",
            "kotakbank": "KOTAKBANK",
            "kotak": "KOTAKBANK",
            "ktk bank": "KTKBANK",
            "karnataka bank": "KTKBANK",
            "ktkbank": "KTKBANK",
            "ktk": "KTKBANK",
            "south indian bank": "SOUTHBANK",
            "southbank": "SOUTHBANK",
            "sib bank": "SOUTHBANK",
            "sib": "SOUTHBANK",
            "hdfc bank": "HDFCBANK",
            "hdfcbank": "HDFCBANK",
            "hdfc": "HDFCBANK",
            "icici bank": "ICICIBANK",
            "icicibank": "ICICIBANK",
            "icici": "ICICIBANK",
            "axis bank": "AXISBANK",
            "axisbank": "AXISBANK",
            "axis": "AXISBANK",
            "sbi": "SBIN",
            "state bank": "SBIN",
            "state bank of india": "SBIN",
            "indusind bank": "INDUSINDBK",
            "indusind": "INDUSINDBK",
            "federal bank": "FEDERALBNK",
            "federalbank": "FEDERALBNK",
        }
        
        try:
            logger.info(f"Searching Google AI for symbol: {query}")
            
            # Construct search query asking for NSE symbol
            search_query = f"what is the NSE stock symbol for {query}"
            
            # Use Google AI mode (udm=17) for better answers
            google_ai_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&udm=17"
            
            # Use browser to search
            if not hasattr(self.controller, 'browser_handler') or not self.controller.browser_handler:
                logger.warning("Browser handler not available for symbol search")
                return None
            
            browser = self.controller.browser_handler
            worker = browser.worker
            
            if not worker:
                logger.warning("Playwright worker not ready for symbol search")
                return None
            
            logger.info(f"Asking Google AI: '{search_query}'")
            if self.chat_ui:
                self.chat_ui.log(f"Searching: {search_query}", "INFO")
            
            # Define navigation function for AI mode
            def _search_google_ai(page):
                page.goto(google_ai_url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)  # Wait for AI to generate response
                # Extract only main content, skip navigation/menu
                text = page.evaluate("() => document.body.innerText")
                # Filter out navigation menu items (News, Images, Shopping, etc.)
                lines = text.split('\n')
                filtered = [line for line in lines if line.strip() and not line.strip().isdigit() and 
                           not line.strip() in ['News', 'Images', 'Shopping', 'Videos', 'More', 'Tools', 'Search Results',
                                                 'Filters and topics', 'AT Mode', 'All', 'Finance', 'Accessibility help',
                                                 'Accessibility feedback', 'Sign in']]
                return '\n'.join(filtered)
            
            # Navigate to Google AI search and extract text
            search_text = worker.execute(_search_google_ai, timeout=20)
            
            # SAFETY: Check for CAPTCHA / robot check
            if search_text and ("not a robot" in search_text.lower() or 
                               "captcha" in search_text.lower() or
                               "unusual traffic" in search_text.lower() or
                               "verify you're human" in search_text.lower()):
                logger.error("[CRITICAL] Google CAPTCHA detected - cannot search safely")
                if self.chat_ui:
                    self.chat_ui.log("Google blocked with CAPTCHA", "ERROR")
                
                # FALLBACK: Use known mapping if available
                query_normalized = query.lower().strip()
                if query_normalized in KNOWN_SYMBOLS:
                    fallback_symbol = KNOWN_SYMBOLS[query_normalized]
                    logger.warning(f"[FALLBACK] Using known mapping due to CAPTCHA: '{query}' → {fallback_symbol}")
                    if self.chat_ui:
                        self.chat_ui.log(f"Using known symbol (CAPTCHA blocked Google): {fallback_symbol}", "WARNING")
                    return fallback_symbol
                
                return None
            
            if not search_text:
                logger.warning("Failed to extract AI search results, trying regular Google...")
                if self.chat_ui:
                    self.chat_ui.log("AI mode failed, trying regular search...", "INFO")
                
                # Fallback to regular Google
                google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                
                def _search_google_regular(page):
                    page.goto(google_url, timeout=10000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    # Extract and filter out UI navigation elements
                    text = page.evaluate("() => document.body.innerText")
                    lines = text.split('\n')
                    filtered = [line for line in lines if line.strip() and not line.strip().isdigit() and 
                               not line.strip() in ['News', 'Images', 'Shopping', 'Videos', 'More', 'Tools', 'Search Results',
                                                     'Filters and topics', 'AT Mode', 'All', 'Finance', 'Accessibility help',
                                                     'Accessibility feedback', 'Sign in']]
                    return '\n'.join(filtered)
                
                search_text = worker.execute(_search_google_regular, timeout=15)
            
            # SAFETY: Check for CAPTCHA again in fallback results
            if search_text and ("not a robot" in search_text.lower() or 
                               "captcha" in search_text.lower() or
                               "unusual traffic" in search_text.lower() or
                               "verify you're human" in search_text.lower()):
                logger.error("[CRITICAL] Google CAPTCHA detected in fallback - cannot search safely")
                if self.chat_ui:
                    self.chat_ui.log("Google blocked with CAPTCHA", "ERROR")
                
                # FALLBACK: Use known mapping if available
                query_normalized = query.lower().strip()
                if query_normalized in KNOWN_SYMBOLS:
                    fallback_symbol = KNOWN_SYMBOLS[query_normalized]
                    logger.warning(f"[FALLBACK] Using known mapping due to CAPTCHA: '{query}' → {fallback_symbol}")
                    if self.chat_ui:
                        self.chat_ui.log(f"Using known symbol (CAPTCHA blocked Google): {fallback_symbol}", "WARNING")
                    return fallback_symbol
                
                return None
            
            if not search_text:
                logger.warning("Failed to extract search results")
                return None
            
            logger.info(f"Got search results ({len(search_text)} chars), using LLM to extract symbol...")
            
            # Log the actual search results for debugging (not to UI)
            logger.debug(f"Google search results preview: {search_text[:500]}")
            logger.info(f"Search returned {len(search_text)} characters of data")
            
            # Use LLM to intelligently extract symbol from search results
            if self.llm_client:
                prompt = f"""You are analyzing Google search results to find the EXACT NSE stock symbol.

USER'S QUERY: "{query}"
FULL SEARCH QUERY: "{search_query}"

GOOGLE RESULTS:
{search_text[:2500]}

CRITICAL MATCHING RULES:
1. Match the EXACT company name from the user's query
2. "ktk bank" = Karnataka Bank → Symbol: KTKBANK (NOT Kotak Mahindra)
3. "kotak bank" = Kotak Mahindra Bank → Symbol: KOTAKBANK
4. "south indian bank" = South Indian Bank → Symbol: SOUTHBANK
5. Look for explicit statements like "NSE: SYMBOL" or "ticker: SYMBOL"
6. If query has abbreviated name (like "ktk"), find the full company name first, then the symbol
7. Common bank abbreviations:
   - KTK = Karnataka Bank (KTKBANK)
   - SIB = South Indian Bank (SOUTHBANK)
   - Kotak = Kotak Mahindra Bank (KOTAKBANK)

TASK: Find the NSE symbol for "{query}" specifically, not similar companies.

RESPOND: Only the exact NSE symbol (uppercase). If unclear or not found, say "NONE"."""

                try:
                    llm_response = self.llm_client.generate_completion(
                        system_prompt="You are a stock market expert. Extract ONLY the specific NSE stock ticker symbol from Google search results. Never return generic words.",
                        user_prompt=prompt
                    )
                    
                    # Clean up response
                    symbol = llm_response.strip().upper()
                    # Remove any non-alphanumeric characters
                    symbol = re.sub(r'[^A-Z0-9]', '', symbol)
                    
                    # Validate it's not a generic word
                    generic_words = ["STOCK", "SYMBOL", "NSE", "BSE", "TRADED", "TICKER", "COMPANY", "EXCHANGE", "NONE"]
                    
                    if symbol and symbol not in generic_words and len(symbol) >= 2 and len(symbol) <= 15:
                        # SAFETY: Validate extracted symbol makes sense for the query
                        # Check if query mentions a different company than extracted symbol
                        query_lower = query.lower()
                        symbol_lower = symbol.lower()
                        
                        # Detect obvious mismatches (e.g., "yes bank" → "KOTAKBANK")
                        mismatch_detected = False
                        if "yes" in query_lower and "yes" not in symbol_lower:
                            mismatch_detected = True
                            logger.error(f"[CRITICAL] Symbol mismatch: query has 'yes' but symbol is {symbol}")
                        elif "kotak" in query_lower and "kotak" not in symbol_lower:
                            mismatch_detected = True
                            logger.error(f"[CRITICAL] Symbol mismatch: query has 'kotak' but symbol is {symbol}")
                        elif "ktk" in query_lower and "ktk" not in symbol_lower and "karnataka" not in query_lower:
                            mismatch_detected = True
                            logger.error(f"[CRITICAL] Symbol mismatch: query has 'ktk' but symbol is {symbol}")
                        elif "south" in query_lower and "south" not in symbol_lower:
                            mismatch_detected = True
                            logger.error(f"[CRITICAL] Symbol mismatch: query has 'south' but symbol is {symbol}")
                        
                        if mismatch_detected:
                            logger.error("[CRITICAL] Rejecting mismatched symbol - likely CAPTCHA/search failure")
                            if self.chat_ui:
                                self.chat_ui.log(f"Symbol mismatch detected - rejecting {symbol}", "ERROR")
                            return None
                        
                        logger.info(f"LLM extracted symbol from search: {symbol}")
                        if self.chat_ui:
                            self.chat_ui.log(f"Found symbol: {symbol}", "SUCCESS")
                        return symbol
                    else:
                        logger.warning(f"LLM returned invalid or generic symbol: {symbol}")
                        
                except Exception as e:
                    logger.warning(f"LLM symbol extraction failed: {e}")
            
            # Try regex patterns as fallback (more specific patterns)
            # Pattern 1: NSE: followed by symbol (not STOCK or generic words)
            nse_match = re.search(r'NSE[:\s]+([A-Z][A-Z0-9]{1,14})\b', search_text, re.IGNORECASE)
            if nse_match:
                symbol = nse_match.group(1).upper()
                # Check it's not a generic word
                if symbol not in ["STOCK", "SYMBOL", "NSE", "BSE", "TRADED", "TICKER"]:
                    logger.info(f"Extracted symbol from NSE: pattern: {symbol}")
                    return symbol
            
            # Pattern 2: "traded as SYMBOL" or "symbol is SYMBOL"
            traded_match = re.search(r'(?:traded as|symbol is|ticker[:\s]+)[\s:]*([A-Z][A-Z0-9]{1,14})\b', search_text, re.IGNORECASE)
            if traded_match:
                symbol = traded_match.group(1).upper()
                if symbol not in ["STOCK", "SYMBOL", "NSE", "BSE", "TRADED", "TICKER", "IS", "AS"] and len(symbol) >= 2:
                    logger.info(f"Extracted symbol from 'traded as' pattern: {symbol}")
                    return symbol
            
            # Pattern 3: Symbol in parentheses like "Company Name (SYMBOL)"
            paren_match = re.search(r'\(([A-Z][A-Z0-9]{1,14})\)', search_text)
            if paren_match:
                symbol = paren_match.group(1).upper()
                if symbol not in ["STOCK", "SYMBOL", "NSE", "BSE", "TRADED", "TICKER"] and len(symbol) >= 2:
                    logger.info(f"Extracted symbol from parentheses: {symbol}")
                    return symbol
            
            logger.warning(f"Could not extract valid symbol from search results")
            if self.chat_ui:
                self.chat_ui.log(f"Could not find NSE symbol for '{query}'. Please try with full company name.", "ERROR")
            
            # FALLBACK: Use known symbol mapping if Google search completely failed
            query_normalized = query.lower().strip()
            if query_normalized in KNOWN_SYMBOLS:
                fallback_symbol = KNOWN_SYMBOLS[query_normalized]
                logger.warning(f"[FALLBACK] Using known mapping as Google failed: '{query}' → {fallback_symbol}")
                if self.chat_ui:
                    self.chat_ui.log(f"Using fallback mapping: {fallback_symbol}", "WARNING")
                return fallback_symbol
            
            return None
            
        except Exception as e:
            logger.error(f"Symbol search failed: {e}", exc_info=True)
            
            # FALLBACK: On exception, try known mapping
            query_normalized = query.lower().strip()
            if query_normalized in KNOWN_SYMBOLS:
                fallback_symbol = KNOWN_SYMBOLS[query_normalized]
                logger.warning(f"[FALLBACK] Using known mapping due to exception: '{query}' → {fallback_symbol}")
                if self.chat_ui:
                    self.chat_ui.log(f"Search failed, using fallback: {fallback_symbol}", "WARNING")
                return fallback_symbol
            
            return None
    
    def _extract_timeframe_from_instruction(self, instruction: str) -> str:
        """
        Extract timeframe from instruction (e.g., "weekly", "monthly", "daily").
        
        Args:
            instruction: User instruction
            
        Returns:
            Timeframe code (1D, 1W, 1M) or default (1D)
        """
        instruction_lower = instruction.lower()
        
        # Map natural language to TradingView timeframe codes
        timeframe_map = {
            "weekly": "1W",
            "week": "1W",
            "monthly": "1M",
            "month": "1M",
            "daily": "1D",
            "day": "1D",
            "hourly": "60",
            "hour": "60",
            "15 min": "15",
            "15min": "15",
            "5 min": "5",
            "5min": "5"
        }
        
        for keyword, code in timeframe_map.items():
            if keyword in instruction_lower:
                return code
        
        # Default to daily
        return "1D"
    
    def _is_market_chat_query(self, instruction: str) -> bool:
        """
        Phase-2C: Detect if instruction is a market chat query (no browser needed).
        
        These queries use stored analyses only, no live chart access.
        
        Args:
            instruction: User instruction
            
        Returns:
            True if it's a chat query
        """
        if not self.market_memory:
            return False
        
        instruction_lower = instruction.lower()
        
        # Chat query patterns (memory-only, no browser)
        chat_patterns = [
            "last analysis",
            "previous analysis",
            "what was",
            "what did you",
            "compare",
            "comparison",
            "vs",
            "versus",
            "which stock",
            "which is",
            "stronger",
            "weaker",
            "has trend changed",
            "trend change",
            "summarize",
            "summary",
            "today's",
            "recent",
            "market bias"
        ]
        
        # Must be a market-related query
        market_keywords = [
            "stock", "reliance", "tcs", "infy", "nifty", "sensex",
            "analysis", "trend", "bullish", "bearish", "market"
        ]
        
        has_chat_pattern = any(pattern in instruction_lower for pattern in chat_patterns)
        has_market_keyword = any(keyword in instruction_lower for keyword in market_keywords)
        
        # Exclude "latest" and "refresh" which need browser
        needs_refresh = any(word in instruction_lower for word in ["latest", "refresh", "current", "now", "live"])
        
        return has_chat_pattern and has_market_keyword and not needs_refresh
    
    def _handle_market_chat_query(self, instruction: str):
        """
        Phase-2C: Handle market chat queries using stored analyses.
        NO browser required - uses memory only.
        Delegates to MarketQueryHandler.
        """
        logger.info("Handling Market Chat Query (memory-only)")
        
        if not self.market_query_handler:
            if self.chat_ui:
                self.chat_ui.log("Market memory not available.", "WARNING")
            return
        
        if self.chat_ui:
            self.chat_ui.log("Querying market memory...", "INFO")
            self.chat_ui.set_status("Thinking")
        
        try:
            instruction_lower = instruction.lower()
            
            # Determine query type
            if "compare" in instruction_lower or "vs" in instruction_lower or "versus" in instruction_lower:
                query_type = "comparison"
            elif "last analysis" in instruction_lower or "previous analysis" in instruction_lower or "what was" in instruction_lower:
                query_type = "last_analysis"
            elif "trend change" in instruction_lower or "has trend changed" in instruction_lower:
                query_type = "trend_change"
            elif "stronger" in instruction_lower or "weaker" in instruction_lower or "which stock" in instruction_lower:
                query_type = "strongest"
            elif "summarize" in instruction_lower or "summary" in instruction_lower or "market bias" in instruction_lower:
                query_type = "market_summary"
            else:
                query_type = "generic"
            
            self.market_query_handler.handle_query(
                instruction, query_type,
                symbol_extractor=self._extract_symbol_from_instruction
            )
                
        except Exception as e:
            logger.error(f"Market chat query failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"Query failed: {e}", "ERROR")
                self.chat_ui.set_status("Failed")
    
    # Market memory query methods extracted to logic/market_query_handler.py
    # Old methods removed — MarketQueryHandler handles all query types now.

    def _handle_followup_intent(self, instruction: str):
        """Shielded execution for FOLLOWUP intent."""
        logger.info("Handling Shielded Follow-up Intent")
        
        last_obs = self.dialogue_state.last_observation
        if not last_obs:
            msg = self.response_composer.compose_clarification("no observation")
            if self.chat_ui:
                self.chat_ui.log(msg, "WARNING")
            else:
                logger.warning(msg)
            return

        # Determine Detail Level
        detail_level = 1
        if any(w in instruction for w in ["details", "explain", "more"]):
            detail_level = 2
        if any(w in instruction for w in ["raw", "ocr", "exact"]):
            detail_level = 3
            
        response = self.response_composer.compose_observation_response(last_obs, detail_level=detail_level)
        if self.chat_ui:
            self.chat_ui.log(response, "OBSERVATION")
        else:
            logger.info(f"Follow-up Response: {response}")

    def _decompose_instruction(self, instruction: str) -> List[str]:
        """
        Phase-14.2: Intent Decomposition.
        Splits compound natural language instructions into atomic sub-tasks for sequential execution.
        Respects quoted strings to prevent splitting typed text (e.g. 'type "cats and dogs"').
        """
        # Separators pattern (case insensitive)
        pattern = re.compile(r'\s+(?:and then|then|and|after that)\s+', re.IGNORECASE)
        
        # Find all candidate separators
        matches = list(pattern.finditer(instruction))
        
        if not matches:
            return [instruction]
            
        # Map quote regions to ignore separators inside them
        quote_ranges = []
        in_quote = False
        quote_char = None
        start = -1
        
        for i, char in enumerate(instruction):
            if char in ['"', "'"]:
                if not in_quote:
                    in_quote = True
                    quote_char = char
                    start = i
                elif char == quote_char:
                    in_quote = False
                    quote_ranges.append((start, i))
                    
        # Filter matches that are inside quotes
        check_points = [0]
        for m in matches:
            m_start, m_end = m.span()
            is_quoted = False
            for q_start, q_end in quote_ranges:
                if q_start < m_start and q_end > m_end: # Separator is fully inside quote
                    is_quoted = True
                    break
            
            if not is_quoted:
                check_points.append(m_start)
                check_points.append(m_end)
                
        check_points.append(len(instruction))
        
        # Reconstruct segments: [0:start1], [end1:start2], ...
        segments = []
        for i in range(0, len(check_points) - 1, 2):
            seg_start = check_points[i]
            seg_end = check_points[i+1]
            segment = instruction[seg_start:seg_end].strip()
            if segment:
                segments.append(segment)
                
        return segments

    def _detect_direct_observation(self, instruction: str) -> Optional[Observation]:
        """
        Detect if instruction is a pure observation query.
        
        Phase-11.1: Bypasses planner for simple "what do you see" queries.
        Phase-11A: Bypasses planner for state checks "is app running".
        """
        instruction_lower = instruction.lower().strip()
        
        # Phase-11.5: Market scan trigger phrases
        market_scan_triggers = [
            "scan",
            "scanner",
            "market scan",
            "scan market",
            "nifty 50",
            "bank nifty",
            "options scan",
            "ce pe"
        ]
        
        # Phase-2B: Market analysis trigger phrases (MUST be first to avoid vision fallback)
        market_analysis_triggers = [
            "analyze",
            "analyse", 
            "technical analysis",
            "chart analysis",
            "support and resistance",
            "support resistance",
            "trend analysis"
        ]
        
        # Symbol keywords to confirm it's a market request
        market_keywords = [
            "stock",
            "reliance",
            "tcs",
            "infy",
            "nifty",
            "sensex",
            "chart",
            "timeframe",
            "daily",
            "weekly"
        ]
        
        # Check if instruction matches market analysis pattern
        has_scan_trigger = any(trigger in instruction_lower for trigger in market_scan_triggers)
        has_analysis_trigger = any(trigger in instruction_lower for trigger in market_analysis_triggers)
        has_market_keyword = any(keyword in instruction_lower for keyword in market_keywords)
        
        if has_analysis_trigger and has_market_keyword:
            return Observation(
                observation_type="vision",
                context="vision",
                target=instruction
            )
        
        # Vision-only trigger phrases
        vision_triggers = [
            "what do you see",
            "what you see",  # Missing "do"
            "what are you seeing",
            "tell me what you see",
            "describe the screen",
            "describe screen",
            "what is on my screen",
            "whats on my screen",
            "what on screen",
            "analyze the chart",
            "read the screen",
            "do you see",
            "can you see"
        ]
        
        if any(trigger in instruction_lower for trigger in vision_triggers):
            return Observation(
                observation_type="vision",
                context="vision",
                target=instruction
            )
            
        # Phase-12: Vision Buffer Read Mode
        if "summarize the last vision ocr text" in instruction_lower:
            return Observation(
                observation_type="vision_buffer_read",
                context="vision_buffer",
                target=instruction
            )

        # State check triggers (Phase-11A)
        # Broader set of triggers for questions
        state_starts = ["is ", "are ", "check if ", "does "]
        
        # Must be a question or check command
        is_question = instruction_lower.endswith("?") or instruction_lower.startswith("check")
        
        if is_question and any(instruction_lower.startswith(t) for t in state_starts):
            # Heuristic to extract target app/window name
            # Remove common words to isolate target
            clean = instruction_lower
            for t in state_starts:
                if clean.startswith(t):
                    clean = clean[len(t):]
                    break
            
            remove_words = ["there a ", "the ", "window", "running", "open", "visible", "exist", "?", "dating"]
            for w in remove_words:
                clean = clean.replace(w, "")
                
            target = clean.strip()
            
            if target:
                return Observation(
                    observation_type="check_app_state",
                    context="desktop",
                    target=target
                )
            
        return None

    def _handle_descriptive_query(self, instruction: str) -> Optional[str]:
        """
        Phase-13.3: Handle descriptive questions using last visual context.
        Bypasses the action planner entirely.
        """
        # Try to get valid vision context from various sources
        last_obs = None
        
        # Source 1: Observation Logger
        if hasattr(self.observation_logger, 'get_last_successful'):
            last_obs = self.observation_logger.get_last_successful("vision")
            
        # Source 2: Dialogue State (Fallback)
        if not last_obs and self.dialogue_state.last_observation:
            if self.dialogue_state.last_observation.observation.context == "vision":
                last_obs = self.dialogue_state.last_observation

        if not last_obs:
            return "[INFO] No visual context available to describe. Try asking 'what do you see?' first."

        # Pass to interpreter
        response = self.semantic_interpreter.describe(last_obs)
        
        if self.chat_ui:
            self.chat_ui.log(response, "OBSERVATION")
        else:
            logger.info(f"Descriptive Response: {response}")
            
        return "HANDLED_INTERNALLY"

    def execute_instruction(self, instruction: str):
        """
        Execute a natural language instruction.
        
        Follows the strict execution loop:
        RESOLVE INTENT -> (SHIELDED PATH or PLANNER PATH) -> ACT -> VERIFY
        """
        logger.info(f"\n{'='*60}")
        
        # 0. CRITICAL: Resolve intent FIRST to avoid decomposition bugs
        # Market analysis instructions must NOT be decomposed
        intent, normalized_text = self.intent_resolver.resolve(instruction)
        logger.info(f"Canonical Intent: {intent.value} | Normalized: '{normalized_text}'")
        
        # 1. Check if intent should bypass decomposition
        if intent == CanonicalIntent.MARKET_SCAN:
            # Phase-11.5: Market scan is ATOMIC - never decompose
            logger.info("Routing to market scan handler (Phase-11.5, bypassing decomposition and planner)")
            self._handle_market_scan_intent(normalized_text)
            return
        
        if intent == CanonicalIntent.MARKET_ANALYSIS:
            # Market analysis is ATOMIC - never decompose
            logger.info("Routing to market analysis handler (bypassing decomposition and planner)")
            
            # Block comparison until implemented
            if "compare" in normalized_text.lower():
                msg = "Cross-analysis comparison is not yet supported. Please analyze each symbol separately."
                if self.chat_ui:
                    self.chat_ui.log(msg, "INFO")
                logger.info(msg)
                return
            
            self._handle_market_analysis_intent(normalized_text)
            return
        
        # 2. Decomposition (Recursive) - only for non-market-analysis intents
        # We must keep this to handle "Observe X and then Action Y"
        sub_instructions = self._decompose_instruction(instruction)
        if len(sub_instructions) > 1:
            logger.info(f"Decomposed compound instruction into {len(sub_instructions)} atomic tasks: {sub_instructions}")
            for idx, sub_instr in enumerate(sub_instructions):
                logger.info(f"--- Executing Sub-Task {idx+1}/{len(sub_instructions)}: '{sub_instr}' ---")
                self.execute_instruction(sub_instr) # Recursive execution
            return

        # 3. Execution Routing (intent already resolved above)
        if intent == CanonicalIntent.MARKET_SCAN:
            # Phase-11.5: Market scanner
            logger.info("Routing to market scan handler (Phase-11.5)")
            self._handle_market_scan_intent(normalized_text)
            return
        
        if intent == CanonicalIntent.OBSERVE_SCREEN:
            self._handle_observation_intent(normalized_text)
            return
        
        if intent == CanonicalIntent.MARKET_ANALYSIS:
            # Already handled above, but keep for safety
            logger.info("Routing to market analysis handler (bypassing planner)")
            self._handle_market_analysis_intent(normalized_text)
            return

        if intent == CanonicalIntent.FOLLOWUP:
            self._handle_followup_intent(normalized_text)
            return

        # Fallback/Action Path -> Planner
        # Reset instruction to normalized version if it was cleaned up
        if normalized_text:
            instruction = normalized_text
            
        logger.info(f"Routing to Planner: {instruction}")
            
        # Planner Path (Legacy Flow)
        plan_id = None  # Track for linking actions
        
        try:
            # === PHASE 1: PLAN ===
            logger.info("PHASE 1: PLAN")
            
            # Phase-5A: Create plan graph(s) with structure metadata
            plan_graphs = self.planner.create_plan_graph(instruction)
            
            # Normalize to list
            if not isinstance(plan_graphs, list):
                plan_graphs = [plan_graphs]
            
            if not plan_graphs:
                logger.error("[POLICY VIOLATION] Instruction rejected by planner - no plan generated")
                logger.error(f"INSTRUCTION FAILED: {instruction}")
                return

            logger.info(f"Plan segmented into {len(plan_graphs)} execution block(s)")
            
            # Execute each segment sequentially
            for segment_idx, plan_graph in enumerate(plan_graphs):
                if len(plan_graphs) > 1:
                    logger.info(f"\n{'='*30}")
                    logger.info(f"EXECUTING SEGMENT {segment_idx+1}/{len(plan_graphs)}")
                    logger.info(f"{'='*30}\n")
                
                # Check for empty segment
                if not plan_graph or not plan_graph.steps:
                    continue
                
                # Apply approval rules
                self._apply_approval_rules(plan_graph)
                
                # === PHASE 5B: LOG PLAN ===
                plan_approval_config = self.config.get("plan_approval", {})
                approval_enabled = plan_approval_config.get("enabled", False)
                approval_required = approval_enabled and plan_graph.approval_required
                
                # Log plan segment
                plan_id = self.plan_logger.log_plan(plan_graph, approval_required)
                logger.info(f"[PLAN] Plan Segment logged: ID={plan_id}")
                
                 # Log plan summary
                logger.info(f"Generated {len(plan_graph.steps)} item(s): {plan_graph.total_actions} action(s), {plan_graph.total_observations} observation(s)")
                
                for i, step in enumerate(plan_graph.steps, 1):
                    item = step.item
                    if isinstance(item, Action):
                        approval_marker = " [REQUIRES APPROVAL]" if step.requires_approval else ""
                        logger.info(f"  {i}. ACTION: {item.action_type} - {item.target or item.text}{approval_marker}")
                    else:
                        logger.info(f"  {i}. OBSERVE: {item.observation_type} - {item.target}")
                
                # === PHASE 5A: PLAN PREVIEW ===
                if plan_approval_config.get("show_preview", True):
                    self._display_plan_preview(plan_graph)
                
                # === PHASE 5A/5B: APPROVAL GATE ===
                if approval_required:
                    if not self._request_plan_approval(plan_graph):
                        logger.warning("Plan segment rejected by user. Aborting sequence.")
                        self.plan_logger.update_approval(
                            plan_id, 
                            approved=False, 
                            actor="local_user", 
                            timestamp=datetime.now().isoformat()
                        )
                        self.plan_logger.mark_execution_completed(
                            plan_id,
                            timestamp=datetime.now().isoformat(),
                            status="cancelled"
                        )
                        return 
                    
                    # Update approval status in DB
                    self.plan_logger.update_approval(
                        plan_id, 
                        approved=True, 
                        approved_by="user", 
                        approved_at=datetime.now()
                    )
                
                # === PHASE 3: ACT ===
                logger.info(f"PHASE 3: ACT (Segment {segment_idx+1})")
                
                # === PHASE 5B: MARK EXECUTION STARTED ===
                self.plan_logger.mark_execution_started(plan_id, datetime.now().isoformat())
                
                # === EXECUTE PLAN ===
                observation_results = []
                for i, step in enumerate(plan_graph.get_execution_order(), 1):
                    item = step.item
                    logger.info(f"\n--- Executing Item {i}/{len(plan_graph.steps)} ---")
                    
                    # === PHASE 6A: STEP-LEVEL APPROVAL GATE ===
                    if step.requires_approval:
                        decision = self._request_step_approval(step, plan_id)
                        
                        if decision == 'rejected':
                            self.plan_logger.mark_execution_completed(
                                plan_id,
                                timestamp=datetime.now().isoformat(),
                                status="cancelled"
                            )
                            logger.warning(f"Step {step.step_id} rejected by user. Plan cancelled.")
                            if self.chat_ui:
                                self.chat_ui.log(f"[INFO] Step {step.step_id} rejected - Plan cancelled", "INFO")
                                self.chat_ui.set_status("Cancelled")
                            return
                        
                        elif decision == 'skipped':
                            logger.info(f"Step {step.step_id} skipped by user")
                            if self.chat_ui:
                                self.chat_ui.log(f"[INFO] Step {step.step_id} skipped", "INFO")
                            continue
                    
                    if isinstance(item, Action):
                        success = self._execute_single_action(item, action_index=i, plan_id=plan_id)
                        
                        if not success:
                            # Action failed - mark plan as failed
                            self.plan_logger.mark_execution_completed(
                                plan_id,
                                timestamp=datetime.now().isoformat(),
                                status="failed"
                            )
                            
                            # Determine reason and abort plan
                            if self.last_failure_reason == 'verification_failed':
                                logger.error(f"Action {i} failed due to verification failure. Aborting plan.")
                                if self.chat_ui:
                                    self.chat_ui.log(f"[FAIL] Plan aborted: Action {i} failed verification", "ERROR")
                            else:
                                logger.error(f"Action {i} failed after retry. Aborting plan.")
                                if self.chat_ui:
                                    self.chat_ui.log(f"[FAIL] Plan aborted: Action {i} failed after retry", "ERROR")
                            
                            if self.chat_ui:
                                self.chat_ui.set_status("Failed")
                            return
                    else:
                        # Execute observation
                        obs_result = self._execute_single_observation(item, obs_index=i)
                        observation_results.append(obs_result)
            
            # === PHASE 5B: MARK EXECUTION COMPLETED ===
            if plan_id:
                self.plan_logger.mark_execution_completed(
                    plan_id,
                    timestamp=datetime.now().isoformat(),
                    status="completed"
                )
            
            # Final success
            logger.info(f"\n{'='*60}")
            logger.info("INSTRUCTION COMPLETED SUCCESSFULLY")
            logger.info(f"{'='*60}\n")
            
            # Phase-12: Update Dialogue State
            completion_msg = "Actions completed successfully."
            if observation_results:
                completion_msg = f"Completed with {len(observation_results)} observations."
            self.dialogue_state.update_interaction(instruction, intent.value, completion_msg)
            
             # Display observation results to user
            if observation_results:
                logger.info("\nObservation Results:")
                for obs_result in observation_results:
                    obs = obs_result.observation
                    if obs_result.status == "success":
                        # Phase-UI-A/C: Use ResponseComposer
                        fmt_obs = self.response_composer.compose_observation_response(obs_result)
                        logger.info(f"  [OK] {obs.target}: {obs_result.result}")
                        if self.chat_ui:
                            self.chat_ui.log(fmt_obs, "OBSERVATION")
                    else:
                        logger.warning(f"  [FAIL] {obs.observation_type}({obs.target}): {obs_result.error}")
                        if self.chat_ui:
                            self.chat_ui.log(f"⚠ {obs.observation_type}({obs.target}): {obs_result.error}", "WARNING")
            
            if self.chat_ui:
                self.chat_ui.log("[OK] Instruction completed successfully", "SUCCESS")
                self.chat_ui.set_status("Success")
        
        except ValueError as e:
            logger.error(f"Planning failed: {e}")
            if self.chat_ui:
                self.chat_ui.log(f"[FAIL] Planner could not generate a safe plan: {e}", "ERROR")
                self.chat_ui.set_status("Error")
            if plan_id:
                self.plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), status="failed")
        
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"[FAIL] Execution failed: {e}", "ERROR")
                self.chat_ui.set_status("Error")
            if plan_id:
                self.plan_logger.mark_execution_completed(plan_id, datetime.now().isoformat(), status="failed")

    def _execute_single_action(
        self, action: Action, action_index: int = 1, attempt: int = 1, plan_id: Optional[int] = None
    ) -> bool:
        """Execute a single action through the full loop with retry support."""
        attempt_label = f"Attempt {attempt}/2" if attempt > 1 else ""
        if attempt_label:
            logger.info(f"RETRY: {attempt_label}")
            if self.chat_ui:
                self.chat_ui.log(f"⟳ Retry: {attempt_label}", "WARNING")
        
        # === PHASE 2: POLICY CHECK ===
        logger.info("PHASE 2: POLICY CHECK")
        approved, reason = self.policy_engine.validate_action(action)
        
        if not approved:
            logger.error(f"[FAIL] POLICY DENIED: {reason}")
            if self.chat_ui:
                self.chat_ui.log(f"[FAIL] Policy denied: {reason}", "ERROR")
            
            # Log the denial
            denial_result = ActionResult(
                action=action,
                success=False,
                message="Policy denial",
                error=reason
            )
            self.action_logger.log_action(denial_result, plan_id=plan_id)
            raise PermissionError(f"Policy denied: {reason}")
        
        logger.info(f"[OK] APPROVED: {action.action_type}")
        if self.chat_ui:
            self.chat_ui.log(f"[OK] Policy approved: {action.action_type}", "INFO")
        
        # === PHASE 3: ACT ===
        logger.info("PHASE 3: ACT")
        exec_result = self.controller.execute_action(action)
        
        if not exec_result.success:
            logger.error(f"[FAIL] EXECUTION FAILED: {exec_result.error}")
            if self.chat_ui:
                self.chat_ui.log(f"[FAIL] Execution failed: {exec_result.error}", "ERROR")
            
            self.action_logger.log_action(exec_result, plan_id=plan_id)
            raise RuntimeError(f"Execution failed: {exec_result.error}")
        
        logger.info(f"[OK] EXECUTED: {exec_result.message}")
        if self.chat_ui:
            self.chat_ui.log(f"-> Executed: {exec_result.message}", "INFO")
        
        # === PHASE 4: VERIFY ===
        logger.info("PHASE 4: VERIFY")
        verify_result = self.critic.verify_action(action)
        
        # Log verification evidence
        if hasattr(verify_result, 'verification_evidence') and verify_result.verification_evidence:
            evidence = verify_result.verification_evidence
            logger.info(f"[EVIDENCE] Source: {evidence.get('source', 'UNKNOWN')}, "
                       f"Checked: '{evidence.get('checked_text', 'N/A')}', "
                       f"Confidence: {evidence.get('confidence', 0.0):.2f}")
            if evidence.get('sample'):
                logger.info(f"[EVIDENCE] Sample: {evidence['sample'][:100]}...")
        
        if not verify_result.success:
            logger.error(f"[FAIL] VERIFICATION FAILED: {verify_result.error}")
            if self.chat_ui:
                self.chat_ui.log(f"[FAIL] Verification failed: {verify_result.message}", "WARNING")
            
            self.action_logger.log_action(verify_result, plan_id=plan_id)
            
            # Check for terminal failure
            if hasattr(verify_result, 'reason') and verify_result.reason == 'verification_failed':
                logger.error("Verification failed. This is a terminal failure (no retry allowed).")
                if self.chat_ui:
                    self.chat_ui.log(f"[FAIL] Verification failed (terminal - no retry)", "ERROR")
                self.last_failure_reason = 'verification_failed'
                return False
            
            if hasattr(action, 'verify') and action.verify:
                logger.error("Verification action failed. Retries forbidden for verification failures.")
                if self.chat_ui:
                    self.chat_ui.log(f"[FAIL] Verification failed (no retry for verification actions)", "ERROR")
                self.last_failure_reason = 'verification_failed'
                return False
            
            # Retry logic
            if attempt == 1:
                logger.warning("Verification failed. Retrying action once...")
                if self.chat_ui:
                    self.chat_ui.log("[Retry] Retrying action...", "WARNING")
                return self._execute_single_action(action, action_index, attempt=2, plan_id=plan_id)
            else:
                logger.error(f"Action failed after {attempt} attempts. Aborting.")
                if self.chat_ui:
                    self.chat_ui.log(f"[FAIL] Action failed after retry", "ERROR")
                self.last_failure_reason = 'retry_exhausted'
                return False
        
        logger.info(f"[OK] VERIFIED: {verify_result.message}")
        if self.chat_ui:
            self.chat_ui.log(f"[OK] Verified: {verify_result.message}", "SUCCESS")
        
        # === PHASE 5: COMMIT ===
        logger.info("PHASE 5: COMMIT")
        self.action_logger.log_action(verify_result, plan_id=plan_id)
        logger.info("[OK] COMMITTED to action history")
        
        return True

    def _execute_single_observation(self, observation: Observation, obs_index: int = 1):
        """Execute a single observation query."""
        logger.info(f"OBSERVE: {observation.observation_type} (context={observation.context}, target={observation.target})")
        
        obs_result = self.observer.observe(observation)
        self.observation_logger.log_observation(obs_result)
        
        if obs_result.status == "success":
            logger.info(f"[OK] OBSERVED: {obs_result.result}")
            # Phase-12: Update memory for follow-up resolution
            self.dialogue_state.update_observation(obs_result)
            
            # Phase-UI-A: Defer UI logging to the main loop final summary or direct routing.
            pass
        else:
            logger.warning(f"[WARN] OBSERVE FAILED: {obs_result.error}")
            if self.chat_ui:
                self.chat_ui.log(f"⚠ Observe failed: {obs_result.error}", "WARNING")
        
        return obs_result

    def _apply_approval_rules(self, plan_graph: PlanGraph):
        """Apply approval rules to plan graph."""
        plan_approval_config = self.config.get("plan_approval", {})
        
        if not plan_approval_config.get("enabled", False):
            return
        
        require_approval_for = plan_approval_config.get("require_approval_for", [])
        
        for step in plan_graph.steps:
            if step.is_action:
                action = step.item
                if action.action_type in require_approval_for:
                    step.requires_approval = True
                    logger.debug(f"Step {step.step_id} ({action.action_type}) marked for approval")

    def _display_plan_preview(self, plan_graph: PlanGraph):
        """Display plan preview to user."""
        print()
        print(plan_graph.to_display_tree())
        print()

    def _request_plan_approval(self, plan_graph: PlanGraph) -> bool:
        """Request user approval for plan execution using ChatUI if available, else CLI."""
        approval_steps = plan_graph.get_approval_steps()
        
        logger.info(f"Requesting approval for plan with {len(approval_steps)} critical steps")
        
        # In a real UI, this would be synchronous or callback-based. 
        # For now, if ChatUI doesn't support interactive prompt, fallback to CLI
        # But wait, ChatUI runs in a separate Qt thread. 
        # Using input() blocks the main thread, which is where this logic runs.
        # So CLI input is actually fine for now as long as we run from terminal.
        
        print(f"⚠️  This plan requires approval ({len(approval_steps)} step(s) marked).")
        print(f"   Approval-required steps:")
        for step in approval_steps:
            print(f"     - Step {step.step_id}: {step.item.action_type} ({step.intent})")
        print()
        
        while True:
            response = input("Approve this plan? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                logger.info("Plan approved by user")
                return True
            elif response in ['n', 'no']:
                logger.info("Plan rejected by user")
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")

    def _request_step_approval(self, step, plan_id: int) -> str:
        """Request user approval for individual step execution."""
        item = step.item
        item_type = item.action_type if step.is_action else item.observation_type
        
        print(f"\n⚠️  Step {step.step_id} requires approval:")
        print(f"   Type: {item_type}")
        print(f"   Intent: {step.intent}")
        print(f"   Expected: {step.expected_outcome}")
        print()
        
        while True:
            response = input("Decision? (approve/skip/reject): ").strip().lower()
            if response in ['approve', 'a']:
                decision = 'approved'
                break
            elif response in ['skip', 's']:
                decision = 'skipped'
                break
            elif response in ['reject', 'r']:
                decision = 'rejected'
                break
            else:
                print("Invalid input. Please enter 'approve', 'skip', or 'reject'.")
        
        timestamp = datetime.now().isoformat()
        self.step_approval_logger.log_step_decision(
            plan_id=plan_id,
            step_id=step.step_id,
            decision=decision,
            timestamp=timestamp
        )
        
        logger.info(f"[STEP APPROVAL] Step {step.step_id}: {decision}")
        return decision
    
    def _display_market_scenarios(
        self,
        monthly_data: Optional[Dict],
        weekly_data: Optional[Dict],
        daily_data: Optional[Dict],
        dominant_tf: str,
        alignment: str
    ):
        """Delegate to extracted MarketDisplayEngine."""
        self.market_display.display_market_scenarios(
            monthly_data, weekly_data, daily_data, dominant_tf, alignment
        )
    
    def _display_price_zones(
        self,
        monthly_data: Optional[Dict],
        weekly_data: Optional[Dict],
        daily_data: Optional[Dict],
        monthly_trend: str
    ):
        """Delegate to extracted MarketDisplayEngine."""
        self.market_display.display_price_zones(
            monthly_data, weekly_data, daily_data, monthly_trend
        )
