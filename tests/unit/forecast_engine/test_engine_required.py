#!/usr/bin/env python3
"""
Test script for Task 2.1: Verify engine parameter is required in all specialists.

This script tests that all three specialist classes (BuoyAnalyst, PressureAnalyst,
SeniorForecaster) raise ValueError when instantiated with engine=None.
"""

import pytest
from src.forecast_engine.specialists.buoy_analyst import BuoyAnalyst
from src.forecast_engine.specialists.pressure_analyst import PressureAnalyst
from src.forecast_engine.specialists.senior_forecaster import SeniorForecaster


@pytest.mark.parametrize("specialist_class,specialist_name", [
    (BuoyAnalyst, "BuoyAnalyst"),
    (PressureAnalyst, "PressureAnalyst"),
    (SeniorForecaster, "SeniorForecaster"),
])
def test_specialist_requires_engine(specialist_class, specialist_name):
    """Test that specialist raises ValueError when engine=None."""
    with pytest.raises(ValueError, match="requires engine parameter for API access"):
        # Attempt to instantiate without engine
        specialist = specialist_class(config=None, model_name="gpt-4o-mini", engine=None)
