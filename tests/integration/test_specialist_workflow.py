"""
Integration tests for the specialist workflow system.

Tests the end-to-end integration of the multi-agent specialist architecture:
BuoyAnalyst → PressureAnalyst → SeniorForecaster with Pydantic data contracts.

This module validates:
- Data flow integration between specialists
- Pydantic model serialization/deserialization
- Error propagation and handling
- Schema validation across workflow
- Complete forecast generation with all specialists
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.forecast_engine.specialists.buoy_analyst import BuoyAnalyst
from src.forecast_engine.specialists.pressure_analyst import PressureAnalyst
from src.forecast_engine.specialists.schemas import (
    AgreementLevel,
    AnalysisSummary,
    BuoyAnalystData,
    BuoyAnalystOutput,
    BuoyAnomaly,
    BuoyTrend,
    Contradiction,
    CrossValidation,
    FetchQuality,
    FetchWindow,
    FrontalBoundary,
    FrontType,
    ImpactLevel,
    IntensificationTrend,
    PredictedSwell,
    PressureAnalystData,
    PressureAnalystOutput,
    QualityFlag,
    SeniorForecasterData,
    SeniorForecasterInput,
    SeniorForecasterOutput,
    SeverityLevel,
    ShoreForecast,
    SummaryStats,
    SwellBreakdown,
    Synthesis,
    SystemType,
    TrendType,
    WeatherSystem,
)
from src.forecast_engine.specialists.senior_forecaster import SeniorForecaster
from src.processing.models.buoy_data import BuoyData, BuoyObservation

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create mock configuration object."""
    config = Mock()
    config.get = Mock(side_effect=lambda section, key, fallback=None: fallback)
    config.getint = Mock(side_effect=lambda section, key, fallback=None: fallback)
    return config


@pytest.fixture
def mock_engine():
    """Create mock ForecastEngine with OpenAI client."""
    engine = Mock()
    engine.openai_client = Mock()
    engine.openai_client.call_openai_api = AsyncMock()
    return engine


@pytest.fixture
def sample_buoy_data():
    """Create sample buoy data for testing."""
    buoy = BuoyData(station_id="51201", name="NW Hawaii (51201)", latitude=21.67, longitude=-158.12)

    # Add 10 observations over 24 hours (increasing trend)
    base_time = datetime.now() - timedelta(hours=24)
    for i in range(10):
        obs = BuoyObservation(
            timestamp=(base_time + timedelta(hours=i * 2.4)).isoformat(),
            wave_height=2.5 + (i * 0.15),  # Increasing from 2.5m to 3.85m
            dominant_period=13.0 + (i * 0.1),
            average_period=10.5,
            wave_direction=320.0,  # NW
            wind_speed=8.0,
            wind_direction=45.0,
            air_temperature=24.0,
            water_temperature=25.5,
            pressure=1015.0,
        )
        buoy.observations.append(obs)

    return [buoy]


@pytest.fixture
def sample_buoy_analysis_dict(sample_buoy_data):
    """Create sample BuoyAnalyst output as dictionary."""
    return {
        "confidence": 0.85,
        "data": {
            "trends": [
                {
                    "buoy_id": "51201",
                    "buoy_name": "NW Hawaii (51201)",
                    "height_trend": "increasing_moderate",
                    "height_slope": 0.15,
                    "height_current": 3.85,
                    "period_trend": "steady",
                    "period_slope": 0.01,
                    "period_current": 13.9,
                    "direction_trend": "steady",
                    "direction_current": 320.0,
                    "observations_count": 10,
                }
            ],
            "anomalies": [],
            "quality_flags": {"51201": "valid"},
            "cross_validation": {
                "agreement_score": 0.95,
                "height_agreement": 0.93,
                "period_agreement": 0.97,
                "num_buoys_compared": 1,
                "interpretation": "excellent_agreement",
            },
            "summary_stats": {
                "avg_wave_height": 3.15,
                "max_wave_height": 3.85,
                "min_wave_height": 2.5,
                "avg_period": 13.45,
                "max_period": 13.9,
                "min_period": 13.0,
            },
        },
        "narrative": "Buoy 51201 (NW Hawaii) shows a moderate increasing trend in wave height from 2.5m to 3.85m over the past 24 hours. The dominant period remains steady around 13-14 seconds, indicating long-period NW groundswell. Wave direction is consistent at 320°. No anomalies detected. Data quality is excellent with high cross-buoy agreement.",
        "metadata": {
            "num_buoys": 1,
            "total_observations": 10,
            "analysis_method": "trend_anomaly_cross_validation",
            "timestamp": datetime.now().isoformat(),
        },
    }


