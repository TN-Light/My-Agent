"""
Response Composer - Phase-12 (CIL)
Generates clean, human-readable responses based on DialogueState and ObservationResults.
Enforces Tiered Output rules (Jarvis-style).

Tiers:
1. Summary (Default): max 2 lines, purpose-oriented.
2. Explanation (Details): Structure, key elements, partial content.
3. Raw (Analysis): Full headers, raw text/OCR (if explicitly requested).
"""
import logging
from typing import Optional
from common.observations import ObservationResult
from interface.response_formatter import ResponseFormatter # Reuse low-level formatter

logger = logging.getLogger(__name__)

class ResponseComposer:
    def __init__(self):
        pass

    def compose_observation_response(self, result: ObservationResult, detail_level: int = 1) -> str:
        """
        Compose a response for an observation.
        """
        # Phase-12: Semantic Enrichment for Vision
        # If this is a vision result, we enforce semantic templating BEFORE falling back to generic formatting.
        if result.observation.observation_type == "vision":
            return self._compose_vision_response(result, detail_level)

        # Fallback to standard formatter
        return ResponseFormatter.format_observation(result, detail_level)

    def _compose_vision_response(self, result: ObservationResult, detail_level: int) -> str:
        """
        Construct a semantic, human-readable vision response.
        Uses structured interpretation from Phase-13 VisionSemanticInterpreter.
        """
        metadata = result.metadata or {}
        interpretation = metadata.get("interpretation", {})
        window_title = metadata.get("window_title", "")
        
        # Phase-14: Check for direct VLM response first (highest priority)
        if metadata.get("source") == "vlm" and result.result:
            # VLM gave us a full description - use it directly
            return f"You are viewing {window_title}.\n{result.result}" if window_title else result.result
        
        # If we have a high-quality interpretation, use it directly
        if interpretation:
            context = interpretation.get("context_type", "Application")
            summary = interpretation.get("summary", "")
            
            # Map context to friendly names if needed
            if context == "App": context = "an application"
            
            # Use the window title if available for specificity
            app_name = window_title if window_title else context
            
            # If the summary is just a generic fallback found in early logic, we might polish it,
            # but usually the interpreter gives good text.
            
            response = f"You are viewing {app_name}."
            if summary:
                response += f"\n{summary}"
                
            if detail_level > 1 and interpretation.get("key_elements"):
                response += f"\nKey elements: {', '.join(interpretation['key_elements'])}"
                
            return response

        # Fallback to legacy OCR parsing if interpretation is missing (Phase-12 logic)
        raw_ocr = metadata.get("raw_ocr", "")
        lines = [line.strip() for line in raw_ocr.split('\n') if line.strip()]
        app_name = "the active application"
        
        if lines:
            first_line = lines[0]
            if "Notepad" in first_line: app_name = "Notepad"
            elif "Visual Studio Code" in first_line: app_name = "Visual Studio Code"
            elif "Edge" in first_line: app_name = "the web browser"

        response = f"You are viewing {app_name}. (Raw OCR analysis only)"
        # Tier 2/3 additions
        if detail_level >= 2:
             response += "\n\n(Details: Use 'show raw' for full OCR dump)"
        
        return response

    def compose_clarification(self, failure_reason: str) -> str:
        """Compose a clarification question."""
        if "no observation" in failure_reason.lower():
            return "I haven't observed anything yet. What would you like me to look at?"
        return "I'm not sure what you're referring to. Could you be more specific?"

    def compose_action_response(self, action_type: str, status: str, message: str) -> str:
        if status == "success":
            return f"Done. {message}"
        else:
            return f"I couldn't complete that. {message}"
