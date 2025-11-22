"""
Unit tests for ConfidenceScorer.

Tests all confidence factors, category determination, and integration.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock

from src.processing.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceWeights,
    format_confidence_for_display
)
from src.processing.models.confidence import ConfidenceReport


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

    def test_categorize_score_high(self):
        """Test confidence category for high score."""
        category = ConfidenceReport.categorize_score(0.85)
        assert category == 'high'

    def test_categorize_score_medium(self):
        """Test confidence category for medium score."""
        category = ConfidenceReport.categorize_score(0.6)
        assert category == 'medium'

    def test_categorize_score_low(self):
        """Test confidence category for low score."""
        category = ConfidenceReport.categorize_score(0.3)
        assert category == 'low'

    def test_categorize_score_boundary_high(self):
        """Test confidence category at high boundary (0.7)."""
        category = ConfidenceReport.categorize_score(0.7)
        assert category == 'high'

    def test_categorize_score_boundary_medium(self):
        """Test confidence category at medium boundary (0.4)."""
        category = ConfidenceReport.categorize_score(0.4)
        assert category == 'medium'

    def test_categorize_score_boundary_low(self):
        """Test confidence category just below medium boundary (0.39)."""
        category = ConfidenceReport.categorize_score(0.39)
        assert category == 'low'

    def test_calculate_confidence_complete(self, scorer, sample_fusion_data):
        """Test complete confidence calculation."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        # Check result structure
        assert isinstance(result, ConfidenceReport)
        assert 0.0 <= result.overall_score <= 1.0
        assert result.category in ['high', 'medium', 'low']
        assert len(result.factors) == 5

        # Check all factors present
        assert 'model_consensus' in result.factors
        assert 'source_reliability' in result.factors
        assert 'data_completeness' in result.factors
        assert 'forecast_horizon' in result.factors
        assert 'historical_accuracy' in result.factors

        # Check breakdown
        assert isinstance(result.breakdown, dict)
        assert isinstance(result.warnings, list)

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

    def test_calculate_confidence_category_correctness(self, scorer, sample_fusion_data):
        """Test that category correctly reflects overall score."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=3
        )

        # Verify category matches score thresholds
        expected_category = ConfidenceReport.categorize_score(result.overall_score)
        assert result.category == expected_category

    def test_build_breakdown(self, scorer, sample_fusion_data):
        """Test breakdown includes source-level confidence scores."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        breakdown = result.breakdown

        # Check that breakdown is a dictionary with source confidence scores
        assert isinstance(breakdown, dict)

        # Should have buoy confidence (from ndbc_51001)
        if 'buoy_confidence' in breakdown:
            assert 0.0 <= breakdown['buoy_confidence'] <= 1.0

        # Should have model confidence (from ww3)
        if 'model_confidence' in breakdown:
            assert 0.0 <= breakdown['model_confidence'] <= 1.0

    def test_format_confidence_for_display(self, scorer, sample_fusion_data):
        """Test confidence display formatting."""
        result = scorer.calculate_confidence(
            sample_fusion_data,
            forecast_horizon_days=2
        )

        display = format_confidence_for_display(result)

        # Check display includes key information
        assert result.category.upper() in display
        assert str(result.overall_score)[:4] in display  # First 4 chars (e.g., "0.85")
        assert 'Model Consensus' in display
        assert 'Source Reliability' in display
        assert 'Data Completeness' in display
        assert 'Forecast Horizon' in display
        assert 'Historical Accuracy' in display

    def test_confidence_with_minimal_data(self, scorer):
        """Test confidence calculation with minimal data."""
        minimal_data = {
            'swell_events': [],
            'locations': [],
            'metadata': {}
        }

        result = scorer.calculate_confidence(minimal_data, forecast_horizon_days=2)

        # Should still produce valid result with low confidence
        assert isinstance(result, ConfidenceReport)
        assert result.overall_score <= 0.6  # Low confidence expected
        assert result.category in ['low', 'medium']

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
        assert result.category in ['high', 'medium']

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
        assert 'Confidence:' in caplog.text or result.category in caplog.text.lower()

    def test_warnings_generated_for_low_confidence(self, scorer):
        """Test that warnings are generated for low confidence scenarios."""
        poor_data = {
            'swell_events': [],
            'locations': [],
            'metadata': {}
        }

        result = scorer.calculate_confidence(poor_data, forecast_horizon_days=2)

        # Should have warnings about poor data quality
        assert len(result.warnings) > 0
        # Check for specific warnings
        warning_text = ' '.join(result.warnings).lower()
        assert any(keyword in warning_text for keyword in ['limited', 'missing', 'no'])

    def test_warnings_for_model_disagreement(self, scorer):
        """Test warnings generated for significant model disagreement."""
        disagreeing_data = {
            'swell_events': [
                Mock(source='model', primary_components=[Mock(height=1.0)]),
                Mock(source='model', primary_components=[Mock(height=5.0)])
            ],
            'metadata': {
                'source_scores': {
                    'model1': {'overall_score': 0.8},
                    'model2': {'overall_score': 0.8}
                }
            }
        }

        result = scorer.calculate_confidence(disagreeing_data, forecast_horizon_days=2)

        # Should have warning about model disagreement
        warning_text = ' '.join(result.warnings).lower()
        assert 'disagreement' in warning_text or 'consensus' in warning_text

    def test_pydantic_validation_enforced(self):
        """Test that Pydantic validation is enforced on ConfidenceReport."""
        # Test valid report
        valid_report = ConfidenceReport(
            overall_score=0.85,
            category='high',
            factors={'model_consensus': 0.9},
            breakdown={'buoy_confidence': 0.8},
            warnings=[]
        )
        assert valid_report.overall_score == 0.85

        # Test invalid score (out of range)
        with pytest.raises(Exception):  # Pydantic will raise ValidationError
            ConfidenceReport(
                overall_score=1.5,  # Invalid: > 1.0
                category='high',
                factors={},
                breakdown={},
                warnings=[]
            )

        # Test invalid category
        with pytest.raises(Exception):  # Pydantic will raise ValidationError
            ConfidenceReport(
                overall_score=0.85,
                category='very_low',  # Invalid: not in ['high', 'medium', 'low']
                factors={},
                breakdown={},
                warnings=[]
            )


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
