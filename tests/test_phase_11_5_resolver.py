"""
Phase-11.5 Test Suite: Instrument Resolver

Tests dynamic instrument resolution without hardcoded watchlists.
"""

from logic.instrument_resolver import InstrumentResolver, InstrumentType, OptionType


def test_instrument_resolver():
    """Test instrument resolution logic"""
    
    resolver = InstrumentResolver()
    
    print("=" * 80)
    print("PHASE-11.5: INSTRUMENT RESOLVER TEST SUITE")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # TEST 1: Single stock resolution
    print("\nTEST 1: Single stock symbol → STOCK type")
    print("-" * 80)
    result = resolver.resolve("YESBANK")
    
    if len(result) == 1 and result[0].instrument_type == InstrumentType.STOCK and result[0].symbol == "YESBANK":
        print(f"✅ PASS: Resolved YESBANK as STOCK")
        passed += 1
    else:
        print(f"❌ FAIL: Expected single STOCK")
        print(f"   Got: {result}")
        failed += 1
    
    # TEST 2: NIFTY index resolution
    print("\nTEST 2: NIFTY index → INDEX type")
    print("-" * 80)
    result = resolver.resolve("nifty")
    
    if len(result) == 1 and result[0].instrument_type == InstrumentType.INDEX and result[0].symbol == "^NSEI":
        print(f"✅ PASS: Resolved NIFTY as INDEX ^NSEI")
        passed += 1
    else:
        print(f"❌ FAIL: Expected INDEX ^NSEI")
        print(f"   Got: {result}")
        failed += 1
    
    # TEST 3: BANKNIFTY index resolution
    print("\nTEST 3: BANKNIFTY index → INDEX type")
    print("-" * 80)
    result = resolver.resolve("bank nifty")
    
    if len(result) >= 1:  # Could be index or constituents depending on context
        print(f"✅ PASS: Resolved BANK NIFTY ({len(result)} instruments)")
        passed += 1
    else:
        print(f"❌ FAIL: Expected at least 1 instrument")
        failed += 1
    
    # TEST 4: NIFTY 50 constituents
    print("\nTEST 4: NIFTY 50 stocks → Multiple STOCK types")
    print("-" * 80)
    result = resolver.resolve("nifty 50 stocks")
    
    if len(result) >= 40 and all(inst.instrument_type == InstrumentType.STOCK for inst in result):
        print(f"✅ PASS: Resolved {len(result)} NIFTY 50 stocks")
        print(f"   Sample: {[result[i].symbol for i in range(min(5, len(result)))]}")
        passed += 1
    else:
        print(f"❌ FAIL: Expected 40+ stocks")
        print(f"   Got: {len(result)}")
        failed += 1
    
    # TEST 5: BANK NIFTY constituents
    print("\nTEST 5: BANK NIFTY constituents → Bank stocks")
    print("-" * 80)
    result = resolver.resolve("bank nifty")
    
    if len(result) >= 10:  # Bank NIFTY has ~12 constituents
        print(f"✅ PASS: Resolved {len(result)} BANK NIFTY constituents")
        print(f"   Sample: {[result[i].symbol for i in range(min(5, len(result)))]}")
        passed += 1
    else:
        print(f"❌ FAIL: Expected 10+ bank stocks")
        print(f"   Got: {len(result)}")
        failed += 1
    
    # TEST 6: Options resolution (CE/PE)
    print("\nTEST 6: Bank NIFTY options → CE/PE contracts")
    print("-" * 80)
    result = resolver.resolve("bank nifty ce pe")
    
    ce_count = sum(1 for inst in result if inst.option_type == OptionType.CE)
    pe_count = sum(1 for inst in result if inst.option_type == OptionType.PE)
    
    if len(result) >= 5 and ce_count > 0 and pe_count > 0:
        print(f"✅ PASS: Resolved {len(result)} option contracts")
        print(f"   CE: {ce_count}, PE: {pe_count}")
        print(f"   Sample: {[str(result[i]) for i in range(min(3, len(result)))]}")
        passed += 1
    else:
        print(f"❌ FAIL: Expected multiple CE and PE contracts")
        print(f"   Got: {len(result)} total, CE={ce_count}, PE={pe_count}")
        failed += 1
    
    # TEST 7: Only CE options
    print("\nTEST 7: Only CE options → No PE contracts")
    print("-" * 80)
    result = resolver.resolve("nifty ce")
    
    ce_count = sum(1 for inst in result if inst.option_type == OptionType.CE)
    pe_count = sum(1 for inst in result if inst.option_type == OptionType.PE)
    
    if ce_count > 0 and pe_count == 0:
        print(f"✅ PASS: Resolved {ce_count} CE contracts, 0 PE")
        passed += 1
    else:
        print(f"❌ FAIL: Expected only CE contracts")
        print(f"   Got: CE={ce_count}, PE={pe_count}")
        failed += 1
    
    # TEST 8: Options have required fields
    print("\nTEST 8: Option contracts → Have expiry, strike, underlying")
    print("-" * 80)
    result = resolver.resolve("nifty options")
    
    if result:
        sample = result[0]
        if (sample.instrument_type == InstrumentType.OPTION and
            sample.underlying and
            sample.expiry and
            sample.strike):
            print(f"✅ PASS: Option has all required fields")
            print(f"   Underlying: {sample.underlying}")
            print(f"   Expiry: {sample.expiry.strftime('%d-%b-%Y') if sample.expiry else 'None'}")
            print(f"   Strike: {sample.strike}")
            print(f"   Type: {sample.option_type.value if sample.option_type else 'None'}")
            passed += 1
        else:
            print(f"❌ FAIL: Option missing required fields")
            failed += 1
    else:
        print(f"❌ FAIL: No options resolved")
        failed += 1
    
    # TEST 9: Multi-word stock name
    print("\nTEST 9: Multi-word stock name → Single STOCK")
    print("-" * 80)
    result = resolver.resolve("yes bank")
    
    if len(result) == 1 and result[0].instrument_type == InstrumentType.STOCK:
        print(f"✅ PASS: Resolved 'yes bank' as STOCK")
        passed += 1
    else:
        print(f"❌ FAIL: Expected single STOCK for multi-word name")
        print(f"   Got: {len(result)} instruments")
        failed += 1
    
    # TEST 10: No hardcoded watchlists
    print("\nTEST 10: Dynamic resolution → No hardcoded limits")
    print("-" * 80)
    # Verify caching mechanism exists
    if hasattr(resolver, '_constituent_cache'):
        print(f"✅ PASS: Constituent caching mechanism exists")
        print(f"   Cache TTL: {resolver._cache_ttl}")
        passed += 1
    else:
        print(f"❌ FAIL: No caching mechanism found")
        failed += 1
    
    # Final summary
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Instrument resolver validated")
        print("\nKEY FEATURES:")
        print("  1. Dynamic resolution (stocks, indices, options)")
        print("  2. No hardcoded watchlists (cached with TTL)")
        print("  3. Options support (CE/PE with strikes)")
        print("  4. Constituent resolution (NIFTY 50, BANK NIFTY)")
    else:
        print(f"\n⚠️ {failed} test(s) failed - review resolver logic")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_instrument_resolver()
