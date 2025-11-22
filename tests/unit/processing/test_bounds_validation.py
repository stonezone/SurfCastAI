"""
Unit tests for buoy data bounds validation.

Tests Task 1.1 from TODO-2.md:
- Physical constraint validation on wave metrics
- Rejection of out-of-bounds values
- Logging of rejected values
"""

import unittest
import logging
import json
from unittest.mock import patch
from src.processing.models.buoy_data import (
    BuoyObservation,
    BuoyData,
    WAVE_HEIGHT_BOUNDS,
    DOMINANT_PERIOD_BOUNDS,
    AVERAGE_PERIOD_BOUNDS,
    WIND_SPEED_BOUNDS,
    PRESSURE_BOUNDS,
    WATER_TEMP_BOUNDS,
    AIR_TEMP_BOUNDS,
    DIRECTION_BOUNDS,
)


class TestBoundsValidation(unittest.TestCase):
    """Test bounds validation for buoy data."""

    def test_valid_wave_height(self):
        """Test that valid wave heights are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '5.5',  # Valid: between 0.0 and 30.0
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.wave_height, 5.5)

    def test_negative_wave_height_rejected(self):
        """Test that negative wave heights are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '-1.0',  # Invalid: below minimum
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.wave_height)
            self.assertTrue(any('wave_height' in message for message in log.output))

    def test_excessive_wave_height_rejected(self):
        """Test that excessively large wave heights are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '50.0',  # Invalid: above maximum of 30.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.wave_height)
            self.assertTrue(any('wave_height' in message for message in log.output))

    def test_phantom_swell_period_rejected(self):
        """Test that phantom swell periods (< 4s) are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'DPD': '3.0',  # Invalid: below minimum of 4.0 seconds
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.dominant_period)
            self.assertTrue(any('dominant_period' in message for message in log.output))

    def test_valid_dominant_period(self):
        """Test that valid dominant periods are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'DPD': '12.5',  # Valid: between 4.0 and 30.0
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.dominant_period, 12.5)

    def test_excessive_dominant_period_rejected(self):
        """Test that excessively long periods are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'DPD': '35.0',  # Invalid: above maximum of 30.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.dominant_period)

    def test_valid_wind_speed(self):
        """Test that valid wind speeds are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WSPD': '25.0',  # Valid: between 0.0 and 150.0
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.wind_speed, 25.0)

    def test_excessive_wind_speed_rejected(self):
        """Test that excessive wind speeds are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WSPD': '200.0',  # Invalid: above maximum of 150.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.wind_speed)

    def test_valid_pressure(self):
        """Test that valid pressure values are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'PRES': '1013.25',  # Valid: between 900.0 and 1100.0
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.pressure, 1013.25)

    def test_low_pressure_rejected(self):
        """Test that abnormally low pressure is rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'PRES': '850.0',  # Invalid: below minimum of 900.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.pressure)

    def test_high_pressure_rejected(self):
        """Test that abnormally high pressure is rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'PRES': '1150.0',  # Invalid: above maximum of 1100.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.pressure)

    def test_valid_water_temperature(self):
        """Test that valid water temperatures are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WTMP': '22.5',  # Valid: between -2.0 and 35.0
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.water_temperature, 22.5)

    def test_extreme_water_temperature_rejected(self):
        """Test that extreme water temperatures are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WTMP': '50.0',  # Invalid: above maximum of 35.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.water_temperature)

    def test_valid_direction(self):
        """Test that valid directions are accepted."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'MWD': '270.0',  # Valid: between 0.0 and 360.0
            'WDIR': '180.0',
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertEqual(obs.wave_direction, 270.0)
        self.assertEqual(obs.wind_direction, 180.0)

    def test_invalid_direction_rejected(self):
        """Test that invalid directions are rejected."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'MWD': '400.0',  # Invalid: above maximum of 360.0
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.wave_direction)

    def test_multiple_invalid_values(self):
        """Test handling of multiple invalid values in single observation."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '-5.0',  # Invalid
            'DPD': '2.0',  # Invalid (phantom swell)
            'WSPD': '200.0',  # Invalid
            'PRES': '1013.25',  # Valid
        }
        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            obs = BuoyObservation.from_ndbc(data)
            self.assertIsNone(obs.wave_height)
            self.assertIsNone(obs.dominant_period)
            self.assertIsNone(obs.wind_speed)
            self.assertEqual(obs.pressure, 1013.25)  # Valid value preserved
            # Should have at least 3 warning messages
            self.assertGreaterEqual(len(log.output), 3)

    def test_missing_values_handled(self):
        """Test that missing values are handled gracefully."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            # No wave data provided
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertIsNone(obs.wave_height)
        self.assertIsNone(obs.dominant_period)
        self.assertIsNone(obs.wind_speed)

    def test_empty_string_values_handled(self):
        """Test that empty string values are handled gracefully."""
        data = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '',
            'DPD': '',
        }
        obs = BuoyObservation.from_ndbc(data)
        self.assertIsNone(obs.wave_height)
        self.assertIsNone(obs.dominant_period)

    def test_boundary_values(self):
        """Test exact boundary values."""
        # Test lower bounds
        data_lower = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '0.0',  # Exact minimum
            'DPD': '4.0',  # Exact minimum
            'WSPD': '0.0',  # Exact minimum
        }
        obs_lower = BuoyObservation.from_ndbc(data_lower)
        self.assertEqual(obs_lower.wave_height, 0.0)
        self.assertEqual(obs_lower.dominant_period, 4.0)
        self.assertEqual(obs_lower.wind_speed, 0.0)

        # Test upper bounds
        data_upper = {
            'Date': '2025-10-09T12:00:00Z',
            'WVHT': '30.0',  # Exact maximum
            'DPD': '30.0',  # Exact maximum
            'WSPD': '150.0',  # Exact maximum
        }
        obs_upper = BuoyObservation.from_ndbc(data_upper)
        self.assertEqual(obs_upper.wave_height, 30.0)
        self.assertEqual(obs_upper.dominant_period, 30.0)
        self.assertEqual(obs_upper.wind_speed, 150.0)

    def test_bounds_constants_defined(self):
        """Test that all bounds constants are properly defined."""
        self.assertEqual(WAVE_HEIGHT_BOUNDS, (0.0, 30.0))
        self.assertEqual(DOMINANT_PERIOD_BOUNDS, (4.0, 30.0))
        self.assertEqual(AVERAGE_PERIOD_BOUNDS, (2.0, 25.0))
        self.assertEqual(WIND_SPEED_BOUNDS, (0.0, 150.0))
        self.assertEqual(PRESSURE_BOUNDS, (900.0, 1100.0))
        self.assertEqual(WATER_TEMP_BOUNDS, (-2.0, 35.0))
        self.assertEqual(AIR_TEMP_BOUNDS, (-40.0, 50.0))
        self.assertEqual(DIRECTION_BOUNDS, (0.0, 360.0))


class TestNormalizedJSONBoundsValidation(unittest.TestCase):
    """
    Test bounds validation for normalized JSON format.

    This addresses Task 0.1 from GEM_ROADMAP.md - ensuring that
    BuoyData.from_json() validates bounds for normalized format data,
    not just raw NDBC format.
    """

    def test_normalized_json_with_negative_wave_height(self):
        """Test that normalized JSON with negative wave height is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'latitude': 21.67,
            'longitude': -158.12,
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': -2.5,  # INVALID: negative
                    'dominant_period': 10.0,
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].wave_height)
            self.assertTrue(any('wave_height' in message for message in log.output))

    def test_normalized_json_with_phantom_swell_period(self):
        """Test that normalized JSON with phantom swell period (< 4s) is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': 5.0,
                    'dominant_period': 3.0,  # INVALID: phantom swell (< 4s)
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].dominant_period)
            self.assertTrue(any('dominant_period' in message for message in log.output))

    def test_normalized_json_with_excessive_wind_speed(self):
        """Test that normalized JSON with excessive wind speed is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wind_speed': 200.0,  # INVALID: above maximum (150 knots)
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].wind_speed)
            self.assertTrue(any('wind_speed' in message for message in log.output))

    def test_normalized_json_with_invalid_pressure(self):
        """Test that normalized JSON with invalid pressure is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'pressure': 850.0,  # INVALID: below minimum (900 mb)
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].pressure)
            self.assertTrue(any('pressure' in message for message in log.output))

    def test_normalized_json_with_extreme_water_temperature(self):
        """Test that normalized JSON with extreme water temperature is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'water_temperature': 50.0,  # INVALID: above maximum (35°C)
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].water_temperature)
            self.assertTrue(any('water_temperature' in message for message in log.output))

    def test_normalized_json_with_invalid_direction(self):
        """Test that normalized JSON with invalid direction is rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_direction': 400.0,  # INVALID: above maximum (360°)
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            self.assertIsNone(buoy_data.observations[0].wave_direction)
            self.assertTrue(any('wave_direction' in message for message in log.output))

    def test_normalized_json_with_valid_data(self):
        """Test that normalized JSON with valid data is accepted."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'latitude': 21.67,
            'longitude': -158.12,
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': 5.5,  # Valid
                    'dominant_period': 12.5,  # Valid
                    'average_period': 10.0,  # Valid
                    'wave_direction': 270.0,  # Valid
                    'wind_speed': 25.0,  # Valid
                    'wind_direction': 180.0,  # Valid
                    'air_temperature': 22.0,  # Valid
                    'water_temperature': 24.5,  # Valid
                    'pressure': 1013.25,  # Valid
                }
            ]
        })

        # Should not log any warnings
        buoy_data = BuoyData.from_json(json_data)
        self.assertEqual(len(buoy_data.observations), 1)
        obs = buoy_data.observations[0]
        self.assertEqual(obs.wave_height, 5.5)
        self.assertEqual(obs.dominant_period, 12.5)
        self.assertEqual(obs.average_period, 10.0)
        self.assertEqual(obs.wave_direction, 270.0)
        self.assertEqual(obs.wind_speed, 25.0)
        self.assertEqual(obs.wind_direction, 180.0)
        self.assertEqual(obs.air_temperature, 22.0)
        self.assertEqual(obs.water_temperature, 24.5)
        self.assertEqual(obs.pressure, 1013.25)

    def test_normalized_json_with_multiple_invalid_values(self):
        """Test that multiple invalid values in normalized JSON are all rejected."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': -3.0,  # INVALID: negative
                    'dominant_period': 2.5,  # INVALID: phantom swell
                    'wind_speed': 180.0,  # INVALID: too high
                    'pressure': 1013.25,  # VALID: should be preserved
                }
            ]
        })

        with self.assertLogs('src.utils.numeric', level='WARNING') as log:
            buoy_data = BuoyData.from_json(json_data)
            self.assertEqual(len(buoy_data.observations), 1)
            obs = buoy_data.observations[0]
            # Invalid values should be None
            self.assertIsNone(obs.wave_height)
            self.assertIsNone(obs.dominant_period)
            self.assertIsNone(obs.wind_speed)
            # Valid value should be preserved
            self.assertEqual(obs.pressure, 1013.25)
            # Should have warnings for all invalid values
            self.assertGreaterEqual(len(log.output), 3)

    def test_normalized_json_with_boundary_values(self):
        """Test that normalized JSON with exact boundary values are accepted."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': 0.0,  # Exact minimum
                    'dominant_period': 4.0,  # Exact minimum
                    'wind_speed': 0.0,  # Exact minimum
                    'pressure': 900.0,  # Exact minimum
                }
            ]
        })

        buoy_data = BuoyData.from_json(json_data)
        obs = buoy_data.observations[0]
        self.assertEqual(obs.wave_height, 0.0)
        self.assertEqual(obs.dominant_period, 4.0)
        self.assertEqual(obs.wind_speed, 0.0)
        self.assertEqual(obs.pressure, 900.0)

    def test_normalized_json_preserves_valid_null_values(self):
        """Test that normalized JSON with None values are preserved (not rejected)."""
        json_data = json.dumps({
            'station_id': '51201',
            'name': 'Test Buoy',
            'observations': [
                {
                    'timestamp': '2025-10-09T12:00:00Z',
                    'wave_height': None,  # Explicitly None (missing data)
                    'dominant_period': None,
                }
            ]
        })

        # Should not log warnings for None values
        buoy_data = BuoyData.from_json(json_data)
        obs = buoy_data.observations[0]
        self.assertIsNone(obs.wave_height)
        self.assertIsNone(obs.dominant_period)


if __name__ == '__main__':
    unittest.main()
