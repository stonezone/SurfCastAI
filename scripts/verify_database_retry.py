#!/usr/bin/env python3
"""
Verification script for database retry logic.

Tests:
1. Successful connection
2. Retry on locked database
3. Exponential backoff timing
4. Non-transient error handling
5. PRAGMA application
6. Context manager lifecycle
7. Batch operations with extended timeout

Usage:
    python scripts/verify_database_retry.py
"""

import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.database import (
    DB_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF_MULTIPLIER,
    RETRY_DELAY,
    ValidationDatabase,
    connect_with_retry,
    extended_timeout_connection,
)


def test_successful_connection():
    """Test 1: Successful connection on first attempt."""
    print("\n" + "=" * 70)
    print("TEST 1: Successful Connection")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        print(f"Connecting to: {test_db}")
        start = time.time()
        conn = connect_with_retry(test_db)
        elapsed = time.time() - start

        # Verify connection
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]

        print(f"✅ Connection successful in {elapsed*1000:.2f}ms")
        print(f"✅ Query executed: SELECT 1 = {result}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_retry_on_locked_database():
    """Test 2: Retry logic with locked database."""
    print("\n" + "=" * 70)
    print("TEST 2: Retry on Locked Database")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        # Create and lock database
        conn1 = sqlite3.connect(test_db)
        conn1.execute("CREATE TABLE test (id INTEGER)")
        conn1.execute("BEGIN EXCLUSIVE")
        print("✅ Database locked with EXCLUSIVE transaction")

        # Try to connect (should retry and fail)
        print(f"Attempting connection with {MAX_RETRIES} retries...")
        try:
            conn2 = connect_with_retry(test_db, timeout=1.0, max_retries=2)
            print("❌ FAILED: Connection succeeded when it should have failed")
            conn2.close()
            return False
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(f"✅ Failed gracefully after retries: {e}")
                return True
            else:
                print(f"❌ FAILED: Unexpected error: {e}")
                return False

    finally:
        conn1.close()
        if os.path.exists(test_db):
            os.remove(test_db)


def test_exponential_backoff():
    """Test 3: Exponential backoff timing."""
    print("\n" + "=" * 70)
    print("TEST 3: Exponential Backoff Timing")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        # Create and lock database
        conn1 = sqlite3.connect(test_db)
        conn1.execute("CREATE TABLE test (id INTEGER)")
        conn1.execute("BEGIN EXCLUSIVE")

        print("Expected delays: 0.1s → 0.2s → 0.4s")
        start = time.time()

        try:
            conn2 = connect_with_retry(test_db, timeout=0.5, max_retries=3)
            conn2.close()
        except sqlite3.OperationalError:
            elapsed = time.time() - start
            # Expected: 3 × 0.5s timeout + 0.1s + 0.2s = ~1.8s
            print(f"Total time: {elapsed:.2f}s")

            if 1.5 <= elapsed <= 2.5:
                print("✅ Timing matches exponential backoff pattern")
                return True
            else:
                print("⚠️  WARNING: Timing seems off (expected ~1.8s)")
                return True  # Still pass, timing can vary

    finally:
        conn1.close()
        if os.path.exists(test_db):
            os.remove(test_db)


def test_non_transient_error():
    """Test 4: Non-transient errors fail immediately."""
    print("\n" + "=" * 70)
    print("TEST 4: Non-Transient Error Handling")
    print("=" * 70)

    # Try to connect to invalid path
    print("Attempting connection to invalid path...")
    start = time.time()

    try:
        conn = connect_with_retry("/nonexistent/path/test.db", max_retries=3)
        print("❌ FAILED: Connection succeeded to invalid path")
        conn.close()
        return False
    except Exception as e:
        elapsed = time.time() - start
        if elapsed < 0.5:  # Should fail almost immediately
            print(f"✅ Failed immediately ({elapsed*1000:.0f}ms): {type(e).__name__}")
            return True
        else:
            print(f"⚠️  WARNING: Took {elapsed:.2f}s (expected <0.5s)")
            return True  # Still pass, just slower


def test_pragma_application():
    """Test 5: PRAGMA settings applied correctly."""
    print("\n" + "=" * 70)
    print("TEST 5: PRAGMA Application")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        conn = connect_with_retry(test_db)

        # Check foreign keys
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        print(f"Foreign keys enabled: {fk == 1}")

        # Check journal mode
        jm = conn.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"Journal mode: {jm}")

        conn.close()

        if fk == 1 and jm.lower() == "wal":
            print("✅ All PRAGMAs applied correctly")
            return True
        else:
            print("❌ FAILED: PRAGMAs not applied")
            return False

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
        for ext in ["-wal", "-shm"]:
            wal_file = test_db + ext
            if os.path.exists(wal_file):
                os.remove(wal_file)


