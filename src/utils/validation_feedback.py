"""
Validation feedback system for adaptive forecast improvement.

This module queries recent forecast performance from the validation database
and generates actionable prompt context for GPT-5 to improve future forecasts.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ShorePerformance(BaseModel):
    """
    Performance metrics for a specific shore.

    Attributes:
        shore: Shore name (e.g., 'North Shore', 'South Shore')
        validation_count: Number of validations in the period
        avg_mae: Average Mean Absolute Error in feet
        avg_rmse: Average Root Mean Squared Error in feet
        avg_bias: Average bias in feet (positive = overpredicting, negative = underpredicting)
        categorical_accuracy: Fraction of correct category predictions (0.0-1.0)
    """

    shore: str = Field(..., description="Shore name")
    validation_count: int = Field(..., ge=0, description="Number of validations")
    avg_mae: float = Field(..., ge=0.0, description="Average MAE in feet")
    avg_rmse: float = Field(..., ge=0.0, description="Average RMSE in feet")
    avg_bias: float = Field(..., description="Average bias in feet (+ = over, - = under)")
    categorical_accuracy: float = Field(..., ge=0.0, le=1.0, description="Category accuracy")

    @field_validator("avg_mae", "avg_rmse")
    @classmethod
    def round_to_one_decimal(cls, v: float) -> float:
        """Round metrics to one decimal place for readability."""
        return round(v, 1)

    @field_validator("avg_bias")
    @classmethod
    def round_bias_to_one_decimal(cls, v: float) -> float:
        """Round bias to one decimal place."""
        return round(v, 1)

    @field_validator("categorical_accuracy")
    @classmethod
    def round_accuracy_to_two_decimals(cls, v: float) -> float:
        """Round accuracy to two decimal places (e.g., 0.85 = 85%)."""
        return round(v, 2)


class PerformanceReport(BaseModel):
    """
    Overall forecast performance report.

    Attributes:
        report_date: ISO format date when report was generated
        lookback_days: Number of days analyzed
        overall_mae: Overall MAE across all shores in feet
        overall_rmse: Overall RMSE across all shores in feet
        overall_categorical: Overall categorical accuracy (0.0-1.0)
        shore_performance: Per-shore performance breakdowns
        has_recent_data: Whether recent validations exist (False if no data)
    """

    report_date: str = Field(..., description="Report generation date (ISO format)")
    lookback_days: int = Field(..., ge=1, description="Days analyzed")
    overall_mae: float = Field(..., ge=0.0, description="Overall MAE in feet")
    overall_rmse: float = Field(..., ge=0.0, description="Overall RMSE in feet")
    overall_categorical: float = Field(
        ..., ge=0.0, le=1.0, description="Overall categorical accuracy"
    )
    shore_performance: list[ShorePerformance] = Field(
        default_factory=list, description="Per-shore metrics"
    )
    has_recent_data: bool = Field(..., description="Whether recent data exists")

    @field_validator("report_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Ensure date is in ISO format."""
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"report_date must be ISO format, got: {v}")
        return v

    @field_validator("overall_mae", "overall_rmse")
    @classmethod
    def round_to_one_decimal(cls, v: float) -> float:
        """Round metrics to one decimal place for readability."""
        return round(v, 1)

    @field_validator("overall_categorical")
    @classmethod
    def round_to_two_decimals(cls, v: float) -> float:
        """Round accuracy to two decimal places."""
        return round(v, 2)


