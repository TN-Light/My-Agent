"""
Vision Semantic Interpreter - Phase-13
Responsible for grounding raw OCR data into human-level semantic summaries.

This module applies deterministic rules based on application context (Notepad, VS Code, Browser, etc.)
to produce descriptions that answer "what do you see?" effectively.
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VisionSemanticInterpreter:
    def __init__(self):
        pass

    def interpret(self, ocr_text: str, window_title: str) -> Dict[str, Any]:
        """
        Interpret vision data into a semantic summary.
        
        Args:
            ocr_text: Raw text extracted from the screenshot.
            window_title: The title of the window (ground truth).
            
        Returns:
            Dict with "summary", "app_name", "content_summary".
        """
        app_name = self._detect_app_name(window_title)
        
        summary = ""
        content_summary = ""
        
        if app_name == "Notepad":
            summary, content_summary = self._summarize_notepad(ocr_text, window_title)
        elif app_name == "Visual Studio Code":
            summary, content_summary = self._summarize_vscode(ocr_text, window_title)
        elif app_name == "Browser":
            summary, content_summary = self._summarize_browser(ocr_text, window_title)
        else:
            summary, content_summary = self._summarize_generic(ocr_text, window_title, app_name)
            
        return {
            "summary": summary,
            "app_name": app_name,
            "content_summary": content_summary,
            "window_title": window_title,
            "context_type": app_name,
            "key_elements": [], # Future Phase: Extract specific buttons/inputs
            "safe_suggestion": "" # Future Phase: Suggest next actions
        }

    def describe(self, observation_result) -> str:
        """
        Phase-13.3: Generate a conversational description from an ObservationResult.
        Bypasses action planner for purely descriptive queries.
        """
        if not observation_result or not hasattr(observation_result, 'metadata') or not observation_result.metadata:
             return "I have no detailed visual memory to describe."

        metadata = observation_result.metadata
        window_title = metadata.get("window_title", "the active application")
        interpretation = metadata.get("interpretation", {})
        
        # If we have a structured interpretation, use it
        if interpretation and "summary" in interpretation:
             summary = interpretation["summary"]
             # If summary already contains the window title or "You are viewing", use it directly
             # to avoid redundancy like "You are viewing Notepad. You are viewing 'file.txt' in Notepad."
             if "You are viewing" in summary or window_title in summary:
                 return summary
                 
             return f"You are viewing {window_title}. {summary}"
             
        # Fallback to raw OCR if interpretation is missing (legacy)
        raw_ocr = metadata.get("raw_ocr", "")
        if raw_ocr:
            return f"You are viewing {window_title}. The screen contains: {raw_ocr[:200]}..."
            
        return f"You are viewing {window_title}, but I can't discern specific content."

    def _detect_app_name(self, title: str) -> str:
        """Identify application from window title."""
        title_lower = title.lower()
        if "notepad" in title_lower:
            return "Notepad"
        if "visual studio code" in title_lower or "vs code" in title_lower:
            return "Visual Studio Code"
        if "edge" in title_lower or "chrome" in title_lower or "firefox" in title_lower:
            return "Browser"
        return title # Fallback to using title as app name

    def extract_document_body(self, ocr_lines: list[str]) -> str:
        """
        Phase-13.1: Strict Content Extraction
        Isolates document body from OCR noise using deterministic rules.
        """
        clean_lines = []
        
        # Hard Filter Tokens (Case-Insensitive)
        # These are tokens that strongly indicate a line is UI chrome, not content.
        FORBIDDEN_SUBSTRINGS = [
            # Menu / chrome tokens
            "file", "edit", "view", "help", "selection", "run", "terminal", "debug", "go",
            "method", "properties", # Object explorer / breadcrumbs
            # Status tokens
            "ln ", "col ", "ln,", "col,", "100%", "utf-8", "utf8", "crlf",
            # System phrases
            "detected text via ocr",
            # UI separators
            "|", "||", "•", "—", ">>", "<<", "::"
        ]
        
        # Regex for Status/Line patterns (Catch "Ln1", "Col:10", "Line 5" etc)
        STATUS_REGEX = re.compile(r"(Ln\s*\d+|Col\s*\d+|Ln,|Col,|Line\s*\d+|Column\s*\d+|Ln\d+|Col\d+)", re.IGNORECASE)
        
        # Formatting/UI keywords that usually appear in toolbar lines
        FORMATTING_KEYWORDS = ["bold", "italic", "underline", "h1", "h2", "h3"] 

        for line in ocr_lines:
            s_line = line.strip()
            if not s_line: continue
            
            lower_line = s_line.lower()
            
            # --- 1. HARD FILTER ---
            
            # Check forbidden substrings
            if any(token in lower_line for token in FORBIDDEN_SUBSTRINGS):
                continue
            
            # Check regex patterns (Status bars)
            if STATUS_REGEX.search(s_line):
                continue
            
            # Check formatting keywords
            if any(k in lower_line for k in FORMATTING_KEYWORDS):
                continue

            # File tabs heuristic: If line looks like a file list (contains extension + spaces)
            # Checking for common source extensions relative to length
            if any(ext in lower_line for ext in [".txt", ".md", ".py", ".js", ".json", ".html", ".css"]):
                 # If visual tab bar (e.g. "main.py utils.py" or "header.h") or just a filename
                 # Heuristic: Short lines with extensions are likely tabs or title bars, NOT content logic.
                 # Content usually has spaces and sentence structure. "open file.txt" is valid. "file.txt" is not.
                 if len(s_line) < 40:
                     continue
            
            # Filter lines that look like filenames (e.g. "untitled.txt", "bye-txt")
            if re.match(r'^[\w\-]+\.(txt|md|py|js|json|html|css)$', s_line, re.IGNORECASE):
                continue
            if re.match(r'^[\w\-]+$', s_line) and len(s_line) < 15 and s_line.lower() != "bye": 
                 # Aggressive single word filter if it looks like "bye-txt" but OCR missed dot
                 # "Bye" might be content, but "bye-txt" is noise.
                 if "-" in s_line: continue
            
            # Special Character Noise (e.g. Blrl® - likely 'Ctrl' or icon artifacts)
            if any(char in s_line for char in ["®", "©", "™"]):
                continue

            # --- 2. POSITIVE CONTENT RULES ---
            
            # Rule: Contains alphabetic characters
            if not re.search(r'[a-zA-Z]', s_line):
                continue
                
            # Rule: Length >= 3 characters (Filters artifacts like "1", "()", "B")
            if len(s_line) < 3:
                continue
                
            # Rule: NOT all uppercase
            # (Exception: Acronyms or short headers, but we abide by strict user rule for basic docs)
            if s_line.isupper():
                continue
            
            # Rule: No UI symbols (covered partly by forbid list, but checking specific single tokens)
            if s_line in [">", "<", "+", "-", "*"]:
                continue
            
            clean_lines.append(s_line)
            
        # --- 3. DOCUMENT BODY SELECTION ---
        if not clean_lines:
            # Fallback: If strict filtering killed everything, try to salvage SOMETHING
            # This handles cases like code files with only imports or unusual syntax
            if ocr_lines:
                # Take the longest lines as likely content
                sorted_raw = sorted(ocr_lines, key=len, reverse=True)
                salvage = " ".join(sorted_raw[:5])
                if salvage.strip():
                     return f"[Raw OCR] {salvage}"
            
            return "Document is open but contains no readable text."
            
        # Join lines in visual order
        body = " ".join(clean_lines)
        
        # Collapse repeated spaces
        body = re.sub(r'\s+', ' ', body)
        
        return body.strip()

    def _summarize_notepad(self, text: str, title: str) -> tuple[str, str]:
        """Summarize Notepad state."""
        # 1. Extract Filename
        clean_title = title.replace("- Notepad", "").strip()
        is_unsaved = clean_title.startswith("*")
        filename = clean_title.lstrip("*")
        
        # 2. Extract Document Content (Strict)
        lines = [l for l in text.splitlines() if l.strip()]
        content = self.extract_document_body(lines)
        
        # Formulate rigid response as requested
        summary = f"You are viewing '{filename}' in Notepad."
        if is_unsaved:
            summary += " (Unsaved changes)."
        
        # Filter: Ensure 'content' doesn't contain the filename itself (common title artifact)
        # e.g. if content is "hello world untitled.txt", strip "untitled.txt"
        # Using simple replace can be dangerous if filename is a common word, but for now it's necessary.
        # Also strip trailing spaces that result.
        
        # We need to handle case where filename is "untitled.txt" and content ends with it.
        # content = content.replace(filename, "") is okay for MVP. 
        if filename and filename in content:
             content = content.replace(filename, "").strip()
             
        summary += f" The document contains: '{content}'."
            
        return summary, content

    def _summarize_vscode(self, text: str, title: str) -> tuple[str, str]:
        """Summarize VS Code state."""
        # Title format: "filename.py - ProjectName - Visual Studio Code"
        parts = title.split(" - ")
        filename = parts[0] if parts else "unknown file"
        
        # Detect language hint from extension
        lang = "code"
        if filename.endswith(".py"): lang = "Python"
        elif filename.endswith(".js"): lang = "JavaScript"
        elif filename.endswith(".md"): lang = "Markdown"
        
        summary = f"Editing {lang} file '{filename}' in Visual Studio Code."
        
        # Content: Extract clean code
        # Use Phase-13.1 logic to filter noise
        clean_text = self.extract_document_body(text.splitlines())
        
        # Heuristic: If we have clean text, show a snippet
        if len(clean_text) > 5:
            summary += f" Visible code: '{clean_text[:100]}...'"
        else:
            summary += " (Code area visible)."
            
        return summary, filename

    def _summarize_browser(self, text: str, title: str) -> tuple[str, str]:
        """Summarize Browser state."""
        # Title format: "Page Title - Profile - Browser Name"
        # Heuristic: Take everything before the last hyphen
        page_title = title.split(" - ")[0]
        
        summary = f"Viewing a webpage titled '{page_title}'."
        
        # Scan text for URL-like patterns or headings 
        # (This is hard with just OCR, but we can try)
        return summary, page_title

    def _summarize_generic(self, text: str, title: str, app_name: str) -> tuple[str, str]:
        """Generic fallback summary."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        content = " ".join(lines[:2]) if lines else "No text detected"
        
        summary = f"Viewing {app_name}. Detected text: '{content}'."
        return summary, content
