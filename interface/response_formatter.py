"""
Response Formatter - Phase-UI-A
Formats raw observation/execution results into Jarvis-style human-readable text.

Features:
- Translates confidence scores to natural language.
- Hides raw data (OCR, metadata) behind progressive disclosure.
- Maintains professional, concise agent persona.
"""
from typing import Union, Dict, Any, Optional
from common.observations import ObservationResult
from common.actions import ActionResult

class ResponseFormatter:
    """Format agent outputs for UI display."""
    
    @staticmethod
    def format_observation(result: ObservationResult, detail_level: int = 1) -> str:
        """
        Format an observation result into a user-friendly message.
        
        Args:
            result: The observation result
            detail_level: 
                1 = Summary (Calm, partial).
                2 = Details (Structure, metadata).
                3 = Raw (OCR dump).
        """
        if result.status != "success":
            return f"I encountered an issue observing the target: {result.error}"

        # Extract content and metadata
        metadata = result.metadata or {}
        confidence = metadata.get("confidence", 1.0)
        source = metadata.get("source", "unknown")
        interpretation = metadata.get("interpretation", {})
        raw_ocr = metadata.get("raw_ocr", result.result)
        
        # --- TIER 3: RAW OCR ---
        if detail_level >= 3:
            return (
                f"**Raw Sensor Output ({source}):**\n"
                f"```text\n{raw_ocr}\n```\n"
                f"_(Note: This text contains raw sensor noise)_"
            )

        # --- TIER 1 & 2 BASE ---
        
        # 1. Determine Confidence Phrasing
        conf_phrase = ResponseFormatter._get_confidence_phrase(confidence)
        
        # 2. Determine Context/Source Phrasing
        source_phrase = ResponseFormatter._get_source_phrase(source, metadata)
        
        # 3. Construct Summary
        summary = ""
        
        if interpretation and "summary" in interpretation:
             full_summary = interpretation["summary"]
             
             # Split preview if present
             if "**Preview:**" in full_summary:
                 parts = full_summary.split("**Preview:**")
                 clean_summary = parts[0].strip()
                 preview_block = "**Preview:**" + parts[1]
             else:
                 clean_summary = full_summary
                 preview_block = ""
             
             # Clean prefixes
             for prefix in ["Description:", "Browser Context:", "Code Editor Context:"]:
                 if clean_summary.startswith(prefix):
                     clean_summary = clean_summary[len(prefix):].strip()
                     
             # Hard Guard: Block metrics in semantic summary
             # If summary contains "lines of code", "words", "text regions", strip it.
             # This is a fallback if the interpreter leaked metrics.
             blocked_phrases = ["lines of code", "text regions", "words of text", "distinct text"]
             if any(p in clean_summary for p in blocked_phrases):
                 clean_summary = "Active application window visible."
             
             # Tier 1: Just the clean sentence
             if detail_level == 1:
                 summary = clean_summary
             # Tier 2: Sentence + Preview
             else:
                 summary = f"{clean_summary}\n\n{preview_block}"
                 
        else:
             # Fallback
             if detail_level == 1:
                 summary = "Visible screen content detected."
             else:
                 summary = raw_ocr[:200].replace('\n', ' ') + "..."
                 if detail_level == 2:
                     summary = raw_ocr[:1000] # More text for Tier 2

        # 4. Assemble Response (Tier 1 Template: Context + Summary)
        # "In the active code editor, I see: Active code editor..." -> redundant
        # If summary starts with "Active...", shorten source phrase
        
        if summary.lower().startswith("active") or summary.lower().startswith("visible"):
             base_response = summary
        else:
             base_response = f"{source_phrase} {summary}"
        
        # Add Confidence Nuance
        if confidence < 1.0: # Always hint at uncertainty if not perfect
            if detail_level == 1:
                # Phase-UI-C: No confidence parentheticals in Tier 1
                pass
            else:
                base_response += f" {conf_phrase}"

        # --- TIER 2 EXTRAS ---
        if detail_level == 2:
            metrics = interpretation.get("metrics")
            if metrics:
                base_response += f"\n\n**Metrics:** {metrics}"
                
            key_elements = interpretation.get("key_elements", [])
            if key_elements:
                base_response += "\n\n**Detected Structures:**\n" + "\n".join([f"- {k}" for k in key_elements])
                
        return base_response

    @staticmethod
    def format_action_result(result: ActionResult) -> str:
        """Format an action execution result."""
        if result.status == "success":
            return f"Success: {result.message}"
        else:
            return f"Action failed: {result.error}"

    @staticmethod
    def _get_confidence_phrase(score: float) -> str:
        """Translate numeric confidence to natural language."""
        if score >= 0.9:
            return "" # Implicit high confidence
        elif score >= 0.7:
            return "(I'm reasonably confident in this)"
        elif score >= 0.4:
            return "(There is some uncertainty in the text)"
        else:
            return "(The view is unclear, I might need guidance)"

    @staticmethod
    def _get_source_phrase(source: str, metadata: dict) -> str:
        """Describe where the information came from."""
        if source == "vision_llm" or source == "ocr":
            # Check interpretation context
            interp = metadata.get("interpretation", {})
            ctx = interp.get("context_type", "")
            
            if ctx == "code":
                return "In the active code editor, I see:"
            elif ctx == "web":
                return "On the visible web page, I found:"
            elif ctx == "screen":
                return "On the screen, I see:"
            
            # Use window title if available
            # (Requires passing window title in metadata, which might be in 'target' or not captured directly in metadata yet)
            return "Based on the visual output,"
            
        elif source == "accessibility":
            return "Checking the application structure,"
        
        return "I found:"
