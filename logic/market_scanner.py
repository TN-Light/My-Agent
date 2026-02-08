"""
Phase-11.5: Market Scanner (CORE)
Multi-instrument scanning engine.

SCANNER NEVER THINKS.
It only asks the existing brain (Phase-4→11) the same question many times.
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from logic.instrument_resolver import InstrumentResolver, ResolvedInstrument
from logic.scan_scheduler import ScanScheduler, ScanMode
from logic.signal_ranker import SignalRanker, RankedSignal
from logic.scan_reporter import ScanReporter

logger = logging.getLogger(__name__)


@dataclass
class ScanRequest:
    """
    Scan request specification.
    """
    scope: str  # e.g., "bank nifty ce pe", "nifty 50 stocks"
    timeframe: ScanMode = ScanMode.SWING
    max_results: int = 5
    strict_mode: bool = True  # Enforce signal rarity


class MarketScanner:
    """
    Phase-11.5 Core: Multi-instrument scanning engine.
    
    Flow:
    1. Resolve scope → instruments
    2. For each instrument:
       - Run Phase-4 (structure)
       - Run Phase-5 (scenarios)
       - Run Phase-6A (probabilities)
       - Run Phase-7A (gates)
       - Run Phase-X (summary)
       - Run Phase-11 (signal eligibility)
    3. Rank eligible signals
    4. Generate report
    
    NO SHORTCUTS, NO PARALLEL REASONING, DETERMINISTIC.
    """
    
    def __init__(self, execution_engine):
        """
        Initialize Market Scanner.
        
        Args:
            execution_engine: ExecutionEngine instance (for running Phase-4→11 pipeline)
        """
        self.execution_engine = execution_engine
        self.resolver = InstrumentResolver()
        self.scheduler = ScanScheduler()
        self.ranker = SignalRanker()
        self.reporter = ScanReporter()
        
        logger.info("MarketScanner initialized (Phase-11.5)")
    
    def scan_market(self, scan_request: ScanRequest) -> Dict[str, Any]:
        """
        Execute market scan.
        
        Args:
            scan_request: ScanRequest specification
        
        Returns:
            Scan results dictionary with signals and metadata
        """
        logger.info(f"Starting market scan: scope='{scan_request.scope}', timeframe={scan_request.timeframe.value}")
        
        # Step 1: Resolve scope into instruments
        try:
            instruments = self.resolver.resolve(scan_request.scope)
            logger.info(f"Resolved {len(instruments)} instruments from scope")
        except Exception as e:
            logger.error(f"Instrument resolution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to resolve instruments: {str(e)}",
                "instruments": [],
                "signals": [],
                "report": ""
            }
        
        if not instruments:
            logger.warning("No instruments resolved from scope")
            return {
                "success": True,
                "instruments": [],
                "signals": [],
                "report": self.reporter.generate_report(
                    scope=scan_request.scope,
                    timeframe=scan_request.timeframe.value,
                    total_scanned=0,
                    eligible_count=0,
                    ranked_signals=[]
                )
            }
        
        # Step 2: Scan each instrument
        scan_results = []
        failed_instruments = []
        
        for i, instrument in enumerate(instruments, 1):
            logger.info(f"Scanning instrument {i}/{len(instruments)}: {instrument.symbol}")
            
            try:
                # Run full Phase-4→11 pipeline for this instrument
                signal = self._analyze_instrument(instrument, scan_request.timeframe)
                
                if signal:
                    scan_results.append((str(instrument), signal))
                    logger.info(f"  → {instrument.symbol}: {signal.signal_status.value}")
                else:
                    failed_instruments.append((str(instrument), "Analysis returned None"))
                    logger.warning(f"  → {instrument.symbol}: Analysis failed (None)")
                    
            except Exception as e:
                error_msg = str(e)[:100]  # Truncate error
                failed_instruments.append((str(instrument), error_msg))
                logger.error(f"  → {instrument.symbol}: SCAN_FAILED - {error_msg}")
                # Continue to next instrument (no global abort)
        
        # Step 3: Rank signals
        eligible_count = sum(1 for _, signal in scan_results if signal.signal_status.value == "ELIGIBLE")
        ranked_signals = self.ranker.rank_signals(scan_results, max_results=scan_request.max_results)
        
        # Step 4: Generate report
        report = self.reporter.generate_report(
            scope=scan_request.scope,
            timeframe=scan_request.timeframe.value,
            total_scanned=len(instruments),
            eligible_count=eligible_count,
            ranked_signals=ranked_signals,
            failed_instruments=failed_instruments if failed_instruments else None
        )
        
        # Log summary
        summary = self.reporter.generate_summary(len(instruments), eligible_count, len(ranked_signals))
        logger.info(summary)
        
        return {
            "success": True,
            "scope": scan_request.scope,
            "timeframe": scan_request.timeframe.value,
            "total_scanned": len(instruments),
            "eligible_count": eligible_count,
            "top_signals_count": len(ranked_signals),
            "instruments": [str(inst) for inst in instruments],
            "signals": [rs.to_dict() for rs in ranked_signals],
            "failed": failed_instruments,
            "report": report
        }
    
    def _analyze_instrument(
        self,
        instrument: ResolvedInstrument,
        scan_mode: ScanMode
    ) -> Optional[Any]:
        """
        Run Phase-4→11 pipeline for single instrument.
        
        Args:
            instrument: Resolved instrument to analyze
            scan_mode: INTRADAY / SWING / POSITIONAL
        
        Returns:
            SignalContract from Phase-11 (or None if failed)
        """
        # Call execution engine's Phase-4→11 pipeline
        # READ-ONLY: No UI display, returns SignalContract only
        try:
            signal = self.execution_engine.analyze_instrument_for_scan(
                symbol=instrument.symbol,
                timeframe_mode=scan_mode.value
            )
            return signal
        except Exception as e:
            logger.error(f"Instrument analysis failed for {instrument.symbol}: {e}", exc_info=True)
            return None
        
        # For now, return a placeholder
        # This will be integrated with actual execution_engine methods
        
        logger.warning(f"_analyze_instrument placeholder called for {instrument.symbol}")
        return None
