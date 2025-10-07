"""
Unit tests for ConfidenceScorer.

Tests all confidence factors, category determination, and integration.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock

from src.processing.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceCategory,
    ConfidenceWeights,
    ConfidenceResult,
    format_confidence_for_display
)


class TestConfidenceScorer:
    """Test suite for ConfidenceScorer."""

    @pytest.fixture
    def scorer(self):
        """Create a ConfidenceScorer instance."""
        return ConfidenceScorer()

    @pytest.fixture
    def sample_fusion_data(self):
        """Create sample fusion data for testing."""
        return {
            'swell_events': [
                Mock(
                    source='model',
                    primary_components=[Mock(height=2.5), Mock(height=2.3)]
                ),
                Mock(
                    source='model',
                    primary_components=[Mock(height=2.4), Mock(height=2.6)]
                ),
                Mock(
                    source='buoy',
                    primary_components=[Mock(height=2.5)]
                )
            ],
            'locations': [Mock(), Mock()],
            'metadata': {
                'source_scores': {
                    'ndbc_51001': {
                        'overall_score': 0.95,
                        'tier': 'TIER_1',
                        'tier_score': 1.0,
                        'freshness_score': 0.9,
                        'completeness_score': 1.0,
                        'accuracy_score': 0.8
                    },
                    'ww3': {
                        'overall_score': 0.85,
                        'tier': 'TIER_2',
                        'tier_score': 0.9,
                        'freshness_score': 0.8,
                        'completeness_score': 0.9,
                        'accuracy_score': 0.7
                    }
                },
                'charts': ['chart1.png', 'chart2.png'],
                'satellite': ['sat1.png']
            },
            'buoy_data': [Mock(station_id='51001')],
            'model_data': [Mock(model_id='ww3'), Mock(model_id='swan')]
        }

    def test_initialization_default_weights(self):
        """Test scorer initialization with default weights."""
        scorer = ConfidenceScorer()
        assert scorer.weights.model_consensus == 0.30
        assert scorer.weights.source_reliability == 0.25
        assert scorer.weights.data_completeness == 0.20
        assert scorer.weights.forecast_horizon == 0.15
        assert scorer.weights.historical_accuracy == 0.10

    def test_initialization_custom_weights(self):
        """Test scorer initialization with custom weights."""
        custom_weights = ConfidenceWeights(
            model_consensus=0.40,
            source_reliability=0.30,
            data_completeness=0.15,
            forecast_horizon=0.10,
            historical_accuracy=0.05
        )
        scorer = ConfidenceScorer(weights=custom_weights)
        assert scorer.weights.model_consensus == 0.40
        assert scorer.weights.source_reliability == 0.30

    def test_calculate_model_consensus_high_agreement(self, scorer):
        """Test model consensus with high agreement between models."""
        fusion_data = {
            'swell_events': [
                Mock(source='model', primary_components=[Mock(height=2.5)]),
                Mock(source='model', primary_components=[Mock(height=2.6)]),
                Mock(source='model', primary_components=[Mock(height=2.4)])
            ],
            'metadata': {}
        }

        consensus = scorer.calculate_model_consensus(fusion_data)
        assert 0.8 <= consensus <= 1.0  # High consensus expected

    def test_calculate_model_consensus_low_agreement(self, scorer):
        """Test model consensus with low agreement between models."""
        fusion_data = {
            'swell_events': [
                Mock(source='model', primary_components=[Mock(height=1.0)]),
                Mock(source='model', primary_components=[Mock(height=3.0)]),
                Mock(source='model', primary_components=[Mock(height=2.0)])
            ],
            'metadata': {}
        }

        consensus = scorer.calculate_model_consensus(fusion_data)
        assert 0.0 <= consensus <= 0.7  # Low consensus expected

    def test_calculate_model_consensus_single_model(self, scorer):
        """Test model consensus with single model (no disagreement)."""
        fusion_data = {
            'swell_events': [
                Mock(source='model', primary_components=[Mock(height=2.5)])
            ],
            'metadata': {}
        }

        consensus = scorer.calculate_model_consensus(fusion_data)
        assert consensus == 0.7  # Default high for single model

    def test_calculate_model_consensus_no_models(self, scorer):
        """Test model consensus with no model data."""
        fusion_data = {
            'swell_events': [],
            'metadata': {}
        }

        consensus = scorer.calculate_model_consensus(fusion_data)
        assert consensus == 0.5  # Neutral

    def test_calculate_source_reliability(self, scorer, sample_fusion_data):
        """Test source reliability calculation."""
        reliability = scorer.calculate_source_reliability(sample_fusion_data)

        # Should be average of source scores: (0.95 + 0.85) / 2 = 0.90
        assert 0.85 <= reliability <= 0.95

    def test_calculate_source_reliability_no_scores(self, scorer):
        """Test source reliability with no source scores."""
        fusion_data = {'metadata': {}}
        reliability = scorer.calculate_source_reliability(fusion_data)
        assert reliability == 0.5  # Neutral default

    def test_calculate_data_completeness_all_sources(self, scorer):
        """Test data completeness with all expected sources."""
        fusion_data = {
            'swell_events': [
                Mock(source='buoy'),
                Mock(source='model')
            ],
            'metadata': {
                'charts': ['chart1.png'],
                'satellite': ['sat1.png']
            }
        }

        completeness = scorer.calculate_data_completeness(fusion_data)
        assert completeness == 1.0  # All 4 sources present

    def test_calculate_data_completeness_partial_sources(self, scorer):
        """Test data completeness with partial sources."""
        fusion_data = {
            'swell_events': [Mock(source='model')],
            'metadata': {}
        }

        completeness = scorer.calculate_data_completeness(fusion_data)
        assert completeness == 0.25  # Only 1 of 4 sources

    def test_calculate_data_completeness_no_sources(self, scorer):
        """Test data completeness with no sources."""
        fusion_data = {
            'swell_events': [],
            'metadata': {}
        }

        completeness = scorer.calculate_data_completeness(fusion_data)
        assert completeness == 0.0

    def test_calculate_forecast_horizon_short_term(self, scorer):
        """Test forecast horizon for short-term forecast (1 day)."""
        horizon = scorer.calculate_forecast_horizon(1)
        assert horizon == 0.9  # 1.0 - (1 * 0.1)

    def test_calculate_forecast_horizon_medium_term(self, scorer):
        """Test forecast horizon for medium-term forecast (3 days)."""
        horizon = scorer.calculate_forecast_horizon(3)
        assert horizon == 0.7  # 1.0 - (3 * 0.1)

    def test_calculate_forecast_horizon_long_term(self, scorer):
        """Test forecast horizon for long-term forecast (7 days)."""
        horizon = scorer.calculate_forecast_horizon(7)
        assert horizon == 0.5  # Floor at 0.5

    def test_calculate_forecast_horizon_very_long_term(self, scorer):
        """Test forecast horizon for very long-term forecast (10 days)."""
        horizon = scorer.calculate_forecast_horizon(10)
        assert horizon == 0.5  # Floor at 0.5

    def test_calculate_historical_accuracy_with_mae(self, scorer):
        """Test historical accuracy with MAE data."""
        fusion_data = {
            'metadata': {
                'validation': {
                    'recent_mae': 2.0  # 2 feet MAE
                }
            }
        }

        accuracy = scorer.calculate_historical_accuracy(fusion_data)
        assert accuracy == 0.6  # 1.0 - (2.0 / 5.0)

    def test_calculate_historical_accuracy_perfect(self, scorer):
        """Test historical accuracy with perfect MAE (0)."""
        fusion_data = {
            'metadata': {
                'validation': {
                    'recent_mae': 0.0
                }
            }
        }

        accuracy = scorer.calculate_historical_accuracy(fusion_data)
        assert accuracy == 1.0

    def test_calculate_historical_accuracy_poor(self, scorer):
        """Test historical accuracy with poor MAE (5+)."""
        fusion_data = {
            'metadata': {
                'validation': {
                    'recent_mae': 6.0
                }
            }
        }

        accuracy = scorer.calculate_historical_accuracy(fusion_data)
        assert accuracy == 0.0  # Floored at 0

    def test_calculate_historical_accuracy_no_data(self, scorer):
        """Test historical accuracy with no validation data."""
        fusion_data = {'metadata': {}}
        accuracy = scorer.calculate_historical_accuracy(fusion_data)
        assert accuracy == 0.7  # Default

    def test_get_confidence_category_high(self, scorer):
        """Test confidence category for high score."""
        category = scorer._get_confidence_category(0.85)
        assert category == ConfidenceCategory.HIGH

    def test_get_confidence_category_moderate(self, scorer):
        """Test confidence category for moderate score."""
        category = scorer._get_confidence_category(0.7)
        assert category == ConfidenceCategory.MODERATE

    def test_get_confidence_category_low(self, scorer):
        """Test confidence category for low score."""
        category = scorer._get_confidence_category(0.5)
        assert category == ConfidenceCategory.LOW

    def test_get_confidence_category_very_low(self, scorer):
        """Test confidence category for very low score."""
        category = scorer._get_confidence_category(0.3)
        assert category == ConfidenceCategory.VERY_LOW

    def test_get_confidence_category_boundary_high(self, scorer):
        """Test confidence category at high boundary (0.8)."""
        category = scorer._get_confidence_category(0.8)
        assert category == ConfidenceCategory.HIGH

    def test_get_confidence_category_boundary_moderate(self, scorer):
        """Test confidence category at moderate boundary (0.6)."""
        category = scorer._get_confidence_category(0.6)
        assert category == ConfidenceCategory.MODERATE

    def test_get_confidence_category_boundary_low(self, scorer):
        """Test confidence category at low boundary (0.4)."""
        category = scorer._get_confidence_category(0.4)
        assert category == ConfidenceCategory.LOW

    def test_calculate_confidence_complete(self, scorer, sample_fusion_data):
        """Test complete confidence calculation."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        # Check result structure
        assert isinstance(result, ConfidenceResult)
        assert 0.0 <= result.overall_score <= 1.0
        assert isinstance(result.category, ConfidenceCategory)
        assert len(result.factors) == 5

        # Check all factors present
        assert 'model_consensus' in result.factors
        assert 'source_reliability' in result.factors
        assert 'data_completeness' in result.factors
        assert 'forecast_horizon' in result.factors
        assert 'historical_accuracy' in result.factors

        # Check breakdown
        assert 'overall_score' in result.breakdown
        assert 'overall_score_out_of_10' in result.breakdown
        assert 'category' in result.breakdown
        assert 'factors' in result.breakdown
        assert 'factor_descriptions' in result.breakdown

    def test_calculate_confidence_weighted_formula(self, scorer, sample_fusion_data):
        """Test that confidence uses correct weighted formula."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        # Calculate expected overall score manually
        expected = (
            result.factors['model_consensus'] * 0.30 +
            result.factors['source_reliability'] * 0.25 +
            result.factors['data_completeness'] * 0.20 +
            result.factors['forecast_horizon'] * 0.15 +
            result.factors['historical_accuracy'] * 0.10
        )

        assert abs(result.overall_score - expected) < 0.001

    def test_calculate_confidence_metadata(self, scorer, sample_fusion_data):
        """Test confidence metadata is complete."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=3
        )

        # Check metadata
        assert result.metadata['forecast_horizon_days'] == 3
        assert 'weights' in result.metadata
        assert 'calculated_at' in result.metadata

        # Verify timestamp format
        calc_time = datetime.fromisoformat(result.metadata['calculated_at'])
        assert calc_time.tzinfo is not None

    def test_build_breakdown(self, scorer, sample_fusion_data):
        """Test breakdown includes all required information."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        breakdown = result.breakdown

        # Check all required fields
        assert 'overall_score' in breakdown
        assert 'overall_score_out_of_10' in breakdown
        assert 'category' in breakdown
        assert 'factors' in breakdown
        assert 'factor_descriptions' in breakdown
        assert 'source_counts' in breakdown
        assert 'total_sources' in breakdown

        # Check scores are converted to /10 scale
        assert 0 <= breakdown['overall_score_out_of_10'] <= 10
        for factor_score in breakdown['factors'].values():
            assert 0 <= factor_score <= 10

    def test_format_confidence_for_display(self, scorer, sample_fusion_data):
        """Test confidence display formatting."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        display = format_confidence_for_display(result)

        # Check display includes key information
        assert result.category.value in display
        assert str(result.breakdown['overall_score_out_of_10']) in display
        assert 'Model Consensus' in display
        assert 'Source Reliability' in display
        assert 'Data Completeness' in display
        assert 'Forecast Horizon' in display
        assert 'Historical Accuracy' in display
        assert 'Data Sources:' in display

    def test_confidence_with_minimal_data(self, scorer):
        """Test confidence calculation with minimal data."""
        minimal_data = {
            'swell_events': [],
            'locations': [],
            'metadata': {}
        }

        result = scorer.calculate_confidence(minimal_data, forecast_horizon_days=2)

        # Should still produce valid result with low confidence
        assert isinstance(result, ConfidenceResult)
        assert result.overall_score <= 0.6  # Low confidence expected
        assert result.category in [ConfidenceCategory.LOW, ConfidenceCategory.VERY_LOW]

    def test_confidence_with_excellent_data(self, scorer):
        """Test confidence calculation with excellent data quality."""
        excellent_data = {
            'swell_events': [
                Mock(source='model', primary_components=[Mock(height=2.5)]),
                Mock(source='model', primary_components=[Mock(height=2.51)]),
                Mock(source='buoy', primary_components=[Mock(height=2.5)])
            ],
            'locations': [Mock(), Mock()],
            'metadata': {
                'source_scores': {
                    'ndbc_51001': {'overall_score': 0.95},
                    'ww3': {'overall_score': 0.90},
                    'swan': {'overall_score': 0.92}
                },
                'charts': ['chart1.png', 'chart2.png'],
                'satellite': ['sat1.png'],
                'validation': {'recent_mae': 0.5}
            },
            'buoy_data': [Mock()],
            'model_data': [Mock(), Mock()]
        }

        result = scorer.calculate_confidence(excellent_data, forecast_horizon_days=1)

        # Should produce high confidence
        assert result.overall_score >= 0.75
        assert result.category in [ConfidenceCategory.HIGH, ConfidenceCategory.MODERATE]

    def test_confidence_scorer_logging(self, scorer, sample_fusion_data, caplog):
        """Test that scorer logs appropriately."""
        import logging
        caplog.set_level(logging.INFO)

        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        # Check that key information was logged
        assert 'Calculating confidence' in caplog.text
        assert 'Confidence calculated:' in caplog.text
        assert result.category.value in caplog.text


class TestConfidenceWeights:
    """Test confidence weights validation."""

    def test_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        weights = ConfidenceWeights()
        total = (
            weights.model_consensus +
            weights.source_reliability +
            weights.data_completeness +
            weights.forecast_horizon +
            weights.historical_accuracy
        )
        assert abs(total - 1.0) < 0.001

    def test_custom_weights(self):
        """Test custom weight configuration."""
        weights = ConfidenceWeights(
            model_consensus=0.40,
            source_reliability=0.30,
            data_completeness=0.15,
            forecast_horizon=0.10,
            historical_accuracy=0.05
        )
        assert weights.model_consensus == 0.40
        assert weights.historical_accuracy == 0.05


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
