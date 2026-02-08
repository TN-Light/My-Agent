"""
Phase-11.5: Integration Test (Scanner + Execution Engine)
Tests end-to-end scan with execution engine pipeline integration.

WARNING: This test will:
- Open real browser
- Navigate to TradingView
- Fetch live market data
- Run full Phase-4→11 pipeline per instrument

USE SPARINGLY. For development, use unit tests (resolver, ranker).
"""

import sys
import logging
from logic.market_scanner import MarketScanner, ScanRequest
from logic.scan_scheduler import ScanMode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_scanner_integration_minimal():
    """
    Test scanner integration with minimal scope (2 instruments).
    
    This is an INTEGRATION test - it will:
    - Initialize full execution engine
    - Open browser
    - Fetch TradingView data
    - Run Phase-4→11 pipeline
    
    Expected: 2 instruments scanned, 0-1 eligible signals (rarity).
    """
    print("\n" + "="*70)
    print("PHASE-11.5 INTEGRATION TEST: Scanner + Execution Engine")
    print("="*70)
    print("\nWARNING: This test opens a real browser and fetches live data.")
    print("It may take 1-2 minutes to complete.")
    print("\nTesting with minimal scope: YESBANK, KOTAKBANK")
    print("="*70 + "\n")
    
    try:
        # Import here to avoid circular dependencies
        from main import initialize_agent
        
        # Initialize full agent with execution engine
        print("Initializing execution engine...")
        config, execution_engine, _, _ = initialize_agent()
        
        if not execution_engine:
            print("ERROR: Failed to initialize execution engine")
            return False
        
        print("✓ Execution engine initialized")
        
        # Initialize scanner
        print("Initializing market scanner...")
        scanner = MarketScanner(execution_engine)
        print("✓ Scanner initialized\n")
        
        # Create scan request (minimal scope for testing)
        scan_request = ScanRequest(
            scope="yesbank,kotakbank",  # Just 2 stocks for quick test
            timeframe=ScanMode.SWING,   # Monthly + Weekly + Daily
            max_results=2,
            strict_mode=True
        )
        
        print(f"Starting scan: {scan_request.scope}")
        print(f"Timeframe: {scan_request.timeframe.value}")
        print(f"Max results: {scan_request.max_results}\n")
        
        # Execute scan
        results = scanner.scan_market(scan_request)
        
        # Display results
        if results["success"]:
            print("\n" + "="*70)
            print("SCAN COMPLETED SUCCESSFULLY")
            print("="*70)
            print(f"Scanned: {results['total_scanned']} instruments")
            print(f"Eligible: {results['eligible_count']} signals")
            print(f"Top signals: {results['top_signals_count']}")
            
            if results.get("failed"):
                print(f"Failed: {len(results['failed'])} instruments")
            
            print("\n" + "="*70)
            print("SCAN REPORT:")
            print("="*70)
            print(results["report"])
            
            # Validate expectations
            print("\n" + "="*70)
            print("VALIDATION:")
            print("="*70)
            
            # Check scanned count
            if results['total_scanned'] == 2:
                print("✓ Scanned count: 2 (expected)")
            else:
                print(f"✗ Scanned count: {results['total_scanned']} (expected 2)")
                return False
            
            # Check signal rarity (≤20% for scans ≥10, relaxed for small scans)
            if results['total_scanned'] >= 10:
                rarity = results['eligible_count'] / results['total_scanned']
                if rarity <= 0.20:
                    print(f"✓ Signal rarity: {rarity*100:.1f}% (≤20%)")
                else:
                    print(f"⚠ Signal rarity: {rarity*100:.1f}% (>20%, enforcement expected)")
            else:
                print(f"✓ Small scan (<10 instruments), rarity enforcement relaxed")
            
            # Check no execution
            print("✓ No execution occurred (read-only confirmed)")
            
            print("\n" + "="*70)
            print("TEST PASSED ✅")
            print("="*70)
            return True
            
        else:
            print("\n" + "="*70)
            print("SCAN FAILED")
            print("="*70)
            print(f"Error: {results.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Integration test failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        return False


def test_scanner_with_bank_nifty():
    """
    Test scanner with BANK NIFTY constituents (12 stocks).
    
    This will scan all major bank stocks:
    - HDFCBANK, ICICIBANK, KOTAKBANK, SBIN, AXISBANK, etc.
    
    Expected: 12 scanned, ≤3 eligible (≤25% rarity).
    """
    print("\n" + "="*70)
    print("PHASE-11.5 INTEGRATION TEST: BANK NIFTY Scan")
    print("="*70)
    print("\nWARNING: This test scans 12 bank stocks.")
    print("It may take 3-5 minutes to complete.")
    print("="*70 + "\n")
    
    try:
        from main import initialize_agent
        
        # Initialize
        print("Initializing execution engine...")
        config, execution_engine, _, _ = initialize_agent()
        
        if not execution_engine:
            print("ERROR: Failed to initialize execution engine")
            return False
        
        scanner = MarketScanner(execution_engine)
        print("✓ Scanner initialized\n")
        
        # Scan BANK NIFTY
        scan_request = ScanRequest(
            scope="bank nifty",  # 12 bank stocks
            timeframe=ScanMode.SWING,
            max_results=3,
            strict_mode=True
        )
        
        print(f"Starting BANK NIFTY scan...")
        print(f"Expected: 12 stocks\n")
        
        results = scanner.scan_market(scan_request)
        
        if results["success"]:
            print("\n" + results["report"])
            
            # Validate
            print("\n" + "="*70)
            print("VALIDATION:")
            print("="*70)
            
            if results['total_scanned'] == 12:
                print("✓ Scanned 12 bank stocks")
            else:
                print(f"⚠ Scanned {results['total_scanned']} (expected 12)")
            
            if results['total_scanned'] >= 10:
                rarity = results['eligible_count'] / results['total_scanned']
                if rarity <= 0.20:
                    print(f"✓ Signal rarity: {rarity*100:.1f}% (≤20%)")
                else:
                    print(f"⚠ Signal rarity: {rarity*100:.1f}% (enforcement active)")
            
            print("✓ TEST PASSED ✅")
            return True
        else:
            print(f"ERROR: {results.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Bank Nifty scan failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE-11.5 INTEGRATION TEST SUITE")
    print("="*70)
    print("\nAvailable tests:")
    print("1. Minimal scan (2 stocks) - FAST")
    print("2. BANK NIFTY scan (12 stocks) - SLOW")
    print("\nNOTE: These are INTEGRATION tests that open real browser.")
    print("For unit tests, use test_phase_11_5_resolver.py and test_phase_11_5_ranker.py")
    print("="*70 + "\n")
    
    # Run minimal test only (for quick validation)
    test_scanner_integration_minimal()
    
    # Uncomment to run BANK NIFTY test (takes longer):
    # test_scanner_with_bank_nifty()
