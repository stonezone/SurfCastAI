"""Unit tests for validation performance query module.

Tests the PerformanceAnalyzer class and related functions that extract
recent forecast performance metrics for adaptive prompt injection.
"""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.validation.performance import (
    PerformanceAnalyzer,
    build_performance_context,
    get_recent_performance,
)


class TestPerformanceAnalyzer(unittest.TestCase):
    """Test cases for PerformanceAnalyzer class."""

    def setUp(self):
        """Create temporary database with test data."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        # Initialize schema
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE forecasts (
                    id INTEGER PRIMARY KEY,
                    forecast_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP NOT NULL
                );

                CREATE TABLE predictions (
                    id INTEGER PRIMARY KEY,
                    forecast_id TEXT NOT NULL,
                    shore TEXT NOT NULL,
                    forecast_time TIMESTAMP NOT NULL,
                    valid_time TIMESTAMP NOT NULL,
                    predicted_height REAL
                );

                CREATE TABLE validations (
                    id INTEGER PRIMARY KEY,
                    forecast_id TEXT NOT NULL,
                    prediction_id INTEGER NOT NULL,
                    actual_id INTEGER NOT NULL,
                    validated_at TIMESTAMP NOT NULL,
                    height_error REAL,
                    period_error REAL,
                    category_match BOOLEAN,
                    mae REAL,
                    rmse REAL
                );

                -- Critical index for performance
                CREATE INDEX idx_validations_validated_at ON validations(validated_at);
            """
            )

        self.analyzer = PerformanceAnalyzer(self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        Path(self.db_path).unlink(missing_ok=True)

    def _insert_test_data(self, num_validations: int = 20, days_ago: int = 3):
        """Insert test validation data.

        Args:
            num_validations: Number of validation records to insert
            days_ago: How many days ago to timestamp the data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Insert forecast
            cursor.execute(
                """
                INSERT INTO forecasts (forecast_id, created_at)
                VALUES ('test-001', ?)
            """,
                (datetime.now().isoformat(),),
            )

            # Insert predictions and validations
            timestamp = datetime.now() - timedelta(days=days_ago)

            for i in range(num_validations):
                shore = ["North Shore", "South Shore", "West Shore", "East Shore"][i % 4]

                # Insert prediction
                cursor.execute(
                    """
                    INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                    VALUES ('test-001', ?, ?, ?, ?)
                """,
                    (shore, timestamp.isoformat(), timestamp.isoformat(), 5.0),
                )

                pred_id = cursor.lastrowid

                # Insert validation with varying error patterns
                # North Shore: overprediction bias (+1.5ft average)
                # South Shore: slight underprediction (-0.3ft average)
                # West Shore: balanced (0.0ft average)
                # East Shore: balanced (0.0ft average)
                if shore == "North Shore":
                    height_error = 1.5 + (i % 3 - 1) * 0.2  # Range: 1.3 to 1.7
                elif shore == "South Shore":
                    height_error = -0.3 + (i % 3 - 1) * 0.1  # Range: -0.4 to -0.2
                else:
                    height_error = (i % 3 - 1) * 0.2  # Range: -0.2 to 0.2

                mae = abs(height_error)
                rmse = mae * 1.2  # Simplified
                category_match = abs(height_error) < 1.0

                cursor.execute(
                    """
                    INSERT INTO validations (
                        forecast_id, prediction_id, actual_id, validated_at,
                        height_error, mae, rmse, category_match
                    ) VALUES ('test-001', ?, 1, ?, ?, ?, ?, ?)
                """,
                    (pred_id, timestamp.isoformat(), height_error, mae, rmse, category_match),
                )

            conn.commit()

    def test_empty_database(self):
        """Test behavior with empty database."""
        result = self.analyzer.get_recent_performance(days=7)

        self.assertFalse(result["has_data"])
        self.assertEqual(result["overall"]["total_validations"], 0)
        self.assertIsNone(result["overall"]["overall_mae"])
        self.assertEqual(result["by_shore"], {})
        self.assertEqual(result["bias_alerts"], [])
        self.assertIn("reason", result["metadata"])

    def test_insufficient_samples(self):
        """Test behavior with insufficient samples (<10)."""
        # Insert only 5 validations (below min_samples=10 threshold)
        self._insert_test_data(num_validations=5, days_ago=3)

        result = self.analyzer.get_recent_performance(days=7, min_samples=10)

        # Should expand window and still fail (no additional data)
        self.assertFalse(result["has_data"])
        self.assertEqual(result["metadata"]["window_days"], 30)  # Expanded to max

    def test_sufficient_samples(self):
        """Test successful query with sufficient samples."""
        # Insert 20 validations (above min_samples=10)
        self._insert_test_data(num_validations=20, days_ago=3)

        result = self.analyzer.get_recent_performance(days=7, min_samples=10)

        # Should return data
        self.assertTrue(result["has_data"])
        self.assertEqual(result["overall"]["total_validations"], 20)
        self.assertIsNotNone(result["overall"]["overall_mae"])
        self.assertIsNotNone(result["overall"]["overall_rmse"])
        self.assertIsNotNone(result["overall"]["avg_bias"])

    def test_shore_level_metrics(self):
        """Test shore-level performance breakdown."""
        self._insert_test_data(num_validations=20, days_ago=3)

        result = self.analyzer.get_recent_performance(days=7)

        # Check shore-specific metrics
        by_shore = result["by_shore"]
        self.assertIn("North Shore", by_shore)
        self.assertIn("South Shore", by_shore)
        self.assertIn("West Shore", by_shore)
        self.assertIn("East Shore", by_shore)

        # North Shore should have data (5 samples: indices 0,4,8,12,16)
        north = by_shore["North Shore"]
        self.assertIsNotNone(north)
        self.assertEqual(north["validation_count"], 5)
        self.assertIsNotNone(north["avg_mae"])
        self.assertIsNotNone(north["avg_height_error"])

    def test_bias_detection(self):
        """Test bias detection with significance filtering."""
        self._insert_test_data(num_validations=20, days_ago=3)

        result = self.analyzer.get_recent_performance(days=7)

        # North Shore has +1.5ft bias (should trigger OVERPREDICTING alert)
        bias_alerts = result["bias_alerts"]

        # Check if North Shore appears in alerts
        north_alert = next((a for a in bias_alerts if a["shore"] == "North Shore"), None)
        self.assertIsNotNone(north_alert, "North Shore should have bias alert")
        self.assertEqual(north_alert["bias_category"], "OVERPREDICTING")
        self.assertGreater(north_alert["avg_bias"], 1.0)

    def test_outlier_filtering(self):
        """Test outlier threshold filtering."""
        self._insert_test_data(num_validations=10, days_ago=3)

        # Insert extreme outlier (50ft error - likely data corruption)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                VALUES ('test-001', 'North Shore', ?, ?, ?)
            """,
                (datetime.now().isoformat(), datetime.now().isoformat(), 5.0),
            )
            pred_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO validations (
                    forecast_id, prediction_id, actual_id, validated_at,
                    height_error, mae, rmse, category_match
                ) VALUES ('test-001', ?, 1, ?, 50.0, 50.0, 50.0, 0)
            """,
                (pred_id, datetime.now().isoformat()),
            )
            conn.commit()

        # Query with default outlier threshold (10.0ft)
        result = self.analyzer.get_recent_performance(days=7, outlier_threshold=10.0)

        # Outlier should be excluded
        self.assertEqual(result["overall"]["total_validations"], 10)  # Not 11

        # Query with high threshold (should include outlier)
        result_with_outlier = self.analyzer.get_recent_performance(days=7, outlier_threshold=100.0)
        self.assertEqual(result_with_outlier["overall"]["total_validations"], 11)

    def test_time_window_filtering(self):
        """Test time window correctly filters old data."""
        # Insert recent data (3 days ago)
        self._insert_test_data(num_validations=10, days_ago=3)

        # Insert old data (15 days ago - within 30-day window but outside 7-day)
        timestamp_old = datetime.now() - timedelta(days=15)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions (forecast_id, shore, forecast_time, valid_time, predicted_height)
                VALUES ('test-001', 'North Shore', ?, ?, ?)
            """,
                (timestamp_old.isoformat(), timestamp_old.isoformat(), 5.0),
            )
            pred_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO validations (
                    forecast_id, prediction_id, actual_id, validated_at,
                    height_error, mae, rmse, category_match
                ) VALUES ('test-001', ?, 1, ?, 2.0, 2.0, 2.0, 1)
            """,
                (pred_id, timestamp_old.isoformat()),
            )
            conn.commit()

        # Query 7-day window (should only get 10 recent validations, not the 15-day-old one)
        result = self.analyzer.get_recent_performance(days=7)
        self.assertEqual(result["overall"]["total_validations"], 10)

        # Query 30-day window (should get all 11 validations including 15-day-old one)
        result_long = self.analyzer.get_recent_performance(days=30)
        self.assertEqual(result_long["overall"]["total_validations"], 11)

    def test_build_performance_context(self):
        """Test human-readable context generation."""
        self._insert_test_data(num_validations=20, days_ago=3)

        result = self.analyzer.get_recent_performance(days=7)
        context = self.analyzer.build_performance_context(result)

        # Should generate non-empty context
        self.assertIsInstance(context, str)
        self.assertGreater(len(context), 0)

        # Should contain key sections
        self.assertIn("Recent Forecast Performance", context)
        self.assertIn("Overall MAE:", context)
        self.assertIn("North Shore:", context)
        self.assertIn("South Shore:", context)

    def test_build_performance_context_empty(self):
        """Test context generation with no data."""
        result = self.analyzer.get_recent_performance(days=7)
        context = self.analyzer.build_performance_context(result)

        # Should return empty string for no data
        self.assertEqual(context, "")

    def test_convenience_functions(self):
        """Test module-level convenience functions."""
        self._insert_test_data(num_validations=20, days_ago=3)

        # Test get_recent_performance()
        result = get_recent_performance(db_path=self.db_path, days=7)
        self.assertTrue(result["has_data"])
        self.assertEqual(result["overall"]["total_validations"], 20)

        # Test build_performance_context()
        context = build_performance_context(db_path=self.db_path, days=7)
        self.assertGreater(len(context), 0)
        self.assertIn("Recent Forecast Performance", context)


class TestDatabaseMissing(unittest.TestCase):
    """Test behavior when database doesn't exist."""

    def test_missing_database(self):
        """Test graceful handling of missing database."""
        analyzer = PerformanceAnalyzer("/nonexistent/path/to/db.db")
        result = analyzer.get_recent_performance()

        self.assertFalse(result["has_data"])
        self.assertIn("Database not found", result["metadata"]["reason"])


if __name__ == "__main__":
    unittest.main()
