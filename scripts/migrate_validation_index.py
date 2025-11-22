#!/usr/bin/env python3
"""Migration script: Add idx_validations_validated_at index to validation.db.

This index is critical for performance of adaptive prompt injection queries.
Without it, time-windowed queries perform full table scans (~500ms @ 10K validations).
With it, queries complete in <50ms.

Usage:
    python scripts/migrate_validation_index.py
    python scripts/migrate_validation_index.py --db-path data/validation.db --verify

See: docs/ADAPTIVE_PERFORMANCE_QUERIES.md for full design documentation
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path


def check_index_exists(db_path: Path, index_name: str) -> bool:
    """Check if index already exists.

    Args:
        db_path: Path to SQLite database
        index_name: Name of index to check

    Returns:
        True if index exists, False otherwise
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND name=?
        """,
            (index_name,),
        )
        return cursor.fetchone() is not None


def get_table_stats(db_path: Path) -> dict:
    """Get validation table statistics.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dict with row_count and table_size_bytes
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Row count
        cursor.execute("SELECT COUNT(*) FROM validations")
        row_count = cursor.fetchone()[0]

        # Table size (approximate via page count)
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        db_size_bytes = page_count * page_size

        return {
            "row_count": row_count,
            "db_size_bytes": db_size_bytes,
            "db_size_mb": round(db_size_bytes / 1024 / 1024, 2),
        }


def benchmark_query(db_path: Path, with_index: bool = False) -> float:
    """Benchmark performance query with/without index.

    Args:
        db_path: Path to SQLite database
        with_index: Whether to expect index usage

    Returns:
        Query execution time in milliseconds
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Warm up cache
        cursor.execute("SELECT COUNT(*) FROM validations")

        # Benchmark time-windowed query (typical for adaptive prompts)
        start = time.time()
        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                AVG(mae) as avg_mae,
                AVG(rmse) as avg_rmse
            FROM validations
            WHERE validated_at >= datetime('now', '-7 days')
        """
        )
        cursor.fetchone()
        elapsed_ms = (time.time() - start) * 1000

        # Verify query plan
        cursor.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT COUNT(*) FROM validations
            WHERE validated_at >= datetime('now', '-7 days')
        """
        )
        query_plan = cursor.fetchall()

        using_index = any("idx_validations_validated_at" in str(row) for row in query_plan)

        return elapsed_ms, using_index


def migrate(db_path: Path, verify: bool = False) -> bool:
    """Apply migration: Add idx_validations_validated_at index.

    Args:
        db_path: Path to SQLite database
        verify: If True, run benchmarks before/after

    Returns:
        True if migration successful, False otherwise
    """
    index_name = "idx_validations_validated_at"

    # Check if database exists
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("   No action needed - index will be created on first database initialization")
        return False

    print(f"🔍 Analyzing validation database: {db_path}")

    # Get table statistics
    stats = get_table_stats(db_path)
    print(f"   Validations: {stats['row_count']} rows")
    print(f"   Database size: {stats['db_size_mb']} MB")

    # Check if index already exists
    if check_index_exists(db_path, index_name):
        print(f"✅ Index '{index_name}' already exists - no migration needed")

        if verify and stats["row_count"] > 0:
            print("\n🔬 Running verification benchmark...")
            elapsed_ms, using_index = benchmark_query(db_path, with_index=True)
            print(f"   Query time: {elapsed_ms:.2f}ms")
            if using_index:
                print(f"   ✅ Query optimizer is using {index_name}")
            else:
                print(f"   ⚠️  Query optimizer NOT using {index_name} (table scan)")
                print("   This may indicate outdated statistics - try: ANALYZE validations;")

        return True

    # Run pre-migration benchmark
    if verify and stats["row_count"] > 0:
        print("\n🔬 Running pre-migration benchmark (without index)...")
        pre_elapsed_ms, _ = benchmark_query(db_path, with_index=False)
        print(f"   Query time: {pre_elapsed_ms:.2f}ms (full table scan)")

    # Apply migration
    print(f"\n🔨 Creating index: {index_name}")
    try:
        with sqlite3.connect(db_path) as conn:
            start = time.time()
            conn.execute(f"CREATE INDEX {index_name} ON validations(validated_at)")
            elapsed_ms = (time.time() - start) * 1000
            print(f"   ✅ Index created successfully in {elapsed_ms:.2f}ms")

    except sqlite3.Error as e:
        print(f"   ❌ Index creation failed: {e}")
        return False

    # Run post-migration benchmark
    if verify and stats["row_count"] > 0:
        print("\n🔬 Running post-migration benchmark (with index)...")
        post_elapsed_ms, using_index = benchmark_query(db_path, with_index=True)
        print(f"   Query time: {post_elapsed_ms:.2f}ms")

        if using_index:
            print(f"   ✅ Query optimizer is using {index_name}")
            speedup = pre_elapsed_ms / post_elapsed_ms
            print(
                f"   📈 Speedup: {speedup:.1f}x faster ({pre_elapsed_ms:.2f}ms → {post_elapsed_ms:.2f}ms)"
            )
        else:
            print(f"   ⚠️  Query optimizer NOT using {index_name}")
            print("   This may resolve after ANALYZE - running now...")
            with sqlite3.connect(db_path) as conn:
                conn.execute("ANALYZE validations")
            print("   ✅ Statistics updated")

    # Final verification
    print("\n✅ Migration complete!")
    print(f"   Index '{index_name}' is ready for adaptive prompt injection queries")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Add performance index to validation.db for adaptive prompt injection"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/validation.db"),
        help="Path to validation database (default: data/validation.db)",
    )
    parser.add_argument(
        "--verify", action="store_true", help="Run benchmarks to verify performance improvement"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("SurfCastAI Validation Database Migration")
    print("Adding idx_validations_validated_at index")
    print("=" * 70)

    success = migrate(args.db_path, verify=args.verify)

    print("\n" + "=" * 70)
    if success:
        print("Migration completed successfully!")
        print("\nNext steps:")
        print(
            "1. Test performance queries: python -c 'from src.validation.performance import get_recent_performance; print(get_recent_performance())'"
        )
        print("2. Review design doc: docs/ADAPTIVE_PERFORMANCE_QUERIES.md")
        print("3. Integrate with ForecastEngine (see doc Section 7)")
    else:
        print("Migration completed with warnings (see above)")
        print("\nIf database does not exist yet, it will be created with the index")
        print("automatically on first use via schema.sql")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
