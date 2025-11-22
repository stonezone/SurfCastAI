#!/usr/bin/env python3
"""
Unit tests for quality flag filtering in ForecastEngine.

Tests that excluded data (quality_flag == "excluded") is properly
filtered out before forecast generation.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.forecast_engine.forecast_engine import ForecastEngine
from src.processing.models.swell_event import (
    ForecastLocation,
    SwellComponent,
    SwellEvent,
    SwellForecast,
)


def create_mock_config():
    """Create a mock config for testing."""
    config = MagicMock()

    def mock_get(*args, **kwargs):
        # Handle both config.get(section, key) and config.get(section, key, default)
        default = args[2] if len(args) > 2 else kwargs.get("default")
        key = args[:2] if len(args) >= 2 else args
        return {
            ("forecast", "templates_dir"): None,
            ("openai", "api_key"): None,
            ("openai", "model"): "gpt-5-nano",
            ("openai", "verbosity"): "high",
            ("openai", "reasoning_effort"): "medium",
            ("openai", "analysis_models"): [],
            ("forecast", "use_local_generator"): True,
            ("forecast", "image_detail_levels"): {},
            ("forecast", "use_specialist_team"): False,
            ("specialists", "buoy"): {},
            ("specialists", "pressure"): {},
        }.get(key, default)

    def mock_getint(*args, **kwargs):
        default = args[2] if len(args) > 2 else kwargs.get("default", 0)
        key = args[:2] if len(args) >= 2 else args
        return {
            ("openai", "max_tokens"): 32768,
            ("forecast", "refinement_cycles"): 0,
            ("forecast", "max_images"): 10,
            ("forecast", "token_budget"): 150000,
            ("forecast", "warn_threshold"): 200000,
        }.get(key, default)

    def mock_getfloat(*args, **kwargs):
        default = args[2] if len(args) > 2 else kwargs.get("default", 0.0)
        key = args[:2] if len(args) >= 2 else args
        return {
            ("openai", "temperature"): 0.7,
            ("forecast", "quality_threshold"): 0.8,
        }.get(key, default)

    def mock_getboolean(*args, **kwargs):
        default = args[2] if len(args) > 2 else kwargs.get("default", False)
        key = args[:2] if len(args) >= 2 else args
        return {
            ("forecast", "use_local_generator"): True,
            ("forecast", "enable_budget_enforcement"): True,
            ("forecast", "use_specialist_team"): False,
        }.get(key, default)

    config.get.side_effect = mock_get
    config.getint.side_effect = mock_getint
    config.getfloat.side_effect = mock_getfloat
    config.getboolean.side_effect = mock_getboolean

    return config


def test_filter_excluded_events():
    """Test that events with quality_flag='excluded' are filtered out."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    # Create test swell events
    valid_event = SwellEvent(
        event_id="event1",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid")
        ],
    )

    excluded_event = SwellEvent(
        event_id="event2",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.2,
        quality_flag="excluded",  # This should be filtered out
        primary_components=[
            SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
        ],
    )

    # Create swell forecast
    swell_forecast = SwellForecast(
        forecast_id="test123",
        generated_time=datetime.now().isoformat(),
        swell_events=[valid_event, excluded_event],
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Verify only valid event is included
    assert len(forecast_data["swell_events"]) == 1
    assert forecast_data["swell_events"][0]["event_id"] == "event1"
    assert forecast_data["swell_events"][0]["primary_direction"] == 315.0


def test_filter_excluded_components():
    """Test that components with quality_flag='excluded' are filtered out."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    # Create event with mixed quality components
    event = SwellEvent(
        event_id="event1",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid"),
            SwellComponent(
                height=1.5, period=15.0, direction=180.0, quality_flag="excluded"
            ),  # Should be filtered
        ],
    )

    swell_forecast = SwellForecast(
        forecast_id="test123", generated_time=datetime.now().isoformat(), swell_events=[event]
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Verify only valid component is included
    assert len(forecast_data["swell_events"]) == 1
    assert len(forecast_data["swell_events"][0]["primary_components"]) == 1
    assert forecast_data["swell_events"][0]["primary_components"][0]["direction"] == 315.0


def test_exclude_event_with_no_valid_components():
    """Test that events with all excluded components are filtered out entirely."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    # Create event where all components are excluded
    event = SwellEvent(
        event_id="event1",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.2,
        quality_flag="valid",  # Event itself is valid
        primary_components=[
            SwellComponent(
                height=1.5, period=15.0, direction=180.0, quality_flag="excluded"
            )  # But component is excluded
        ],
    )

    swell_forecast = SwellForecast(
        forecast_id="test123", generated_time=datetime.now().isoformat(), swell_events=[event]
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Event should be excluded because it has no valid components
    assert len(forecast_data["swell_events"]) == 0


def test_filter_shore_specific_events():
    """Test that shore-specific events are also filtered by quality flag."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    # Create shore location with excluded event
    valid_event = SwellEvent(
        event_id="event1",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid")
        ],
    )

    excluded_event = SwellEvent(
        event_id="event2",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.2,
        quality_flag="excluded",
        primary_components=[
            SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
        ],
    )

    north_shore = ForecastLocation(
        name="North Shore",
        shore="North Shore",
        latitude=21.6,
        longitude=-158.0,
        facing_direction=0.0,
        swell_events=[valid_event, excluded_event],
    )

    swell_forecast = SwellForecast(
        forecast_id="test123", generated_time=datetime.now().isoformat(), locations=[north_shore]
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Verify only valid event appears in shore data
    shore_events = forecast_data["shore_data"]["north_shore"]["swell_events"]
    assert len(shore_events) == 1
    assert shore_events[0]["event_id"] == "event1"


def test_suspect_data_not_filtered():
    """Test that 'suspect' quality flag data is NOT filtered (only 'excluded' is filtered)."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    # Create event with suspect quality
    suspect_event = SwellEvent(
        event_id="event1",
        start_time="2025-10-09T00:00:00Z",
        peak_time="2025-10-09T12:00:00Z",
        primary_direction=180.0,
        significance=0.6,
        hawaii_scale=4.5,
        quality_flag="suspect",  # Suspect data should pass through
        primary_components=[
            SwellComponent(height=1.2, period=12.0, direction=180.0, quality_flag="suspect")
        ],
    )

    swell_forecast = SwellForecast(
        forecast_id="test123",
        generated_time=datetime.now().isoformat(),
        swell_events=[suspect_event],
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Suspect data should NOT be filtered
    assert len(forecast_data["swell_events"]) == 1
    assert forecast_data["swell_events"][0]["event_id"] == "event1"


def test_mixed_quality_scenario():
    """Test realistic scenario with valid, suspect, and excluded data."""
    config = create_mock_config()
    engine = ForecastEngine(config)

    events = [
        SwellEvent(
            event_id="nw_valid",
            start_time="2025-10-09T00:00:00Z",
            peak_time="2025-10-09T12:00:00Z",
            primary_direction=315.0,
            significance=0.8,
            hawaii_scale=6.0,
            quality_flag="valid",
            primary_components=[
                SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid")
            ],
        ),
        SwellEvent(
            event_id="s_excluded",
            start_time="2025-10-09T00:00:00Z",
            peak_time="2025-10-09T12:00:00Z",
            primary_direction=180.0,
            significance=0.5,
            hawaii_scale=5.2,
            quality_flag="excluded",  # Anomalous single-scan spike
            primary_components=[
                SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
            ],
        ),
        SwellEvent(
            event_id="sw_suspect",
            start_time="2025-10-09T00:00:00Z",
            peak_time="2025-10-09T12:00:00Z",
            primary_direction=225.0,
            significance=0.6,
            hawaii_scale=3.5,
            quality_flag="suspect",  # Moderate anomaly
            primary_components=[
                SwellComponent(height=1.0, period=10.0, direction=225.0, quality_flag="suspect")
            ],
        ),
    ]

    swell_forecast = SwellForecast(
        forecast_id="test123", generated_time=datetime.now().isoformat(), swell_events=events
    )

    # Prepare forecast data
    forecast_data = engine.data_manager.prepare_forecast_data(swell_forecast)

    # Should have 2 events: valid + suspect (excluded filtered out)
    assert len(forecast_data["swell_events"]) == 2

    event_ids = [e["event_id"] for e in forecast_data["swell_events"]]
    assert "nw_valid" in event_ids
    assert "sw_suspect" in event_ids
    assert "s_excluded" not in event_ids
