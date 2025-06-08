"""
Standardized data model for buoy observations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import json


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
    wave_height: Optional[float] = None
    dominant_period: Optional[float] = None
    average_period: Optional[float] = None
    wave_direction: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    air_temperature: Optional[float] = None
    water_temperature: Optional[float] = None
    pressure: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_ndbc(cls, data: Dict[str, str]) -> 'BuoyObservation':
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
        timestamp = data.get('Date', data.get('DATE', ''))
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        # Convert string values to float, handling missing or invalid values
        def safe_float(value: str) -> Optional[float]:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        
        return cls(
            timestamp=timestamp,
            wave_height=safe_float(data.get('WVHT', data.get('wave_height', None))),
            dominant_period=safe_float(data.get('DPD', data.get('dominant_period', None))),
            average_period=safe_float(data.get('APD', data.get('average_period', None))),
            wave_direction=safe_float(data.get('MWD', data.get('wave_direction', None))),
            wind_speed=safe_float(data.get('WSPD', data.get('wind_speed', None))),
            wind_direction=safe_float(data.get('WDIR', data.get('wind_direction', None))),
            air_temperature=safe_float(data.get('ATMP', data.get('air_temperature', None))),
            water_temperature=safe_float(data.get('WTMP', data.get('water_temperature', None))),
            pressure=safe_float(data.get('PRES', data.get('pressure', None))),
            raw_data=data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': self.timestamp,
            'wave_height': self.wave_height,
            'dominant_period': self.dominant_period,
            'average_period': self.average_period,
            'wave_direction': self.wave_direction,
            'wind_speed': self.wind_speed,
            'wind_direction': self.wind_direction,
            'air_temperature': self.air_temperature,
            'water_temperature': self.water_temperature,
            'pressure': self.pressure
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
    """
    station_id: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observations: List[BuoyObservation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def latest_observation(self) -> Optional[BuoyObservation]:
        """Get the latest observation."""
        if not self.observations:
            return None
        return self.observations[0]
    
    @classmethod
    def from_ndbc_json(cls, data: Dict[str, Any]) -> 'BuoyData':
        """
        Create a BuoyData from NDBC JSON data.
        
        Args:
            data: Dictionary with NDBC JSON data
            
        Returns:
            BuoyData instance
        """
        station_id = data.get('station_id', 'unknown')
        
        # Create BuoyData instance
        buoy_data = cls(
            station_id=station_id,
            name=data.get('name', f"NDBC Buoy {station_id}"),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            metadata=data.get('metadata', {})
        )
        
        # Add observations
        for obs in data.get('observations', []):
            buoy_data.observations.append(BuoyObservation.from_ndbc(obs))
        
        return buoy_data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'station_id': self.station_id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'observations': [obs.to_dict() for obs in self.observations],
            'metadata': self.metadata
        }
    
    def to_json(self) -> str:
        """
        Convert to JSON string.
        
        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BuoyData':
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
            station_id=data.get('station_id', 'unknown'),
            name=data.get('name'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            metadata=data.get('metadata', {})
        )
        
        # Add observations
        for obs in data.get('observations', []):
            # Create BuoyObservation
            observation = BuoyObservation(
                timestamp=obs.get('timestamp', ''),
                wave_height=obs.get('wave_height'),
                dominant_period=obs.get('dominant_period'),
                average_period=obs.get('average_period'),
                wave_direction=obs.get('wave_direction'),
                wind_speed=obs.get('wind_speed'),
                wind_direction=obs.get('wind_direction'),
                air_temperature=obs.get('air_temperature'),
                water_temperature=obs.get('water_temperature'),
                pressure=obs.get('pressure'),
                raw_data=obs.get('raw_data', {})
            )
            buoy_data.observations.append(observation)
        
        return buoy_data