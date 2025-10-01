"""
Data collection agents for SurfCastAI.
"""

from .base_agent import BaseAgent
from .buoy_agent import BuoyAgent
from .weather_agent import WeatherAgent
from .model_agent import ModelAgent
from .satellite_agent import SatelliteAgent
from .metar_agent import MetarAgent
from .tide_agent import TideAgent
from .chart_agent import ChartAgent
from .tropical_agent import TropicalAgent

__all__ = [
    'BaseAgent',
    'BuoyAgent',
    'WeatherAgent',
    'ModelAgent',
    'SatelliteAgent',
    'MetarAgent',
    'TideAgent',
    'ChartAgent',
    'TropicalAgent'
]