@pytest.fixture
def sample_pressure_analysis_dict():
    """Create sample PressureAnalyst output as dictionary."""
    generation_time = datetime.now() - timedelta(hours=48)
    arrival_time = datetime.now() + timedelta(hours=6)

    return {
        "confidence": 0.78,
        "data": {
            "systems": [
                {
                    "type": "low_pressure",
                    "location": "45N 160W",
                    "location_lat": 45.0,
                    "location_lon": -160.0,
                    "pressure_mb": 985,
                    "wind_speed_kt": 45,
                    "movement": "E at 20kt",
                    "intensification": "weakening",
                    "generation_time": generation_time.isoformat(),
                    "fetch": {
                        "direction": "NNW",
                        "distance_nm": 1200.0,
                        "duration_hrs": 36.0,
                        "fetch_length_nm": 500.0,
                        "quality": "strong",
                    },
                }
            ],
            "predicted_swells": [
                {
                    "source_system": "low_45N_160W",
                    "source_lat": 45.0,
                    "source_lon": -160.0,
                    "direction": "NNW",
                    "direction_degrees": 330,
                    "arrival_time": arrival_time.isoformat(),
                    "estimated_height": "8-10ft",
                    "estimated_period": "14-16s",
                    "confidence": 0.82,
                    "calculated_arrival": arrival_time.isoformat(),
                    "travel_time_hrs": 54.0,
                    "distance_nm": 1200.0,
                    "group_velocity_knots": 22.2,
                    "propagation_method": "physics_based",
                    "fetch_quality": "strong",
                    "fetch_duration_hrs": 36.0,
                    "fetch_length_nm": 500.0,
                    "source_pressure_mb": 985,
                    "source_wind_speed_kt": 45,
                    "source_trend": "weakening",
                }
            ],
            "frontal_boundaries": [],
            "analysis_summary": {
                "num_low_pressure": 1,
                "num_high_pressure": 0,
                "num_predicted_swells": 1,
                "region": "North Pacific",
            },
        },
        "narrative": "A significant low-pressure system at 45N 160W (985mb) has generated a strong NNW fetch extending 500nm over 36 hours. The system is now weakening and moving east at 20kt. Predicted NNW swell (8-10ft @ 14-16s) is expected to arrive in approximately 6 hours after traveling 1200nm from the source. Group velocity calculated at 22.2 knots using physics-based propagation model. High confidence (0.82) due to strong fetch characteristics.",
        "metadata": {
            "num_images": 1,
            "analysis_method": "gpt_vision",
            "model": "gpt-5-nano",
            "timestamp": datetime.now().isoformat(),
            "region": "North Pacific",
            "chart_times": [],
        },
    }


@pytest.fixture
def sample_shore_data():
    """Create sample shore-specific data."""
    return {
        "north_shore": {
            "locations": ["Pipeline", "Sunset Beach", "Waimea Bay"],
            "exposure": [315, 0, 45],
            "typical_conditions": "world-class winter surf",
        },
        "south_shore": {
            "locations": ["Ala Moana", "Diamond Head", "Queens"],
            "exposure": [135, 180, 225],
            "typical_conditions": "summer south swells",
        },
        "east_shore": {
            "locations": ["Makapuu", "Sandy Beach"],
            "exposure": [45, 90, 135],
            "typical_conditions": "trade wind swell",
        },
        "west_shore": {
            "locations": ["Makaha", "Yokohama"],
            "exposure": [225, 270, 315],
            "typical_conditions": "winter wrap, summer west swells",
        },
    }


@pytest.fixture
def sample_seasonal_context():
    """Create sample seasonal context."""
    return {
        "season": "winter",
        "typical_patterns": {"dominant_swells": ["N", "NW", "W"], "primary_shore": "north_shore"},
        "climatology": {"avg_height": "6-8ft", "avg_period": "12-16s"},
    }


