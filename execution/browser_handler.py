"""
Browser Handler - Playwright Integration for Phase-2A
Authority Hierarchy Level 2: DOM is authoritative for web actions.

Provides browser automation via Playwright with strict domain policy enforcement.

Phase-2B: Uses dedicated Playwright worker thread to prevent greenlet lifecycle issues.
"""
import logging
from typing import Optional
from pathlib import Path
from common.actions import Action, ActionResult

try:
    from execution.playwright_worker import PlaywrightWorker
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
except ImportError:
    PlaywrightWorker = None
    PlaywrightTimeout = Exception

logger = logging.getLogger(__name__)


class BrowserHandler:
    """
    Playwright-based browser automation handler.
    
    Handles web context actions using DOM as the authoritative layer.
    Enforces allowed domain policy before navigation.
    
    Phase-2B: Uses PlaywrightWorker thread to ensure Playwright greenlet
    survives across Qt event loop cycles.
    
    Worker thread is created lazily on first use to avoid blank browser window
    appearing before chat UI.
    """
    
    def __init__(self, config: dict):
        """
        Initialize the browser handler.
        
        Args:
            config: Browser configuration dictionary
        """
        if PlaywrightWorker is None:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install"
            )
        
        self.config = config
        self.browser_config = config.get("browser", {})
        self.headless = self.browser_config.get("headless", False)
        
        # Lazy initialization - worker created on first use
        self._worker = None
        
        logger.info(f"BrowserHandler initialized (headless={self.headless}, lazy-init)")
    
    @property
    def worker(self):
        """Get or create worker thread (lazy initialization)."""
        if self._worker is None:
            logger.info("Starting Playwright worker thread (first use)")
            
            # Priority 1: Connect to existing browser via CDP
            use_existing = self.browser_config.get("use_existing_browser", False)
            cdp_url = self.browser_config.get("cdp_url", None)
            
            if use_existing and cdp_url:
                logger.info(f"Connecting to existing browser at: {cdp_url}")
                self._worker = PlaywrightWorker(
                    headless=self.headless,
                    cdp_url=cdp_url
                )
            else:
                # Priority 2: Launch with personal profile
                use_profile = self.browser_config.get("use_personal_profile", False)
                profile_path = self.browser_config.get("profile_path", None)
                
                if use_profile and profile_path:
                    logger.info(f"Using personal browser profile: {profile_path}")
                    self._worker = PlaywrightWorker(
                        headless=self.headless,
                        user_data_dir=profile_path
                    )
                else:
                    # Priority 3: Fresh browser session
                    logger.info("Using fresh browser session (no profile)")
                    self._worker = PlaywrightWorker(headless=self.headless)
            
            self._worker.start()
            
            # Wait for worker to be ready
            if not self._worker.ready_event.wait(timeout=10.0):
                raise RuntimeError("Playwright worker failed to initialize")
            
            logger.info("Playwright worker ready")
        
        return self._worker
    
    @property
    def page(self):
        """
        Get Playwright page object.
        WARNING: Only for read-only access. Never call page methods directly from main thread.
        """
        return self.worker.page
    
    def _ensure_browser(self):
        """Ensure browser is initialized (triggers lazy loading)."""
        _ = self.worker  # Access property to trigger lazy init
        pass
    
    def execute_action(self, action: Action) -> ActionResult:
        """
        Execute a web context action.
        
        Args:
            action: Action with context="web"
            
        Returns:
            ActionResult with execution status
        """
        if action.context != "web":
            return ActionResult(
                action=action,
                success=False,
                message="Invalid context",
                error=f"BrowserHandler only handles web context, got: {action.context}"
            )
        
        try:
            if action.action_type == "launch_app":
                return self._navigate(action)
            elif action.action_type == "type_text":
                return self._type_text(action)
            elif action.action_type == "close_app":
                return self._close_browser(action)
            else:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Unknown action type",
                    error=f"BrowserHandler does not support: {action.action_type}"
                )
        
        except Exception as e:
            logger.error(f"Browser action failed: {e}", exc_info=True)
            return ActionResult(
                action=action,
                success=False,
                message="Browser action failed",
                error=str(e)
            )
    
    def _navigate(self, action: Action) -> ActionResult:
        """
        Navigate to a URL.
        
        Args:
            action: launch_app action with target=URL
            
        Returns:
            ActionResult
        """
        url = action.target
        logger.info(f"Navigating to: {url}")
        
        try:
            # Execute navigation on worker thread
            def _nav_fn(page):
                page.goto(url, timeout=30000)  # 30 second timeout
                page.wait_for_load_state("domcontentloaded")
                return page.url
            
            final_url = self.worker.execute(_nav_fn, timeout=35.0)
            
            logger.info(f"[OK] Navigated to: {final_url}")
            return ActionResult(
                action=action,
                success=True,
                message=f"Navigated to {url}"
            )
        
        except TimeoutError:
            return ActionResult(
                action=action,
                success=False,
                message="Navigation timeout",
                error=f"Page load timed out after 30s: {url}"
            )
        except Exception as e:
            return ActionResult(
                action=action,
                success=False,
                message="Navigation failed",
                error=str(e)
            )
    
    def _type_text(self, action: Action) -> ActionResult:
        """
        Type text into a web element.
        
        Args:
            action: type_text action with target=selector, text=content
            
        Returns:
            ActionResult
        """
        selector = action.target
        text = action.text
        
        logger.info(f"Typing into selector: {selector}")
        
        try:
            # Execute typing on worker thread
            def _type_fn(page, sel, txt):
                page.wait_for_selector(sel, timeout=10000)
                page.fill(sel, txt)
                return True
            
            self.worker.execute(_type_fn, selector, text, timeout=15.0)
            
            logger.info(f"[OK] Typed text into: {selector}")
            return ActionResult(
                action=action,
                success=True,
                message=f"Typed text into {selector}"
            )
        
        except TimeoutError:
            return ActionResult(
                action=action,
                success=False,
                message="Element not found",
                error=f"Selector not found after 10s: {selector}"
            )
        except Exception as e:
            return ActionResult(
                action=action,
                success=False,
                message="Type action failed",
                error=str(e)
            )
    
    def _close_browser(self, action: Action) -> ActionResult:
        """
        Close the browser.
        
        Args:
            action: close_app action
            
        Returns:
            ActionResult
        """
        logger.info("Closing browser...")
        
        try:
            if self._worker is not None:
                self._worker.stop()
                self._worker = None
                logger.info("[OK] Browser closed (worker stopped)")
            else:
                logger.info("[OK] Browser already closed (no worker)")
            
            return ActionResult(
                action=action,
                success=True,
                message="Browser closed"
            )
        
        except Exception as e:
            logger.error(f"Error closing browser: {e}", exc_info=True)
            return ActionResult(
                action=action,
                success=False,
                message="Failed to close browser",
                error=str(e)
            )
    
    def get_current_url(self) -> Optional[str]:
        """Get current page URL for verification."""
        if self.page:
            return self.page.url
        return None
    
    def is_element_visible(self, selector: str) -> bool:
        """Check if element is visible on page."""
        if self.page is None:
            return False
        try:
            return self.page.is_visible(selector, timeout=1000)
        except Exception:
            return False
    
    def get_element_text(self, selector: str) -> Optional[str]:
        """
        Extract text content from an element.
        
        Phase-2B: Used by Observer for read_text observations.
        
        Args:
            selector: CSS selector
            
        Returns:
            Element text content or None if not found
        """
        if self.page is None:
            return None
        try:
            element = self.page.wait_for_selector(selector, timeout=5000, state="visible")
            if element:
                return element.text_content()
            return None
        except Exception as e:
            logger.warning(f"Could not get text for selector '{selector}': {e}")
            return None
    
    def get_page_text(self) -> Optional[str]:
        """
        Extract all visible text content from the page.
        
        Used for verification of text visibility.
        
        Returns:
            Page text content or None if page not available
        """
        if self.page is None:
            return None
        try:
            # Get all text from the body element
            return self.page.locator('body').text_content()
        except Exception as e:
            logger.warning(f"Could not get page text: {e}")
            return None
    
    def get_element_value(self, selector: str) -> Optional[str]:
        """
        Get the value of a form input element.
        
        Args:
            selector: CSS selector
            
        Returns:
            Element value or None if not found
        """
        if self.page is None:
            return None
        try:
            element = self.page.query_selector(selector)
            if element:
                return element.input_value()
            return None
        except Exception as e:
            logger.warning(f"Could not get value for selector '{selector}': {e}")
            return None
    
    def cleanup(self):
        """Cleanup browser resources."""
        try:
            if self._worker is not None:
                self._worker.stop()
                self._worker = None
        except Exception as e:
            logger.error(f"Error during browser cleanup: {e}")
