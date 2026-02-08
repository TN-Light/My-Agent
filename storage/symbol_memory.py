"""
Symbol Memory - Phase-11.5G
Caches successful symbol resolutions to avoid repeated Google searches.

Stores mappings:
- User text → NSE symbol
- Confidence level
- Timestamp
- Expiry: 30 days
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class CachedSymbol:
    """Cached symbol resolution."""
    user_text: str
    nse_symbol: str
    confidence: str  # HIGH, MEDIUM, LOW
    source: str  # GOOGLE, TRADINGVIEW, USER
    timestamp: str
    
    def is_expired(self, max_age_days: int = 30) -> bool:
        """Check if cache entry is expired."""
        try:
            cached_time = datetime.fromisoformat(self.timestamp)
            age = datetime.now() - cached_time
            return age > timedelta(days=max_age_days)
        except Exception:
            return True  # Invalid timestamp = expired


class SymbolMemory:
    """
    In-memory and persistent cache for symbol resolutions.
    
    Prevents repeated Google searches for the same user input.
    """
    
    def __init__(self, cache_file: str = "symbol_cache.json"):
        """
        Initialize symbol memory.
        
        Args:
            cache_file: Path to JSON cache file
        """
        self.cache_file = Path(cache_file)
        self.memory: Dict[str, CachedSymbol] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from disk."""
        if not self.cache_file.exists():
            logger.info("Symbol cache does not exist, starting fresh")
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert dict to CachedSymbol objects
            for user_text, entry in data.items():
                cached = CachedSymbol(**entry)
                if not cached.is_expired():
                    self.memory[user_text.lower()] = cached
                else:
                    logger.debug(f"Expired cache entry: {user_text} -> {cached.nse_symbol}")
            
            logger.info(f"Loaded {len(self.memory)} symbol resolutions from cache")
        except Exception as e:
            logger.error(f"Failed to load symbol cache: {e}")
            self.memory = {}
    
    def _save_cache(self):
        """Save cache to disk."""
        try:
            # Convert CachedSymbol objects to dict
            data = {
                user_text: asdict(cached)
                for user_text, cached in self.memory.items()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved {len(self.memory)} symbol resolutions to cache")
        except Exception as e:
            logger.error(f"Failed to save symbol cache: {e}")
    
    def lookup(self, user_text: str) -> Optional[CachedSymbol]:
        """
        Look up symbol resolution in cache.
        
        Args:
            user_text: User input text (e.g., "tata consumer", "ktk bank")
        
        Returns:
            CachedSymbol if found and not expired, None otherwise
        """
        normalized = user_text.lower().strip()
        cached = self.memory.get(normalized)
        
        if cached:
            if cached.is_expired():
                logger.debug(f"Cache hit but expired: {user_text} -> {cached.nse_symbol}")
                del self.memory[normalized]
                self._save_cache()
                return None
            
            logger.info(f"Cache HIT: {user_text} -> {cached.nse_symbol} (confidence: {cached.confidence})")
            return cached
        
        return None
    
    def store(
        self,
        user_text: str,
        nse_symbol: str,
        confidence: str,
        source: str
    ):
        """
        Store successful symbol resolution.
        
        Args:
            user_text: User input text
            nse_symbol: Resolved NSE symbol
            confidence: HIGH, MEDIUM, LOW
            source: GOOGLE, TRADINGVIEW, USER
        """
        normalized = user_text.lower().strip()
        
        cached = CachedSymbol(
            user_text=user_text,
            nse_symbol=nse_symbol,
            confidence=confidence,
            source=source,
            timestamp=datetime.now().isoformat()
        )
        
        self.memory[normalized] = cached
        self._save_cache()
        
        logger.info(f"Cache STORE: {user_text} -> {nse_symbol} (confidence: {confidence}, source: {source})")
    
    def invalidate(self, user_text: str):
        """
        Invalidate cache entry.
        
        Args:
            user_text: User input text to invalidate
        """
        normalized = user_text.lower().strip()
        if normalized in self.memory:
            del self.memory[normalized]
            self._save_cache()
            logger.info(f"Cache INVALIDATE: {user_text}")
    
    def clear_expired(self):
        """Remove all expired entries from cache."""
        before_count = len(self.memory)
        
        self.memory = {
            user_text: cached
            for user_text, cached in self.memory.items()
            if not cached.is_expired()
        }
        
        removed_count = before_count - len(self.memory)
        if removed_count > 0:
            self._save_cache()
            logger.info(f"Cleared {removed_count} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_entries": len(self.memory),
            "cache_file": str(self.cache_file),
            "sources": {
                "GOOGLE": sum(1 for c in self.memory.values() if c.source == "GOOGLE"),
                "TRADINGVIEW": sum(1 for c in self.memory.values() if c.source == "TRADINGVIEW"),
                "USER": sum(1 for c in self.memory.values() if c.source == "USER")
            },
            "confidence": {
                "HIGH": sum(1 for c in self.memory.values() if c.confidence == "HIGH"),
                "MEDIUM": sum(1 for c in self.memory.values() if c.confidence == "MEDIUM"),
                "LOW": sum(1 for c in self.memory.values() if c.confidence == "LOW")
            }
        }
