"""
Weather Agent for collecting weather forecast data from NOAA and other sources.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging

from .base_agent import BaseAgent
from ..core.config import Config
from ..core.http_client import HTTPClient


class WeatherAgent(BaseAgent):
    """
    Agent for collecting weather forecast data from various sources.

    Features:
    - Collects data from National Weather Service API
    - Supports location-specific forecasts for Oahu
    - Extracts marine forecasts and wind data
    - Processes and normalizes forecast data
    """

    def __init__(self, config: Config, http_client: Optional[HTTPClient] = None):
        """Initialize the WeatherAgent."""
        super().__init__(config, http_client)
        self.logger = logging.getLogger('agent.weather')

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Collect weather data from configured sources.

        Args:
            data_dir: Directory to store collected data

        Returns:
            List of metadata dictionaries
        """
        # Use the provided data_dir directly (already agent-specific)
        weather_dir = data_dir

        # Get weather URLs from config
        weather_urls = self.config.get_data_source_urls('weather').get('weather', [])

        if not weather_urls:
            self.logger.warning("No weather URLs configured")
            return []

        # Ensure HTTP client is available
        await self.ensure_http_client()

        # Create tasks for all weather URLs
        tasks = []
        for url in weather_urls:
            tasks.append(self.process_weather_url(url, weather_dir))

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing weather data: {result}")
            elif result:
                metadata_list.append(result)

        return metadata_list

    async def process_weather_url(self, url: str, weather_dir: Path) -> Dict[str, Any]:
        """
        Process a single weather data URL.

        Args:
            url: URL to the weather data
            weather_dir: Directory to store weather data

        Returns:
            Metadata dictionary
        """
        try:
            # Generate a descriptive name based on the URL
            parts = url.split('/')
            location = "unknown"

            # Extract location information from URL
            if 'gridpoints' in url:
                # NWS API format: /gridpoints/XXX/Y,Z/forecast
                office_idx = parts.index('gridpoints') + 1
                grid_idx = office_idx + 1

                if office_idx < len(parts) and grid_idx < len(parts):
                    office = parts[office_idx]
                    grid = parts[grid_idx]
                    location = f"{office}_{grid}"
            elif 'points' in url:
                # NWS API format: /points/LAT,LON/forecast
                coords_idx = parts.index('points') + 1

                if coords_idx < len(parts):
                    coords = parts[coords_idx].replace(',', '_')
                    location = f"point_{coords}"

            self.logger.info(f"Processing weather data for {location}")

            # Download the weather data
            result = await self.http_client.download(url)

            if not result.success:
                return self.create_metadata(
                    name=f"weather_{location}",
                    description=f"Failed to fetch weather data for {location}",
                    data_type="json",
                    source_url=url,
                    error=result.error
                )

            # Parse the JSON content
            try:
                content = result.content.decode('utf-8', errors='ignore')
                data = json.loads(content)

                # Save the parsed data
                filename = f"weather_{location}.json"
                file_path = weather_dir / filename

                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)

                # Extract key information for metadata
                forecast_info = self._extract_forecast_info(data)

                return self.create_metadata(
                    name=f"weather_{location}",
                    description=f"Weather forecast data for {location}",
                    data_type="json",
                    source_url=url,
                    file_path=str(file_path),
                    location=location,
                    forecast_info=forecast_info
                )
            except json.JSONDecodeError:
                # Not valid JSON, save as text
                filename = f"weather_{location}.txt"
                file_path = weather_dir / filename

                with open(file_path, 'w') as f:
                    f.write(content)

                return self.create_metadata(
                    name=f"weather_{location}",
                    description=f"Raw weather data for {location}",
                    data_type="text",
                    source_url=url,
                    file_path=str(file_path),
                    location=location,
                    warning="Could not parse as JSON"
                )

        except Exception as e:
            self.logger.error(f"Error processing weather data from {url}: {e}")
            return self.create_metadata(
                name=f"weather_{location if 'location' in locals() else 'unknown'}",
                description="Failed to process weather data",
                data_type="unknown",
                source_url=url,
                error=str(e)
            )

    def _extract_forecast_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key forecast information from weather data.

        Args:
            data: Weather data dictionary

        Returns:
            Dictionary with key forecast information
        """
        forecast_info = {
            'update_time': datetime.now().isoformat(),
            'provider': 'unknown',
            'forecast_period': 'unknown',
            'periods': 0,
            'contains_wind': False,
            'contains_marine': False
        }

        try:
            # Handle NWS API format
            if 'properties' in data:
                props = data['properties']

                if 'updateTime' in props:
                    forecast_info['update_time'] = props['updateTime']

                if 'periods' in props:
                    periods = props['periods']
                    forecast_info['periods'] = len(periods)

                    # Check for wind data
                    if periods and 'windSpeed' in periods[0]:
                        forecast_info['contains_wind'] = True

                # Set provider
                forecast_info['provider'] = 'National Weather Service'

                # Determine if it's a marine forecast
                if 'forecastOffice' in props and 'Marine' in props.get('forecastOffice', ''):
                    forecast_info['contains_marine'] = True

                # Get forecast period
                if periods:
                    start = periods[0].get('startTime', '')
                    end = periods[-1].get('endTime', '')
                    if start and end:
                        forecast_info['forecast_period'] = f"{start} to {end}"

        except Exception as e:
            self.logger.warning(f"Error extracting forecast info: {e}")

        return forecast_info
