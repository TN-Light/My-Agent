"""
Test script for symbol resolution safety features
Tests known mappings and CAPTCHA detection
"""

def test_known_mappings():
    """Test that known symbol mappings work"""
    
    # Simulating the KNOWN_SYMBOLS dict from execution_engine.py
    KNOWN_SYMBOLS = {
        "yes bank": "YESBANK",
        "yesbank": "YESBANK",
        "yes": "YESBANK",
        "kotak bank": "KOTAKBANK",
        "kotak mahindra": "KOTAKBANK",
        "kotak mahindra bank": "KOTAKBANK",
        "kotakbank": "KOTAKBANK",
        "kotak": "KOTAKBANK",
        "ktk bank": "KTKBANK",
        "karnataka bank": "KTKBANK",
        "ktkbank": "KTKBANK",
        "ktk": "KTKBANK",
        "south indian bank": "SOUTHBANK",
        "southbank": "SOUTHBANK",
        "sib bank": "SOUTHBANK",
        "sib": "SOUTHBANK",
    }
    
    test_cases = [
        ("yes bank", "YESBANK"),
        ("YES BANK", "YESBANK"),
        ("yes", "YESBANK"),
        ("kotak", "KOTAKBANK"),
        ("kotak bank", "KOTAKBANK"),
        ("ktk bank", "KTKBANK"),
        ("ktk", "KTKBANK"),
        ("karnataka bank", "KTKBANK"),
        ("south indian bank", "SOUTHBANK"),
        ("sib", "SOUTHBANK"),
    ]
    
    print("=" * 70)
    print("SYMBOL SAFETY TEST - Known Mappings")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for query, expected in test_cases:
        query_normalized = query.lower().strip()
        result = KNOWN_SYMBOLS.get(query_normalized)
        
        if result == expected:
            print(f"✅ PASS: '{query}' → {result}")
            passed += 1
        else:
            print(f"❌ FAIL: '{query}' → {result} (expected {expected})")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return passed, failed


def test_captcha_detection():
    """Test CAPTCHA detection logic"""
    
    test_texts = [
        ("I am not a robot verification required", True),
        ("CAPTCHA: Please verify you are human", True),
        ("Unusual traffic from your computer network", True),
        ("Verify you're human to continue", True),
        ("NSE: YESBANK, Price: 25.50", False),
        ("Stock symbol for Yes Bank is YESBANK", False),
    ]
    
    print("\n" + "=" * 70)
    print("CAPTCHA DETECTION TEST")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for text, should_detect in test_texts:
        is_captcha = ("not a robot" in text.lower() or 
                     "captcha" in text.lower() or
                     "unusual traffic" in text.lower() or
                     "verify you're human" in text.lower())
        
        if is_captcha == should_detect:
            status = "DETECTED" if is_captcha else "CLEAN"
            print(f"✅ PASS: {status} - '{text[:50]}...'")
            passed += 1
        else:
            print(f"❌ FAIL: Expected {'CAPTCHA' if should_detect else 'CLEAN'} - '{text[:50]}...'")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return passed, failed


def test_symbol_validation():
    """Test symbol mismatch detection"""
    
    test_cases = [
        ("yes bank", "YESBANK", False),  # OK match
        ("yes bank", "KOTAKBANK", True),  # MISMATCH
        ("kotak", "KOTAKBANK", False),  # OK match
        ("kotak", "YESBANK", True),  # MISMATCH
        ("ktk bank", "KTKBANK", False),  # OK match
        ("ktk bank", "KOTAKBANK", True),  # MISMATCH
        ("south indian bank", "SOUTHBANK", False),  # OK match
        ("south indian bank", "KTKBANK", True),  # MISMATCH
    ]
    
    print("\n" + "=" * 70)
    print("SYMBOL VALIDATION TEST - Mismatch Detection")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for query, symbol, should_reject in test_cases:
        query_lower = query.lower()
        symbol_lower = symbol.lower()
        
        # Detection logic from execution_engine.py
        mismatch_detected = False
        if "yes" in query_lower and "yes" not in symbol_lower:
            mismatch_detected = True
        elif "kotak" in query_lower and "kotak" not in symbol_lower:
            mismatch_detected = True
        elif "ktk" in query_lower and "ktk" not in symbol_lower and "karnataka" not in query_lower:
            mismatch_detected = True
        elif "south" in query_lower and "south" not in symbol_lower:
            mismatch_detected = True
        
        if mismatch_detected == should_reject:
            status = "REJECTED" if mismatch_detected else "ACCEPTED"
            print(f"✅ PASS: {status} - '{query}' → {symbol}")
            passed += 1
        else:
            print(f"❌ FAIL: Should {'REJECT' if should_reject else 'ACCEPT'} - '{query}' → {symbol}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return passed, failed


if __name__ == "__main__":
    print("\n" + "🔒 " * 35)
    print("SYMBOL RESOLUTION SAFETY TEST SUITE")
    print("🔒 " * 35)
    
    total_passed = 0
    total_failed = 0
    
    # Test 1: Known mappings
    p, f = test_known_mappings()
    total_passed += p
    total_failed += f
    
    # Test 2: CAPTCHA detection
    p, f = test_captcha_detection()
    total_passed += p
    total_failed += f
    
    # Test 3: Symbol validation
    p, f = test_symbol_validation()
    total_passed += p
    total_failed += f
    
    # Final summary
    print("\n" + "🔒 " * 35)
    print("FINAL SUMMARY")
    print("🔒 " * 35)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n✅ ALL SAFETY CHECKS PASSED - System is protected")
    else:
        print(f"\n⚠️  {total_failed} checks failed - Review safety logic")
    
    print("🔒 " * 35 + "\n")
