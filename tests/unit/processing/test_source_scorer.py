"""
Unit tests for SourceScorer.

Tests source reliability scoring including tier assignment, freshness
calculation, completeness scoring, and integration with data fusion.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from typing import Dict, Any

from src.processing.source_scorer import (
    SourceScorer,
    SourceTier,
    ScoringWeights,
    SourceScore
)


class TestSourceTier:
    """Test SourceTier enum."""

    def test_tier_values(self):
        """Test that tier values are correctly defined."""
        assert SourceTier.TIER_1.value == 1.0
        assert SourceTier.TIER_2.value == 0.9
        assert SourceTier.TIER_3.value == 0.7
        assert SourceTier.TIER_4.value == 0.5
        assert SourceTier.TIER_5.value == 0.3

    def test_tier_ordering(self):
        """Test that tier values are properly ordered."""
        assert SourceTier.TIER_1.value > SourceTier.TIER_2.value
        assert SourceTier.TIER_2.value > SourceTier.TIER_3.value
        assert SourceTier.TIER_3.value > SourceTier.TIER_4.value
        assert SourceTier.TIER_4.value > SourceTier.TIER_5.value


class TestScoringWeights:
    """Test ScoringWeights dataclass."""

    def test_default_weights(self):
        """Test default weight values sum to 1.0."""
        weights = ScoringWeights()
        total = (
            weights.source_tier +
            weights.data_freshness +
            weights.completeness +
            weights.historical_accuracy
        )
        assert abs(total - 1.0) < 0.001  # Allow for floating point precision

    def test_custom_weights(self):
        """Test custom weight initialization."""
        weights = ScoringWeights(
            source_tier=0.6,
            data_freshness=0.2,
            completeness=0.1,
            historical_accuracy=0.1
        )
        assert weights.source_tier == 0.6
        assert weights.data_freshness == 0.2
        assert weights.completeness == 0.1
        assert weights.historical_accuracy == 0.1


class TestSourceScorer:
    """Test SourceScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a SourceScorer instance for testing."""
        return SourceScorer()

    @pytest.fixture
    def custom_weights_scorer(self):
        """Create a SourceScorer with custom weights."""
        weights = ScoringWeights(
            source_tier=0.6,
            data_freshness=0.2,
            completeness=0.1,
            historical_accuracy=0.1
        )
        return SourceScorer(weights=weights)

    def test_initialization(self, scorer):
        """Test scorer initialization."""
        assert scorer.weights.source_tier == 0.5
        assert scorer.weights.data_freshness == 0.2
        assert scorer.weights.completeness == 0.2
        assert scorer.weights.historical_accuracy == 0.1
        assert isinstance(scorer._validation_cache, dict)

    def test_custom_weights_initialization(self, custom_weights_scorer):
        """Test scorer with custom weights."""
        assert custom_weights_scorer.weights.source_tier == 0.6
        assert custom_weights_scorer.weights.data_freshness == 0.2

    # Tier Scoring Tests

    def test_get_tier_score_tier1(self, scorer):
        """Test tier scoring for Tier 1 (NOAA) sources."""
        assert scorer.get_tier_score('ndbc') == 1.0
        assert scorer.get_tier_score('noaa_buoy') == 1.0
        assert scorer.get_tier_score('nws') == 1.0
        assert scorer.get_tier_score('opc') == 1.0

    def test_get_tier_score_tier2(self, scorer):
        """Test tier scoring for Tier 2 (Research) sources."""
        assert scorer.get_tier_score('pacioos') == 0.9
        assert scorer.get_tier_score('cdip') == 0.9
        assert scorer.get_tier_score('swan') == 0.9
        assert scorer.get_tier_score('ww3') == 0.9

    def test_get_tier_score_tier3(self, scorer):
        """Test tier scoring for Tier 3 (International) sources."""
        assert scorer.get_tier_score('ecmwf') == 0.7
        assert scorer.get_tier_score('bom') == 0.7

    def test_get_tier_score_tier4(self, scorer):
        """Test tier scoring for Tier 4 (Commercial) sources."""
        assert scorer.get_tier_score('stormglass') == 0.5
        assert scorer.get_tier_score('windy') == 0.5
        assert scorer.get_tier_score('open_meteo') == 0.5

    def test_get_tier_score_tier5(self, scorer):
        """Test tier scoring for Tier 5 (Surf Sites) sources."""
        assert scorer.get_tier_score('surfline') == 0.3
        assert scorer.get_tier_score('magicseaweed') == 0.3

    def test_get_tier_score_partial_match(self, scorer):
        """Test tier scoring with partial source name matches."""
        assert scorer.get_tier_score('ndbc_51001') == 1.0
        assert scorer.get_tier_score('pacioos_swan_oahu') == 0.9

    def test_get_tier_score_unknown(self, scorer):
        """Test tier scoring for unknown sources defaults to Tier 4."""
        assert scorer.get_tier_score('unknown_source') == 0.5

    # Freshness Scoring Tests

    def test_calculate_freshness_recent_data(self, scorer):
        """Test freshness scoring for recent data."""
        now = datetime.now(timezone.utc)
        data = {'timestamp': now.isoformat()}

        freshness = scorer.calculate_freshness(data)
        assert freshness >= 0.999  # Very recent should be ~1.0

    def test_calculate_freshness_12h_old(self, scorer):
        """Test freshness scoring for 12-hour-old data."""
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        data = {'timestamp': twelve_hours_ago.isoformat()}

        freshness = scorer.calculate_freshness(data)
        assert 0.4 <= freshness <= 0.6  # Should be around 0.5

    def test_calculate_freshness_24h_old(self, scorer):
        """Test freshness scoring for 24-hour-old data."""
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        data = {'timestamp': twenty_four_hours_ago.isoformat()}

        freshness = scorer.calculate_freshness(data)
        assert freshness == 0.0

    def test_calculate_freshness_no_timestamp(self, scorer):
        """Test freshness scoring with missing timestamp."""
        data = {'wave_height': 2.0}

        freshness = scorer.calculate_freshness(data)
        assert freshness == 0.5  # Neutral score

    def test_calculate_freshness_nested_timestamp(self, scorer):
        """Test freshness scoring with nested timestamp."""
        now = datetime.now(timezone.utc)
        data = {
            'metadata': {
                'timestamp': now.isoformat()
            }
        }

        freshness = scorer.calculate_freshness(data)
        assert freshness >= 0.999  # Very recent should be ~1.0

    def test_calculate_freshness_observations_timestamp(self, scorer):
        """Test freshness scoring from observations array."""
        now = datetime.now(timezone.utc)
        data = {
            'observations': [
                {'timestamp': now.isoformat(), 'wave_height': 2.0}
            ]
        }

        freshness = scorer.calculate_freshness(data)
        assert freshness >= 0.999  # Very recent should be ~1.0

    # Completeness Scoring Tests

    def test_calculate_completeness_buoy_complete(self, scorer):
        """Test completeness for complete buoy data."""
        data = {
            'wave_height': 2.0,
            'dominant_period': 10.0,
            'wave_direction': 315.0,
            'wind_speed': 5.0,
            'wind_direction': 45.0,
            'timestamp': datetime.now().isoformat()
        }

        completeness = scorer.calculate_completeness(data, 'buoy')
        assert completeness == 1.0

    def test_calculate_completeness_buoy_partial(self, scorer):
        """Test completeness for partial buoy data."""
        data = {
            'wave_height': 2.0,
            'dominant_period': 10.0,
            'timestamp': datetime.now().isoformat()
        }

        completeness = scorer.calculate_completeness(data, 'buoy')
        # 3 out of 6 expected fields
        assert completeness == 0.5

    def test_calculate_completeness_weather_complete(self, scorer):
        """Test completeness for complete weather data."""
        data = {
            'temperature': 25.0,
            'wind_speed': 10.0,
            'wind_direction': 90.0,
            'forecast_periods': [],
            'timestamp': datetime.now().isoformat()
        }

        completeness = scorer.calculate_completeness(data, 'weather')
        assert completeness == 1.0

    def test_calculate_completeness_model_complete(self, scorer):
        """Test completeness for complete model data."""
        data = {
            'wave_height': 3.0,
            'wave_period': 12.0,
            'wave_direction': 270.0,
            'run_time': datetime.now().isoformat(),
            'forecast_hour': 24,
            'points': []
        }

        completeness = scorer.calculate_completeness(data, 'model')
        assert completeness == 1.0

    def test_calculate_completeness_null_fields(self, scorer):
        """Test completeness ignores null fields."""
        data = {
            'wave_height': 2.0,
            'dominant_period': None,
            'wave_direction': None,
            'timestamp': datetime.now().isoformat()
        }

        completeness = scorer.calculate_completeness(data, 'buoy')
        # Only 2 non-null fields out of 6
        assert completeness < 0.5

    # Historical Accuracy Tests

    def test_get_historical_accuracy_default(self, scorer):
        """Test default historical accuracy."""
        accuracy = scorer.get_historical_accuracy('test_source')
        assert accuracy == 0.7  # Default neutral value

    def test_set_and_get_historical_accuracy(self, scorer):
        """Test setting and retrieving historical accuracy."""
        scorer.set_historical_accuracy('test_source', 0.85)
        accuracy = scorer.get_historical_accuracy('test_source')
        assert accuracy == 0.85

    def test_set_historical_accuracy_validation(self, scorer):
        """Test historical accuracy validation."""
        with pytest.raises(ValueError):
            scorer.set_historical_accuracy('test_source', 1.5)

        with pytest.raises(ValueError):
            scorer.set_historical_accuracy('test_source', -0.1)

    # Score Single Source Tests

    def test_score_single_source_perfect(self, scorer):
        """Test scoring a perfect data source."""
        now = datetime.now(timezone.utc)
        data = {
            'source': 'ndbc',
            'station_id': '51001',
            'wave_height': 2.0,
            'dominant_period': 10.0,
            'wave_direction': 315.0,
            'wind_speed': 5.0,
            'wind_direction': 45.0,
            'timestamp': now.isoformat()
        }

        score = scorer.score_single_source('ndbc', data, 'buoy')

        assert isinstance(score, SourceScore)
        assert score.source_name == 'ndbc'
        assert score.tier == SourceTier.TIER_1
        assert score.tier_score == 1.0
        assert score.freshness_score >= 0.999  # Very recent
        assert score.completeness_score == 1.0
        assert 0.9 <= score.overall_score <= 1.0

    def test_score_single_source_degraded(self, scorer):
        """Test scoring a degraded data source."""
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        data = {
            'source': 'surfline',
            'wave_height': 2.0,
            'timestamp': twelve_hours_ago.isoformat()
        }

        score = scorer.score_single_source('surfline', data, 'buoy')

        assert score.tier == SourceTier.TIER_5
        assert score.tier_score == 0.3
        assert 0.4 <= score.freshness_score <= 0.6
        assert score.completeness_score < 1.0
        assert score.overall_score < 0.6

    # Score Sources Tests

    def test_score_sources_multiple_sources(self, scorer):
        """Test scoring multiple data sources."""
        now = datetime.now(timezone.utc)
        fusion_data = {
            'buoy_data': [
                {
                    'station_id': '51001',
                    'wave_height': 2.0,
                    'dominant_period': 10.0,
                    'wave_direction': 315.0,
                    'wind_speed': 5.0,
                    'wind_direction': 45.0,
                    'timestamp': now.isoformat()
                }
            ],
            'weather_data': [
                {
                    'provider': 'nws',
                    'temperature': 25.0,
                    'wind_speed': 10.0,
                    'wind_direction': 90.0,
                    'forecast_periods': [],
                    'timestamp': now.isoformat()
                }
            ],
            'model_data': [
                {
                    'model_id': 'swan',
                    'wave_height': 3.0,
                    'wave_period': 12.0,
                    'wave_direction': 270.0,
                    'run_time': now.isoformat(),
                    'forecast_hour': 24,
                    'points': []
                }
            ]
        }

        scores = scorer.score_sources(fusion_data)

        assert len(scores) == 3
        assert all(isinstance(score, SourceScore) for score in scores.values())
        assert all(0.0 <= score.overall_score <= 1.0 for score in scores.values())

    def test_score_sources_empty_data(self, scorer):
        """Test scoring with no data sources."""
        fusion_data = {
            'buoy_data': [],
            'weather_data': [],
            'model_data': []
        }

        scores = scorer.score_sources(fusion_data)

        assert len(scores) == 0

    # Extract Source ID Tests

    def test_extract_source_id_from_dict(self, scorer):
        """Test extracting source ID from dictionary."""
        data = {'source': 'ndbc', 'station_id': '51001'}
        source_id = scorer._extract_source_id(data, 'buoy')
        assert source_id == 'ndbc'

    def test_extract_source_id_fallback(self, scorer):
        """Test extracting source ID with fallback fields."""
        data = {'model_id': 'swan_oahu'}
        source_id = scorer._extract_source_id(data, 'model')
        assert source_id == 'swan_oahu'

    def test_extract_source_id_unknown(self, scorer):
        """Test extracting source ID when unknown."""
        data = {'wave_height': 2.0}
        source_id = scorer._extract_source_id(data, 'buoy')
        assert source_id == 'buoy_unknown'

    # Extract Timestamp Tests

    def test_extract_timestamp_direct(self, scorer):
        """Test extracting direct timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        data = {'timestamp': now}
        timestamp = scorer._extract_timestamp(data)
        assert timestamp == now

    def test_extract_timestamp_nested(self, scorer):
        """Test extracting nested timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        data = {'metadata': {'timestamp': now}}
        timestamp = scorer._extract_timestamp(data)
        assert timestamp == now

    def test_extract_timestamp_none(self, scorer):
        """Test extracting timestamp when missing."""
        data = {'wave_height': 2.0}
        timestamp = scorer._extract_timestamp(data)
        assert timestamp is None

    # Extract Fields Tests

    def test_extract_fields_from_dict(self, scorer):
        """Test extracting fields from dictionary."""
        data = {
            'wave_height': 2.0,
            'wave_period': 10.0,
            'timestamp': 'now'
        }
        fields = scorer._extract_fields(data)
        assert fields == data

    def test_extract_fields_from_object(self, scorer):
        """Test extracting fields from object."""
        class TestData:
            def __init__(self):
                self.wave_height = 2.0
                self.wave_period = 10.0

        data = TestData()
        fields = scorer._extract_fields(data)
        assert 'wave_height' in fields
        assert 'wave_period' in fields
        assert fields['wave_height'] == 2.0

    # Integration Tests

    def test_weighted_scoring_formula(self, scorer):
        """Test that overall score uses correct weighted formula."""
        now = datetime.now(timezone.utc)
        data = {
            'source': 'ndbc',
            'wave_height': 2.0,
            'dominant_period': 10.0,
            'wave_direction': 315.0,
            'wind_speed': 5.0,
            'wind_direction': 45.0,
            'timestamp': now.isoformat()
        }

        score = scorer.score_single_source('ndbc', data, 'buoy')

        # Manual calculation
        expected = (
            score.tier_score * 0.5 +
            score.freshness_score * 0.2 +
            score.completeness_score * 0.2 +
            score.accuracy_score * 0.1
        )

        assert abs(score.overall_score - expected) < 0.001

    def test_tier_dominates_scoring(self, scorer):
        """Test that tier score dominates overall score."""
        now = datetime.now(timezone.utc)

        # High tier source with average data
        high_tier_data = {
            'source': 'ndbc',
            'wave_height': 2.0,
            'timestamp': now.isoformat()
        }
        high_tier_score = scorer.score_single_source('ndbc', high_tier_data, 'buoy')

        # Low tier source with perfect data
        low_tier_data = {
            'source': 'surfline',
            'wave_height': 2.0,
            'dominant_period': 10.0,
            'wave_direction': 315.0,
            'wind_speed': 5.0,
            'wind_direction': 45.0,
            'timestamp': now.isoformat()
        }
        low_tier_score = scorer.score_single_source('surfline', low_tier_data, 'buoy')

        # High tier should still score higher
        assert high_tier_score.overall_score > low_tier_score.overall_score

    def test_score_metadata_structure(self, scorer):
        """Test that score metadata has correct structure."""
        now = datetime.now(timezone.utc)
        data = {
            'source': 'ndbc',
            'wave_height': 2.0,
            'timestamp': now.isoformat()
        }

        score = scorer.score_single_source('ndbc', data, 'buoy')

        assert 'data_type' in score.metadata
        assert 'weights' in score.metadata
        assert score.metadata['data_type'] == 'buoy'
        assert 'tier' in score.metadata['weights']
        assert 'freshness' in score.metadata['weights']
        assert 'completeness' in score.metadata['weights']
        assert 'accuracy' in score.metadata['weights']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
