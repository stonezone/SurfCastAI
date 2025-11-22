"""
Specialist modules for SurfCastAI forecast engine.

This package contains specialized analysis modules that use AI to analyze
specific types of data (buoys, weather, models) and provide structured
insights for forecast generation.
"""

from .base_specialist import BaseSpecialist, SpecialistOutput
from .buoy_analyst import BuoyAnalyst
from .pressure_analyst import PressureAnalyst
from .senior_forecaster import SeniorForecaster

__all__ = [
    'BaseSpecialist',
    'SpecialistOutput',
    'BuoyAnalyst',
    'PressureAnalyst',
    'SeniorForecaster',
]