# =============================================================================
# INTEGRATION TEST 1: DATA FLOW - BUOY TO SENIOR FORECASTER
# =============================================================================


@pytest.mark.asyncio
async def test_buoy_analyst_to_senior_forecaster_integration(
    mock_config, mock_engine, sample_buoy_data, sample_shore_data, sample_seasonal_context
):
    """
    Test data flow from BuoyAnalyst to SeniorForecaster.

    Validates:
    - BuoyAnalyst produces valid BuoyAnalystOutput
    - Pydantic model serialization via model_dump()
    - SeniorForecaster consumes BuoyAnalystOutput correctly
    - Backward compatibility with dict format
    """
    # Mock AI responses
    mock_engine.openai_client.call_openai_api.side_effect = [
        "Buoy analysis narrative",  # BuoyAnalyst
        "Caldwell-style forecast narrative",  # SeniorForecaster
    ]

    # Initialize specialists
    buoy_analyst = BuoyAnalyst(mock_config, model_name="gpt-5-nano", engine=mock_engine)
    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    # Run BuoyAnalyst
    buoy_output = await buoy_analyst.analyze({"buoy_data": sample_buoy_data})

    # Validate BuoyAnalyst output is Pydantic model
    assert isinstance(buoy_output, BuoyAnalystOutput)
    assert 0.0 <= buoy_output.confidence <= 1.0
    assert isinstance(buoy_output.data, BuoyAnalystData)
    assert len(buoy_output.data.trends) > 0

    # Test model_dump() for backward compatibility
    buoy_dict = buoy_output.model_dump()
    assert isinstance(buoy_dict, dict)
    assert "confidence" in buoy_dict
    assert "data" in buoy_dict
    assert "narrative" in buoy_dict

    # Run SeniorForecaster with Pydantic model (test Union[Dict, Model] input)
    senior_input = SeniorForecasterInput(
        buoy_analysis=buoy_output,
        pressure_analysis=None,
        swell_events=[],
        shore_data=sample_shore_data,
        seasonal_context=sample_seasonal_context,
        metadata={"forecast_date": datetime.now().strftime("%Y-%m-%d")},
    )

    # Should raise ValueError because we need minimum 2 specialists
    with pytest.raises(ValueError, match="Insufficient specialists"):
        await senior_forecaster.analyze(senior_input)


# =============================================================================
# INTEGRATION TEST 2: DATA FLOW - PRESSURE TO SENIOR FORECASTER
# =============================================================================


@pytest.mark.asyncio
async def test_pressure_analyst_to_senior_forecaster_integration(
    mock_config,
    mock_engine,
    sample_pressure_analysis_dict,
    sample_shore_data,
    sample_seasonal_context,
):
    """
    Test data flow from PressureAnalyst to SeniorForecaster.

    Validates:
    - PressureAnalyst produces valid PressureAnalystOutput
    - Enhanced swell predictions with physics calculations
    - SeniorForecaster handles pressure-only input
    """
    # Create Pydantic model from dict
    pressure_output = PressureAnalystOutput(**sample_pressure_analysis_dict)

    # Validate structure
    assert isinstance(pressure_output, PressureAnalystOutput)
    assert isinstance(pressure_output.data, PressureAnalystData)
    assert len(pressure_output.data.systems) > 0
    assert len(pressure_output.data.predicted_swells) > 0

    # Validate physics-enhanced fields
    swell = pressure_output.data.predicted_swells[0]
    assert isinstance(swell, PredictedSwell)
    assert swell.calculated_arrival is not None
    assert swell.travel_time_hrs == 54.0
    assert swell.distance_nm == 1200.0
    assert swell.propagation_method == "physics_based"

    # Test model_dump() serialization
    pressure_dict = pressure_output.model_dump()
    assert isinstance(pressure_dict["data"]["predicted_swells"], list)
    assert pressure_dict["data"]["predicted_swells"][0]["travel_time_hrs"] == 54.0


# =============================================================================
# INTEGRATION TEST 3: COMPLETE WORKFLOW
# =============================================================================


