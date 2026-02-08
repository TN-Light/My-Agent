"""
Market Memory Client - Phase-2C
Semantic search and retrieval of market analyses using ChromaDB.

Enables natural language queries over stored analyses.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

# Lazy import ChromaDB to avoid slow startup
CHROMADB_AVAILABLE = False
chromadb = None

def _lazy_import_chromadb():
    """Lazy import ChromaDB only when needed."""
    global CHROMADB_AVAILABLE, chromadb
    if chromadb is None:
        try:
            import chromadb as _chromadb
            chromadb = _chromadb
            CHROMADB_AVAILABLE = True
            logger.info("ChromaDB imported successfully")
        except ImportError:
            CHROMADB_AVAILABLE = False
            logger.warning("ChromaDB not available, using SQL-only mode")

logger = logging.getLogger(__name__)


class MarketMemory:
    """
    Semantic memory layer for market analyses.
    
    Uses ChromaDB to store embeddings of analyses for natural language retrieval.
    Falls back to SQLite-only if ChromaDB unavailable.
    """
    
    def __init__(self, chroma_path: str = "db/market_memory", store=None):
        """
        Initialize market memory.
        
        Args:
            chroma_path: Path to ChromaDB persistent storage
            store: MarketAnalysisStore instance (required)
        """
        if store is None:
            raise ValueError("MarketAnalysisStore required")
        
        self.store = store
        self.chroma_path = chroma_path
        self.client = None
        self.collection = None
        
        # Try lazy initialization of ChromaDB
        _lazy_import_chromadb()
        
        # Use global CHROMADB_AVAILABLE after lazy import
        global CHROMADB_AVAILABLE
        
        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=chroma_path)
                self.collection = self.client.get_or_create_collection(
                    name="market_analyses",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"MarketMemory initialized with ChromaDB at {chroma_path}")
            except Exception as e:
                logger.warning(f"ChromaDB initialization failed: {e}. Using SQLite only.")
                CHROMADB_AVAILABLE = False
        else:
            logger.warning("ChromaDB not available. Using SQLite only for queries.")
    
    def store_analysis(self, analysis: Dict[str, Any], analysis_id: int):
        """
        Store analysis in semantic memory.
        
        Args:
            analysis: Analysis dictionary
            analysis_id: Database ID from SQLite store
        """
        if not CHROMADB_AVAILABLE or self.collection is None:
            return
        
        try:
            # Create searchable text representation
            symbol = analysis.get("symbol", "Unknown")
            timeframe = analysis.get("timeframe", "Unknown")
            trend = analysis.get("trend", "Unknown")
            momentum = analysis.get("momentum", "Unknown")
            bias = analysis.get("bias", "")
            
            # Format for embedding
            text = f"""
            Symbol: {symbol}
            Timeframe: {timeframe}
            Trend: {trend}
            Momentum: {momentum}
            Bias: {bias}
            """.strip()
            
            # Store in ChromaDB
            self.collection.add(
                documents=[text],
                metadatas=[{
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "trend": trend,
                    "analysis_id": str(analysis_id),
                    "timestamp": analysis.get("timestamp", datetime.now().isoformat())
                }],
                ids=[f"analysis_{analysis_id}"]
            )
            
            logger.info(f"Stored analysis {analysis_id} in semantic memory")
            
        except Exception as e:
            logger.error(f"Failed to store in ChromaDB: {e}")
    
    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant analyses.
        
        Args:
            query_text: Natural language query
            n_results: Number of results to return
            
        Returns:
            List of relevant analyses
        """
        if not CHROMADB_AVAILABLE or self.collection is None:
            # Fallback to keyword-based search
            return self._keyword_search(query_text, n_results)
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            # Retrieve full analyses from SQLite
            analyses = []
            if results and results.get("metadatas") and results["metadatas"][0]:
                for metadata in results["metadatas"][0]:
                    analysis_id = int(metadata.get("analysis_id", -1))
                    if analysis_id > 0:
                        # Get from SQLite by reconstructing
                        symbol = metadata.get("symbol")
                        full_analysis = self.store.get_latest_analysis(symbol)
                        if full_analysis:
                            analyses.append(full_analysis)
            
            return analyses
            
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return self._keyword_search(query_text, n_results)
    
    def _keyword_search(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Fallback keyword-based search using SQLite.
        
        Args:
            query_text: Query text
            n_results: Number of results
            
        Returns:
            List of analyses
        """
        # Extract potential symbol from query
        query_upper = query_text.upper()
        
        # Common symbols
        symbols = [
            "RELIANCE", "TCS", "INFY", "INFOSYS", "HDFCBANK", "HDFC",
            "ICICIBANK", "ICICI", "SBIN", "BHARTIARTL", "ITC",
            "KOTAKBANK", "KOTAK", "LT", "ASIANPAINT", "AXISBANK",
            "NIFTY", "SENSEX", "BANKNIFTY"
        ]
        
        found_symbols = [s for s in symbols if s in query_upper]
        
        if found_symbols:
            # Get latest for each found symbol
            results = []
            for symbol in found_symbols[:n_results]:
                analysis = self.store.get_latest_analysis(symbol)
                if analysis:
                    results.append(analysis)
            return results
        else:
            # Return recent analyses
            return self.store.get_recent_analyses(hours=24, limit=n_results)
    
    def get_latest_for_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest analysis for a specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Latest analysis or None
        """
        return self.store.get_latest_analysis(symbol)
    
    def compare_symbols(
        self,
        symbols: List[str],
        timeframe: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple symbols.
        
        Args:
            symbols: List of symbols to compare
            timeframe: Optional timeframe filter
            
        Returns:
            Comparison dictionary
        """
        analyses = self.store.get_latest_by_symbols(symbols, timeframe)
        
        comparison = {
            "symbols": symbols,
            "timeframe": timeframe or "latest",
            "analyses": {},
            "summary": {}
        }
        
        bullish_count = 0
        bearish_count = 0
        sideways_count = 0
        
        for symbol, analysis in analyses.items():
            if analysis:
                comparison["analyses"][symbol] = analysis
                trend = analysis.get("trend", "").lower()
                if "bullish" in trend:
                    bullish_count += 1
                elif "bearish" in trend:
                    bearish_count += 1
                else:
                    sideways_count += 1
            else:
                comparison["analyses"][symbol] = None
        
        # Determine strongest
        strongest = None
        strongest_score = -1
        
        for symbol, analysis in comparison["analyses"].items():
            if analysis:
                # Simple scoring: bullish with strong momentum
                trend = analysis.get("trend", "").lower()
                momentum = analysis.get("momentum", "").lower()
                
                score = 0
                if "bullish" in trend:
                    score += 2
                elif "sideways" in trend:
                    score += 1
                
                if "strong" in momentum:
                    score += 2
                elif "moderate" in momentum:
                    score += 1
                
                if score > strongest_score:
                    strongest_score = score
                    strongest = symbol
        
        comparison["summary"] = {
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "sideways_count": sideways_count,
            "strongest": strongest,
            "market_bias": "bullish" if bullish_count > bearish_count else 
                          "bearish" if bearish_count > bullish_count else "mixed"
        }
        
        return comparison
    
    def check_trend_change(
        self,
        symbol: str,
        current_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if trend has changed for a symbol.
        
        Args:
            symbol: Stock symbol
            current_analysis: Current analysis (optional, will fetch if not provided)
            
        Returns:
            Trend change information
        """
        if not current_analysis:
            current_analysis = self.store.get_latest_analysis(symbol)
        
        if not current_analysis:
            return {
                "symbol": symbol,
                "changed": False,
                "message": f"No analysis found for {symbol}"
            }
        
        current_trend = current_analysis.get("trend", "Unknown")
        change_info = self.store.has_trend_changed(symbol, current_trend, lookback=5)
        
        return {
            "symbol": symbol,
            "current_trend": current_trend,
            "changed": change_info["changed"],
            "previous_trend": change_info.get("previous_trend"),
            "description": change_info.get("change_description"),
            "timestamp": current_analysis.get("timestamp")
        }
    
    def get_market_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get overall market summary from recent analyses.
        
        Args:
            hours: Time window for summary
            
        Returns:
            Market summary
        """
        recent = self.store.get_recent_analyses(hours=hours, limit=50)
        
        if not recent:
            return {
                "period_hours": hours,
                "total_analyses": 0,
                "message": "No recent analyses available"
            }
        
        bullish = sum(1 for a in recent if "bullish" in a.get("trend", "").lower())
        bearish = sum(1 for a in recent if "bearish" in a.get("trend", "").lower())
        sideways = sum(1 for a in recent if "sideways" in a.get("trend", "").lower() or 
                       a.get("trend", "").lower() == "neutral")
        
        symbols_analyzed = list(set(a.get("symbol", "Unknown") for a in recent))
        
        return {
            "period_hours": hours,
            "total_analyses": len(recent),
            "unique_symbols": len(symbols_analyzed),
            "symbols": symbols_analyzed[:10],  # Top 10
            "bullish_count": bullish,
            "bearish_count": bearish,
            "sideways_count": sideways,
            "overall_bias": "bullish" if bullish > bearish else 
                           "bearish" if bearish > bullish else "mixed",
            "sentiment_ratio": round(bullish / len(recent) * 100, 1) if recent else 0
        }
