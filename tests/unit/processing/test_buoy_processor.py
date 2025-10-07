"""
Unit tests for the BuoyProcessor with enhanced trend analysis.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.processing.buoy_processor import BuoyProcessor
from src.processing.models.buoy_data import BuoyData, BuoyObservation
from src.core.config import Config


class TestBuoyProcessor(unittest.TestCase):
    """Tests for the BuoyProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock config
        self.config = MagicMock(spec=Config)

        # Create processor
        self.processor = BuoyProcessor(self.config)

    def _create_sample_buoy_data(self, num_observations=24, wave_height=2.0):
        """Create sample buoy data for testing."""
        observations = []
        now = datetime.now()

        for i in range(num_observations):
            timestamp = now - timedelta(hours=i)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=wave_height,
                dominant_period=12.0,
                average_period=10.0,
                wave_direction=315.0,
                wind_speed=5.0,
                wind_direction=45.0,
                water_temperature=20.0
            )
            observations.append(obs)

        return BuoyData(
            station_id='51001',
            name='NW Hawaii',
            latitude=23.4,
            longitude=-162.3,
            observations=observations
        )

    def test_detect_trend_increasing(self):
        """Test trend detection with increasing wave heights."""
        # Create buoy data with increasing trend
        observations = []
        now = datetime.now()

        for i in range(24):
            timestamp = now - timedelta(hours=i)
            # Wave height increases from 1.0 to 3.0 meters over 24 hours
            wave_height = 3.0 - (i * 2.0 / 23.0)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=wave_height,
                dominant_period=12.0,
                wave_direction=315.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Detect trend
        trend_info = self.processor.detect_trend(buoy_data, hours=24)

        # Check results
        self.assertEqual(trend_info['direction'], 'increasing')
        self.assertGreater(trend_info['slope'], 0.2)  # Above threshold
        self.assertGreater(trend_info['confidence'], 0.5)
        self.assertGreater(trend_info['r_squared'], 0.7)
        self.assertEqual(trend_info['sample_size'], 24)

    def test_detect_trend_decreasing(self):
        """Test trend detection with decreasing wave heights."""
        # Create buoy data with decreasing trend
        observations = []
        now = datetime.now()

        for i in range(24):
            timestamp = now - timedelta(hours=i)
            # Wave height decreases from 3.0 to 1.0 meters over 24 hours
            wave_height = 1.0 + (i * 2.0 / 23.0)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=wave_height,
                dominant_period=12.0,
                wave_direction=315.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Detect trend
        trend_info = self.processor.detect_trend(buoy_data, hours=24)

        # Check results
        self.assertEqual(trend_info['direction'], 'decreasing')
        self.assertLess(trend_info['slope'], -0.2)  # Below threshold
        self.assertGreater(trend_info['confidence'], 0.5)

    def test_detect_trend_stable(self):
        """Test trend detection with stable wave heights."""
        buoy_data = self._create_sample_buoy_data(num_observations=24, wave_height=2.0)

        # Detect trend
        trend_info = self.processor.detect_trend(buoy_data, hours=24)

        # Check results
        self.assertEqual(trend_info['direction'], 'stable')
        self.assertLess(abs(trend_info['slope']), 0.2)  # Below threshold

    def test_detect_trend_insufficient_data(self):
        """Test trend detection with insufficient data."""
        buoy_data = self._create_sample_buoy_data(num_observations=2, wave_height=2.0)

        # Detect trend
        trend_info = self.processor.detect_trend(buoy_data, hours=24)

        # Check results
        self.assertEqual(trend_info['direction'], 'unknown')
        self.assertEqual(trend_info['confidence'], 0.0)
        self.assertEqual(trend_info['sample_size'], 2)

    def test_detect_anomalies_with_outliers(self):
        """Test anomaly detection with outliers."""
        # Create buoy data with normal values and a few outliers
        observations = []
        now = datetime.now()

        for i in range(24):
            timestamp = now - timedelta(hours=i)
            # Normal wave height around 2.0, but add outliers at specific positions
            if i == 5:
                wave_height = 6.0  # Outlier - very high
            elif i == 15:
                wave_height = 0.2  # Outlier - very low
            else:
                wave_height = 2.0 + (i % 3 - 1) * 0.2  # Normal variation

            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=wave_height,
                dominant_period=12.0,
                wave_direction=315.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Detect anomalies
        anomaly_info = self.processor.detect_anomalies(buoy_data, threshold=2.0)

        # Check results
        self.assertGreater(anomaly_info['anomaly_count'], 0)
        self.assertEqual(len(anomaly_info['anomalies']), anomaly_info['anomaly_count'])
        self.assertGreater(anomaly_info['mean_height'], 0)
        self.assertGreater(anomaly_info['std_height'], 0)
        self.assertEqual(len(anomaly_info['z_scores']), 24)

    def test_detect_anomalies_no_outliers(self):
        """Test anomaly detection with no outliers."""
        buoy_data = self._create_sample_buoy_data(num_observations=24, wave_height=2.0)

        # Detect anomalies
        anomaly_info = self.processor.detect_anomalies(buoy_data, threshold=2.0)

        # Check results
        self.assertEqual(anomaly_info['anomaly_count'], 0)
        self.assertEqual(len(anomaly_info['anomalies']), 0)

    def test_detect_anomalies_insufficient_data(self):
        """Test anomaly detection with insufficient data."""
        buoy_data = self._create_sample_buoy_data(num_observations=2, wave_height=2.0)

        # Detect anomalies
        anomaly_info = self.processor.detect_anomalies(buoy_data, threshold=2.0)

        # Check results
        self.assertEqual(anomaly_info['anomaly_count'], 0)
        self.assertEqual(anomaly_info['sample_size'], 2)

    def test_calculate_quality_score_fresh_complete(self):
        """Test quality score calculation with fresh, complete data."""
        # Create fresh data (within 1 hour)
        observations = []
        now = datetime.now()

        for i in range(12):
            timestamp = now - timedelta(minutes=i * 5)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=2.0,
                dominant_period=12.0,
                average_period=10.0,
                wave_direction=315.0,
                wind_speed=5.0,
                wind_direction=45.0,
                water_temperature=20.0,
                air_temperature=22.0,
                pressure=1013.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Calculate quality score
        quality_info = self.processor.calculate_quality_score(buoy_data)

        # Check results - should have high scores
        self.assertGreater(quality_info['freshness_score'], 0.9)
        self.assertGreater(quality_info['completeness_score'], 0.8)
        self.assertGreater(quality_info['consistency_score'], 0.9)
        self.assertGreater(quality_info['overall_score'], 0.8)

    def test_calculate_quality_score_old_data(self):
        """Test quality score calculation with old data."""
        # Create old data (6+ hours old)
        observations = []
        now = datetime.now()

        for i in range(12):
            timestamp = now - timedelta(hours=8 + i)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=2.0,
                dominant_period=12.0,
                wave_direction=315.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Calculate quality score
        quality_info = self.processor.calculate_quality_score(buoy_data)

        # Check results - freshness should be very low
        self.assertLess(quality_info['freshness_score'], 0.2)
        self.assertLess(quality_info['overall_score'], 0.6)

    def test_calculate_quality_score_incomplete_data(self):
        """Test quality score calculation with incomplete data."""
        # Create data with missing fields
        observations = []
        now = datetime.now()

        for i in range(12):
            timestamp = now - timedelta(minutes=i * 5)
            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=2.0,
                # Missing dominant_period, wave_direction, etc.
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Calculate quality score
        quality_info = self.processor.calculate_quality_score(buoy_data)

        # Check results - completeness should be low
        self.assertLess(quality_info['completeness_score'], 0.6)

    def test_calculate_quality_score_inconsistent_data(self):
        """Test quality score calculation with inconsistent data (sudden jumps)."""
        # Create data with sudden jumps
        observations = []
        now = datetime.now()

        for i in range(12):
            timestamp = now - timedelta(minutes=i * 5)
            # Add sudden jumps every few observations
            if i % 4 == 0:
                wave_height = 5.0  # Sudden jump
            else:
                wave_height = 2.0

            obs = BuoyObservation(
                timestamp=timestamp.isoformat(),
                wave_height=wave_height,
                dominant_period=12.0,
                wave_direction=315.0
            )
            observations.append(obs)

        buoy_data = BuoyData(
            station_id='51001',
            name='Test Buoy',
            observations=observations
        )

        # Calculate quality score
        quality_info = self.processor.calculate_quality_score(buoy_data)

        # Check results - consistency should be reduced
        self.assertLess(quality_info['consistency_score'], 0.8)

    def test_process_integration(self):
        """Test that enhanced methods are integrated into process()."""
        # Create sample buoy data in the format expected by process()
        buoy_json = {
            'station_id': '51001',
            'name': 'Test Buoy',
            'observations': []
        }

        now = datetime.now()
        for i in range(24):
            timestamp = now - timedelta(hours=i)
            buoy_json['observations'].append({
                'timestamp': timestamp.isoformat(),
                'wave_height': 2.0 + (i * 0.1),  # Slight increasing trend
                'dominant_period': 12.0,
                'wave_direction': 315.0
            })

        # Process the data
        result = self.processor.process(buoy_json)

        # Check that processing succeeded
        self.assertTrue(result.success)
        self.assertIsNone(result.error)

        # Check that enhanced metadata is present
        self.assertIn('analysis', result.data.metadata)
        analysis = result.data.metadata['analysis']

        # Check for trend information
        self.assertIn('trends', analysis)
        self.assertIn('direction', analysis['trends'])

        # Check for anomaly information
        self.assertIn('anomalies', analysis)
        self.assertIn('anomaly_count', analysis['anomalies'])

        # Check for quality information
        self.assertIn('quality_details', analysis)
        self.assertIn('overall_score', analysis['quality_details'])

        # Check for weight (for data fusion)
        self.assertIn('weight', analysis)
        self.assertGreater(analysis['weight'], 0.0)

    def test_process_with_anomalies_generates_warnings(self):
        """Test that anomalies generate appropriate warnings."""
        # Create buoy data with outliers
        buoy_json = {
            'station_id': '51001',
            'name': 'Test Buoy',
            'observations': []
        }

        now = datetime.now()
        for i in range(24):
            timestamp = now - timedelta(hours=i)
            # Add an outlier
            wave_height = 10.0 if i == 12 else 2.0

            buoy_json['observations'].append({
                'timestamp': timestamp.isoformat(),
                'wave_height': wave_height,
                'dominant_period': 12.0,
                'wave_direction': 315.0
            })

        # Process the data
        result = self.processor.process(buoy_json)

        # Check for warnings about anomalies
        self.assertTrue(result.success)
        self.assertGreater(len(result.warnings), 0)
        # Check that at least one warning mentions anomalies
        anomaly_warning = any('anomalous' in warning.lower() for warning in result.warnings)
        self.assertTrue(anomaly_warning)

    def test_hawaii_scale_conversion(self):
        """Test Hawaiian scale conversion."""
        # Test various wave heights
        test_cases = [
            (1.0, 3.28084),   # 1m ≈ 3.28ft (back height)
            (2.0, 6.56168),   # 2m ≈ 6.56ft
            (3.0, 9.84252)    # 3m ≈ 9.84ft
        ]

        for meters, expected_feet in test_cases:
            result = self.processor.get_hawaii_scale(meters)
            self.assertAlmostEqual(result, expected_feet, places=2,
                msg=f"{meters}m should convert to ~{expected_feet}ft in Hawaiian scale")


if __name__ == '__main__':
    unittest.main()
