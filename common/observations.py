"""
Observation Schema - Phase-2B/2C/3A
Non-actional observation layer for reading state without side effects.

Phase-2B: Read-only operations using authority hierarchy (Accessibility, DOM, File).
Phase-2C: Vision added as Level 4 (lowest authority) - advisory only.
Phase-3A: Visual Scaffolding added (Level 3) - structured layout understanding.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class Observation:
    """
    Immutable observation request.
    
    Observations are non-actional queries that read system state without
    causing side effects. They bypass policy checks and never trigger retries.
    
    Supported observation_types:
    - read_text: Extract text from an element/file
    - query_element: Check element existence/attributes
    - describe_screen: Get VLM description of screen (Phase-2C)
    - find_element: Search for element using vision (Phase-2C)
    - list_visual_regions: Identify layout regions (Phase-3A, Level 3)
    - identify_visible_text_blocks: Extract structured text content (Phase-3A, Level 3)
    
    Contexts (authority routing):
    - desktop: Windows Accessibility Tree (pywinauto)
    - web: Browser DOM (Playwright)
    - file: File system (workspace-only)
    - vision: VLM analysis (Phase-2C - Level 4, advisory only)
    
    Phase-2C vision constraints:
    - Vision is lowest authority (Level 4)
    - Vision output is advisory, never authoritative
    - Vision never triggers actions
    - Vision used only when Level 1-3 unavailable
    """
    observation_type: str  # "read_text" | "query_element"
    context: str           # "desktop" | "web" | "file"
    target: Optional[str] = None  # CSS selector, element name, or file path
    
    def __post_init__(self):
        """Validate observation constraints."""
        # Validate observation_type
        valid_types = [
            "read_text", "query_element", 
            "describe_screen", "find_element",  # Phase-2C
            "list_visual_regions", "identify_visible_text_blocks",  # Phase-3A
            "vision", # Phase-10: General vision query
            "check_app_state", # Phase-11A: Check if app/window exists
            "vision_buffer_read" # Phase-12: Read from last vision observation
        ]
        if self.observation_type not in valid_types:
            raise ValueError(
                f"Invalid observation_type: {self.observation_type}. "
                f"Must be one of {valid_types}"
            )
        
        # Validate context
        valid_contexts = ["desktop", "web", "file", "vision", "vision_buffer"]
        if self.context not in valid_contexts:
            raise ValueError(
                f"Invalid context: {self.context}. "
                f"Must be one of {valid_contexts}"
            )
        
        # Validate target (optional for whole-screen observations)
        whole_screen_types = ["describe_screen", "list_visual_regions", "identify_visible_text_blocks"]
        if not self.target and self.observation_type not in whole_screen_types:
            raise ValueError(
                f"Observation requires 'target' field for {self.observation_type}"
            )


@dataclass(frozen=True)
class ObservationResult:
    """
    Result of an observation query.
    
    Status values:
    - "success": Observation completed successfully
    - "not_found": Target element/file not found
    - "error": Observation failed due to exception
    """
    observation: Observation
    status: str  # "success" | "not_found" | "error"
    result: Optional[str] = None  # Text content, attribute value, etc.
    error: Optional[str] = None   # Error message if status == "error"
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None # Extra info (confidence, source, etc.)
    
    def __post_init__(self):
        """Validate result constraints."""
        valid_statuses = ["success", "not_found", "error"]
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.status}. "
                f"Must be one of {valid_statuses}"
            )
