"""
Unit tests for the ForecastFormatter class.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from src.core import Config
from src.forecast_engine import ForecastFormatter


class TestForecastFormatter(unittest.TestCase):
    """Test cases for ForecastFormatter."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        # Create config
        self.config = Config()
        self.config._config = {
            "general": {"output_directory": self.test_dir},
            "forecast": {"formats": "markdown,html"},
        }

        # Create formatter
        self.formatter = ForecastFormatter(self.config)

        # Test forecast data
        self.forecast_data = {
            "forecast_id": "test_forecast",
            "generated_time": "2023-01-01T00:00:00Z",
            "main_forecast": "This is a test forecast for Hawaii.",
            "north_shore": "North Shore forecast: Waves are 5-7 feet.",
            "south_shore": "South Shore forecast: Waves are 1-3 feet.",
            "daily": "Daily forecast: Good surfing conditions.",
            "metadata": {
                "confidence": {
                    "overall_score": 0.8,
                    "factors": {"data_freshness": 0.9, "source_diversity": 0.7},
                }
            },
        }

    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)

    def test_format_forecast(self):
        """Test format_forecast method."""
        # Format forecast
        result = self.formatter.format_forecast(self.forecast_data)

        # Check if output files exist
        self.assertIn("markdown", result)
        self.assertIn("html", result)
        self.assertIn("json", result)

        # Check if files were created
        markdown_path = Path(result["markdown"])
        html_path = Path(result["html"])
        json_path = Path(result["json"])

        self.assertTrue(markdown_path.exists())
        self.assertTrue(html_path.exists())
        self.assertTrue(json_path.exists())

        # Check file content
        with open(markdown_path) as f:
            markdown_content = f.read()
            self.assertIn("Hawaii Surf Forecast", markdown_content)
            self.assertIn("North Shore", markdown_content)
            self.assertIn("South Shore", markdown_content)

        with open(html_path) as f:
            html_content = f.read()
            self.assertIn("<html", html_content)
            self.assertIn("Hawaii Surf Forecast", html_content)
            self.assertIn("North Shore", html_content)
            self.assertIn("South Shore", html_content)

        with open(json_path) as f:
            import json

            json_content = json.load(f)
            self.assertEqual(json_content["forecast_id"], "test_forecast")
            self.assertIn("main_forecast", json_content)
            self.assertIn("north_shore", json_content)
            self.assertIn("south_shore", json_content)
