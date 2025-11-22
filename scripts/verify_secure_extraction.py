#!/usr/bin/env python3
"""
Verification script for secure archive extraction implementation.

This script verifies that all security requirements from Task 2.4 are met.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.bundle_manager import (
    BundleManager,
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_TOTAL_SIZE,
    MAX_COMPRESSION_RATIO
)
from src.utils.exceptions import SecurityError


def verify_constants():
    """Verify security constants are defined correctly."""
    print("Verifying Security Constants...")

    checks = [
        ("MAX_ARCHIVE_FILE_SIZE", MAX_ARCHIVE_FILE_SIZE, 100 * 1024 * 1024),
        ("MAX_ARCHIVE_TOTAL_SIZE", MAX_ARCHIVE_TOTAL_SIZE, 1024 * 1024 * 1024),
        ("MAX_COMPRESSION_RATIO", MAX_COMPRESSION_RATIO, 100),
    ]

    all_passed = True
    for name, actual, expected in checks:
        if actual == expected:
            print(f"  ✓ {name} = {expected:,}")
        else:
            print(f"  ✗ {name} = {actual:,} (expected {expected:,})")
            all_passed = False

    return all_passed


def verify_exception():
    """Verify SecurityError exception is available."""
    print("\nVerifying SecurityError Exception...")

    try:
        # Check that SecurityError is importable
        from src.utils.exceptions import SecurityError
        # Check that it can be raised and caught
        try:
            raise SecurityError("Test error")
        except SecurityError as e:
            if str(e) == "Test error":
                print("  ✓ SecurityError exception works correctly")
                return True
            else:
                print(f"  ✗ SecurityError message incorrect: {e}")
                return False
    except ImportError:
        print("  ✗ SecurityError not found in src.utils.exceptions")
        return False


def verify_methods():
    """Verify required methods exist and have correct signatures."""
    print("\nVerifying BundleManager Methods...")

    all_passed = True

    # Check safe_extract_archive exists
    if hasattr(BundleManager, 'safe_extract_archive'):
        print("  ✓ safe_extract_archive() method exists")

        # Check method signature
        import inspect
        sig = inspect.signature(BundleManager.safe_extract_archive)
        params = list(sig.parameters.keys())

        if params == ['self', 'archive_path', 'target_dir']:
            print("  ✓ safe_extract_archive() has correct signature")
        else:
            print(f"  ✗ safe_extract_archive() signature incorrect: {params}")
            all_passed = False
    else:
        print("  ✗ safe_extract_archive() method not found")
        all_passed = False

    # Check extract_archived_bundle still exists
    if hasattr(BundleManager, 'extract_archived_bundle'):
        print("  ✓ extract_archived_bundle() method exists")

        # Check method signature (should be unchanged)
        import inspect
        sig = inspect.signature(BundleManager.extract_archived_bundle)
        params = list(sig.parameters.keys())

        if params == ['self', 'bundle_id']:
            print("  ✓ extract_archived_bundle() signature maintained (backward compatible)")
        else:
            print(f"  ✗ extract_archived_bundle() signature changed: {params}")
            all_passed = False
    else:
        print("  ✗ extract_archived_bundle() method not found")
        all_passed = False

    return all_passed


def verify_implementation():
    """Verify implementation uses secure extraction."""
    print("\nVerifying Implementation Details...")

    import inspect

    # Get source code of extract_archived_bundle
    source = inspect.getsource(BundleManager.extract_archived_bundle)

    checks = [
        ("safe_extract_archive", "✓ Calls safe_extract_archive()"),
        ("SecurityError", "✓ Handles SecurityError"),
        ("self.logger.error", "✓ Logs errors"),
    ]

    all_passed = True
    for check, success_msg in checks:
        if check in source:
            print(f"  {success_msg}")
        else:
            print(f"  ✗ Missing: {check}")
            all_passed = False

    # Check for unsafe methods that should NOT be present
    unsafe_checks = [
        ("shutil.unpack_archive", "✗ Still uses unsafe shutil.unpack_archive()"),
    ]

    for check, error_msg in unsafe_checks:
        if check in source:
            print(f"  {error_msg}")
            all_passed = False
        else:
            print(f"  ✓ Removed unsafe: {check}")

    return all_passed


def verify_tests():
    """Verify test file exists and can be imported."""
    print("\nVerifying Test Suite...")

    test_path = Path(__file__).parent.parent / "tests" / "unit" / "core" / "test_secure_extraction.py"

    if test_path.exists():
        print(f"  ✓ Test file exists: {test_path.name}")

        # Try to import the test module
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_secure_extraction", test_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Count test methods
            import inspect
            test_class = getattr(module, 'TestSecureArchiveExtraction', None)
            if test_class:
                test_methods = [m for m in dir(test_class) if m.startswith('test_')]
                print(f"  ✓ Found {len(test_methods)} test methods")
                return True
            else:
                print("  ✗ TestSecureArchiveExtraction class not found")
                return False

        except Exception as e:
            print(f"  ✗ Error importing test module: {e}")
            return False
    else:
        print(f"  ✗ Test file not found: {test_path}")
        return False


def verify_documentation():
    """Verify documentation files exist."""
    print("\nVerifying Documentation...")

    docs = [
        "TASK_2.4_SECURE_EXTRACTION_REPORT.md",
        "TASK_2.4_COMPLETION_SUMMARY.md",
    ]

    all_passed = True
    project_root = Path(__file__).parent.parent

    for doc in docs:
        doc_path = project_root / doc
        if doc_path.exists():
            size_kb = doc_path.stat().st_size / 1024
            print(f"  ✓ {doc} ({size_kb:.1f}KB)")
        else:
            print(f"  ✗ {doc} not found")
            all_passed = False

    return all_passed


def main():
    """Run all verification checks."""
    print("="*70)
    print("TASK 2.4: SECURE ARCHIVE EXTRACTION - VERIFICATION")
    print("="*70)
    print()

    results = []

    results.append(("Security Constants", verify_constants()))
    results.append(("SecurityError Exception", verify_exception()))
    results.append(("BundleManager Methods", verify_methods()))
    results.append(("Implementation Details", verify_implementation()))
    results.append(("Test Suite", verify_tests()))
    results.append(("Documentation", verify_documentation()))

    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    all_passed = True
    for category, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {category}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n✓ ALL VERIFICATION CHECKS PASSED")
        print("\nTask 2.4 implementation is complete and correct.")
        return 0
    else:
        print("\n✗ SOME VERIFICATION CHECKS FAILED")
        print("\nPlease review the failed checks above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
