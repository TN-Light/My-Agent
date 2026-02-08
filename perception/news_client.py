"""
News & Catalyst Intelligence Client
Fetches market-moving news, corporate actions, and fundamental catalysts
for stocks to enhance trading analysis.

Sources:
- Google News (via browser, AI mode)
- Extracts: earnings, corporate actions, sector news, regulatory changes,
  management changes, analyst upgrades/downgrades

Integration:
- Called during market analysis flow (after chart analysis)
- Results stored in market memory for future reference
- News sentiment feeds into signal eligibility

Safety:
- Read-only, observation layer only
- Never triggers trades — advisory input
- Rate limited (minimum 15s between searches)
"""
import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CatalystType(Enum):
    """Types of market-moving catalysts."""
    EARNINGS = "earnings"
    CORPORATE_ACTION = "corporate_action"      # splits, dividends, buybacks, mergers
    MANAGEMENT_CHANGE = "management_change"
    REGULATORY = "regulatory"                   # govt policy, SEBI, RBI
    SECTOR_NEWS = "sector_news"                # industry-wide events
    ANALYST_RATING = "analyst_rating"           # upgrades, downgrades, target prices
    INSTITUTIONAL = "institutional"             # FII/DII flows, bulk/block deals
    MACRO = "macro"                             # GDP, inflation, global events
    GENERAL = "general"


class NewsSentiment(Enum):
    """Sentiment classification for news items."""
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"


@dataclass
class NewsItem:
    """A single news item with analysis."""
    headline: str
    source: str
    catalyst_type: CatalystType
    sentiment: NewsSentiment
    impact_timeframe: str          # "immediate", "short_term" (1-5 days), "medium_term" (1-4 weeks), "long_term"
    relevance_score: float         # 0.0 to 1.0
    summary: str = ""
    price_impact: str = ""         # e.g., "Potential 2-5% upside", "Risk of gap down"


@dataclass
class CatalystReport:
    """Complete catalyst/news report for a stock."""
    symbol: str
    timestamp: str
    news_items: List[NewsItem] = field(default_factory=list)
    overall_sentiment: str = "neutral"
    catalyst_summary: str = ""
    key_risk: str = ""
    key_opportunity: str = ""
    upcoming_events: List[str] = field(default_factory=list)
    fundamental_view: str = ""     # "strong", "moderate", "weak", "deteriorating"
    
    def has_actionable_catalyst(self) -> bool:
        """Check if any catalyst is actionable for trading."""
        return any(
            item.relevance_score >= 0.7 and item.impact_timeframe in ("immediate", "short_term")
            for item in self.news_items
        )


