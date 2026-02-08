"""
Technical Analyzer - Phase-2B/16 Market Analysis
LLM-based technical analysis synthesis using DOM + Vision observations.

Phase-16: DOM/VLM Perception Reconciliation
  Before LLM synthesis, DOM and VLM are reconciled through trust-weighted fusion.
  Conflicts are detected, scored, and resolved before the LLM sees the data.

GOLDEN RULE: Vision proposes → Reconciler scores → DOM validates → LLM reasons

Output: Structured JSON analysis (trend, support/resistance, momentum, bias)
"""
import logging
import json
from typing import Dict, Any, Optional, List
from logic.llm_client import LLMClient

try:
    from logic.perception_reconciler import PerceptionReconciler, ReconciliationReport
    _reconciler_available = True
except ImportError:
    _reconciler_available = False

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """
    Synthesizes DOM data + Vision observations into structured technical analysis.
    
    Phase-2B: LLM-based reasoning for market analysis.
    Uses LLM to interpret chart data and provide textual analysis.
    NEVER provides trading recommendations or execution instructions.
    """
    
    def __init__(self, config: dict, llm_client: LLMClient, market_store=None):
        """
        Initialize technical analyzer.
        
        Args:
            config: Market analysis configuration
            llm_client: LLM client for reasoning
            market_store: MarketAnalysisStore for persistence (Phase-2C)
        """
        self.config = config
        self.llm_client = llm_client
        self.ma_config = config.get("market_analysis", {})
        self.output_config = self.ma_config.get("output", {})
        self.market_store = market_store
        
        # Phase-16: Perception Reconciler
        self.reconciler = PerceptionReconciler() if _reconciler_available else None
        if self.reconciler:
            logger.info("Phase-16: Perception Reconciler enabled")
        
        logger.info("TechnicalAnalyzer initialized")
    
    def analyze(
        self,
        dom_data: Dict[str, Any],
        vision_observation: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform technical analysis using DOM data and optional vision observation.
        
        Args:
            dom_data: Chart data extracted from DOM (symbol, price, indicators, etc.)
            vision_observation: Optional vision-based trend/support/resistance description
            
        Returns:
            Structured JSON analysis with trend, support/resistance, momentum, bias
        """
        logger.info(f"Analyzing chart data for {dom_data.get('symbol', 'Unknown')}")
        
        try:
            # Phase-16: Reconcile DOM + VLM before LLM synthesis
            reconciliation = None
            if self.reconciler:
                reconciliation = self.reconciler.reconcile(dom_data, vision_observation)
            
            # Build analysis prompt with reconciled data
            prompt = self._build_analysis_prompt(dom_data, vision_observation, reconciliation)
            
            # Get LLM analysis using generate_completion (not plan)
            llm_response = self.llm_client.generate_completion(
                system_prompt="You are a professional technical analyst providing precise market analysis for trading decisions. Analyze charts accurately with specific support/resistance levels and clear trend identification.",
                user_prompt=prompt
            )
            
            # Parse LLM response into structured format
            analysis = self._parse_analysis(llm_response, dom_data)
            
            # Add safety disclaimer
            if self.output_config.get("include_disclaimer", True):
                analysis["risk_note"] = "For informational purposes. Trade at your own risk."
            
            # Phase-2C: Store analysis in persistent store
            if self.market_store:
                try:
                    # Add timestamp if not present
                    if "timestamp" not in analysis:
                        from datetime import datetime
                        analysis["timestamp"] = datetime.now().isoformat()
                    
                    # Extract price from dom_data if available
                    if "price" not in analysis and dom_data.get("price"):
                        try:
                            # Try to convert price to float
                            price_str = str(dom_data.get("price", "")).replace(",", "")
                            analysis["price"] = float(price_str)
                        except (ValueError, TypeError):
                            pass
                    
                    analysis_id = self.market_store.store_analysis(analysis)
                    logger.info(f"Stored analysis in database: ID {analysis_id}")
                except Exception as e:
                    logger.error(f"Failed to store analysis: {e}")
            
            # Phase-16: Attach reconciliation metadata to analysis
            if reconciliation:
                analysis["_perception_confidence"] = reconciliation.overall_confidence
                analysis["_perception_completeness"] = reconciliation.completeness
                analysis["_perception_conflicts"] = len(reconciliation.conflicts)
                if reconciliation.has_critical_conflicts():
                    analysis["_critical_conflict"] = True
            
            logger.info(f"[OK] Analysis complete: {analysis.get('symbol')}")
            return analysis
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            return {
                "symbol": dom_data.get("symbol", "Unknown"),
                "error": str(e),
                "risk_note": "Analysis failed. Educational purposes only."
            }
    
    def _build_analysis_prompt(
        self,
        dom_data: Dict[str, Any],
        vision_observation: Optional[str],
        reconciliation: Optional['ReconciliationReport'] = None
    ) -> str:
        """
        Build LLM prompt for technical analysis.
        
        Args:
            dom_data: DOM-extracted chart data
            vision_observation: Optional vision description
            
        Returns:
            Analysis prompt string
        """
        symbol = dom_data.get("symbol", "Unknown")
        price = dom_data.get("price", "N/A")
        change = dom_data.get("change", "N/A")
        timeframe = dom_data.get("timeframe", "1D")
        indicators = dom_data.get("indicators", {})
        
        prompt = f"""You are a professional technical analyst. Synthesize the following DOM data and vision observation into a precise structural assessment.

CHART DATA (DOM - AUTHORITATIVE):
- Symbol: {symbol}
- Current Price: {price}
- Change: {change}
- Timeframe: {timeframe}
"""
        
        # Add indicators if available
        if indicators:
            prompt += "\nINDICATORS (FROM DOM - AUTHORITATIVE):\n"
            for name, value in indicators.items():
                prompt += f"- {name}: {value}\n"
        else:
            prompt += "\nINDICATORS: None available from DOM\n"
        
        # Add volume data
        volume = dom_data.get("volume")
        if volume:
            prompt += f"\nVOLUME: {volume}\n"
        
        # Add vision observation if available
        if vision_observation:
            prompt += f"\nVISION OBSERVATION (ADVISORY - use to identify patterns, levels, candles):\n{vision_observation}\n"
        
        # Phase-16: Add reconciliation report if available
        if reconciliation:
            prompt += f"\n--- PERCEPTION RECONCILIATION (Phase-16) ---\n"
            prompt += reconciliation.evidence_brief
            prompt += "\n"
            if reconciliation.conflicts:
                prompt += "\n" + reconciliation.conflict_brief + "\n"
            prompt += f"\nIMPORTANT: The reconciliation above resolves conflicts between DOM and VLM.\n"
            prompt += f"Use the trust-weighted facts above as your PRIMARY input. Where trust=HIGH, treat as fact.\n"
            prompt += f"Where trust=LOW (e.g., VLM-read price levels), verify against other evidence.\n"
            prompt += f"--- END RECONCILIATION ---\n"
        
        prompt += f"""
TASK:
Provide a precise technical analysis for {symbol} on the {timeframe} timeframe.

RULES FOR SUPPORT/RESISTANCE LEVELS:
- If DOM provides OHLC (High/Low) data: use actual High as near resistance, actual Low as near support
- If Vision reports specific price levels from the chart Y-axis: use those exact numbers
- If indicators (EMA/SMA) are available: use their values as dynamic support/resistance
- ONLY if NO data is available from DOM or Vision: estimate levels based on current price
- ALL support levels MUST be BELOW current price
- ALL resistance levels MUST be ABOVE current price

RULES FOR VOLUME:
- If volume data is available, assess whether volume confirms the trend
- "volume_trend": "increasing" (confirms trend), "decreasing" (weakening), "spike" (climax/breakout), "dry" (low interest)
- If no volume data: set volume_trend to "unavailable"

Respond ONLY with this JSON (no other text):

{{
  "symbol": "{symbol}",
  "timeframe": "{timeframe}",
  "trend": "<bullish|bearish|sideways>",
  "structure": "<higher-highs|lower-lows|range-bound|consolidation>",
  "support": [<level_1>, <level_2>],
  "resistance": [<level_1>, <level_2>],
  "momentum": "<strong bullish|moderate bullish|neutral|moderate bearish|strong bearish>",
  "momentum_condition": "<expanding|exhausting|improving|neutral>",
  "volume_trend": "<increasing|decreasing|spike|dry|unavailable>",
  "candlestick_pattern": "<pattern name or none>",
  "reasoning": "<2-3 sentences: what the chart structure shows>",
  "bias": "<directional outlook with specific levels to monitor>",
  "key_levels": "<critical price levels for validation or rejection>"
}}

CRITICAL LOGIC RULES:
1. Support levels MUST be numeric and BELOW current price ({price})
2. Resistance levels MUST be numeric and ABOVE current price ({price})
3. If RSI is available and > 70: momentum_condition should be "exhausting"
4. If RSI is available and < 30: momentum_condition should be "improving"
5. NEVER use words: "trade", "entry", "exit", "position", "buy", "sell"
6. Use ONLY: "monitor", "observe", "validate", "watch"
7. Momentum MUST have both strength AND condition
8. Provide at least 2 support and 2 resistance levels as numbers
"""
        
        return prompt
    
    def _parse_analysis(
        self,
        llm_response: str,
        dom_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse LLM response into structured analysis format.
        
        Args:
            llm_response: Raw LLM response
            dom_data: Original DOM data
            
        Returns:
            Structured analysis dict
        """
        try:
            # Try to parse as JSON
            # LLM should return JSON, but may wrap it in markdown code blocks
            response_clean = llm_response.strip()
            
            # Remove markdown code blocks if present
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])  # Remove first and last lines
            
            # Parse JSON
            analysis = json.loads(response_clean)
            
            # Validate required fields
            required_fields = ["symbol", "timeframe", "trend", "structure", "support", "resistance", "momentum", "bias"]
            for field in required_fields:
                if field not in analysis:
                    # Provide fallback value
                    if field == "symbol":
                        analysis[field] = dom_data.get("symbol", "Unknown")
                    elif field == "timeframe":
                        analysis[field] = dom_data.get("timeframe", "1D")
                    elif field in ["support", "resistance"]:
                        analysis[field] = []
                    elif field == "structure":
                        # Infer structure from trend if missing
                        trend = analysis.get("trend", "").lower()
                        if trend == "bullish":
                            analysis[field] = "higher-highs"
                        elif trend == "bearish":
                            analysis[field] = "lower-lows"
                        else:
                            analysis[field] = "range-bound"
                    else:
                        analysis[field] = "N/A"
            
            # Phase-15: Ensure new fields have defaults
            if "volume_trend" not in analysis:
                analysis["volume_trend"] = "unavailable"
            if "candlestick_pattern" not in analysis:
                analysis["candlestick_pattern"] = "none"
            if "momentum_condition" not in analysis:
                analysis["momentum_condition"] = "neutral"
            
            # Add price from DOM data for mean reversion checks
            if "price" not in analysis and dom_data.get("price"):
                analysis["price"] = dom_data.get("price")
            
            # Validate logical consistency
            validation_errors = self._validate_logic_consistency(analysis)
            if validation_errors:
                logger.warning(f"Logic consistency issues detected: {'; '.join(validation_errors)}")
                # Store validation warnings in analysis
                analysis["validation_warnings"] = validation_errors
            
            return analysis
            
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON, using fallback format")
            # Fallback: Return textual analysis
            return {
                "symbol": dom_data.get("symbol", "Unknown"),
                "timeframe": dom_data.get("timeframe", "1D"),
                "trend": "Unknown",
                "support": [],
                "resistance": [],
                "momentum": "Unknown",
                "bias": llm_response[:200],  # First 200 chars
                "error": "Failed to parse structured analysis"
            }
    
    def _validate_logic_consistency(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Validate logical consistency of analysis.
        
        Args:
            analysis: Parsed analysis dictionary
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        try:
            # Extract current price
            price = analysis.get("price")
            if price:
                try:
                    price_val = float(str(price).replace(",", ""))
                except (ValueError, TypeError):
                    price_val = None
            else:
                price_val = None
            
            # Validate support/resistance ordering
            support = analysis.get("support", [])
            resistance = analysis.get("resistance", [])
            
            if price_val and support and resistance:
                # Check support < price < resistance
                support_vals = []
                resistance_vals = []
                
                for s in support:
                    try:
                        support_vals.append(float(s))
                    except (ValueError, TypeError):
                        pass
                
                for r in resistance:
                    try:
                        resistance_vals.append(float(r))
                    except (ValueError, TypeError):
                        pass
                
                # Validate ordering
                if support_vals:
                    max_support = max(support_vals)
                    if max_support > price_val:
                        errors.append(f"Support level ({max_support}) above current price ({price_val}) - illogical")
                
                if resistance_vals:
                    min_resistance = min(resistance_vals)
                    if min_resistance < price_val:
                        errors.append(f"Resistance level ({min_resistance}) below current price ({price_val}) - illogical")
            
            # Validate momentum completeness
            momentum = analysis.get("momentum", "")
            momentum_condition = analysis.get("momentum_condition", "")
            
            if momentum and not momentum_condition:
                errors.append("Momentum condition missing (must be: expanding/exhausting/improving/neutral)")
            
            # Validate phase discipline (no trade language)
            forbidden_words = ["trade", "trading", "entry", "exit", "position", "buy", "sell", "long", "short"]
            for field in ["reasoning", "bias", "key_levels"]:
                text = str(analysis.get(field, "")).lower()
                for word in forbidden_words:
                    if word in text:
                        errors.append(f"Phase violation: '{word}' found in {field} (use 'monitor/observe/validate' instead)")
                        break
            
        except Exception as e:
            logger.error(f"Validation check failed: {e}")
        
        return errors
    
    def validate_analysis(self, analysis: Dict[str, Any]) -> bool:
        """
        Validate that analysis does not contain trading instructions.
        
        Args:
            analysis: Analysis dict
            
        Returns:
            True if valid, False if contains forbidden content
        """
        # Check for forbidden phrases
        forbidden_phrases = [
            "buy now",
            "sell now",
            "execute trade",
            "place order",
            "market order",
            "limit order",
            "stop loss",
            "take profit"
        ]
        
        # Convert analysis to string for checking
        analysis_str = json.dumps(analysis).lower()
        
        for phrase in forbidden_phrases:
            if phrase in analysis_str:
                logger.warning(f"Analysis contains forbidden phrase: {phrase}")
                return False
        
        return True
    
    def format_analysis_for_display(self, analysis: Dict[str, Any]) -> str:
        """
        Format analysis in strict structured point-by-point format (NO paragraphs).
        
        Args:
            analysis: Structured analysis dict
            
        Returns:
            Structured bullet-point text
        """
        symbol = analysis.get("symbol", "Unknown")
        timeframe = analysis.get("timeframe", "Unknown")
        trend = analysis.get("trend", "Unknown")
        structure = analysis.get("structure", "Unknown")
        support = analysis.get("support", [])
        resistance = analysis.get("resistance", [])
        momentum = analysis.get("momentum", "Unknown")
        momentum_condition = analysis.get("momentum_condition", "neutral")
        volume_trend = analysis.get("volume_trend", "unavailable")
        candlestick_pattern = analysis.get("candlestick_pattern", "none")
        bias = analysis.get("bias", "")
        reasoning = analysis.get("reasoning", "")
        price = analysis.get("price", "N/A")
        
        # Map timeframe codes to readable names
        timeframe_names = {
            "1D": "Daily",
            "1W": "Weekly", 
            "1M": "Monthly",
            "60": "Hourly",
            "15": "15-Minute",
            "5": "5-Minute"
        }
        tf_name = timeframe_names.get(timeframe, timeframe)
        
        # Build structured output (NO PARAGRAPHS)
        lines = []
        lines.append(f"MARKET ANALYSIS - {symbol} ({tf_name})")
        lines.append("")
        
        # 1. Trend
        lines.append("1. Trend")
        lines.append(f"   - Direction: {trend.capitalize() if trend else 'Unknown'}")
        lines.append(f"   - Structure: {structure if structure else 'Unknown'}")
        lines.append("")
        
        # 2. Momentum
        lines.append("2. Momentum")
        if momentum:
            lines.append(f"   - Strength: {momentum.capitalize()}")
            lines.append(f"   - Condition: {momentum_condition.capitalize()}")
        else:
            lines.append("   - Strength: Unknown")
            lines.append("   - Condition: Neutral")
        lines.append("")
        
        # 3. Volume
        lines.append("3. Volume")
        if volume_trend and volume_trend != "unavailable":
            vol_emoji = {"increasing": "++ (confirming)", "decreasing": "-- (weakening)", 
                        "spike": "!! (climax/breakout)", "dry": ".. (low interest)"}
            lines.append(f"   - Trend: {volume_trend.capitalize()} {vol_emoji.get(volume_trend, '')}")
        else:
            lines.append("   - Trend: Data unavailable")
        lines.append("")
        
        # 4. Key Levels (use Rs instead of rupee symbol to avoid unicode errors)
        lines.append("4. Key Levels")
        if support:
            lines.append("   - Support:")
            for s in support:
                lines.append(f"     * Rs {s}")
        else:
            lines.append("   - Support: None identified")
        
        if resistance:
            lines.append("   - Resistance:")
            for r in resistance:
                lines.append(f"     * Rs {r}")
        else:
            lines.append("   - Resistance: None identified")
        lines.append("")
        
        # 5. Candlestick Pattern
        if candlestick_pattern and candlestick_pattern.lower() != "none":
            lines.append("5. Candlestick Pattern")
            lines.append(f"   - {candlestick_pattern}")
            lines.append("")
        
        # 6. Context
        lines.append("6. Context")
        if price and price != "N/A":
            lines.append(f"   - Current Price: Rs {price}")
        
        # Determine price location
        if support and resistance and price and price != "N/A":
            try:
                price_val = float(str(price).replace(",", ""))
                avg_support = sum(support) / len(support)
                avg_resistance = sum(resistance) / len(resistance)
                mid_range = (avg_support + avg_resistance) / 2
                
                if price_val > mid_range:
                    location = "Near resistance"
                elif price_val < mid_range:
                    location = "Near support"
                else:
                    location = "Mid-range"
                lines.append(f"   - Price Location: {location}")
            except (ValueError, TypeError, ZeroDivisionError):
                pass  # Price parsing may fail on unusual data
        
        if reasoning:
            lines.append(f"   - Technical Setup: {reasoning}")
        lines.append("")
        
        # 7. Scenario Outlook
        lines.append("7. Scenario Outlook (No trade instructions)")
        if bias:
            lines.append(f"   - {bias}")
        else:
            lines.append("   - Watch key levels for breakout/breakdown")
        lines.append("")
        
        # Disclaimer
        lines.append("---")
        lines.append("Educational analysis only. Not financial advice.")
        
        return "\n".join(lines)
