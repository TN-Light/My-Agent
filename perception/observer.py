"""
Observer - Phase-2B Non-Actional State Reader
Routes observation requests to appropriate perception clients.

Phase-2B: Read-only operations, no side effects, no retries.
Uses existing authority hierarchy (Accessibility > DOM > File).
"""
import logging
from datetime import datetime
from typing import Optional
from common.observations import Observation, ObservationResult
from logic.vision_semantic_interpreter import VisionSemanticInterpreter

logger = logging.getLogger(__name__)


class Observer:
    """
    Non-actional state observer.
    
    Routes observation requests by context to appropriate perception clients:
    - desktop → AccessibilityClient (Windows UIA)
    - web → BrowserHandler (Playwright DOM)
    - file → FileHandler (workspace file reads)
    - vision → VisionClient + ScreenCapture (Phase-2C Level 4, Phase-3A Level 3)
    
    Phase-2C vision (Level 4): Basic vision observations
    Phase-3A visual scaffolding (Level 3): Structured layout understanding
    
    Vision constraints:
    - Vision is advisory only (observation-only)
    - Vision never triggers actions
    - Returns structured ObservationResult
    """
    
    def __init__(self, accessibility_client=None, browser_handler=None, file_handler=None, 
                 vision_client=None, screen_capture=None, action_logger=None, dialogue_state=None):
        """
        Initialize the observer.
        
        Args:
            accessibility_client: AccessibilityClient instance for desktop observations
            browser_handler: BrowserHandler instance for web observations
            file_handler: FileHandler instance for file observations
            vision_client: VisionClient instance for vision observations (Phase-2C)
            screen_capture: ScreenCapture instance for screen capture (Phase-2C)
            action_logger: ActionLogger instance for context-aware selection (Phase-10E)
            dialogue_state: DialogueState instance for session state (Phase-12)
        """
        self.accessibility_client = accessibility_client
        self.browser_handler = browser_handler
        self.file_handler = file_handler
        self.vision_client = vision_client
        self.screen_capture = screen_capture
        self.action_logger = action_logger
        self.dialogue_state = dialogue_state
        self.interpreter = VisionSemanticInterpreter()
        
        phase = "Phase-2C" if vision_client else "Phase-2B"
        logger.info(f"Observer initialized ({phase})")
    
    def observe(self, observation: Observation) -> ObservationResult:
        """
        Execute an observation request.
        
        Routes by context to appropriate handler. Never throws exceptions;
        returns ObservationResult with error status on failure.
        
        Args:
            observation: Observation to execute
            
        Returns:
            ObservationResult with status and optional result/error
        """
        logger.info(
            f"Observing: {observation.observation_type} "
            f"(context={observation.context}, target={observation.target})"
        )
        
        try:
            # Route by context
            if observation.context == "vision_buffer":
                # Phase-12: Vision Buffer Read Mode
                return self._observe_vision_buffer(observation)
            elif observation.context == "desktop":
                return self._observe_desktop(observation)
            elif observation.context == "web":
                return self._observe_web(observation)
            elif observation.context == "file":
                return self._observe_file(observation)
            elif observation.context == "vision":
                return self._observe_vision(observation)
            else:
                # Should never reach here due to Observation validation
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error=f"Unknown context: {observation.context}",
                    timestamp=datetime.now().isoformat()
                )
        
        except Exception as e:
            logger.error(f"Observation failed: {e}", exc_info=True)
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def _observe_vision_buffer(self, observation: Observation) -> ObservationResult:
        """
        Execute vision buffer observation (Phase-12).
        Reads directly from last successful vision capture.
        """
        if not self.dialogue_state:
             return ObservationResult(
                observation=observation,
                status="error",
                error="Session state not initialized (no dialogue_state)",
                timestamp=datetime.now().isoformat()
            )
            
        last_obs = self.dialogue_state.last_observation
        if not last_obs or not last_obs.metadata or "raw_ocr" not in last_obs.metadata:
            return ObservationResult(
                observation=observation,
                status="not_found",
                error="No previous vision buffer available to read",
                timestamp=datetime.now().isoformat()
            )
            
        raw_text = last_obs.metadata["raw_ocr"]
        # Fallback for old buffers that might not have window_title
        window_title = last_obs.metadata.get("window_title", "Unknown Context")
        
        # Re-interpret the raw buffer text
        interpretation = self.interpreter.interpret(raw_text, window_title)
        
        display_text = f"**Vision Buffer Summary** (Reading from previous capture)\n{interpretation['summary']}\n"
        if interpretation['key_elements']:
            elements_str = ", ".join(interpretation['key_elements'])
            display_text += f"\n**Key Elements:** {elements_str}\n"

        if interpretation.get('safe_suggestion'):
             display_text += f"\n_{interpretation['safe_suggestion']}_"

        return ObservationResult(
            observation=observation,
            status="success",
            result=display_text,
            metadata={
                "confidence": 1.0, # Buffer read is 100% confident relative to source
                "source": "vision_buffer",
                "advisory_only": True,
                "raw_ocr": raw_text,
                "interpretation": interpretation
            },
            timestamp=datetime.now().isoformat()
        )

    def _observe_desktop(self, observation: Observation) -> ObservationResult:
        """
        Execute desktop observation using Accessibility Tree.
        
        Args:
            observation: Observation with context="desktop"
            
        Returns:
            ObservationResult
        """
        if not self.accessibility_client:
            return ObservationResult(
                observation=observation,
                status="error",
                error="AccessibilityClient not initialized",
                timestamp=datetime.now().isoformat()
            )
        
        try:
            if observation.observation_type == "read_text":
                # Read text from focused window or specific element
                if observation.target == "window_title":
                    # Get focused window title
                    focused = self.accessibility_client.get_focused_window()
                    if focused and hasattr(focused, 'window_text'):
                        return ObservationResult(
                            observation=observation,
                            status="success",
                            result=focused.window_text(),
                            timestamp=datetime.now().isoformat()
                        )
                    else:
                        return ObservationResult(
                            observation=observation,
                            status="not_found",
                            error="No focused window",
                            timestamp=datetime.now().isoformat()
                        )
                else:
                    # Try to find element by name and read its text
                    element = self.accessibility_client.find_element_by_name(observation.target)
                    if element and hasattr(element, 'window_text'):
                        return ObservationResult(
                            observation=observation,
                            status="success",
                            result=element.window_text(),
                            timestamp=datetime.now().isoformat()
                        )
                    else:
                        return ObservationResult(
                            observation=observation,
                            status="not_found",
                            error=f"Element not found: {observation.target}",
                            timestamp=datetime.now().isoformat()
                        )
            
            elif observation.observation_type == "query_element":
                # Check if element exists
                element = self.accessibility_client.find_element_by_name(observation.target)
                if element:
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=f"Element exists: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    return ObservationResult(
                        observation=observation,
                        status="not_found",
                        error=f"Element not found: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )

            elif observation.observation_type == "observe_dialog":
                # Phase-4C: Check for active dialog state (e.g. Save As)
                logger.info("Observing active dialog state")
                if not getattr(self.accessibility_client, "find_child_window", None):
                    return ObservationResult(observation=observation, status="error", error="UIA not ready")
                
                # We need the parent app context from somewhere, or check focused window
                focused = self.accessibility_client.get_focused_window()
                buttons = []
                dialog_type = "unknown"
                
                if focused:
                    # Is the focused window itself a dialog (or child)?
                     # Simplified: just dump buttons/text of focused window to classify
                     # Using accessibility client helper if available or implementing minimal one here
                     # Using `get_dialog_element_names` we defined earlier
                     if hasattr(self.accessibility_client, "get_dialog_element_names"):
                         elements = self.accessibility_client.get_dialog_element_names(focused.handle) # UIElement doesn't have handle in dataclass unless we added it?
                         # Let's assume focused window is relevant
                         buttons = [e for e in elements if "Button" in e] # Basic heuristic based on string format
                         
                         if any("Save" in b for b in buttons) and any("Cancel" in b for b in buttons):
                             dialog_type = "save_file"
                         elif any("Don't Save" in b or "Don't save" in b for b in buttons):
                             dialog_type = "close_confirmation"
                
                return ObservationResult(
                    observation=observation,
                    status="success",
                    result=dialog_type,
                    timestamp=datetime.now().isoformat()
                )

            elif observation.observation_type == "check_app_state":
                # Phase-11A: Check if app/window exists
                target_name = observation.target
                exists = False
                title = ""
                
                # Try simple window find
                try:
                    window = self.accessibility_client.find_window(target_name)
                    if window:
                        exists = True
                        title = window.name
                except Exception:
                    exists = False
                
                if exists:
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=f"Yes, {target_name} is running (Title: {title})",
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    return ObservationResult(
                        observation=observation,
                        status="not_found",
                        result=f"No, {target_name} is not running or visible.",
                        timestamp=datetime.now().isoformat()
                    )
            
            else:
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error=f"Unsupported observation type: {observation.observation_type}",
                    timestamp=datetime.now().isoformat()
                )
        
        except Exception as e:
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def _observe_web(self, observation: Observation) -> ObservationResult:
        """
        Execute web observation using Playwright DOM.
        
        Args:
            observation: Observation with context="web"
            
        Returns:
            ObservationResult
        """
        if not self.browser_handler:
            return ObservationResult(
                observation=observation,
                status="error",
                error="BrowserHandler not initialized",
                timestamp=datetime.now().isoformat()
            )
        
        try:
            if observation.observation_type == "read_text":
                # Extract text from CSS selector
                text = self.browser_handler.get_element_text(observation.target)
                if text is not None:
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=text,
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    return ObservationResult(
                        observation=observation,
                        status="not_found",
                        error=f"Element not found: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
            
            elif observation.observation_type == "query_element":
                # Check if element is visible
                visible = self.browser_handler.is_element_visible(observation.target)
                if visible:
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=f"Element visible: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    return ObservationResult(
                        observation=observation,
                        status="not_found",
                        error=f"Element not visible: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
            
            else:
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error=f"Unsupported observation type: {observation.observation_type}",
                    timestamp=datetime.now().isoformat()
                )
        
        except Exception as e:
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def _observe_file(self, observation: Observation) -> ObservationResult:
        """
        Execute file observation using FileHandler.
        
        Args:
            observation: Observation with context="file"
            
        Returns:
            ObservationResult
        """
        if not self.file_handler:
            return ObservationResult(
                observation=observation,
                status="error",
                error="FileHandler not initialized",
                timestamp=datetime.now().isoformat()
            )
        
        try:
            if observation.observation_type == "read_text":
                # Read file contents using new read_file_content method (Phase-2B)
                content = self.file_handler.read_file_content(observation.target)
                return ObservationResult(
                    observation=observation,
                    status="success",
                    result=content,
                    timestamp=datetime.now().isoformat()
                )
            
            elif observation.observation_type == "query_element":
                # Check if file exists
                exists = self.file_handler.file_exists(observation.target)
                if exists:
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=f"File exists: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
                else:
                    return ObservationResult(
                        observation=observation,
                        status="not_found",
                        error=f"File not found: {observation.target}",
                        timestamp=datetime.now().isoformat()
                    )
            
            else:
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error=f"Unsupported observation type for file context: {observation.observation_type}",
                    timestamp=datetime.now().isoformat()
                )
        
        except Exception as e:
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )
    
    def _observe_vision(self, observation: Observation) -> ObservationResult:
        """
        Execute vision observation using VLM.
        
        Phase-10: Safe Mode Upgrade.
        - Strict Confidence Cap (0.7)
        - Read-Only Evidence Collection
        - Structured Metadata
        
        Args:
            observation: Observation with context="vision"
            
        Returns:
            ObservationResult with confidence metadata
        """
        if not self.vision_client or not self.screen_capture:
            return ObservationResult(
                observation=observation,
                status="error",
                error="VisionClient not initialized",
                timestamp=datetime.now().isoformat()
            )
        
        try:
            import time
            max_attempts = 3
            last_result = None
            
            for attempt in range(max_attempts):
                # Phase-10E: Intent-Aware Window Selection
                screenshot = None
                window_title = "Unknown"
                prompt_lower = observation.target.lower() if observation.target else ""
                
                # Helper to unpack potential tuple return from capture methods
                def unpack_capture(result):
                    if isinstance(result, tuple):
                        return result[0], result[1]
                    return result, "Active Window"

                # 1. Intent-Based Selection
                if "code" in prompt_lower or "editor" in prompt_lower:
                    hwnd = self.screen_capture.find_window_by_title("Visual Studio Code")
                    if hwnd: 
                        res = self.screen_capture.capture_window_handle(hwnd)
                        screenshot, window_title = unpack_capture(res)

                elif any(kw in prompt_lower for kw in ("browser", "edge", "chart", "tradingview",
                                                        "stock", "support/resistance", "momentum",
                                                        "trend", "candlestick", "price")):
                    # Chart analysis keywords → find the TradingView browser window
                    # Priority: 1) Window with symbol in title, 2) TradingView, 3) Any Edge/Chrome
                    hwnd = None
                    
                    # Extract symbol from observation target (e.g., "Analyze TATACHEM chart...")
                    import re
                    symbol_match = re.search(r'Analyze\s+(\S+)\s+chart', observation.target or "", re.IGNORECASE)
                    if symbol_match:
                        symbol_in_target = symbol_match.group(1)
                        hwnd = self.screen_capture.find_window_by_title(symbol_in_target)
                    
                    if not hwnd:
                        hwnd = self.screen_capture.find_window_by_title("TradingView")
                    if not hwnd:
                        hwnd = self.screen_capture.find_window_by_title("Edge")
                    if not hwnd:
                        hwnd = self.screen_capture.find_window_by_title("Chrome")
                    if hwnd: 
                        res = self.screen_capture.capture_window_handle(hwnd)
                        screenshot, window_title = unpack_capture(res)
                
                # 2. Context-Based Selection (Last Interaction)
                if not screenshot and self.action_logger:
                    recent = self.action_logger.get_recent_actions(limit=1)
                    if recent and recent[0]["success"]:
                        # Try to infer app from last action logic (Phase-10E+: Needs structured target tracking)
                        pass

                # 3. Last Resort: Active App (Foreground non-agent)
                if not screenshot:
                    # Exclusion: "My Agent" targets the ChatUI window and any agent-related windows.
                    # "Visual Studio Code" is preserved because its title format is distinct.
                    res = self.screen_capture.capture_active_app(exclude_titles=["My Agent"])
                    screenshot, window_title = unpack_capture(res)
                
                if not screenshot:
                    # Final Fallback: Full screen
                    res = self.screen_capture.capture_full_screen()
                    screenshot, window_title = unpack_capture(res)
                    if window_title == "Active Window": window_title = "Full Screen"
                
                if not screenshot:
                    return ObservationResult(
                        observation=observation,
                        status="error",
                        error="Failed to capture screen",
                        timestamp=datetime.now().isoformat()
                    )
                
                # Phase-13.1.1: UIA-Guided Viewport Isolation
                # Crop screenshot to document body if possible (cleaner OCR)
                if self.accessibility_client:
                    doc_bbox = self.accessibility_client.get_document_content_bbox(window_title)
                    if doc_bbox:
                        hwnd_target = self.screen_capture.find_window_by_title(window_title)
                        if hwnd_target:
                            win_rect = self.screen_capture.get_window_rect(hwnd_target)
                            if win_rect[2] > win_rect[0] and win_rect[3] > win_rect[1]:
                                doc_left, doc_top, doc_right, doc_bottom = doc_bbox
                                win_left, win_top, win_right, win_bottom = win_rect
                                
                                rel_left = max(0, doc_left - win_left)
                                rel_top = max(0, doc_top - win_top)
                                rel_right = min(screenshot.width, doc_right - win_left)
                                rel_bottom = min(screenshot.height, doc_bottom - win_top)
                                
                                if rel_right > rel_left and rel_bottom > rel_top:
                                    # Phase-13.3 - Viewport Qualification Rule 1 (Client Side)
                                    crop_h = rel_bottom - rel_top
                                    crop_w = rel_right - rel_left
                                    
                                    # Strict check for VS Code tab bars (often ~20-30px)
                                    if crop_h < 100:
                                        logger.warning(f"Cropped region too small ({crop_w}x{crop_h}). Falling back to full capture.")
                                        # Do NOT crop. Keep full screenshot.
                                        pass 
                                    else:
                                        logger.info(f"Cropping to document viewport: {rel_left},{rel_top},{rel_right},{rel_bottom} ({crop_w}x{crop_h})")
                                        screenshot = screenshot.crop((rel_left, rel_top, rel_right, rel_bottom))
                                
                                    # Phase-13.3 Rule 3: Fallback Logic
                                    # If UIA failed (doc_bbox was None) or crop rejected, we are here with full screenshot.
                                    # (screenshot variable is intact)
                    
                    # Phase-13.3 Rule 3 (Active Fallback)
                    # If we still have a full screenshot and target suggests code/editor
                    # We can try a "Center Focus" crop if UIA failed
                    # (Implementation deferred to avoid breaking generic cases, standard fallback is full screen)
                
                # Phase-14: Chart-Area Isolation
                # When analyzing charts, crop browser chrome (tabs, address bar, bookmarks)
                # to give the VLM a cleaner chart-only image
                chart_keywords = ("chart", "support/resistance", "momentum", "trend", "candlestick")
                if any(kw in prompt_lower for kw in chart_keywords) and screenshot:
                    w, h = screenshot.size
                    # Browser chrome is typically 100-140px at the top (title bar + tabs + address/bookmarks)
                    # TradingView toolbar at bottom is ~30px
                    # Only crop if image is large enough to have meaningful chrome
                    if h > 400:
                        chrome_top = int(h * 0.12)    # ~12% top = browser chrome
                        chrome_bottom = int(h * 0.97)  # ~3% bottom = status bar
                        screenshot = screenshot.crop((0, chrome_top, w, chrome_bottom))
                        logger.info(f"Phase-14: Cropped browser chrome for chart analysis: {w}x{h} → {screenshot.size[0]}x{screenshot.size[1]}")
                
                # Phase-10: Use analyze_screen which returns structured dict
                # observation.target is treated as the prompt/query
                prompt = observation.target
                # Phase-13.2: Pass context_key (window_title) for temporal buffering
                result = self.vision_client.analyze_screen(screenshot, prompt, context_key=window_title)
                last_result = result
                
                # Burst Mode Logic: If result is "stabilizing", retry
                if isinstance(result, dict) and result.get("source") == "ocr_temporal_stabilizing":
                    if attempt < max_attempts - 1:
                        logger.info(f"Vision signal stabilizing ({attempt+1}/{max_attempts}). Retrying...")
                        time.sleep(0.3)
                        continue
                
                # If stable, break loop
                break

            result = last_result
            
            # Case 1: Structured Dict Response (Phase-10B standard)
            if isinstance(result, dict):
                text = result.get("text", "")
                confidence = result.get("confidence", 0.5)
                source = result.get("source", "vision_llm")
                
                # Phase-14: Direct VLM response handling
                # If source is VLM, use the response directly without re-interpretation
                if source == "vlm":
                    return ObservationResult(
                        observation=observation,
                        status="success",
                        result=text,  # VLM response is already semantic
                        metadata={
                            "confidence": confidence,
                            "source": source,
                            "advisory_only": True,
                            "window_title": window_title
                        },
                        timestamp=datetime.now().isoformat()
                    )
                
                # Phase-13: Semantic Interpretation (for OCR only)
                # Pass both OCR text and Window Title to the interpreter
                interpretation = self.interpreter.interpret(text, window_title)
                
                # Format final display string
                display_text = f"**Vision Summary ({interpretation['context_type']})**\n{interpretation['summary']}\n"
                
                if interpretation['key_elements']:
                    elements_str = ", ".join(interpretation['key_elements'])
                    display_text += f"\n**Key Elements:** {elements_str}\n"

                if interpretation.get('safe_suggestion'):
                    display_text += f"\n_{interpretation['safe_suggestion']}_"
                
                # We store the raw OCR in metadata, not in the primary result string
                # to prevent UI clutter.
                return ObservationResult(
                    observation=observation,
                    status="success",
                    result=display_text,
                    metadata={
                        "confidence": confidence,
                        "source": source,
                        "advisory_only": True,
                        "raw_ocr": text, # Raw text preserved here
                        "window_title": window_title,
                        "interpretation": interpretation
                    },
                    timestamp=datetime.now().isoformat()
                )
            
            # Case 2: Legacy String Response
            elif isinstance(result, str) and result.strip():
                 return ObservationResult(
                    observation=observation,
                    status="success",
                    result=result,
                    metadata={
                        "confidence": 0.5,
                        "source": "vision_llm",
                        "advisory_only": True
                    },
                    timestamp=datetime.now().isoformat()
                )

            # Case 3: Empty or Invalid Result
            return ObservationResult(
                observation=observation,
                status="not_found",
                error="Vision analysis returned no result",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Vision observation failed: {e}")
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )    
    def _observe_market_analysis(self, observation: Observation) -> ObservationResult:
        """
        Execute market analysis observation (Phase-2B).
        Read-only chart analysis using vision.
        
        Args:
            observation: Market analysis observation
            
        Returns:
            ObservationResult with chart analysis
        """
        if not self.vision_client or not self.screen_capture:
            return ObservationResult(
                observation=observation,
                status="error",
                error="Vision or screen capture not available",
                timestamp=datetime.now().isoformat()
            )
        
        logger.info("Observing market analysis (chart vision)")
        
        try:
            # Capture current screen
            capture_result = self.screen_capture.capture_active_app(
                exclude_titles=["My Agent"]
            )
            
            if not capture_result or not capture_result.get("image"):
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error="Failed to capture chart screen",
                    timestamp=datetime.now().isoformat()
                )
            
            image = capture_result["image"]
            window_title = capture_result.get("window_title", "Unknown")
            
            # Use vision to analyze chart with special prompt
            description = self.vision_client.describe_screen(
                image,
                target=observation.target,
                analysis_type="chart_technical"
            )
            
            if not description:
                return ObservationResult(
                    observation=observation,
                    status="error",
                    error="Vision analysis failed",
                    timestamp=datetime.now().isoformat()
                )
            
            return ObservationResult(
                observation=observation,
                status="success",
                result=description,
                metadata={
                    "source": "vision",
                    "window_title": window_title,
                    "analysis_type": "chart_technical",
                    "advisory_only": True
                },
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Market analysis observation failed: {e}", exc_info=True)
            return ObservationResult(
                observation=observation,
                status="error",
                error=str(e),
                timestamp=datetime.now().isoformat()
            )