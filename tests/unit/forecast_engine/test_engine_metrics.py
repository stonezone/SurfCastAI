"""Unit tests for ForecastEngine metric reset behavior."""

import unittest
from datetime import datetime

from src.core import Config
from src.forecast_engine import ForecastEngine
from src.processing.models.swell_event import SwellForecast


def _build_config() -> Config:
    config = Config()
    config._config = {
        "forecast": {
            "use_local_generator": True,
            "use_specialist_team": False,
            "refinement_cycles": 0,
            "templates_dir": None,
            "image_detail_levels": {},
        },
        "openai": {
            "model": "gpt-5-nano",
            "analysis_models": [],
        },
    }
    return config


class TestForecastEngineMetrics(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = ForecastEngine(_build_config())

    async def test_reset_run_metrics_zeroes_counters(self) -> None:
        # Manually set metrics in OpenAIClient
        self.engine.openai_client.total_cost = 3.14
        self.engine.openai_client.api_call_count = 5
        self.engine.openai_client.total_input_tokens = 123
        self.engine.openai_client.total_output_tokens = 456
        self.engine.estimated_tokens = 789

        await self.engine._reset_run_metrics()

        # Verify OpenAIClient metrics reset
        metrics = await self.engine.openai_client.get_metrics()
        self.assertEqual(metrics["total_cost"], 0.0)
        self.assertEqual(metrics["api_calls"], 0)
        self.assertEqual(metrics["input_tokens"], 0)
        self.assertEqual(metrics["output_tokens"], 0)
        self.assertEqual(self.engine.estimated_tokens, 0)

    async def test_generate_forecast_resets_between_runs(self) -> None:
        run_metrics = iter(
            [
                {
                    "cost": 1.25,
                    "calls": 2,
                    "input_tokens": 120,
                    "output_tokens": 45,
                    "estimated_tokens": 165,
                },
                {
                    "cost": 0.4,
                    "calls": 1,
                    "input_tokens": 30,
                    "output_tokens": 15,
                    "estimated_tokens": 60,
                },
            ]
        )

        async def fake_main(forecast_data):
            values = next(run_metrics)
            # Update OpenAIClient metrics
            self.engine.openai_client.total_cost += values["cost"]
            self.engine.openai_client.api_call_count += values["calls"]
            self.engine.openai_client.total_input_tokens += values["input_tokens"]
            self.engine.openai_client.total_output_tokens += values["output_tokens"]
            self.engine.estimated_tokens += values["estimated_tokens"]
            return "main-forecast"

        async def fake_shore(shore_key, forecast_data):
            return f"{shore_key}-forecast"

        async def fake_daily(forecast_data):
            return "daily-forecast"

        def fake_prepare(swell_forecast):
            return {"confidence": {}}

        self.engine._generate_main_forecast = fake_main
        self.engine._generate_shore_forecast = fake_shore
        self.engine._generate_daily_forecast = fake_daily
        self.engine.data_manager.prepare_forecast_data = fake_prepare

        first_forecast = SwellForecast(
            forecast_id="run-1",
            generated_time=datetime.utcnow().isoformat(),
        )

        first_result = await self.engine.generate_forecast(first_forecast)
        self.assertEqual(first_result["main_forecast"], "main-forecast")

        # Check OpenAIClient metrics
        metrics = await self.engine.openai_client.get_metrics()
        self.assertEqual(metrics["total_cost"], 1.25)
        self.assertEqual(metrics["api_calls"], 2)
        self.assertEqual(metrics["input_tokens"], 120)
        self.assertEqual(metrics["output_tokens"], 45)
        self.assertEqual(self.engine.estimated_tokens, 165)

        second_forecast = SwellForecast(
            forecast_id="run-2",
            generated_time=datetime.utcnow().isoformat(),
        )

        second_result = await self.engine.generate_forecast(second_forecast)
        self.assertEqual(second_result["main_forecast"], "main-forecast")

        # Check metrics reset between runs
        metrics = await self.engine.openai_client.get_metrics()
        self.assertEqual(metrics["total_cost"], 0.4)
        self.assertEqual(metrics["api_calls"], 1)
        self.assertEqual(metrics["input_tokens"], 30)
        self.assertEqual(metrics["output_tokens"], 15)
        self.assertEqual(self.engine.estimated_tokens, 60)


if __name__ == "__main__":
    unittest.main()
