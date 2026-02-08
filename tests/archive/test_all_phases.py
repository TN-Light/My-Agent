"""
Complete Validation Script
Runs all phase tests to verify no regressions.

Phases:
- Phase-4A: Control primitives with policy enforcement
- Phase-4B: Vision verification fallback (Critic only)
- Phase-5A: Plan graph with preview and approval
- Phase-5B: Plan persistence and audit trail
- Phase-6A: Step-level approval gates
- Phase-6B: Post-execution debug reporting
- Phase-7A: Deterministic plan replay
- Phase-7B: Execution plan comparison
- Phase-8A: Recommendation Engine
- Phase-9A: Plan Repair Engine
"""

import sys
import subprocess
from pathlib import Path


def run_test_suite(name: str, script: str) -> bool:
    """Run a test suite and report results."""
    print(f"\n{'='*70}")
    print(f"Running {name}...")
    print(f"{'='*70}")
    
    result = subprocess.run([sys.executable, script], capture_output=False)
    
    if result.returncode == 0:
        print(f"\n✅ {name} PASSED")
        return True
    else:
        print(f"\n❌ {name} FAILED")
        return False


def main():
    """Run all test suites."""
    print("╔" + "="*68 + "╗")
    print("║" + " "*12 + "COMPLETE VALIDATION - ALL PHASES" + " "*23 + "║")
    print("╚" + "="*68 + "╝")
    
    results = {}
    
    # Phase-4 (4A + 4B combined)
    results["Phase-4 (4A+4B)"] = run_test_suite(
        "Phase-4 Complete Tests",
        "test_phase4_complete.py"
    )
    
    # Phase-5A
    results["Phase-5A"] = run_test_suite(
        "Phase-5A Plan Graph Tests",
        "test_phase5a_plan_graph.py"
    )
    
    # Phase-5B
    results["Phase-5B"] = run_test_suite(
        "Phase-5B Persistence Tests",
        "test_phase5b_persistence.py"
    )
    
    # Phase-6A
    results["Phase-6A"] = run_test_suite(
        "Phase-6A Step Approval Tests",
        "test_phase6a_step_approval.py"
    )
    
    # Phase-6B
    results["Phase-6B"] = run_test_suite(
        "Phase-6B Debug Reporting Tests",
        "test_phase6b_debug_report.py"
    )
    
    # Phase-7A
    results["Phase-7A"] = run_test_suite(
        "Phase-7A Plan Replay Tests",
        "test_phase7a_replay.py"
    )

    # Phase-7B
    results["Phase-7B"] = run_test_suite(
        "Phase-7B Execution Diff Tests",
        "test_phase7b_execution_diff.py"
    )

    # Phase-8A
    results["Phase-8A"] = run_test_suite(
        "Phase-8A Recommendation Engine Tests",
        "test_phase8a_recommendations.py"
    )

    # Phase-9A
    results["Phase-9A"] = run_test_suite(
        "Phase-9A Plan Repair Tests",
        "test_phase9a_plan_repair.py"
    )

    # Phase-9B
    results["Phase-9B"] = run_test_suite(
        "Phase-9B Interactive Repair Tests",
        "test_phase9b_interactive_repair.py"
    )
    
    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    
    total = len(results)
    passed = sum(1 for success in results.values() if success)
    
    for phase, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {phase}")
    
    print("="*70)
    print(f"Total: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n✅ ALL VALIDATION TESTS PASSED")
        print("="*70)
        return 0
    else:
        print(f"\n❌ {total - passed} test suite(s) failed")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
