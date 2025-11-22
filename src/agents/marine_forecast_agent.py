"""
Marine Forecast Agent for collecting wave forecast data from Open-Meteo Marine API.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.http_client import HTTPClient
from .base_agent import BaseAgent


class MarineForecastAgent(BaseAgent):
    """
    Agent for collecting marine wave forecasts from Open-Meteo Marine API.

    Features:
    - Collects hourly wave height, period, and direction forecasts
    - Covers multiple grid points around Oahu
    - Free API with no authentication required
    - 7-day forecast horizon
    """

    def __init__(self, config: Config, http_client: HTTPClient | None = None):
        """Initialize the MarineForecastAgent."""
        super().__init__(config, http_client)

    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        """
        Collect marine forecast data from Open-Meteo Marine API.

        Args:
            data_dir: Directory to store collected data

        Returns:
            List of metadata dictionaries
        """
        # Ensure data directory exists
        forecast_dir = data_dir / "marine_forecasts"
        forecast_dir.mkdir(exist_ok=True)

        # Get marine forecast URLs from config
        forecast_urls = self.config.get_data_source_urls("marine_forecasts").get(
            "marine_forecasts", []
        )

        if not forecast_urls:
            self.logger.warning("No marine forecast URLs configured")
            return []

        # Ensure HTTP client is available
        await self.ensure_http_client()

        # Create tasks for all forecast URLs
        tasks = []
        for url in forecast_urls:
            tasks.append(self.process_forecast(url, forecast_dir))

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing marine forecast: {result}")
            elif result:
                metadata_list.append(result)

        return metadata_list

    async def process_forecast(self, url: str, forecast_dir: Path) -> dict[str, Any]:
        """
        Process a single marine forecast endpoint.

        Args:
            url: Open-Meteo Marine API URL
            forecast_dir: Directory to save forecast data

        Returns:
            Metadata dictionary for the collected forecast
        """
        try:
            # Extract location from URL for identification
            location_id = self._extract_location_id(url)
            self.logger.info(f"Processing marine forecast for location {location_id}")

            # Fetch forecast data
            result = await self.http_client.download(url)
            if not result.success:
                return self.create_metadata(
                    name=f"marine_forecast_{location_id}",
                    description=f"Failed to fetch marine forecast for {location_id}",
                    data_type="json",
                    source_url=url,
                    error=result.error,
                )

            # Parse JSON response
            try:
                forecast_data = json.loads(result.content.decode("utf-8"))
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON from {url}: {e}")
                return self.create_metadata(
                    name=f"marine_forecast_{location_id}",
                    description=f"Failed to parse marine forecast JSON for {location_id}",
                    data_type="json",
                    source_url=url,
                    error=str(e),
                )

            # Validate required fields
            if "hourly" not in forecast_data:
                self.logger.warning(f"No hourly data in marine forecast for {location_id}")
                return self.create_metadata(
                    name=f"marine_forecast_{location_id}",
                    description=f"No hourly data in marine forecast for {location_id}",
                    data_type="json",
                    source_url=url,
                    error="Missing hourly data",
                )

            # Save forecast data
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"marine_forecast_{location_id}_{timestamp}.json"
            filepath = forecast_dir / filename

            with open(filepath, "w") as f:
                json.dump(forecast_data, f, indent=2)

            self.logger.info(f"Saved marine forecast to {filepath}")

            # Extract summary statistics
            hourly = forecast_data.get("hourly", {})
            wave_heights = hourly.get("wave_height", [])
            wave_periods = hourly.get("wave_period", [])
            wave_directions = hourly.get("wave_direction", [])

            summary = {
                "data_points": len(wave_heights),
                "max_wave_height": max(wave_heights) if wave_heights else None,
                "avg_wave_height": sum(wave_heights) / len(wave_heights) if wave_heights else None,
                "max_wave_period": max(wave_periods) if wave_periods else None,
                "avg_wave_period": sum(wave_periods) / len(wave_periods) if wave_periods else None,
            }

            return self.create_metadata(
                name=f"marine_forecast_{location_id}",
                description=f"Open-Meteo Marine API wave forecast for {location_id}",
                data_type="json",
                source_url=url,
                file_path=str(filepath),
                metadata={
                    "location_id": location_id,
                    "latitude": forecast_data.get("latitude"),
                    "longitude": forecast_data.get("longitude"),
                    "timezone": forecast_data.get("timezone"),
                    "summary": summary,
                    "forecast_horizon_hours": len(wave_heights),
                },
            )

        except Exception as e:
            self.logger.error(f"Error processing marine forecast {url}: {e}", exc_info=True)
            return self.create_metadata(
                name="marine_forecast_unknown",
                description="Error processing marine forecast",
                data_type="json",
                source_url=url,
                error=str(e),
            )

    def _extract_location_id(self, url: str) -> str:
        """
        Extract a location identifier from the Open-Meteo URL.

        Args:
            url: Open-Meteo Marine API URL

        Returns:
            Location identifier (e.g., "lat21.7_lon-158.0")
        """
        try:
            # Parse URL parameters
            if "?" not in url:
                return "unknown"

            params = url.split("?")[1]
            lat = None
            lon = None

            for param in params.split("&"):
                if "=" not in param:
                    continue
                key, value = param.split("=", 1)
                if key == "latitude":
                    lat = value
                elif key == "longitude":
                    lon = value

            if lat and lon:
                # Create clean identifier
                lat_str = lat.replace(".", "p").replace("-", "m")
                lon_str = lon.replace(".", "p").replace("-", "m")
                return f"lat{lat_str}_lon{lon_str}"

            return "unknown"

        except Exception as e:
            self.logger.warning(f"Failed to extract location from URL {url}: {e}")
            return "unknown"
