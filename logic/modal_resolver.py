import logging
import time
from typing import Optional, Dict, Any
import win32gui
from pywinauto.application import Application
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.keyboard import send_keys

from perception.accessibility_client import AccessibilityClient

logger = logging.getLogger(__name__)

class ModalResolver:
    """
    Utility to detect, analyze, and resolve modal dialogs blocking automation.
    Implements Phase 1 of the "Refined & Safe" architecture.
    """
    
    def __init__(self, accessibility_client: AccessibilityClient):
        self.accessibility = accessibility_client
        self.max_attempts = 2

    def check_modal_state(self, tracked_app_handle: int) -> Optional[int]:
        """
        Compare current foreground window with tracked app handle.
        Returns handle of blocking modal if detected and verified.
        
        Algorithm:
        1. GetForegroundWindow()
        2. If different from tracked_app_handle:
        3. Verify is_modal/enabled/visible
        4. Check ownership (same process or owned window)
        """
        try:
            fg_hwnd = win32gui.GetForegroundWindow()
            
            if fg_hwnd == 0 or fg_hwnd == tracked_app_handle:
                return None
            
            # Potential modal detected (Focus Shift)
            # Verify Modal State
            # 1. Visibility
            if not win32gui.IsWindowVisible(fg_hwnd):
                return None
                
            # 2. Enabled state
            if not win32gui.IsWindowEnabled(fg_hwnd):
                # If foreground is disabled, something else might be the real modal?
                # But typically the modal IS the enabled foreground window.
                return None
            
            # 3. Process Check
            # Get process ID of foreground and tracked
            import win32process
            _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
            _, tracked_pid = win32process.GetWindowThreadProcessId(tracked_app_handle)
            
            if fg_pid != tracked_pid:
                # Different process - might be system dialog or completely different app
                # For "Open with" or system dialogs spawned by app, PID might differ or be same?
                # Usually Save As is same process.
                # If user switched app manually, we should not treat as modal block usually.
                # But strictly per instruction: "Same process OR owned by tracked app"
                
                # Check ownership
                owner = win32gui.GetWindow(fg_hwnd, 4) # GW_OWNER = 4
                if owner != tracked_app_handle:
                     logger.debug(f"Focus shift to unrelated app (PID {fg_pid} != {tracked_pid})")
                     return None
            
            logger.info(f"MODAL_BLOCKED: Detected unrelated foreground window {fg_hwnd} (Title: '{win32gui.GetWindowText(fg_hwnd)}') blocking {tracked_app_handle}")
            return fg_hwnd
            
        except Exception as e:
            logger.error(f"Error checking modal state: {e}")
            return None

    def resolve_modal_action(self, modal_handle: int, action_target: str) -> bool:
        """
        Attempt to resolve the modal by clicking a button (UIA or Fallback).
        
        Args:
            modal_handle: Handle of the blocking modal
            action_target: Name of the button to click (e.g. "Save", "Don't Save")
            
        Returns:
            True if successful
        """
        logger.info(f"Attempting to resolve modal {modal_handle} with action '{action_target}'")
        
        for attempt in range(self.max_attempts):
            # 1. Multi-Signal UIA Search
            if self._click_uia_button(modal_handle, action_target):
                return True
                
            # Wait briefly before heuristic/fallback
            time.sleep(0.5)
            
            # 2. Keyboard Mnemonic Fallback
            # Only on last attempt or if UIA fails fast? 
            # "If UIA button not found within 2 seconds" -> Simplified to "If UIA fails"
            # We can try shortcuts immediately if UIA fails.
            if self._trigger_keyboard_fallback(action_target):
                return True
                
        return False

    def _click_uia_button(self, modal_handle: int, button_name: str) -> bool:
        """Search and invoke button using UIA."""
        try:
            logger.info(f"Searching for UIA button '{button_name}' in modal {modal_handle}")
            
            # Using pywinauto to wrap the handle
            app = Application(backend="uia").connect(handle=modal_handle)
            win = app.window(handle=modal_handle)
            
            # Find button - robust search
            # Try exact name first
            btn = win.child_window(title=button_name, control_type="Button")
            if btn.exists():
                btn.invoke()
                logger.info(f"Invoked UIA button '{button_name}'")
                return True
                
            # Try case-insensitive or partial
            # "Save" vs "Save button" vs "&Save"
            # Pywinauto's best_match usually handles &
            
            # If standard lookup fails, iterate descendants (expensive but safer for small modals)
            # Limit depth? Modals are usually shallow.
            for descendant in win.descendants(control_type="Button"):
                text = descendant.window_text()
                if button_name.lower() in text.lower():
                     logger.info(f"Found match '{text}', invoking...")
                     descendant.invoke()
                     return True
                     
            logger.warning(f"UIA button '{button_name}' not found")
            return False
            
        except Exception as e:
            logger.warning(f"UIA interaction failed: {e}")
            return False

    def _trigger_keyboard_fallback(self, button_name: str) -> bool:
        """Use deterministic shortcuts."""
        logger.info(f"Triggering keyboard fallback for '{button_name}'")
        
        key_map = {
            "save": "%s",      # Alt+S
            "don't save": "%d",# Alt+D
            "cancel": "{ESC}", # Escape
            "ok": "{ENTER}",   # Enter
            "yes": "%y",
            "no": "%n"
        }
        
        target_lower = button_name.lower()
        keys = None
        
        # Exact/Map match
        if target_lower in key_map:
            keys = key_map[target_lower]
        elif "save" in target_lower:
            keys = "%s"
        elif "cancel" in target_lower:
             keys = "{ESC}"
             
        if keys:
            try:
                # Ensure focus is on the modal (should be if it's foreground)
                send_keys(keys)
                logger.info(f"Sent fallback keys: {keys}")
                return True
            except Exception as e:
                logger.error(f"Keyboard fallback failed: {e}")
                return False
        
        logger.warning(f"No keyboard mapping for '{button_name}'")
        return False
