#!/usr/bin/env python3
"""Generate a sample SurfCastAI forecast using the configured OpenAI model."""

import argparse
import asyncio
import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path

from src.core import load_config
from src.forecast_engine import ForecastEngine, ForecastFormatter
from src.processing.models.swell_event import (
    SwellEvent,
    SwellComponent,
    SwellForecast,
    ForecastLocation,
)


def create_sample_forecast() -> SwellForecast:
    """Reuse the synthetic swell data from the unit test for quick validation."""
    now = datetime.now()
    start_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    peak_time = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def swell(event_id: str, direction: int, hawaiian: float, source: str) -> SwellEvent:
        event = SwellEvent(
            event_id=event_id,
            start_time=start_time,
            peak_time=peak_time,
            end_time=end_time,
            primary_direction=direction,
            significance=0.7,
            hawaii_scale=hawaiian,
            source=source,
        )
        event.primary_components.append(
            SwellComponent(
                height=hawaiian / 2.0,
                period=14.0,
                direction=direction,
                confidence=0.8,
                source=source,
            )
        )
        return event

    north_event = swell("sample_north", 315, 12.0, "model")
    south_event = swell("sample_south", 190, 4.0, "model")
    trade_event = swell("sample_trade", 70, 3.0, "buoy")

    north_shore = ForecastLocation(
        name="Oahu North Shore",
        shore="North Shore",
        latitude=21.6639,
        longitude=-158.0529,
        facing_direction=0,
        metadata={
            "seasonal_factor": 0.9,
            "popular_breaks": ["Pipeline", "Sunset Beach", "Waimea Bay"],
        },
    )
    north_shore.swell_events.extend([north_event, trade_event])

    south_shore = ForecastLocation(
        name="Oahu South Shore",
        shore="South Shore",
        latitude=21.2749,
        longitude=-157.8238,
        facing_direction=180,
        metadata={
            "seasonal_factor": 0.3,
            "popular_breaks": ["Waikiki", "Ala Moana", "Kewalos"],
        },
    )
    south_shore.swell_events.append(south_event)

    forecast = SwellForecast(
        forecast_id="sample_forecast",
        generated_time=start_time,
        metadata={
            "confidence": {
                "overall_score": 0.8,
                "factors": {
                    "data_freshness": 0.9,
                    "source_diversity": 0.75,
                    "source_agreement": 0.8,
                },
            }
        },
    )
    forecast.swell_events.extend([north_event, south_event, trade_event])
    forecast.locations.extend([north_shore, south_shore])
    return forecast


async def run(model: str, output_dir: Path, force_remote: bool) -> None:
    load_dotenv()
    config = load_config()
    config._config.setdefault("openai", {})["model"] = model
    if force_remote:
        config._config.setdefault("forecast", {})["use_local_generator"] = False

    logger = logging.getLogger("surfcastai.sample")
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    engine = ForecastEngine(config)
    forecast = await engine.generate_forecast(create_sample_forecast())
    if "error" in forecast:
        raise RuntimeError(f"Forecast generation failed: {forecast['error']}")

    formatter = ForecastFormatter(config)
    formatted = formatter.format_forecast(forecast)

    output_dir.mkdir(parents=True, exist_ok=True)
    main_path = output_dir / "forecast.txt"
    main_path.write_text(forecast["main_forecast"], encoding="utf-8")

    print(f"Generated forecast with {model}; main text saved to {main_path}")
    for fmt, path in formatted.items():
        print(f"  {fmt}: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a sample SurfCastAI forecast via GPT-5 nano")
    parser.add_argument("--model", default="gpt-5-nano", help="OpenAI model to use")
    parser.add_argument("--output", default="output/sample", help="Directory for rendered forecast")
    parser.add_argument("--force-remote", action="store_true", help="Disable local fallback even if configured")
    args = parser.parse_args()

    config = load_config()
    if not config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        parser.error("Set OPENAI_API_KEY or provide openai.api_key in config/config.yaml")

    asyncio.run(run(args.model, Path(args.output), args.force_remote))


if __name__ == "__main__":
    main()