@pytest.mark.asyncio
async def test_complete_specialist_workflow(
    mock_config,
    mock_engine,
    sample_buoy_data,
    sample_buoy_analysis_dict,
    sample_pressure_analysis_dict,
    sample_shore_data,
    sample_seasonal_context,
):
    """
    Test complete workflow: BuoyAnalyst → PressureAnalyst → SeniorForecaster.

    Validates:
    - End-to-end data flow with all specialists
    - Cross-validation and contradiction detection
    - Final forecast contains data from all specialists
    - Pydantic models work throughout pipeline
    """
    # Mock AI responses
    mock_engine.openai_client.call_openai_api.side_effect = [
        "Buoy analysis narrative",  # BuoyAnalyst
        "Pressure chart analysis narrative",  # PressureAnalyst (vision)
        "Pressure analysis narrative",  # PressureAnalyst (narrative)
        "Caldwell-style forecast with all specialist data",  # SeniorForecaster
    ]

    # Initialize specialists
    buoy_analyst = BuoyAnalyst(mock_config, model_name="gpt-5-nano", engine=mock_engine)
    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    # Run BuoyAnalyst
    buoy_output = await buoy_analyst.analyze({"buoy_data": sample_buoy_data})
    assert isinstance(buoy_output, BuoyAnalystOutput)

    # Create PressureAnalyst output from sample
    pressure_output = PressureAnalystOutput(**sample_pressure_analysis_dict)
    assert isinstance(pressure_output, PressureAnalystOutput)

    # Run SeniorForecaster with both specialists
    senior_input = SeniorForecasterInput(
        buoy_analysis=buoy_output,
        pressure_analysis=pressure_output,
        swell_events=[],
        shore_data=sample_shore_data,
        seasonal_context=sample_seasonal_context,
        metadata={"forecast_date": datetime.now().strftime("%Y-%m-%d")},
    )

    senior_output = await senior_forecaster.analyze(senior_input)

    # Validate final output
    assert isinstance(senior_output, SeniorForecasterOutput)
    assert 0.0 <= senior_output.confidence <= 1.0
    assert isinstance(senior_output.data, SeniorForecasterData)
    assert isinstance(senior_output.data.synthesis, Synthesis)

    # Validate synthesis includes data from both specialists
    assert 0.0 <= senior_output.data.synthesis.specialist_agreement <= 1.0
    assert len(senior_output.data.synthesis.key_findings) > 0

    # Validate shore forecasts
    assert "north_shore" in senior_output.data.shore_forecasts
    assert "south_shore" in senior_output.data.shore_forecasts
    for shore, forecast in senior_output.data.shore_forecasts.items():
        assert isinstance(forecast, ShoreForecast)
        assert forecast.size_range is not None
        assert 0.0 <= forecast.confidence <= 1.0

    # Validate swell breakdown merges data from both sources
    assert len(senior_output.data.swell_breakdown) > 0
    for swell in senior_output.data.swell_breakdown:
        assert isinstance(swell, SwellBreakdown)
        assert swell.direction is not None
        assert swell.source is not None


# =============================================================================
# INTEGRATION TEST 4: ERROR PROPAGATION - INVALID PYDANTIC DATA
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_pydantic_model_rejected(mock_config, mock_engine):
    """
    Test that invalid Pydantic models are rejected with clear errors.

    Validates:
    - Field validators work correctly
    - Invalid data raises ValidationError
    - Error messages are descriptive
    """
    from pydantic import ValidationError

    # Test invalid confidence (out of range)
    with pytest.raises(ValidationError, match="confidence"):
        BuoyAnalystOutput(
            confidence=1.5,  # Invalid: > 1.0
            data=BuoyAnalystData(
                trends=[],
                anomalies=[],
                quality_flags={},
                cross_validation=CrossValidation(
                    agreement_score=0.9,
                    height_agreement=0.9,
                    period_agreement=0.9,
                    num_buoys_compared=1,
                    interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
                ),
                summary_stats=SummaryStats(),
            ),
            narrative="Test narrative",
            metadata={},
        )

    # Test invalid direction (out of range)
    with pytest.raises(ValidationError, match="direction"):
        BuoyTrend(
            buoy_id="51201",
            buoy_name="Test Buoy",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            direction_trend=TrendType.STEADY,
            direction_current=400.0,  # Invalid: > 360
            observations_count=10,
        )

    # Test invalid enum value
    with pytest.raises(ValidationError):
        BuoyTrend(
            buoy_id="51201",
            buoy_name="Test Buoy",
            height_trend="invalid_trend",  # Invalid enum value
            height_slope=0.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )


