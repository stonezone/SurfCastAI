"""Query recent forecast performance for adaptive prompt injection.

This module provides efficient extraction of forecast performance metrics from
validation.db to enable adaptive prompt injection. Key features:

- Shore-level accuracy metrics (MAE, RMSE, bias)
- Bias detection with statistical significance filtering
- Adaptive time window expansion for cold start scenarios
- Outlier filtering to handle data quality issues
- Human-readable prompt context generation

Performance: <50ms for 3 queries on 10,000 validations (with proper indexing).

Example:
    >>> from src.validation.performance import build_performance_context
    >>> context = build_performance_context(days=7)
    >>> print(context)
    ## Recent Forecast Performance
    Based on 28 validations over the last 7 days:
    - Overall MAE: 1.15ft
    ...
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes recent forecast performance for prompt adaptation.

    This class executes optimized SQL queries against validation.db to extract
    recent forecast accuracy metrics. Designed for minimal overhead during
    forecast generation (<50ms total query time).

    Attributes:
        db_path: Path to SQLite validation database

    Performance Requirements:
        - Requires idx_validations_validated_at index on validations.validated_at
        - Query time <50ms @ 10K validations (with index)
        - Without index: 1.5s @ 10K validations (NOT ACCEPTABLE)
    """

    def __init__(self, db_path: str = "data/validation.db"):
        """Initialize performance analyzer.

        Args:
            db_path: Path to validation database (must exist)
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            logger.warning(f"Validation database not found: {db_path}")

    def get_recent_performance(
        self,
        days: int = 7,
        min_samples: int = 10,
        outlier_threshold: float = 10.0
    ) -> Dict[str, Any]:
        """Fetch recent forecast performance metrics.

        Executes 3 optimized queries:
        1. Overall system accuracy (MAE, RMSE, bias)
        2. Shore-level performance breakdown
        3. Bias detection with significance filtering

        If insufficient data (<min_samples), automatically expands time window
        up to 30 days (recursive).

        Args:
            days: Time window for analysis (default 7 days)
            min_samples: Minimum validations required for reliable metrics
            outlier_threshold: Exclude errors > this value (feet)

        Returns:
            Dictionary with keys:
                - has_data: bool (sufficient data for analysis)
                - overall: dict (system-wide metrics)
                    - total_validations: int
                    - overall_mae: float (feet)
                    - overall_rmse: float (feet)
                    - overall_categorical: float (0-1 accuracy)
                    - avg_bias: float (signed error, ft)
                - by_shore: dict (shore -> metrics dict)
                    - validation_count: int
                    - avg_mae: float (feet)
                    - avg_rmse: float (feet)
                    - avg_height_error: float (bias, ft)
                    - categorical_accuracy: float (0-1)
                - bias_alerts: list (shores with significant bias)
                    - shore: str
                    - avg_bias: float (signed error, ft)
                    - sample_size: int
                    - bias_category: str (OVERPREDICTING/UNDERPREDICTING)
                - metadata: dict (query info)
                    - query_timestamp: str (ISO8601)
                    - window_days: int
                    - min_samples_threshold: int
                    - outlier_threshold_ft: float

        Example:
            >>> analyzer = PerformanceAnalyzer()
            >>> perf = analyzer.get_recent_performance(days=7)
            >>> if perf['has_data']:
            ...     print(f"Overall MAE: {perf['overall']['overall_mae']}ft")
            Overall MAE: 1.15ft
        """
        if not self.db_path.exists():
            return self._empty_result(days, "Database not found")

        try:
            overall = self._query_overall_performance(days, outlier_threshold)

            # Check for sufficient data
            if overall['total_validations'] < min_samples:
                logger.warning(
                    f"Insufficient validation data: {overall['total_validations']} < {min_samples} "
                    f"(window={days} days)"
                )

                # Try expanding window (recursive with cap at 30 days)
                if days < 30:
                    expanded_days = min(days * 2, 30)
                    logger.info(f"Expanding window to {expanded_days} days")
                    return self.get_recent_performance(
                        days=expanded_days,
                        min_samples=min_samples,
                        outlier_threshold=outlier_threshold
                    )

                return self._empty_result(
                    days,
                    f"Insufficient samples ({overall['total_validations']} < {min_samples})"
                )

            # Fetch detailed metrics
            by_shore = self._query_shore_performance(days, outlier_threshold)
            bias_alerts = self._query_bias_detection(days, outlier_threshold)

            return {
                'has_data': True,
                'overall': overall,
                'by_shore': by_shore,
                'bias_alerts': bias_alerts,
                'metadata': {
                    'query_timestamp': datetime.now().isoformat(),
                    'window_days': days,
                    'min_samples_threshold': min_samples,
                    'outlier_threshold_ft': outlier_threshold
                }
            }

        except Exception as e:
            logger.error(f"Performance query failed: {e}", exc_info=True)
            return self._empty_result(days, f"Query error: {str(e)}")

    def _query_overall_performance(
        self,
        days: int,
        outlier_threshold: float
    ) -> Dict[str, Any]:
        """Execute Query 2: Overall system performance.

        SQL: Aggregates MAE/RMSE/bias across all shores for time window.

        Performance: ~8ms @ 10K validations (with idx_validations_validated_at)

        Args:
            days: Lookback window (e.g., 7)
            outlier_threshold: Exclude |height_error| > this value

        Returns:
            Dict with keys: total_validations, overall_mae, overall_rmse,
            overall_categorical, avg_bias
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_validations,
                    ROUND(AVG(mae), 2) as overall_mae,
                    ROUND(AVG(rmse), 2) as overall_rmse,
                    ROUND(AVG(CASE WHEN category_match THEN 1.0 ELSE 0.0 END), 3) as overall_categorical,
                    ROUND(AVG(height_error), 2) as avg_bias
                FROM validations
                WHERE validated_at >= datetime('now', '-' || ? || ' days')
                  AND ABS(height_error) < ?
            """, (days, outlier_threshold))

            row = cursor.fetchone()
            return dict(row) if row else {}

    def _query_shore_performance(
        self,
        days: int,
        outlier_threshold: float
    ) -> Dict[str, Dict[str, Any]]:
        """Execute Query 1: Shore-level performance metrics.

        SQL: Groups by shore, calculates MAE/RMSE/bias for each.

        Performance: ~15ms @ 10K validations (with idx_validations_validated_at)

        Args:
            days: Lookback window
            outlier_threshold: Exclude |height_error| > this value

        Returns:
            Dict mapping shore name -> metrics dict. Missing shores have None value.

        Example:
            {
                'North Shore': {
                    'shore': 'North Shore',
                    'validation_count': 10,
                    'avg_mae': 1.42,
                    'avg_rmse': 1.85,
                    'avg_height_error': 0.85,  # Bias (signed)
                    'categorical_accuracy': 0.700
                },
                'South Shore': {...},
                'West Shore': None,  # No validations
                'East Shore': {...}
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    p.shore,
                    COUNT(*) as validation_count,
                    ROUND(AVG(v.mae), 2) as avg_mae,
                    ROUND(AVG(v.rmse), 2) as avg_rmse,
                    ROUND(AVG(v.height_error), 2) as avg_height_error,
                    ROUND(AVG(CASE WHEN v.category_match THEN 1.0 ELSE 0.0 END), 3) as categorical_accuracy
                FROM validations v
                JOIN predictions p ON v.prediction_id = p.id
                WHERE v.validated_at >= datetime('now', '-' || ? || ' days')
                  AND ABS(v.height_error) < ?
                GROUP BY p.shore
                ORDER BY p.shore
            """, (days, outlier_threshold))

            results = cursor.fetchall()

            # Normalize to ensure all Oahu shores present (None if no data)
            OAHU_SHORES = ['North Shore', 'South Shore', 'West Shore', 'East Shore']
            by_shore = {shore: None for shore in OAHU_SHORES}

            for row in results:
                by_shore[row['shore']] = dict(row)

            return by_shore

    def _query_bias_detection(
        self,
        days: int,
        outlier_threshold: float,
        min_samples: int = 3,
        bias_threshold: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Execute Query 3: Bias detection with significance filtering.

        SQL: Identifies shores with systematic over/underprediction.

        Bias Categories:
        - OVERPREDICTING: avg_height_error > +1.0ft (forecasts too high)
        - UNDERPREDICTING: avg_height_error < -1.0ft (forecasts too low)
        - BALANCED: -1.0 to +1.0ft (acceptable variation)

        Filters:
        - Requires min_samples (default 3) to avoid spurious signals
        - Excludes BALANCED shores from results (only returns alerts)

        Performance: ~15ms @ 10K validations (with idx_validations_validated_at)

        Args:
            days: Lookback window
            outlier_threshold: Exclude |height_error| > this value
            min_samples: Minimum validations required for significance
            bias_threshold: Absolute bias threshold (feet)

        Returns:
            List of dicts for shores with significant bias (sorted by severity).
            Empty list if all shores balanced.

        Example:
            [
                {
                    'shore': 'North Shore',
                    'avg_bias': 1.25,  # Overpredicting by 1.25ft
                    'sample_size': 10,
                    'bias_category': 'OVERPREDICTING'
                }
            ]
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    p.shore,
                    ROUND(AVG(v.height_error), 2) as avg_bias,
                    COUNT(*) as sample_size,
                    CASE
                        WHEN AVG(v.height_error) > ? THEN 'OVERPREDICTING'
                        WHEN AVG(v.height_error) < -? THEN 'UNDERPREDICTING'
                        ELSE 'BALANCED'
                    END as bias_category
                FROM validations v
                JOIN predictions p ON v.prediction_id = p.id
                WHERE v.validated_at >= datetime('now', '-' || ? || ' days')
                  AND ABS(v.height_error) < ?
                GROUP BY p.shore
                HAVING COUNT(*) >= ?
                ORDER BY ABS(AVG(v.height_error)) DESC
            """, (bias_threshold, bias_threshold, days, outlier_threshold, min_samples))

            results = cursor.fetchall()

            # Filter out BALANCED shores (only return alerts)
            return [dict(row) for row in results if row['bias_category'] != 'BALANCED']

    def _empty_result(self, days: int, reason: str) -> Dict[str, Any]:
        """Return empty result structure with metadata.

        Used when insufficient data or database error occurs.

        Args:
            days: Window size that was attempted
            reason: Human-readable explanation

        Returns:
            Dict with has_data=False and empty metrics
        """
        logger.info(f"Returning empty performance result: {reason}")
        return {
            'has_data': False,
            'overall': {
                'total_validations': 0,
                'overall_mae': None,
                'overall_rmse': None,
                'overall_categorical': None,
                'avg_bias': 0.0
            },
            'by_shore': {},
            'bias_alerts': [],
            'metadata': {
                'query_timestamp': datetime.now().isoformat(),
                'window_days': days,
                'reason': reason
            }
        }

    def build_performance_context(self, perf_data: Dict[str, Any]) -> str:
        """Generate human-readable performance context for prompt injection.

        Converts structured performance metrics into formatted text suitable
        for inclusion in GPT prompts. Returns empty string if insufficient data.

        Args:
            perf_data: Output from get_recent_performance()

        Returns:
            Formatted markdown string for prompt injection.
            Empty string if has_data=False.

        Example:
            >>> analyzer = PerformanceAnalyzer()
            >>> perf = analyzer.get_recent_performance()
            >>> context = analyzer.build_performance_context(perf)
            >>> print(context)
            ## Recent Forecast Performance
            Based on 28 validations over the last 7 days:
            - Overall MAE: 1.15ft
            - Overall RMSE: 1.48ft
            - Categorical accuracy: 78.6%

            ### Systematic Bias Detected:
            - North Shore: Recent forecasts trending high by 0.85ft (10 samples)

            ### Performance by Shore:
            - North Shore: MAE=1.42ft, Bias=+0.85ft, Samples=10
            - South Shore: MAE=0.98ft, Bias=-0.12ft, Samples=9
            ...
        """
        if not perf_data['has_data']:
            return ""

        overall = perf_data['overall']
        bias_alerts = perf_data['bias_alerts']
        days = perf_data['metadata']['window_days']

        context_lines = [
            "## Recent Forecast Performance",
            f"Based on {overall['total_validations']} validations over the last {days} days:",
            f"- Overall MAE: {overall['overall_mae']}ft",
            f"- Overall RMSE: {overall['overall_rmse']}ft",
            f"- Categorical accuracy: {overall['overall_categorical']*100:.1f}%"
        ]

        # Add bias alerts if present
        if bias_alerts:
            context_lines.append("\n### Systematic Bias Detected:")
            for alert in bias_alerts:
                direction = "high" if alert['avg_bias'] > 0 else "low"
                context_lines.append(
                    f"- {alert['shore']}: Recent forecasts trending {direction} by "
                    f"{abs(alert['avg_bias'])}ft ({alert['sample_size']} samples)"
                )

        # Add shore-specific performance
        by_shore = perf_data['by_shore']
        context_lines.append("\n### Performance by Shore:")
        for shore, metrics in by_shore.items():
            if metrics is None:
                context_lines.append(f"- {shore}: No recent validations")
            else:
                context_lines.append(
                    f"- {shore}: MAE={metrics['avg_mae']}ft, "
                    f"Bias={metrics['avg_height_error']:+.2f}ft, "
                    f"Samples={metrics['validation_count']}"
                )

        return "\n".join(context_lines)


# Convenience functions for direct imports
def get_recent_performance(
    db_path: str = "data/validation.db",
    days: int = 7
) -> Dict[str, Any]:
    """Quick accessor for recent performance metrics.

    Example:
        >>> from src.validation.performance import get_recent_performance
        >>> perf = get_recent_performance(days=14)
        >>> print(perf['overall']['overall_mae'])
        1.15
    """
    analyzer = PerformanceAnalyzer(db_path)
    return analyzer.get_recent_performance(days=days)


def build_performance_context(
    db_path: str = "data/validation.db",
    days: int = 7
) -> str:
    """Quick accessor for prompt injection context.

    Example:
        >>> from src.validation.performance import build_performance_context
        >>> context = build_performance_context(days=7)
        >>> if context:
        ...     print(f"Injecting performance context: {len(context)} chars")
    """
    analyzer = PerformanceAnalyzer(db_path)
    perf_data = analyzer.get_recent_performance(days=days)
    return analyzer.build_performance_context(perf_data)
