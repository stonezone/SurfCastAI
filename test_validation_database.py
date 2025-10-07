#!/usr/bin/env python3
"""Test script for validation database functionality."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, 'src')
from validation import ValidationDatabase


def test_database_initialization():
    """Test database initialization."""
    print("Testing database initialization...")
    db = ValidationDatabase(db_path="data/test_validation.db")
    assert db.db_path.exists(), "Database file not created"
    print("  PASS: Database initialized\n")
    return db


def test_save_forecast(db):
    """Test saving forecast metadata."""
    print("Testing save_forecast...")

    forecast_data = {
        'forecast_id': 'test-forecast-001',
        'generated_time': datetime.now().isoformat(),
        'metadata': {
            'source_data': {
                'bundle_id': 'test-bundle-123'
            },
            'api_usage': {
                'model': 'gpt-5-mini',
                'input_tokens': 5000,
                'output_tokens': 1000,
                'total_cost': 0.042
            },
            'generation_time': 12.5
        }
    }

    forecast_id = db.save_forecast(forecast_data)
    assert forecast_id == 'test-forecast-001', "Forecast ID mismatch"
    print("  PASS: Forecast saved\n")
    return forecast_id


def test_save_predictions(db, forecast_id):
    """Test saving predictions."""
    print("Testing save_predictions...")

    now = datetime.now()
    predictions = [
        {
            'shore': 'North Shore',
            'forecast_time': now,
            'valid_time': now + timedelta(hours=24),
            'height': 8.5,
            'period': 14.0,
            'direction': 'NW',
            'category': 'moderate',
            'confidence': 0.85
        },
        {
            'shore': 'South Shore',
            'forecast_time': now,
            'valid_time': now + timedelta(hours=24),
            'height': 3.2,
            'period': 12.0,
            'direction': 'S',
            'category': 'small',
            'confidence': 0.75
        }
    ]

    db.save_predictions(forecast_id, predictions)
    print("  PASS: Predictions saved\n")


def test_save_actual(db):
    """Test saving actual observations."""
    print("Testing save_actual...")

    actual_id = db.save_actual(
        buoy_id='51201',
        observation_time=datetime.now(),
        wave_height=8.2,
        dominant_period=13.5,
        direction=315.0,
        source='NDBC'
    )
    assert actual_id > 0, "Actual ID not returned"
    print("  PASS: Actual observation saved\n")
    return actual_id


def test_save_validation(db, forecast_id, actual_id):
    """Test saving validation result."""
    print("Testing save_validation...")

    validation_id = db.save_validation(
        forecast_id=forecast_id,
        prediction_id=1,
        actual_id=actual_id,
        height_error=0.3,
        period_error=0.5,
        direction_error=5.0,
        category_match=True,
        mae=0.3,
        rmse=0.35
    )
    assert validation_id > 0, "Validation ID not returned"
    print("  PASS: Validation saved\n")


def test_get_forecasts_needing_validation(db):
    """Test querying forecasts that need validation."""
    print("Testing get_forecasts_needing_validation...")

    # This should return empty since our test forecast was just created
    forecasts = db.get_forecasts_needing_validation(hours_after=24)
    assert isinstance(forecasts, list), "Should return list"
    print(f"  PASS: Found {len(forecasts)} forecasts needing validation\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Validation Database Test Suite")
    print("=" * 60 + "\n")

    try:
        # Run tests
        db = test_database_initialization()
        forecast_id = test_save_forecast(db)
        test_save_predictions(db, forecast_id)
        actual_id = test_save_actual(db)
        test_save_validation(db, forecast_id, actual_id)
        test_get_forecasts_needing_validation(db)

        print("=" * 60)
        print("All tests PASSED!")
        print("=" * 60)

        # Clean up test database
        Path("data/test_validation.db").unlink(missing_ok=True)

        return 0

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
