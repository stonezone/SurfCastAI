"""
Standardized data model for wave model outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import json


@dataclass
class ModelPoint:
    """
    Single point prediction from a wave model.
    
    Attributes:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        wave_height: Significant wave height in meters
        wave_period: Wave period in seconds
        wave_direction: Wave direction in degrees
        wind_speed: Wind speed in meters per second
        wind_direction: Wind direction in degrees
        timestamp: Forecast timestamp
        raw_data: Original raw data
    """
    latitude: float
    longitude: float
    wave_height: float
    wave_period: Optional[float] = None
    wave_direction: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    timestamp: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'wave_height': self.wave_height,
            'wave_period': self.wave_period,
            'wave_direction': self.wave_direction,
            'wind_speed': self.wind_speed,
            'wind_direction': self.wind_direction,
            'timestamp': self.timestamp
        }


@dataclass
class ModelForecast:
    """
    Single time step forecast from a wave model.
    
    Attributes:
        timestamp: Forecast timestamp
        forecast_hour: Hours from model run start
        points: List of point predictions
        metadata: Additional metadata
    """
    timestamp: str
    forecast_hour: int
    points: List[ModelPoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': self.timestamp,
            'forecast_hour': self.forecast_hour,
            'points': [point.to_dict() for point in self.points],
            'metadata': self.metadata
        }


@dataclass
class ModelData:
    """
    Complete wave model dataset with metadata and forecasts.
    
    Attributes:
        model_id: Model identifier (e.g., 'swan', 'ww3')
        run_time: Model run timestamp
        region: Geographic region (e.g., 'hawaii', 'north_pacific')
        forecasts: List of time step forecasts
        metadata: Additional metadata
    """
    model_id: str
    run_time: str
    region: str
    forecasts: List[ModelForecast] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def latest_forecast(self) -> Optional[ModelForecast]:
        """Get the first forecast time step."""
        if not self.forecasts:
            return None
        return min(self.forecasts, key=lambda f: f.forecast_hour)
    
    @classmethod
    def from_swan_json(cls, data: Dict[str, Any]) -> 'ModelData':
        """
        Create a ModelData from SWAN model JSON data.
        
        Args:
            data: Dictionary with SWAN JSON data
            
        Returns:
            ModelData instance
        """
        # Extract basic metadata
        metadata = data.get('metadata', {})
        run_time = metadata.get('run_time', datetime.now().isoformat())
        region = metadata.get('region', 'unknown')
        
        # Create ModelData instance
        model_data = cls(
            model_id='swan',
            run_time=run_time,
            region=region,
            metadata=metadata
        )
        
        # Process forecasts
        forecasts_data = data.get('forecasts', [])
        for forecast in forecasts_data:
            timestamp = forecast.get('timestamp', '')
            forecast_hour = forecast.get('hour', 0)
            
            model_forecast = ModelForecast(
                timestamp=timestamp,
                forecast_hour=forecast_hour,
                metadata=forecast.get('metadata', {})
            )
            
            # Add points
            points_data = forecast.get('points', [])
            for point in points_data:
                model_point = ModelPoint(
                    latitude=point.get('lat', 0.0),
                    longitude=point.get('lon', 0.0),
                    wave_height=point.get('hs', 0.0),  # Significant wave height
                    wave_period=point.get('tp', None),  # Peak period
                    wave_direction=point.get('dir', None),  # Direction
                    wind_speed=point.get('wind_speed', None),
                    wind_direction=point.get('wind_dir', None),
                    timestamp=timestamp,
                    raw_data=point
                )
                model_forecast.points.append(model_point)
            
            model_data.forecasts.append(model_forecast)
        
        return model_data
    
    @classmethod
    def from_ww3_json(cls, data: Dict[str, Any]) -> 'ModelData':
        """
        Create a ModelData from WaveWatch III model JSON data.
        
        Args:
            data: Dictionary with WW3 JSON data
            
        Returns:
            ModelData instance
        """
        # Extract basic metadata
        header = data.get('header', {})
        run_time = header.get('refTime', datetime.now().isoformat())
        region = header.get('area', 'unknown')
        
        # Create ModelData instance
        model_data = cls(
            model_id='ww3',
            run_time=run_time,
            region=region,
            metadata=header
        )
        
        # Process forecasts - WW3 format is different from SWAN
        forecast_data = data.get('data', [])
        for time_step in forecast_data:
            timestamp = time_step.get('timestamp', '')
            forecast_hour = time_step.get('forecastHour', 0)
            
            model_forecast = ModelForecast(
                timestamp=timestamp,
                forecast_hour=forecast_hour,
                metadata={}
            )
            
            # Add grid points
            grid_data = time_step.get('grid', [])
            for point in grid_data:
                model_point = ModelPoint(
                    latitude=point.get('lat', 0.0),
                    longitude=point.get('lon', 0.0),
                    wave_height=point.get('hs', 0.0),
                    wave_period=point.get('tp', None),
                    wave_direction=point.get('dir', None),
                    wind_speed=point.get('ws', None),
                    wind_direction=point.get('wd', None),
                    timestamp=timestamp,
                    raw_data=point
                )
                model_forecast.points.append(model_point)
            
            model_data.forecasts.append(model_forecast)
        
        return model_data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'model_id': self.model_id,
            'run_time': self.run_time,
            'region': self.region,
            'forecasts': [forecast.to_dict() for forecast in self.forecasts],
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
    def from_json(cls, json_str: str) -> 'ModelData':
        """
        Create a ModelData from JSON string.
        
        Args:
            json_str: JSON string
            
        Returns:
            ModelData instance
        """
        data = json.loads(json_str)
        
        # Create ModelData instance
        model_data = cls(
            model_id=data.get('model_id', 'unknown'),
            run_time=data.get('run_time', ''),
            region=data.get('region', 'unknown'),
            metadata=data.get('metadata', {})
        )
        
        # Add forecasts
        for forecast_data in data.get('forecasts', []):
            model_forecast = ModelForecast(
                timestamp=forecast_data.get('timestamp', ''),
                forecast_hour=forecast_data.get('forecast_hour', 0),
                metadata=forecast_data.get('metadata', {})
            )
            
            # Add points
            for point_data in forecast_data.get('points', []):
                model_point = ModelPoint(
                    latitude=point_data.get('latitude', 0.0),
                    longitude=point_data.get('longitude', 0.0),
                    wave_height=point_data.get('wave_height', 0.0),
                    wave_period=point_data.get('wave_period'),
                    wave_direction=point_data.get('wave_direction'),
                    wind_speed=point_data.get('wind_speed'),
                    wind_direction=point_data.get('wind_direction'),
                    timestamp=point_data.get('timestamp')
                )
                model_forecast.points.append(model_point)
            
            model_data.forecasts.append(model_forecast)
        
        return model_data