"""
Unit tests for the DataFusionSystem.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path
import sys
import os
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.processing.data_fusion_system import DataFusionSystem
from src.processing.models.buoy_data import BuoyData, BuoyObservation
from src.processing.models.weather_data import WeatherData, WeatherPeriod
from src.processing.models.wave_model import ModelData, ModelForecast, ModelPoint
from src.processing.models.swell_event import SwellEvent, SwellComponent, SwellForecast
from src.core.config import Config


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
                    wind_direction=45
                )
            ],
            metadata={}
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
                    short_forecast="Partly Sunny"
                )
            ],
            metadata={
                "wind_analysis": {
                    "shore_impacts": {
                        "north_shore": {"overall_rating": 0.8},
                        "south_shore": {"overall_rating": 0.3}
                    }
                }
            }
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
                            wave_direction=320
                        )
                    ]
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
                        "hawaii_scale": 19.7
                    }
                ]
            }
        )
        
        # Sample fusion input data
        self.sample_fusion_data = {
            "metadata": {
                "forecast_id": "test_forecast",
                "region": "hawaii"
            },
            "buoy_data": [self.sample_buoy_data],
            "weather_data": [self.sample_weather_data],
            "model_data": [self.sample_model_data]
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
        self.assertGreaterEqual(len(forecast.locations), 4, "Should have at least 4 Hawaii locations")
        
        # Check swell events
        self.assertGreaterEqual(len(forecast.swell_events), 1, "Should have at least 1 swell event")
        
        # Check metadata
        self.assertIn('confidence', forecast.metadata, "Should have confidence metadata")
    
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
    
    def test_calculate_shore_impacts(self):
        """Test shore impact calculation."""
        # Create a test forecast
        forecast = SwellForecast(
            forecast_id="test",
            generated_time=datetime.now().isoformat()
        )
        
        # Add Hawaii locations
        self.fusion_system._add_hawaii_locations(forecast)
        
        # Add a test swell event
        event = SwellEvent(
            event_id="test_event",
            start_time=datetime.now().isoformat(),
            peak_time=datetime.now().isoformat(),
            primary_direction=315,  # NW swell (good for North Shore)
            significance=0.7,
            hawaii_scale=15.0
        )
        forecast.swell_events.append(event)
        
        # Calculate shore impacts
        self.fusion_system._calculate_shore_impacts(forecast, [self.sample_weather_data])
        
        # Check that North Shore has higher quality than South Shore
        north_shore = next(l for l in forecast.locations if l.shore.lower() == "north shore")
        south_shore = next(l for l in forecast.locations if l.shore.lower() == "south shore")
        
        self.assertIn('overall_quality', north_shore.metadata)
        self.assertIn('overall_quality', south_shore.metadata)
        
        north_quality = north_shore.metadata['overall_quality']
        south_quality = south_shore.metadata['overall_quality']
        
        self.assertGreater(north_quality, south_quality, 
                          "North Shore should have higher quality for NW swell")
    
    def test_calculate_confidence_scores(self):
        """Test confidence score calculation."""
        forecast = SwellForecast(
            forecast_id="test",
            generated_time=datetime.now().isoformat()
        )
        
        buoy_data = self.fusion_system._extract_buoy_data(self.sample_fusion_data)
        weather_data = self.fusion_system._extract_weather_data(self.sample_fusion_data)
        model_data = self.fusion_system._extract_model_data(self.sample_fusion_data)
        
        warnings, metadata = self.fusion_system._calculate_confidence_scores(
            forecast, buoy_data, weather_data, model_data
        )
        
        self.assertIn('confidence', metadata, "Should have confidence metadata")
        self.assertIn('overall_score', metadata['confidence'], "Should have overall score")
        self.assertIsInstance(metadata['confidence']['overall_score'], float, 
                             "Overall score should be a float")
    
    def test_convert_to_hawaii_scale(self):
        """Test Hawaiian scale conversion."""
        # Test various wave heights
        test_cases = [
            (1.0, 6.56),   # 1m ≈ 6.56ft face
            (2.0, 13.12),  # 2m ≈ 13.12ft face
            (3.0, 19.68)   # 3m ≈ 19.68ft face
        ]
        
        for meters, expected_feet in test_cases:
            result = self.fusion_system._convert_to_hawaii_scale(meters)
            self.assertAlmostEqual(result, expected_feet, places=1, 
                msg=f"{meters}m should convert to ~{expected_feet}ft in Hawaiian scale")
        
        # Test None input
        self.assertIsNone(self.fusion_system._convert_to_hawaii_scale(None),
                         "None input should return None")


if __name__ == '__main__':
    unittest.main()
