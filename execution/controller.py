"""
Controller - Low-Level Execution with Context Routing
Executes actions at the OS/Web/File level based on context.

Phase-2A: Routes actions by context to appropriate handlers.
"""
import logging
import subprocess
import time
from typing import Optional
from common.actions import Action, ActionResult
from logic.modal_resolver import ModalResolver

try:
    from pywinauto import Desktop, Application
    from pywinauto.keyboard import send_keys
except ImportError:
    Desktop = None
    Application = None
    send_keys = None

try:
    import keyboard
except ImportError:
    keyboard = None


logger = logging.getLogger(__name__)


class Controller:
    """
    Multi-context execution controller.
    
    Routes actions based on context field:
    - desktop â†’ Desktop automation (pywinauto)
    - web â†’ Browser automation (Playwright)
    - file â†’ File operations (workspace-only)
    
    Must only be called after Policy Engine approval.
    """
    
    def __init__(self, browser_handler=None, file_handler=None, accessibility_client=None):
        """
        Initialize the controller.
        
        Args:
            browser_handler: BrowserHandler instance (optional)
            file_handler: FileHandler instance (optional)
            accessibility_client: AccessibilityClient instance (optional)
        """
        if Desktop is None:
            raise ImportError("pywinauto is not installed. Run: pip install pywinauto")
        
        self.browser_handler = browser_handler
        self.file_handler = file_handler
        self.accessibility_client = accessibility_client
        self.launched_apps = {}  # key: app_name, value: window_handle or UIA element
        self.active_window_handle = None # Track the most recently interacted window
        
        # Phase 1: Modal Resolver
        self.modal_resolver = ModalResolver(accessibility_client) if accessibility_client else None
        
        logger.info("Controller initialized (multi-context)")
    
    def execute_action(self, action: Action) -> ActionResult:
        """
        Execute a validated action (routes by context).
        
        Args:
            action: Type-safe Action object with context
            
        Returns:
            ActionResult with execution status
        """
        # Phase-2A: Route by context
        if action.context == "desktop":
            return self._execute_desktop_action(action)
        elif action.context == "web":
            return self._execute_web_action(action)
        elif action.context == "file":
            return self._execute_file_action(action)
        else:
            logger.error(f"Unknown context: {action.context}")
            return ActionResult(
                action=action,
                success=False,
                message="Unknown context",
                error=f"Controller does not support context: {action.context}"
            )
    
    def _execute_desktop_action(self, action: Action) -> ActionResult:
        """Execute desktop context action."""
        try:
            if action.action_type == "launch_app":
                return self._launch_app(action)
            
            elif action.action_type == "type_text":
                return self._type_text(action)
            
            elif action.action_type == "close_app":
                return self._close_app(action)
            
            elif action.action_type == "focus_window":
                return self._focus_window(action)
            
            elif action.action_type == "wait":
                return self._wait(action)
            
            elif action.action_type == "click_control":
                return self._click_control(action)
            
            else:
                logger.error(f"Unknown action type: {action.action_type}")
                return ActionResult(
                    action=action,
                    success=False,
                    message="Unknown action type",
                    error=f"Controller does not support: {action.action_type}"
                )
        
        except Exception as e:
            logger.error(f"Desktop action execution failed: {e}", exc_info=True)
            return ActionResult(
                action=action,
                success=False,
                message="Execution error",
                error=str(e)
            )
    
    def _execute_web_action(self, action: Action) -> ActionResult:
        """Execute web context action via browser handler."""
        if self.browser_handler is None:
            return ActionResult(
                action=action,
                success=False,
                message="Browser handler not available",
                error="BrowserHandler not initialized"
            )
        
        return self.browser_handler.execute_action(action)
    
    def _execute_file_action(self, action: Action) -> ActionResult:
        """Execute file context action via file handler."""
        if self.file_handler is None:
            return ActionResult(
                action=action,
                success=False,
                message="File handler not available",
                error="FileHandler not initialized"
            )
        
        return self.file_handler.execute_action(action)
    
    def _launch_app(self, action: Action) -> ActionResult:
        """
        Launch an application.
        
        Args:
            action: launch_app action with target executable
            
        Returns:
            ActionResult with execution status
        """
        target = action.target
        logger.info(f"Launching application: {target}")
        
        try:
            # Launch using subprocess (detached process)
            if target.endswith(".exe"):
                # Try to launch by name (assumes it's in PATH or Windows knows about it)
                subprocess.Popen(target, shell=True)
            else:
                # Assume it's a command
                subprocess.Popen(target, shell=True)
            
            # Give the app time to start (state-based verification happens after)
            time.sleep(2.0)
            
            # Capture window handle for precise closing later
            if self.accessibility_client:
                # Extract filename if full path provided
                app_name = target.split('\\')[-1].split('/')[-1]
                # Try finding window with retries
                window = None
                for _ in range(3):
                     window = self.accessibility_client.find_window_by_process(app_name)
                     if window:
                         break
                     time.sleep(1.0)
                
                if window:
                    self.launched_apps[target] = window
                    self.active_window_handle = window.handle
                    logger.info(f"Captured and set active window handle for {target}: {window.handle}")
                    
                    # Explicitly focus the new window to ensure subsequent typing goes to it
                    try:
                        app = Application(backend="uia").connect(handle=window.handle)
                        win = app.window(handle=window.handle)
                        win.set_focus()
                        logger.info(f"Explicitly focused launched app: {window.name}")

                        # FRESHNESS ENFORCEMENT (Phase-3C)
                        # If launching a generic editor like Notepad without a specific file argument,
                        # ensure we get a fresh document (Untitled). Windows 11 often restores previous session.
                        if "notepad" in target.lower() and "untitled" not in window.name.lower():
                             logger.info("Freshness Check: Existing document detected. Enforcing new document (Ctrl+N).")
                             # Use keyboard lib for reliability if available
                             if keyboard:
                                 time.sleep(0.5)
                                 keyboard.press_and_release("ctrl+n")
                             else:
                                 win.type_keys("^n", pause=0.5)
                             
                             time.sleep(1.0)
                             
                             # Handle potential "Do you want to save?" dialog from Ctrl+N
                             potential_dialog = self.accessibility_client.get_active_window()
                             if potential_dialog and ("save" in potential_dialog.name.lower() or "notepad" not in potential_dialog.name.lower()):
                                 logger.info("Freshness Check: Save dialog detected after Ctrl+N. Clicking 'Don't Save'.")
                                 variants = ["Don't Save", "Don't save", "No"]
                                 for btn_name in variants:
                                     if self.accessibility_client.click_element_by_name(potential_dialog.handle, btn_name):
                                         logger.info(f"Clicked '{btn_name}' to dismiss save dialog")
                                         time.sleep(0.5)
                                         break
                             
                             # Re-acquire active window (Ctrl+N might open new window or tab)
                             fg_window = self.accessibility_client.get_active_window()
                             if fg_window and "notepad" in fg_window.name.lower():
                                  self.active_window_handle = fg_window.handle
                                  self.launched_apps[target] = fg_window
                                  logger.info(f"Freshness Check: Updated active handle to {fg_window.handle}")

                    except Exception as e:
                        logger.warning(f"Failed to focus/sanitize launched app: {e}")
            
            logger.info(f"[OK] Launched: {target}")
            return ActionResult(
                action=action,
                success=True,
                message=f"Launched {target}"
            )
        
        except Exception as e:
            logger.error(f"Failed to launch {target}: {e}")
            return ActionResult(
                action=action,
                success=False,
                message="Launch failed",
                error=str(e)
            )
    
    def _type_text(self, action: Action) -> ActionResult:
        """
        Type text into the currently focused window with ghost typing protection.
        
        Phase 3 Patch (Refined):
        1. Verify foreground window
        2. If modal blocking or detected:
           - Wait for Edit control
           - Verify focus on correct control
        3. Send text
        """
        text = action.text
        logger.info(f"Typing text: '{text}'")
        
        try:
            if send_keys is None:
                raise ImportError("pywinauto keyboard module not available")
            
            target_handle = self.active_window_handle

            # Phase 3: Ghost Typing Protection
            if self.active_window_handle:
                # 1. Direct Modal Check (Strict)
                # Always check for direct children dialogs first
                child_modal = None
                if self.accessibility_client and self.accessibility_client.is_handle_valid(self.active_window_handle):
                     child_modal = self.accessibility_client.find_child_window(self.active_window_handle)
                
                modal_handle = None
                if child_modal:
                    modal_handle = child_modal.handle
                elif self.modal_resolver:
                     # Fallback to resolver (heuristics)
                     modal_handle = self.modal_resolver.check_modal_state(self.active_window_handle)
                
                if modal_handle:
                    logger.info(f"Ghost Check: Detected modal {modal_handle}. Switching target from {target_handle} to {modal_handle}")
                    
                    # Update target to the modal
                    target_handle = modal_handle
                    
                    # Heuristic: If typing a path, ensure we solve the "Save As" focus trap
                    is_file_path = any(x in text for x in ["\\", "/", ".txt", ".json", ".py", ".md", ".log"])
                    
                    if is_file_path:
                        logger.info("Ghost Check: Text looks like path. Verifying 'File name' focus...")
                        success = self._verify_modal_focus(modal_handle, "File name", set_focus=True)
                        if not success:
                            # Try "File name:" or just generic edit
                            logger.warning("Ghost Check: Specific 'File name' focus failed. Trying generic Edit focus...")
                            if not self._verify_modal_focus(modal_handle, "", set_focus=True):
                                 logger.error("Ghost Check: Failed to focus any Edit control in modal")
                    else:
                        # Ensure basic modal focus for non-path text
                        try:
                            app_temp = Application(backend="uia").connect(handle=modal_handle)
                            app_temp.window(handle=modal_handle).set_focus()
                        except Exception as e:
                            logger.debug(f"Modal focus failed: {e}")

            # Method 1: Try targeting the specific window handle
            if target_handle:
                try:
                    # If we didn't find a modal, try to find a child (e.g. editor pane)
                    # NOTE: If modal was found and set as target_handle, we skip looking for children of active_window_handle
                    # because the modal is a top-level popup usually.
                    if target_handle == self.active_window_handle and self.accessibility_client and self.accessibility_client.is_handle_valid(target_handle):
                        child = self.accessibility_client.find_child_window(target_handle)
                        if child:
                            target_handle = child.handle

                    app = Application(backend="uia").connect(handle=target_handle)
                    win = app.window(handle=target_handle)
                    
                    # Ensure focus one last time
                    win.set_focus()
                    
                    # Phase 3B: UIA Value Pattern Fix
                    # If this is a file path in a modal, try to set text value directly via UIA
                    # This prevents 'typing' issues with modifier keys (like %USERPROFILE% triggering Start Menu)
                    is_file_path = any(x in text for x in ["\\", "/", ".txt", ".json", ".py", ".md"])
                    value_pattern_success = False

                    if is_file_path and self.modal_resolver and target_handle == modal_handle:
                        try:
                            # Verify we are focused on an Edit control
                            focused_elem = self.accessibility_client.get_focused_element()
                            if focused_elem and focused_elem.control_type == "Edit":
                                logger.info("Phase 3B: Using UIA ValuePattern for safe text entry")
                                # We need the raw element to use patterns, but accessibility_client returns wrapper
                                # So we might just skip the value pattern opt for now or re-implement
                                pass
                        except Exception as vp_e:
                            logger.warning(f"UIA ValuePattern failed, falling back to typing: {vp_e}")
                    
                    if not value_pattern_success:
                        # LOGIC: Differentiate between "Command Codes" (^s, {ENTER}) and "Content Text" (filename, hi)
                        # Command codes must go through pywinauto logic.
                        # Content text should go through keyboard.write (if available) for reliability.
                        
                        is_command_code = any(marker in text for marker in ["^", "{", "}", "+", "~", "!", "#"])
                        # Exception: % is handled by keyboard.write fine, but is a special char for pywinauto.
                        # We do NOT treat % as a command code here, so paths like %USERPROFILE% go to keyboard.write path.

                        if is_command_code:
                            # PATH A: Command Codes
                            # Try to translate to 'keyboard' library for better reliability
                            translated_hotkey = None
                            
                            if keyboard:
                                # Translation Table
                                if text == "^s": translated_hotkey = "ctrl+s"
                                elif text == "^n": translated_hotkey = "ctrl+n"
                                elif text == "^o": translated_hotkey = "ctrl+o"
                                elif text == "{ENTER}": translated_hotkey = "enter"
                                elif text == "{LEFT}": translated_hotkey = "left"
                                elif text == "{RIGHT}": translated_hotkey = "right"
                                elif text == "{UP}": translated_hotkey = "up"
                                elif text == "{DOWN}": translated_hotkey = "down"
                                elif text == "{TAB}": translated_hotkey = "tab"
                                elif text == "{ESC}": translated_hotkey = "esc"
                                elif text == "{F4}": translated_hotkey = "f4"
                            
                            if translated_hotkey:
                                logger.info(f"Translated pywinauto code '{text}' to keyboard hotkey '{translated_hotkey}'")
                                try:
                                    win.set_focus()
                                    time.sleep(0.1)
                                    keyboard.press_and_release(translated_hotkey)
                                    # Verification delay
                                    time.sleep(0.1)
                                except Exception as k_err:
                                    logger.error(f"Keyboard hotkey failed: {k_err}, falling back to pywinauto")
                                    # Fallback to pywinauto below
                                    translated_hotkey = None 
                            
                            if not translated_hotkey:
                                # Legacy pywinauto path
                                logger.info("Using pywinauto for command/fallback")
                                
                                # Apply Escaping ONLY for pywinauto path
                                final_text = text
                                if is_file_path:
                                    # Escape special pywinauto characters: %, ^, +, ~, (, ), {, }
                                    # Order matters: escape { first to prevent double escaping
                                    for char in ['{', '}', '(', ')', '+', '^', '%', '~']:
                                        final_text = final_text.replace(char, f"{{{char}}}")
                                    logger.info(f"Escaped text for pywinauto: '{final_text}'")
                                
                                try:
                                    pause_val = 0.05
                                    win.type_keys(final_text, with_spaces=True, with_newlines=True, pause=pause_val)
                                except Exception as e:
                                    logger.error(f"pywinauto typing failed: {e}")
                                    # Fallback to send_keys? 
                                    send_keys(final_text, pause=0.05) if send_keys else None
                        
                        else:
                            # PATH B: Use pure keyboard injection (Content Text)
                            # Do NOT escape characters (keyboard.write handles %, {, } literally)
                            logger.info("Using keyboard.write for typing (Pure content)")
                            
                            try:
                                win.set_focus()
                                time.sleep(0.3)  # Increased wait for focus to settle
                                
                                # Paranoid: Ensure clean state
                                if keyboard:
                                     # Release potentially stuck modifiers
                                     for k in ["ctrl", "alt", "shift", "win"]:
                                         if keyboard.is_pressed(k):
                                             logger.warning(f"Forcing release of stuck key: {k}")
                                             keyboard.release(k)
                                
                                # Verify window still has focus before typing
                                time.sleep(0.1)
                                keyboard.write(text, delay=0.08)  # Slower typing for reliability
                            except Exception as e:
                                logger.error(f"keyboard.write failed: {e}")
                                # Fallback to pywinauto (with escaping)
                                final_text = text
                                for char in ['{', '}', '(', ')', '+', '^', '%', '~']:
                                    final_text = final_text.replace(char, f"{{{char}}}")
                                win.type_keys(final_text, with_spaces=True, pause=0.05)

                    logger.info(f"[OK] Typed {len(text)} chars into handle {target_handle}")
                    return ActionResult(action=action, success=True, message=f"Typed '{text}'")
                except Exception as e:
                    logger.warning(f"Typing into handle {target_handle} failed: {e}")

            # Fallback
            logger.info("Using global send_keys fallback")
            time.sleep(0.5)
            send_keys(text, pause=0.05)
            return ActionResult(action=action, success=True, message=f"Typed (global): '{text}'")

        except Exception as e:
            logger.error(f"Typing failed: {e}")
            return ActionResult(action=action, success=False, message="Typing failed", error=str(e))

    def _verify_modal_focus(self, modal_handle: int, control_name_fragment: str, set_focus: bool = False) -> bool:
        """Helper to verify or set focus on specific control in modal."""
        try:
            app = Application(backend="uia").connect(handle=modal_handle)
            win = app.window(handle=modal_handle)
            
            # Find control
            # Try Edit controls first
            for edit in win.descendants(control_type="Edit"):
                if control_name_fragment.lower() in edit.window_text().lower() or \
                   control_name_fragment.lower() in edit.element_info.name.lower():
                    if set_focus:
                        edit.set_focus()
                        logger.info(f"Set focus to control: {edit.element_info.name}")
                    return True
            
            # Try ComboBox (Save as type, etc. sometimes have File name mixed)
            for combo in win.descendants(control_type="ComboBox"):
                 if control_name_fragment.lower() in combo.element_info.name.lower():
                     if set_focus:
                         combo.set_focus()
                     return True
                     
            return False
        except Exception:
            return False
    
    def _handle_unsaved_dialog(self, dialog_handle: int, app_handle: int, action: Action) -> ActionResult:
        """
        Automatically handle unsaved changes dialog by discarding changes.
        This prevents the agent from blocking indefinitely.
        
        Args:
            dialog_handle: Handle of the discovered dialog
            app_handle: Handle of the main application window
            action: The original close_app action
            
        Returns:
            ActionResult indicating the final outcome
        """
        logger.warning(f"Unsaved changes dialog detected for {action.target}")
        logger.info("Automated handling: selecting 'Don't Save' to ensure closure.")
        
        # Try clicking "Don't Save" variants
        # Notepad Win 11 usually has "Don't save"
        # Legacy might have "No" (Save changes? Yes/No/Cancel)
        
        variants = ["Don't Save", "Don't save", "No", "Discard", "Close without saving"]
        
        for btn_name in variants:
            if self.accessibility_client.click_element_by_name(dialog_handle, btn_name):
                logger.info(f"Clicked '{btn_name}'")
                time.sleep(1.0)
                # Verify closed
                if not self.accessibility_client.is_handle_valid(app_handle):
                    return ActionResult(action=action, success=True, message=f"Closed ({btn_name})")
                
                logger.warning(f"Clicked '{btn_name}' but window still exists (maybe slow?). Assuming success or retrying forced close.")
                # Force close again if stubborn
                try:
                    Application(backend="uia").connect(handle=app_handle).window(handle=app_handle).close()
                except Exception as e:
                    logger.debug(f"Force close retry failed: {e}")
                # Re-verify
                if not self.accessibility_client.is_handle_valid(app_handle):
                     return ActionResult(action=action, success=True, message=f"Closed ({btn_name})")

        # Fallback: Keyboard shortcut (Alt+N for No, Alt+D for Don't Save)
        # We try strict "Don't Save" assumption
        try:
             logger.info("Button click failed, trying keyboard shortcuts (Alt+N then Alt+D)")
             if send_keys:
                 app = Application(backend="uia").connect(handle=dialog_handle)
                 dlg = app.window(handle=dialog_handle)
                 dlg.set_focus()
                 dlg.type_keys("%n") # Alt+N
                 time.sleep(0.5)
                 if self.accessibility_client.is_handle_valid(app_handle):
                      dlg.type_keys("%d") # Alt+D
                 
                 time.sleep(1.0)
                 if not self.accessibility_client.is_handle_valid(app_handle):
                     return ActionResult(action=action, success=True, message="Closed (Keys)")
        except Exception as e:
             logger.error(f"Keyboard fallback failed: {e}")

        logger.error("Dialog handling failed. Window remains stuck.")
        return ActionResult(
            action=action,
            success=False,
            message="Dialog handling failed",
            error="Could not find 'Don't Save' button or usage failed"
        )


    def _close_app(self, action: Action) -> ActionResult:
        """
        Close an application window.
        
        Phase-4A: Proper implementation with window finding and closing.
        Phase-5: Priority to tracked windows
        Phase-5B: Unsaved changes handling
        
        Args:
            action: close_app action with target app name
            
        Returns:
            ActionResult with execution status
        """
        target = action.target
        
        # Last line of defense for empty target
        # Should have been repaired by Planner, but handle just in case
        if not target:
             logger.error("close_app called with no target (not caught by planner)")
             return ActionResult(
                 action=action,
                 success=False,
                 message="Missing target",
                 error="Target cannot be None for close_app"
             )

        logger.info(f"Closing application: {target}")
        
        window_handle = None
        
        try:
            # 1. Priority: Tracked window
            if target in self.launched_apps:
                ui_element = self.launched_apps[target]
                window_handle = ui_element.handle
                try:
                    logger.info(f"Attempting to close tracked window for {target} (handle={window_handle})")
                    # Connect to app and close specific window
                    app = Application(backend="uia").connect(handle=window_handle)
                    win = app.window(handle=window_handle)
                    win.close()
                    # Do NOT delete from launched_apps yet - wait for verification
                except Exception as e:
                    logger.warning(f"Failed to close tracked window for {target}: {e}")
                    window_handle = None # Fallback to search

            # 2. Fallback: Search by title/text if no handle or handle interaction failed
            if not window_handle:
                desktop = Desktop(backend="uia")
                windows = desktop.windows()
                
                # ... (existing search logic remains similar but simplified for flow) ...
                matches = []
                for win in windows:
                    try:
                        if target.lower() in win.window_text().lower():
                            matches.append(win)
                    except Exception as e:
                        logger.debug(f"Error reading window text during close: {e}")
                        continue
                
                if len(matches) == 0:
                    return ActionResult(action=action, success=False, message="App not running", error="No matching window")
                
                # Use first match
                win = matches[0]
                window_handle = win.handle
                win.close()

            # 3. VERIFICATION & DIALOG HANDLING
            time.sleep(2.0) # Wait for close or dialog (increased from 1.0)
            
            # Phase-13.6 -> 14.6: Robust Close Verification
            # Issue: Notepad takes time to close, or handle remains valid briefly.
            # Strategy: Retry loop for disappearance.
            
            start_time = time.time()
            still_exists = True
            
            # 5-second timeout to wait for window death or dialog appearance
            while time.time() - start_time < 5.0:
                if not self.accessibility_client.is_handle_valid(window_handle):
                    still_exists = False
                    break
                    
                # If handle valid, check if it's a dialog
                dialog = self.accessibility_client.find_child_window(window_handle)
                if dialog:
                     logger.info("Blocking dialog detected during close wait.")
                     return self._handle_unsaved_dialog(dialog.handle, window_handle, action)

                # Check visibility
                try:
                    import pywinauto
                    app = pywinauto.Application(backend="uia").connect(handle=window_handle)
                    w = app.window(handle=window_handle)
                    if not w.is_visible():
                         logger.info("Window hidden. Considering closed.")
                         still_exists = False
                         break
                except Exception as e:
                    # Connection failed means it's gone
                    logger.debug(f"Window connection lost (closed): {e}")
                    still_exists = False
                    break
                    
                time.sleep(0.5)
            
            if still_exists:
                # One final definitive check
                 return ActionResult(action=action, success=False, message="Close failed (Window stuck)", error="Window remains visible after clear signal")
            
            # Success path
            if target in self.launched_apps:
                del self.launched_apps[target]
                
            logger.info(f"[OK] Closed window: {target}")
            return ActionResult(
                action=action,
                success=True,
                message=f"Closed {target}"
            )
        
        except Exception as e:
            logger.error(f"Failed to close app: {e}")
            return ActionResult(
                action=action,
                success=False,
                message="Close failed",
                error=str(e)
            )    
    def _focus_window(self, action: Action) -> ActionResult:
        """
        Focus a window by name or title.
        
        Phase-4A: Bring window to foreground.
        Matching order: exact match, then contains match.
        Fails if 0 or >1 matches.
        
        Args:
            action: focus_window action with target window name/title
            
        Returns:
            ActionResult with execution status
        """
        target = action.target
        logger.info(f"Focusing window: {target}")
        
        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()
            
            # First pass: exact match
            exact_matches = []
            for win in windows:
                try:
                    win_text = win.window_text()
                    if win_text.lower() == target.lower():
                        exact_matches.append(win)
                except Exception:
                    continue
            
            if len(exact_matches) == 1:
                win = exact_matches[0]
                win.set_focus()
                self.active_window_handle = win.handle
                win_text = win.window_text()
                logger.info(f"[OK] Focused window (exact match): {win_text}")
                return ActionResult(
                    action=action,
                    success=True,
                    message=f"Focused {win_text}"
                )
            elif len(exact_matches) > 1:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Multiple exact matches",
                    error=f"Found {len(exact_matches)} windows with exact name '{target}'"
                )
            
            # Second pass: contains match
            contains_matches = []
            for win in windows:
                try:
                    win_text = win.window_text()
                    if target.lower() in win_text.lower():
                        contains_matches.append(win)
                except Exception:
                    continue
            
            # Fallback: Check active application windows (for dialogs missed by Desktop walker)
            if len(contains_matches) == 0 and self.active_window_handle:
                 try:
                    # Check validity using accessibility client if possible, or just try connecting
                    # Using Application connect by handle gets the PROCESS of that window
                    app = Application(backend="uia").connect(handle=self.active_window_handle)
                    app_windows = app.windows() # Scopes to that process
                    
                    for win in app_windows:
                        try:
                            # Avoid duplicates if they were already found (check handle)
                            if any(m.handle == win.handle for m in contains_matches):
                                continue
                                
                            win_text = win.window_text()
                            if target.lower() in win_text.lower():
                                logger.info(f"Fallback search found app-specific window: {win_text}")
                                contains_matches.append(win)
                        except Exception as e:
                            logger.debug(f"Error in fallback window search: {e}")
                            continue
                 except Exception as fb_e:
                     logger.debug(f"Fallback search failed: {fb_e}")
            
            if len(contains_matches) == 0:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Window not found",
                    error=f"No window found matching '{target}'"
                )
            
            if len(contains_matches) > 1:
                window_list = [w.window_text() for w in contains_matches]
                return ActionResult(
                    action=action,
                    success=False,
                    message="Multiple windows found",
                    error=f"Found {len(contains_matches)} windows matching '{target}': {window_list}"
                )
            
            # Single contains match
            win = contains_matches[0]
            win.set_focus()
            win_text = win.window_text()
            logger.info(f"[OK] Focused window (contains match): {win_text}")
            return ActionResult(
                action=action,
                success=True,
                message=f"Focused {win_text}"
            )
        
        except Exception as e:
            logger.error(f"Failed to focus window: {e}")
            return ActionResult(
                action=action,
                success=False,
                message="Focus failed",
                error=str(e)
            )
    
    def _wait(self, action: Action) -> ActionResult:
        """
        Wait for specified duration.
        
        Phase-4A: Simple sleep with duration validation.
        Max duration enforced via config (default 30 seconds).
        
        Args:
            action: wait action with target=duration (seconds as string)
            
        Returns:
            ActionResult with execution status
        """
        duration_str = action.target
        logger.info(f"Waiting: {duration_str} seconds")
        
        try:
            duration = float(duration_str)
            
            # Validation
            if duration <= 0:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Invalid duration",
                    error=f"Duration must be > 0, got {duration}"
                )
            
            # Max duration check (default 30 seconds)
            max_duration = 30  # TODO: Load from config
            if duration > max_duration:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Duration exceeds maximum",
                    error=f"Duration {duration}s exceeds max {max_duration}s"
                )
            
            # Execute wait
            start_time = time.time()
            time.sleep(duration)
            elapsed = time.time() - start_time
            
            logger.info(f"[OK] Waited {elapsed:.2f} seconds")
            return ActionResult(
                action=action,
                success=True,
                message=f"Waited {elapsed:.2f}s"
            )
        
        except ValueError:
            return ActionResult(
                action=action,
                success=False,
                message="Invalid duration format",
                error=f"Duration must be numeric, got '{duration_str}'"
            )
        except Exception as e:
            logger.error(f"Wait failed: {e}")
            return ActionResult(
                action=action,
                success=False,
                message="Wait failed",
                error=str(e)
            )

    def _click_control(self, action: Action) -> ActionResult:
        """
        Click a generic UI control (Button, etc) by name/label.
        Prioritizes modal dialogs to support 'Save As' flows.
        Phase 1: Uses ModalResolver for robustness.
        """
        target_name = action.target
        logger.info(f"Clicking control: '{target_name}'")
        
        try:
             # 1. Resolve target context
            target_handle = self.active_window_handle
            
            # 2. Check for blocking modal dialogs via Resolver
            if self.modal_resolver and self.active_window_handle:
                 modal_handle = self.modal_resolver.check_modal_state(self.active_window_handle)
                 if modal_handle:
                      logger.info(f"ModalResolver found blocking modal: {modal_handle}. Redirecting...")
                      target_handle = modal_handle
                      
                      # Use Resolver's robust click
                      if self.modal_resolver.resolve_modal_action(target_handle, target_name):
                           return ActionResult(action=action, success=True, message=f"Clicked {target_name} (Modal)")
                      else:
                           return ActionResult(action=action, success=False, message="Modal action failed", error=f"Could not click '{target_name}' in modal")

            # Fallback to standard click if no modal or resolver disabled
            if not target_handle:
                return ActionResult(action=action, success=False, message="No active window")

            # 3. Invoke click (Standard)
            success = self.accessibility_client.click_element_by_name(target_handle, target_name)
            
            if not success and target_name.lower() == "save":
                 # Fallback: Sometimes "Save" is just "Save (Button)" or "Save (Alt+S)"
                 # Or in standard Notepad Save As dialogs, wait 0.5s and try Enter if focus is right?
                 # Better: Try partial match or standard hotkey
                 logger.info("Click 'Save' failed. Trying Alt+S hotkey fallback.")
                 try:
                     app = Application(backend="uia").connect(handle=target_handle)
                     win = app.window(handle=target_handle)
                     win.set_focus()
                     win.type_keys("%s", pause=0.1)
                     success = True
                 except Exception as e:
                     logger.warning(f"Fallback Alt+S failed: {e}")

            if success:
                logger.info(f"[OK] Clicked control '{target_name}'")
                return ActionResult(action=action, success=True, message=f"Clicked {target_name}")
            else:
                 # Debug info
                try:
                    items = self.accessibility_client.get_dialog_element_names(target_handle)
                    logger.warning(f"Control '{target_name}' not found. Visible: {items}")
                except Exception as e:
                    logger.debug(f"Failed to get dialog elements for debug: {e}")
                    items = "Unavailable"
                
                return ActionResult(
                    action=action,
                    success=False,
                    message="Control not found",
                    error=f"Could not find '{target_name}'. Visible items: {items}"
                )

        except Exception as e:
            logger.error(f"Click control failed: {e}")
            return ActionResult(action=action, success=False, message="Click failed", error=str(e))
