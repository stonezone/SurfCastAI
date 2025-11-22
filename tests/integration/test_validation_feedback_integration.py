"""
Integration tests for validation feedback with realistic scenarios.

Tests the complete workflow from database queries to prompt generation
with realistic validation data patterns.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from src.utils.validation_feedback import ValidationFeedback


@pytest.fixture
def realistic_db():
    """Create database with realistic multi-day validation data."""
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

    now = datetime.now()

    # Create realistic validation data over 7 days
    # Pattern: North Shore accurate, South Shore overpredicting
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for day_offset in range(7):
            day = now - timedelta(days=day_offset)
            forecast_id = f'forecast-{day.strftime("%Y%m%d")}'

            cursor.execute(
                "INSERT INTO forecasts (forecast_id, created_at) VALUES (?, ?)",
                (forecast_id, day.timestamp())
            )

            # North Shore: accurate predictions (MAE ~1.2 ft, slight underprediction)
            for hour in [6, 12, 18]:
                pred_time = day.replace(hour=hour)
                predicted = 5.0 + (hour - 12) * 0.1  # Varies by time
                actual = predicted + 0.3  # Slight underprediction

                cursor.execute(
                    """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                       VALUES (?, ?, ?, ?, ?)""",
                    (forecast_id, 'North Shore', pred_time.timestamp(), pred_time.timestamp(), predicted)
                )
                pred_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
                    ('51201', pred_time.timestamp(), actual)
                )
                actual_id = cursor.lastrowid

                error = abs(predicted - actual)
                cursor.execute(
                    """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                               height_error, mae, rmse, category_match)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (forecast_id, pred_id, actual_id, pred_time.timestamp(),
                     predicted - actual, error, error, True)
                )

            # South Shore: overpredicting (MAE ~1.8 ft, +0.8 ft bias)
            for hour in [6, 12, 18]:
                pred_time = day.replace(hour=hour)
                predicted = 3.5 + (hour - 12) * 0.1
                actual = predicted - 0.8  # Significant overprediction

                cursor.execute(
                    """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                       VALUES (?, ?, ?, ?, ?)""",
                    (forecast_id, 'South Shore', pred_time.timestamp(), pred_time.timestamp(), predicted)
                )
                pred_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
                    ('51202', pred_time.timestamp(), actual)
                )
                actual_id = cursor.lastrowid

                error = abs(predicted - actual)
                cursor.execute(
                    """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                               height_error, mae, rmse, category_match)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (forecast_id, pred_id, actual_id, pred_time.timestamp(),
                     predicted - actual, error, error, False)  # Category mismatch
                )

            # West Shore: minimal data (only 1 validation per day)
            pred_time = day.replace(hour=12)
            predicted = 2.5
            actual = 2.6

            cursor.execute(
                """INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                   VALUES (?, ?, ?, ?, ?)""",
                (forecast_id, 'West Shore', pred_time.timestamp(), pred_time.timestamp(), predicted)
            )
            pred_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO actuals (buoy_id, observation_time, wave_height) VALUES (?, ?, ?)",
                ('51203', pred_time.timestamp(), actual)
            )
            actual_id = cursor.lastrowid

            error = abs(predicted - actual)
            cursor.execute(
                """INSERT INTO validations (forecast_id, prediction_id, actual_id, validated_at,
                                           height_error, mae, rmse, category_match)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (forecast_id, pred_id, actual_id, pred_time.timestamp(),
                 predicted - actual, error, error, True)
            )

        conn.commit()

    yield db_path

    # Cleanup
    db_path.unlink()


