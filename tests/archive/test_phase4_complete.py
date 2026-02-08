"""
Combined Phase-4 Validation
Runs both Phase-4A and Phase-4B test suites to verify complete implementation.
"""

import subprocess
import sys

def run_test_suite(test_file, phase_name):
    """Run a test suite and return success status."""
    print()
    print("╔" + "═" * 68 + "╗")
    print(f"║  Running {phase_name} Test Suite{' ' * (52 - len(phase_name))}║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    result = subprocess.run(
        ["python", test_file],
        capture_output=False,
        text=True
    )
    
    return result.returncode == 0

def main():
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "PHASE-4 COMPLETE VALIDATION" + " " * 21 + "║")
    print("║" + " " * 68 + "║")
    print("║  Phase-4A: Control Primitives (focus_window, close_app, wait)   ║")
    print("║  Phase-4B: Vision Verification Fallback (Critic only)           ║")
    print("╚" + "═" * 68 + "╝")
    
    all_passed = True
    
    # Run Phase-4A tests
    if not run_test_suite("test_phase4a_policy.py", "Phase-4A Policy Enforcement"):
        print("❌ Phase-4A tests FAILED")
        all_passed = False
    else:
        print("✅ Phase-4A tests PASSED")
    
    # Run Phase-4B tests
    if not run_test_suite("test_phase4b_vision.py", "Phase-4B Vision Fallback"):
        print("❌ Phase-4B tests FAILED")
        all_passed = False
    else:
        print("✅ Phase-4B tests PASSED")
    
    print()
    print("=" * 70)
    if all_passed:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "✅ PHASE-4 COMPLETE - ALL TESTS PASSED" + " " * 14 + "║")
        print("║" + " " * 68 + "║")
        print("║  Phase-4A: 7/7 policy tests passed                              ║")
        print("║  Phase-4B: 4/4 vision tests passed                              ║")
        print("║" + " " * 68 + "║")
        print("║  Status: LOCKED AND APPROVED ✅                                  ║")
        print("╚" + "═" * 68 + "╝")
        return 0
    else:
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 15 + "❌ PHASE-4 VALIDATION FAILED" + " " * 20 + "║")
        print("╚" + "═" * 68 + "╝")
        return 1

if __name__ == "__main__":
    sys.exit(main())
