"""Smoke tests for ForecastEngine attribute initialization."""

import unittest

from src.core import Config
from src.forecast_engine import ForecastEngine


class TestForecastEngineAttributes(unittest.TestCase):
    """Verify specialist-related attributes exist when disabled."""

    def test_specialist_attributes_present_when_disabled(self) -> None:
        config = Config()
        config._config = {
            "forecast": {
                "use_specialist_team": False,
            },
            "openai": {},
        }

        engine = ForecastEngine(config)

        self.assertTrue(hasattr(engine, "use_specialist_team"))
        self.assertIs(engine.use_specialist_team, False)

        self.assertTrue(hasattr(engine, "buoy_analyst"))
        self.assertIsNone(engine.buoy_analyst)

        self.assertTrue(hasattr(engine, "pressure_analyst"))
        self.assertIsNone(engine.pressure_analyst)

        self.assertTrue(hasattr(engine, "senior_forecaster"))
        self.assertIsNone(engine.senior_forecaster)


if __name__ == "__main__":
    unittest.main()
