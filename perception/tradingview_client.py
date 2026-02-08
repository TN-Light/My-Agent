"""
TradingView Client - Phase-2B Market Analysis
Playwright-based navigation for TradingView chart observation.

STRICTLY READ-ONLY:
- Navigate to symbol charts
- Switch timeframes (if DOM-accessible)
- Extract DOM data (price, indicators)
- NO chart drawing
- NO coordinate clicks
- NO trading execution

Phase-2B: Uses BrowserHandler worker pattern for thread-safe Playwright access.
"""
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class TradingViewClient:
    """
    TradingView navigation and DOM extraction client.
    
    Phase-2B: Read-only chart observation via Playwright worker thread.
    Authority: DOM is authoritative for all data.
    Vision is used only for trend/support/resistance (advisory).
    """
    
    def __init__(self, config: dict, browser_handler):
        """
        Initialize TradingView client.
        
        Args:
            config: Market analysis configuration dict
            browser_handler: BrowserHandler instance with PlaywrightWorker
        """
        self.config = config
        self.browser_handler = browser_handler
        self.ma_config = config.get("market_analysis", {})
        self.tv_config = self.ma_config.get("tradingview", {})
        self.base_url = self.tv_config.get("base_url", "https://www.tradingview.com")
        self.chart_load_timeout = self.tv_config.get("chart_load_timeout", 15)  # seconds
        
        logger.info("TradingViewClient initialized (read-only mode)")
    
    def navigate_to_chart(self, symbol: str, timeframe: Optional[str] = None) -> Dict[str, Any]:
        """
        Navigate to a TradingView chart for the given symbol.
        
        Args:
            symbol: Stock symbol (e.g., "TCS", "RELIANCE", "NIFTY")
            timeframe: Optional timeframe (e.g., "1D", "1H", "15")
            
        Returns:
            Dict with status and navigation details
        """
        logger.info(f"Navigating to TradingView chart: {symbol}")
        
        try:
            # Construct chart URL
            if not symbol.startswith(("NSE:", "BSE:", "NASDAQ:", "NYSE:")):
                symbol = f"NSE:{symbol.upper()}"
            
            chart_url = f"{self.base_url}/chart/?symbol={symbol}"
            if timeframe:
                chart_url += f"&interval={timeframe}"
            
            # Navigate using worker thread
            def _navigate(page):
                page.goto(chart_url, timeout=self.chart_load_timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_selector("div[class*='chart-container']", timeout=self.chart_load_timeout * 1000)
                time.sleep(2)  # Wait for price to render
                return page.url
            
            final_url = self.browser_handler.worker.execute(_navigate, timeout=self.chart_load_timeout + 5)
            
            logger.info(f"[OK] Navigated to {symbol} chart")
            return {
                "status": "success",
                "symbol": symbol,
                "url": final_url,
                "message": f"Chart loaded for {symbol}"
            }
            
        except TimeoutError:
            logger.error(f"Timeout loading chart for {symbol}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": "Chart load timeout (>15s)"
            }
        except Exception as e:
            logger.error(f"Failed to navigate to chart: {e}", exc_info=True)
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }
    
    def extract_chart_data(self) -> Dict[str, Any]:
        """
        Extract chart data from DOM.
        
        DOM is authoritative for:
        - Symbol name
        - Current price
        - Timeframe
        - Indicator values (if visible in legend)
        
        Returns:
            Dict with extracted data
        """
        logger.info("Extracting chart data from DOM")
        
        try:
            # Capture config outside closure
            default_timeframe = self.tv_config.get("default_timeframe", "1D")
            
            # Extract all data in worker thread
            def _extract(page):
                import re
                data = {
                    "symbol": None,
                    "price": None,
                    "change": None,
                    "timeframe": default_timeframe,  # Default to requested timeframe
                    "indicators": {},
                    "volume": None,
                    "volume_change": None
                }
                
                # Wait for chart to fully load
                time.sleep(2)
                
                # Extract from page title (most reliable)
                try:
                    title = page.title()
                    # Title format: "RELIANCE 1,437.10 +3.36% - TradingView"
                    if title:
                        parts = title.split()
                        if len(parts) >= 2:
                            data["symbol"] = parts[0]
                            # Extract price (remove commas)
                            if len(parts) >= 2:
                                price_str = parts[1].replace(",", "")
                                try:
                                    # Remove any non-numeric except decimal point
                                    price_clean = ''.join(c for c in price_str if c.isdigit() or c == '.')
                                    if price_clean:
                                        data["price"] = price_clean
                                except (ValueError, TypeError):
                                    pass
                            # Extract change
                            if len(parts) >= 3:
                                change_raw = parts[2]
                                # Remove unicode arrows that cause logging errors
                                change_clean = change_raw.replace("▲", "+").replace("▼", "-").replace("△", "+").replace("▽", "-")
                                data["change"] = change_clean
                except Exception as e:
                    logger.warning(f"Failed to extract from title: {e}")
                
                # Try to extract symbol from header if title failed
                if not data["symbol"]:
                    try:
                        # Look for any text containing the symbol
                        header_text = page.locator("div[data-name='legend-source-item']").first.text_content(timeout=2000)
                        if header_text:
                            # Format: "Reliance Industries Limited · 1W · NSE"
                            data["symbol"] = header_text.split("·")[0].strip()
                    except Exception:
                        pass  # Header element may not exist
                
                # Extract timeframe from URL
                try:
                    current_url = page.url
                    if "interval=" in current_url:
                        # Extract interval parameter
                        interval = current_url.split("interval=")[1].split("&")[0]
                        data["timeframe"] = interval
                except (ValueError, IndexError):
                    pass  # URL may not contain interval param
                
                # If still no symbol, try from the symbol input
                if not data["symbol"]:
                    try:
                        symbol_input = page.locator("input[data-role='search']").first
                        if symbol_input:
                            value = symbol_input.get_attribute("value", timeout=1000)
                            if value:
                                # Format might be "NSE:RELIANCE"
                                data["symbol"] = value.split(":")[-1]
                    except Exception:
                        pass  # Symbol input may not be present
                
                # ─── Phase-15: Enhanced DOM Extraction ─────────────────────
                # Extract indicator values from chart legend area
                try:
                    legend_items = page.locator("div[data-name='legend-source-item']").all()
                    for item in legend_items:
                        try:
                            item_text = item.text_content(timeout=1000)
                            if not item_text:
                                continue
                            item_text = item_text.strip()
                            text_lower = item_text.lower()
                            
                            # Moving Averages: "EMA (20) 1,450.25" or "SMA (50) 1,420.00"
                            if any(ma in text_lower for ma in ('ema', 'sma', 'wma')):
                                ma_match = re.search(r'(e?s?w?ma)\s*\(?\s*(\d+)\s*\)?\D*([\d,]+\.?\d*)', item_text, re.IGNORECASE)
                                if ma_match:
                                    ma_type = ma_match.group(1).upper()
                                    ma_period = ma_match.group(2)
                                    ma_value = ma_match.group(3).replace(',', '')
                                    data["indicators"][f"{ma_type}({ma_period})"] = ma_value
                            
                            # RSI: "RSI (14) 65.32"
                            elif 'rsi' in text_lower:
                                rsi_match = re.search(r'rsi\D*(\d+)\D*([\d.]+)', item_text, re.IGNORECASE)
                                if rsi_match:
                                    data["indicators"][f"RSI({rsi_match.group(1)})"] = rsi_match.group(2)
                            
                            # MACD
                            elif 'macd' in text_lower:
                                macd_match = re.search(r'macd\D*([-\d,.]+)', item_text, re.IGNORECASE)
                                if macd_match:
                                    data["indicators"]["MACD"] = macd_match.group(1).replace(',', '')
                            
                            # Volume from legend
                            elif 'vol' in text_lower and not data["volume"]:
                                vol_match = re.search(r'([\d,]+\.?\d*)\s*([KMB]?)', item_text)
                                if vol_match:
                                    data["volume"] = vol_match.group(1).replace(',', '') + vol_match.group(2)
                                    
                        except Exception:
                            continue
                            
                except Exception as e:
                    logger.debug(f"Indicator extraction from legend: {e}")
                
                # Extract OHLC values from the chart header/series legend
                try:
                    ohlc_selectors = [
                        "div[data-name='legend-series-item']",
                        "div[class*='valuesWrapper']"
                    ]
                    for selector in ohlc_selectors:
                        try:
                            ohlc_el = page.locator(selector).first
                            ohlc_text = ohlc_el.text_content(timeout=1500)
                            if ohlc_text and any(c.isdigit() for c in ohlc_text):
                                numbers = re.findall(r'[\d,]+\.?\d+', ohlc_text)
                                if len(numbers) >= 4:
                                    data["indicators"]["Open"] = numbers[0].replace(',', '')
                                    data["indicators"]["High"] = numbers[1].replace(',', '')
                                    data["indicators"]["Low"] = numbers[2].replace(',', '')
                                    data["indicators"]["Close"] = numbers[3].replace(',', '')
                                if len(numbers) >= 5 and not data["volume"]:
                                    data["volume"] = numbers[4].replace(',', '')
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"OHLC extraction: {e}")
                
                # Volume from dedicated volume panel
                if not data["volume"]:
                    try:
                        vol_el = page.locator("div[data-name='legend-source-item']:has-text('Vol')").first
                        vol_text = vol_el.text_content(timeout=1500)
                        if vol_text:
                            vol_match = re.search(r'([\d,]+\.?\d*)\s*([KMB]?)', vol_text)
                            if vol_match:
                                data["volume"] = vol_match.group(1).replace(',', '') + vol_match.group(2)
                    except Exception:
                        pass
                
                # ─── Phase-D: Deep JavaScript Extraction ──────────────────
                # Extract data from TradingView's internal chart widget via JS evaluation.
                # This bypasses VLM for numeric data that VLMs read poorly.
                try:
                    deep_data = page.evaluate("""() => {
                        const result = {
                            indicators_deep: {},
                            candles: [],
                            technicals_rating: null,
                            price_scale: null,
                            all_studies: []
                        };
                        
                        // Method 1: Extract from TradingView's legend values (more reliable selectors)
                        try {
                            const legendValues = document.querySelectorAll('[class*="legendWrapper"] [class*="value"]');
                            if (legendValues.length > 0) {
                                result.indicators_deep['legend_value_count'] = legendValues.length;
                            }
                        } catch(e) {}
                        
                        // Method 2: Extract ALL legend source items with their values
                        try {
                            const sources = document.querySelectorAll("div[data-name='legend-source-item']");
                            for (const src of sources) {
                                const titleEl = src.querySelector("[class*='title']");
                                const valEls = src.querySelectorAll("[class*='value']");
                                if (titleEl) {
                                    const title = titleEl.textContent.trim();
                                    const vals = Array.from(valEls).map(v => v.textContent.trim()).filter(v => v);
                                    if (vals.length > 0) {
                                        result.all_studies.push({
                                            name: title,
                                            values: vals
                                        });
                                    }
                                }
                            }
                        } catch(e) {}
                        
                        // Method 3: Extract study values via the indicator panel
                        try {
                            // Bollinger Bands
                            const allText = document.body.innerText;
                            const bbMatch = allText.match(/BB\\s*\\((\\d+)[^)]*\\)[^\\d]*(\\d[\\d,.]+).*?(\\d[\\d,.]+).*?(\\d[\\d,.]+)/i);
                            if (bbMatch) {
                                result.indicators_deep['BB_period'] = bbMatch[1];
                                result.indicators_deep['BB_upper'] = bbMatch[2].replace(/,/g, '');
                                result.indicators_deep['BB_middle'] = bbMatch[3].replace(/,/g, '');
                                result.indicators_deep['BB_lower'] = bbMatch[4].replace(/,/g, '');
                            }
                            
                            // Stochastic
                            const stochMatch = allText.match(/Stoch(?:astic)?\\s*\\(([^)]+)\\)[^\\d]*(\\d+\\.?\\d*)[^\\d]*(\\d+\\.?\\d*)/i);
                            if (stochMatch) {
                                result.indicators_deep['Stoch_K'] = stochMatch[2];
                                result.indicators_deep['Stoch_D'] = stochMatch[3];
                            }
                            
                            // VWAP
                            const vwapMatch = allText.match(/VWAP[^\\d]*(\\d[\\d,.]+\\.?\\d*)/i);
                            if (vwapMatch) {
                                result.indicators_deep['VWAP'] = vwapMatch[1].replace(/,/g, '');
                            }
                            
                            // Supertrend
                            const stMatch = allText.match(/Supertrend[^\\d]*(\\d[\\d,.]+\\.?\\d*)/i);
                            if (stMatch) {
                                result.indicators_deep['Supertrend'] = stMatch[1].replace(/,/g, '');
                            }
                            
                            // ADX
                            const adxMatch = allText.match(/ADX[^\\d]*(\\d+\\.?\\d*)/i);
                            if (adxMatch) {
                                result.indicators_deep['ADX'] = adxMatch[1];
                            }
                            
                            // ATR
                            const atrMatch = allText.match(/ATR[^\\d]*(\\d[\\d,.]*\\.?\\d*)/i);
                            if (atrMatch) {
                                result.indicators_deep['ATR'] = atrMatch[1].replace(/,/g, '');
                            }
                        } catch(e) {}
                        
                        // Method 4: Extract price scale range (Y-axis bounds)
                        try {
                            const scaleLabels = document.querySelectorAll("[class*='price-axis'] [class*='label']");
                            const prices = [];
                            for (const label of scaleLabels) {
                                const t = label.textContent.trim().replace(/,/g, '');
                                const v = parseFloat(t);
                                if (!isNaN(v) && v > 0) prices.push(v);
                            }
                            if (prices.length >= 2) {
                                prices.sort((a, b) => a - b);
                                result.price_scale = {
                                    min: prices[0],
                                    max: prices[prices.length - 1],
                                    labels: prices
                                };
                            }
                        } catch(e) {}
                        
                        // Method 5: TradingView Technicals Rating widget (if present)
                        try {
                            const techEl = document.querySelector("[class*='speedometer'], [class*='recommendation']");
                            if (techEl) {
                                result.technicals_rating = techEl.textContent.trim();
                            }
                        } catch(e) {}
                        
                        return result;
                    }""")
                    
                    if deep_data:
                        # Merge deep indicators
                        deep_indicators = deep_data.get('indicators_deep', {})
                        for k, v in deep_indicators.items():
                            if k not in ('legend_value_count',) and v:
                                data["indicators"][k] = v
                        
                        # Extract additional indicators from all_studies
                        for study in deep_data.get('all_studies', []):
                            name = study.get('name', '')
                            vals = study.get('values', [])
                            name_lower = name.lower()
                            
                            # Extract Bollinger Bands values
                            if 'bollinger' in name_lower or 'bb' in name_lower:
                                if len(vals) >= 3:
                                    data["indicators"]["BB_upper"] = vals[0].replace(',', '')
                                    data["indicators"]["BB_middle"] = vals[1].replace(',', '') if len(vals) > 1 else None
                                    data["indicators"]["BB_lower"] = vals[2].replace(',', '') if len(vals) > 2 else None
                            
                            # Extract Stochastic
                            elif 'stoch' in name_lower:
                                if len(vals) >= 2:
                                    data["indicators"]["Stoch_K"] = vals[0]
                                    data["indicators"]["Stoch_D"] = vals[1]
                            
                            # VWAP
                            elif 'vwap' in name_lower:
                                if vals:
                                    data["indicators"]["VWAP"] = vals[0].replace(',', '')
                            
                            # ADX
                            elif 'adx' in name_lower:
                                if vals:
                                    data["indicators"]["ADX"] = vals[0]
                            
                            # ATR  
                            elif 'atr' in name_lower:
                                if vals:
                                    data["indicators"]["ATR"] = vals[0].replace(',', '')
                            
                            # Supertrend
                            elif 'supertrend' in name_lower:
                                if vals:
                                    data["indicators"]["Supertrend"] = vals[0].replace(',', '')
                            
                            # Additional MAs/EMAs not caught by Phase-15
                            elif any(ma in name_lower for ma in ('ema', 'sma', 'wma')):
                                ma_match = re.search(r'(e?s?w?ma)\s*\(?(\d+)\)?', name, re.IGNORECASE)
                                if ma_match and vals:
                                    key = f"{ma_match.group(1).upper()}({ma_match.group(2)})"
                                    if key not in data["indicators"]:
                                        data["indicators"][key] = vals[0].replace(',', '')
                        
                        # Store price scale
                        price_scale = deep_data.get('price_scale')
                        if price_scale:
                            data["price_scale"] = price_scale
                        
                        # Technicals rating
                        rating = deep_data.get('technicals_rating')
                        if rating:
                            data["technicals_rating"] = rating
                        
                        deep_count = len([k for k in data["indicators"] if k not in ('Open', 'High', 'Low', 'Close')])
                        if deep_count > 0:
                            logger.info(f"Phase-D: Deep JS extraction yielded {deep_count} indicator values")
                            
                except Exception as e:
                    logger.debug(f"Phase-D: Deep JS extraction failed (non-critical): {e}")
                
                if data.get("indicators"):
                    logger.info(f"Phase-D: All extracted indicators: {list(data['indicators'].keys())}")
                if data.get("volume"):
                    logger.info(f"Phase-D: Volume from DOM: {data['volume']}")
                
                return data
            
            # Execute extraction in worker thread
            data = self.browser_handler.worker.execute(_extract, timeout=10)
            
            logger.info(f"[OK] Extracted chart data: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to extract chart data: {e}", exc_info=True)
            return {
                "symbol": None,
                "price": None,
                "error": str(e)
            }
    
    def search_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Search for a symbol using TradingView search.
        
        Args:
            symbol: Symbol to search
            
        Returns:
            Dict with search results
        """
        logger.info(f"Searching for symbol: {symbol}")
        
        try:
            # Search in worker thread
            def _search(page):
                # Click search icon/input
                search_input = page.locator("input[class*='search']").first
                search_input.click()
                search_input.fill(symbol)
                
                # Wait for search results
                time.sleep(1)
                
                # Get first result
                first_result = page.locator("div[class*='search-result'] [class*='item']").first
                if first_result.is_visible(timeout=3000):
                    result_text = first_result.text_content().strip()
                    first_result.click()
                    
                    # Wait for chart to load
                    time.sleep(2)
                    
                    return {
                        "status": "success",
                        "symbol": symbol,
                        "selected": result_text
                    }
                else:
                    return {
                        "status": "error",
                        "symbol": symbol,
                        "error": "No search results found"
                    }
            
            return self.browser_handler.worker.execute(_search, timeout=10)
                
        except Exception as e:
            logger.error(f"Symbol search failed: {e}", exc_info=True)
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }
    
    def switch_timeframe(self, timeframe: str) -> Dict[str, Any]:
        """
        Switch chart timeframe (if DOM-accessible).
        
        Args:
            timeframe: Timeframe code (e.g., "1D", "1H", "15", "1W")
            
        Returns:
            Dict with operation status
        """
        logger.info(f"Switching timeframe to: {timeframe}")
        
        try:
            # Switch timeframe in worker thread
            def _switch(page):
                # Look for timeframe button
                tf_button = page.locator(f"button[data-value='{timeframe}']").first
                if tf_button.is_visible(timeout=2000):
                    tf_button.click()
                    time.sleep(1)  # Wait for chart to redraw
                    
                    return {
                        "status": "success",
                        "timeframe": timeframe,
                        "message": f"Switched to {timeframe}"
                    }
                else:
                    return {
                        "status": "error",
                        "timeframe": timeframe,
                        "error": "Timeframe button not found (may require manual selection)"
                    }
            
            return self.browser_handler.worker.execute(_switch, timeout=5)
                
        except Exception as e:
            logger.error(f"Timeframe switch failed: {e}", exc_info=True)
            return {
                "status": "error",
                "timeframe": timeframe,
                "error": str(e)
            }
    
    def validate_safety_constraints(self) -> bool:
        """
        Validate that safety constraints are enforced.
        
        Returns:
            True if all constraints pass
        """
        safety = self.ma_config.get("safety", {})
        
        # Check that all dangerous actions are disabled
        constraints = [
            safety.get("allow_chart_drawing", True) == False,
            safety.get("allow_trading", True) == False,
            safety.get("allow_coordinate_clicks", True) == False,
            safety.get("allow_chart_manipulation", True) == False
        ]
        
        return all(constraints)
