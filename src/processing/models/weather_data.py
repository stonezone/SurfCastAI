"""
Standardized data model for weather forecast data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import json


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
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    temperature: Optional[float] = None
    temperature_unit: str = "C"
    wind_speed: Optional[float] = None
    wind_speed_unit: str = "m/s"
    wind_direction: Optional[float] = None
    short_forecast: Optional[str] = None
    detailed_forecast: Optional[str] = None
    icon: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_nws(cls, data: Dict[str, Any]) -> 'WeatherPeriod':
        """
        Create a WeatherPeriod from NWS API data format.
        
        Args:
            data: Dictionary with NWS API data fields
            
        Returns:
            WeatherPeriod instance
        """
        # Convert string values to float, handling missing or invalid values
        def safe_float(value: Any) -> Optional[float]:
            try:
                if isinstance(value, (int, float)):
                    return float(value)
                elif isinstance(value, str):
                    # Handle strings like "10 mph" or "10-15 mph"
                    if ' ' in value:
                        value = value.split(' ')[0]
                    if '-' in value:
                        # Take average of range
                        low, high = value.split('-')
                        return (float(low) + float(high)) / 2
                    return float(value)
                return None
            except (ValueError, TypeError):
                return None
        
        # Extract wind speed and unit
        wind_speed = None
        wind_speed_unit = "m/s"
        wind_speed_str = data.get('windSpeed', '')
        if wind_speed_str:
            # Handle formats like "10 mph" or "10-15 mph"
            if ' ' in wind_speed_str:
                speed_part, unit_part = wind_speed_str.rsplit(' ', 1)
                wind_speed = safe_float(speed_part)
                wind_speed_unit = unit_part
            else:
                wind_speed = safe_float(wind_speed_str)
        
        # Extract temperature and unit
        temperature = None
        temperature_unit = "C"
        temp_value = data.get('temperature')
        temp_unit = data.get('temperatureUnit', 'F')
        if temp_value is not None:
            temperature = safe_float(temp_value)
            temperature_unit = temp_unit
        
        # Extract timestamp
        timestamp = data.get('startTime', data.get('timestamp', ''))
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        return cls(
            timestamp=timestamp,
            start_time=data.get('startTime'),
            end_time=data.get('endTime'),
            temperature=temperature,
            temperature_unit=temperature_unit,
            wind_speed=wind_speed,
            wind_speed_unit=wind_speed_unit,
            wind_direction=safe_float(data.get('windDirection')),
            short_forecast=data.get('shortForecast'),
            detailed_forecast=data.get('detailedForecast'),
            icon=data.get('icon'),
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
            'start_time': self.start_time,
            'end_time': self.end_time,
            'temperature': self.temperature,
            'temperature_unit': self.temperature_unit,
            'wind_speed': self.wind_speed,
            'wind_speed_unit': self.wind_speed_unit,
            'wind_direction': self.wind_direction,
            'short_forecast': self.short_forecast,
            'detailed_forecast': self.detailed_forecast,
            'icon': self.icon
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
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    periods: List[WeatherPeriod] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def current_period(self) -> Optional[WeatherPeriod]:
        """Get the current/first forecast period."""
        if not self.periods:
            return None
        return self.periods[0]
    
    @classmethod
    def from_nws_json(cls, data: Dict[str, Any]) -> 'WeatherData':
        """
        Create a WeatherData from NWS API JSON data.
        
        Args:
            data: Dictionary with NWS API JSON data
            
        Returns:
            WeatherData instance
        """
        properties = data.get('properties', {})
        
        # Extract location information
        location = properties.get('location', {}).get('name', 'Unknown')
        
        # Extract coordinates if available
        geometry = data.get('geometry', {})
        coordinates = geometry.get('coordinates', [0, 0]) if geometry else [0, 0]
        latitude, longitude = coordinates[1], coordinates[0] if len(coordinates) >= 2 else (None, None)
        
        # Create WeatherData instance
        weather_data = cls(
            provider='nws',
            location=location,
            latitude=latitude,
            longitude=longitude,
            metadata=properties
        )
        
        # Add forecast periods
        periods_data = properties.get('periods', [])
        for period_data in periods_data:
            weather_data.periods.append(WeatherPeriod.from_nws(period_data))
        
        return weather_data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'provider': self.provider,
            'location': self.location,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'periods': [period.to_dict() for period in self.periods],
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
    def from_json(cls, json_str: str) -> 'WeatherData':
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
            provider=data.get('provider', 'unknown'),
            location=data.get('location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            metadata=data.get('metadata', {})
        )
        
        # Add periods
        for period_data in data.get('periods', []):
            period = WeatherPeriod(
                timestamp=period_data.get('timestamp', ''),
                start_time=period_data.get('start_time'),
                end_time=period_data.get('end_time'),
                temperature=period_data.get('temperature'),
                temperature_unit=period_data.get('temperature_unit', 'C'),
                wind_speed=period_data.get('wind_speed'),
                wind_speed_unit=period_data.get('wind_speed_unit', 'm/s'),
                wind_direction=period_data.get('wind_direction'),
                short_forecast=period_data.get('short_forecast'),
                detailed_forecast=period_data.get('detailed_forecast'),
                icon=period_data.get('icon')
            )
            weather_data.periods.append(period)
        
        return weather_data