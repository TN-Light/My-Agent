"""
Symbol Resolver - Phase-11.5B
Unified 3-layer symbol resolution system with strict Google usage rules.

Resolution Flow:
1. Symbol Memory (cache) - Instant lookup
2. TradingView Validation - Direct chart load test
3. Google Search - ONLY when allowed (SINGLE_ANALYSIS mode)

Google Usage Rules (STRICT):
- ONLY allowed in SINGLE_ANALYSIS mode
- User input must be NON-TICKER text (e.g., "tata consumer", "ktk bank")
- TradingView validation must have FAILED
- System has not already attempted Google once per session

Scanner Behavior:
- If TradingView fails → DATA_UNAVAILABLE (NOT Invalid)
- NO Google search in scan mode
- Continue scan without aborting
"""

import logging
import re
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from storage.symbol_memory import SymbolMemory

logger = logging.getLogger(__name__)


class ResolutionStatus(Enum):
    """Symbol resolution status."""
    VALID = "VALID"  # Symbol validated via TradingView
    RESOLVED = "RESOLVED"  # Symbol resolved via Google/cache
    UNKNOWN = "UNKNOWN"  # Name could not be resolved
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"  # TradingView failed, data unavailable


class ResolutionSource(Enum):
    """Where symbol was resolved from."""
    CACHE = "CACHE"  # Symbol memory cache
    TRADINGVIEW = "TRADINGVIEW"  # Direct TradingView validation
    GOOGLE = "GOOGLE"  # Google search
    USER = "USER"  # User provided exact ticker


class ResolutionConfidence(Enum):
    """Confidence level in resolution."""
    HIGH = "HIGH"  # Exact match, validated
    MEDIUM = "MEDIUM"  # Fuzzy match, likely correct
    LOW = "LOW"  # Best guess, may be wrong


class ResolutionMode(Enum):
    """Analysis mode (determines Google usage rules)."""
    SINGLE_ANALYSIS = "SINGLE_ANALYSIS"  # Normal "analyze" command
    MARKET_SCAN = "MARKET_SCAN"  # Phase-11.5 scanner
    AUTOMATED_SCAN = "AUTOMATED_SCAN"  # Future automation
    BACKTEST = "BACKTEST"  # Historical testing
    REPLAY = "REPLAY"  # Replay mode
    MULTI_INSTRUMENT = "MULTI_INSTRUMENT"  # Batch analysis


@dataclass
class SymbolResolutionResult:
    """Result of symbol resolution."""
    status: ResolutionStatus
    symbol: Optional[str]
    source: ResolutionSource
    confidence: ResolutionConfidence
    original_input: str
    error_message: Optional[str] = None


