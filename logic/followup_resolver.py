"""
[DEPRECATED] Follow-Up Resolver - Phase-12
Rewritten by DialogueState in Phase-12 (CIL).
Do not use in active execution path.

Resolves context-dependent queries like "yes read it" into fully grounded instructions.
Maintains session observation state.
"""
import logging
from typing import Optional
from common.observations import ObservationResult

logger = logging.getLogger(__name__)

class FollowupResolver:
    """
    Resolves pronouns and short follow-up commands by binding them 
    to the context of the last successful observation.
    """
    
    def __init__(self):
        self._last_observation: Optional[ObservationResult] = None
        
    def update_observation(self, result: ObservationResult):
        """Update session state with latest successful observation."""
        if result.status == "success":
            self._last_observation = result
            # logger.info(f"Observation state updated: {result.observation.context}")

    def get_last_observation(self) -> Optional[ObservationResult]:
        return self._last_observation

    def get_last_vision_content(self) -> Optional[str]:
        """Retrieve raw text content from the last vision observation."""
        if not self._last_observation or not self._last_observation.metadata:
            return None
        return self._last_observation.metadata.get("raw_ocr")

    def resolve(self, instruction: str) -> str:
        """
        Rewrite instruction if it's a context-dependent follow-up.
        """
        if not self._last_observation:
            return instruction
            
        text = instruction.strip().lower()
        
        # 1. Detect Formatting Requests (Phase-UI-B)
        # These are handled by ExecutionEngine bypassing nature
        # But we resolve them to a canonical intent for clearer logging
        detail_level = self.check_formatting_request(instruction)
        if detail_level:
            if detail_level == 2:
                return "render_tier_2_details"
            elif detail_level == 3:
                return "render_tier_3_raw"
        
        # 2. Detect Vision Follow-Ups
        obs_meta = self._last_observation.metadata or {}
        raw_ocr = obs_meta.get("raw_ocr")
        
        if raw_ocr and self._is_vision_confirmation(text):
            # It's a vision follow-up
            # Check interpretation context
            interpretation = obs_meta.get("interpretation", {})
            context_type = interpretation.get("context_type", "screen")
            
            logger.info(f"Resolving follow-up '{instruction}' -> Vision Summary ({context_type})")
            return f"Summarize the last vision OCR text from {context_type}"
            
        return instruction

    def check_formatting_request(self, instruction: str) -> int:
        """
        Check if instruction is a UI formatting request.
        Returns:
            0 (None), 2 (Details), 3 (Raw)
        """
        text = instruction.strip().lower()
        
        # Tier 3: Raw
        raw_triggers = ["raw", "ocr", "exact text", "show raw", "show ocr"]
        if any(t in text for t in raw_triggers):
            return 3
            
        # Tier 2: Details
        detail_triggers = ["show more", "details", "explain structure", "show details"]
        if any(t in text for t in detail_triggers):
            return 2
            
        return 0

    def _is_vision_confirmation(self, text: str) -> bool:
        """Check for short confirmation phrases."""
        triggers = [
            "yes", 
            "read it", 
            "read that",
            "summarize", 
            "summarize it",
            "explain", 
            "what does it say",
            "yes please",
            "go ahead"
        ]
        
        if text in triggers:
            return True
        
        # Check starts-with for slightly longer phrases "read the code"
        if any(text.startswith(t + " ") for t in triggers):
            return True
            
        return False
