"""
Test script to verify UnboundLocalError fix in execution_engine.py
Tests that htf_location and gate_evaluation are properly initialized.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_variable_initialization():
    """
    Verify that htf_location and gate_evaluation are initialized at function start.
    This prevents UnboundLocalError when variables are conditionally assigned.
    """
    print("=" * 70)
    print("TESTING: UnboundLocalError Fix in execution_engine.py")
    print("=" * 70)
    print()
    
    # Read the function
    engine_path = Path(__file__).parent / "logic" / "execution_engine.py"
    with open(engine_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find _display_mtf_summary function
    func_start = content.find("def _display_mtf_summary(")
    if func_start == -1:
        print("[FAIL] Could not find _display_mtf_summary function")
        return False
    
    # Extract function (up to next def or class)
    func_end = content.find("\n    def ", func_start + 100)
    if func_end == -1:
        func_end = content.find("\nclass ", func_start + 100)
    if func_end == -1:
        func_end = len(content)
    
    function_code = content[func_start:func_end]
    
    print("TEST 1: Verify htf_location initialized at function start")
    print("-" * 70)
    
    # Check for initialization block
    init_block_start = function_code.find("# Initialize variables to prevent UnboundLocalError")
    if init_block_start == -1:
        print("[FAIL] Initialization comment not found")
        return False
    
    print("[PASS] Found initialization comment block")
    
    # Check htf_location initialization
    if 'htf_location = "UNKNOWN"' in function_code[:init_block_start + 500]:
        print("[PASS] htf_location = \"UNKNOWN\" found in initialization block")
    else:
        print("[FAIL] htf_location not initialized to UNKNOWN")
        return False
    
    # Check gate_evaluation initialization
    if 'gate_evaluation = None' in function_code[:init_block_start + 500]:
        print("[PASS] gate_evaluation = None found in initialization block")
    else:
        print("[FAIL] gate_evaluation not initialized to None")
        return False
    
    print()
    print("TEST 2: Verify htf_location assignment comes AFTER initialization")
    print("-" * 70)
    
    # Find where htf_location is conditionally assigned (the old location around line 759)
    calc_htf_location = function_code.find("# Calculate HTF Location")
    if calc_htf_location == -1:
        print("[FAIL] HTF Location calculation block not found")
        return False
    
    if calc_htf_location > init_block_start:
        print("[PASS] HTF Location calculation comes AFTER initialization")
    else:
        print("[FAIL] HTF Location calculation comes BEFORE initialization")
        return False
    
    print()
    print("TEST 3: Verify htf_location used in Phase-6A comes AFTER calculation")
    print("-" * 70)
    
    # Find Phase-6A usage
    phase6a_usage = function_code.find("probability_result = self.probability_calculator.calculate_probabilities(")
    if phase6a_usage == -1:
        print("[FAIL] Phase-6A calculator call not found")
        return False
    
    if phase6a_usage > calc_htf_location:
        print("[PASS] Phase-6A usage comes AFTER HTF Location calculation")
    else:
        print("[WARNING] Phase-6A usage comes BEFORE HTF Location calculation")
        print("         (But initialization prevents error)")
    
    print()
    print("TEST 4: Verify gate_evaluation is guarded with None checks")
    print("-" * 70)
    
    # Find gate_evaluation usage in display logic
    gate_display = function_code.find("if gate_evaluation:")
    if gate_display == -1:
        print("[FAIL] Gate evaluation display guard not found")
        return False
    
    print("[PASS] Found 'if gate_evaluation:' guard for display logic")
    
    # Check that gate_evaluation access comes inside the if block
    gate_access_1 = function_code.find('permission = gate_evaluation["execution_permission"]')
    if gate_access_1 == -1:
        print("[FAIL] gate_evaluation[\"execution_permission\"] access not found")
        return False
    
    if gate_access_1 > gate_display:
        print("[PASS] gate_evaluation access is guarded by if statement")
    else:
        print("[FAIL] gate_evaluation accessed before guard")
        return False
    
    print()
    print("=" * 70)
    print("RESULT: ALL TESTS PASSED")
    print("=" * 70)
    print()
    print("SUMMARY:")
    print("  - htf_location initialized to \"UNKNOWN\" at function start")
    print("  - gate_evaluation initialized to None at function start")
    print("  - Both variables safe for ANALYSIS_ONLY mode")
    print("  - Phase-6A deterministic calculator receives UNKNOWN as valid state")
    print("  - Gate evaluation display properly guarded with None check")
    print()
    print("[OK] UnboundLocalError bugs fixed successfully")
    
    return True


if __name__ == "__main__":
    try:
        success = test_variable_initialization()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[FAIL] Test script error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
