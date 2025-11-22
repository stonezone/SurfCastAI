"""Migration script to convert timestamps to ISO 8601 format.

This script migrates the validation database from mixed timestamp formats
(Unix epoch floats and ISO 8601 strings with 'T' separator) to a standardized
ISO 8601 format (YYYY-MM-DD HH:MM:SS).

Run this script once to migrate existing data before deploying the new schema.
"""
import sqlite3
import sys
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'


def backup_database(db_path: Path) -> Path:
    """Create a backup of the database before migration.

    Args:
        db_path: Path to the database file

    Returns:
        Path to the backup file
    """
    backup_path = db_path.with_suffix('.db.backup')
    import shutil
    shutil.copy2(db_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    return backup_path


def convert_timestamp(value: str) -> str:
    """Convert various timestamp formats to ISO 8601 standard.

    Args:
        value: Timestamp value (Unix epoch float or ISO 8601 string)

    Returns:
        ISO 8601 formatted string (YYYY-MM-DD HH:MM:SS)
    """
    if not value:
        return value

    # Try parsing as Unix timestamp first
    try:
        timestamp_float = float(value)
        if timestamp_float > 1000000000:  # Likely a Unix timestamp
            dt = datetime.fromtimestamp(timestamp_float)
            return dt.strftime(TIMESTAMP_FORMAT)
    except (ValueError, TypeError):
        pass

    # Try parsing as ISO 8601 string (with T, Z, or microseconds)
    try:
        # Remove T separator, Z suffix, and microseconds
        clean_str = str(value).replace('T', ' ').replace('Z', '').split('.')[0]

        # Check if already in correct format
        dt = datetime.strptime(clean_str, TIMESTAMP_FORMAT)
        return dt.strftime(TIMESTAMP_FORMAT)
    except ValueError:
        logger.warning(f"Could not parse timestamp: {value}")
        return value


def migrate_table(conn: sqlite3.Connection, table: str, columns: list) -> int:
    """Migrate timestamp columns in a table.

    Args:
        conn: Database connection
        table: Table name
        columns: List of timestamp column names

    Returns:
        Number of rows updated
    """
    cursor = conn.cursor()

    # Get all rows
    cursor.execute(f"SELECT id, {', '.join(columns)} FROM {table}")
    rows = cursor.fetchall()

    if not rows:
        logger.info(f"Table {table}: No rows to migrate")
        return 0

    updated = 0
    for row in rows:
        row_id = row[0]
        old_values = row[1:]
        new_values = [convert_timestamp(val) for val in old_values]

        # Check if any values changed
        if old_values != tuple(new_values):
            # Build UPDATE query
            set_clause = ', '.join([f"{col} = ?" for col in columns])
            query = f"UPDATE {table} SET {set_clause} WHERE id = ?"
            cursor.execute(query, (*new_values, row_id))
            updated += 1

    logger.info(f"Table {table}: Updated {updated}/{len(rows)} rows")
    return updated


def verify_format(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Verify that all timestamps in a column are in correct format.

    Args:
        conn: Database connection
        table: Table name
        column: Column name

    Returns:
        True if all timestamps are valid, False otherwise
    """
    cursor = conn.cursor()
    cursor.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL LIMIT 100")

    for row in cursor.fetchall():
        value = row[0]
        try:
            # Should be parseable as ISO 8601 without T or Z
            datetime.strptime(value, TIMESTAMP_FORMAT)
        except ValueError:
            logger.error(f"Invalid timestamp format in {table}.{column}: {value}")
            return False

    logger.info(f"Verified format for {table}.{column}")
    return True


def migrate_database(db_path: str, skip_backup: bool = False) -> bool:
    """Migrate validation database to ISO 8601 timestamp format.

    Args:
        db_path: Path to the database file
        skip_backup: Skip creating backup (for testing)

    Returns:
        True if migration successful, False otherwise
    """
    db_path = Path(db_path)

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return False

    # Create backup unless skipped
    if not skip_backup:
        backup_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")  # Disable during migration

    try:
        # Migrate each table with timestamp columns
        tables_to_migrate = {
            'forecasts': ['created_at'],
            'predictions': ['forecast_time', 'valid_time'],
            'actuals': ['observation_time'],
            'validations': ['validated_at']
        }

        total_updated = 0
        for table, columns in tables_to_migrate.items():
            updated = migrate_table(conn, table, columns)
            total_updated += updated

        # Verify all timestamps are in correct format
        logger.info("Verifying timestamp formats...")
        all_valid = True
        for table, columns in tables_to_migrate.items():
            for column in columns:
                if not verify_format(conn, table, column):
                    all_valid = False

        if all_valid:
            conn.commit()
            logger.info(f"Migration complete! Updated {total_updated} total rows")
            logger.info("All timestamps verified to be in ISO 8601 format (YYYY-MM-DD HH:MM:SS)")
            return True
        else:
            conn.rollback()
            logger.error("Migration verification failed, rolled back changes")
            return False

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate validation database timestamps to ISO 8601 format"
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/validation.db',
        help='Path to validation database (default: data/validation.db)'
    )
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Skip creating backup (for testing only)'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Validation Database Timestamp Migration")
    logger.info("=" * 60)
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Target format: ISO 8601 (YYYY-MM-DD HH:MM:SS)")
    logger.info("")

    if migrate_database(args.db_path, skip_backup=args.skip_backup):
        logger.info("Migration successful!")
        sys.exit(0)
    else:
        logger.error("Migration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
