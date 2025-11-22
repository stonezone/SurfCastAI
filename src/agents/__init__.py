"""
Data collection agents for SurfCastAI.
"""

from .altimetry_agent import AltimetryAgent
from .base_agent import BaseAgent
from .buoy_agent import BuoyAgent
from .cdip_agent import CDIPAgent
from .chart_agent import ChartAgent
from .climatology_agent import ClimatologyAgent
from .marine_forecast_agent import MarineForecastAgent
from .metar_agent import MetarAgent
from .model_agent import ModelAgent
from .satellite_agent import SatelliteAgent
from .tide_agent import TideAgent
from .tropical_agent import TropicalAgent
from .upper_air_agent import UpperAirAgent
from .weather_agent import WeatherAgent

__all__ = [
    "BaseAgent",
    "BuoyAgent",
    "WeatherAgent",
    "ModelAgent",
    "SatelliteAgent",
    "MetarAgent",
    "TideAgent",
    "ChartAgent",
    "TropicalAgent",
    "MarineForecastAgent",
    "CDIPAgent",
    "AltimetryAgent",
    "UpperAirAgent",
    "ClimatologyAgent",
]
