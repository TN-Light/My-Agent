"""
Playwright Worker Thread - Phase-2B Stabilization
Runs Playwright in a dedicated background thread to prevent greenlet lifecycle issues.

CRITICAL: Playwright MUST run in its own thread when used with Qt/GUI frameworks.
The greenlet dispatcher cannot survive across Qt event loop cycles.
"""
import threading
import queue
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
except ImportError:
    sync_playwright = None
    Browser = None
    BrowserContext = None
    Page = None


class PlaywrightWorker(threading.Thread):
    """
    Dedicated thread for Playwright operations.
    
    Ensures Playwright greenlet stays alive for entire agent lifetime.
    Communicates with main thread via command queue.
    """
    
    def __init__(self, headless: bool = False, user_data_dir: str = None, cdp_url: str = None):
        """
        Initialize Playwright worker thread.
        
        Args:
            headless: Whether to run browser in headless mode
            user_data_dir: Path to browser profile (e.g., Edge User Data)
            cdp_url: Chrome DevTools Protocol URL to connect to existing browser
        """
        super().__init__(daemon=True, name="PlaywrightWorker")
        
        if sync_playwright is None:
            raise ImportError("Playwright not installed")
        
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.cdp_url = cdp_url
        self.cmd_queue = queue.Queue()
        self.ready_event = threading.Event()
        
        # Playwright objects (owned by worker thread only)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        logger.info("PlaywrightWorker initialized")
    
    def run(self):
        """
        Worker thread main loop.
        Initializes Playwright and processes commands until shutdown.
        """
        try:
            # Initialize Playwright (thread-pinned)
            logger.info("Starting Playwright in worker thread...")
            self.playwright = sync_playwright().start()
            
            # Choose connection method
            if self.cdp_url:
                # Connect to existing browser via CDP (recommended)
                logger.info(f"Connecting to existing browser via CDP: {self.cdp_url}")
                try:
                    self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
                    # Get existing context or create new one
                    contexts = self.browser.contexts
                    if contexts:
                        self.context = contexts[0]
                        logger.info(f"Using existing context with {len(self.context.pages)} pages")
                    else:
                        self.context = self.browser.new_context()
                        logger.info("Created new context in existing browser")
                    
                    # Get existing page or create new tab
                    if self.context.pages:
                        self.page = self.context.pages[-1]  # Use last active page
                        logger.info(f"Using existing page: {self.page.url}")
                    else:
                        self.page = self.context.new_page()
                        logger.info("Created new tab in existing browser")
                        
                except Exception as e:
                    logger.error(f"Failed to connect to existing browser: {e}")
                    logger.info("Falling back to launching new browser...")
                    self.cdp_url = None  # Disable CDP and fall through to launch
            
            if not self.cdp_url:
                # Launch browser with or without user profile
                if self.user_data_dir:
                    logger.info(f"Launching browser with user profile: {self.user_data_dir}")
                    try:
                        # Use persistent context (Edge/Chrome profile with cookies/login)
                        self.context = self.playwright.chromium.launch_persistent_context(
                            user_data_dir=self.user_data_dir,
                            headless=self.headless,
                            channel="msedge",  # Use installed Edge browser
                            args=[
                                "--disable-blink-features=AutomationControlled",  # Hide automation
                                "--disable-automation",
                                "--disable-infobars",
                                "--ignore-certificate-errors",  # Phase-11.5G: SSL bypass for Google/TradingView
                                "--ignore-ssl-errors=yes",
                                "--disable-web-security"
                            ]
                        )
                        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                        self.browser = None  # Not used in persistent context
                    except Exception as profile_error:
                        logger.error(f"Failed to use profile {self.user_data_dir}: {profile_error}")
                        logger.warning("Falling back to fresh session without profile...")
                        # Fallback to fresh session
                        self.browser = self.playwright.chromium.launch(
                            headless=self.headless,
                            channel="msedge",
                            args=[
                                "--ignore-certificate-errors",  # Phase-11.5G: SSL bypass
                                "--ignore-ssl-errors=yes",
                                "--disable-web-security"
                            ]
                        )
                        self.context = self.browser.new_context()
                        self.page = self.context.new_page()
                else:
                    logger.info("Launching browser without user profile (fresh session)")
                    self.browser = self.playwright.chromium.launch(
                        headless=self.headless,
                        args=[
                            "--ignore-certificate-errors",  # Phase-11.5G: SSL bypass
                            "--ignore-ssl-errors=yes",
                            "--disable-web-security"
                        ]
                    )
                    self.context = self.browser.new_context()
                    self.page = self.context.new_page()
            
            logger.info("Playwright ready (thread-pinned, will never exit)")
            self.ready_event.set()
            
            # Command processing loop
            while True:
                try:
                    cmd = self.cmd_queue.get(timeout=1.0)
                    
                    if cmd is None:
                        # Shutdown signal
                        logger.info("PlaywrightWorker shutdown requested")
                        break
                    
                    fn, args, kwargs, result_queue = cmd
                    
                    try:
                        # Execute function with page object
                        result = fn(self.page, *args, **kwargs)
                        result_queue.put(("success", result))
                    except Exception as e:
                        logger.error(f"Playwright command failed: {e}", exc_info=True)
                        result_queue.put(("error", e))
                    
                except queue.Empty:
                    # Timeout, continue loop
                    continue
                    
        except Exception as e:
            logger.error(f"PlaywrightWorker crashed: {e}", exc_info=True)
            self.ready_event.set()  # Unblock waiting threads
        finally:
            # Cleanup
            self._cleanup()
    
    def execute(self, fn: Callable, *args, timeout: float = 60.0, **kwargs) -> Any:
        """
        Execute a function on the Playwright page (thread-safe).
        
        Args:
            fn: Function to execute. Must accept page as first argument.
            args: Positional arguments to pass to fn
            timeout: Maximum time to wait for result (seconds)
            kwargs: Keyword arguments to pass to fn
            
        Returns:
            Result from fn
            
        Raises:
            Exception: If fn raises an exception
            TimeoutError: If execution exceeds timeout
        """
        if not self.ready_event.is_set():
            # Wait for worker to be ready
            if not self.ready_event.wait(timeout=10.0):
                raise RuntimeError("PlaywrightWorker failed to initialize")
        
        result_queue = queue.Queue()
        self.cmd_queue.put((fn, args, kwargs, result_queue))
        
        try:
            status, result = result_queue.get(timeout=timeout)
            
            if status == "error":
                raise result
            
            return result
            
        except queue.Empty:
            raise TimeoutError(f"Playwright command timed out after {timeout}s")
    
    def _cleanup(self):
        """Cleanup Playwright resources."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Playwright cleanup complete")
        except Exception as e:
            logger.error(f"Error during Playwright cleanup: {e}")
    
    def shutdown(self):
        """Gracefully shutdown the worker thread."""
        logger.info("Shutting down PlaywrightWorker...")
        self.cmd_queue.put(None)
        self.join(timeout=5.0)
