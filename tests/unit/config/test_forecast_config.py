"""Config template coverage tests for multimodal forecast settings."""

import unittest
from pathlib import Path

import yaml


class TestForecastConfigTemplates(unittest.TestCase):
    REQUIRED_DETAIL_KEYS = {"pressure_charts", "wave_models", "satellite", "sst_charts"}

    def _load_config(self, path: Path) -> dict:
        with path.open() as handle:
            return yaml.safe_load(handle)

    def test_templates_define_multimodal_settings(self) -> None:
        for filename in ("config/config.example.yaml", "config/config.yaml"):
            path = Path(filename)
            self.assertTrue(path.exists(), f"Missing config file: {filename}")
            data = self._load_config(path)

            self.assertIn("forecast", data, f"forecast section missing in {filename}")
            forecast = data["forecast"]

            self.assertIn("max_images", forecast, f"forecast.max_images missing in {filename}")
            self.assertIn(
                "image_detail_levels",
                forecast,
                f"forecast.image_detail_levels missing in {filename}",
            )

            detail = forecast["image_detail_levels"]
            self.assertIsInstance(
                detail, dict, f"forecast.image_detail_levels must be dict in {filename}"
            )
            for key in self.REQUIRED_DETAIL_KEYS:
                self.assertIn(key, detail, f"Missing image detail key '{key}' in {filename}")


if __name__ == "__main__":
    unittest.main()
