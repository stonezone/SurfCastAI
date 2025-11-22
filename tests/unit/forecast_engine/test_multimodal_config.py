"""Tests for ForecastEngine multimodal image configuration."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core import Config
from src.forecast_engine import ForecastEngine


def _build_config(temp_root: Path) -> Config:
    config = Config()
    config._config = {
        "general": {
            "output_directory": str(temp_root / "output"),
            "data_directory": str(temp_root / "data"),
        },
        "forecast": {
            "templates_dir": str(temp_root / "prompts"),
            "use_local_generator": True,
            "formats": "markdown",
            "max_images": 3,
            "image_detail_levels": {
                "pressure_charts": "low",
                "wave_models": "high",
                "satellite": "auto",
                "sst_charts": "low",
            },
        },
        "openai": {
            "model": "gpt-5-nano",
        },
    }
    return config


class TestForecastEngineMultimodalConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_image_selection_respects_configured_limits(self) -> None:
        config = _build_config(self.root)
        engine = ForecastEngine(config)

        images = {
            "pressure_charts": [f"pressure_{i}.png" for i in range(5)],
            "wave_models": [f"wave_{i}.png" for i in range(5)],
            "satellite": ["satellite.png"],
            "sst_charts": ["sst.png"],
        }

        selected = engine.data_manager.select_critical_images(images)

        self.assertLessEqual(len(selected), 3)
        detail_by_type = {item["type"]: item["detail"] for item in selected}
        if "pressure_chart" in detail_by_type:
            self.assertEqual(detail_by_type["pressure_chart"], "low")
        if "wave_model" in detail_by_type:
            self.assertEqual(detail_by_type["wave_model"], "high")
        if "satellite" in detail_by_type:
            self.assertEqual(detail_by_type["satellite"], "auto")


if __name__ == "__main__":
    unittest.main()
