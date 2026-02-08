"""
Market Query Handler — Extracted from ExecutionEngine (Phase-2C market memory queries).

Handles all memory-only market queries that don't require browser navigation:
- Last analysis lookup
- Symbol comparison
- Trend change detection
- Strength ranking
- Market summary
- Generic semantic search
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MarketQueryHandler:
    """
    Processes market queries using stored analysis data (no browser needed).
    
    Requires:
        market_memory: MarketMemory instance
        chat_ui: Optional ChatUI for display
        llm_client: Optional LLM client for formatting
        config: Agent config dict
    """
    
    def __init__(self, market_memory, chat_ui=None, llm_client=None, config: dict = None):
        self.market_memory = market_memory
        self.chat_ui = chat_ui
        self.llm_client = llm_client
        self.config = config or {}
    
    def handle_query(self, instruction: str, query_type: str, symbol_extractor=None):
        """
        Route a market chat query to the appropriate handler.
        
        Args:
            instruction: User instruction text
            query_type: One of 'last_analysis', 'comparison', 'trend_change',
                        'strongest', 'market_summary', 'generic'
            symbol_extractor: Callable(str) -> Optional[str] for extracting symbols
        """
        try:
            if self.chat_ui:
                self.chat_ui.set_status("Querying market memory...")
            
            handlers = {
                "last_analysis": self._handle_last_analysis,
                "comparison": self._handle_comparison,
                "trend_change": self._handle_trend_change,
                "strongest": self._handle_strongest,
                "market_summary": self._handle_market_summary,
                "generic": self._handle_generic,
            }
            
            handler = handlers.get(query_type, self._handle_generic)
            handler(instruction, symbol_extractor)
            
            if self.chat_ui:
                self.chat_ui.set_status("Complete")
                
        except Exception as e:
            logger.error(f"Market chat query failed: {e}", exc_info=True)
            if self.chat_ui:
                self.chat_ui.log(f"Query failed: {e}", "ERROR")
                self.chat_ui.set_status("Failed")
    
    def _log(self, msg: str, level: str = "INFO"):
        """Log to UI and logger."""
        if self.chat_ui:
            self.chat_ui.log(msg, level)
        logger.info(msg)
    
    def _handle_last_analysis(self, instruction: str, symbol_extractor=None):
        """Handle 'last analysis' queries."""
        symbol = symbol_extractor(instruction) if symbol_extractor else None
        
        if not symbol:
            self._log("Could not identify symbol. Please specify (e.g., TCS, RELIANCE)", "WARNING")
            return
        
        analysis = self.market_memory.get_latest_for_symbol(symbol)
        
        if not analysis:
            self._log(f"No previous analysis found for {symbol}.", "INFO")
            return
        
        # Format analysis
        from logic.technical_analyzer import TechnicalAnalyzer
        if not self.llm_client:
            formatted = json.dumps(analysis, indent=2)
        else:
            analyzer = TechnicalAnalyzer(self.config, self.llm_client)
            formatted = analyzer.format_analysis_for_display(analysis)
        
        timestamp = analysis.get("timestamp", "Unknown time")
        msg = f"**Last Analysis for {symbol}**\n*Analyzed at: {timestamp}*\n\n{formatted}"
        self._log(msg, "ANALYSIS")
    
    def _handle_comparison(self, instruction: str, symbol_extractor=None):
        """Handle comparison queries."""
        instruction_upper = instruction.upper()
        
        common_symbols = [
            "RELIANCE", "TCS", "INFY", "INFOSYS", "HDFCBANK", "HDFC",
            "ICICIBANK", "ICICI", "SBIN", "BHARTIARTL", "ITC",
            "KOTAKBANK", "KOTAK", "LT", "ASIANPAINT", "AXISBANK",
            "NIFTY", "SENSEX", "BANKNIFTY"
        ]
        
        found_symbols = [s for s in common_symbols if s in instruction_upper]
        
        if len(found_symbols) < 2:
            self._log("Please specify at least 2 symbols to compare (e.g., 'Compare TCS vs INFY')", "WARNING")
            return
        
        comparison = self.market_memory.compare_symbols(found_symbols[:5])
        
        msg = "**Market Comparison**\n\n"
        
        for symbol in found_symbols[:5]:
            analysis = comparison["analyses"].get(symbol)
            if analysis:
                trend = analysis.get("trend", "Unknown")
                momentum = analysis.get("momentum", "Unknown")
                timestamp = analysis.get("timestamp", "Unknown")
                msg += f"**{symbol}:**\n"
                msg += f"  - Trend: {trend}\n"
                msg += f"  - Momentum: {momentum}\n"
                msg += f"  - Analyzed: {timestamp}\n\n"
            else:
                msg += f"**{symbol}:** No analysis available\n\n"
        
        summary = comparison["summary"]
        msg += "**Summary:**\n"
        msg += f"- Bullish: {summary['bullish_count']}\n"
        msg += f"- Bearish: {summary['bearish_count']}\n"
        msg += f"- Sideways: {summary['sideways_count']}\n"
        msg += f"- Strongest: {summary['strongest']}\n"
        msg += f"- Market Bias: {summary['market_bias']}\n"
        
        self._log(msg, "ANALYSIS")
    
    def _handle_trend_change(self, instruction: str, symbol_extractor=None):
        """Handle trend change queries."""
        symbol = symbol_extractor(instruction) if symbol_extractor else None
        
        if not symbol:
            self._log("Could not identify symbol. Please specify (e.g., 'Has NIFTY trend changed?')", "WARNING")
            return
        
        change_info = self.market_memory.check_trend_change(symbol)
        
        msg = f"**Trend Change Analysis: {symbol}**\n\n"
        
        if change_info.get("changed"):
            msg += f"✓ **Trend has CHANGED**\n"
            msg += f"  - Previous: {change_info.get('previous_trend')}\n"
            msg += f"  - Current: {change_info.get('current_trend')}\n"
            msg += f"  - {change_info.get('description')}\n"
        else:
            msg += f"✗ **Trend has NOT changed**\n"
            msg += f"  - Current: {change_info.get('current_trend')}\n"
            msg += f"  - {change_info.get('description')}\n"
        
        msg += f"\n*Last analyzed: {change_info.get('timestamp', 'Unknown')}*"
        
        self._log(msg, "ANALYSIS")
    
    def _handle_strongest(self, instruction: str, symbol_extractor=None):
        """Handle 'which stock is stronger' queries."""
        summary = self.market_memory.get_market_summary(hours=24)
        
        if summary["total_analyses"] == 0:
            self._log("No recent analyses available. Try analyzing some stocks first.", "INFO")
            return
        
        symbols = summary.get("symbols", [])
        if len(symbols) < 2:
            self._log("Need at least 2 analyzed symbols to compare strength.", "INFO")
            return
        
        comparison = self.market_memory.compare_symbols(symbols[:5])
        strongest = comparison["summary"].get("strongest", "Unknown")
        
        msg = "**Strength Analysis**\n\n"
        msg += f"Analyzing {len(symbols[:5])} stocks from last 24 hours:\n\n"
        
        for symbol in symbols[:5]:
            analysis = comparison["analyses"].get(symbol)
            if analysis:
                trend = analysis.get("trend", "Unknown")
                momentum = analysis.get("momentum", "Unknown")
                score_indicator = "🔥" if symbol == strongest else ""
                msg += f"{score_indicator} **{symbol}**: {trend} / {momentum}\n"
        
        msg += f"\n**Strongest Stock: {strongest}** 🏆\n"
        msg += f"Overall Market Bias: {comparison['summary']['market_bias']}\n"
        
        self._log(msg, "ANALYSIS")
    
    def _handle_market_summary(self, instruction: str, symbol_extractor=None):
        """Handle market summary queries."""
        summary = self.market_memory.get_market_summary(hours=24)
        
        if summary["total_analyses"] == 0:
            self._log("No analyses in the last 24 hours.", "INFO")
            return
        
        msg = "**Market Summary (Last 24 Hours)**\n\n"
        msg += f"- Total Analyses: {summary['total_analyses']}\n"
        msg += f"- Unique Symbols: {summary['unique_symbols']}\n"
        msg += f"- Bullish: {summary['bullish_count']} ({summary['sentiment_ratio']}%)\n"
        msg += f"- Bearish: {summary['bearish_count']}\n"
        msg += f"- Sideways: {summary['sideways_count']}\n"
        msg += f"- **Overall Bias: {summary['overall_bias'].upper()}**\n\n"
        msg += f"Symbols analyzed: {', '.join(summary['symbols'][:10])}\n"
        
        self._log(msg, "ANALYSIS")
    
    def _handle_generic(self, instruction: str, symbol_extractor=None):
        """Handle generic market queries using semantic search."""
        results = self.market_memory.query(instruction, n_results=3)
        
        if not results:
            self._log("No relevant analyses found. Try analyzing some stocks first.", "INFO")
            return
        
        msg = f"**Found {len(results)} Relevant Analyses:**\n\n"
        
        for i, analysis in enumerate(results, 1):
            symbol = analysis.get("symbol", "Unknown")
            trend = analysis.get("trend", "Unknown")
            momentum = analysis.get("momentum", "Unknown")
            timestamp = analysis.get("timestamp", "Unknown")
            
            msg += f"{i}. **{symbol}** - {trend} / {momentum}\n"
            msg += f"   _{timestamp}_\n\n"
        
        self._log(msg, "ANALYSIS")
