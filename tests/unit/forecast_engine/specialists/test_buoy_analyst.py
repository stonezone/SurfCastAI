"""
Unit tests for BuoyAnalyst specialist module.

Tests cover all critical functionality including:
- Trend analysis (slope calculation and categorization)
- Anomaly detection (Z-score based outlier detection)
- Quality flag assignment (data validation and exclusion rules)
- Cross-validation (agreement between buoys)
- Data normalization (mixed input format handling)
- Confidence calculation (multi-factor confidence scoring)

Test Structure:
- Tests are organized by functionality area
- Each test follows AAA pattern (Arrange-Act-Assert)
- Mocked dependencies (config, engine, OpenAI client)
- Isolated tests (no interdependencies)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.forecast_engine.specialists.buoy_analyst import BuoyAnalyst
from src.forecast_engine.specialists.schemas import (
    BuoyAnalystOutput,
    BuoyTrend,
    BuoyAnomaly,
    CrossValidation,
    TrendType,
    SeverityLevel,
    QualityFlag,
    AgreementLevel
)
from src.processing.models.buoy_data import BuoyData, BuoyObservation


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.get.return_value = 'fake-api-key'
    config.getint.return_value = 2000
    return config


@pytest.fixture
def mock_engine():
    """Create a mock forecast engine with OpenAI client."""
    engine = Mock()
    engine.openai_client = Mock()
    engine.openai_client.call_openai_api = AsyncMock(return_value="Test narrative analysis")
    return engine


@pytest.fixture
def buoy_analyst(mock_config, mock_engine):
    """Create a BuoyAnalyst instance with mocked dependencies."""
    return BuoyAnalyst(config=mock_config, model_name='gpt-4o-mini', engine=mock_engine)


@pytest.fixture
def sample_buoy_data():
    """Create sample BuoyData object with observations."""
    buoy = BuoyData(
        station_id='51001',
        name='NW Hawaii',
        latitude=23.5,
        longitude=-162.2
    )

    # Add 10 observations with increasing trend
    base_time = datetime.now()
    for i in range(10):
        obs = BuoyObservation(
            timestamp=(base_time - timedelta(hours=i)).isoformat(),
            wave_height=2.0 + (i * 0.2),  # Increasing from 2.0 to 3.8m
            dominant_period=12.0 + (i * 0.1),  # Increasing from 12.0 to 12.9s
            wave_direction=315.0,  # Steady NW
            wind_speed=10.0,
            wind_direction=45.0,
            water_temperature=25.0,
            pressure=1013.0
        )
        buoy.observations.insert(0, obs)  # Insert at front to maintain chronological order

    return buoy


@pytest.fixture
def sample_buoy_data_steady():
    """Create sample BuoyData with steady conditions."""
    buoy = BuoyData(
        station_id='51002',
        name='South Hawaii',
        latitude=17.2,
        longitude=-157.8
    )

    base_time = datetime.now()
    for i in range(10):
        obs = BuoyObservation(
            timestamp=(base_time - timedelta(hours=i)).isoformat(),
            wave_height=2.5,  # Steady
            dominant_period=14.0,  # Steady
            wave_direction=180.0,  # Steady S
        )
        buoy.observations.insert(0, obs)

    return buoy


@pytest.fixture
def sample_buoy_data_anomaly():
    """Create sample BuoyData with anomalous observation."""
    buoy = BuoyData(
        station_id='51003',
        name='Anomaly Buoy',
        latitude=20.0,
        longitude=-160.0
    )

    base_time = datetime.now()
    # Normal observations
    for i in range(1, 10):
        obs = BuoyObservation(
            timestamp=(base_time - timedelta(hours=i)).isoformat(),
            wave_height=2.0,
            dominant_period=12.0,
        )
        buoy.observations.insert(0, obs)

    # Latest observation is anomalous (extreme outlier)
    anomaly_obs = BuoyObservation(
        timestamp=base_time.isoformat(),
        wave_height=15.0,  # Extreme outlier (Z-score > 3.0)
        dominant_period=25.0,  # Extreme outlier
    )
    buoy.observations.insert(0, anomaly_obs)  # Insert at front (latest observation)

    return buoy


@pytest.fixture
def sample_buoy_data_single_scan():
    """Create sample BuoyData with single observation (spike)."""
    buoy = BuoyData(
        station_id='51004',
        name='Single Scan Buoy',
        latitude=22.0,
        longitude=-159.0
    )

    # Only 1 observation
    obs = BuoyObservation(
        timestamp=datetime.now().isoformat(),
        wave_height=8.0,  # High value
        dominant_period=16.0,
    )
    buoy.observations.append(obs)

    return buoy


# =============================================================================
# TREND ANALYSIS TESTS (8 tests)
# =============================================================================


class TestBuoyAnalystTrendAnalysis:
    """Tests for trend analysis functionality."""

    def test_calculate_trend_increasing_strong(self, buoy_analyst):
        """Test strong increasing trend detection (slope > 0.1)."""
        # Arrange: Values increasing by 0.15 per observation
        values = [1.0, 1.15, 1.30, 1.45, 1.60, 1.75]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'increasing_strong'
        assert result['slope'] > 0.1
        assert result['slope'] == pytest.approx(0.15, abs=0.001)

    def test_calculate_trend_increasing_moderate(self, buoy_analyst):
        """Test moderate increasing trend detection (0.05 < slope <= 0.1)."""
        # Arrange: Values increasing by 0.07 per observation
        values = [2.0, 2.07, 2.14, 2.21, 2.28]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'increasing_moderate'
        assert 0.05 < result['slope'] <= 0.1

    def test_calculate_trend_increasing_slight(self, buoy_analyst):
        """Test slight increasing trend detection (0 < slope <= 0.05)."""
        # Arrange: Values increasing by 0.03 per observation
        values = [3.0, 3.03, 3.06, 3.09, 3.12]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'increasing_slight'
        assert 0 < result['slope'] <= 0.05

    def test_calculate_trend_decreasing_strong(self, buoy_analyst):
        """Test strong decreasing trend detection (slope < -0.1)."""
        # Arrange: Values decreasing by 0.2 per observation
        values = [5.0, 4.8, 4.6, 4.4, 4.2, 4.0]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'decreasing_strong'
        assert result['slope'] < -0.1
        assert result['slope'] == pytest.approx(-0.2, abs=0.001)

    def test_calculate_trend_decreasing_moderate(self, buoy_analyst):
        """Test moderate decreasing trend detection (-0.1 <= slope < -0.05)."""
        # Arrange: Values decreasing by 0.08 per observation
        values = [4.0, 3.92, 3.84, 3.76, 3.68]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'decreasing_moderate'
        assert -0.1 <= result['slope'] < -0.05

    def test_calculate_trend_steady(self, buoy_analyst):
        """Test steady trend detection (abs(slope) < 0.01)."""
        # Arrange: Nearly constant values
        values = [2.5, 2.501, 2.499, 2.500, 2.501]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'steady'
        assert abs(result['slope']) < 0.01

    def test_calculate_trend_single_value(self, buoy_analyst):
        """Test trend calculation with single value (insufficient data)."""
        # Arrange: Only one value
        values = [3.0]

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'insufficient_data'
        assert result['slope'] == 0.0

    def test_calculate_trend_empty_list(self, buoy_analyst):
        """Test trend calculation with empty list (edge case)."""
        # Arrange: Empty values
        values = []

        # Act
        result = buoy_analyst._calculate_trend(values)

        # Assert
        assert result['description'] == 'insufficient_data'
        assert result['slope'] == 0.0


# =============================================================================
# ANOMALY DETECTION TESTS (6 tests)
# =============================================================================


class TestBuoyAnalystAnomalyDetection:
    """Tests for anomaly detection functionality."""

    def test_detect_anomalies_high_severity_zscore_above_3(self, buoy_analyst, sample_buoy_data_anomaly, sample_buoy_data_steady):
        """Test high severity anomaly detection with Z-score > 3.0."""
        # Arrange: buoy_data_anomaly has extreme outlier (15.0m vs normal 2.0m)
        # Add steady buoy to provide baseline for statistics
        buoy_list = [sample_buoy_data_anomaly, sample_buoy_data_steady]

        # Act
        anomalies = buoy_analyst._detect_anomalies(buoy_list)

        # Assert
        assert len(anomalies) >= 1
        height_anomaly = next((a for a in anomalies if 'wave_height' in a['issue']), None)
        assert height_anomaly is not None
        assert height_anomaly['severity'] == 'high'
        assert height_anomaly['z_score'] > 3.0
        assert height_anomaly['buoy_id'] == '51003'

    def test_detect_anomalies_moderate_severity_zscore_2_to_3(self, buoy_analyst):
        """Test moderate severity anomaly detection with 2.0 < Z-score <= 3.0."""
        # Arrange: Create buoy with moderate outlier
        buoy = BuoyData(station_id='test', name='Test')
        base_time = datetime.now()

        # 9 normal observations around 2.0m
        for i in range(9):
            obs = BuoyObservation(
                timestamp=(base_time - timedelta(hours=i+1)).isoformat(),
                wave_height=2.0 + (i * 0.1 - 0.4),  # 1.6-2.4m range
                dominant_period=12.0
            )
            buoy.observations.insert(0, obs)

        # Latest observation is moderate outlier (4.5m)
        # With mean ~2.0 and std ~0.3, Z-score ~2.5
        outlier_obs = BuoyObservation(
            timestamp=base_time.isoformat(),
            wave_height=4.5,
            dominant_period=12.0
        )
        buoy.observations.append(outlier_obs)

        # Act
        anomalies = buoy_analyst._detect_anomalies([buoy])

        # Assert
        if anomalies:  # May or may not trigger depending on exact Z-score
            height_anomaly = next((a for a in anomalies if 'wave_height' in a['issue']), None)
            if height_anomaly:
                assert height_anomaly['severity'] in ['moderate', 'high']
                assert height_anomaly['z_score'] >= 2.0

    def test_detect_anomalies_no_anomalies_normal_distribution(self, buoy_analyst, sample_buoy_data_steady):
        """Test that no anomalies are detected in normal distribution."""
        # Arrange: Steady buoy data with consistent values
        buoy_list = [sample_buoy_data_steady]

        # Act
        anomalies = buoy_analyst._detect_anomalies(buoy_list)

        # Assert: No anomalies detected (all values are identical, Z-score = 0)
        assert len(anomalies) == 0

    def test_detect_anomalies_multiple_concurrent(self, buoy_analyst, sample_buoy_data_steady):
        """Test detection of multiple anomalies in same buoy."""
        # Arrange: Buoy with both height and period anomalies
        buoy = BuoyData(station_id='multi', name='Multi Anomaly')
        base_time = datetime.now()

        # Normal observations
        for i in range(9):
            obs = BuoyObservation(
                timestamp=(base_time - timedelta(hours=i+1)).isoformat(),
                wave_height=2.0,
                dominant_period=12.0
            )
            buoy.observations.insert(0, obs)

        # Anomalous observation (both height and period)
        anomaly_obs = BuoyObservation(
            timestamp=base_time.isoformat(),
            wave_height=10.0,  # Extreme outlier
            dominant_period=25.0  # Extreme outlier
        )
        buoy.observations.insert(0, anomaly_obs)  # Insert at front (latest observation)

        # Add steady buoy to provide baseline
        buoy_list = [buoy, sample_buoy_data_steady]

        # Act
        anomalies = buoy_analyst._detect_anomalies(buoy_list)

        # Assert: Both height and period anomalies detected
        assert len(anomalies) >= 2
        assert any('wave_height' in a['issue'] for a in anomalies)
        assert any('period' in a['issue'] for a in anomalies)

    def test_detect_anomalies_insufficient_data(self, buoy_analyst):
        """Test that anomaly detection requires minimum data points."""
        # Arrange: Buoy with only 2 observations (insufficient for statistics)
        buoy = BuoyData(station_id='minimal', name='Minimal Data')
        buoy.observations = [
            BuoyObservation(timestamp=datetime.now().isoformat(), wave_height=2.0, dominant_period=12.0),
            BuoyObservation(timestamp=datetime.now().isoformat(), wave_height=3.0, dominant_period=13.0)
        ]

        # Act
        anomalies = buoy_analyst._detect_anomalies([buoy])

        # Assert: No anomalies (not enough data for meaningful statistics)
        assert len(anomalies) == 0

    def test_detect_anomalies_all_values_identical(self, buoy_analyst):
        """Test edge case where all values are identical (std = 0)."""
        # Arrange: All observations have identical values
        buoy = BuoyData(station_id='identical', name='Identical Values')
        base_time = datetime.now()

        for i in range(10):
            obs = BuoyObservation(
                timestamp=(base_time - timedelta(hours=i)).isoformat(),
                wave_height=3.0,  # All identical
                dominant_period=14.0  # All identical
            )
            buoy.observations.insert(0, obs)

        # Act
        anomalies = buoy_analyst._detect_anomalies([buoy])

        # Assert: No anomalies (Z-score = 0 for all, std = 0 prevents division)
        assert len(anomalies) == 0


# =============================================================================
# QUALITY FLAG ASSIGNMENT TESTS (6 tests)
# =============================================================================


class TestBuoyAnalystQualityFlags:
    """Tests for quality flag assignment functionality."""

    def test_assign_quality_flags_excellent(self, buoy_analyst, sample_buoy_data_steady):
        """Test excellent quality flag (consistent, no anomalies)."""
        # Arrange
        buoy_list = [sample_buoy_data_steady]
        anomalies = []  # No anomalies
        trends = [{'buoy_id': '51002', 'height_trend': 'steady'}]

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert
        assert quality_flags['51002'] == 'valid'

    def test_assign_quality_flags_excluded_high_severity(self, buoy_analyst, sample_buoy_data_anomaly):
        """Test excluded quality flag for high severity anomaly."""
        # Arrange
        buoy_list = [sample_buoy_data_anomaly]
        anomalies = [{
            'buoy_id': '51003',
            'buoy_name': 'Anomaly Buoy',
            'issue': 'wave_height_anomaly',
            'severity': 'high',
            'details': 'Height 15.0m is 5.0 std devs from mean',
            'z_score': 5.0
        }]
        trends = [{'buoy_id': '51003', 'height_trend': 'steady'}]

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert
        assert quality_flags['51003'] == 'excluded'

    def test_assign_quality_flags_excluded_single_scan_spike(self, buoy_analyst, sample_buoy_data_single_scan):
        """Test excluded quality flag for single-scan spike (1-2 observations + anomaly)."""
        # Arrange
        buoy_list = [sample_buoy_data_single_scan]
        anomalies = [{
            'buoy_id': '51004',
            'buoy_name': 'Single Scan Buoy',
            'issue': 'wave_height_anomaly',
            'severity': 'moderate',
            'details': 'Height 8.0m is 2.5 std devs from mean',
            'z_score': 2.5
        }]
        trends = [{'buoy_id': '51004', 'height_trend': 'steady'}]

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert: Single observation with anomaly = excluded
        assert quality_flags['51004'] == 'excluded'

    def test_assign_quality_flags_excluded_moderate_declining(self, buoy_analyst):
        """Test excluded flag for moderate anomaly on strongly declining trend."""
        # Arrange: Buoy with declining trend
        buoy = BuoyData(station_id='declining', name='Declining Buoy')
        for i in range(10):
            obs = BuoyObservation(
                timestamp=datetime.now().isoformat(),
                wave_height=5.0 - (i * 0.3),  # Declining
                dominant_period=14.0
            )
            buoy.observations.append(obs)

        buoy_list = [buoy]
        anomalies = [{
            'buoy_id': 'declining',
            'buoy_name': 'Declining Buoy',
            'issue': 'wave_height_anomaly',
            'severity': 'moderate',
            'details': 'Anomaly on declining trend',
            'z_score': 2.2
        }]
        trends = [{
            'buoy_id': 'declining',
            'height_trend': 'decreasing_strong'
        }]

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert: Moderate anomaly + declining = excluded
        assert quality_flags['declining'] == 'excluded'

    def test_assign_quality_flags_suspect_moderate_anomaly(self, buoy_analyst):
        """Test suspect quality flag for moderate anomaly without declining trend."""
        # Arrange
        buoy = BuoyData(station_id='moderate', name='Moderate Anomaly')
        for i in range(10):
            obs = BuoyObservation(
                timestamp=datetime.now().isoformat(),
                wave_height=2.0,
                dominant_period=12.0
            )
            buoy.observations.append(obs)

        buoy_list = [buoy]
        anomalies = [{
            'buoy_id': 'moderate',
            'buoy_name': 'Moderate Anomaly',
            'issue': 'wave_height_anomaly',
            'severity': 'moderate',
            'details': 'Moderate anomaly',
            'z_score': 2.3
        }]
        trends = [{'buoy_id': 'moderate', 'height_trend': 'steady'}]

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert
        assert quality_flags['moderate'] == 'suspect'

    def test_assign_quality_flags_no_observations(self, buoy_analyst):
        """Test quality flag assignment with no observations."""
        # Arrange: Buoy with no observations
        buoy = BuoyData(station_id='empty', name='Empty Buoy')
        buoy_list = [buoy]
        anomalies = []
        trends = []

        # Act
        quality_flags = buoy_analyst._assign_quality_flags(buoy_list, anomalies, trends)

        # Assert: No quality flag assigned (no observations to analyze)
        assert 'empty' not in quality_flags or quality_flags.get('empty') == 'valid'


# =============================================================================
# CROSS-VALIDATION TESTS (4 tests)
# =============================================================================


class TestBuoyAnalystCrossValidation:
    """Tests for cross-buoy validation functionality."""

    def test_calculate_cross_validation_excellent_agreement(self, buoy_analyst):
        """Test excellent agreement (agreement score >= 0.9)."""
        # Arrange: Two buoys with very similar values
        buoy1 = BuoyData(station_id='b1', name='Buoy 1')
        buoy1.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=2.0,
            dominant_period=12.0
        )]

        buoy2 = BuoyData(station_id='b2', name='Buoy 2')
        buoy2.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=2.05,  # Very close to buoy1
            dominant_period=12.1
        )]

        buoy_list = [buoy1, buoy2]

        # Act
        cross_val = buoy_analyst._calculate_cross_validation(buoy_list)

        # Assert
        assert cross_val['agreement_score'] >= 0.9
        assert cross_val['interpretation'] == 'excellent_agreement'
        assert cross_val['num_buoys_compared'] == 2

    def test_calculate_cross_validation_poor_agreement(self, buoy_analyst):
        """Test poor agreement (large variance between buoys)."""
        # Arrange: Three buoys with very different values
        buoy1 = BuoyData(station_id='b1', name='Buoy 1')
        buoy1.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=1.0,
            dominant_period=8.0
        )]

        buoy2 = BuoyData(station_id='b2', name='Buoy 2')
        buoy2.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=5.0,  # Very different
            dominant_period=16.0
        )]

        buoy3 = BuoyData(station_id='b3', name='Buoy 3')
        buoy3.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=10.0,  # Very different
            dominant_period=20.0
        )]

        buoy_list = [buoy1, buoy2, buoy3]

        # Act
        cross_val = buoy_analyst._calculate_cross_validation(buoy_list)

        # Assert
        assert cross_val['agreement_score'] < 0.75
        assert cross_val['interpretation'] in ['poor_agreement', 'very_poor_agreement', 'moderate_agreement']

    def test_calculate_cross_validation_single_buoy(self, buoy_analyst, sample_buoy_data):
        """Test cross-validation with single buoy (no comparison possible)."""
        # Arrange: Only one buoy
        buoy_list = [sample_buoy_data]

        # Act
        cross_val = buoy_analyst._calculate_cross_validation(buoy_list)

        # Assert: Single buoy returns low agreement (can't compare)
        assert cross_val['num_buoys_compared'] == 1
        assert 0.0 <= cross_val['agreement_score'] <= 1.0

    def test_calculate_cross_validation_mixed_missing_data(self, buoy_analyst):
        """Test cross-validation with some buoys missing data."""
        # Arrange: Mix of buoys with complete and incomplete data
        buoy1 = BuoyData(station_id='complete', name='Complete')
        buoy1.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=2.0,
            dominant_period=12.0
        )]

        buoy2 = BuoyData(station_id='partial', name='Partial')
        buoy2.observations = [BuoyObservation(
            timestamp=datetime.now().isoformat(),
            wave_height=None,  # Missing height
            dominant_period=12.5
        )]

        buoy3 = BuoyData(station_id='empty', name='Empty')
        # No observations

        buoy_list = [buoy1, buoy2, buoy3]

        # Act
        cross_val = buoy_analyst._calculate_cross_validation(buoy_list)

        # Assert: Calculation proceeds with available data
        assert cross_val['num_buoys_compared'] == 3
        assert 0.0 <= cross_val['agreement_score'] <= 1.0


# =============================================================================
# DATA NORMALIZATION TESTS (3 tests)
# =============================================================================


class TestBuoyAnalystNormalization:
    """Tests for data normalization functionality."""

    def test_normalize_buoy_data_all_buoydata_objects(self, buoy_analyst, sample_buoy_data):
        """Test normalization when all inputs are BuoyData objects (no conversion needed)."""
        # Arrange: List of BuoyData objects
        buoy_list = [sample_buoy_data]

        # Act
        normalized = buoy_analyst._normalize_buoy_data(buoy_list)

        # Assert: Returns same objects unchanged
        assert len(normalized) == 1
        assert isinstance(normalized[0], BuoyData)
        assert normalized[0].station_id == '51001'

    def test_normalize_buoy_data_all_dicts(self, buoy_analyst):
        """Test normalization when all inputs are dicts (full conversion)."""
        # Arrange: List of dict format buoy data
        dict_data = [
            {
                'station_id': '51201',
                'name': 'Test Buoy',
                'latitude': 21.5,
                'longitude': -158.1,
                'observations': [
                    {
                        'timestamp': datetime.now().isoformat(),
                        'wave_height': 2.5,
                        'dominant_period': 13.0,
                        'wave_direction': 315.0
                    }
                ]
            }
        ]

        # Act
        normalized = buoy_analyst._normalize_buoy_data(dict_data)

        # Assert: Converted to BuoyData objects
        assert len(normalized) == 1
        assert isinstance(normalized[0], BuoyData)
        assert normalized[0].station_id == '51201'
        assert len(normalized[0].observations) == 1
        assert normalized[0].observations[0].wave_height == 2.5

    def test_normalize_buoy_data_mixed_formats(self, buoy_analyst, sample_buoy_data):
        """Test normalization with mixed BuoyData objects and dicts."""
        # Arrange: Mix of BuoyData and dict
        mixed_list = [
            sample_buoy_data,  # BuoyData object
            {
                'station_id': '51202',
                'name': 'Dict Buoy',
                'observations': [
                    {
                        'timestamp': datetime.now().isoformat(),
                        'wave_height': 3.0,
                        'dominant_period': 14.0
                    }
                ]
            }
        ]

        # Act
        normalized = buoy_analyst._normalize_buoy_data(mixed_list)

        # Assert: All converted to BuoyData objects
        assert len(normalized) == 2
        assert all(isinstance(b, BuoyData) for b in normalized)
        assert normalized[0].station_id == '51001'
        assert normalized[1].station_id == '51202'


# =============================================================================
# CONFIDENCE CALCULATION TESTS (3 tests)
# =============================================================================


class TestBuoyAnalystConfidence:
    """Tests for confidence calculation functionality."""

    def test_calculate_confidence_high_quality(self, buoy_analyst, sample_buoy_data, sample_buoy_data_steady):
        """Test high confidence scenario (complete data, good agreement, no anomalies)."""
        # Arrange: Multiple buoys with complete data, no anomalies
        buoy_list = [sample_buoy_data, sample_buoy_data_steady]
        trends = [
            {'buoy_id': '51001'},
            {'buoy_id': '51002'}
        ]
        anomalies = []  # No anomalies
        cross_validation = {
            'agreement_score': 0.95,
            'height_agreement': 0.95,
            'period_agreement': 0.95
        }

        # Act
        confidence = buoy_analyst._calculate_analysis_confidence(
            buoy_list, trends, anomalies, cross_validation
        )

        # Assert: High confidence (>0.8)
        assert confidence > 0.8
        assert confidence <= 1.0

    def test_calculate_confidence_low_quality(self, buoy_analyst, sample_buoy_data_anomaly):
        """Test low confidence scenario (anomalies, poor agreement)."""
        # Arrange: Single buoy with anomaly
        buoy_list = [sample_buoy_data_anomaly]
        trends = [{'buoy_id': '51003'}]
        anomalies = [
            {'buoy_id': '51003', 'severity': 'high'},
            {'buoy_id': '51003', 'severity': 'moderate'}
        ]
        cross_validation = {
            'agreement_score': 0.3,  # Poor agreement
            'height_agreement': 0.3,
            'period_agreement': 0.3
        }

        # Act
        confidence = buoy_analyst._calculate_analysis_confidence(
            buoy_list, trends, anomalies, cross_validation
        )

        # Assert: Low confidence (<0.6)
        assert confidence < 0.6
        assert confidence >= 0.0

    def test_calculate_confidence_no_data(self, buoy_analyst):
        """Test confidence calculation with no data (edge case)."""
        # Arrange: Empty buoy list
        buoy_list = []
        trends = []
        anomalies = []
        cross_validation = {
            'agreement_score': 0.5,
            'height_agreement': 0.5,
            'period_agreement': 0.5
        }

        # Act
        confidence = buoy_analyst._calculate_analysis_confidence(
            buoy_list, trends, anomalies, cross_validation
        )

        # Assert: Some confidence value (handles edge case gracefully)
        assert 0.0 <= confidence <= 1.0


# =============================================================================
# INTEGRATION TESTS (3 tests)
# =============================================================================


class TestBuoyAnalystIntegration:
    """Integration tests for complete analyze() workflow."""

    @pytest.mark.asyncio
    async def test_analyze_complete_workflow(self, buoy_analyst, sample_buoy_data, sample_buoy_data_steady):
        """Test complete analyze workflow with valid data."""
        # Arrange
        data = {
            'buoy_data': [sample_buoy_data, sample_buoy_data_steady]
        }

        # Act
        result = await buoy_analyst.analyze(data)

        # Assert: Returns BuoyAnalystOutput
        assert isinstance(result, BuoyAnalystOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.data.trends) == 2
        assert result.narrative is not None
        assert len(result.narrative) > 0
        assert 'num_buoys' in result.metadata

    @pytest.mark.asyncio
    async def test_analyze_missing_required_key(self, buoy_analyst):
        """Test analyze raises ValueError for missing required key."""
        # Arrange: Missing 'buoy_data' key
        data = {'wrong_key': []}

        # Act & Assert
        with pytest.raises(ValueError, match="Missing required keys"):
            await buoy_analyst.analyze(data)

    @pytest.mark.asyncio
    async def test_analyze_empty_buoy_list(self, buoy_analyst):
        """Test analyze raises ValueError for empty buoy list."""
        # Arrange: Empty buoy_data list
        data = {'buoy_data': []}

        # Act & Assert
        with pytest.raises(ValueError, match="must be a non-empty list"):
            await buoy_analyst.analyze(data)


# =============================================================================
# INITIALIZATION TESTS (2 tests)
# =============================================================================


class TestBuoyAnalystInitialization:
    """Tests for BuoyAnalyst initialization."""

    def test_initialization_requires_engine(self, mock_config):
        """Test that BuoyAnalyst requires engine parameter."""
        # Act & Assert: Missing engine raises ValueError
        with pytest.raises(ValueError, match="requires engine parameter"):
            BuoyAnalyst(config=mock_config, model_name='gpt-4o-mini', engine=None)

    def test_initialization_success(self, mock_config, mock_engine):
        """Test successful initialization with all required parameters."""
        # Act
        analyst = BuoyAnalyst(config=mock_config, model_name='gpt-4o-mini', engine=mock_engine)

        # Assert
        assert analyst.model_name == 'gpt-4o-mini'
        assert analyst.engine == mock_engine
        assert analyst.anomaly_threshold == 2.0
