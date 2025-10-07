"""
Integration tests for ConfidenceScorer with DataFusionSystem.

Tests the complete workflow of confidence calculation in the forecast pipeline.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.processing.data_fusion_system import DataFusionSystem
from src.processing.confidence_scorer import ConfidenceScorer, ConfidenceCategory
from src.core.config import Config


class TestConfidenceScorerIntegration:
    """Test ConfidenceScorer integration with DataFusionSystem."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()

    @pytest.fixture
    def fusion_system(self, config):
        """Create DataFusionSystem instance."""
        return DataFusionSystem(config)

    @pytest.fixture
    def sample_input_data(self):
        """Create sample input data for fusion system."""
        return {
            'metadata': {
                'forecast_id': 'test_forecast_001',
                'bundle_id': 'test_bundle'
            },
            'buoy_data': [
                {
                    'station_id': '51001',
                    'name': 'Northwest Hawaii',
                    'source': 'ndbc',
                    'observations': [
                        {
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'wave_height': 2.5,
                            'dominant_period': 12.0,
                            'wave_direction': 315.0
                        }
                    ]
                }
            ],
            'model_data': [
                {
                    'model_id': 'ww3_global',
                    'region': 'global',
                    'source': 'ww3',
                    'run_time': datetime.now(timezone.utc).isoformat(),
                    'forecasts': [],
                    'metadata': {
                        'swell_events': [
                            {
                                'event_id': 'event_001',
                                'start_time': datetime.now(timezone.utc).isoformat(),
                                'peak_time': datetime.now(timezone.utc).isoformat(),
                                'peak_direction': 315,
                                'peak_height': 2.4,
                                'peak_period': 12,
                                'significance': 0.75
                            }
                        ]
                    }
                }
            ]
        }

    def test_confidence_calculated_in_fusion(self, fusion_system, sample_input_data):
        """Test that confidence is calculated during data fusion."""
        result = fusion_system.process(sample_input_data)

        # Check result success
        assert result.success is True
        assert result.data is not None

        # Check confidence is present in metadata
        assert 'confidence' in result.data.metadata
        confidence = result.data.metadata['confidence']

        # Verify confidence structure
        assert 'overall_score' in confidence
        assert 'category' in confidence
        assert 'factors' in confidence
        assert 'breakdown' in confidence

        # Check score range
        assert 0.0 <= confidence['overall_score'] <= 1.0

        # Check category is valid
        valid_categories = [c.value for c in ConfidenceCategory]
        assert confidence['category'] in valid_categories

    def test_confidence_factors_present(self, fusion_system, sample_input_data):
        """Test that all confidence factors are calculated."""
        result = fusion_system.process(sample_input_data)
        confidence = result.data.metadata['confidence']

        factors = confidence['factors']

        # Check all expected factors
        assert 'model_consensus' in factors
        assert 'source_reliability' in factors
        assert 'data_completeness' in factors
        assert 'forecast_horizon' in factors
        assert 'historical_accuracy' in factors

        # Check all factors are in valid range
        for factor_name, factor_value in factors.items():
            assert 0.0 <= factor_value <= 1.0, f"{factor_name} out of range"

    def test_confidence_breakdown_complete(self, fusion_system, sample_input_data):
        """Test that confidence breakdown includes all required info."""
        result = fusion_system.process(sample_input_data)
        breakdown = result.data.metadata['confidence']['breakdown']

        # Check required breakdown fields
        assert 'overall_score' in breakdown
        assert 'overall_score_out_of_10' in breakdown
        assert 'category' in breakdown
        assert 'factors' in breakdown
        assert 'factor_descriptions' in breakdown
        assert 'source_counts' in breakdown
        assert 'total_sources' in breakdown

        # Verify score conversions
        overall = breakdown['overall_score']
        overall_10 = breakdown['overall_score_out_of_10']
        assert abs(overall_10 - (overall * 10)) < 0.2

    def test_confidence_with_multiple_models(self, fusion_system, sample_input_data):
        """Test confidence with multiple model sources (better consensus)."""
        # Add second model with similar predictions
        sample_input_data['model_data'].append({
            'model_id': 'swan_pacific',
            'region': 'pacific',
            'source': 'swan',
            'run_time': datetime.now(timezone.utc).isoformat(),
            'forecasts': [],
            'metadata': {
                'swell_events': [
                    {
                        'event_id': 'event_002',
                        'start_time': datetime.now(timezone.utc).isoformat(),
                        'peak_time': datetime.now(timezone.utc).isoformat(),
                        'peak_direction': 315,
                        'peak_height': 2.5,  # Similar to first model
                        'peak_period': 12,
                        'significance': 0.75
                    }
                ]
            }
        })

        result = fusion_system.process(sample_input_data)
        confidence = result.data.metadata['confidence']

        # Should have high model consensus
        assert confidence['factors']['model_consensus'] >= 0.7

    def test_confidence_with_disagreeing_models(self, fusion_system, sample_input_data):
        """Test confidence with disagreeing model predictions."""
        # Add second model with very different predictions
        sample_input_data['model_data'].append({
            'model_id': 'swan_pacific',
            'region': 'pacific',
            'source': 'swan',
            'run_time': datetime.now(timezone.utc).isoformat(),
            'forecasts': [],
            'metadata': {
                'swell_events': [
                    {
                        'event_id': 'event_002',
                        'start_time': datetime.now(timezone.utc).isoformat(),
                        'peak_time': datetime.now(timezone.utc).isoformat(),
                        'peak_direction': 180,  # Opposite direction
                        'peak_height': 4.5,  # Much larger
                        'peak_period': 8,  # Shorter period
                        'significance': 0.5
                    }
                ]
            }
        })

        result = fusion_system.process(sample_input_data)
        confidence = result.data.metadata['confidence']

        # Should have lower model consensus
        # Note: With only 2 models, consensus may not drop as low as with more models
        assert confidence['factors']['model_consensus'] <= 0.7

    def test_confidence_with_complete_data(self, fusion_system, sample_input_data):
        """Test confidence with complete data sources."""
        # Add chart and satellite data
        sample_input_data['metadata']['charts'] = ['chart1.png', 'chart2.png']
        sample_input_data['metadata']['satellite'] = ['sat1.png']

        result = fusion_system.process(sample_input_data)
        confidence = result.data.metadata['confidence']

        # Should have high data completeness
        assert confidence['factors']['data_completeness'] >= 0.75

    def test_confidence_with_minimal_data(self, fusion_system):
        """Test confidence with minimal data sources."""
        minimal_data = {
            'metadata': {
                'forecast_id': 'test_minimal',
                'bundle_id': 'test_bundle'
            },
            'model_data': [
                {
                    'model_id': 'ww3_global',
                    'region': 'global',
                    'source': 'ww3',
                    'run_time': datetime.now(timezone.utc).isoformat(),
                    'forecasts': [],
                    'metadata': {}
                }
            ]
        }

        result = fusion_system.process(minimal_data)
        confidence = result.data.metadata['confidence']

        # Should have low data completeness
        assert confidence['factors']['data_completeness'] <= 0.5
        # Overall confidence should be moderate or low
        assert confidence['overall_score'] <= 0.7

    def test_confidence_warnings_generated(self, fusion_system, sample_input_data):
        """Test that appropriate warnings are generated for low confidence."""
        # Create conditions for low confidence
        sample_input_data['model_data'] = []  # No model data
        sample_input_data['buoy_data'] = []  # No buoy data

        result = fusion_system.process(sample_input_data)

        # Should have warnings about low confidence
        assert len(result.warnings) > 0
        # Check for specific warning about limited data
        assert any('limited data' in w.lower() or 'missing' in w.lower()
                  for w in result.warnings)

    def test_confidence_logged(self, fusion_system, sample_input_data, caplog):
        """Test that confidence calculation is properly logged."""
        import logging
        caplog.set_level(logging.INFO)

        result = fusion_system.process(sample_input_data)

        # Check logging
        assert 'Calculating confidence scores' in caplog.text
        confidence = result.data.metadata['confidence']
        # Confidence score should be logged
        assert str(round(confidence['overall_score'], 3)) in caplog.text or \
               str(round(confidence['overall_score'], 2)) in caplog.text

    def test_confidence_scorer_instance(self, fusion_system):
        """Test that fusion system has ConfidenceScorer instance."""
        assert hasattr(fusion_system, 'confidence_scorer')
        assert isinstance(fusion_system.confidence_scorer, ConfidenceScorer)

    def test_confidence_with_source_scores(self, fusion_system, sample_input_data):
        """Test that confidence uses source scores from SourceScorer."""
        result = fusion_system.process(sample_input_data)

        # Check that source scores were calculated
        assert 'source_scores' in result.data.metadata
        source_scores = result.data.metadata['source_scores']
        assert len(source_scores) > 0

        # Check that confidence used these scores
        confidence = result.data.metadata['confidence']
        assert 'source_reliability' in confidence['factors']
        # Should have reasonable reliability from NDBC buoy
        assert confidence['factors']['source_reliability'] > 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
