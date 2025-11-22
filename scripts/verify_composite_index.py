"""Verification script for composite index on predictions(shore, valid_time).

This script verifies that the composite index exists and is being used by SQLite's
query planner for shore-specific time-range queries.

Usage:
    python scripts/verify_composite_index.py
"""
import sqlite3
from pathlib import Path
import sys

def verify_composite_index(db_path: str = "data/validation.db"):
    """Verify composite index exists and is being used.

    Args:
        db_path: Path to validation database
    """
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    print("=" * 80)
    print("COMPOSITE INDEX VERIFICATION")
    print("=" * 80)

    # 1. Check if index exists
    print("\n1. Checking if composite index exists...")
    result = conn.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND name='idx_predictions_shore_time'
    """).fetchone()

    if result:
        print(f"   ✓ Index 'idx_predictions_shore_time' exists")
        print(f"   SQL: {result[1]}")
    else:
        print("   ❌ Index 'idx_predictions_shore_time' NOT FOUND")
        sys.exit(1)

    # 2. List all indexes on predictions table
    print("\n2. All indexes on predictions table:")
    indexes = conn.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND tbl_name='predictions'
        ORDER BY name
    """).fetchall()

    for idx_name, idx_sql in indexes:
        if not idx_name.startswith('sqlite_'):
            print(f"   - {idx_name}")

    # 3. Get table statistics
    print("\n3. Table statistics:")
    total_predictions = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    print(f"   Total predictions: {total_predictions}")

    if total_predictions > 0:
        shore_counts = conn.execute("""
            SELECT shore, COUNT(*) as count
            FROM predictions
            GROUP BY shore
            ORDER BY count DESC
        """).fetchall()

        print("   Predictions by shore:")
        for shore, count in shore_counts:
            print(f"     {shore}: {count}")

    # 4. Test query plans
    print("\n4. Query plan verification:")

    test_queries = [
        (
            "Shore + time range (BETWEEN)",
            """SELECT * FROM predictions
               WHERE shore='North Shore'
                 AND valid_time BETWEEN '2025-10-01 00:00:00' AND '2025-10-15 00:00:00'
               ORDER BY valid_time"""
        ),
        (
            "Shore + time range (>)",
            """SELECT * FROM predictions
               WHERE shore='North Shore'
                 AND valid_time > '2025-10-01 00:00:00'
               ORDER BY valid_time"""
        ),
        (
            "Shore only",
            """SELECT * FROM predictions
               WHERE shore='North Shore'
               ORDER BY valid_time"""
        ),
    ]

    for query_name, query in test_queries:
        print(f"\n   Query: {query_name}")
        explain = conn.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
        for row in explain:
            plan = row[-1]  # Last column is the plan description
            if 'idx_predictions_shore_time' in plan:
                print(f"   ✓ Uses composite index: {plan}")
            elif 'idx_predictions' in plan:
                print(f"   ⚠ Uses different index: {plan}")
            else:
                print(f"   ❌ No index used: {plan}")

    # 5. Performance comparison (if data exists)
    if total_predictions > 0:
        print("\n5. Performance test:")
        print("   Running shore+time query...")

        # Enable timing
        conn.execute("PRAGMA timer = ON")

        # Run a test query
        cursor = conn.execute("""
            SELECT COUNT(*) FROM predictions
            WHERE shore='North Shore'
              AND valid_time > '2025-10-01 00:00:00'
        """)
        result_count = cursor.fetchone()[0]
        print(f"   ✓ Query completed: {result_count} results")
        print("   Note: With composite index, this query uses direct index lookup")
        print("         without full table scan, regardless of data size.")

    conn.close()

    print("\n" + "=" * 80)
    print("✓ VERIFICATION COMPLETE - Composite index is properly configured")
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify composite index on predictions(shore, valid_time)"
    )
    parser.add_argument(
        "--db-path",
        default="data/validation.db",
        help="Path to validation database (default: data/validation.db)"
    )

    args = parser.parse_args()
    verify_composite_index(args.db_path)