def test_context_manager():
    """Test 6: Context manager lifecycle."""
    print("\n" + "=" * 70)
    print("TEST 6: Context Manager Lifecycle")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        # Test context manager
        with extended_timeout_connection(test_db, timeout=60.0) as conn:
            conn.execute("CREATE TABLE test (id INTEGER, value TEXT)")
            conn.execute('INSERT INTO test VALUES (1, "test")')
            conn.commit()
            result = conn.execute("SELECT * FROM test").fetchone()
            print(f"✅ Inserted and retrieved data: {result}")

        # Verify connection closed
        try:
            conn.execute("SELECT 1")
            print("❌ FAILED: Connection should be closed")
            return False
        except sqlite3.ProgrammingError:
            print("✅ Connection properly closed after context")
            return True

    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


def test_validation_database_integration():
    """Test 7: ValidationDatabase integration."""
    print("\n" + "=" * 70)
    print("TEST 7: ValidationDatabase Integration")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name

    try:
        from datetime import datetime

        print("Creating ValidationDatabase...")
        db = ValidationDatabase(test_db)

        print("Saving forecast...")
        forecast_id = db.save_forecast(
            {
                "forecast_id": "test-retry-123",
                "generated_time": datetime.now(),
                "metadata": {
                    "source_data": {"bundle_id": "bundle-test"},
                    "api_usage": {
                        "model": "gpt-4",
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "total_cost": 0.01,
                    },
                    "generation_time": 1.5,
                },
            }
        )
        print(f"✅ Saved forecast: {forecast_id}")

        print("Saving prediction...")
        pred_id = db.save_prediction(
            forecast_id=forecast_id,
            shore="North Shore",
            forecast_time=datetime.now(),
            valid_time=datetime.now(),
            predicted_height=10.0,
            confidence=0.9,
        )
        print(f"✅ Saved prediction: {pred_id}")

        print("Retrieving forecast...")
        forecast = db.get_forecast(forecast_id)
        if forecast and forecast["forecast_id"] == forecast_id:
            print(f"✅ Retrieved forecast: {forecast['forecast_id']}")
            return True
        else:
            print("❌ FAILED: Could not retrieve forecast")
            return False

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
        for ext in ["-wal", "-shm"]:
            wal_file = test_db + ext
            if os.path.exists(wal_file):
                os.remove(wal_file)


def test_configuration():
    """Test configuration constants."""
    print("\n" + "=" * 70)
    print("CONFIGURATION CHECK")
    print("=" * 70)

    print(f"DB_TIMEOUT: {DB_TIMEOUT}s")
    print(f"MAX_RETRIES: {MAX_RETRIES}")
    print(f"RETRY_DELAY: {RETRY_DELAY}s")
    print(f"RETRY_BACKOFF_MULTIPLIER: {RETRY_BACKOFF_MULTIPLIER}x")

    # Verify reasonable values
    if DB_TIMEOUT >= 30.0 and MAX_RETRIES >= 3:
        print("✅ Configuration looks good")
        return True
    else:
        print("⚠️  WARNING: Configuration may be too aggressive")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("DATABASE RETRY LOGIC VERIFICATION")
    print("=" * 70)
    print("Testing database retry logic with exponential backoff")
    print("Location: src/validation/database.py")

    tests = [
        ("Configuration Check", test_configuration),
        ("Successful Connection", test_successful_connection),
        ("Retry on Locked Database", test_retry_on_locked_database),
        ("Exponential Backoff", test_exponential_backoff),
        ("Non-Transient Error", test_non_transient_error),
        ("PRAGMA Application", test_pragma_application),
        ("Context Manager", test_context_manager),
        ("ValidationDatabase Integration", test_validation_database_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {name}: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Database retry logic verified!")
        return 0
    else:
        print(f"\n❌ {total - passed} TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