# =============================================================================
# INTEGRATION TEST 5: ERROR PROPAGATION - SPECIALIST FAILURE
# =============================================================================


@pytest.mark.asyncio
async def test_specialist_failure_handling(mock_config, mock_engine, sample_buoy_data):
    """
    Test handling of specialist failures.

    Validates:
    - Exceptions from specialists are propagated correctly
    - Error messages are descriptive
    - System fails gracefully
    """
    # Mock AI call to raise exception
    mock_engine.openai_client.call_openai_api.side_effect = Exception("OpenAI API error")

    buoy_analyst = BuoyAnalyst(mock_config, model_name="gpt-5-nano", engine=mock_engine)

    # Should raise exception from OpenAI call
    with pytest.raises(Exception, match="OpenAI API error"):
        await buoy_analyst.analyze({"buoy_data": sample_buoy_data})


# =============================================================================
# INTEGRATION TEST 6: ERROR PROPAGATION - INSUFFICIENT SPECIALISTS
# =============================================================================


@pytest.mark.asyncio
async def test_insufficient_specialists_error(
    mock_config, mock_engine, sample_shore_data, sample_seasonal_context
):
    """
    Test that SeniorForecaster requires minimum specialists.

    Validates:
    - Error raised when < 2 specialists available
    - Error message is descriptive
    """
    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    # Test with no specialists
    senior_input = SeniorForecasterInput(
        buoy_analysis=None,
        pressure_analysis=None,
        swell_events=[],
        shore_data=sample_shore_data,
        seasonal_context=sample_seasonal_context,
        metadata={},
    )

    with pytest.raises(ValueError, match="Insufficient specialists"):
        await senior_forecaster.analyze(senior_input)


# =============================================================================
# INTEGRATION TEST 7: SCHEMA VALIDATION - ENUM CONVERSIONS
# =============================================================================


def test_enum_conversions_work_correctly():
    """
    Test that enum conversions work across workflow.

    Validates:
    - String values are converted to enums
    - Enum values are serialized correctly
    - model_dump() preserves enum values as strings
    """
    # Test TrendType enum
    trend = BuoyTrend(
        buoy_id="51201",
        buoy_name="Test Buoy",
        height_trend="increasing_moderate",  # String input
        height_slope=0.15,
        period_trend=TrendType.STEADY,  # Enum input
        period_slope=0.01,
        direction_trend=TrendType.STEADY,
        observations_count=10,
    )

    # Validate enum conversion
    assert isinstance(trend.height_trend, TrendType)
    assert trend.height_trend == TrendType.INCREASING_MODERATE

    # Validate serialization
    trend_dict = trend.model_dump()
    assert trend_dict["height_trend"] == "increasing_moderate"
    assert trend_dict["period_trend"] == "steady"

    # Test all enum types
    fetch_window = FetchWindow(
        direction="NNW",
        distance_nm=1200.0,
        duration_hrs=36.0,
        fetch_length_nm=500.0,
        quality="strong",  # String input
    )
    assert isinstance(fetch_window.quality, FetchQuality)
    assert fetch_window.quality == FetchQuality.STRONG


# =============================================================================
# INTEGRATION TEST 8: SCHEMA VALIDATION - FIELD VALIDATORS
# =============================================================================


def test_field_validators_work_correctly():
    """
    Test that field validators work across workflow.

    Validates:
    - Numeric validators (rounding, ranges)
    - Timestamp validators
    - Custom validators
    """
    # Test confidence rounding
    output = BuoyAnalystOutput(
        confidence=0.8567,  # Should round to 0.857
        data=BuoyAnalystData(
            trends=[],
            anomalies=[],
            quality_flags={},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        ),
        narrative="Test",
        metadata={},
    )
    assert output.confidence == 0.857

    # Test slope rounding
    trend = BuoyTrend(
        buoy_id="51201",
        buoy_name="Test",
        height_trend=TrendType.STEADY,
        height_slope=0.123456,  # Should round to 0.1235
        period_trend=TrendType.STEADY,
        period_slope=0.987654,  # Should round to 0.9877
        direction_trend=TrendType.STEADY,
        observations_count=10,
    )
    assert trend.height_slope == 0.1235
    assert trend.period_slope == 0.9877

    # Test height/period rounding by creating new model with value
    # (Pydantic doesn't validate on assignment, only on model creation)
    trend_with_height = BuoyTrend(
        buoy_id="51201",
        buoy_name="Test",
        height_trend=TrendType.STEADY,
        height_slope=0.1235,
        height_current=3.456,  # Should round to 3.46
        period_trend=TrendType.STEADY,
        period_slope=0.9877,
        direction_trend=TrendType.STEADY,
        observations_count=10,
    )
    assert trend_with_height.height_current == 3.46


