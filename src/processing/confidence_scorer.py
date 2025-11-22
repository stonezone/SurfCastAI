"""
Confidence Scorer for SurfCastAI.

Calculates overall forecast confidence based on multiple factors including
model consensus, source reliability, data completeness, forecast horizon,
and historical accuracy. Provides transparent scoring breakdown for users.

Reference: CONSOLIDATION_EXECUTION_PLAN.md Phase 3, Task 3.2 (lines 1128-1247)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, stdev

from .models.confidence import ConfidenceReport


@dataclass
class ConfidenceWeights:
    """Weights for different confidence factors."""
    model_consensus: float = 0.30      # Agreement between different models
    source_reliability: float = 0.25   # Weighted average of source scores
    data_completeness: float = 0.20    # Percentage of expected data received
    forecast_horizon: float = 0.15     # Confidence decreases with time
    historical_accuracy: float = 0.10  # Recent validation performance


class ConfidenceScorer:
    """
    Calculates forecast confidence based on multiple data quality factors.

    Features:
    - Five-factor confidence model (consensus, reliability, completeness, horizon, accuracy)
    - Transparent scoring breakdown for users
    - Integration with source scoring and validation systems
    - Four-tier confidence categories

    Scoring Formula:
    overall_score = (consensus * 0.30) + (reliability * 0.25) +
                    (completeness * 0.20) + (horizon * 0.15) +
                    (accuracy * 0.10)
    """

    # Expected data sources for completeness calculation
    EXPECTED_SOURCES = ['buoys', 'models', 'charts', 'satellite']

    def __init__(
        self,
        weights: Optional[ConfidenceWeights] = None,
        validation_db: Optional[Any] = None
    ):
        """
        Initialize the confidence scorer.

        Args:
            weights: Optional custom confidence weights
            validation_db: Optional validation database for historical accuracy
        """
        self.logger = logging.getLogger('processing.confidence_scorer')
        self.weights = weights or ConfidenceWeights()
        self.validation_db = validation_db

        self.logger.info(
            f"ConfidenceScorer initialized with weights: "
            f"consensus={self.weights.model_consensus}, "
            f"reliability={self.weights.source_reliability}, "
            f"completeness={self.weights.data_completeness}, "
            f"horizon={self.weights.forecast_horizon}, "
            f"accuracy={self.weights.historical_accuracy}"
        )

    def calculate_confidence(
        self,
        fusion_data: Dict[str, Any],
        forecast_horizon_days: int = 2
    ) -> ConfidenceReport:
        """
        Calculate overall confidence score for a forecast.

        This method should be called after data fusion but before forecast generation.

        Args:
            fusion_data: Fused data from DataFusionSystem containing:
                - swell_events: List of detected swell events
                - locations: List of forecast locations
                - metadata: Including source_scores, confidence factors
            forecast_horizon_days: Number of days ahead being forecast

        Returns:
            ConfidenceReport with overall score, category, factors, breakdown, and warnings
        """
        self.logger.info(f"Calculating confidence for {forecast_horizon_days}-day forecast")

        # Extract component scores
        consensus_score = self.calculate_model_consensus(fusion_data)
        reliability_score = self.calculate_source_reliability(fusion_data)
        completeness_score = self.calculate_data_completeness(fusion_data)
        horizon_score = self.calculate_forecast_horizon(forecast_horizon_days)
        accuracy_score = self.calculate_historical_accuracy(fusion_data)

        # Store individual factor scores
        factors = {
            'model_consensus': consensus_score,
            'source_reliability': reliability_score,
            'data_completeness': completeness_score,
            'forecast_horizon': horizon_score,
            'historical_accuracy': accuracy_score
        }

        # Calculate weighted overall score
        overall_score = (
            consensus_score * self.weights.model_consensus +
            reliability_score * self.weights.source_reliability +
            completeness_score * self.weights.data_completeness +
            horizon_score * self.weights.forecast_horizon +
            accuracy_score * self.weights.historical_accuracy
        )

        # Determine confidence category using ConfidenceReport's static method
        category = ConfidenceReport.categorize_score(overall_score)

        # Build source-level breakdown
        breakdown = self._build_source_breakdown(fusion_data)

        # Collect warnings based on confidence factors
        warnings = self._collect_warnings(
            overall_score,
            factors,
            fusion_data,
            forecast_horizon_days
        )

        # Create ConfidenceReport
        report = ConfidenceReport(
            overall_score=overall_score,
            category=category,
            factors=factors,
            breakdown=breakdown,
            warnings=warnings
        )

        # Log using the report's built-in summary method
        self.logger.info(report.to_log_summary())

        return report

    def calculate_model_consensus(self, fusion_data: Dict[str, Any]) -> float:
        """
        Calculate model consensus score based on agreement between models.

        Formula: 1.0 / (1.0 + variance)
        High variance = low consensus, low variance = high consensus

        Args:
            fusion_data: Fused data with swell events from multiple models

        Returns:
            Consensus score (0.0 to 1.0)
        """
        try:
            # Extract swell events from different model sources
            swell_events = fusion_data.get('swell_events', [])

            if not swell_events:
                self.logger.debug("No swell events for consensus calculation")
                return 0.5  # Neutral if no events

            # Group events by source
            model_events = [e for e in swell_events if e.source == 'model']

            if len(model_events) < 2:
                self.logger.debug("Need at least 2 model events for consensus")
                return 0.7  # High confidence if single model (no disagreement)

            # Extract wave heights from model events
            heights = []
            for event in model_events:
                if event.primary_components:
                    # Use maximum component height
                    max_height = max(c.height for c in event.primary_components)
                    heights.append(max_height)

            if len(heights) < 2:
                return 0.7

            # Calculate variance in predictions
            mean_height = mean(heights)
            if mean_height == 0:
                return 0.5

            variance = stdev(heights) / mean_height  # Coefficient of variation

            # Convert to consensus score (higher variance = lower consensus)
            consensus = 1.0 / (1.0 + variance)

            self.logger.debug(
                f"Model consensus: {len(model_events)} models, "
                f"heights={heights}, variance={variance:.3f}, score={consensus:.3f}"
            )

            return min(1.0, max(0.0, consensus))

        except Exception as e:
            self.logger.warning(f"Error calculating model consensus: {e}")
            return 0.5  # Neutral on error

    def calculate_source_reliability(self, fusion_data: Dict[str, Any]) -> float:
        """
        Calculate weighted average of source reliability scores.

        Formula: sum(reliability_scores) / len(sources)

        Args:
            fusion_data: Fused data with source_scores in metadata

        Returns:
            Reliability score (0.0 to 1.0)
        """
        try:
            # Extract source scores from metadata
            metadata = fusion_data.get('metadata', {})
            source_scores = metadata.get('source_scores', {})

            if not source_scores:
                self.logger.debug("No source scores available")
                return 0.5  # Neutral if no scores

            # Calculate weighted average of overall scores
            scores = [score['overall_score'] for score in source_scores.values()]

            if not scores:
                return 0.5

            reliability = sum(scores) / len(scores)

            self.logger.debug(
                f"Source reliability: {len(scores)} sources, "
                f"average={reliability:.3f}"
            )

            return min(1.0, max(0.0, reliability))

        except Exception as e:
            self.logger.warning(f"Error calculating source reliability: {e}")
            return 0.5

    def calculate_data_completeness(self, fusion_data: Dict[str, Any]) -> float:
        """
        Calculate data completeness based on expected vs received data sources.

        Formula: len(received) / len(expected)
        Expected sources: buoys, models, charts, satellite

        Args:
            fusion_data: Fused data with available data sources

        Returns:
            Completeness score (0.0 to 1.0)
        """
        try:
            received_sources = []

            # Check for buoy data
            if fusion_data.get('buoy_data') or any(
                e.source == 'buoy' for e in fusion_data.get('swell_events', [])
            ):
                received_sources.append('buoys')

            # Check for model data
            if fusion_data.get('model_data') or any(
                e.source == 'model' for e in fusion_data.get('swell_events', [])
            ):
                received_sources.append('models')

            # Check for chart data
            metadata = fusion_data.get('metadata', {})
            if metadata.get('charts'):
                received_sources.append('charts')

            # Check for satellite data
            if metadata.get('satellite'):
                received_sources.append('satellite')

            # Calculate completeness ratio
            completeness = len(received_sources) / len(self.EXPECTED_SOURCES)

            self.logger.debug(
                f"Data completeness: {len(received_sources)}/{len(self.EXPECTED_SOURCES)} "
                f"sources ({', '.join(received_sources)}), score={completeness:.3f}"
            )

            return min(1.0, max(0.0, completeness))

        except Exception as e:
            self.logger.warning(f"Error calculating data completeness: {e}")
            return 0.5

    def calculate_forecast_horizon(self, days_ahead: int) -> float:
        """
        Calculate confidence based on forecast horizon.

        Formula: max(0.5, 1.0 - (days_ahead * 0.1))
        Confidence decreases linearly with forecast horizon,
        with a minimum of 0.5 for long-range forecasts.

        Args:
            days_ahead: Number of days ahead being forecast

        Returns:
            Horizon score (0.5 to 1.0)
        """
        # Linear decay with floor at 0.5
        horizon_score = max(0.5, 1.0 - (days_ahead * 0.1))

        self.logger.debug(
            f"Forecast horizon: {days_ahead} days, score={horizon_score:.3f}"
        )

        return horizon_score

    def calculate_historical_accuracy(self, fusion_data: Dict[str, Any]) -> float:
        """
        Calculate confidence based on recent validation performance.

        Formula: max(0.0, 1.0 - (recent_mae / 5.0))
        MAE (Mean Absolute Error) in feet compared to observations.

        Args:
            fusion_data: Fused data (may include validation history)

        Returns:
            Accuracy score (0.0 to 1.0)
        """
        try:
            # If validation database is available, query recent accuracy
            if self.validation_db:
                # TODO: Query validation database for recent MAE
                # recent_mae = self.validation_db.get_recent_mae(days=7)
                # accuracy = max(0.0, 1.0 - (recent_mae / 5.0))
                # return min(1.0, accuracy)
                pass

            # Check fusion metadata for validation info
            metadata = fusion_data.get('metadata', {})
            validation = metadata.get('validation', {})
            recent_mae = validation.get('recent_mae')

            if recent_mae is not None:
                # Convert MAE to accuracy score
                # MAE of 0 = perfect (1.0), MAE of 5ft+ = poor (0.0)
                accuracy = max(0.0, 1.0 - (recent_mae / 5.0))

                self.logger.debug(
                    f"Historical accuracy: MAE={recent_mae:.2f}ft, score={accuracy:.3f}"
                )

                return min(1.0, accuracy)

            # Default to good accuracy if no validation data
            self.logger.debug("No validation data available, using default accuracy")
            return 0.7

        except Exception as e:
            self.logger.warning(f"Error calculating historical accuracy: {e}")
            return 0.7

    def _build_source_breakdown(self, fusion_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Build source-level confidence breakdown (e.g., buoy, pressure, model).

        Args:
            fusion_data: Fused data containing source information

        Returns:
            Dictionary mapping source types to confidence scores
        """
        breakdown = {}

        # Extract metadata
        metadata = fusion_data.get('metadata', {})
        source_scores = metadata.get('source_scores', {})

        # Calculate buoy confidence (average of buoy source scores)
        buoy_scores = [
            score['overall_score']
            for source_id, score in source_scores.items()
            if 'buoy' in source_id.lower() or 'ndbc' in source_id.lower()
        ]
        if buoy_scores:
            breakdown['buoy_confidence'] = sum(buoy_scores) / len(buoy_scores)

        # Calculate model confidence (average of model source scores)
        model_scores = [
            score['overall_score']
            for source_id, score in source_scores.items()
            if 'model' in source_id.lower() or 'swan' in source_id.lower() or 'ww3' in source_id.lower()
        ]
        if model_scores:
            breakdown['model_confidence'] = sum(model_scores) / len(model_scores)

        # Calculate pressure/weather confidence (average of weather source scores)
        weather_scores = [
            score['overall_score']
            for source_id, score in source_scores.items()
            if 'weather' in source_id.lower() or 'nws' in source_id.lower()
        ]
        if weather_scores:
            breakdown['pressure_confidence'] = sum(weather_scores) / len(weather_scores)

        return breakdown

    def _collect_warnings(
        self,
        overall_score: float,
        factors: Dict[str, float],
        fusion_data: Dict[str, Any],
        forecast_horizon_days: int
    ) -> List[str]:
        """
        Collect quality warnings based on confidence factors.

        Args:
            overall_score: Overall confidence score
            factors: Individual factor scores
            fusion_data: Fused data
            forecast_horizon_days: Forecast horizon in days

        Returns:
            List of warning messages
        """
        warnings = []

        # Overall confidence warnings
        if overall_score < 0.4:
            warnings.append("Very low forecast confidence due to poor data quality or high uncertainty")
        elif overall_score < 0.6:
            warnings.append("Low forecast confidence - limited data or model disagreement present")

        # Factor-specific warnings
        if factors['model_consensus'] < 0.5:
            warnings.append("Significant disagreement between model predictions")

        if factors['data_completeness'] < 0.5:
            warnings.append("Limited data sources available - missing expected data types")

        if factors['source_reliability'] < 0.6:
            warnings.append("Some data sources have low reliability scores")

        if factors['historical_accuracy'] < 0.5:
            warnings.append("Recent forecasts have shown lower accuracy")

        # Check for missing buoy data
        metadata = fusion_data.get('metadata', {})
        source_scores = metadata.get('source_scores', {})
        buoy_count = sum(1 for s in source_scores if 'buoy' in s.lower() or 'ndbc' in s.lower())

        if buoy_count == 0:
            warnings.append("No buoy data available")
        elif buoy_count < 2:
            warnings.append("Limited buoy data (only 1 buoy)")

        # Check for model disagreement
        swell_events = fusion_data.get('swell_events', [])
        model_events = [e for e in swell_events if e.source == 'model']

        if len(model_events) == 0:
            warnings.append("No model data available")
        elif len(model_events) == 1:
            warnings.append("Limited model data (only 1 model)")

        # Long forecast horizon warning
        if forecast_horizon_days > 5:
            warnings.append(f"Long forecast horizon ({forecast_horizon_days} days) - reduced confidence")

        return warnings


def format_confidence_for_display(report: ConfidenceReport) -> str:
    """
    Format confidence report for user-friendly display in forecast output.

    Args:
        report: ConfidenceReport from ConfidenceScorer

    Returns:
        Formatted string for display
    """
    lines = [
        f"**Forecast Confidence: {report.category.upper()}** ({report.overall_score:.2f})",
        "",
        "**Confidence Factors:**"
    ]

    # Add each factor with its score
    factor_names = {
        'model_consensus': 'Model Consensus',
        'source_reliability': 'Source Reliability',
        'data_completeness': 'Data Completeness',
        'forecast_horizon': 'Forecast Horizon',
        'historical_accuracy': 'Historical Accuracy'
    }

    for factor_key, factor_name in factor_names.items():
        score = report.factors.get(factor_key, 0.0)
        lines.append(f"- {factor_name}: {score:.2f}")

    # Add source breakdown if available
    if report.breakdown:
        lines.append("")
        lines.append("**Source Breakdown:**")
        for source_key, source_score in sorted(report.breakdown.items()):
            # Convert snake_case to Title Case for display
            source_name = source_key.replace('_', ' ').title()
            lines.append(f"- {source_name}: {source_score:.2f}")

    # Add warnings if any
    if report.warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for warning in report.warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)