class TestRealisticValidationFeedback:
    """Integration tests with realistic validation scenarios."""

    def test_realistic_performance_report(self, realistic_db):
        """Test performance report with realistic multi-day data."""
        feedback = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report = feedback.get_recent_performance()

        # Should have data
        assert report.has_recent_data is True

        # Should have 3 shores
        assert len(report.shore_performance) == 3
        shore_names = {sp.shore for sp in report.shore_performance}
        assert 'North Shore' in shore_names
        assert 'South Shore' in shore_names
        assert 'West Shore' in shore_names

        # Total validations: 7 days * (3 North + 3 South + 1 West) = 49
        total_validations = sum(sp.validation_count for sp in report.shore_performance)
        assert total_validations == 49

        # Check North Shore performance (accurate, slight underprediction)
        north = next(sp for sp in report.shore_performance if sp.shore == 'North Shore')
        assert north.validation_count == 21  # 7 days * 3 per day
        assert north.avg_mae < 0.5  # Should be very accurate
        assert north.avg_bias < 0  # Underprediction (predicted < actual)
        assert north.categorical_accuracy == 1.0  # All categories matched

        # Check South Shore performance (overpredicting)
        south = next(sp for sp in report.shore_performance if sp.shore == 'South Shore')
        assert south.validation_count == 21
        assert south.avg_mae > 0.5  # Less accurate
        assert south.avg_bias > 0.5  # Significant overprediction
        assert south.categorical_accuracy == 0.0  # No categories matched

        # Check West Shore performance (minimal data, accurate)
        west = next(sp for sp in report.shore_performance if sp.shore == 'West Shore')
        assert west.validation_count == 7  # Only 1 per day
        assert west.avg_mae < 0.2  # Accurate

    def test_realistic_prompt_context(self, realistic_db):
        """Test prompt context generation with realistic data."""
        feedback = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report = feedback.get_recent_performance()
        context = feedback.generate_prompt_context(report)

        # Should contain key sections
        assert "RECENT FORECAST PERFORMANCE" in context
        assert "49 validations" in context  # Total count
        assert "Per-Shore Performance" in context
        assert "ADAPTIVE GUIDANCE" in context

        # Should mention all shores
        assert "North Shore" in context
        assert "South Shore" in context
        assert "West Shore" in context

        # Should identify South Shore bias
        assert "South Shore" in context
        assert ("overpredicting" in context.lower() or "overprediction" in context.lower())
        assert "running high" in context

        # Should provide specific guidance
        assert "conservative" in context.lower()

    def test_adaptive_guidance_generation(self, realistic_db):
        """Test that adaptive guidance is actionable and specific."""
        feedback = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report = feedback.get_recent_performance()
        guidance = feedback._generate_guidance(report)

        # Should have multiple guidance items
        assert len(guidance) >= 2

        # Should mention South Shore overprediction
        south_guidance = [g for g in guidance if 'South Shore' in g and 'running high' in g]
        assert len(south_guidance) >= 1
        assert any('conservative' in g.lower() for g in south_guidance)

        # Should mention North Shore accuracy (MAE < 1.5, bias < 0.3 triggers "good performance")
        north_guidance = [g for g in guidance if 'North Shore' in g]
        assert len(north_guidance) >= 1
        # Check that it mentions accuracy or maintaining approach
        assert any('accurate' in g.lower() or 'maintain' in g.lower() for g in north_guidance)

    def test_different_lookback_windows(self, realistic_db):
        """Test that different lookback windows work correctly."""
        # 3-day lookback
        feedback_3day = ValidationFeedback(db_path=str(realistic_db), lookback_days=3)
        report_3day = feedback_3day.get_recent_performance()

        assert report_3day.has_recent_data is True
        assert report_3day.lookback_days == 3
        total_3day = sum(sp.validation_count for sp in report_3day.shore_performance)
        assert total_3day == 21  # 3 days * 7 validations per day

        # 7-day lookback
        feedback_7day = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report_7day = feedback_7day.get_recent_performance()

        assert report_7day.has_recent_data is True
        assert report_7day.lookback_days == 7
        total_7day = sum(sp.validation_count for sp in report_7day.shore_performance)
        assert total_7day == 49  # 7 days * 7 validations per day

        # 14-day lookback (should still work, just returns 7 days worth)
        feedback_14day = ValidationFeedback(db_path=str(realistic_db), lookback_days=14)
        report_14day = feedback_14day.get_recent_performance()

        assert report_14day.has_recent_data is True
        total_14day = sum(sp.validation_count for sp in report_14day.shore_performance)
        assert total_14day == 49  # Only 7 days of data available

    def test_bias_detection_accuracy(self, realistic_db):
        """Test that bias detection correctly identifies patterns."""
        feedback = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report = feedback.get_recent_performance()

        # North Shore: underprediction (negative bias)
        north = next(sp for sp in report.shore_performance if sp.shore == 'North Shore')
        assert north.avg_bias < 0
        north_desc = feedback._describe_bias(north.avg_bias)
        assert "underprediction" in north_desc.lower()

        # South Shore: overprediction (positive bias)
        south = next(sp for sp in report.shore_performance if sp.shore == 'South Shore')
        assert south.avg_bias > 0.5
        south_desc = feedback._describe_bias(south.avg_bias)
        assert "overpredicting" in south_desc.lower()

        # West Shore: minimal bias (well-calibrated)
        west = next(sp for sp in report.shore_performance if sp.shore == 'West Shore')
        assert abs(west.avg_bias) < 0.2
        west_desc = feedback._describe_bias(west.avg_bias)
        assert "well-calibrated" in west_desc.lower()

    def test_categorical_accuracy_tracking(self, realistic_db):
        """Test that categorical accuracy is tracked correctly."""
        feedback = ValidationFeedback(db_path=str(realistic_db), lookback_days=7)
        report = feedback.get_recent_performance()

        # North Shore: perfect categorical accuracy
        north = next(sp for sp in report.shore_performance if sp.shore == 'North Shore')
        assert north.categorical_accuracy == 1.0

        # South Shore: zero categorical accuracy
        south = next(sp for sp in report.shore_performance if sp.shore == 'South Shore')
        assert south.categorical_accuracy == 0.0

        # Overall: should be weighted average
        # (21 * 1.0 + 21 * 0.0 + 7 * 1.0) / 49 = 28/49 ≈ 0.57
        assert 0.5 <= report.overall_categorical <= 0.6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
