"""
Accessibility Client - Windows UI Automation Inspector
Authority Hierarchy: Level 1 (Highest Trust - Ground Truth for OS)

Read-only interface to Windows UI Automation.
Queries the accessibility tree for window states and element properties.
"""
import logging
import psutil
from typing import Optional
from dataclasses import dataclass

try:
    from pywinauto import Desktop
    from pywinauto.application import Application
    from pywinauto.findwindows import ElementNotFoundError
except ImportError:
    Desktop = None
    Application = None
    ElementNotFoundError = Exception

logger = logging.getLogger(__name__)


@dataclass
class UIElement:
    """Represents a UI element from the accessibility tree."""
    name: str
    class_name: str
    control_type: str
    is_visible: bool
    rectangle: tuple[int, int, int, int]  # (left, top, right, bottom)
    handle: int = 0


class AccessibilityClient:
    """
    Windows UI Automation client for querying the accessibility tree.
    
    This is the highest-trust data source in the Perception Authority Hierarchy.
    All UI interactions must be validated through this layer before execution.
    """
    
    def __init__(self):
        """Initialize the accessibility client."""
        if Desktop is None:
            raise ImportError("pywinauto is not installed. Run: pip install pywinauto")
        self.desktop = Desktop(backend="uia")
        logger.info("AccessibilityClient initialized with UIA backend")

    def get_document_content_bbox(self, window_title_regex: str) -> Optional[tuple[int, int, int, int]]:
        """
        Phase-13.1.1: Get the bounding box of the main document/editor area.
        Returns screen coordinates (left, top, right, bottom).
        Used for UIA-guided cropping.
        """
        try:
            # Connect to window
            # Note: window(title_re=...) is fuzzy. We assume caller provides a good regex or title.
            # Using regex match allows matching "Untitled - Notepad" with ".*Notepad.*"
            # But if exact title is known, escape special chars? 
            # Ideally caller does escaping. For now we assume title_re compatible string.
            
            # If title has regex chars that shouldn't be regex, handle it?
            # Safe bet: If specific title passed, treat as literal if possible?
            # pywinauto window() supports 'title' (exact) and 'title_re'.
            
            target_window = None
            try:
                target_window = self.desktop.window(title=window_title_regex)
                if not target_window.exists(timeout=1):
                    target_window = self.desktop.window(title_re=window_title_regex)
            except Exception:
                target_window = self.desktop.window(title_re=window_title_regex)

            if not target_window.exists(timeout=1):
                logger.debug(f"Window '{window_title_regex}' not found for bbox lookup")
                return None

            doc_control = None
            
            # 1. Notepad / Text Editors
            try:
                # "Edit" control is standard for Notepad
                doc_control = target_window.child_window(control_type="Edit", found_index=0)
                # Check if it actually exists (lazy lookup)
                doc_control.wrapper_object() 
            except Exception:
                doc_control = None

            # 2. VS Code / Chromium / Modern Editors
            if not doc_control:
                try:
                    # "Document" control type is common in UIA for web-based editors
                    doc_control = target_window.child_window(control_type="Document", found_index=0)
                    doc_control.wrapper_object()
                except Exception:
                    doc_control = None

            # 3. Fallback: Code editors often use custom classes
            if not doc_control:
                try:
                    doc_control = target_window.child_window(class_name="Chrome_RenderWidgetHostHWND", found_index=0)
                    doc_control.wrapper_object()
                except Exception:
                    doc_control = None

            if doc_control:
                rect = doc_control.rectangle()
                
                # Phase-13.3 - Viewport Qualification Rule 1
                # REJECT MICRO-VIEWPORTS
                # Increased threshold to 80 to avoid tab bars/status bars
                if rect.height() < 80:
                    # Unicode-safe logging for Windows console
                    safe_title = window_title_regex.encode("cp1252", errors="ignore").decode("cp1252")
                    logger.warning(f"Rejecting micro-viewport (height={rect.height()}) in '{safe_title}'")
                    # Force fallback logic by looping or returning None to trigger observer fallback
                    doc_control = None
                else:
                     logger.info(f"Found document control: {rect}")
                     return (rect.left, rect.top, rect.right, rect.bottom)
            
            # Phase-13.3 - Rule 2: Advanced VS Code Heuristics
            if not doc_control and "Code" in window_title_regex:
                 # Logic for VS Code specifically:
                 # The accessibility tree is messy.
                 # 1. Try "Editor" Group/Pane
                 # 2. Try maximizing: Last-Resort 60% center crop (Handled by observer fallback currently, 
                 #    but we can offer a 'smart rect' here)
                 pass
            
            return None

        except Exception as e:
            logger.warning(f"Failed to get document bbox for '{window_title_regex}': {e}")
            return None

    
    def find_window(self, title: Optional[str] = None, class_name: Optional[str] = None) -> Optional[UIElement]:
        """
        Find a window by title or class name.
        
        Args:
            title: Window title (partial match)
            class_name: Window class name (exact match)
            
        Returns:
            UIElement if found, None otherwise
        """
        try:
            windows = self.desktop.windows()
            for window in windows:
                window_title = window.window_text()
                window_class = window.class_name()
                
                # Match by title (case-insensitive, partial)
                if title and title.lower() in window_title.lower():
                    rect = window.rectangle()
                    return UIElement(
                        name=window_title,
                        class_name=window_class,
                        control_type="Window",
                        is_visible=window.is_visible(),
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        handle=window.handle
                    )
                
                # Match by class name (exact)
                if class_name and class_name == window_class:
                    rect = window.rectangle()
                    return UIElement(
                        name=window_title,
                        class_name=window_class,
                        control_type="Window",
                        is_visible=window.is_visible(),
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        handle=window.handle
                    )
            
            logger.debug(f"Window not found: title={title}, class_name={class_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding window: {e}")
            return None

    def find_window_by_process(self, process_name: str) -> Optional[UIElement]:
        """
        Find a window by process name (e.g., 'notepad.exe').
        
        Args:
            process_name: Executable name (case-insensitive)
            
        Returns:
            UIElement if found, None otherwise
        """
        try:
            # First, find valid PIDs for this process
            pids = []
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    pids.append(proc.info['pid'])
            
            if not pids:
                logger.debug(f"No process found with name: {process_name}")
                return None
                
            windows = self.desktop.windows()
            for window in windows:
                if window.process_id() in pids:
                    # Found a window belonging to one of the PIDs
                    window_title = window.window_text()
                    window_class = window.class_name()
                    rect = window.rectangle()
                    return UIElement(
                        name=window_title,
                        class_name=window_class,
                        control_type="Window",
                        is_visible=window.is_visible(),
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        handle=window.handle
                    )
            logger.debug(f"No window found for process: {process_name} (pids={pids})")
            return None
        except Exception as e:
            logger.error(f"Error finding window by process: {e}")
            return None
    
    def find_windows(self, name_pattern: str) -> list[UIElement]:
        """
        Find all windows matching a title pattern.
        
        Args:
            name_pattern: Title substring to match
            
        Returns:
            List of matching UIElements
        """
        results = []
        try:
            windows = self.desktop.windows()
            for window in windows:
                if name_pattern and name_pattern.lower() in window.window_text().lower():
                    rect = window.rectangle()
                    results.append(UIElement(
                        name=window.window_text(),
                        class_name=window.class_name(),
                        control_type="Window",
                        is_visible=window.is_visible(),
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        handle=window.handle
                    ))
        except Exception as e:
            logger.error(f"Error finding windows: {e}")
        return results

    def get_window_count(self, title_pattern: str) -> int:
        """
        Count windows matching a title pattern.
        
        Args:
            title_pattern: Pattern to match against window titles
            
        Returns:
            Number of matching windows
        """
        try:
            windows = self.desktop.windows()
            count = sum(1 for w in windows if title_pattern.lower() in w.window_text().lower())
            return count
        except Exception as e:
            logger.error(f"Error counting windows: {e}")
            return 0
    
    def is_window_visible(self, title: str) -> bool:
        """
        Check if a window with given title is visible.
        
        Args:
            title: Window title to search for
            
        Returns:
            True if window exists and is visible
        """
        element = self.find_window(title=title)
        return element is not None and element.is_visible
    
    def is_handle_valid(self, handle: int) -> bool:
        """
        Check if a window handle is still valid and visible.
        
        Args:
            handle: The window handle
            
        Returns:
            True if valid and visible
        """
        try:
            if not Application:
                return False
            
            # Use pywinauto/common logic
            # Simplest way: try to retrieve element
            app = Application(backend="uia").connect(handle=handle)
            win = app.window(handle=handle)
            return win.is_visible()
            
        except Exception:
            return False

    def get_focused_window(self) -> Optional[UIElement]:
        """
        Get the currently focused window.
        
        Uses Win32 API. Legacy naming, alias for get_active_window.
        
        Returns:
            UIElement of focused window, or None
        """
        return self.get_active_window()

    def get_active_window(self) -> Optional[UIElement]:
        """
        Get the currently active (foreground) window.
        """
        try:
            # Use pywinauto if available for consistency
            if Desktop:
                try:
                    win = Desktop(backend="uia").active() # Get active window
                    if win:
                        rect = win.rectangle()
                        return UIElement(
                            name=win.window_text(),
                            class_name=win.class_name(),
                            control_type="Window",
                            is_visible=True,
                            rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                            handle=win.handle
                        )
                except Exception:
                    pass

            # Fallback to win32gui
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            
            if hwnd == 0:
                return None
            
            # Get window text (title)
            window_text = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            # Get window rect
            try:
                rect_tuple = win32gui.GetWindowRect(hwnd)
                # Ensure we have a 4-tuple
                if len(rect_tuple) == 4:
                     # Convert to standard tuple if needed (win32 returns tuple)
                     pass
                else:
                    rect_tuple = (0,0,0,0)
            except Exception:
                rect_tuple = (0,0,0,0)

            return UIElement(
                name=window_text,
                class_name=class_name,
                control_type="Window",
                is_visible=win32gui.IsWindowVisible(hwnd),
                rectangle=rect_tuple,
                handle=hwnd
            )
            
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return None
    
    def wait_for_window(self, title: str, timeout: float = 5.0, poll_interval: float = 0.5) -> bool:
        """
        Wait for a window to appear.
        
        Args:
            title: Window title to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds
            
        Returns:
            True if window appeared, False if timeout
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_window_visible(title):
                logger.info(f"Window appeared: {title}")
                return True
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout waiting for window: {title}")
        return False

    def find_child_window(self, parent_handle: int) -> Optional[UIElement]:
        """
        Find a blocking dialog for the application.
        
        Args:
            parent_handle: Handle of the parent window
            
        Returns:
            UIElement of the child window/dialog if found, None otherwise
        """
        try:
            if not Application:
                return None
                
            app = Application(backend="uia").connect(handle=parent_handle)
            
            # Application.windows() returns all top-level windows for the process
            windows = app.windows()
            
            for w in windows:
                if w.handle == parent_handle:
                    continue
                    
                # If we found another window, it's likely a dialog
                if w.is_visible():
                     rect = w.rectangle()
                     return UIElement(
                        name=w.window_text(),
                        class_name=w.class_name(),
                        control_type="Window",
                        is_visible=True,
                        rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                        handle=w.handle
                    )
            return None
        except Exception as e:
            logger.debug(f"Error finding child window: {e}")
            return None

    def get_focused_element(self):
        """
        Get the currently focused UI element using UIA.
        Returns a pywinauto wrapper object (UIAWrapper) or None.
        """
        try:
            # Use pywinauto's UIA element info to get the focused element
            import pywinauto.uia_element_info
            from pywinauto.controls.uiawrapper import UIAWrapper
            
            info = pywinauto.uia_element_info.UIAElementInfo.focused_element()
            if info:
                # Create a generic UIA wrapper for the element
                # This wrapper exposes patterns like ValuePattern via set_text/get_value
                return UIAWrapper(info)
            return None
        except Exception as e:
            logger.error(f"Error getting focused element: {e}")
            return None

    def get_dialog_element_names(self, window_handle: int) -> list[str]:
        """
        Get names of all interactive elements in a dialog.
        Useful for debugging when specific buttons can't be found.
        """
        names = []
        try:
            if Desktop:
                try:
                    win = Desktop(backend="uia").window(handle=window_handle)
                    descendants = win.descendants()
                    for desc in descendants:
                        try:
                            # Filter for likely interactive elements
                            if desc.friendly_class_name() in ["Button", "Hyperlink", "MenuItem", "Static"]:
                                text = desc.window_text()
                                if text:
                                    names.append(f"{text} ({desc.friendly_class_name()})")
                        except Exception:
                            continue
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error getting dialog elements: {e}")
        return names

    def click_element_by_name(self, window_handle: int, name: str) -> bool:
        """
        Click a UI element (button) by name within a window.
        
        Args:
            window_handle: Handle of the window containing the element
            name: Name/Title of the element to click (e.g. "Save", "Don't Save")
            
        Returns:
            True if clicked, False otherwise
        """
        try:
            win = None
            # Method A: Try Desktop object (safest for direct handle binding)
            if Desktop:
                try:
                    win = Desktop(backend="uia").window(handle=window_handle)
                except Exception:
                    pass
            
            # Method B: Try Application connect (fallback)
            if win is None and Application:
                try:
                    app = Application(backend="uia").connect(handle=window_handle)
                    win = app.window(handle=window_handle)
                except Exception:
                    pass
            
            if win is None:
                logger.error(f"Could not bind to window handle: {window_handle}")
                return False

            # Find the button (Button, Hyperlink, MenuItem - usually Button)
            # Try exact match first
            try:
                # Common control types for action buttons
                for control_type in ["Button", "Hyperlink", "MenuItem", "Pane"]:
                    try:
                        btn = win.child_window(title=name, control_type=control_type)
                        if btn.exists():
                            btn.click()
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
                
            # If pywinauto logic fails, try iterating descendants (slower but more thorough)
            try:
                descendants = win.descendants()
                available_texts = []
                for desc in descendants:
                    try:
                        text = desc.window_text()
                        if text:
                            available_texts.append(text)
                            if name.lower() == text.lower():
                                desc.click()
                                return True
                    except Exception:
                        continue
                
                logger.debug(f"Element '{name}' not found. Visible text in dialog: {available_texts[:20]}...")
            except Exception as e:
                logger.debug(f"Error iterating descendants: {e}")
                
            return False
        except Exception as e:
            logger.error(f"Error clicking element '{name}': {e}")
            return False
