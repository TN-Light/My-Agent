"""
Phase-11.5: Scan Scheduler
Timeframe-based scanning rules.

Determines which timeframes to use for scanning.
"""

import logging
from typing import List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ScanMode(Enum):
    """Scanning mode / timeframe class"""
    INTRADAY = "INTRADAY"
    SWING = "SWING"
    POSITIONAL = "POSITIONAL"


class ScanScheduler:
    """
    Determine timeframes for scanning based on mode.
    
    Rules:
    - INTRADAY: 15m, 1h, 4h
    - SWING: 1D, 1W
    - POSITIONAL: 1W, 1M
    
    Auto-downgrade if insufficient data.
    """
    
    def __init__(self):
        """Initialize Scan Scheduler"""
        logger.info("ScanScheduler initialized (Phase-11.5)")
    
    def get_timeframes(self, mode: ScanMode) -> List[str]:
        """
        Get timeframes for scan mode.
        
        Args:
            mode: INTRADAY / SWING / POSITIONAL
        
        Returns:
            List of timeframe codes for TradingView
        """
        if mode == ScanMode.INTRADAY:
            # For intraday: 15m, 1h, 4h
            return ["15", "60", "240"]  # TradingView codes: 15m, 1h, 4h
        
        elif mode == ScanMode.SWING:
            # For swing: Daily, Weekly
            return ["1D", "1W"]
        
        elif mode == ScanMode.POSITIONAL:
            # For positional: Weekly, Monthly
            return ["1W", "1M"]
        
        else:
            # Default to swing
            logger.warning(f"Unknown scan mode: {mode}, defaulting to SWING")
            return ["1D", "1W"]
    
    def should_downgrade(self, mode: ScanMode, data_available: int) -> Tuple[bool, ScanMode]:
        """
        Check if mode should be downgraded due to insufficient data.
        
        Args:
            mode: Current scan mode
            data_available: Number of data points available
        
        Returns:
            (should_downgrade, new_mode)
        """
        # Minimum data requirements
        min_data = {
            ScanMode.INTRADAY: 100,  # Need 100 bars for intraday
            ScanMode.SWING: 60,      # Need 60 days
            ScanMode.POSITIONAL: 24  # Need 24 weeks (6 months)
        }
        
        if data_available < min_data.get(mode, 0):
            # Downgrade
            if mode == ScanMode.INTRADAY:
                logger.warning(f"Insufficient data ({data_available} bars) for INTRADAY, downgrading to SWING")
                return True, ScanMode.SWING
            elif mode == ScanMode.SWING:
                logger.warning(f"Insufficient data ({data_available} bars) for SWING, downgrading to POSITIONAL")
                return True, ScanMode.POSITIONAL
        
        return False, mode
