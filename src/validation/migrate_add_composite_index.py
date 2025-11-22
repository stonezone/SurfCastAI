"""Migration script to add composite index on (shore, valid_time).

This migration adds a composite index on predictions(shore, valid_time) to optimize
shore-specific time-range queries, which are common in validation feedback and
performance analysis workflows.

Query pattern optimized:
    SELECT * FROM predictions
    WHERE shore = 'North Shore'
      AND valid_time BETWEEN '2025-10-01 00:00:00' AND '2025-10-15 00:00:00'
    ORDER BY valid_time;

Performance improvement:
    Without composite index: Full table scan -> filter by shore -> filter by time -> sort
    With composite index: Direct index lookup -> results already sorted

Usage:
    python src/validation/migrate_add_composite_index.py
"""

import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def add_composite_index(db_path: str) -> None:
    """Add composite index on predictions(shore, valid_time).

    Args:
        db_path: Path to SQLite database file

    Raises:
        RuntimeError: If index creation fails
    """
    db_file = Path(db_path)
    if not db_file.exists():
        logger.error(f"Database file not found: {db_path}")
        sys.exit(1)

    logger.info(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Check if index already exists
        logger.info("Checking if composite index already exists...")
        result = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_predictions_shore_time'
        """
        ).fetchone()

        if result:
            logger.info("✓ Composite index 'idx_predictions_shore_time' already exists")
            logger.info("Migration not needed - skipping")
            return

        # Create composite index
        logger.info("Creating composite index on (shore, valid_time)...")
        conn.execute(
            """
            CREATE INDEX idx_predictions_shore_time
            ON predictions(shore, valid_time)
        """
        )
        conn.commit()
        logger.info("✓ Index creation committed")

        # Verify index was created
        logger.info("Verifying index creation...")
        result = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_predictions_shore_time'
        """
        ).fetchone()

        if result:
            logger.info("✓ Composite index 'idx_predictions_shore_time' created successfully")

            # Show all indexes on predictions table
            logger.info("\nAll indexes on predictions table:")
            indexes = conn.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type='index' AND tbl_name='predictions'
                ORDER BY name
            """
            ).fetchall()

            for idx_name, idx_sql in indexes:
                # Skip auto-generated indexes (sqlite_autoindex_*)
                if not idx_name.startswith("sqlite_"):
                    logger.info(f"  - {idx_name}")
                    if idx_sql:
                        logger.info(f"    {idx_sql}")
        else:
            raise RuntimeError("Index creation failed - index not found after creation")

    except Exception as e:
        conn.rollback()
        logger.error(f"✗ Failed to create composite index: {e}")
        raise
    finally:
        conn.close()
        logger.info("\nDatabase connection closed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Add composite index on predictions(shore, valid_time)"
    )
    parser.add_argument(
        "--db-path",
        default="data/validation.db",
        help="Path to validation database (default: data/validation.db)",
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Migration: Add Composite Index on predictions(shore, valid_time)")
    logger.info("=" * 70)

    try:
        add_composite_index(args.db_path)
        logger.info("\n" + "=" * 70)
        logger.info("Migration completed successfully!")
        logger.info("=" * 70)
    except Exception:
        logger.error("\n" + "=" * 70)
        logger.error("Migration failed!")
        logger.error("=" * 70)
        sys.exit(1)
