"""Test database transaction rollback for batch operations."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.validation.database import ValidationDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create database instance
    db = ValidationDatabase(db_path=db_path)

    yield db

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_forecast(temp_db):
    """Create a sample forecast for testing."""
    forecast_data = {
        "forecast_id": "test-forecast-123",
        "generated_time": datetime.now(),
        "metadata": {
            "source_data": {"bundle_id": "bundle-123"},
            "api_usage": {
                "model": "gpt-4",
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_cost": 0.05,
            },
            "generation_time": 5.5,
        },
    }
    forecast_id = temp_db.save_forecast(forecast_data)
    return forecast_id


class TestPredictionsBatchRollback:
    """Test batch predictions with rollback."""

    def test_save_predictions_success(self, temp_db, sample_forecast):
        """Test successful batch prediction insert."""
        predictions = [
            {
                "shore": "North Shore",
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=i),
                "height": 8.0 + i,
                "period": 12.0,
                "direction": "NW",
                "category": "overhead",
                "confidence": 0.85,
            }
            for i in range(5)
        ]

        # Should not raise exception
        temp_db.save_predictions(sample_forecast, predictions)

        # Verify all predictions were saved
        saved_predictions = temp_db.get_predictions_for_forecast(sample_forecast)
        assert len(saved_predictions) == 5
        assert saved_predictions[0]["shore"] == "North Shore"

    def test_save_predictions_rollback_on_invalid_data(self, temp_db, sample_forecast):
        """Test that batch insert rolls back on invalid data."""
        predictions = [
            {
                "shore": "North Shore",
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=1),
                "height": 8.0,
                "period": 12.0,
            },
            {
                "shore": None,  # Invalid: shore is required
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=2),
                "height": 9.0,
                "period": 13.0,
            },
        ]

        # Should raise exception and rollback
        with pytest.raises(Exception):
            temp_db.save_predictions(sample_forecast, predictions)

        # Verify no predictions were saved (rollback occurred)
        saved_predictions = temp_db.get_predictions_for_forecast(sample_forecast)
        assert len(saved_predictions) == 0


class TestActualsBatchRollback:
    """Test batch actuals with rollback."""

    def test_save_actuals_success(self, temp_db):
        """Test successful batch actual insert."""
        actuals = [
            {
                "buoy_id": "51201",
                "observation_time": datetime.now() - timedelta(hours=i),
                "wave_height": 8.0 + i,
                "dominant_period": 12.0,
                "direction": 315.0,
                "source": "NDBC",
            }
            for i in range(5)
        ]

        # Should not raise exception
        temp_db.save_actuals(actuals)

        # Verify actuals were saved
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM actuals WHERE buoy_id = '51201'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 5

    def test_save_actuals_rollback_on_invalid_data(self, temp_db):
        """Test that batch insert rolls back on invalid data."""
        actuals = [
            {
                "buoy_id": "51201",
                "observation_time": datetime.now(),
                "wave_height": 8.0,
                "dominant_period": 12.0,
            },
            {
                "buoy_id": None,  # Invalid: buoy_id is required
                "observation_time": datetime.now(),
                "wave_height": 9.0,
                "dominant_period": 13.0,
            },
        ]

        # Should raise exception and rollback
        with pytest.raises(Exception):
            temp_db.save_actuals(actuals)

        # Verify no actuals were saved (rollback occurred)
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM actuals WHERE buoy_id = '51201'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0


class TestValidationsBatchRollback:
    """Test batch validations with rollback."""

    def test_save_validations_success(self, temp_db, sample_forecast):
        """Test successful batch validation insert."""
        # Create some predictions and actuals first
        predictions = [
            {
                "shore": "North Shore",
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=i),
                "height": 8.0 + i,
            }
            for i in range(3)
        ]
        temp_db.save_predictions(sample_forecast, predictions)

        actuals = [
            {
                "buoy_id": "51201",
                "observation_time": datetime.now() + timedelta(hours=i),
                "wave_height": 8.5 + i,
            }
            for i in range(3)
        ]
        temp_db.save_actuals(actuals)

        # Get prediction and actual IDs
        saved_predictions = temp_db.get_predictions_for_forecast(sample_forecast)
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM actuals ORDER BY observation_time")
        actual_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Create validations
        validations = [
            {
                "forecast_id": sample_forecast,
                "prediction_id": saved_predictions[i]["id"],
                "actual_id": actual_ids[i],
                "height_error": 0.5,
                "mae": 0.5,
                "rmse": 0.6,
            }
            for i in range(3)
        ]

        # Should not raise exception
        temp_db.save_validations(validations)

        # Verify validations were saved
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM validations WHERE forecast_id = ?", (sample_forecast,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    def test_save_validations_rollback_on_invalid_data(self, temp_db, sample_forecast):
        """Test that batch insert rolls back on constraint violation."""
        # Create a validation with None for required field
        validations = [
            {
                "forecast_id": None,  # Invalid: forecast_id is required
                "prediction_id": 1,
                "actual_id": 1,
                "height_error": 0.5,
                "mae": 0.5,
                "rmse": 0.6,
            }
        ]

        # Should raise exception and rollback
        with pytest.raises(Exception):
            temp_db.save_validations(validations)

        # Verify no validations were saved (rollback occurred)
        conn = sqlite3.connect(temp_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM validations")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0


class TestDatabaseIntegrity:
    """Test database integrity after rollback."""

    def test_connection_closed_after_exception(self, temp_db, sample_forecast):
        """Test that database connection is properly closed even after exception."""
        invalid_predictions = [
            {
                "shore": None,  # Invalid
                "forecast_time": datetime.now(),
                "valid_time": datetime.now(),
            }
        ]

        # This should raise exception
        with pytest.raises(Exception):
            temp_db.save_predictions(sample_forecast, invalid_predictions)

        # Should be able to perform other operations (connection was closed)
        predictions = [
            {
                "shore": "South Shore",
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=1),
                "height": 4.0,
            }
        ]

        # This should succeed
        temp_db.save_predictions(sample_forecast, predictions)

        saved = temp_db.get_predictions_for_forecast(sample_forecast)
        assert len(saved) == 1
        assert saved[0]["shore"] == "South Shore"

    def test_empty_batch_operations(self, temp_db, sample_forecast):
        """Test that empty batch operations don't cause issues."""
        # Empty predictions list
        temp_db.save_predictions(sample_forecast, [])

        # Empty actuals list
        temp_db.save_actuals([])

        # Empty validations list
        temp_db.save_validations([])

        # Verify database is still functional
        predictions = [
            {
                "shore": "East Shore",
                "forecast_time": datetime.now(),
                "valid_time": datetime.now() + timedelta(hours=1),
                "height": 3.0,
            }
        ]
        temp_db.save_predictions(sample_forecast, predictions)

        saved = temp_db.get_predictions_for_forecast(sample_forecast)
        assert len(saved) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