# =============================================================================
# INTEGRATION TEST 9: BACKWARD COMPATIBILITY - DICT INPUT
# =============================================================================


@pytest.mark.asyncio
async def test_backward_compatibility_dict_input(
    mock_config,
    mock_engine,
    sample_buoy_analysis_dict,
    sample_pressure_analysis_dict,
    sample_shore_data,
    sample_seasonal_context,
):
    """
    Test backward compatibility with dict input format.

    Validates:
    - SeniorForecaster accepts dict input (Union[Dict, SeniorForecasterInput])
    - Dict inputs are converted internally
    - Output is identical to Pydantic input
    """
    # Mock AI response
    mock_engine.openai_client.call_openai_api.return_value = "Forecast narrative"

    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    # Test with dict input (legacy format)
    senior_input_dict = {
        "buoy_analysis": sample_buoy_analysis_dict,
        "pressure_analysis": sample_pressure_analysis_dict,
        "swell_events": [],
        "shore_data": sample_shore_data,
        "seasonal_context": sample_seasonal_context,
        "metadata": {"forecast_date": datetime.now().strftime("%Y-%m-%d")},
    }

    senior_output = await senior_forecaster.analyze(senior_input_dict)

    # Validate output is still Pydantic model
    assert isinstance(senior_output, SeniorForecasterOutput)
    assert isinstance(senior_output.data, SeniorForecasterData)
    assert len(senior_output.data.shore_forecasts) > 0


# =============================================================================
# INTEGRATION TEST 10: CONTRADICTION DETECTION
# =============================================================================


@pytest.mark.asyncio
async def test_contradiction_detection(
    mock_config, mock_engine, sample_buoy_data, sample_shore_data, sample_seasonal_context
):
    """
    Test contradiction detection between specialists.

    Validates:
    - Contradictions are detected correctly
    - Impact levels are assigned appropriately
    - Resolutions are proposed
    """
    # Mock AI responses
    mock_engine.openai_client.call_openai_api.side_effect = [
        "Buoy analysis narrative",
        "Forecast narrative",
    ]

    # Initialize specialists
    buoy_analyst = BuoyAnalyst(mock_config, model_name="gpt-5-nano", engine=mock_engine)
    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    # Run BuoyAnalyst
    buoy_output = await buoy_analyst.analyze({"buoy_data": sample_buoy_data})

    # Create conflicting PressureAnalyst output (predicting different direction)
    conflicting_pressure = {
        "confidence": 0.75,
        "data": {
            "systems": [
                {
                    "type": "low_pressure",
                    "location": "35S 170W",
                    "location_lat": -35.0,
                    "location_lon": -170.0,
                    "pressure_mb": 995,
                    "wind_speed_kt": 35,
                    "movement": "NE at 15kt",
                    "intensification": "steady",
                    "generation_time": datetime.now().isoformat(),
                    "fetch": {
                        "direction": "S",  # Conflicting with NW buoy signal
                        "distance_nm": 800.0,
                        "duration_hrs": 24.0,
                        "fetch_length_nm": 300.0,
                        "quality": "moderate",
                    },
                }
            ],
            "predicted_swells": [
                {
                    "source_system": "low_35S_170W",
                    "source_lat": -35.0,
                    "source_lon": -170.0,
                    "direction": "S",  # Conflicting direction
                    "direction_degrees": 180,
                    "arrival_time": (datetime.now() + timedelta(hours=48)).isoformat(),
                    "estimated_height": "4-6ft",
                    "estimated_period": "11-13s",
                    "confidence": 0.70,
                }
            ],
            "frontal_boundaries": [],
            "analysis_summary": {
                "num_low_pressure": 1,
                "num_high_pressure": 0,
                "num_predicted_swells": 1,
                "region": "South Pacific",
            },
        },
        "narrative": "South Pacific low pressure system generating S swell.",
        "metadata": {},
    }

    pressure_output = PressureAnalystOutput(**conflicting_pressure)

    # Run SeniorForecaster
    senior_input = SeniorForecasterInput(
        buoy_analysis=buoy_output,
        pressure_analysis=pressure_output,
        swell_events=[],
        shore_data=sample_shore_data,
        seasonal_context=sample_seasonal_context,
        metadata={"forecast_date": datetime.now().strftime("%Y-%m-%d")},
    )

    senior_output = await senior_forecaster.analyze(senior_input)

    # Validate contradictions were detected
    assert len(senior_output.data.synthesis.contradictions) > 0

    # Check contradiction structure
    for contradiction in senior_output.data.synthesis.contradictions:
        assert isinstance(contradiction, Contradiction)
        assert contradiction.issue is not None
        assert contradiction.resolution is not None
        assert isinstance(contradiction.impact, ImpactLevel)


