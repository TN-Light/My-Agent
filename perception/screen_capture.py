"""
Screen Capture - Phase-2C Vision Integration
Captures screen content for VLM analysis (observation only).

Phase-2C: Vision is Level 4 authority (lowest) - proposal layer only.
"""
import logging
from typing import Optional, Tuple, List
from PIL import Image, ImageGrab
import pywinauto
import win32gui
import win32ui
import win32con
import ctypes

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    Screen capture utility for vision-based observations.
    
    Phase-2C: Captures screen content for VLM analysis only.
    Phase-10D: Adds Window-Handle capture to ignore Agent UI occlusion.
    
    Vision never triggers actions - it's observation/verification only.
    """
    
    def __init__(self):
        """Initialize screen capture."""
        logger.info("ScreenCapture initialized (Phase-2C/10D)")

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        """Get the screen coordinates (left, top, right, bottom) of a window."""
        try:
            return win32gui.GetWindowRect(hwnd)
        except Exception:
            return (0, 0, 0, 0)
    
    def capture_active_app(self, exclude_titles: List[str] = None) -> tuple[Optional[Image.Image], str]:
        """
        Capture the foreground application window, excluding specified titles.
        Uses PrintWindow to bypass occlusion (e.g., Agent UI covering target).
        
        Args:
            exclude_titles: List of window titles to ignore (e.g., ["My Agent"])
            
        Returns:
            (PIL Image or None, Window Title)
        """
        if exclude_titles is None:
            exclude_titles = []
        
        # Add system windows and overlays to exclusions
        system_excludes = ["Settings", "Task Manager", "Program Manager", 
                          "NVIDIA GeForce", "Discord Overlay", "Steam Overlay",
                          "Xbox Game Bar", "GeForce Experience"]
        all_excludes = exclude_titles + system_excludes
            
        try:
            # First try: Get actual foreground window
            import time
            time.sleep(0.3)  # Brief delay for focus to settle
            
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd:
                title = win32gui.GetWindowText(foreground_hwnd).strip()
                # Check if foreground window is excluded
                if title and not any(ex in title for ex in all_excludes):
                    safe_title = title.encode('ascii', 'ignore').decode('ascii')
                    logger.info(f"Phase-10D: Capturing foreground window: '{safe_title}'")
                    return self._capture_window_printwindow(foreground_hwnd), title
            
            # Fallback: Find largest NON-FULLSCREEN window (ignores overlays)
            windows = []
            
            def enum_window_callback(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return
                
                # Check exclusions
                if any(ex in title for ex in all_excludes):
                    return
                
                # Get window size
                try:
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    width = right - left
                    height = bottom - top
                    area = width * height
                    
                    # Ignore fullscreen windows (likely overlays) and tiny windows
                    screen_area = 1920 * 1080  # Common fullscreen
                    is_fullscreen = area > screen_area * 0.95  # 95% of screen = fullscreen
                    
                    if not is_fullscreen and area > 100000:  # At least 100k px²
                        windows.append((hwnd, title, area))
                except Exception:
                    pass  # Some windows may not have valid rects

            win32gui.EnumWindows(enum_window_callback, None)
            
            # Sort by area (largest first) and take the biggest non-fullscreen
            if windows:
                windows.sort(key=lambda x: x[2], reverse=True)
                target_hwnd, title, area = windows[0]
                # Sanitize title for logging to prevent encoding errors
                safe_title = title.encode('ascii', 'ignore').decode('ascii')
                logger.info(f"Phase-10D: Capturing largest non-fullscreen window: '{safe_title}' ({area} px²)")
                return self._capture_window_printwindow(target_hwnd), title
            else:
                logger.warning("No suitable target window found for active capture.")
                return None, ""
                
        except Exception as e:
            logger.error(f"Failed to find/capture active app: {e}")
            return None, ""

    def _capture_window_printwindow(self, hwnd) -> Optional[Image.Image]:
        """
        Helper: Capture window using PrintWindow API (ignores occlusion).
        """
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            if width <= 0 or height <= 0:
                logger.warning(f"Window has invalid dimensions: {width}x{height}")
                return None

            # Create compatible DC
            hwindc = win32gui.GetWindowDC(hwnd)
            srcdc = win32ui.CreateDCFromHandle(hwindc)
            # Create a memory DC compatible with the *source* DC (screen) usually works best
            # But using CreateCompatibleDC from the win32ui object
            memdc = srcdc.CreateCompatibleDC()
            
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(srcdc, width, height)
            memdc.SelectObject(bmp)
            
            # PrintWindow with PW_RENDERFULLCONTENT (0x00000002)
            # This asks the window to render itself to the bitmap
            result = ctypes.windll.user32.PrintWindow(hwnd, memdc.GetSafeHdc(), 2)
            
            if result != 1:
                # Fallback to standard PrintWindow (0) if flag invalid?
                logger.warning("PrintWindow (Full) failed, trying default")
                result = ctypes.windll.user32.PrintWindow(hwnd, memdc.GetSafeHdc(), 0)
            
            if result == 1:
                bmpinfo = bmp.GetInfo()
                bmpstr = bmp.GetBitmapBits(True)
                image = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )
            else:
                logger.error("PrintWindow API failed")
                image = None
                
            # Cleanup
            win32gui.DeleteObject(bmp.GetHandle())
            memdc.DeleteDC()
            srcdc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwindc)
            
            return image
            
        except Exception as e:
            logger.error(f"Low-level capture error: {e}")
            return None

    def find_window_by_title(self, title_query: str) -> Optional[int]:
        """
        Find a window handle (HWND) by fuzzy title match.
        Phase-10E: Intent-Aware Selection helper.
        """
        target_hwnd = None
        
        def enum_callback(hwnd, _):
            nonlocal target_hwnd
            if target_hwnd: return
            
            if not win32gui.IsWindowVisible(hwnd): return
            title = win32gui.GetWindowText(hwnd).strip()
            
            if title_query.lower() in title.lower():
                target_hwnd = hwnd
        
        try:
            win32gui.EnumWindows(enum_callback, None)
            return target_hwnd
        except Exception as e:
            logger.error(f"Error finding window '{title_query}': {e}")
            return None

    def capture_window_handle(self, hwnd: int) -> tuple[Optional[Image.Image], str]:
        """
        Capture a specific window by handle (Phase-10E).
        Restores minimized windows before capture to avoid tiny screenshots.
        Returns: (image, window_title)
        """
        try:
            title = win32gui.GetWindowText(hwnd)
            
            # Restore window if minimized — GetWindowRect returns tiny rect for minimized windows
            if win32gui.IsIconic(hwnd):
                logger.info(f"Window '{title}' is minimized — restoring before capture")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                import time
                time.sleep(0.5)  # Wait for window to restore
            
            # Validate window dimensions before capture
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width < 200 or height < 200:
                logger.warning(f"Window '{title}' too small ({width}x{height}) — attempting restore")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                import time
                time.sleep(0.5)
            
            logger.info(f"Phase-10E: Capturing specific window: '{title}'")
            return self._capture_window_printwindow(hwnd), title
        except Exception as e:
            logger.error(f"Failed to capture handle {hwnd}: {e}")
            return None, ""

    def capture_active_window(self) -> Optional[Image.Image]:
        """
        Capture the currently active/focused window.
        
        Returns:
            PIL Image of active window or None if capture fails
        """
        try:
            # Get active window using pywinauto
            app = pywinauto.Application(backend="uia").connect(active_only=True)
            window = app.top_window()
            
            # Get window rectangle
            rect = window.rectangle()
            
            # Capture region
            screenshot = ImageGrab.grab(bbox=(
                rect.left,
                rect.top,
                rect.right,
                rect.bottom
            ))
            
            logger.info(f"Captured active window: {window.window_text()} ({rect.width()}x{rect.height()})")
            return screenshot
            
        except Exception as e:
            logger.warning(f"Failed to capture active window: {e}")
            return None
    
    def capture_full_screen(self) -> Optional[Image.Image]:
        """
        Capture the entire screen.
        
        Returns:
            PIL Image of full screen or None if capture fails
        """
        try:
            screenshot = ImageGrab.grab()
            width, height = screenshot.size
            logger.info(f"Captured full screen ({width}x{height})")
            return screenshot
            
        except Exception as e:
            logger.error(f"Failed to capture full screen: {e}")
            return None
    
    def capture_region(self, left: int, top: int, right: int, bottom: int) -> Optional[Image.Image]:
        """
        Capture a specific screen region.
        
        Args:
            left: Left coordinate
            top: Top coordinate
            right: Right coordinate
            bottom: Bottom coordinate
            
        Returns:
            PIL Image of region or None if capture fails
        """
        try:
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            width = right - left
            height = bottom - top
            logger.info(f"Captured region ({width}x{height})")
            return screenshot
            
        except Exception as e:
            logger.error(f"Failed to capture region: {e}")
            return None
    
    def save_screenshot(self, image: Image.Image, path: str) -> bool:
        """
        Save screenshot to file (for debugging).
        
        Args:
            image: PIL Image to save
            path: File path
            
        Returns:
            True if saved successfully
        """
        try:
            image.save(path)
            logger.info(f"Saved screenshot: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return False
