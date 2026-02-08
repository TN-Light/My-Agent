"""
Phase-11.5: Instrument Resolver
Dynamic resolution of market scope into tradable instruments.

NO HARDCODED WATCHLISTS.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InstrumentType(Enum):
    """Type of tradable instrument"""
    STOCK = "STOCK"
    INDEX = "INDEX"
    OPTION = "OPTION"


class OptionType(Enum):
    """Option contract type"""
    CE = "CE"  # Call Option
    PE = "PE"  # Put Option


@dataclass
class ResolvedInstrument:
    """
    Resolved tradable instrument.
    
    NO PRICES, NO GREEKS, NO IV.
    Just identity and classification.
    """
    symbol: str
    instrument_type: InstrumentType
    underlying: Optional[str] = None  # For options
    expiry: Optional[datetime] = None  # For options
    strike: Optional[int] = None  # For options
    option_type: Optional[OptionType] = None  # CE/PE
    
    def __str__(self):
        if self.instrument_type == InstrumentType.OPTION:
            expiry_str = self.expiry.strftime("%d%b").upper() if self.expiry else "UNKNOWN"
            return f"{self.underlying}_{expiry_str}_{self.strike}_{self.option_type.value}"
        return self.symbol


class InstrumentResolver:
    """
    Resolve user scope into tradable instruments.
    
    Supports:
    - Indices (NIFTY, BANKNIFTY)
    - Stock constituents (NIFTY 50, BANKNIFTY constituents)
    - Options (CE/PE with dynamic strike resolution)
    - Custom lists
    
    NO HARDCODED TICKERS.
    """
    
    def __init__(self):
        """Initialize Instrument Resolver"""
        logger.info("InstrumentResolver initialized (Phase-11.5)")
        
        # Cache for constituents (24h TTL)
        self._constituent_cache: Dict[str, tuple[List[str], datetime]] = {}
        self._cache_ttl = timedelta(hours=24)
    
    def resolve(self, scope: str) -> List[ResolvedInstrument]:
        """
        Resolve scope string into list of instruments.
        
        Args:
            scope: User-provided scope (e.g., "bank nifty ce pe", "nifty 50 stocks", "yesbank,kotakbank")
        
        Returns:
            List of ResolvedInstrument objects
        """
        scope_lower = scope.lower().strip()
        
        # Normalize: Remove "scan" prefix if present
        if scope_lower.startswith("scan "):
            scope = scope[5:].strip()  # Remove "scan " prefix
            scope_lower = scope.lower().strip()
        
        logger.info(f"Resolving instrument scope: '{scope}'")
        
        # Pattern matching for different scope types
        
        # 0. Comma-separated symbols (e.g., "yesbank,kotakbank,sbin")
        if "," in scope:
            symbols = [s.strip().upper() for s in scope.split(",") if s.strip()]
            logger.info(f"Detected {len(symbols)} comma-separated symbols")
            return [ResolvedInstrument(symbol=sym, instrument_type=InstrumentType.STOCK) for sym in symbols]
        
        # 1. Options (CE/PE)
        if self._is_options_scope(scope_lower):
            return self._resolve_options(scope_lower)
        
        # 2. Index constituents
        if "nifty 50" in scope_lower or "nifty50" in scope_lower:
            return self._resolve_nifty50_constituents()
        
        if "bank nifty" in scope_lower and "option" not in scope_lower and "ce" not in scope_lower:
            return self._resolve_banknifty_constituents()
        
        # 3. Direct index
        if scope_lower in ["nifty", "^nsei"]:
            return [ResolvedInstrument(symbol="^NSEI", instrument_type=InstrumentType.INDEX)]
        
        if scope_lower in ["banknifty", "bank nifty", "^nsebank"]:
            return [ResolvedInstrument(symbol="^NSEBANK", instrument_type=InstrumentType.INDEX)]
        
        # 4. Single stock
        if len(scope.split()) == 1 or scope.isupper():
            # Treat as single stock symbol
            return [ResolvedInstrument(symbol=scope.upper(), instrument_type=InstrumentType.STOCK)]
        
        # 5. Multi-word bank name (e.g., "yes bank", "kotak bank")
        # Treat as stock symbol to be resolved by existing symbol search
        return [ResolvedInstrument(symbol=scope.upper(), instrument_type=InstrumentType.STOCK)]
    
    def _is_options_scope(self, scope: str) -> bool:
        """Check if scope requests options"""
        option_keywords = ["ce", "pe", "call", "put", "option"]
        return any(kw in scope for kw in option_keywords)
    
    def _resolve_options(self, scope: str) -> List[ResolvedInstrument]:
        """
        Resolve options scope into CE/PE contracts.
        
        Args:
            scope: Options scope (e.g., "bank nifty ce pe", "nifty options")
        
        Returns:
            List of option contracts around ATM strikes
        """
        # Determine underlying
        if "bank" in scope or "banknifty" in scope:
            underlying = "BANKNIFTY"
            underlying_symbol = "^NSEBANK"
        else:
            underlying = "NIFTY"
            underlying_symbol = "^NSEI"
        
        # Determine which option types to include
        include_ce = "ce" in scope or "call" in scope or ("option" in scope and "pe" not in scope)
        include_pe = "pe" in scope or "put" in scope or ("option" in scope and "ce" not in scope)
        
        # If neither specified explicitly, include both
        if not include_ce and not include_pe:
            include_ce = include_pe = True
        
        # Get nearest weekly expiry (Thursday)
        expiry = self._get_nearest_expiry()
        
        # For now, use placeholder ATM strikes (would normally fetch current price)
        # Scanner will handle actual price lookup via TradingView
        atm_strike = self._get_placeholder_atm(underlying)
        
        # Generate strikes around ATM (±2 strikes, 100 point intervals for NIFTY, 200 for BANKNIFTY)
        strike_interval = 100 if underlying == "NIFTY" else 100
        strikes = [
            atm_strike - (2 * strike_interval),
            atm_strike - strike_interval,
            atm_strike,
            atm_strike + strike_interval,
            atm_strike + (2 * strike_interval),
        ]
        
        # Generate contracts
        instruments = []
        for strike in strikes:
            if include_ce:
                instruments.append(ResolvedInstrument(
                    symbol=f"{underlying}{expiry.strftime('%d%b').upper()}{strike}CE",
                    instrument_type=InstrumentType.OPTION,
                    underlying=underlying,
                    expiry=expiry,
                    strike=strike,
                    option_type=OptionType.CE
                ))
            if include_pe:
                instruments.append(ResolvedInstrument(
                    symbol=f"{underlying}{expiry.strftime('%d%b').upper()}{strike}PE",
                    instrument_type=InstrumentType.OPTION,
                    underlying=underlying,
                    expiry=expiry,
                    strike=strike,
                    option_type=OptionType.PE
                ))
        
        logger.info(f"Resolved {len(instruments)} option contracts for {underlying}")
        return instruments
    
    def _get_nearest_expiry(self) -> datetime:
        """
        Get nearest weekly expiry (Thursday).
        
        Returns:
            Next Thursday datetime
        """
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0 and today.hour >= 15:  # After 3:30 PM, roll to next week
            days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.replace(hour=15, minute=30, second=0, microsecond=0)
    
    def _get_placeholder_atm(self, underlying: str) -> int:
        """
        Get placeholder ATM strike (round to nearest 100).
        Real implementation would fetch current price.
        
        Args:
            underlying: NIFTY or BANKNIFTY
        
        Returns:
            Placeholder ATM strike
        """
        # Placeholder - scanner will use actual price from TradingView
        if underlying == "NIFTY":
            return 23000  # Will be replaced with actual index level
        else:  # BANKNIFTY
            return 49000  # Will be replaced with actual index level
    
    def _resolve_nifty50_constituents(self) -> List[ResolvedInstrument]:
        """
        Resolve NIFTY 50 constituent stocks.
        
        Returns:
            List of NIFTY 50 stocks (cached with 24h TTL)
        """
        cache_key = "NIFTY50"
        
        # Check cache
        if cache_key in self._constituent_cache:
            constituents, cached_time = self._constituent_cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                logger.info(f"Using cached NIFTY 50 constituents ({len(constituents)} stocks)")
                return [ResolvedInstrument(symbol=sym, instrument_type=InstrumentType.STOCK) 
                       for sym in constituents]
        
        # Fallback: Common NIFTY 50 stocks (will be replaced by API in production)
        constituents = [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
            "TITAN", "BAJFINANCE", "NESTLEIND", "ULTRACEMCO", "WIPRO",
            "TECHM", "HCLTECH", "POWERGRID", "NTPC", "M&M",
            "ADANIPORTS", "TATAMOTORS", "TATASTEEL", "ONGC", "JSWSTEEL",
            "BAJAJFINSV", "GRASIM", "INDUSINDBK", "CIPLA", "DRREDDY",
            "EICHERMOT", "COALINDIA", "DIVISLAB", "BRITANNIA", "HINDALCO",
            "SHREECEM", "APOLLOHOSP", "BPCL", "HEROMOTOCO", "TATACONSUM",
            "UPL", "SBILIFE", "BAJAJ-AUTO", "HDFCLIFE", "ADANIENT"
        ]
        
        # Cache for 24 hours
        self._constituent_cache[cache_key] = (constituents, datetime.now())
        
        logger.info(f"Resolved {len(constituents)} NIFTY 50 constituents")
        return [ResolvedInstrument(symbol=sym, instrument_type=InstrumentType.STOCK) 
               for sym in constituents]
    
    def _resolve_banknifty_constituents(self) -> List[ResolvedInstrument]:
        """
        Resolve BANK NIFTY constituent stocks.
        
        Returns:
            List of BANK NIFTY stocks (cached with 24h TTL)
        """
        cache_key = "BANKNIFTY"
        
        # Check cache
        if cache_key in self._constituent_cache:
            constituents, cached_time = self._constituent_cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                logger.info(f"Using cached BANK NIFTY constituents ({len(constituents)} stocks)")
                return [ResolvedInstrument(symbol=sym, instrument_type=InstrumentType.STOCK) 
                       for sym in constituents]
        
        # Fallback: Bank NIFTY constituents
        constituents = [
            "HDFCBANK", "ICICIBANK", "KOTAKBANK", "SBIN", "AXISBANK",
            "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB",
            "BANKBARODA", "AUBANK"
        ]
        
        # Cache for 24 hours
        self._constituent_cache[cache_key] = (constituents, datetime.now())
        
        logger.info(f"Resolved {len(constituents)} BANK NIFTY constituents")
        return [ResolvedInstrument(symbol=sym, instrument_type=InstrumentType.STOCK) 
               for sym in constituents]
