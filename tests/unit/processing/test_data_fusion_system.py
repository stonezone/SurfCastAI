"""
Unit tests for the DataFusionSystem.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.core.config import Config
from src.processing.data_fusion_system import DataFusionSystem
from src.processing.models.buoy_data import BuoyData, BuoyObservation
from src.processing.models.swell_event import SwellComponent, SwellEvent, SwellForecast
from src.processing.models.wave_model import ModelData, ModelForecast, ModelPoint
from src.processing.models.weather_data import WeatherData, WeatherPeriod


class TestDataFusionSystem(unittest.TestCase):
    """Tests for the DataFusionSystem class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock config
        self.config = MagicMock(spec=Config)

        # Create processor
        self.fusion_system = DataFusionSystem(self.config)

        # Sample buoy data
        self.sample_buoy_data = BuoyData(
            station_id="51001",
            name="NDBC 51001 - NW Hawaii",
            observations=[
                BuoyObservation(
                    timestamp="2023-01-01T12:00:00Z",
                    wave_height=2.5,
                    dominant_period=12.0,
                    wave_direction=315,
                    wind_speed=15.0,
                    wind_direction=45,
                )
            ],
            metadata={},
        )

        # Sample weather data
        self.sample_weather_data = WeatherData(
            provider="nws",
            location="Oahu",
            latitude=21.5,
            longitude=-158.0,
            periods=[
                WeatherPeriod(
                    timestamp="2023-01-01T12:00:00Z",
                    temperature=28,
                    temperature_unit="C",
                    wind_speed=5,
                    wind_speed_unit="m/s",
                    wind_direction=45,
                    short_forecast="Partly Sunny",
                )
            ],
            metadata={
                "wind_analysis": {
                    "shore_impacts": {
                        "north_shore": {"overall_rating": 0.8},
                        "south_shore": {"overall_rating": 0.3},
                    }
                }
            },
        )

        # Sample model data
        self.sample_model_data = ModelData(
            model_id="swan",
            run_time="2023-01-01T00:00:00Z",
            region="hawaii",
            forecasts=[
                ModelForecast(
                    timestamp="2023-01-01T12:00:00Z",
                    forecast_hour=12,
                    points=[
                        ModelPoint(
                            latitude=21.6,
                            longitude=-158.1,
                            wave_height=3.0,
                            wave_period=14.0,
                            wave_direction=320,
                        )
                    ],
                )
            ],
            metadata={
                "swell_events": [
                    {
                        "event_id": "swan_test_1",
                        "peak_time": "2023-01-01T12:00:00Z",
                        "peak_height": 3.0,
                        "peak_period": 14.0,
                        "peak_direction": 320,
                        "significance": 0.7,
                        "hawaii_scale": 19.7,
                    }
                ]
            },
        )

        # Sample fusion input data
        self.sample_fusion_data = {
            "metadata": {"forecast_id": "test_forecast", "region": "hawaii"},
            "buoy_data": [self.sample_buoy_data],
            "weather_data": [self.sample_weather_data],
            "model_data": [self.sample_model_data],
        }

    def test_validate_valid_data(self):
        """Test validation with valid data."""
        errors = self.fusion_system.validate(self.sample_fusion_data)
        self.assertEqual(len(errors), 0, "Should not have validation errors")

    def test_validate_invalid_data(self):
        """Test validation with invalid data."""
        # Test missing metadata
        invalid_data = {}
        errors = self.fusion_system.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")

        # Test no data sources
        invalid_data = {"metadata": {}}
        errors = self.fusion_system.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")

    def test_process_fusion_data(self):
        """Test processing with fusion data."""
        result = self.fusion_system.process(self.sample_fusion_data)

        # Check success
        self.assertTrue(result.success, "Processing should succeed")
        self.assertIsNone(result.error, "Should not have error")

        # Check data type
        self.assertIsInstance(result.data, SwellForecast, "Result should be SwellForecast")

        # Check basic properties
        forecast = result.data
        self.assertEqual(forecast.forecast_id, "test_forecast", "Forecast ID should match input")

        # Check locations
        self.assertGreaterEqual(
            len(forecast.locations), 4, "Should have at least 4 Hawaii locations"
        )

        # Check swell events
        self.assertGreaterEqual(len(forecast.swell_events), 1, "Should have at least 1 swell event")

        # Check metadata
        self.assertIn("confidence", forecast.metadata, "Should have confidence metadata")

    def test_extract_buoy_data(self):
        """Test buoy data extraction."""
        result = self.fusion_system._extract_buoy_data(self.sample_fusion_data)

        self.assertEqual(len(result), 1, "Should extract 1 buoy data object")
        self.assertEqual(result[0].station_id, "51001", "Station ID should match")

    def test_extract_weather_data(self):
        """Test weather data extraction."""
        result = self.fusion_system._extract_weather_data(self.sample_fusion_data)

        self.assertEqual(len(result), 1, "Should extract 1 weather data object")
        self.assertEqual(result[0].provider, "nws", "Provider should match")

    def test_extract_model_data(self):
        """Test model data extraction."""
        result = self.fusion_system._extract_model_data(self.sample_fusion_data)

        self.assertEqual(len(result), 1, "Should extract 1 model data object")
        self.assertEqual(result[0].model_id, "swan", "Model ID should match")

    def test_identify_swell_events(self):
        """Test swell event identification."""
        buoy_data = self.fusion_system._extract_buoy_data(self.sample_fusion_data)
        model_data = self.fusion_system._extract_model_data(self.sample_fusion_data)

        events = self.fusion_system._identify_swell_events(buoy_data, model_data)

        self.assertGreaterEqual(len(events), 2, "Should identify at least 2 swell events")

        # Check for both buoy and model events
        sources = [e.source for e in events]
        self.assertIn("buoy", sources, "Should include buoy events")
        self.assertIn("model", sources, "Should include model events")

    def test_integrate_altimetry_metadata(self):
        forecast = SwellForecast(
            forecast_id="test", generated_time="2025-10-16T12:00:00Z", metadata={}
        )
        entries = [
            {
                "file_path": "/tmp/altimetry.png",
                "description": "SSH anomaly",
                "source_url": "https://example.com/alt.png",
                "type": "image",
            }
        ]

        self.fusion_system._integrate_altimetry_data(forecast, entries)
        self.assertIn("altimetry", forecast.metadata)
        self.assertEqual(forecast.metadata["altimetry"][0]["file_path"], "/tmp/altimetry.png")

    def test_integrate_nearshore_metadata(self):
        forecast = SwellForecast(
            forecast_id="test", generated_time="2025-10-16T12:00:00Z", metadata={}
        )
        entries = [
            {
                "station_id": "hanalei_225",
                "station_name": "Hanalei",
                "significant_height_m": 2.4,
                "peak_period_s": 14.8,
                "file_path": "/tmp/hanalei.json",
            }
        ]

        self.fusion_system._integrate_nearshore_data(forecast, entries)
        self.assertIn("nearshore_buoys", forecast.metadata)
        self.assertEqual(forecast.metadata["nearshore_buoys"][0]["station_id"], "hanalei_225")

    def test_integrate_upper_air_metadata(self):
        forecast = SwellForecast(
            forecast_id="test", generated_time="2025-10-16T12:00:00Z", metadata={}
        )
        entries = [
            {"analysis_level": "250", "product_type": "jet_stream", "source_id": "wpc_250mb"}
        ]

        self.fusion_system._integrate_upper_air_data(forecast, entries)
        self.assertIn("upper_air", forecast.metadata)
        self.assertIn("upper_air_summary", forecast.metadata)
        self.assertIn("250", forecast.metadata["upper_air_summary"])

    def test_integrate_climatology_metadata(self):
        forecast = SwellForecast(
            forecast_id="test", generated_time="2025-10-16T12:00:00Z", metadata={}
        )
        entries = [
            {"source_id": "snn_nsstat10", "format": "text", "file_path": "/tmp/nsstat10.txt"}
        ]

        self.fusion_system._integrate_climatology_data(forecast, entries)
        self.assertIn("climatology", forecast.metadata)
        self.assertIn("climatology_summary", forecast.metadata)
        self.assertIn("snn_nsstat10", forecast.metadata["climatology_summary"])

    def test_calculate_shore_impacts(self):
        """Test shore impact calculation."""
        # Create a test forecast
        forecast = SwellForecast(forecast_id="test", generated_time=datetime.now().isoformat())

        # Add Hawaii locations
        self.fusion_system._add_hawaii_locations(forecast)

        # Add a test swell event
        event = SwellEvent(
            event_id="test_event",
            start_time=datetime.now().isoformat(),
            peak_time=datetime.now().isoformat(),
            primary_direction=315,  # NW swell (good for North Shore)
            significance=0.7,
            hawaii_scale=15.0,
        )
        forecast.swell_events.append(event)

        # Calculate shore impacts
        self.fusion_system._calculate_shore_impacts(forecast, [self.sample_weather_data])

        # Check that North Shore has higher quality than South Shore
        north_shore = next(loc for loc in forecast.locations if loc.shore.lower() == "north shore")
        south_shore = next(loc for loc in forecast.locations if loc.shore.lower() == "south shore")

        self.assertIn("overall_quality", north_shore.metadata)
        self.assertIn("overall_quality", south_shore.metadata)

        north_quality = north_shore.metadata["overall_quality"]
        south_quality = south_shore.metadata["overall_quality"]

        self.assertGreater(
            north_quality, south_quality, "North Shore should have higher quality for NW swell"
        )

    def test_calculate_confidence_scores(self):
        """Test confidence score calculation."""
        forecast = SwellForecast(forecast_id="test", generated_time=datetime.now().isoformat())

        buoy_data = self.fusion_system._extract_buoy_data(self.sample_fusion_data)
        weather_data = self.fusion_system._extract_weather_data(self.sample_fusion_data)
        model_data = self.fusion_system._extract_model_data(self.sample_fusion_data)

        warnings, metadata = self.fusion_system._calculate_confidence_scores(
            forecast, buoy_data, weather_data, model_data
        )

        self.assertIn("confidence", metadata, "Should have confidence metadata")
        self.assertIn("overall_score", metadata["confidence"], "Should have overall score")
        self.assertIsInstance(
            metadata["confidence"]["overall_score"], float, "Overall score should be a float"
        )

    def test_convert_to_hawaii_scale(self):
        """Test Hawaiian scale conversion."""
        # Test various wave heights with average shore correction (0.75)
        # Hawaiian scale measures back height with refraction/shadowing corrections
        test_cases = [
            (1.0, 2.46),  # 1m × 3.28084 × 0.75 ≈ 2.46ft Hawaiian scale (back height)
            (2.0, 4.92),  # 2m × 3.28084 × 0.75 ≈ 4.92ft
            (3.0, 7.38),  # 3m × 3.28084 × 0.75 ≈ 7.38ft
        ]

        for meters, expected_feet in test_cases:
            result = self.fusion_system._convert_to_hawaii_scale(meters)
            self.assertAlmostEqual(
                result,
                expected_feet,
                places=1,
                msg=f"{meters}m should convert to ~{expected_feet}ft in Hawaiian scale",
            )

        # Test None input
        self.assertIsNone(
            self.fusion_system._convert_to_hawaii_scale(None), "None input should return None"
        )


