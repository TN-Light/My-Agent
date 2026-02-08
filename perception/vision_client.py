"""
Vision Client - Phase-2C/3A/3B Ollama VLM Integration
Connects to Ollama vision models for screen analysis (observation only).

Phase-2C: Vision is Level 4 authority - advisory output only, never authoritative.
Phase-3A: Visual Scaffolding (Level 3) - structured layout understanding.
Phase-3B: Vision-Assisted Verification - verification fallback only, no actions.
"""
import logging
import base64
import io
import requests
from typing import Optional, Dict, Any, Union
from PIL import Image
from perception.temporal_buffer import TemporalTextBuffer

try:
    import pytesseract
    from pytesseract import pytesseract as _pt
    _pt.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    pytesseract.pandas_available = False
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to import pytesseract: {e}")
    pytesseract = None

logger = logging.getLogger(__name__)


class VisionClient:
    """
    Ollama VLM client for vision-based observations.
    
    Phase-2C: Vision output is advisory only. Used for:
    - Screen description
    - Text recognition (OCR fallback)
    - Element detection proposals
    
    Phase-10B: Basic Vision Signal (OCR-only)
    - Uses pytesseract for text extraction
    - Bypasses VLM for speed/stability in Safe Mode
    
    Vision NEVER:
    - Triggers actions directly
    - Overrides DOM/UIA authority
    - Provides click coordinates (for execution)
    """

    # Phase-10: Max confidence cap for vision-only observations
    MAX_CONFIDENCE = 0.7
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2-vision", timeout: int = 60):
        """
        Initialize the vision client.
        
        Args:
            base_url: Ollama API endpoint
            model: VLM model name (llama3.2-vision, qwen2.5-vl, etc.)
            timeout: Request timeout in seconds (VLMs are slow)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        
        # Phase-13.2: Temporal Buffering
        # Map: context_key (window_title) -> TemporalTextBuffer
        self.buffers: Dict[str, TemporalTextBuffer] = {}
        
        # Test connection
        if not self._test_connection():
            logger.warning(
                f"Cannot connect to Ollama VLM at {base_url}. "
                "Vision observations will fail. Ensure Ollama is running with vision model."
            )
        else:
            logger.info(f"VisionClient initialized: {model} @ {base_url}")
            
        # Check for OCR
        if pytesseract:
            try:
                version = pytesseract.get_tesseract_version()
                self.ocr_available = True
                logger.info(f"OCR enabled: {version}")
            except Exception as e:
                self.ocr_available = False
                logger.error(f"OCR initialization failed: {e}")
        else:
            self.ocr_available = False
            logger.warning("pytesseract not installed. Vision reduced.")
    
    def _test_connection(self) -> bool:
        """Test if Ollama is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                # Check if vision model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(self.model in name for name in model_names):
                    return True
                else:
                    logger.warning(f"Vision model '{self.model}' not found in Ollama. Available: {model_names}")
                    return False
            return False
        except Exception as e:
            logger.error(f"Ollama VLM connection test failed: {e}")
            return False
    
    def analyze_screen(self, image: Image.Image, prompt: str, context_key: str = None) -> Union[Dict[str, Any], None]:
        """
        Analyze a screenshot using OCR (Phase-10B).
        
        Args:
            image: PIL Image of screen
            prompt: Original query (ignored in OCR mode, used for logging)
            context_key: Unique identifier for temporal buffering (e.g. Window Title)
            
        Returns:
            Dict with text, confidence, source
        """
        # Phase-10B.2: Instrumentation
        try:
            from pathlib import Path
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            debug_path = log_dir / "last_vision_capture.png"
            image.save(debug_path)
            logger.info(f"Vision capture saved to {debug_path} | Size: {image.size} | Mode: {image.mode}")
        except Exception as e:
            logger.warning(f"Failed to save debug vision capture: {e}")

        # Try VLM first (llama3.2-vision) for better accuracy
        image_base64 = self._image_to_base64(image)
        vlm_response = self._call_ollama_vision(prompt, image_base64)
        
        if vlm_response:
            logger.info("Vision analysis successful via VLM")
            return {
                "text": vlm_response,
                "confidence": 0.8,  # VLM confidence
                "source": "vlm",
                "advisory_only": True
            }
        
        # Fallback to OCR if VLM fails
        if self.ocr_available and pytesseract:
            try:
                logger.info("VLM failed, falling back to OCR analysis...")
                raw_text = pytesseract.image_to_string(image)
                
                final_text = raw_text.strip()
                source = "ocr"
                
                # Phase-13.2: Temporal Consistency Filter
                if context_key:
                    if context_key not in self.buffers:
                        logger.info(f"Initializing temporal buffer for: {context_key}")
                        self.buffers[context_key] = TemporalTextBuffer(window_size=3)
                    
                    buffer = self.buffers[context_key]
                    
                    # Split into lines
                    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
                    buffer.add_frame(lines)
                    
                    # Get stable lines (persistence >= 2)
                    stable_lines = buffer.get_stable_text(min_persistence=2)
                    
                    if not stable_lines:
                        # "If stable_lines is empty: 'The document is open, but no stable readable content is detected yet.'"
                        final_text = "The document is open, but no stable readable content is detected yet."
                        source = "ocr_temporal_stabilizing"
                    else:
                        # Join stable lines
                        final_text = "\n".join(stable_lines)
                        source = "ocr_temporal_stable"
                
                if not final_text:
                    final_text = "No readable text detected"
                
                return {
                    "text": final_text, # Return clean raw text without prefixes
                    "confidence": self.MAX_CONFIDENCE,
                    "source": source,
                    "advisory_only": True
                }
            except Exception as e:
                logger.error(f"OCR failed: {e}")
                return {
                    "text": f"OCR Analysis Failed: {str(e)}",
                    "confidence": 0.0,
                    "source": "ocr_error",
                    "advisory_only": True
                }
        
        # Fallback if OCR unavailable
        logger.warning(f"OCR unavailable (Available={self.ocr_available}), returning empty signal.")
        return {
             "text": "Vision signal unavailable (OCR missing)",
             "confidence": 0.0,
             "source": "system",
             "advisory_only": True
        }

    def _call_ollama_vision(self, prompt: str, image_base64: str) -> Optional[str]:
        """
        Send request to Ollama VLM (Legacy/Disabled for Phase-10B).
        """
        # ... logic preserved but not called ...
    
    def describe_screen(self, image: Image.Image, context: str = "desktop", analysis_type: str = "general", target: str = "") -> Optional[str]:
        """
        Get a general description of the screen.
        
        Args:
            image: PIL Image of screen
            context: Context type ("desktop", "web", "vision")
            analysis_type: Type of analysis ("general", "chart_technical")
            target: Target description or prompt (for detecting chart analysis)
            
        Returns:
            Screen description or None if analysis fails
        """
        # Phase-2B: Special prompt for market analysis / chart reading
        is_chart_analysis = ("chart" in str(target).lower() or 
                            "support" in str(target).lower() or 
                            "resistance" in str(target).lower() or
                            "trend" in str(target).lower() or
                            analysis_type == "chart_technical")
        
        # Extract timeframe from target string for context
        tf_label = "unknown"
        target_lower = str(target).lower()
        if "monthly" in target_lower or "1m" in target_lower:
            tf_label = "Monthly"
        elif "weekly" in target_lower or "1w" in target_lower:
            tf_label = "Weekly"
        elif "daily" in target_lower or "1d" in target_lower:
            tf_label = "Daily"
        elif "4h" in target_lower or "4 hour" in target_lower:
            tf_label = "4-Hour"
        elif "1h" in target_lower or "hourly" in target_lower:
            tf_label = "Hourly"
        
        if is_chart_analysis:
            prompt = f"""You are a professional chart analyst specializing in VISUAL pattern recognition.
This is a {tf_label} trading chart. Each candle = one {tf_label.lower()} period.

YOUR ROLE: Identify VISUAL patterns, structure, and candlestick formations.
DO NOT try to read exact numbers from the chart — numeric data is extracted separately from DOM.

ANALYZE THESE VISUAL ELEMENTS ONLY:

1. TREND & STRUCTURE (most important):
   - Is price making higher-highs & higher-lows (uptrend)?
   - Or lower-highs & lower-lows (downtrend)?  
   - Or moving sideways within a range?
   - How strong/clean is the trend? Any signs of weakening?

2. CANDLESTICK PATTERNS (last 3-5 candles):
   - Are recent candles large-body or small-body?
   - Any long wicks/shadows? Upper or lower?
   - Name any recognizable patterns: doji, hammer, engulfing, shooting star, pin bar, inside bar, morning/evening star, harami
   - Color sequence of last candles (green/red)

3. CHART PATTERNS (if visible):
   - Any geometric patterns? Triangle (ascending/descending/symmetrical), wedge, channel, flag, pennant
   - Head and shoulders? Double top/bottom? Cup and handle?
   - Is price at a breakout/breakdown point of any pattern?

4. VISUAL SUPPORT/RESISTANCE ZONES:
   - Where has price bounced UP multiple times? (support zone)
   - Where has price reversed DOWN multiple times? (resistance zone)
   - Describe location relative to current price (well below, just below, at price, etc.)
   - Do NOT try to read the exact numbers — just describe the zones visually

5. VOLUME BARS (if visible at bottom):
   - Are recent volume bars taller or shorter than earlier ones?
   - Any volume spikes? Are they on green or red candles?
   - Is volume confirming or diverging from price direction?

6. VISUAL MOMENTUM:
   - Are the candle bodies getting larger (accelerating) or smaller (decelerating)?
   - Any divergence between price movement and visible momentum indicators?
   - Does the chart look "stretched" or "compressed"?

CRITICAL RULES:
- Focus ONLY on what you can clearly SEE in the image
- Describe visual locations, NOT exact price numbers
- Say "unclear" if you cannot determine something
- Do NOT say "buy" or "sell" — observation ONLY
- Prioritize: Trend > Candlestick > Chart Pattern > Volume"""
        else:
            # Original prompt for general screen description
            prompt = (
                "Analyze this screen capture and describe what you see in detail.\n\n"
                "Application & Context:\n"
                "- Identify the application/window\n"
                "- What is the user working on?\n\n"
                "Content:\n"
                "- If code is visible: Identify the programming language, read the code line by line, describe what the code does\n"
                "- If text is visible: Extract and read the complete text content\n"
                "- If UI elements are visible: Describe buttons, menus, dialogs, controls\n\n"
                "Layout & Structure:\n"
                "- Describe the window layout and organization\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "- Read ALL visible text carefully, character by character\n"
                "- Transcribe code EXACTLY as written, preserving indentation and formatting\n"
                "- Include function names, variable names, import statements, comments\n"
                "- If text appears small, focus harder and read it anyway\n"
                "- Do NOT say 'resolution too low' unless text is truly unreadable\n"
                "- Extract file names, paths, line numbers if visible\n\n"
                "Be thorough and extract as much readable text/code as possible."
            )
        result = self.analyze_screen(image, prompt, context_key=context)
        return result.get("text") if result else None
    
    def read_text(self, image: Image.Image) -> Optional[str]:
        """
        Extract all visible text from the screen.
        
        Args:
            image: PIL Image of screen
            
        Returns:
            Extracted text or None if analysis fails
        """
        prompt = (
            "Extract ALL text visible on this screen. Include:\n"
            "- Window titles and application names\n"
            "- Menu items and button labels\n"
            "- Headings and subheadings\n"
            "- Body text and paragraphs\n"
            "- Code snippets if visible\n"
            "- Status bar text\n"
            "Organize the text logically and preserve structure."
        )
        result = self.analyze_screen(image, prompt)
        return result.get("text") if result else None
    
    def find_element(self, image: Image.Image, element_description: str) -> Optional[str]:
        """
        Search for a specific UI element.
        
        Phase-2C: Proposal only - never used for clicking.
        
        Args:
            image: PIL Image of screen
            element_description: Description of element to find (e.g., "Save button")
            
        Returns:
            Element description/location or None if not found
        """
        prompt = (
            f"Is there a '{element_description}' visible on this screen? "
            "If yes, describe its location (e.g., 'top-left corner', 'center', 'bottom menu bar'). "
            "If no, respond with 'Not found'."
        )
        return self.analyze_screen(image, prompt)
    
    def list_visual_regions(self, image: Image.Image) -> Optional[str]:
        """
        Identify major layout regions on the screen.
        
        Phase-3A Visual Scaffolding (Level 3): Structured layout understanding.
        
        Returns descriptive region names ONLY - no coordinates, no actions.
        This is observation-only metadata for understanding screen structure.
        
        Args:
            image: PIL Image of screen
            
        Returns:
            JSON-formatted list of regions (e.g., ["title bar", "main content", "sidebar"])
            or None if analysis fails
        """
        prompt = (
            "Identify the major layout regions visible on this screen. "
            "List them as a JSON array of descriptive region names. "
            "Examples: [\"title bar\", \"navigation menu\", \"main content area\", \"toolbar\", \"status bar\"]. "
            "Focus on functional areas, not specific buttons or text. "
            "Do NOT include pixel coordinates or positions. "
            "Return ONLY the JSON array, nothing else."
        )
        return self.analyze_screen(image, prompt)
    
    def identify_visible_text_blocks(self, image: Image.Image) -> Optional[str]:
        """
        Extract structured text content from screen.
        
        Phase-3A Visual Scaffolding (Level 3): Structured text understanding.
        
        Returns text content organized by semantic blocks - no coordinates, no actions.
        This is observation-only metadata for understanding screen content.
        
        Args:
            image: PIL Image of screen
            
        Returns:
            JSON-formatted text blocks with semantic labels
            (e.g., {"heading": "...", "body": "...", "buttons": [...]})
            or None if analysis fails
        """
        prompt = (
            "Extract and organize all visible text on this screen into semantic blocks. "
            "Return a JSON object with these keys: "
            "- \"heading\": main heading text (if any), "
            "- \"body\": main body text (if any), "
            "- \"buttons\": array of button labels (if any), "
            "- \"menu_items\": array of menu item labels (if any), "
            "- \"other\": array of other text fragments. "
            "Do NOT include pixel coordinates or positions. "
            "Return ONLY the JSON object, nothing else."
        )
        return self.analyze_screen(image, prompt)
    
    def verify_text_visible(self, image: Image.Image, expected_text: str) -> str:
        """
        Verify if expected text is visible on screen.
        
        Phase-3B: Vision-Assisted Verification (verification fallback only).
        
        Used ONLY when DOM/UIA verification fails. Returns verification status
        without proposing actions or generating coordinates.
        
        Args:
            image: PIL Image of screen
            expected_text: Text to look for
            
        Returns:
            "VERIFIED" | "NOT_VERIFIED" | "UNKNOWN"
        """
        prompt = (
            f"Is the text '{expected_text}' visible on this screen? "
            "Answer ONLY with one of these words: "
            "VERIFIED (if text is clearly visible), "
            "NOT_VERIFIED (if text is not visible), or "
            "UNKNOWN (if uncertain). "
            "Do NOT include any other text, coordinates, or suggestions."
        )
        result = self.analyze_screen(image, prompt)
        
        if not result:
            return "UNKNOWN"
        
        # Normalize response
        result_upper = result.strip().upper()
        if "VERIFIED" in result_upper and "NOT" not in result_upper:
            return "VERIFIED"
        elif "NOT_VERIFIED" in result_upper or "NOT VERIFIED" in result_upper:
            return "NOT_VERIFIED"
        else:
            return "UNKNOWN"
    
    def verify_layout_contains(self, image: Image.Image, region_name: str) -> str:
        """
        Verify if a layout region is present on screen.
        
        Phase-3B: Vision-Assisted Verification (verification fallback only).
        
        Used ONLY when DOM/UIA verification fails. Returns verification status
        without proposing actions or generating coordinates.
        
        Args:
            image: PIL Image of screen
            region_name: Region to look for (e.g., "sidebar", "toolbar")
            
        Returns:
            "VERIFIED" | "NOT_VERIFIED" | "UNKNOWN"
        """
        prompt = (
            f"Is there a '{region_name}' visible on this screen? "
            "Answer ONLY with one of these words: "
            "VERIFIED (if region is clearly visible), "
            "NOT_VERIFIED (if region is not visible), or "
            "UNKNOWN (if uncertain). "
            "Do NOT include any other text, coordinates, or suggestions."
        )
        result = self.analyze_screen(image, prompt)
        
        if not result:
            return "UNKNOWN"
        
        # Normalize response
        result_upper = result.strip().upper()
        if "VERIFIED" in result_upper and "NOT" not in result_upper:
            return "VERIFIED"
        elif "NOT_VERIFIED" in result_upper or "NOT VERIFIED" in result_upper:
            return "NOT_VERIFIED"
        else:
            return "UNKNOWN"
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string.
        
        Args:
            image: PIL Image
            
        Returns:
            Base64-encoded image string
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Upscale small images for better VLM code reading
        # If image is smaller than 1200px on any dimension, scale up 2x
        width, height = image.size
        if width < 1200 or height < 1200:
            new_width = width * 2
            new_height = height * 2
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Upscaled image from {width}x{height} to {new_width}x{new_height} for better VLM analysis")
        
        # Save to bytes buffer with high quality
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', optimize=False)
        buffer.seek(0)
        
        # Encode to base64
        image_bytes = buffer.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        return image_base64
    
    def _call_ollama_vision(self, prompt: str, image_base64: str) -> Optional[str]:
        """
        Call Ollama vision API with retry logic.
        
        Retries up to 3 times with exponential backoff before falling back to OCR.
        
        Args:
            prompt: Text prompt
            image_base64: Base64-encoded image
            
        Returns:
            VLM response text or None if all attempts fail
        """
        import time as _time
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic output
                "num_predict": 2000  # Allow longer responses for detailed chart analysis
            }
        }
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Calling Ollama VLM: {self.model} (attempt {attempt}/{max_retries})")
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                
                result = response.json()
                text = result.get("response", "").strip()
                
                # Validate response quality — reject very short or empty responses
                if not text or len(text) < 50:
                    logger.warning(f"VLM returned insufficient response ({len(text)} chars), retrying...")
                    if attempt < max_retries:
                        _time.sleep(2 ** (attempt - 1))  # 1s, 2s
                        continue
                
                if attempt > 1:
                    logger.info(f"VLM succeeded on attempt {attempt}")
                return text
                
            except requests.exceptions.Timeout:
                logger.error(f"Ollama VLM request timed out (attempt {attempt}/{max_retries})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Ollama VLM request failed (attempt {attempt}/{max_retries}): {e}")
            
            # Exponential backoff: 1s, 2s
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                logger.info(f"VLM retry in {backoff}s...")
                _time.sleep(backoff)
        
        logger.error(f"VLM failed after {max_retries} attempts")
        return None
