"""
Unit tests for validation feedback system.

Tests performance report generation, database queries, and adaptive guidance.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from src.utils.validation_feedback import (
    ValidationFeedback,
    PerformanceReport,
    ShorePerformance
)


@pytest.fixture
def temp_db():
    """Create temporary database with schema."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
    temp_file.close()
    db_path = Path(temp_file.name)

    # Initialize with schema
    schema = """
    CREATE TABLE forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_id TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_id TEXT NOT NULL,
        shore TEXT NOT NULL,
        forecast_time TIMESTAMP NOT NULL,
        valid_time TIMESTAMP NOT NULL,
        predicted_height REAL,
        FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
    );

    CREATE TABLE actuals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buoy_id TEXT NOT NULL,
        observation_time TIMESTAMP NOT NULL,
        wave_height REAL
    );

    CREATE TABLE validations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        forecast_id TEXT NOT NULL,
        prediction_id INTEGER NOT NULL,
        actual_id INTEGER NOT NULL,
        validated_at TIMESTAMP NOT NULL,
        height_error REAL,
        mae REAL,
        rmse REAL,
        category_match BOOLEAN,
        FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id),
        FOREIGN KEY (prediction_id) REFERENCES predictions(id),
        FOREIGN KEY (actual_id) REFERENCES actuals(id)
    );
    """

    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)

    yield db_path

    # Cleanup
    db_path.unlink()