class ValidationFeedback:
    """
    Query recent forecast performance and generate adaptive prompt context.

    This class analyzes validation data to provide actionable feedback for
    improving forecast accuracy. It identifies systematic biases (over/underprediction)
    and generates guidance suitable for inclusion in GPT-5 system prompts.
    """

    def __init__(self, db_path: str = "data/validation.db", lookback_days: int = 7):
        """
        Initialize validation feedback system.

        Args:
            db_path: Path to validation database
            lookback_days: Number of days to analyze (default 7)
        """
        self.db_path = Path(db_path)
        self.lookback_days = lookback_days

        if not self.db_path.exists():
            logger.warning(f"Validation database not found: {self.db_path}")

    def get_recent_performance(self) -> PerformanceReport:
        """
        Query database for recent forecast performance.

        Returns:
            PerformanceReport with overall and per-shore metrics, or empty report if no data

        Raises:
            sqlite3.Error: If database query fails
        """
        # Check if database exists
        if not self.db_path.exists():
            logger.warning(f"Database not found at {self.db_path}, returning empty report")
            return self._empty_report()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Calculate cutoff timestamp aligned to start-of-day for deterministic windows
                now = datetime.now()
                lookback_span = max(self.lookback_days, 1)
                start_date = now.date() - timedelta(days=lookback_span - 1)
                cutoff = datetime.combine(start_date, datetime.min.time())
                cutoff_timestamp = cutoff.timestamp()

                # Query for overall metrics
                overall_query = """
                    SELECT
                        COUNT(*) as total_validations,
                        AVG(v.mae) as avg_mae,
                        AVG(v.rmse) as avg_rmse,
                        AVG(v.height_error) as avg_bias,
                        AVG(CAST(v.category_match AS FLOAT)) as categorical_accuracy
                    FROM validations v
                    WHERE v.validated_at >= ?
                    AND v.mae IS NOT NULL
                """

                cursor.execute(overall_query, (cutoff_timestamp,))
                overall_row = cursor.fetchone()

                # Check if we have any data
                total_validations = overall_row["total_validations"] if overall_row else 0
                if total_validations == 0:
                    logger.info(f"No validations found in last {self.lookback_days} days")
                    return self._empty_report()

                # Query for per-shore metrics
                shore_query = """
                    SELECT
                        p.shore,
                        COUNT(*) as validation_count,
                        AVG(v.mae) as avg_mae,
                        AVG(v.rmse) as avg_rmse,
                        AVG(v.height_error) as avg_bias,
                        AVG(CAST(v.category_match AS FLOAT)) as categorical_accuracy
                    FROM validations v
                    JOIN predictions p ON v.prediction_id = p.id
                    WHERE v.validated_at >= ?
                    AND v.mae IS NOT NULL
                    GROUP BY p.shore
                    ORDER BY p.shore
                """

                cursor.execute(shore_query, (cutoff_timestamp,))
                shore_rows = cursor.fetchall()

                # Build shore performance list
                shore_performance = []
                for row in shore_rows:
                    shore_perf = ShorePerformance(
                        shore=row["shore"],
                        validation_count=row["validation_count"],
                        avg_mae=row["avg_mae"] or 0.0,
                        avg_rmse=row["avg_rmse"] or 0.0,
                        avg_bias=row["avg_bias"] or 0.0,
                        categorical_accuracy=row["categorical_accuracy"] or 0.0,
                    )
                    shore_performance.append(shore_perf)

                # Build overall report
                report = PerformanceReport(
                    report_date=datetime.now().isoformat(),
                    lookback_days=self.lookback_days,
                    overall_mae=overall_row["avg_mae"] or 0.0,
                    overall_rmse=overall_row["avg_rmse"] or 0.0,
                    overall_categorical=overall_row["categorical_accuracy"] or 0.0,
                    shore_performance=shore_performance,
                    has_recent_data=True,
                )

                logger.info(
                    f"Generated performance report: {total_validations} validations, "
                    f"MAE={report.overall_mae:.1f}ft"
                )
                return report

        except sqlite3.Error as e:
            logger.error(f"Database error while querying performance: {e}")
            raise

    def _empty_report(self) -> PerformanceReport:
        """
        Generate empty report when no data is available.

        Returns:
            PerformanceReport with has_recent_data=False
        """
        return PerformanceReport(
            report_date=datetime.now().isoformat(),
            lookback_days=self.lookback_days,
            overall_mae=0.0,
            overall_rmse=0.0,
            overall_categorical=0.0,
            shore_performance=[],
            has_recent_data=False,
        )

    def generate_prompt_context(self, report: PerformanceReport) -> str:
        """
        Convert performance report into text suitable for GPT-5 system prompt.

        Args:
            report: PerformanceReport from get_recent_performance()

        Returns:
            Formatted string with performance summary and adaptive guidance,
            or empty string if no recent data exists

        Example output:
            ```
            RECENT FORECAST PERFORMANCE (Last 7 days, 15 validations):
            Overall MAE: 1.8 ft (target: <2.0 ft) ✓
            Overall RMSE: 2.3 ft
            Categorical Accuracy: 85%

            Per-Shore Performance:
            - North Shore: MAE 1.5 ft, slight underprediction (-0.3 ft avg bias)
            - South Shore: MAE 2.1 ft, overpredicting (+0.5 ft avg bias) ⚠️

            ADAPTIVE GUIDANCE:
            - South Shore forecasts have been running high. Be conservative with height predictions.
            - North Shore predictions are accurate but trending slightly low. Maintain current approach.
            ```
        """
        if not report.has_recent_data:
            logger.debug("No recent data available, returning empty prompt context")
            return ""

        lines = []

        # Header with validation count
        total_validations = sum(sp.validation_count for sp in report.shore_performance)
        lines.append(
            f"RECENT FORECAST PERFORMANCE (Last {report.lookback_days} days, "
            f"{total_validations} validations):"
        )

        # Overall metrics with target comparison
        mae_status = "✓" if report.overall_mae < 2.0 else "⚠️"
        lines.append(f"Overall MAE: {report.overall_mae:.1f} ft (target: <2.0 ft) {mae_status}")
        lines.append(f"Overall RMSE: {report.overall_rmse:.1f} ft")
        lines.append(f"Categorical Accuracy: {int(report.overall_categorical * 100)}%")
        lines.append("")

        # Per-shore breakdown
        if report.shore_performance:
            lines.append("Per-Shore Performance:")
            for sp in report.shore_performance:
                bias_desc = self._describe_bias(sp.avg_bias)
                bias_warning = " ⚠️" if abs(sp.avg_bias) > 0.5 else ""
                lines.append(f"- {sp.shore}: MAE {sp.avg_mae:.1f} ft, {bias_desc}{bias_warning}")
            lines.append("")

        # Adaptive guidance
        guidance = self._generate_guidance(report)
        if guidance:
            lines.append("ADAPTIVE GUIDANCE:")
            for item in guidance:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def _describe_bias(self, bias: float) -> str:
        """
        Generate human-readable bias description.

        Args:
            bias: Average bias in feet (+ = overpredicting, - = underpredicting)

        Returns:
            Description string (e.g., "overpredicting (+0.5 ft avg bias)")
        """
        abs_bias = abs(bias)

        if abs_bias < 0.2:
            return "well-calibrated (minimal bias)"
        elif abs_bias < 0.5:
            if bias > 0:
                return f"slight overprediction (+{bias:.1f} ft avg bias)"
            else:
                return f"slight underprediction ({bias:.1f} ft avg bias)"
        else:
            if bias > 0:
                return f"overpredicting (+{bias:.1f} ft avg bias)"
            else:
                return f"underpredicting ({bias:.1f} ft avg bias)"

    def _generate_guidance(self, report: PerformanceReport) -> list[str]:
        """
        Generate actionable guidance based on performance metrics.

        Args:
            report: PerformanceReport with metrics

        Returns:
            List of guidance strings
        """
        guidance = []

        # Check for overall poor performance
        if report.overall_mae > 2.5:
            guidance.append(
                "Overall forecast accuracy is below target. Review data sources "
                "and consider more conservative predictions."
            )

        # Per-shore bias guidance
        for sp in report.shore_performance:
            # Significant overprediction
            if sp.avg_bias > 0.5:
                guidance.append(
                    f"{sp.shore} forecasts have been running high. "
                    f"Be conservative with height predictions."
                )

            # Significant underprediction
            elif sp.avg_bias < -0.5:
                guidance.append(
                    f"{sp.shore} forecasts have been running low. "
                    f"Consider upward adjustments when conditions support it."
                )

            # Good performance - reinforce
            elif sp.avg_mae < 1.5 and abs(sp.avg_bias) <= 0.3:
                guidance.append(
                    f"{sp.shore} predictions are accurate and well-calibrated. "
                    f"Maintain current approach."
                )

        # Categorical accuracy issues
        if report.overall_categorical < 0.7:
            guidance.append(
                "Categorical predictions (flat/small/moderate/large) need improvement. "
                "Pay closer attention to size thresholds."
            )

        return guidance


__all__ = ["ValidationFeedback", "PerformanceReport", "ShorePerformance"]