class TestPatCaldwellCalibration(unittest.TestCase):
    """
    Test _convert_to_surf_height() against Pat Caldwell's Nov 2025 forecast data.

    Source: Pat Caldwell / Surf News Network, Nov 21, 2025
    These tests validate that our conversion produces surf heights
    within acceptable range of Pat's real-world forecasts.
    """

    def setUp(self):
        """Create a DataFusionSystem instance for testing."""
        from src.processing.data_fusion_system import DataFusionSystem

        # Create mock config (following pattern from TestDataFusionSystem)
        self.config = MagicMock(spec=Config)
        self.fusion_system = DataFusionSystem(self.config)

    def test_north_shore_nw_swell_14s(self):
        """
        Pat 11/23: 7ft (2.13m) NNW @ 14s → 10 ft H1/3 surf
        Factor: 1.35 + 0.1*(14-12) = 1.55x
        Expected: 2.13 * 3.28 * 1.55 = 10.8 ft
        """
        result = self.fusion_system._convert_to_surf_height(2.13, "north_shore", period=14)
        self.assertIsNotNone(result, "Should return a value for North Shore 14s swell")
        self.assertGreaterEqual(
            result, 9, f"North Shore 14s swell: expected ≥9ft, got {result:.1f}ft"
        )
        self.assertLessEqual(
            result, 12, f"North Shore 14s swell: expected ≤12ft, got {result:.1f}ft"
        )

    def test_north_shore_nw_swell_16s(self):
        """
        Pat 11/26: 9ft (2.74m) NNW @ 16s → 15 ft H1/3 surf (Big Wednesday!)
        Factor: 1.35 + 0.1*(16-12) = 1.75x
        Expected: 2.74 * 3.28 * 1.75 = 15.7 ft
        """
        result = self.fusion_system._convert_to_surf_height(2.74, "north_shore", period=16)
        self.assertIsNotNone(result, "Should return a value for North Shore 16s swell")
        self.assertGreaterEqual(
            result, 13, f"North Shore 16s swell: expected ≥13ft, got {result:.1f}ft"
        )
        self.assertLessEqual(
            result, 18, f"North Shore 16s swell: expected ≤18ft, got {result:.1f}ft"
        )

    def test_north_shore_nw_swell_13s(self):
        """
        Pat 11/21: 5ft (1.52m) NNW @ 13s → 6 ft H1/3 surf
        Factor: 1.35 + 0.1*(13-12) = 1.45x
        Expected: 1.52 * 3.28 * 1.45 = 7.2 ft
        """
        result = self.fusion_system._convert_to_surf_height(1.52, "north_shore", period=13)
        self.assertIsNotNone(result, "Should return a value for North Shore 13s swell")
        self.assertGreaterEqual(
            result, 5, f"North Shore 13s swell: expected ≥5ft, got {result:.1f}ft"
        )
        self.assertLessEqual(result, 9, f"North Shore 13s swell: expected ≤9ft, got {result:.1f}ft")

    def test_south_shore_sse_swell(self):
        """
        Pat 11/23: 2ft (0.61m) SSE @ 11s → 1 ft H1/3 surf
        Factor: 1.0 (no period bonus for south shore)
        Expected: 0.61 * 3.28 * 1.0 = 2.0 ft
        """
        result = self.fusion_system._convert_to_surf_height(0.61, "south_shore", period=11)
        self.assertIsNotNone(result, "Should return a value for South Shore 11s swell")
        self.assertGreaterEqual(
            result, 1, f"South Shore 11s swell: expected ≥1ft, got {result:.1f}ft"
        )
        self.assertLessEqual(result, 3, f"South Shore 11s swell: expected ≤3ft, got {result:.1f}ft")

    def test_east_shore_trade_swell(self):
        """
        Pat 11/22: 6ft (1.83m) ENE @ 8s → 3 ft H1/3 surf
        Factor: 0.55 (trade swell loses energy)
        Expected: 1.83 * 3.28 * 0.55 = 3.3 ft
        """
        result = self.fusion_system._convert_to_surf_height(1.83, "east_shore", period=8)
        self.assertIsNotNone(result, "Should return a value for East Shore 8s trade swell")
        self.assertGreaterEqual(
            result, 2, f"East Shore 8s trade swell: expected ≥2ft, got {result:.1f}ft"
        )
        self.assertLessEqual(
            result, 5, f"East Shore 8s trade swell: expected ≤5ft, got {result:.1f}ft"
        )

    def test_east_shore_stronger_trade(self):
        """
        Pat 11/21: 8ft (2.44m) ENE @ 8s → 5 ft H1/3 surf
        Factor: 0.55
        Expected: 2.44 * 3.28 * 0.55 = 4.4 ft
        """
        result = self.fusion_system._convert_to_surf_height(2.44, "east_shore", period=8)
        self.assertIsNotNone(result, "Should return a value for East Shore stronger trade")
        self.assertGreaterEqual(
            result, 3, f"East Shore stronger trade: expected ≥3ft, got {result:.1f}ft"
        )
        self.assertLessEqual(
            result, 6, f"East Shore stronger trade: expected ≤6ft, got {result:.1f}ft"
        )

    def test_west_shore_nw_wrap(self):
        """
        West shore receives wrapped NW swell with some energy loss.
        Test: 2.5m @ 14s
        Factor: 0.9 + 0.05*(14-12) = 1.0x
        Expected: 2.5 * 3.28 * 1.0 = 8.2 ft
        """
        result = self.fusion_system._convert_to_surf_height(2.5, "west_shore", period=14)
        self.assertIsNotNone(result, "Should return a value for West Shore NW wrap")
        self.assertGreaterEqual(result, 7, f"West Shore NW wrap: expected ≥7ft, got {result:.1f}ft")
        self.assertLessEqual(result, 10, f"West Shore NW wrap: expected ≤10ft, got {result:.1f}ft")

    def test_default_no_shore(self):
        """
        When no shore specified, use 1.0x factor (no adjustment).
        Test: 2.0m deepwater → 6.56 ft
        """
        result = self.fusion_system._convert_to_surf_height(2.0, shore=None, period=14)
        self.assertIsNotNone(result, "Should return a value for default (no shore)")
        self.assertGreaterEqual(result, 6, f"Default (no shore): expected ≥6ft, got {result:.1f}ft")
        self.assertLessEqual(result, 7, f"Default (no shore): expected ≤7ft, got {result:.1f}ft")

    def test_none_input(self):
        """None input should return None."""
        result = self.fusion_system._convert_to_surf_height(None, "north_shore", period=14)
        self.assertIsNone(result, "None input should return None")


if __name__ == "__main__":
    unittest.main()
