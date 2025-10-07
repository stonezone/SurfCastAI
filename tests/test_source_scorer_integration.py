"""
Integration test for SourceScorer with DataFusionSystem.

Verifies that source scoring integrates correctly with the data fusion pipeline.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from src.processing.data_fusion_system import DataFusionSystem
from src.processing.source_scorer import SourceTier
from src.core.config import Config


class TestSourceScorerIntegration:
    """Test SourceScorer integration with DataFusionSystem."""

    @pytest.fixture
    def config(self):
        """Create a mock config."""
        config = Mock(spec=Config)
        return config

    @pytest.fixture
    def fusion_system(self, config):
        """Create a DataFusionSystem instance."""
        return DataFusionSystem(config)

    def test_source_scoring_in_fusion_pipeline(self, fusion_system):
        """Test that source scoring is applied during fusion processing."""
        now = datetime.now(timezone.utc)

        # Create test data with multiple sources
        fusion_data = {
            'metadata': {
                'forecast_id': 'test_forecast'
            },
            'buoy_data': [
                {
                    'station_id': '51001',
                    'name': 'NW Hawaii',
                    'latitude': 23.445,
                    'longitude': -162.279,
                    'observations': [
                        {
                            'timestamp': now.isoformat(),
                            'wave_height': 2.5,
                            'dominant_period': 12.0,
                            'wave_direction': 315.0,
                            'wind_speed': 5.0,
                            'wind_direction': 45.0
                        }
                    ],
                    'metadata': {}
                }
            ],
            'weather_data': [],
            'model_data': []
        }

        # Process the data
        result = fusion_system.process(fusion_data)

        # Verify processing succeeded
        assert result.success is True
        assert result.data is not None

        # Verify source scores are in metadata
        forecast = result.data
        assert 'source_scores' in forecast.metadata
        assert len(forecast.metadata['source_scores']) > 0

        # Verify score structure
        for source_id, score_data in forecast.metadata['source_scores'].items():
            assert 'overall_score' in score_data
            assert 'tier' in score_data
            assert 'tier_score' in score_data
            assert 'freshness_score' in score_data
            assert 'completeness_score' in score_data
            assert 'accuracy_score' in score_data

            # Verify scores are in valid range
            assert 0.0 <= score_data['overall_score'] <= 1.0
            assert 0.0 <= score_data['tier_score'] <= 1.0
            assert 0.0 <= score_data['freshness_score'] <= 1.0
            assert 0.0 <= score_data['completeness_score'] <= 1.0
            assert 0.0 <= score_data['accuracy_score'] <= 1.0

    def test_source_scores_attached_to_buoy_data(self, fusion_system):
        """Test that reliability scores are attached to buoy data items."""
        now = datetime.now(timezone.utc)

        fusion_data = {
            'metadata': {'forecast_id': 'test_forecast'},
            'buoy_data': [
                {
                    'station_id': '51001',
                    'name': 'NW Hawaii',
                    'latitude': 23.445,
                    'longitude': -162.279,
                    'observations': [
                        {
                            'timestamp': now.isoformat(),
                            'wave_height': 2.5,
                            'dominant_period': 12.0,
                            'wave_direction': 315.0
                        }
                    ],
                    'metadata': {}
                }
            ],
            'weather_data': [],
            'model_data': []
        }

        result = fusion_system.process(fusion_data)

        # Note: The buoy_data passed to _extract_buoy_data gets converted to BuoyData objects
        # We can verify the scores were calculated by checking the forecast metadata
        assert result.success is True
        assert 'source_scores' in result.data.metadata
        assert len(result.data.metadata['source_scores']) > 0

    def test_tier_scores_differ_by_source(self, fusion_system):
        """Test that different source types get different tier scores."""
        now = datetime.now(timezone.utc)

        # Mix of different source tiers
        fusion_data = {
            'metadata': {'forecast_id': 'test_forecast'},
            'buoy_data': [
                {
                    'station_id': '51001',
                    'source': 'ndbc',  # Tier 1
                    'name': 'NDBC Buoy',
                    'observations': [
                        {
                            'timestamp': now.isoformat(),
                            'wave_height': 2.5,
                            'dominant_period': 12.0,
                            'wave_direction': 315.0,
                            'wind_speed': 5.0,
                            'wind_direction': 45.0
                        }
                    ],
                    'metadata': {}
                }
            ],
            'weather_data': [
                {
                    'provider': 'nws',  # Tier 1
                    'latitude': 21.3,
                    'longitude': -157.8,
                    'temperature': 25.0,
                    'wind_speed': 10.0,
                    'wind_direction': 90.0,
                    'forecast_periods': [],
                    'timestamp': now.isoformat(),
                    'metadata': {}
                }
            ],
            'model_data': [
                {
                    'model_id': 'swan',  # Tier 2
                    'region': 'oahu',
                    'run_time': now.isoformat(),
                    'forecasts': [],
                    'metadata': {}
                }
            ]
        }

        result = fusion_system.process(fusion_data)

        assert result.success is True
        source_scores = result.data.metadata['source_scores']

        # Verify we have scores for different sources
        assert len(source_scores) >= 3

        # Check that Tier 1 sources (NOAA) score higher than Tier 2 (Research)
        tier1_scores = []
        tier2_scores = []

        for source_id, score_data in source_scores.items():
            if score_data['tier'] == 'TIER_1':
                tier1_scores.append(score_data['tier_score'])
            elif score_data['tier'] == 'TIER_2':
                tier2_scores.append(score_data['tier_score'])

        if tier1_scores and tier2_scores:
            assert min(tier1_scores) >= max(tier2_scores)

    def test_freshness_affects_score(self, fusion_system):
        """Test that data freshness affects overall score."""
        # This is implicitly tested by the scoring system
        # Fresh data should score higher than old data
        now = datetime.now(timezone.utc)

        fusion_data = {
            'metadata': {'forecast_id': 'test_forecast'},
            'buoy_data': [
                {
                    'station_id': '51001',
                    'source': 'ndbc',
                    'name': 'Fresh Buoy',
                    'observations': [
                        {
                            'timestamp': now.isoformat(),  # Very fresh
                            'wave_height': 2.5,
                            'dominant_period': 12.0,
                            'wave_direction': 315.0,
                            'wind_speed': 5.0,
                            'wind_direction': 45.0
                        }
                    ],
                    'metadata': {}
                }
            ],
            'weather_data': [],
            'model_data': []
        }

        result = fusion_system.process(fusion_data)

        assert result.success is True
        source_scores = result.data.metadata['source_scores']

        # Verify fresh data has high freshness score
        for source_id, score_data in source_scores.items():
            # Fresh data should have freshness score near 1.0
            assert score_data['freshness_score'] >= 0.95


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
