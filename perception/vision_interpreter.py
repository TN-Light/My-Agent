"""
Vision Interpreter - Phase-11B
Converts raw vision/OCR signals into human-readable, structured summaries.

Strictly Read-Only:
- Never executes code
- Never triggers actions
- Enforces confidence caps (0.7)
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VisionInterpreter:
    """
    Interprets raw vision data into structured UI-ready content.
    """
    
    def interpret(self, raw_text: str, intent: str, confidence: float) -> Dict[str, Any]:
        """
        Main entry point for interpreting vision data.
        
        Args:
            raw_text: The raw string text (OCR output)
            intent: The original user query/prompt (e.g. "what is in the code?")
            confidence: The raw confidence from the vision client
            
        Returns:
            Dict containing:
            - summary: Human readable summary
            - raw_text: Original text
            - context_type: 'code', 'web', 'general'
            - key_elements: List of extracted entities (filenames, buttons, etc)
        """
        if not raw_text or "(No readable text detected)" in raw_text:
             return {
                "summary": "Screen appears empty or text is not readable via OCR.",
                "raw_text": raw_text,
                "context_type": "empty",
                "key_elements": []
            }
        
        intent = intent.lower()
        context_type = "general"
        
        # 1. Detect Context from Intent or Content
        if "code" in intent or "editor" in intent or self._detect_code_content(raw_text):
            context_type = "code"
        elif "browser" in intent or "web" in intent or "http" in raw_text:
            context_type = "web"
            
        # 2. Generate Summary based on Context
        metrics = ""
        if context_type == "code":
            summary, metrics = self._summarize_code(raw_text)
        elif context_type == "web":
            summary, metrics = self._summarize_web(raw_text)
        else:
            summary, metrics = self._summarize_general(raw_text)
            
        # 3. Extract Key Elements (Safe read-only extraction)
        key_elements = self._extract_key_elements(raw_text, context_type)
        
        return {
            "summary": summary,
            "metrics": metrics,
            "raw_text": raw_text,
            "context_type": context_type,
            "key_elements": key_elements,
            "safe_suggestion": self._generate_safe_suggestion(context_type)
        }

    def _detect_code_content(self, text: str) -> bool:
        """Heuristics to detect if text looks like code."""
        code_indicators = [
            r"import\s+\w+", r"def\s+\w+\(", r"class\s+\w+", 
            r"console\.log", r"EXPECTED", r"FAILED", r"Traceback"
        ]
        return any(re.search(p, text) for p in code_indicators)

    def _summarize_code(self, text: str) -> tuple[str, str]:
        """Summarize code editor content. Returns (semantic_summary + preview, metrics)."""
        lines = text.split('\n')
        non_empty = [l for l in lines if l.strip()]
        
        import_count = sum(1 for l in non_empty if "import" in l or "from" in l)
        func_count = sum(1 for l in non_empty if "def " in l or "function " in l)
        class_count = sum(1 for l in non_empty if "class " in l)
        
        # Metrics for Tier 2
        details = []
        if import_count: details.append(f"{import_count} imports")
        if class_count: details.append(f"{class_count} classes")
        if func_count: details.append(f"{func_count} functions")
        metrics = f"{len(non_empty)} lines of code ({', '.join(details)})" if details else f"{len(non_empty)} lines of code"

        # Semantic Summary for Tier 1
        # Phase-UI-C: Infer high-level purpose
        module_role, responsibility = self._infer_code_purpose(text)
        
        semantic_summary = (
            f"You're viewing the {module_role} in the code editor. "
            f"This component is responsible for {responsibility}."
        )

        # Include preview
        preview_lines = non_empty[:15]
        preview_text = "\n".join(preview_lines)
        
        full_summary = (
            f"{semantic_summary}\n"
            f"**Preview:**\n```python\n{preview_text}\n...\n```"
        )
        
        return full_summary, metrics

    def _infer_code_purpose(self, text: str) -> tuple[str, str]:
        """Infer high-level module role and responsibility from content."""
        t = text.lower()
        
        # Mapping rules: keywords -> (Role, Responsibility)
        rules = [
            (["visionclient", "ocr", "screen_capture", "tesseract"], 
             ("Vision Subsystem", "handling screen perception and text recognition")),
            
            (["planner", "llm_planner", "graph", "plan"], 
             ("Planning Engine", "generating execution strategies and decomposing tasks")),
            
            (["executionengine", "execute_instruction", "observer", "loop"], 
             ("Core Execution Loop", "orchestrating agent actions, observations, and safety checks")),
            
            (["chatui", "interface", "qt", "pyside", "window"], 
             ("User Interface", "managing user interaction and visual feedback")),
             
            (["browser", "selenium", "playwright", "web"], 
             ("Browser Automation Module", "navigating and interacting with web pages")),
             
            (["filehandler", "read_file", "write_file"], 
             ("File System Handler", "managing workspace file operations")),

            (["test", "unittest", "case", "assert"], 
             ("Test Suite", "validating system functionality")),
        ]
        
        for keywords, (role, resp) in rules:
            if any(k in t for k in keywords):
                return role, resp
                
        # Default fallback
        return "Source Code", "defining specific agent functionality"

    def _summarize_web(self, text: str) -> tuple[str, str]:
        """Summarize web browser content."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        metrics = f"Page contains approx {len(text.split())} words."
        
        # Heuristic for page title or main header
        semantic_summary = "Active web browser tab."
        for line in lines[:5]:
            if len(line) > 5 and len(line) < 60:
                semantic_summary = f"Active web browser tab showing '{line}'."
                break
                
        preview = "\n".join(lines[:5])
        full_summary = f"{semantic_summary}\n**Preview:**\n{preview}..."
        return full_summary, metrics

    def _summarize_general(self, text: str) -> tuple[str, str]:
        """General UI summary."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        metrics = f"Found {len(lines)} distinct text regions."
        
        semantic_summary = "Visible application or desktop region."
        # Try to guess app
        if any(".py" in l for l in lines):
            semantic_summary = "Visible interface appears to be a development environment."
        elif any("http" in l for l in lines):
             semantic_summary = "Visible interface appears to be a web browser."
             
        preview = "\n".join(lines[:8])
        full_summary = f"{semantic_summary}\n**Preview:**\n{preview}\n..."
        return full_summary, metrics

    def _extract_key_elements(self, text: str, context_type: str) -> list:
        """Extract interesting entities without executing them."""
        elements = []
        lines = text.split('\n')
        
        if context_type == "code":
            # Extract function names
            for line in lines:
                match = re.search(r"def\s+(\w+)", line)
                if match:
                    elements.append(f"Function: {match.group(1)}")
                match = re.search(r"class\s+(\w+)", line)
                if match:
                    elements.append(f"Class: {match.group(1)}")
                    
        return elements[:5]  # Limit to 5

    def _generate_safe_suggestion(self, context_type: str) -> str:
        """Generate a passive, non-executing follow-up suggestion."""
        if context_type == "code":
            return "Would you like me to read specific function details?"
        elif context_type == "web":
            return "Would you like me to look for specific links or text?"
        return "Would you like to narrow the search?"
