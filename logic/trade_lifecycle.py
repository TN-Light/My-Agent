"""
PHASE-8A: TRADE LIFECYCLE TRACKER
Purpose: Track execution facts only - no opinions, no profit labels

NON-NEGOTIABLE RULES:
1. Facts only: prices, times, excursions
2. No P&L calculations (structure decides correctness, not money)
3. MAE/MFE tracked for expectancy measurement
4. Exit reason tracked for pattern analysis

Philosophy:
"Structure > P&L. Measure truth, not opinion."
"""

from datetime import datetime
from typing import Optional
import uuid

from storage.trade_lifecycle_store import TradeLifecycleStore


class TradeLifecycleTracker:
    """
    Track trade execution lifecycle.
    
    Tracks facts only - no reasoning, no profit labels.
    """
    
    def __init__(self, store: Optional[TradeLifecycleStore] = None):
        """
        Initialize tracker.
        
        Args:
            store: Database store (creates new if None)
        """
        self.store = store or TradeLifecycleStore()
    
    def create_trade(
        self,
        symbol: str,
        timeframe: str,
        market_mode: str,
        scenario: str,
        probability: float,
        alignment_state: str,
        htf_support: Optional[float],
        htf_resistance: Optional[float],
        htf_direction: str,
        entry_price: float,
        direction: str,
        entry_time: Optional[datetime] = None
    ) -> str:
        """
        Create new trade record.
        
        Args:
            symbol: Trading symbol
            timeframe: Chart timeframe
            market_mode: INTRADAY or SWING
            scenario: Active scenario (A/B/C)
            probability: Scenario probability
            alignment_state: Alignment state
            htf_support/resistance: HTF structural levels (for resolution)
            htf_direction: HTF trend (BULLISH/BEARISH/NEUTRAL)
            entry_price: Entry price
            direction: Trade direction (LONG/SHORT)
            entry_time: Entry timestamp (defaults to now)
        
        Returns:
            trade_id
        """
        if entry_time is None:
            entry_time = datetime.now()
        
        # Generate unique trade ID
        trade_id = str(uuid.uuid4())
        
        # Validate inputs
        if market_mode not in ["INTRADAY", "SWING"]:
            raise ValueError(f"Invalid market_mode: {market_mode}")
        if scenario not in ["A", "B", "C"]:
            raise ValueError(f"Invalid scenario: {scenario}")
        if direction not in ["LONG", "SHORT"]:
            raise ValueError(f"Invalid direction: {direction}")
        if not (0.0 <= probability <= 1.0):
            raise ValueError(f"Invalid probability: {probability}")
        
        # Store trade
        self.store.create_trade(
            trade_id=trade_id,
            symbol=symbol,
            timeframe=timeframe,
            market_mode=market_mode,
            scenario=scenario,
            probability=probability,
            alignment_state=alignment_state,
            htf_support=htf_support,
            htf_resistance=htf_resistance,
            htf_direction=htf_direction,
            entry_price=entry_price,
            entry_time=entry_time,
            direction=direction
        )
        
        return trade_id
    
    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        mae: float,
        mfe: float,
        exit_time: Optional[datetime] = None
    ) -> None:
        """
        Close trade and record exit.
        
        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            exit_reason: TIME | STRUCTURE_BREAK | MANUAL | AUTO_EXIT
            mae: Max Adverse Excursion (worst point, in points)
            mfe: Max Favorable Excursion (best point, in points)
            exit_time: Exit timestamp (defaults to now)
        """
        if exit_time is None:
            exit_time = datetime.now()
        
        # Validate exit reason
        valid_reasons = ["TIME", "STRUCTURE_BREAK", "MANUAL", "AUTO_EXIT"]
        if exit_reason not in valid_reasons:
            raise ValueError(f"Invalid exit_reason: {exit_reason}. Must be one of {valid_reasons}")
        
        # Update trade
        self.store.update_exit(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
            mae=mae,
            mfe=mfe
        )
    
    def get_trade(self, trade_id: str) -> Optional[dict]:
        """
        Get trade by ID.
        
        Args:
            trade_id: Trade identifier
        
        Returns:
            Trade dictionary or None
        """
        return self.store.get_trade(trade_id)
    
    def get_open_trades(self) -> list:
        """
        Get all open (unexited) trades.
        
        Returns:
            List of open trades
        """
        all_trades = self.store.get_all_trades()
        return [t for t in all_trades if t["exit_price"] is None]
    
    def get_closed_trades(self) -> list:
        """
        Get all closed (exited) trades.
        
        Returns:
            List of closed trades
        """
        all_trades = self.store.get_all_trades()
        return [t for t in all_trades if t["exit_price"] is not None]
    
    def get_unresolved_trades(self) -> list:
        """
        Get trades that are closed but not yet resolved.
        
        Returns:
            List of unresolved trades
        """
        closed = self.get_closed_trades()
        return [t for t in closed if t["resolved_scenario"] is None]
    
    def __repr__(self) -> str:
        """String representation."""
        all_trades = self.store.get_all_trades()
        open_count = len([t for t in all_trades if t["exit_price"] is None])
        closed_count = len([t for t in all_trades if t["exit_price"] is not None])
        
        return f"TradeLifecycleTracker(open={open_count}, closed={closed_count}, total={len(all_trades)})"