@pytest.fixture
def populated_db(temp_db):
    """Database with sample validation data."""
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()

        # Insert forecast
        cursor.execute(
            "INSERT INTO forecasts (forecast_id, created_at) VALUES (?, ?)",
            ('test-forecast-1', week_ago.timestamp())
        )

        # Insert predictions for North Shore and South Shore
        cursor.execute(
            """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
               VALUES (?, ?, ?, ?, ?)""",
            ('test-forecast-1', 'North Shore', week_ago.timestamp(), yesterday.timestamp(), 5.0)
        )
        north_pred_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
               VALUES (?, ?, ?, ?, ?)""",
            ('test-forecast-1', 'South Shore', week_ago.timestamp(), yesterday.timestamp(), 3.0)
        )
        south_pred_id = cursor.lastrowid

        # Insert actuals
        cursor.execute(
            "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
            ('51201', yesterday.timestamp(), 4.7)  # North actual
        )
        north_actual_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
            ('51202', yesterday.timestamp(), 2.0)  # South actual
        )
        south_actual_id = cursor.lastrowid

        # Insert validations
        # North Shore: predicted 5.0, actual 4.7, error = +0.3 (overprediction)
        cursor.execute(
            """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                       height_error, mae, rmse, category_match)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('test-forecast-1', north_pred_id, north_actual_id, now.timestamp(),
             0.3, 0.3, 0.3, True)
        )

        # South Shore: predicted 3.0, actual 2.0, error = +1.0 (overprediction)
        cursor.execute(
            """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                       height_error, mae, rmse, category_match)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ('test-forecast-1', south_pred_id, south_actual_id, now.timestamp(),
             1.0, 1.0, 1.0, False)
        )

        conn.commit()

    return temp_db


class TestShorePerformance:
    """Tests for ShorePerformance Pydantic model."""

    def test_valid_shore_performance(self):
        """Test valid shore performance creation."""
        perf = ShorePerformance(
            shore='North Shore',
            validation_count=10,
            avg_mae=1.5,
            avg_rmse=2.0,
            avg_bias=-0.3,
            categorical_accuracy=0.85
        )

        assert perf.shore == 'North Shore'
        assert perf.validation_count == 10
        assert perf.avg_mae == 1.5
        assert perf.avg_rmse == 2.0
        assert perf.avg_bias == -0.3
        assert perf.categorical_accuracy == 0.85

    def test_rounding_validation(self):
        """Test that metrics are rounded to appropriate precision."""
        perf = ShorePerformance(
            shore='South Shore',
            validation_count=5,
            avg_mae=1.234567,
            avg_rmse=2.345678,
            avg_bias=0.456789,
            categorical_accuracy=0.857142
        )

        assert perf.avg_mae == 1.2  # Rounded to 1 decimal
        assert perf.avg_rmse == 2.3  # Rounded to 1 decimal
        assert perf.avg_bias == 0.5  # Rounded to 1 decimal
        assert perf.categorical_accuracy == 0.86  # Rounded to 2 decimals

    def test_negative_validation_count_rejected(self):
        """Test that negative validation counts are rejected."""
        with pytest.raises(ValueError, match="validation_count"):
            ShorePerformance(
                shore='North Shore',
                validation_count=-1,
                avg_mae=1.0,
                avg_rmse=1.0,
                avg_bias=0.0,
                categorical_accuracy=0.5
            )

    def test_negative_mae_rejected(self):
        """Test that negative MAE is rejected."""
        with pytest.raises(ValueError, match="avg_mae"):
            ShorePerformance(
                shore='North Shore',
                validation_count=10,
                avg_mae=-1.0,
                avg_rmse=1.0,
                avg_bias=0.0,
                categorical_accuracy=0.5
            )

    def test_categorical_accuracy_out_of_range(self):
        """Test that categorical accuracy must be in [0, 1]."""
        with pytest.raises(ValueError, match="categorical_accuracy"):
            ShorePerformance(
                shore='North Shore',
                validation_count=10,
                avg_mae=1.0,
                avg_rmse=1.0,
                avg_bias=0.0,
                categorical_accuracy=1.5
            )


class TestPerformanceReport:
    """Tests for PerformanceReport Pydantic model."""

    def test_valid_report(self):
        """Test valid performance report creation."""
        shore_perf = ShorePerformance(
            shore='North Shore',
            validation_count=10,
            avg_mae=1.5,
            avg_rmse=2.0,
            avg_bias=-0.3,
            categorical_accuracy=0.85
        )

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=1.8,
            overall_rmse=2.3,
            overall_categorical=0.80,
            shore_performance=[shore_perf],
            has_recent_data=True
        )

        assert report.report_date == '2025-10-10T12:00:00'
        assert report.lookback_days == 7
        assert report.overall_mae == 1.8
        assert report.has_recent_data is True
        assert len(report.shore_performance) == 1

    def test_invalid_date_format(self):
        """Test that invalid date format is rejected."""
        with pytest.raises(ValueError, match="ISO format"):
            PerformanceReport(
                report_date='10/10/2025',  # Not ISO format
                lookback_days=7,
                overall_mae=1.8,
                overall_rmse=2.3,
                overall_categorical=0.80,
                shore_performance=[],
                has_recent_data=True
            )

    def test_empty_shore_performance(self):
        """Test report with no shore performance data."""
        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=0.0,
            overall_rmse=0.0,
            overall_categorical=0.0,
            shore_performance=[],
            has_recent_data=False
        )

        assert report.has_recent_data is False
        assert len(report.shore_performance) == 0


class TestValidationFeedback:
    """Tests for ValidationFeedback class."""

    def test_init_with_nonexistent_database(self):
        """Test initialization with nonexistent database."""
        feedback = ValidationFeedback(db_path='nonexistent.db', lookback_days=7)
        assert feedback.lookback_days == 7
        assert not feedback.db_path.exists()

    def test_empty_report_when_no_database(self):
        """Test that empty report is returned when database doesn't exist."""
        feedback = ValidationFeedback(db_path='nonexistent.db', lookback_days=7)
        report = feedback.get_recent_performance()

        assert report.has_recent_data is False
        assert report.overall_mae == 0.0
        assert len(report.shore_performance) == 0

    def test_empty_report_when_no_data(self, temp_db):
        """Test that empty report is returned when no validation data exists."""
        feedback = ValidationFeedback(db_path=str(temp_db), lookback_days=7)
        report = feedback.get_recent_performance()

        assert report.has_recent_data is False
        assert report.overall_mae == 0.0
        assert len(report.shore_performance) == 0

    def test_performance_report_with_data(self, populated_db):
        """Test performance report generation with sample data."""
        feedback = ValidationFeedback(db_path=str(populated_db), lookback_days=7)
        report = feedback.get_recent_performance()

        assert report.has_recent_data is True
        assert report.overall_mae > 0.0
        assert len(report.shore_performance) == 2  # North and South Shore

        # Check shore-specific data
        shore_names = {sp.shore for sp in report.shore_performance}
        assert 'North Shore' in shore_names
        assert 'South Shore' in shore_names

        # North Shore: error = 0.3 (slight overprediction)
        north = next(sp for sp in report.shore_performance if sp.shore == 'North Shore')
        assert north.avg_mae == 0.3
        assert north.avg_bias == 0.3

        # South Shore: error = 1.0 (significant overprediction)
        south = next(sp for sp in report.shore_performance if sp.shore == 'South Shore')
        assert south.avg_mae == 1.0
        assert south.avg_bias == 1.0

    def test_generate_prompt_context_with_no_data(self, temp_db):
        """Test that empty string is returned when no data exists."""
        feedback = ValidationFeedback(db_path=str(temp_db), lookback_days=7)
        report = feedback.get_recent_performance()
        context = feedback.generate_prompt_context(report)

        assert context == ""

    def test_generate_prompt_context_with_data(self, populated_db):
        """Test prompt context generation with sample data."""
        feedback = ValidationFeedback(db_path=str(populated_db), lookback_days=7)
        report = feedback.get_recent_performance()
        context = feedback.generate_prompt_context(report)

        # Check that context contains expected sections
        assert "RECENT FORECAST PERFORMANCE" in context
        assert "Last 7 days" in context
        assert "Overall MAE" in context
        assert "Per-Shore Performance" in context
        assert "North Shore" in context
        assert "South Shore" in context
        assert "ADAPTIVE GUIDANCE" in context

        # Check for bias warnings
        assert "overpredicting" in context.lower() or "overprediction" in context.lower()

    def test_describe_bias_minimal(self):
        """Test bias description for minimal bias."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)
        desc = feedback._describe_bias(0.1)

        assert "well-calibrated" in desc
        assert "minimal bias" in desc

    def test_describe_bias_slight_overprediction(self):
        """Test bias description for slight overprediction."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)
        desc = feedback._describe_bias(0.3)

        assert "slight overprediction" in desc
        assert "+0.3" in desc

    def test_describe_bias_slight_underprediction(self):
        """Test bias description for slight underprediction."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)
        desc = feedback._describe_bias(-0.4)

        assert "slight underprediction" in desc
        assert "-0.4" in desc

    def test_describe_bias_significant_overprediction(self):
        """Test bias description for significant overprediction."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)
        desc = feedback._describe_bias(0.8)

        assert "overpredicting" in desc
        assert "+0.8" in desc

    def test_describe_bias_significant_underprediction(self):
        """Test bias description for significant underprediction."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)
        desc = feedback._describe_bias(-0.9)

        assert "underpredicting" in desc
        assert "-0.9" in desc

    def test_generate_guidance_poor_overall_performance(self):
        """Test guidance generation for poor overall performance."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=3.0,  # Poor performance
            overall_rmse=3.5,
            overall_categorical=0.60,
            shore_performance=[],
            has_recent_data=True
        )

        guidance = feedback._generate_guidance(report)
        assert len(guidance) > 0
        assert any("below target" in g.lower() for g in guidance)

    def test_generate_guidance_overprediction(self):
        """Test guidance generation for overprediction bias."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)

        shore_perf = ShorePerformance(
            shore='South Shore',
            validation_count=10,
            avg_mae=2.0,
            avg_rmse=2.5,
            avg_bias=0.8,  # Significant overprediction
            categorical_accuracy=0.70
        )

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=2.0,
            overall_rmse=2.5,
            overall_categorical=0.70,
            shore_performance=[shore_perf],
            has_recent_data=True
        )

        guidance = feedback._generate_guidance(report)
        assert len(guidance) > 0
        assert any("running high" in g for g in guidance)
        assert any("conservative" in g.lower() for g in guidance)

    def test_generate_guidance_underprediction(self):
        """Test guidance generation for underprediction bias."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)

        shore_perf = ShorePerformance(
            shore='North Shore',
            validation_count=10,
            avg_mae=1.8,
            avg_rmse=2.2,
            avg_bias=-0.7,  # Significant underprediction
            categorical_accuracy=0.75
        )

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=1.8,
            overall_rmse=2.2,
            overall_categorical=0.75,
            shore_performance=[shore_perf],
            has_recent_data=True
        )

        guidance = feedback._generate_guidance(report)
        assert len(guidance) > 0
        assert any("running low" in g for g in guidance)
        assert any("upward" in g.lower() for g in guidance)

    def test_generate_guidance_good_performance(self):
        """Test guidance generation for good performance."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)

        shore_perf = ShorePerformance(
            shore='North Shore',
            validation_count=10,
            avg_mae=1.2,  # Good performance
            avg_rmse=1.5,
            avg_bias=0.1,  # Minimal bias
            categorical_accuracy=0.90
        )

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=1.2,
            overall_rmse=1.5,
            overall_categorical=0.90,
            shore_performance=[shore_perf],
            has_recent_data=True
        )

        guidance = feedback._generate_guidance(report)
        assert len(guidance) > 0
        assert any("accurate" in g.lower() or "maintain" in g.lower() for g in guidance)

    def test_generate_guidance_poor_categorical(self):
        """Test guidance generation for poor categorical accuracy."""
        feedback = ValidationFeedback(db_path='dummy.db', lookback_days=7)

        report = PerformanceReport(
            report_date='2025-10-10T12:00:00',
            lookback_days=7,
            overall_mae=1.5,
            overall_rmse=2.0,
            overall_categorical=0.60,  # Poor categorical accuracy
            shore_performance=[],
            has_recent_data=True
        )

        guidance = feedback._generate_guidance(report)
        assert len(guidance) > 0
        assert any("categorical" in g.lower() for g in guidance)

    def test_custom_lookback_days(self, populated_db):
        """Test using custom lookback days."""
        feedback = ValidationFeedback(db_path=str(populated_db), lookback_days=3)
        report = feedback.get_recent_performance()

        assert report.lookback_days == 3
        # Should still find data since it was inserted recently
        assert report.has_recent_data is True

    def test_old_data_excluded(self, temp_db):
        """Test that old data outside lookback window is excluded."""
        # Insert old validation data (30 days ago)
        old_date = datetime.now() - timedelta(days=30)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO forecasts (forecast_id, created_at) VALUES (?, ?)",
                ('old-forecast', old_date.timestamp())
            )

            cursor.execute(
                """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                   VALUES (?, ?, ?, ?, ?)""",
                ('old-forecast', 'North Shore', old_date.timestamp(), old_date.timestamp(), 5.0)
            )
            pred_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
                ('51201', old_date.timestamp(), 4.5)
            )
            actual_id = cursor.lastrowid

            cursor.execute(
                """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                           height_error, mae, rmse, category_match)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ('old-forecast', pred_id, actual_id, old_date.timestamp(), 0.5, 0.5, 0.5, True)
            )

            conn.commit()

        # Query with 7-day lookback should find no data
        feedback = ValidationFeedback(db_path=str(temp_db), lookback_days=7)
        report = feedback.get_recent_performance()

        assert report.has_recent_data is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
