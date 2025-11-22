"""
Unit tests for the WeatherProcessor.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.core.config import Config
from src.processing.models.weather_data import WeatherData, WeatherPeriod
from src.processing.weather_processor import WeatherProcessor


class TestWeatherProcessor(unittest.TestCase):
    """Tests for the WeatherProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock config
        self.config = MagicMock(spec=Config)

        # Create processor
        self.processor = WeatherProcessor(self.config)

        # Sample weather data
        self.sample_data = {
            "properties": {
                "periods": [
                    {
                        "number": 1,
                        "name": "Today",
                        "startTime": "2023-01-01T12:00:00-10:00",
                        "endTime": "2023-01-01T18:00:00-10:00",
                        "temperature": 82,
                        "temperatureUnit": "F",
                        "windSpeed": "10 mph",
                        "windDirection": "NE",
                        "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
                        "shortForecast": "Partly Sunny",
                        "detailedForecast": "Partly sunny with northeast winds around 10 mph.",
                    },
                    {
                        "number": 2,
                        "name": "Tonight",
                        "startTime": "2023-01-01T18:00:00-10:00",
                        "endTime": "2023-01-02T06:00:00-10:00",
                        "temperature": 72,
                        "temperatureUnit": "F",
                        "windSpeed": "5 mph",
                        "windDirection": "ENE",
                        "icon": "https://api.weather.gov/icons/land/night/few?size=medium",
                        "shortForecast": "Mostly Clear",
                        "detailedForecast": "Mostly clear with east northeast winds around 5 mph.",
                    },
                ]
            }
        }

    def test_validate_valid_data(self):
        """Test validation with valid data."""
        errors = self.processor.validate(self.sample_data)
        self.assertEqual(len(errors), 0, "Should not have validation errors")

    def test_validate_invalid_data(self):
        """Test validation with invalid data."""
        # Test missing properties
        invalid_data = {"wrong_key": "value"}
        errors = self.processor.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")

        # Test empty periods
        invalid_data = {"properties": {"periods": []}}
        errors = self.processor.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")

    def test_process_valid_data(self):
        """Test processing with valid data."""
        result = self.processor.process(self.sample_data)

        # Check success
        self.assertTrue(result.success, "Processing should succeed")
        self.assertIsNone(result.error, "Should not have error")

        # Check data type
        self.assertIsInstance(result.data, WeatherData, "Result should be WeatherData")

        # Check basic properties
        weather_data = result.data
        self.assertEqual(weather_data.provider, "nws", "Provider should be 'nws'")
        self.assertEqual(len(weather_data.periods), 2, "Should have 2 periods")

        # Check period data
        first_period = weather_data.periods[0]
        self.assertIsInstance(first_period, WeatherPeriod, "Period should be WeatherPeriod")
        self.assertEqual(
            first_period.temperature_unit, "C", "Temperature unit should be converted to C"
        )
        self.assertEqual(
            first_period.wind_speed_unit, "m/s", "Wind speed unit should be converted to m/s"
        )

        # Check metadata
        self.assertIn("wind_analysis", weather_data.metadata, "Should have wind analysis metadata")
        self.assertIn(
            "text_extraction", weather_data.metadata, "Should have text extraction metadata"
        )
        self.assertIn("surf_weather", weather_data.metadata, "Should have surf weather metadata")

    def test_standardize_units(self):
        """Test unit standardization."""
        # Create test data
        weather_data = WeatherData(
            provider="test",
            periods=[
                WeatherPeriod(
                    timestamp="2023-01-01T12:00:00Z",
                    temperature=80,
                    temperature_unit="F",
                    wind_speed=15,
                    wind_speed_unit="mph",
                    wind_direction=45,
                ),
                WeatherPeriod(
                    timestamp="2023-01-01T18:00:00Z",
                    temperature=25,
                    temperature_unit="C",
                    wind_speed=10,
                    wind_speed_unit="knots",
                    wind_direction=90,
                ),
            ],
        )

        # Standardize units
        result = self.processor._standardize_units(weather_data)

        # Check units
        self.assertEqual(result.periods[0].temperature_unit, "C", "Temperature unit should be C")
        self.assertEqual(result.periods[0].wind_speed_unit, "m/s", "Wind speed unit should be m/s")
        self.assertEqual(result.periods[1].temperature_unit, "C", "Temperature unit should be C")
        self.assertEqual(result.periods[1].wind_speed_unit, "m/s", "Wind speed unit should be m/s")

        # Check converted values (approximate due to floating point)
        self.assertAlmostEqual(
            result.periods[0].temperature, 26.67, delta=0.1, msg="80F should be ~26.67C"
        )
        self.assertAlmostEqual(
            result.periods[0].wind_speed, 6.7, delta=0.1, msg="15mph should be ~6.7m/s"
        )
        self.assertAlmostEqual(
            result.periods[1].wind_speed, 5.14, delta=0.1, msg="10knots should be ~5.14m/s"
        )

    def test_is_offshore_wind(self):
        """Test offshore wind determination."""
        # Test cases: (shore_direction, wind_direction, expected_result)
        test_cases = [
            (0, 180, True),  # North shore, south wind (offshore)
            (0, 0, False),  # North shore, north wind (onshore)
            (0, 90, False),  # North shore, east wind (side-shore)
            (180, 0, True),  # South shore, north wind (offshore)
            (180, 180, False),  # South shore, south wind (onshore)
            (270, 90, True),  # West shore, east wind (offshore)
            (90, 270, True),  # East shore, west wind (offshore)
        ]

        for shore_dir, wind_dir, expected in test_cases:
            result = self.processor._is_offshore_wind(shore_dir, wind_dir)
            self.assertEqual(
                result,
                expected,
                f"Shore {shore_dir}, Wind {wind_dir} should be {'offshore' if expected else 'not offshore'}",
            )

    def test_get_surf_quality_factor(self):
        """Test surf quality factor calculation."""
        # Create test data
        weather_data = WeatherData(
            provider="test",
            periods=[
                WeatherPeriod(
                    timestamp="2023-01-01T12:00:00Z",
                    wind_speed=5,
                    wind_direction=180,
                    short_forecast="Sunny",
                )
            ],
            # Mock metadata with pre-analyzed results
            metadata={
                "wind_analysis": {
                    "shore_impacts": {
                        "north_shore": {"overall_rating": 0.8},  # Good rating for north shore
                        "south_shore": {"overall_rating": 0.2},  # Poor rating for south shore
                    }
                },
                "surf_weather": {"patterns": ["sunny"]},
            },
        )

        # Test quality factors
        north_factor = self.processor.get_surf_quality_factor(weather_data, "north shore")
        south_factor = self.processor.get_surf_quality_factor(weather_data, "south shore")

        # Check factors (north should be better than south)
        self.assertGreater(north_factor, 0.6, "North shore factor should be good")
        self.assertLess(south_factor, 0.4, "South shore factor should be poor")
        self.assertGreater(
            north_factor, south_factor, "North shore should have better factor than south"
        )


if __name__ == "__main__":
    unittest.main()
