"""
Standardized data model for buoy observations.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ...utils.numeric import safe_float

# Physical constraint bounds for buoy data validation
WAVE_HEIGHT_BOUNDS = (0.0, 30.0)  # meters
DOMINANT_PERIOD_BOUNDS = (4.0, 30.0)  # seconds (< 4s = phantom swell)
AVERAGE_PERIOD_BOUNDS = (2.0, 25.0)  # seconds
WIND_SPEED_BOUNDS = (0.0, 150.0)  # knots
PRESSURE_BOUNDS = (900.0, 1100.0)  # millibars
WATER_TEMP_BOUNDS = (-2.0, 35.0)  # celsius
AIR_TEMP_BOUNDS = (-40.0, 50.0)  # celsius
DIRECTION_BOUNDS = (0.0, 360.0)  # degrees

logger = logging.getLogger(__name__)


@dataclass
class BuoyObservation:
    """
    Single observation from a buoy.

    Attributes:
        timestamp: Time of observation in ISO format
        wave_height: Significant wave height in meters
        dominant_period: Dominant wave period in seconds
        average_period: Average wave period in seconds
        wave_direction: Wave direction in degrees
        wind_speed: Wind speed in meters per second
        wind_direction: Wind direction in degrees
        air_temperature: Air temperature in Celsius
        water_temperature: Water temperature in Celsius
        pressure: Atmospheric pressure in hPa
        raw_data: Original raw data
    """

    timestamp: str
    wave_height: float | None = None
    dominant_period: float | None = None
    average_period: float | None = None
    wave_direction: float | None = None
    wind_speed: float | None = None
    wind_direction: float | None = None
    air_temperature: float | None = None
    water_temperature: float | None = None
    pressure: float | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_ndbc(cls, data: dict[str, str]) -> "BuoyObservation":
        """
        Create a BuoyObservation from NDBC data format.

        Args:
            data: Dictionary with NDBC data fields

        Returns:
            BuoyObservation instance
        """
        # NDBC key mappings
        # WVHT - wave height in meters
        # DPD - dominant wave period in seconds
        # APD - average wave period in seconds
        # MWD - wave direction in degrees
        # WSPD - wind speed in m/s
        # WDIR - wind direction in degrees
        # ATMP - air temperature in Celsius
        # WTMP - water temperature in Celsius
        # PRES - atmospheric pressure in hPa

        # Extract timestamp
        timestamp = data.get("Date", data.get("DATE", ""))
        if not timestamp:
            timestamp = datetime.now().isoformat()

        return cls(
            timestamp=timestamp,
            wave_height=safe_float(
                data.get("WVHT", data.get("wave_height", None)),
                min_val=WAVE_HEIGHT_BOUNDS[0],
                max_val=WAVE_HEIGHT_BOUNDS[1],
                field_name="wave_height",
            ),
            dominant_period=safe_float(
                data.get("DPD", data.get("dominant_period", None)),
                min_val=DOMINANT_PERIOD_BOUNDS[0],
                max_val=DOMINANT_PERIOD_BOUNDS[1],
                field_name="dominant_period",
            ),
            average_period=safe_float(
                data.get("APD", data.get("average_period", None)),
                min_val=AVERAGE_PERIOD_BOUNDS[0],
                max_val=AVERAGE_PERIOD_BOUNDS[1],
                field_name="average_period",
            ),
            wave_direction=safe_float(
                data.get("MWD", data.get("wave_direction", None)),
                min_val=DIRECTION_BOUNDS[0],
                max_val=DIRECTION_BOUNDS[1],
                field_name="wave_direction",
            ),
            wind_speed=safe_float(
                data.get("WSPD", data.get("wind_speed", None)),
                min_val=WIND_SPEED_BOUNDS[0],
                max_val=WIND_SPEED_BOUNDS[1],
                field_name="wind_speed",
            ),
            wind_direction=safe_float(
                data.get("WDIR", data.get("wind_direction", None)),
                min_val=DIRECTION_BOUNDS[0],
                max_val=DIRECTION_BOUNDS[1],
                field_name="wind_direction",
            ),
            air_temperature=safe_float(
                data.get("ATMP", data.get("air_temperature", None)),
                min_val=AIR_TEMP_BOUNDS[0],
                max_val=AIR_TEMP_BOUNDS[1],
                field_name="air_temperature",
            ),
            water_temperature=safe_float(
                data.get("WTMP", data.get("water_temperature", None)),
                min_val=WATER_TEMP_BOUNDS[0],
                max_val=WATER_TEMP_BOUNDS[1],
                field_name="water_temperature",
            ),
            pressure=safe_float(
                data.get("PRES", data.get("pressure", None)),
                min_val=PRESSURE_BOUNDS[0],
                max_val=PRESSURE_BOUNDS[1],
                field_name="pressure",
            ),
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
            "wave_height": self.wave_height,
            "dominant_period": self.dominant_period,
            "average_period": self.average_period,
            "wave_direction": self.wave_direction,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "air_temperature": self.air_temperature,
            "water_temperature": self.water_temperature,
            "pressure": self.pressure,
        }


@dataclass
class BuoyData:
    """
    Complete buoy dataset with metadata and observations.

    Attributes:
        station_id: Buoy station ID
        name: Buoy name or description
        latitude: Buoy latitude
        longitude: Buoy longitude
        observations: List of buoy observations
        metadata: Additional metadata
        spec_file_path: Optional path to spectral data file (.spec)
    """

    station_id: str
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    observations: list[BuoyObservation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    spec_file_path: str | None = None

    @property
    def latest_observation(self) -> BuoyObservation | None:
        """Get the latest observation."""
        if not self.observations:
            return None
        return self.observations[0]

    @classmethod
    def from_ndbc_json(cls, data: dict[str, Any]) -> "BuoyData":
        """
        Create a BuoyData from NDBC JSON data.

        Args:
            data: Dictionary with NDBC JSON data

        Returns:
            BuoyData instance
        """
        station_id = data.get("station_id", "unknown")

        # Create BuoyData instance
        buoy_data = cls(
            station_id=station_id,
            name=data.get("name", f"NDBC Buoy {station_id}"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            metadata=data.get("metadata", {}),
        )

        # Add observations
        for obs in data.get("observations", []):
            buoy_data.observations.append(BuoyObservation.from_ndbc(obs))

        return buoy_data

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "station_id": self.station_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "observations": [obs.to_dict() for obs in self.observations],
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
    def from_json(cls, json_str: str) -> "BuoyData":
        """
        Create a BuoyData from JSON string.

        Args:
            json_str: JSON string

        Returns:
            BuoyData instance
        """
        data = json.loads(json_str)

        # Create BuoyData instance
        buoy_data = cls(
            station_id=data.get("station_id", "unknown"),
            name=data.get("name"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            metadata=data.get("metadata", {}),
        )

        # Add observations - handle both raw NDBC format and normalized format
        for obs in data.get("observations", []):
            # Check if this is raw NDBC format (has 'WVHT', 'DPD', etc.)
            # or normalized format (has 'wave_height', 'dominant_period', etc.)
            if "WVHT" in obs or "DPD" in obs or "MWD" in obs:
                # Raw NDBC format - use from_ndbc to parse it
                observation = BuoyObservation.from_ndbc(obs)
            else:
                # Normalized format - apply bounds validation
                observation = BuoyObservation(
                    timestamp=obs.get("timestamp", ""),
                    wave_height=safe_float(
                        obs.get("wave_height"),
                        WAVE_HEIGHT_BOUNDS[0],
                        WAVE_HEIGHT_BOUNDS[1],
                        "wave_height",
                    ),
                    dominant_period=safe_float(
                        obs.get("dominant_period"),
                        DOMINANT_PERIOD_BOUNDS[0],
                        DOMINANT_PERIOD_BOUNDS[1],
                        "dominant_period",
                    ),
                    average_period=safe_float(
                        obs.get("average_period"),
                        AVERAGE_PERIOD_BOUNDS[0],
                        AVERAGE_PERIOD_BOUNDS[1],
                        "average_period",
                    ),
                    wave_direction=safe_float(
                        obs.get("wave_direction"),
                        DIRECTION_BOUNDS[0],
                        DIRECTION_BOUNDS[1],
                        "wave_direction",
                    ),
                    wind_speed=safe_float(
                        obs.get("wind_speed"),
                        WIND_SPEED_BOUNDS[0],
                        WIND_SPEED_BOUNDS[1],
                        "wind_speed",
                    ),
                    wind_direction=safe_float(
                        obs.get("wind_direction"),
                        DIRECTION_BOUNDS[0],
                        DIRECTION_BOUNDS[1],
                        "wind_direction",
                    ),
                    air_temperature=safe_float(
                        obs.get("air_temperature"),
                        AIR_TEMP_BOUNDS[0],
                        AIR_TEMP_BOUNDS[1],
                        "air_temperature",
                    ),
                    water_temperature=safe_float(
                        obs.get("water_temperature"),
                        WATER_TEMP_BOUNDS[0],
                        WATER_TEMP_BOUNDS[1],
                        "water_temperature",
                    ),
                    pressure=safe_float(
                        obs.get("pressure"), PRESSURE_BOUNDS[0], PRESSURE_BOUNDS[1], "pressure"
                    ),
                    raw_data=obs.get("raw_data", {}),
                )
            buoy_data.observations.append(observation)

        return buoy_data