class NewsClient:
    """
    Fetches and analyzes news/catalysts for stocks.
    
    Uses Google News via browser + LLM for intelligent extraction.
    Rate limited to avoid CAPTCHA issues.
    """
    
    def __init__(self, browser_handler=None, llm_client=None):
        """
        Args:
            browser_handler: BrowserHandler instance for Google searches
            llm_client: LLMClient for news analysis
        """
        self.browser_handler = browser_handler
        self.llm_client = llm_client
        self._last_search_time = 0.0
        self._min_interval = 15.0  # Minimum seconds between searches
        
        logger.info("NewsClient initialized")
    
    def get_catalyst_report(self, symbol: str, company_name: str = "") -> Optional[CatalystReport]:
        """
        Generate a complete catalyst report for a stock.
        
        Args:
            symbol: NSE symbol (e.g., "TATACHEM")
            company_name: Optional full company name for better search
            
        Returns:
            CatalystReport or None if search fails
        """
        if not self.browser_handler or not self.llm_client:
            logger.warning("[NEWS] Browser or LLM not available")
            return None
        
        # Rate limiting
        elapsed = time.time() - self._last_search_time
        if elapsed < self._min_interval:
            remaining = self._min_interval - elapsed
            logger.info(f"[NEWS] Rate limited: wait {remaining:.0f}s")
            time.sleep(remaining)
        
        logger.info(f"[NEWS] Fetching catalysts for {symbol}")
        
        try:
            # Step 1: Fetch news from Google
            raw_news = self._fetch_news(symbol, company_name)
            if not raw_news:
                logger.warning(f"[NEWS] No news found for {symbol}")
                return self._empty_report(symbol)
            
            # Step 2: Analyze with LLM
            report = self._analyze_news(symbol, raw_news)
            
            if report:
                logger.info(f"[NEWS] Catalyst report ready: {symbol} | Sentiment: {report.overall_sentiment} | Items: {len(report.news_items)}")
            
            return report
            
        except Exception as e:
            logger.error(f"[NEWS] Failed to generate report for {symbol}: {e}", exc_info=True)
            return None
    
    def _fetch_news(self, symbol: str, company_name: str = "") -> Optional[str]:
        """Fetch raw news text from Google."""
        self._last_search_time = time.time()
        
        worker = self.browser_handler.worker if self.browser_handler else None
        if not worker:
            logger.error("[NEWS] Playwright worker not ready")
            return None
        
        # Build search query - use company name if available for better results
        search_term = company_name if company_name else symbol
        queries = [
            f"{search_term} NSE stock news latest catalyst",
            f"{symbol} share price news corporate action earnings",
        ]
        
        all_text = []
        
        for query in queries:
            try:
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=nws&tbs=qdr:m"
                
                def _search(page):
                    page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    text = page.evaluate("() => document.body.innerText")
                    return text
                
                result = worker.execute(_search, timeout=20)
                
                if result and "not a robot" not in result.lower():
                    all_text.append(result)
                    logger.info(f"[NEWS] Fetched {len(result)} chars for query: {query[:50]}...")
                
                # Small delay between queries
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"[NEWS] Search failed for '{query[:40]}...': {e}")
                continue
        
        if not all_text:
            return None
        
        # Combine and trim
        combined = "\n---\n".join(all_text)
        return combined[:6000]  # Cap at 6k chars for LLM context
    
    def _analyze_news(self, symbol: str, raw_news: str) -> Optional[CatalystReport]:
        """Use LLM to analyze raw news into structured report."""
        from datetime import datetime
        
        system_prompt = """You are a stock market analyst specializing in Indian equities (NSE/BSE).
Analyze the news and identify catalysts that could affect the stock price.
You MUST respond in the EXACT format specified. Do not add extra text."""

        user_prompt = f"""Analyze these news results for {symbol} and identify trading catalysts.

NEWS:
{raw_news}

Respond in EXACTLY this format (fill in each field):
OVERALL_SENTIMENT: [strongly_bullish/bullish/neutral/bearish/strongly_bearish]
FUNDAMENTAL_VIEW: [strong/moderate/weak/deteriorating]
CATALYST_SUMMARY: [1-2 sentence summary of key catalysts]
KEY_RISK: [biggest risk factor, 1 sentence]
KEY_OPPORTUNITY: [biggest opportunity, 1 sentence]

NEWS_ITEMS:
1. HEADLINE: [headline text]
   TYPE: [earnings/corporate_action/management_change/regulatory/sector_news/analyst_rating/institutional/macro/general]
   SENTIMENT: [strongly_bullish/bullish/neutral/bearish/strongly_bearish]
   IMPACT: [immediate/short_term/medium_term/long_term]
   RELEVANCE: [0.1 to 1.0]
   PRICE_IMPACT: [expected price impact, e.g., "Potential 2-5% upside"]

2. HEADLINE: [next item...]
   TYPE: ...
   SENTIMENT: ...
   IMPACT: ...
   RELEVANCE: ...
   PRICE_IMPACT: ...

[List up to 5 most important news items. If no news found, write "NO_NEWS_FOUND"]

UPCOMING_EVENTS:
- [any upcoming earnings, AGMs, ex-dates, board meetings]
- [or "NONE" if no upcoming events found]"""
        
        try:
            response = self.llm_client.generate_completion(system_prompt, user_prompt)
            return self._parse_report(symbol, response)
        except Exception as e:
            logger.error(f"[NEWS] LLM analysis failed: {e}")
            return None
    
    def _parse_report(self, symbol: str, llm_response: str) -> CatalystReport:
        """Parse LLM response into structured CatalystReport."""
        from datetime import datetime
        import re
        
        report = CatalystReport(
            symbol=symbol,
            timestamp=datetime.now().isoformat()
        )
        
        lines = llm_response.strip().split('\n')
        
        # Parse header fields
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("OVERALL_SENTIMENT:"):
                val = line_stripped.split(":", 1)[1].strip().lower()
                report.overall_sentiment = val if val in ("strongly_bullish", "bullish", "neutral", "bearish", "strongly_bearish") else "neutral"
            elif line_stripped.startswith("FUNDAMENTAL_VIEW:"):
                val = line_stripped.split(":", 1)[1].strip().lower()
                report.fundamental_view = val if val in ("strong", "moderate", "weak", "deteriorating") else "moderate"
            elif line_stripped.startswith("CATALYST_SUMMARY:"):
                report.catalyst_summary = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("KEY_RISK:"):
                report.key_risk = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("KEY_OPPORTUNITY:"):
                report.key_opportunity = line_stripped.split(":", 1)[1].strip()
        
        # Parse news items
        item_pattern = re.compile(
            r'HEADLINE:\s*(.+?)$.*?'
            r'TYPE:\s*(\w+).*?'
            r'SENTIMENT:\s*(\w+).*?'
            r'IMPACT:\s*(\w+).*?'
            r'RELEVANCE:\s*([\d.]+).*?'
            r'PRICE_IMPACT:\s*(.+?)$',
            re.MULTILINE | re.DOTALL
        )
        
        # Simpler line-by-line parsing for robustness
        current_item = {}
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith("HEADLINE:"):
                if current_item.get("headline"):
                    # Save previous item
                    self._add_news_item(report, current_item)
                current_item = {"headline": line_stripped.split(":", 1)[1].strip()}
            elif line_stripped.startswith("TYPE:") and current_item:
                current_item["type"] = line_stripped.split(":", 1)[1].strip().lower()
            elif line_stripped.startswith("SENTIMENT:") and current_item:
                current_item["sentiment"] = line_stripped.split(":", 1)[1].strip().lower()
            elif line_stripped.startswith("IMPACT:") and current_item:
                current_item["impact"] = line_stripped.split(":", 1)[1].strip().lower()
            elif line_stripped.startswith("RELEVANCE:") and current_item:
                try:
                    current_item["relevance"] = float(line_stripped.split(":", 1)[1].strip())
                except ValueError:
                    current_item["relevance"] = 0.5
            elif line_stripped.startswith("PRICE_IMPACT:") and current_item:
                current_item["price_impact"] = line_stripped.split(":", 1)[1].strip()
        
        # Save last item
        if current_item.get("headline"):
            self._add_news_item(report, current_item)
        
        # Parse upcoming events
        in_events = False
        for line in lines:
            line_stripped = line.strip()
            if "UPCOMING_EVENTS:" in line_stripped:
                in_events = True
                continue
            if in_events and line_stripped.startswith("- "):
                event = line_stripped[2:].strip()
                if event and event.upper() != "NONE":
                    report.upcoming_events.append(event)
        
        return report
    
    def _add_news_item(self, report: CatalystReport, item_dict: dict):
        """Add a parsed news item to the report."""
        # Map type string to enum
        type_map = {
            "earnings": CatalystType.EARNINGS,
            "corporate_action": CatalystType.CORPORATE_ACTION,
            "management_change": CatalystType.MANAGEMENT_CHANGE,
            "regulatory": CatalystType.REGULATORY,
            "sector_news": CatalystType.SECTOR_NEWS,
            "analyst_rating": CatalystType.ANALYST_RATING,
            "institutional": CatalystType.INSTITUTIONAL,
            "macro": CatalystType.MACRO,
            "general": CatalystType.GENERAL,
        }
        
        sentiment_map = {
            "strongly_bullish": NewsSentiment.STRONGLY_BULLISH,
            "bullish": NewsSentiment.BULLISH,
            "neutral": NewsSentiment.NEUTRAL,
            "bearish": NewsSentiment.BEARISH,
            "strongly_bearish": NewsSentiment.STRONGLY_BEARISH,
        }
        
        try:
            news_item = NewsItem(
                headline=item_dict.get("headline", "Unknown"),
                source="Google News",
                catalyst_type=type_map.get(item_dict.get("type", "general"), CatalystType.GENERAL),
                sentiment=sentiment_map.get(item_dict.get("sentiment", "neutral"), NewsSentiment.NEUTRAL),
                impact_timeframe=item_dict.get("impact", "medium_term"),
                relevance_score=min(1.0, max(0.0, item_dict.get("relevance", 0.5))),
                price_impact=item_dict.get("price_impact", "")
            )
            report.news_items.append(news_item)
        except Exception as e:
            logger.warning(f"[NEWS] Failed to parse news item: {e}")
    
    def _empty_report(self, symbol: str) -> CatalystReport:
        """Return an empty report when no news is found."""
        from datetime import datetime
        return CatalystReport(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            overall_sentiment="neutral",
            catalyst_summary="No recent news or catalysts found.",
            fundamental_view="unknown"
        )
    
    def format_for_display(self, report: CatalystReport) -> str:
        """Format catalyst report for ChatUI display."""
        if not report:
            return "No catalyst data available."
        
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"NEWS & CATALYST REPORT: {report.symbol}")
        lines.append(f"{'='*60}")
        lines.append("")
        
        # Sentiment indicator
        sentiment_emoji = {
            "strongly_bullish": "🟢🟢",
            "bullish": "🟢",
            "neutral": "⚪",
            "bearish": "🔴",
            "strongly_bearish": "🔴🔴"
        }
        emoji = sentiment_emoji.get(report.overall_sentiment, "⚪")
        lines.append(f"OVERALL SENTIMENT: {emoji} {report.overall_sentiment.upper()}")
        lines.append(f"FUNDAMENTAL VIEW: {report.fundamental_view.upper()}")
        lines.append("")
        
        if report.catalyst_summary:
            lines.append(f"CATALYST SUMMARY:")
            lines.append(f"  {report.catalyst_summary}")
            lines.append("")
        
        if report.key_opportunity:
            lines.append(f"KEY OPPORTUNITY: {report.key_opportunity}")
        if report.key_risk:
            lines.append(f"KEY RISK: {report.key_risk}")
        lines.append("")
        
        # News items
        if report.news_items:
            lines.append("NEWS ITEMS:")
            for i, item in enumerate(report.news_items, 1):
                sentiment_icon = {"strongly_bullish": "++", "bullish": "+", "neutral": "~", "bearish": "-", "strongly_bearish": "--"}
                icon = sentiment_icon.get(item.sentiment.value, "~")
                lines.append(f"  {i}. [{icon}] {item.headline}")
                lines.append(f"     Type: {item.catalyst_type.value} | Impact: {item.impact_timeframe} | Relevance: {item.relevance_score:.1f}")
                if item.price_impact:
                    lines.append(f"     Price Impact: {item.price_impact}")
            lines.append("")
        
        # Upcoming events
        if report.upcoming_events:
            lines.append("UPCOMING EVENTS:")
            for event in report.upcoming_events:
                lines.append(f"  • {event}")
            lines.append("")
        
        lines.append(f"{'='*60}")
        
        return "\n".join(lines)