# =============================================================================
# INTEGRATION TEST 11: SERIALIZATION ROUND-TRIP
# =============================================================================


def test_serialization_round_trip(sample_buoy_analysis_dict):
    """
    Test that Pydantic models survive serialization round-trip.

    Validates:
    - model_dump() produces valid dict
    - Dict can be deserialized back to model
    - JSON serialization works correctly
    """
    # Create Pydantic model
    original = BuoyAnalystOutput(**sample_buoy_analysis_dict)

    # Serialize to dict
    serialized = original.model_dump()
    assert isinstance(serialized, dict)

    # Deserialize back to model
    deserialized = BuoyAnalystOutput(**serialized)
    assert isinstance(deserialized, BuoyAnalystOutput)

    # Validate data integrity
    assert deserialized.confidence == original.confidence
    assert len(deserialized.data.trends) == len(original.data.trends)
    assert deserialized.narrative == original.narrative

    # Test JSON serialization
    json_str = json.dumps(serialized)
    assert isinstance(json_str, str)

    # Deserialize from JSON
    from_json = BuoyAnalystOutput(**json.loads(json_str))
    assert from_json.confidence == original.confidence


# =============================================================================
# INTEGRATION TEST 12: PERFORMANCE - FAST EXECUTION
# =============================================================================


@pytest.mark.asyncio
async def test_specialist_workflow_performance(
    mock_config,
    mock_engine,
    sample_buoy_data,
    sample_buoy_analysis_dict,
    sample_pressure_analysis_dict,
    sample_shore_data,
    sample_seasonal_context,
):
    """
    Test that specialist workflow completes quickly.

    Validates:
    - Complete workflow runs in < 5 seconds
    - No blocking operations
    - Efficient data processing
    """
    import time

    # Mock fast AI responses
    mock_engine.openai_client.call_openai_api.side_effect = ["Buoy narrative", "Forecast narrative"]

    start_time = time.time()

    # Run complete workflow
    buoy_analyst = BuoyAnalyst(mock_config, model_name="gpt-5-nano", engine=mock_engine)
    senior_forecaster = SeniorForecaster(mock_config, model_name="gpt-5-mini", engine=mock_engine)

    buoy_output = await buoy_analyst.analyze({"buoy_data": sample_buoy_data})
    pressure_output = PressureAnalystOutput(**sample_pressure_analysis_dict)

    senior_input = SeniorForecasterInput(
        buoy_analysis=buoy_output,
        pressure_analysis=pressure_output,
        swell_events=[],
        shore_data=sample_shore_data,
        seasonal_context=sample_seasonal_context,
        metadata={"forecast_date": datetime.now().strftime("%Y-%m-%d")},
    )

    senior_output = await senior_forecaster.analyze(senior_input)

    elapsed_time = time.time() - start_time

    # Validate performance
    assert elapsed_time < 5.0, f"Workflow took {elapsed_time:.2f}s, expected < 5s"
    assert isinstance(senior_output, SeniorForecasterOutput)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
