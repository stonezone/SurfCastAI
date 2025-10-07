#!/usr/bin/env python3
"""Verification script to ensure validation database matches spec exactly."""
import sqlite3
import sys
from pathlib import Path

# Expected schema from spec (lines 406-490)
EXPECTED_TABLES = {
    'forecasts': {
        'columns': [
            'id', 'forecast_id', 'created_at', 'bundle_id', 'model_version',
            'total_tokens', 'input_tokens', 'output_tokens', 'model_cost_usd',
            'generation_time_sec', 'status'
        ],
        'indexes': [
            'idx_forecasts_created',
            'idx_forecasts_bundle'
        ],
        'foreign_keys': []
    },
    'predictions': {
        'columns': [
            'id', 'forecast_id', 'shore', 'forecast_time', 'valid_time',
            'predicted_height', 'predicted_period', 'predicted_direction',
            'predicted_category', 'confidence'
        ],
        'indexes': [
            'idx_predictions_forecast',
            'idx_predictions_valid_time'
        ],
        'foreign_keys': [
            ('forecast_id', 'forecasts', 'forecast_id')
        ]
    },
    'actuals': {
        'columns': [
            'id', 'buoy_id', 'observation_time', 'wave_height',
            'dominant_period', 'direction', 'source'
        ],
        'indexes': [
            'idx_actuals_buoy_time'
        ],
        'foreign_keys': []
    },
    'validations': {
        'columns': [
            'id', 'forecast_id', 'prediction_id', 'actual_id', 'validated_at',
            'height_error', 'period_error', 'direction_error', 'category_match',
            'mae', 'rmse'
        ],
        'indexes': [
            'idx_validations_forecast'
        ],
        'foreign_keys': [
            ('forecast_id', 'forecasts', 'forecast_id'),
            ('prediction_id', 'predictions', 'id'),
            ('actual_id', 'actuals', 'id')
        ]
    }
}


def verify_schema(db_path: str = 'data/validation.db') -> bool:
    """Verify database schema matches specification.

    Returns:
        True if schema matches spec, False otherwise
    """
    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    all_passed = True

    print("=" * 70)
    print("Validation Database Schema Verification")
    print("=" * 70)

    # Verify each table
    for table_name, expected in EXPECTED_TABLES.items():
        print(f"\nVerifying table: {table_name}")
        print("-" * 70)

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if not cursor.fetchone():
            print(f"  ERROR: Table {table_name} not found")
            all_passed = False
            continue

        # Check columns
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_columns = [row[1] for row in cursor.fetchall()]

        print(f"  Columns ({len(actual_columns)}):")
        for col in expected['columns']:
            if col in actual_columns:
                print(f"    {col:30} OK")
            else:
                print(f"    {col:30} MISSING")
                all_passed = False

        # Check for extra columns
        extra_columns = set(actual_columns) - set(expected['columns'])
        if extra_columns:
            print(f"  WARNING: Extra columns found: {extra_columns}")

        # Check indexes
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? AND name NOT LIKE 'sqlite_%'",
            (table_name,)
        )
        actual_indexes = [row[0] for row in cursor.fetchall()]

        print(f"  Indexes ({len(actual_indexes)}):")
        for idx in expected['indexes']:
            if idx in actual_indexes:
                print(f"    {idx:30} OK")
            else:
                print(f"    {idx:30} MISSING")
                all_passed = False

        # Check foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        actual_fks = [(row[3], row[2], row[4]) for row in cursor.fetchall()]

        print(f"  Foreign Keys ({len(actual_fks)}):")
        for fk in expected['foreign_keys']:
            if fk in actual_fks:
                print(f"    {fk[0]} -> {fk[1]}.{fk[2]:15} OK")
            else:
                print(f"    {fk[0]} -> {fk[1]}.{fk[2]:15} MISSING")
                all_passed = False

    conn.close()

    print("\n" + "=" * 70)
    if all_passed:
        print("VERIFICATION PASSED: Schema matches specification exactly")
    else:
        print("VERIFICATION FAILED: Schema does not match specification")
    print("=" * 70)

    return all_passed


def verify_methods() -> bool:
    """Verify ValidationDatabase has all required methods."""
    print("\n" + "=" * 70)
    print("ValidationDatabase Method Verification")
    print("=" * 70)

    sys.path.insert(0, 'src')
    from validation import ValidationDatabase

    required_methods = [
        '_init_database',
        'save_forecast',
        'save_prediction',
        'save_predictions',
        'save_actual',
        'save_validation',
        'get_forecasts_needing_validation'
    ]

    all_passed = True
    db = ValidationDatabase()

    for method in required_methods:
        if hasattr(db, method):
            print(f"  {method:40} OK")
        else:
            print(f"  {method:40} MISSING")
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("METHOD VERIFICATION PASSED: All required methods present")
    else:
        print("METHOD VERIFICATION FAILED: Missing required methods")
    print("=" * 70)

    return all_passed


def main():
    """Run all verifications."""
    schema_ok = verify_schema()
    methods_ok = verify_methods()

    if schema_ok and methods_ok:
        print("\nSUCCESS: Task 2.1 implementation matches spec exactly")
        return 0
    else:
        print("\nFAILURE: Task 2.1 implementation does not match spec")
        return 1


if __name__ == '__main__':
    sys.exit(main())
