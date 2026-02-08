# Phase-2B Quick Reference Guide

## How to Use Market Analysis Mode

### Supported Prompts

1. **Basic Analysis:**
   ```
   "Analyze RELIANCE"
   "Technical analysis of TCS"
   "Analyze NIFTY trend"
   ```

2. **With Timeframe:**
   ```
   "Analyze RELIANCE on daily timeframe"
   "Give weekly chart analysis of INFY"
   ```

3. **Support/Resistance:**
   ```
   "What are support and resistance levels for TCS?"
   "Show me key levels for HDFCBANK"
   ```

4. **With TradingView:**
   ```
   "Open TradingView and analyze NIFTY"
   "Show RELIANCE chart and analyze"
   ```

### Supported Symbols

**Indian Stocks (NSE):**
- RELIANCE, TCS, INFY/INFOSYS
- HDFCBANK, ICICIBANK, SBIN
- KOTAKBANK, LT, ITC, AXISBANK
- BHARTIARTL, ASIANPAINT

**Indices:**
- NIFTY, SENSEX, BANKNIFTY

**Format:** Use uppercase symbol names. Agent auto-prepends "NSE:" prefix.

### What You Get

1. **Structured Analysis:**
   - Trend direction (bullish/bearish/sideways)
   - Support levels (array of price levels)
   - Resistance levels (array of price levels)
   - Momentum assessment
   - Textual bias (educational)
   - Risk disclaimer

2. **JSON Output:**
   ```json
   {
     "symbol": "NSE:TCS",
     "timeframe": "1D",
     "trend": "bullish",
     "support": [3650, 3580],
     "resistance": [3850, 3920],
     "momentum": "moderate bullish",
     "bias": "watch for pullback to support",
     "risk_note": "Educational analysis only"
   }
   ```

3. **Human-Readable Format:**
   ```
   **Market Analysis: NSE:TCS (1D)**
   
   **Trend:** bullish
   **Momentum:** moderate bullish
   
   **Support Levels:** 3650, 3580
   **Resistance Levels:** 3850, 3920
   
   **Bias:** watch for pullback to support
   
   *Educational analysis only. Not financial advice.*
   ```

## What is NOT Allowed

❌ **Trading:** "Buy TCS", "Sell RELIANCE", "Place order"
❌ **Drawing:** "Draw trendline", "Add Fibonacci", "Mark support"
❌ **Execution:** "Execute trade", "Set stop loss", "Take profit"
❌ **Recommendations:** Agent will NOT say "buy now" or "sell now"

### If You Try Forbidden Actions:

```
User: "Buy RELIANCE at market price"
Agent: "Analysis-only mode. Execution is disabled."
```

## Safety Features

✅ **Multi-Layer Protection:**
1. Config enforces read-only mode
2. Policy blocks forbidden actions
3. Policy Engine validates at runtime
4. Technical Analyzer filters output
5. Action schema prevents coordinates

✅ **No Chart Interaction:**
- Browser navigates to chart URL only
- DOM reads data (price, indicators)
- Vision observes visually (trend, levels)
- NO clicks on chart canvas
- NO drawing tools accessed

✅ **Authority Hierarchy:**
- DOM = Authoritative (price, indicators)
- Vision = Advisory (trend, patterns)
- LLM = Reasoning (synthesis)

## Testing

### Quick Test:
```bash
python tests/test_market_analysis.py --symbol-only
```

### Safety Test:
```bash
python tests/test_market_analysis.py --safety-only
```

### Full Test:
```bash
python tests/test_market_analysis.py
```

## Troubleshooting

### "Symbol not found"
- Use uppercase: TCS, not tcs
- Use common symbols: RELIANCE, INFY, NIFTY
- Quote if needed: "analyze 'SBIN' stock"

### "Browser handler not available"
- Ensure Playwright installed: `pip install playwright`
- Run: `playwright install`
- Check browser config in agent_config.yaml

### "Market analysis disabled"
- Check `market_analysis.enabled: true` in agent_config.yaml
- Check `market_analysis.enabled: true` in policy.yaml

### "Chart load timeout"
- Increase timeout in agent_config.yaml
- Check internet connection
- Try again (TradingView may be slow)

## Configuration Files

### Enable/Disable Market Analysis

**agent_config.yaml:**
```yaml
market_analysis:
  enabled: true  # Set to false to disable
  mode: "read_only"
```

**policy.yaml:**
```yaml
market_analysis:
  enabled: true  # Set to false to disable
  safety:
    allow_trading: false  # MUST be false
```

### Adjust Timeouts

**agent_config.yaml:**
```yaml
market_analysis:
  tradingview:
    chart_load_timeout: 15  # Increase if charts load slowly
```

## Architecture

```
User Prompt
    ↓
Execution Engine (detect market analysis intent)
    ↓
Extract Symbol (RELIANCE → NSE:RELIANCE)
    ↓
Browser Handler (navigate to TradingView)
    ↓
TradingView Client (extract DOM data)
    ↓
Observer (capture screen, vision analysis)
    ↓
Vision Client (chart-specific prompts)
    ↓
Technical Analyzer (LLM synthesis)
    ↓
Policy Validation (safety check)
    ↓
Formatted Output (JSON + human-readable)
    ↓
User
```

## Key Files

- **Config:** `config/agent_config.yaml`, `config/policy.yaml`
- **TradingView:** `perception/tradingview_client.py`
- **Analysis:** `logic/technical_analyzer.py`
- **Execution:** `logic/execution_engine.py` (market analysis handler)
- **Observation:** `perception/observer.py` (market_analysis context)
- **Vision:** `perception/vision_client.py` (chart prompts)
- **Policy:** `logic/policy_engine.py` (safety validation)
- **Tests:** `tests/test_market_analysis.py`

## Support

For issues or questions:
1. Check logs: `logs/agent.log`
2. Review implementation: `docs/PHASE_2B_IMPLEMENTATION.md`
3. Run tests to verify setup
4. Check safety constraints in policy files

---

**Remember:** Phase-2B is **ANALYSIS-ONLY**. No trading, drawing, or chart manipulation.