class SymbolResolver:
    """
    Unified symbol resolution system with 3-layer architecture.
    
    Layer 1: Symbol Memory (cache)
    Layer 2: TradingView validation
    Layer 3: Google search (STRICT rules)
    """
    
    def __init__(self, tradingview_client=None, llm_client=None):
        """
        Initialize symbol resolver.
        
        Args:
            tradingview_client: TradingView client for validation
            llm_client: LLM client for Google search parsing
        """
        self.symbol_memory = SymbolMemory()
        self.tradingview_client = tradingview_client
        self.llm_client = llm_client
        self.google_attempts = 0  # Track Google attempts per session
        self._last_google_search_time = 0.0  # Timestamp of last Google search
        self._google_min_interval = 30.0  # Minimum seconds between Google searches
    
    def resolve(
        self,
        user_input: str,
        mode: ResolutionMode = ResolutionMode.SINGLE_ANALYSIS,
        context: Optional[str] = None
    ) -> SymbolResolutionResult:
        """
        Resolve user input to NSE symbol.
        
        Args:
            user_input: User's symbol query (e.g., "tata consumer", "YESBANK", "ktk bank")
            mode: Analysis mode (determines Google usage)
            context: Optional context for better resolution
        
        Returns:
            SymbolResolutionResult with status, symbol, source, confidence
        """
        logger.info(f"[RESOLVER] Input: '{user_input}' | Mode: {mode.value}")
        
        # Normalize input
        normalized = user_input.strip().upper()
        
        # Layer 1: Check symbol memory cache
        cached = self.symbol_memory.lookup(user_input)
        if cached:
            return SymbolResolutionResult(
                status=ResolutionStatus.RESOLVED,
                symbol=cached.nse_symbol,
                source=ResolutionSource.CACHE,
                confidence=ResolutionConfidence[cached.confidence],
                original_input=user_input
            )
        
        # Layer 2: TradingView validation
        # Try direct ticker validation first
        if self._looks_like_ticker(normalized):
            tv_result = self._validate_via_tradingview(normalized)
            if tv_result:
                # Store in cache for future
                self.symbol_memory.store(
                    user_text=user_input,
                    nse_symbol=normalized,
                    confidence="HIGH",
                    source="TRADINGVIEW"
                )
                return tv_result
        
        # If TradingView validation failed...
        
        # Layer 3: Google search (with STRICT rules)
        if self._is_google_allowed(user_input, mode):
            google_result = self._resolve_via_google(user_input, context)
            if google_result and google_result.status == ResolutionStatus.RESOLVED:
                # Store successful Google resolution in cache
                self.symbol_memory.store(
                    user_text=user_input,
                    nse_symbol=google_result.symbol,
                    confidence=google_result.confidence.value,
                    source="GOOGLE"
                )
                return google_result
        
        # Failed to resolve
        if mode == ResolutionMode.MARKET_SCAN:
            # Scanner-safe: Mark as DATA_UNAVAILABLE, not UNKNOWN
            return SymbolResolutionResult(
                status=ResolutionStatus.DATA_UNAVAILABLE,
                symbol=None,
                source=ResolutionSource.TRADINGVIEW,
                confidence=ResolutionConfidence.LOW,
                original_input=user_input,
                error_message="TradingView data unavailable (scan mode, no Google fallback)"
            )
        else:
            return SymbolResolutionResult(
                status=ResolutionStatus.UNKNOWN,
                symbol=None,
                source=ResolutionSource.USER,
                confidence=ResolutionConfidence.LOW,
                original_input=user_input,
                error_message="Could not resolve symbol"
            )
    
    def _looks_like_ticker(self, text: str) -> bool:
        """
        Check if input looks like a ticker symbol.
        
        Tickers are typically:
        - All uppercase
        - No spaces
        - 2-15 characters
        - Alphanumeric only
        
        Examples:
        - "YESBANK" → True
        - "SBIN" → True
        - "tata consumer" → False
        - "ktk bank" → False
        """
        if not text:
            return False
        
        # Must be uppercase already (caller normalizes)
        # Must have no spaces
        if ' ' in text:
            return False
        
        # Must be 2-15 characters
        if len(text) < 2 or len(text) > 15:
            return False
        
        # Must be alphanumeric
        if not text.isalnum():
            return False
        
        return True
    
    def _validate_via_tradingview(self, symbol: str) -> Optional[SymbolResolutionResult]:
        """
        Validate symbol by attempting to load TradingView chart.
        
        Args:
            symbol: NSE symbol to validate (e.g., "YESBANK")
        
        Returns:
            SymbolResolutionResult if valid, None if validation failed
        """
        if not self.tradingview_client:
            logger.warning("[RESOLVER] TradingView client not available")
            return None
        
        try:
            # Attempt to navigate to chart
            result = self.tradingview_client.navigate_to_chart(symbol, timeframe="1D")
            
            if result.get("status") == "success":
                # Extract chart data to confirm symbol is valid
                dom_data = self.tradingview_client.extract_chart_data()
                
                if dom_data and dom_data.get('symbol') and dom_data.get('price'):
                    logger.info(f"[RESOLVER] TradingView VALIDATED: {symbol}")
                    return SymbolResolutionResult(
                        status=ResolutionStatus.VALID,
                        symbol=symbol,
                        source=ResolutionSource.TRADINGVIEW,
                        confidence=ResolutionConfidence.HIGH,
                        original_input=symbol
                    )
            
            logger.warning(f"[RESOLVER] TradingView validation failed for {symbol}")
            return None
            
        except Exception as e:
            logger.warning(f"[RESOLVER] TradingView validation error for {symbol}: {e}")
            return None
    
    def _is_google_allowed(self, user_input: str, mode: ResolutionMode) -> bool:
        """
        Check if Google search is allowed based on strict rules.
        
        Google ONLY allowed when ALL conditions met:
        1. Mode == SINGLE_ANALYSIS
        2. User input contains NON-TICKER text (e.g., "tata consumer", "ktk bank")
        3. TradingView validation FAILED
        4. System has not already attempted Google once
        
        Args:
            user_input: User's input text
            mode: Analysis mode
        
        Returns:
            True if Google search is allowed, False otherwise
        """
        # Rule 1: Must be SINGLE_ANALYSIS mode
        if mode != ResolutionMode.SINGLE_ANALYSIS:
            logger.info(f"[RESOLVER] Google BLOCKED: Mode={mode.value} (not SINGLE_ANALYSIS)")
            return False
        
        # Rule 2: Input must look like NON-TICKER text (has spaces or lowercase)
        normalized = user_input.strip().upper()
        if self._looks_like_ticker(normalized):
            logger.info(f"[RESOLVER] Google BLOCKED: '{user_input}' looks like ticker")
            return False
        
        # Rule 3: TradingView validation already failed (implicit - we're here)
        
        # Rule 4: Haven't attempted Google yet
        if self.google_attempts > 0:
            logger.info(f"[RESOLVER] Google BLOCKED: Already attempted {self.google_attempts} time(s)")
            return False
        
        # Rule 5: Rate limiting — minimum interval between Google searches
        import time
        elapsed = time.time() - self._last_google_search_time
        if elapsed < self._google_min_interval:
            remaining = self._google_min_interval - elapsed
            logger.info(f"[RESOLVER] Google RATE LIMITED: Wait {remaining:.0f}s before next search")
            return False
        
        logger.info(f"[RESOLVER] Google ALLOWED for '{user_input}'")
        return True
    
    def _resolve_via_google(
        self,
        user_input: str,
        context: Optional[str]
    ) -> Optional[SymbolResolutionResult]:
        """
        Resolve symbol via Google search (STRICT rules applied).
        
        Args:
            user_input: User's input text
            context: Optional context for better search
        
        Returns:
            SymbolResolutionResult if resolved, None if failed
        """
        if not self.llm_client:
            logger.warning("[RESOLVER] LLM client not available for Google search")
            return None
        
        self.google_attempts += 1
        import time
        self._last_google_search_time = time.time()
        logger.info(f"[RESOLVER] Attempting Google search (attempt #{self.google_attempts})")
        
        try:
            # Construct Google AI search query
            search_query = f"what is the NSE stock symbol for {user_input}"
            google_ai_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&udm=17"
            
            logger.info(f"[RESOLVER] Asking Google AI: '{search_query}'")
            
            # Get browser from TradingView client
            if not self.tradingview_client or not self.tradingview_client.browser_handler:
                logger.error("[RESOLVER] Browser not available for Google search")
                return None
            
            worker = self.tradingview_client.browser_handler.worker
            if not worker:
                logger.error("[RESOLVER] Playwright worker not ready for Google search")
                return None
            
            # Navigate and extract Google AI response
            def _search_google_ai(page):
                page.goto(google_ai_url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)  # Wait for AI response
                text = page.evaluate("() => document.body.innerText")
                lines = text.split('\n')
                filtered = [line for line in lines if line.strip() and not line.strip().isdigit() and 
                           not line.strip() in ['News', 'Images', 'Shopping', 'Videos', 'More', 'Tools']]
                return '\n'.join(filtered)
            
            search_text = worker.execute(_search_google_ai, timeout=20)
            
            # Check for CAPTCHA
            if search_text and ("not a robot" in search_text.lower() or "captcha" in search_text.lower()):
                logger.error("[RESOLVER] Google CAPTCHA detected")
                return None
            
            if not search_text:
                logger.warning("[RESOLVER] No search results from Google AI")
                return None
            
            # Use LLM to extract symbol from search results
            logger.info(f"[RESOLVER] Asking LLM to extract symbol from {len(search_text)} chars of Google results")
            
            system_prompt = "You are a stock market expert. Extract NSE stock symbols from search results."
            user_prompt = f"""Extract the NSE stock symbol from these Google search results.

User asked about: {user_input}

Google search results:
{search_text[:2000]}

Reply with ONLY the NSE stock symbol (e.g., YESBANK, TATACONSUM, SBIN).
If you cannot find a clear NSE symbol, reply with "UNKNOWN"."""
            
            llm_response = self.llm_client.generate_completion(system_prompt, user_prompt)
            symbol = llm_response.strip().upper()
            
            # Validate response
            if symbol == "UNKNOWN" or len(symbol) < 2 or len(symbol) > 15 or not symbol.isalpha():
                logger.warning(f"[RESOLVER] LLM returned invalid symbol: {symbol}")
                return None
            
            logger.info(f"[RESOLVER] LLM extracted symbol: {symbol}")
            
            # Validate via TradingView
            tv_result = self._validate_via_tradingview(symbol)
            if tv_result:
                logger.info(f"[RESOLVER] Google resolved '{user_input}' → {symbol} (validated)")
                return SymbolResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    symbol=symbol,
                    source=ResolutionSource.GOOGLE,
                    confidence=ResolutionConfidence.HIGH,
                    original_input=user_input
                )
            else:
                logger.warning(f"[RESOLVER] Google resolved '{user_input}' → {symbol} but TradingView validation failed")
                return SymbolResolutionResult(
                    status=ResolutionStatus.UNKNOWN,
                    symbol=symbol,
                    source=ResolutionSource.GOOGLE,
                    confidence=ResolutionConfidence.LOW,
                    original_input=user_input,
                    error_message="Google resolution failed TradingView validation"
                )
            
        except Exception as e:
            logger.error(f"[RESOLVER] Google search failed: {e}", exc_info=True)
            return None
    
    def health_check(self) -> bool:
        """
        Perform TradingView health check by loading NIFTY chart.
        
        Returns:
            True if TradingView is available, False otherwise
        """
        logger.info("[RESOLVER] Performing TradingView health check (NSE:NIFTY)")
        
        try:
            result = self._validate_via_tradingview("NIFTY")
            if result and result.status == ResolutionStatus.VALID:
                logger.info("[RESOLVER] TradingView health check PASSED")
                return True
            
            logger.error("[RESOLVER] TradingView health check FAILED")
            return False
            
        except Exception as e:
            logger.error(f"[RESOLVER] TradingView health check error: {e}")
            return False
    
    def reset_google_attempts(self):
        """Reset Google attempt counter (for new session)."""
        self.google_attempts = 0
        logger.debug("[RESOLVER] Google attempts counter reset")
