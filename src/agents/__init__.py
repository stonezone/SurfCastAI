"""
Data collection agents for SurfCastAI.
"""

from .base_agent import BaseAgent
from .buoy_agent import BuoyAgent
from .weather_agent import WeatherAgent
from .model_agent import ModelAgent
from .satellite_agent import SatelliteAgent

__all__ = [
    'BaseAgent',
    'BuoyAgent',
    'WeatherAgent',
    'ModelAgent',
    'SatelliteAgent'
]