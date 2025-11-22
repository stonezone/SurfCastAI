"""Tests for visualization and historical comparison helpers."""

import json
import tempfile
import unittest
from pathlib import Path

from src.forecast_engine.historical import HistoricalComparator
from src.forecast_engine.visualization import ForecastVisualizer

SAMPLE_FORECAST = {
    "forecast_id": "unit_test_forecast",
    "generated_time": "2025-09-30T12:00:00Z",
    "swell_events": [
        {
            "event_id": "event_1",
            "primary_direction_cardinal": "NW",
            "dominant_period": 15.0,
            "hawaii_scale": 10.0,
        },
        {
            "event_id": "event_2",
            "primary_direction_cardinal": "S",
            "dominant_period": 14.0,
            "hawaii_scale": 4.0,
        },
    ],
    "shore_data": {
        "north_shore": {
            "name": "North Shore",
            "swell_events": [
                {
                    "event_id": "event_1",
                    "hawaii_scale": 10.0,
                }
            ],
        },
        "south_shore": {
            "name": "South Shore",
            "swell_events": [
                {
                    "event_id": "event_2",
                    "hawaii_scale": 4.0,
                }
            ],
        },
    },
    "metadata": {
        "confidence": {"overall_score": 0.75},
    },
}


class TestForecastVisualization(unittest.TestCase):
    """Validate that charts and historical summaries are produced."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_generate_visualizations_creates_pngs(self) -> None:
        visualizer = ForecastVisualizer()
        if not visualizer.available:  # pragma: no cover - depends on optional dependency
            self.skipTest("matplotlib not installed")

        assets = visualizer.generate_all(SAMPLE_FORECAST, self.output_dir)
        self.assertIn("swell_mix", assets)
        self.assertIn("shore_focus", assets)
        for path_str in assets.values():
            self.assertTrue(Path(path_str).exists(), "Chart file should exist on disk")

    def test_historical_comparator_detects_changes(self) -> None:
        comparator = HistoricalComparator(self.output_dir)

        previous_dir = self.output_dir / "previous"
        previous_dir.mkdir()
        previous_payload = dict(SAMPLE_FORECAST)
        previous_payload["swell_events"] = [
            {
                "event_id": "event_1",
                "primary_direction_cardinal": "NW",
                "dominant_period": 13.0,
                "hawaii_scale": 8.0,
            }
        ]
        previous_payload.setdefault("metadata", {}).setdefault("confidence", {}).update(
            {"overall_score": 0.65}
        )
        (previous_dir / "forecast_data.json").write_text(json.dumps(previous_payload))

        current_dir = self.output_dir / SAMPLE_FORECAST["forecast_id"]
        current_dir.mkdir()

        summary = comparator.build_summary(
            SAMPLE_FORECAST["forecast_id"], current_dir, SAMPLE_FORECAST
        )
        self.assertIsNotNone(summary)
        assert summary  # for mypy/static type hints
        self.assertIn("confidence_change", summary)
        self.assertIn("hawaiian_avg_change", summary)
        self.assertTrue(summary.get("summary_lines"))
