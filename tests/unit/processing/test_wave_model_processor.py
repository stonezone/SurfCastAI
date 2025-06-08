"""
Unit tests for the WaveModelProcessor.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.processing.wave_model_processor import WaveModelProcessor
from src.processing.models.wave_model import ModelData, ModelForecast, ModelPoint
from src.core.config import Config


class TestWaveModelProcessor(unittest.TestCase):
    """Tests for the WaveModelProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock config
        self.config = MagicMock(spec=Config)
        
        # Create processor
        self.processor = WaveModelProcessor(self.config)
        
        # Sample SWAN model data
        self.sample_swan_data = {
            "metadata": {
                "model": "SWAN",
                "region": "hawaii",
                "run_time": "2023-01-01T00:00:00Z",
                "forecast_hours": 72
            },
            "forecasts": [
                {
                    "hour": 0,
                    "timestamp": "2023-01-01T00:00:00Z",
                    "points": [
                        {
                            "lat": 21.6, "lon": -158.1,
                            "hs": 2.5, "tp": 12.0, "dir": 315,
                            "wind_speed": 5.0, "wind_dir": 45
                        },
                        {
                            "lat": 21.5, "lon": -158.0,
                            "hs": 2.3, "tp": 12.0, "dir": 310,
                            "wind_speed": 5.0, "wind_dir": 50
                        }
                    ]
                },
                {
                    "hour": 6,
                    "timestamp": "2023-01-01T06:00:00Z",
                    "points": [
                        {
                            "lat": 21.6, "lon": -158.1,
                            "hs": 2.8, "tp": 13.0, "dir": 315,
                            "wind_speed": 4.5, "wind_dir": 40
                        },
                        {
                            "lat": 21.5, "lon": -158.0,
                            "hs": 2.6, "tp": 13.0, "dir": 310,
                            "wind_speed": 4.5, "wind_dir": 45
                        }
                    ]
                },
                {
                    "hour": 12,
                    "timestamp": "2023-01-01T12:00:00Z",
                    "points": [
                        {
                            "lat": 21.6, "lon": -158.1,
                            "hs": 3.0, "tp": 14.0, "dir": 320,
                            "wind_speed": 4.0, "wind_dir": 35
                        },
                        {
                            "lat": 21.5, "lon": -158.0,
                            "hs": 2.8, "tp": 14.0, "dir": 315,
                            "wind_speed": 4.0, "wind_dir": 40
                        }
                    ]
                }
            ]
        }
        
        # Sample WW3 model data
        self.sample_ww3_data = {
            "header": {
                "model": "WaveWatch III",
                "refTime": "2023-01-01T00:00:00Z",
                "area": "north_pacific"
            },
            "data": [
                {
                    "timestamp": "2023-01-01T00:00:00Z",
                    "forecastHour": 0,
                    "grid": [
                        {
                            "lat": 21.6, "lon": -158.1,
                            "hs": 2.5, "tp": 12.0, "dir": 315,
                            "ws": 5.0, "wd": 45
                        },
                        {
                            "lat": 21.5, "lon": -158.0,
                            "hs": 2.3, "tp": 12.0, "dir": 310,
                            "ws": 5.0, "wd": 50
                        }
                    ]
                },
                {
                    "timestamp": "2023-01-01T06:00:00Z",
                    "forecastHour": 6,
                    "grid": [
                        {
                            "lat": 21.6, "lon": -158.1,
                            "hs": 2.8, "tp": 13.0, "dir": 315,
                            "ws": 4.5, "wd": 40
                        },
                        {
                            "lat": 21.5, "lon": -158.0,
                            "hs": 2.6, "tp": 13.0, "dir": 310,
                            "ws": 4.5, "wd": 45
                        }
                    ]
                }
            ]
        }
    
    def test_validate_valid_swan_data(self):
        """Test validation with valid SWAN data."""
        errors = self.processor.validate(self.sample_swan_data)
        self.assertEqual(len(errors), 0, "Should not have validation errors")
    
    def test_validate_valid_ww3_data(self):
        """Test validation with valid WW3 data."""
        errors = self.processor.validate(self.sample_ww3_data)
        self.assertEqual(len(errors), 0, "Should not have validation errors")
    
    def test_validate_invalid_data(self):
        """Test validation with invalid data."""
        # Test missing forecasts
        invalid_data = {"metadata": {"model": "SWAN"}, "forecasts": []}
        errors = self.processor.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")
        
        # Test unknown format
        invalid_data = {"wrong_key": "value"}
        errors = self.processor.validate(invalid_data)
        self.assertGreater(len(errors), 0, "Should have validation errors")
    
    def test_process_swan_data(self):
        """Test processing with SWAN data."""
        result = self.processor.process(self.sample_swan_data)
        
        # Check success
        self.assertTrue(result.success, "Processing should succeed")
        self.assertIsNone(result.error, "Should not have error")
        
        # Check data type
        self.assertIsInstance(result.data, ModelData, "Result should be ModelData")
        
        # Check basic properties
        model_data = result.data
        self.assertEqual(model_data.model_id, 'swan', "Model ID should be 'swan'")
        self.assertEqual(model_data.region, 'hawaii', "Region should be 'hawaii'")
        self.assertEqual(len(model_data.forecasts), 3, "Should have 3 forecasts")
        
        # Check metadata
        self.assertIn('analysis', model_data.metadata, "Should have analysis metadata")
        self.assertIn('shore_analysis', model_data.metadata, "Should have shore analysis metadata")
        self.assertIn('swell_events', model_data.metadata, "Should have swell events metadata")
    
    def test_process_ww3_data(self):
        """Test processing with WW3 data."""
        result = self.processor.process(self.sample_ww3_data)
        
        # Check success
        self.assertTrue(result.success, "Processing should succeed")
        
        # Check data type
        self.assertIsInstance(result.data, ModelData, "Result should be ModelData")
        
        # Check basic properties
        model_data = result.data
        self.assertEqual(model_data.model_id, 'ww3', "Model ID should be 'ww3'")
        self.assertEqual(model_data.region, 'north_pacific', "Region should be 'north_pacific'")
        self.assertEqual(len(model_data.forecasts), 2, "Should have 2 forecasts")
    
    def test_clean_forecasts(self):
        """Test forecast cleaning."""
        # Create test model data with some invalid points
        forecasts = [
            ModelForecast(
                timestamp="2023-01-01T00:00:00Z",
                forecast_hour=0,
                points=[
                    ModelPoint(latitude=21.6, longitude=-158.1, wave_height=2.5, wave_period=12.0),
                    ModelPoint(latitude=21.5, longitude=-158.0, wave_height=-1.0, wave_period=12.0),  # Invalid height
                    ModelPoint(latitude=21.4, longitude=-157.9, wave_height=2.3, wave_period=-5.0)   # Invalid period
                ]
            )
        ]
        
        model_data = ModelData(
            model_id="test",
            run_time="2023-01-01T00:00:00Z",
            region="test",
            forecasts=forecasts
        )
        
        # Clean forecasts
        result = self.processor._clean_forecasts(model_data)
        
        # Check cleaned points
        self.assertEqual(len(result.forecasts), 1, "Should still have 1 forecast")
        self.assertEqual(len(result.forecasts[0].points), 2, "Should have 2 valid points")
        
        # Check invalid point was removed
        heights = [p.wave_height for p in result.forecasts[0].points]
        self.assertNotIn(-1.0, heights, "Negative height should be removed")
        
        # Check invalid period was set to None
        for point in result.forecasts[0].points:
            if point.wave_height == 2.3:
                self.assertIsNone(point.wave_period, "Invalid period should be set to None")
    
    def test_detect_swell_events(self):
        """Test swell event detection."""
        # Create model data with a clear swell event
        forecasts = []
        # Create a rise-peak-fall pattern
        for hour in range(0, 36, 6):
            # Wave height follows a pattern: starts at 1.5, peaks at 3.0, then falls
            if hour <= 18:
                wave_height = 1.5 + (hour / 18) * 1.5  # Rising to peak at hour 18
            else:
                wave_height = 3.0 - ((hour - 18) / 18) * 1.5  # Falling after peak
            
            forecasts.append(
                ModelForecast(
                    timestamp=f"2023-01-01T{hour:02d}:00:00Z",
                    forecast_hour=hour,
                    points=[
                        ModelPoint(
                            latitude=21.6, 
                            longitude=-158.1, 
                            wave_height=wave_height, 
                            wave_period=12.0, 
                            wave_direction=315
                        )
                    ]
                )
            )
        
        model_data = ModelData(
            model_id="test",
            run_time="2023-01-01T00:00:00Z",
            region="test",
            forecasts=forecasts
        )
        
        # Detect swell events
        events = self.processor._detect_swell_events(model_data)
        
        # Check event detection
        self.assertGreaterEqual(len(events), 1, "Should detect at least one event")
        
        # Check peak time
        peak_event = events[0]
        self.assertEqual(peak_event['peak_hour'], 18, "Peak should be at hour 18")
        self.assertAlmostEqual(peak_event['peak_height'], 3.0, places=1, msg="Peak height should be about 3.0")
    
    def test_hawaii_scale_conversion(self):
        """Test Hawaiian scale conversion."""
        # Test various wave heights
        test_cases = [
            (1.0, 6.56),   # 1m ≈ 6.56ft face
            (2.0, 13.12),  # 2m ≈ 13.12ft face
            (3.0, 19.68)   # 3m ≈ 19.68ft face
        ]
        
        for meters, expected_feet in test_cases:
            result = self.processor.get_hawaii_scale(meters)
            self.assertAlmostEqual(result, expected_feet, places=1, 
                msg=f"{meters}m should convert to ~{expected_feet}ft in Hawaiian scale")


if __name__ == '__main__':
    unittest.main()
