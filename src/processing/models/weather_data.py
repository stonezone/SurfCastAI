"""
Standardized data model for weather forecast data.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ...utils.numeric import safe_float


@dataclass
class WeatherPeriod:
    """
    Single period in a weather forecast.

    Attributes:
        timestamp: Time of forecast in ISO format
        start_time: Start time of forecast period
        end_time: End time of forecast period
        temperature: Temperature in Celsius
        temperature_unit: Unit for temperature (C, F)
        wind_speed: Wind speed in the specified unit
        wind_speed_unit: Unit for wind speed (m/s, mph, knots)
        wind_direction: Wind direction in degrees
        short_forecast: Short forecast description
        detailed_forecast: Detailed forecast description
        icon: URL to forecast icon
        raw_data: Original raw data
    """

    timestamp: str
    start_time: str | None = None
    end_time: str | None = None
    temperature: float | None = None
    temperature_unit: str = "C"
    wind_speed: float | None = None
    wind_speed_unit: str = "m/s"
    wind_direction: float | None = None
    short_forecast: str | None = None
    detailed_forecast: str | None = None
    icon: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_nws(cls, data: dict[str, Any]) -> "WeatherPeriod":
        """
        Create a WeatherPeriod from NWS API data format.

        Args:
            data: Dictionary with NWS API data fields

        Returns:
            WeatherPeriod instance
        """
        # Extract wind speed and unit
        wind_speed = None
        wind_speed_unit = "m/s"
        wind_speed_str = data.get("windSpeed", "")
        if wind_speed_str:
            # Handle formats like "10 mph" or "10-15 mph"
            if " " in wind_speed_str:
                speed_part, unit_part = wind_speed_str.rsplit(" ", 1)
                wind_speed = safe_float(speed_part)
                wind_speed_unit = unit_part
            else:
                wind_speed = safe_float(wind_speed_str)

        # Extract temperature and unit
        temperature = None
        temperature_unit = "C"
        temp_value = data.get("temperature")
        temp_unit = data.get("temperatureUnit", "F")
        if temp_value is not None:
            temperature = safe_float(temp_value)
            temperature_unit = temp_unit

        # Extract timestamp
        timestamp = data.get("startTime", data.get("timestamp", ""))
        if not timestamp:
            timestamp = datetime.now().isoformat()

        return cls(
            timestamp=timestamp,
            start_time=data.get("startTime"),
            end_time=data.get("endTime"),
            temperature=temperature,
            temperature_unit=temperature_unit,
            wind_speed=wind_speed,
            wind_speed_unit=wind_speed_unit,
            wind_direction=safe_float(data.get("windDirection")),
            short_forecast=data.get("shortForecast"),
            detailed_forecast=data.get("detailedForecast"),
            icon=data.get("icon"),
            raw_data=data,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "timestamp": self.timestamp,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "temperature": self.temperature,
            "temperature_unit": self.temperature_unit,
            "wind_speed": self.wind_speed,
            "wind_speed_unit": self.wind_speed_unit,
            "wind_direction": self.wind_direction,
            "short_forecast": self.short_forecast,
            "detailed_forecast": self.detailed_forecast,
            "icon": self.icon,
        }


@dataclass
class WeatherData:
    """
    Complete weather dataset with metadata and forecast periods.

    Attributes:
        provider: Weather data provider (e.g., 'nws', 'noaa')
        location: Location description or name
        latitude: Location latitude
        longitude: Location longitude
        periods: List of forecast periods
        metadata: Additional metadata
    """

    provider: str
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    periods: list[WeatherPeriod] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def current_period(self) -> WeatherPeriod | None:
        """Get the current/first forecast period."""
        if not self.periods:
            return None
        return self.periods[0]

    @classmethod
    def from_nws_json(cls, data: dict[str, Any]) -> "WeatherData":
        """
        Create a WeatherData from NWS API JSON data.

        Args:
            data: Dictionary with NWS API JSON data

        Returns:
            WeatherData instance
        """
        properties = data.get("properties", {})

        # Extract location information
        location = properties.get("location", {}).get("name", "Unknown")

        # Extract coordinates if available
        latitude = None
        longitude = None
        geometry = data.get("geometry") or {}
        coords: list[Any] | None = None

        if geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
        else:
            # NWS gridpoint forecasts often expose a relativeLocation point instead of a geometry point
            relative = properties.get("relativeLocation", {}).get("geometry", {})
            if relative.get("type") == "Point":
                coords = relative.get("coordinates", [])

        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            longitude, latitude = coords[0], coords[1]

        # Create WeatherData instance
        weather_data = cls(
            provider="nws",
            location=location,
            latitude=latitude,
            longitude=longitude,
            metadata=properties,
        )

        # Add forecast periods
        periods_data = properties.get("periods", [])
        for period_data in periods_data:
            weather_data.periods.append(WeatherPeriod.from_nws(period_data))

        return weather_data

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "provider": self.provider,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "periods": [period.to_dict() for period in self.periods],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WeatherData":
        """
        Create a WeatherData from JSON string.

        Args:
            json_str: JSON string

        Returns:
            WeatherData instance
        """
        data = json.loads(json_str)

        # Create WeatherData instance
        weather_data = cls(
            provider=data.get("provider", "unknown"),
            location=data.get("location"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            metadata=data.get("metadata", {}),
        )

        # Add periods
        for period_data in data.get("periods", []):
            period = WeatherPeriod(
                timestamp=period_data.get("timestamp", ""),
                start_time=period_data.get("start_time"),
                end_time=period_data.get("end_time"),
                temperature=period_data.get("temperature"),
                temperature_unit=period_data.get("temperature_unit", "C"),
                wind_speed=period_data.get("wind_speed"),
                wind_speed_unit=period_data.get("wind_speed_unit", "m/s"),
                wind_direction=period_data.get("wind_direction"),
                short_forecast=period_data.get("short_forecast"),
                detailed_forecast=period_data.get("detailed_forecast"),
                icon=period_data.get("icon"),
            )
            weather_data.periods.append(period)

        return weather_data
