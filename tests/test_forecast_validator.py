"""
Unit tests for ForecastValidator.

Tests validation logic, metrics calculation (MAE, RMSE, categorical accuracy,
direction accuracy), and integration with ValidationDatabase.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.validation import ForecastValidator, ValidationDatabase


class TestForecastValidator:
    """Test suite for ForecastValidator."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = ValidationDatabase(db_path)
        yield db

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def validator(self, temp_db):
        """Create ForecastValidator instance."""
        return ForecastValidator(temp_db)

    def test_initialization(self, temp_db):
        """Test ForecastValidator initialization."""
        validator = ForecastValidator(temp_db)
        assert validator.database == temp_db
        assert validator.SHORE_BUOYS == {
            "North Shore": ["51001", "51101"],
            "South Shore": ["51003", "51004"],
        }
        assert validator.DIRECTION_TOLERANCE == 22.5

    def test_categorize_height(self, validator):
        """Test wave height categorization."""
        assert validator._categorize_height(None) is None
        assert validator._categorize_height(2.0) == "small"
        assert validator._categorize_height(3.5) == "small"
        assert validator._categorize_height(4.0) == "moderate"
        assert validator._categorize_height(6.0) == "moderate"
        assert validator._categorize_height(8.0) == "large"
        assert validator._categorize_height(10.0) == "large"
        assert validator._categorize_height(12.0) == "extra_large"
        assert validator._categorize_height(15.0) == "extra_large"

    def test_direction_to_degrees(self, validator):
        """Test compass direction to degrees conversion."""
        assert validator._direction_to_degrees("N") == 0
        assert validator._direction_to_degrees("NE") == 45
        assert validator._direction_to_degrees("E") == 90
        assert validator._direction_to_degrees("SE") == 135
        assert validator._direction_to_degrees("S") == 180
        assert validator._direction_to_degrees("SW") == 225
        assert validator._direction_to_degrees("W") == 270
        assert validator._direction_to_degrees("NW") == 315
        assert validator._direction_to_degrees("n") == 0  # Case insensitive
        assert validator._direction_to_degrees("nw") == 315
        assert validator._direction_to_degrees("INVALID") is None

    def test_angular_difference(self, validator):
        """Test angular difference calculation."""
        # Same direction
        assert validator._angular_difference(0, 0) == 0
        assert validator._angular_difference(180, 180) == 0

        # Simple differences
        assert validator._angular_difference(0, 45) == 45
        assert validator._angular_difference(45, 0) == 45
        assert validator._angular_difference(90, 180) == 90

        # Wraparound cases
        assert validator._angular_difference(10, 350) == 20
        assert validator._angular_difference(350, 10) == 20
        assert validator._angular_difference(0, 180) == 180
        assert validator._angular_difference(180, 0) == 180
        assert validator._angular_difference(1, 359) == 2

    def test_match_predictions_to_actuals(self, validator):
        """Test prediction-actual matching logic."""
        base_time = datetime(2025, 10, 7, 12, 0, 0)

        predictions = [
            {
                "id": 1,
                "shore": "North Shore",
                "valid_time": base_time,
                "height": 8.0,
                "period": 14.0,
                "direction": "NW",
            },
            {
                "id": 2,
                "shore": "South Shore",
                "valid_time": base_time + timedelta(hours=6),
                "height": 4.0,
                "period": 10.0,
                "direction": "S",
            },
            {
                "id": 3,
                "shore": "North Shore",
                "valid_time": base_time + timedelta(hours=12),
                "height": None,  # Missing height - should not match
                "period": 15.0,
                "direction": "NNW",
            },
        ]

        actuals = [
            {
                "id": 101,
                "shore": "North Shore",
                "observation_time": base_time + timedelta(minutes=30),  # Within 2h window
                "wave_height": 7.5,
                "dominant_period": 14.5,
                "direction": 320.0,
            },
            {
                "id": 102,
                "shore": "South Shore",
                "observation_time": base_time + timedelta(hours=6, minutes=15),
                "wave_height": 3.8,
                "dominant_period": 9.5,
                "direction": 180.0,
            },
            {
                "id": 103,
                "shore": "North Shore",
                "observation_time": base_time + timedelta(hours=12, minutes=45),
                "wave_height": 8.2,
                "dominant_period": 15.5,
                "direction": 330.0,
            },
            {
                "id": 104,
                "shore": "North Shore",
                "observation_time": base_time + timedelta(hours=5),  # Too far from any prediction
                "wave_height": 7.0,
                "dominant_period": 13.0,
                "direction": 315.0,
            },
        ]

        matches = validator._match_predictions_to_actuals(predictions, actuals)

        # Should match predictions 1 and 2, but not 3 (missing height)
        assert len(matches) == 2

        # Check first match (prediction 1 -> actual 101)
        match1 = matches[0]
        assert match1["prediction"]["id"] == 1
        assert match1["actual"]["id"] == 101
        assert match1["time_diff_hours"] == 0.5

        # Check second match (prediction 2 -> actual 102)
        match2 = matches[1]
        assert match2["prediction"]["id"] == 2
        assert match2["actual"]["id"] == 102
        assert match2["time_diff_hours"] == 0.25

    def test_calculate_metrics(self, validator):
        """Test metrics calculation."""
        matches = [
            {
                "prediction": {
                    "height": 8.0,
                    "period": 14.0,
                    "direction": "NW",
                    "category": "large",
                },
                "actual": {
                    "wave_height": 7.5,
                    "dominant_period": 14.5,
                    "direction": 320.0,  # NW = 315, so 5 degrees off
                },
            },
            {
                "prediction": {
                    "height": 4.0,
                    "period": 10.0,
                    "direction": "S",
                    "category": "moderate",
                },
                "actual": {
                    "wave_height": 4.5,
                    "dominant_period": 9.5,
                    "direction": 185.0,  # S = 180, so 5 degrees off
                },
            },
            {
                "prediction": {
                    "height": 6.0,
                    "period": 12.0,
                    "direction": "N",
                    "category": "moderate",
                },
                "actual": {
                    "wave_height": 8.0,  # 2 ft error
                    "dominant_period": 11.0,
                    "direction": 10.0,  # N = 0, so 10 degrees off
                },
            },
        ]

        metrics = validator._calculate_metrics(matches)

        # MAE = (|8-7.5| + |4-4.5| + |6-8|) / 3 = (0.5 + 0.5 + 2.0) / 3 = 1.0
        assert abs(metrics["mae"] - 1.0) < 0.01

        # RMSE = sqrt((0.5^2 + 0.5^2 + 2.0^2) / 3) = sqrt(4.5 / 3) = 1.225
        assert abs(metrics["rmse"] - 1.225) < 0.01

        # Categorical accuracy:
        # - pred=large vs actual=7.5ft (moderate) → MISMATCH
        # - pred=moderate vs actual=4.5ft (moderate) → MATCH
        # - pred=moderate vs actual=8.0ft (large) → MISMATCH
        # = 1/3 = 0.333
        assert abs(metrics["categorical_accuracy"] - 0.333) < 0.01

        # Direction accuracy: all within 22.5 degrees
        assert metrics["direction_accuracy"] == 1.0

        assert metrics["sample_size"] == 3

    def test_calculate_metrics_empty(self, validator):
        """Test metrics calculation with no matches."""
        metrics = validator._calculate_metrics([])

        assert metrics["mae"] is None
        assert metrics["rmse"] is None
        assert metrics["categorical_accuracy"] is None
        assert metrics["direction_accuracy"] is None
        assert metrics["sample_size"] == 0

    @pytest.mark.asyncio
    async def test_get_forecast_data(self, validator, temp_db):
        """Test forecast data retrieval from database."""
        # Insert test forecast
        forecast_id = "test-forecast-123"
        forecast_time = datetime.now() - timedelta(hours=48)  # Old enough

        temp_db.save_forecast(
            {
                "forecast_id": forecast_id,
                "generated_time": forecast_time.isoformat(),
                "metadata": {
                    "source_data": {"bundle_id": "test-bundle"},
                    "api_usage": {"model": "gpt-5-mini", "input_tokens": 100, "output_tokens": 50},
                },
            }
        )

        # Insert predictions
        temp_db.save_prediction(
            forecast_id=forecast_id,
            shore="North Shore",
            forecast_time=forecast_time,
            valid_time=forecast_time + timedelta(hours=24),
            predicted_height=8.0,
            predicted_period=14.0,
            predicted_direction="NW",
            predicted_category="large",
            confidence=0.85,
        )

        # Get forecast data
        data = await validator._get_forecast_data(forecast_id, hours_after=24)

        assert data is not None
        assert data["forecast_id"] == forecast_id
        assert len(data["predictions"]) == 1

        pred = data["predictions"][0]
        assert pred["shore"] == "North Shore"
        assert pred["height"] == 8.0
        assert pred["period"] == 14.0
        assert pred["direction"] == "NW"
        assert pred["category"] == "large"
        assert pred["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_get_forecast_data_too_recent(self, validator, temp_db):
        """Test that recent forecasts are rejected."""
        # Insert very recent forecast
        forecast_id = "recent-forecast"
        forecast_time = datetime.now() - timedelta(hours=12)  # Too recent

        temp_db.save_forecast(
            {
                "forecast_id": forecast_id,
                "generated_time": forecast_time.isoformat(),
                "metadata": {},
            }
        )

        # Should return None for recent forecasts
        data = await validator._get_forecast_data(forecast_id, hours_after=24)
        assert data is None

    @pytest.mark.asyncio
    async def test_get_forecast_data_not_found(self, validator):
        """Test forecast not found in database."""
        data = await validator._get_forecast_data("nonexistent-forecast", hours_after=24)
        assert data is None

    @pytest.mark.asyncio
    async def test_fetch_actual_observations(self, validator):
        """Test fetching actual observations."""
        base_time = datetime(2025, 10, 7, 12, 0, 0)

        predictions = [
            {
                "shore": "North Shore",
                "valid_time": base_time,
            },
            {
                "shore": "South Shore",
                "valid_time": base_time + timedelta(hours=6),
            },
        ]

        # Mock BuoyDataFetcher
        mock_observations_north = [
            {
                "buoy_id": "51001",
                "observation_time": base_time,
                "wave_height": 8.0,
                "dominant_period": 14.0,
                "direction": 315.0,
                "source": "NDBC",
            }
        ]

        mock_observations_south = [
            {
                "buoy_id": "51003",
                "observation_time": base_time + timedelta(hours=6),
                "wave_height": 4.0,
                "dominant_period": 10.0,
                "direction": 180.0,
                "source": "NDBC",
            }
        ]

        with patch("src.validation.buoy_fetcher.BuoyDataFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value.__aenter__.return_value

            async def mock_fetch_observations(shore, start_time, end_time):
                if shore == "north_shore":
                    return mock_observations_north
                elif shore == "south_shore":
                    return mock_observations_south
                return []

            mock_fetcher.fetch_observations = AsyncMock(side_effect=mock_fetch_observations)

            actuals = await validator._fetch_actual_observations(predictions)

            # Should have fetched observations for both shores
            assert len(actuals) == 2

            # Check that observations were saved to database with IDs
            assert all("id" in obs for obs in actuals)
            assert all("shore" in obs for obs in actuals)

    @pytest.mark.asyncio
    async def test_validate_forecast_integration(self, validator, temp_db):
        """Integration test for complete validation flow."""
        # Setup forecast
        forecast_id = "integration-test-forecast"
        forecast_time = datetime.now() - timedelta(hours=48)

        temp_db.save_forecast(
            {
                "forecast_id": forecast_id,
                "generated_time": forecast_time.isoformat(),
                "metadata": {},
            }
        )

        # Add prediction
        valid_time = forecast_time + timedelta(hours=24)
        temp_db.save_prediction(
            forecast_id=forecast_id,
            shore="North Shore",
            forecast_time=forecast_time,
            valid_time=valid_time,
            predicted_height=8.0,
            predicted_period=14.0,
            predicted_direction="NW",
            predicted_category="large",
            confidence=0.85,
        )

        # Mock buoy observations
        mock_observations = [
            {
                "buoy_id": "51001",
                "observation_time": valid_time,
                "wave_height": 7.5,  # 0.5 ft error
                "dominant_period": 14.5,
                "direction": 320.0,  # 5 degrees from NW (315)
                "source": "NDBC",
            }
        ]

        with patch("src.validation.buoy_fetcher.BuoyDataFetcher") as MockFetcher:
            mock_fetcher = MockFetcher.return_value.__aenter__.return_value
            mock_fetcher.fetch_observations = AsyncMock(return_value=mock_observations)

            # Run validation
            results = await validator.validate_forecast(forecast_id, hours_after=24)

        # Check results
        assert results["forecast_id"] == forecast_id
        assert results["predictions_validated"] == 1
        assert results["predictions_total"] == 1
        assert "error" not in results

        # Check metrics
        metrics = results["metrics"]
        assert abs(metrics["mae"] - 0.5) < 0.01  # MAE = 0.5 ft
        assert abs(metrics["rmse"] - 0.5) < 0.01  # RMSE = 0.5 ft
        # Prediction: category='large', Actual: 7.5ft = 'moderate' → MISMATCH
        assert metrics["categorical_accuracy"] == 0.0
        assert metrics["direction_accuracy"] == 1.0  # Within 22.5 degrees
        assert metrics["sample_size"] == 1

        # Check that validation was saved to database
        validations = results["validations"]
        assert len(validations) == 1

        validation = validations[0]
        assert abs(validation["height_error"] - 0.5) < 0.01
        assert validation["category_match"] is False  # large != moderate
        assert validation["direction_error"] < 22.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
