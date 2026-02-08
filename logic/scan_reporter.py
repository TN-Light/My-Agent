"""
Phase-11.5: Scan Reporter
Human-readable output formatting for scan results.

NO PRICES, NO BUY/SELL, NO EXECUTION HINTS.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ScanReporter:
    """
    Format scan results for human consumption.
    
    Output rules:
    - No prices
    - No buy/sell language
    - No execution instructions
    - Clear signal status
    - Transparent reasoning
    """
    
    def __init__(self):
        """Initialize Scan Reporter"""
        logger.info("ScanReporter initialized (Phase-11.5)")
    
    def generate_report(
        self,
        scope: str,
        timeframe: str,
        total_scanned: int,
        eligible_count: int,
        ranked_signals: List[Any],  # List of RankedSignal
        failed_instruments: List[tuple[str, str]] = None  # (instrument, error_msg)
    ) -> str:
        """
        Generate human-readable scan report.
        
        Args:
            scope: Original scan scope
            timeframe: INTRADAY / SWING / POSITIONAL
            total_scanned: Total instruments scanned
            eligible_count: Number of eligible signals found
            ranked_signals: Top-ranked signals
            failed_instruments: Instruments that failed analysis
        
        Returns:
            Formatted report string
        """
        lines = []
        
        # Header
        lines.append("")
        lines.append("=" * 80)
        lines.append("PHASE-11.5: MARKET SCAN RESULT")
        lines.append("=" * 80)
        lines.append("")
        
        # Scan metadata
        lines.append(f"SCOPE: {scope}")
        lines.append(f"TIMEFRAME: {timeframe}")
        lines.append(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"SCANNED: {total_scanned} instruments")
        lines.append(f"ELIGIBLE: {eligible_count} signals")
        
        # Signal rarity indicator
        if total_scanned > 0:
            rarity_pct = (eligible_count / total_scanned) * 100
            rarity_status = "✅" if rarity_pct <= 20 else "⚠️"
            lines.append(f"SIGNAL RARITY: {rarity_pct:.1f}% {rarity_status}")
        
        lines.append("")
        lines.append("=" * 80)
        
        # Top signals
        if ranked_signals:
            lines.append("")
            lines.append("TOP SIGNALS:")
            lines.append("")
            
            for i, ranked_signal in enumerate(ranked_signals, 1):
                signal = ranked_signal.signal_contract
                
                lines.append(f"{i}) {ranked_signal.instrument}")
                lines.append(f"   Score: {ranked_signal.rank_score:.0f} ({ranked_signal.rank_reason})")
                lines.append(f"   Verdict: {signal.verdict} ({signal.confidence} confidence)")
                lines.append(f"   Direction: {signal.direction.value}")
                lines.append(f"   Risk: {signal.risk_class.value}")
                lines.append(f"   Entry Style: {signal.entry_style.value}")
                lines.append(f"   Structure: {signal.alignment_state} alignment, {signal.htf_location} location")
                lines.append(f"   Summary: {signal.summary[:100]}...")
                lines.append("")
        else:
            lines.append("")
            lines.append("NO ELIGIBLE SIGNALS")
            lines.append("")
            lines.append("All scanned instruments marked NOT_ELIGIBLE.")
            lines.append("This is expected behavior - signals should be rare.")
            lines.append("")
        
        # Failed instruments (if any)
        if failed_instruments:
            lines.append("=" * 80)
            lines.append("")
            lines.append("SCAN FAILURES:")
            lines.append("")
            for instrument, error in failed_instruments[:5]:  # Show max 5
                lines.append(f"   {instrument}: {error}")
            
            if len(failed_instruments) > 5:
                lines.append(f"   ... and {len(failed_instruments) - 5} more")
            lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("")
        lines.append("⚠️  SIGNALS ARE READ-ONLY")
        lines.append("    Human review and manual execution required")
        lines.append("    No automatic trading, no price targets, no position sizing")
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_summary(
        self,
        total_scanned: int,
        eligible_count: int,
        top_signal_count: int
    ) -> str:
        """
        Generate one-line summary for logging.
        
        Args:
            total_scanned: Total instruments scanned
            eligible_count: Number of eligible signals
            top_signal_count: Number of top signals returned
        
        Returns:
            Summary string
        """
        if total_scanned == 0:
            return "Scan completed: 0 instruments"
        
        rarity_pct = (eligible_count / total_scanned) * 100
        return f"Scan completed: {total_scanned} scanned, {eligible_count} eligible ({rarity_pct:.1f}%), {top_signal_count} top signals"
