#!/usr/bin/env python3
"""
Unit tests for ForecastDataManager class.

Tests all data preparation, quality filtering, image collection, and token estimation
functionalities of the data manager extracted from ForecastEngine.

Following TDD best practices with comprehensive coverage of all public methods
and error handling scenarios.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from src.forecast_engine.data_manager import ForecastDataManager
from src.processing.models.swell_event import (
    ForecastLocation,
    SwellComponent,
    SwellEvent,
    SwellForecast,
)

# ==================== Fixtures ====================


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def data_manager(mock_logger):
    """Create a ForecastDataManager instance with default config."""
    return ForecastDataManager(
        max_images=10,
        image_detail_pressure="high",
        image_detail_wave="auto",
        image_detail_satellite="auto",
        image_detail_sst="low",
        logger=mock_logger,
    )


@pytest.fixture
def sample_swell_component():
    """Create a sample swell component for testing."""
    return SwellComponent(
        height=2.5,
        period=14.0,
        direction=315.0,
        confidence=0.8,
        source="buoy",
        quality_flag="valid",
    )


@pytest.fixture
def sample_swell_event(sample_swell_component):
    """Create a sample swell event for testing."""
    return SwellEvent(
        event_id="test_event_1",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        end_time="2025-10-12T18:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        source="model",
        quality_flag="valid",
        primary_components=[sample_swell_component],
        metadata={"source_details": {"buoy_id": "51201"}},
    )


@pytest.fixture
def sample_location(sample_swell_event):
    """Create a sample forecast location for testing."""
    return ForecastLocation(
        name="North Shore",
        shore="North Shore",
        latitude=21.6,
        longitude=-158.0,
        facing_direction=0.0,
        swell_events=[sample_swell_event],
        metadata={"popular_breaks": ["Pipeline", "Sunset"]},
    )


@pytest.fixture
def sample_swell_forecast(sample_swell_event, sample_location):
    """Create a sample swell forecast for testing."""
    return SwellForecast(
        forecast_id="test_forecast_123",
        generated_time=datetime.now().isoformat(),
        swell_events=[sample_swell_event],
        locations=[sample_location],
        metadata={
            "bundle_id": "test_bundle_123",
            "confidence": {"overall_score": 0.85, "category": "High"},
            "agent_results": {
                "buoy": {"total": 5, "successful": 5},
                "weather": {"total": 1, "successful": 1},
            },
        },
    )


@pytest.fixture
def sample_images_dict():
    """Create sample images dictionary for testing."""
    return {
        "pressure_charts": [
            "data/test_bundle/charts/pressure_0hr.png",
            "data/test_bundle/charts/pressure_24hr.png",
            "data/test_bundle/charts/pressure_48hr.png",
            "data/test_bundle/charts/pressure_96hr.png",
        ],
        "wave_models": [
            "data/test_bundle/models/wave_0hr.png",
            "data/test_bundle/models/wave_24hr.png",
            "data/test_bundle/models/wave_48hr.png",
        ],
        "satellite": ["data/test_bundle/satellite/satellite/latest.png"],
        "sst_charts": ["data/test_bundle/charts/sst_anomaly.png"],
    }


@pytest.fixture
def sample_fused_data():
    """Create sample fused data for filter_quality_data testing."""
    return {
        "buoy_observations": [
            {"buoy_id": "51201", "significant_wave_height": 2.5, "quality_flag": "valid"},
            {
                "buoy_id": "51202",
                "significant_wave_height": 50.0,
                "quality_flag": "excluded",  # Anomalous
            },
            {"buoy_id": "51207", "significant_wave_height": 3.1, "quality_flag": "suspect"},
        ],
        "swell_events": [
            {
                "event_id": "event1",
                "quality_flag": "valid",
                "primary_components": [{"height": 2.0, "period": 14.0, "quality_flag": "valid"}],
                "secondary_components": [],
            },
            {
                "event_id": "event2",
                "quality_flag": "excluded",
                "primary_components": [{"height": 1.5, "period": 15.0, "quality_flag": "excluded"}],
                "secondary_components": [],
            },
            {
                "event_id": "event3",
                "quality_flag": "valid",
                "primary_components": [
                    {"height": 1.8, "period": 12.0, "quality_flag": "valid"},
                    {"height": 25.0, "period": 8.0, "quality_flag": "excluded"},
                ],
                "secondary_components": [
                    {"height": 1.0, "period": 10.0, "quality_flag": "suspect"}
                ],
            },
        ],
    }


# ==================== Initialization Tests ====================


def test_init_default_values():
    """Test ForecastDataManager initialization with default values."""
    # Arrange & Act
    manager = ForecastDataManager()

    # Assert
    assert manager.max_images == 10, "Default max_images should be 10"
    assert manager.image_detail_pressure == "high", "Default pressure detail should be 'high'"
    assert manager.image_detail_wave == "auto", "Default wave detail should be 'auto'"
    assert manager.image_detail_satellite == "auto", "Default satellite detail should be 'auto'"
    assert manager.image_detail_sst == "low", "Default SST detail should be 'low'"
    assert manager.logger is not None, "Logger should be created if not provided"


def test_init_custom_values(mock_logger):
    """Test ForecastDataManager initialization with custom configuration."""
    # Arrange & Act
    manager = ForecastDataManager(
        max_images=5,
        image_detail_pressure="low",
        image_detail_wave="high",
        image_detail_satellite="low",
        image_detail_sst="auto",
        logger=mock_logger,
    )

    # Assert
    assert manager.max_images == 5, "Custom max_images should be set"
    assert manager.image_detail_pressure == "low", "Custom pressure detail should be set"
    assert manager.image_detail_wave == "high", "Custom wave detail should be set"
    assert manager.image_detail_satellite == "low", "Custom satellite detail should be set"
    assert manager.image_detail_sst == "auto", "Custom SST detail should be set"
    assert manager.logger == mock_logger, "Custom logger should be set"


def test_init_logs_configuration(mock_logger):
    """Test that initialization logs configuration details."""
    # Arrange & Act
    ForecastDataManager(max_images=8, image_detail_pressure="high", logger=mock_logger)

    # Assert
    assert mock_logger.info.call_count >= 2, "Should log configuration"
    log_calls = [str(call) for call in mock_logger.info.call_args_list]
    assert any("max_images=8" in str(call) for call in log_calls), "Should log max_images"
    assert any("pressure=high" in str(call) for call in log_calls), "Should log detail levels"


# ==================== prepare_forecast_data Tests ====================


def test_prepare_forecast_data_basic(data_manager, sample_swell_forecast):
    """Test basic prepare_forecast_data functionality with valid data."""
    # Arrange
    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {
            "data_digest": "Test digest",
            "shore_digests": {"north_shore": "North shore digest"},
        }

        # Act
        result = data_manager.prepare_forecast_data(sample_swell_forecast)

    # Assert
    assert result is not None, "Should return prepared data"
    assert result["forecast_id"] == "test_forecast_123", "Should preserve forecast_id"
    assert result["region"] == "Oahu", "Should set region to Oahu"
    assert "start_date" in result, "Should include start_date"
    assert "end_date" in result, "Should include end_date"
    assert len(result["swell_events"]) == 1, "Should include swell events"
    assert "confidence" in result, "Should include confidence data"
    assert result["data_digest"] == "Test digest", "Should include context digest"


def test_prepare_forecast_data_filters_excluded_events(data_manager, mock_logger):
    """Test that excluded swell events are filtered out."""
    # Arrange
    valid_event = SwellEvent(
        event_id="valid_1",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid")
        ],
    )

    excluded_event = SwellEvent(
        event_id="excluded_1",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.0,
        quality_flag="excluded",  # Should be filtered
        primary_components=[
            SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
        ],
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        swell_events=[valid_event, excluded_event],
        metadata={},
    )

    data_manager.logger = mock_logger

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert len(result["swell_events"]) == 1, "Should filter excluded event"
    assert result["swell_events"][0]["event_id"] == "valid_1", "Should keep valid event"
    assert mock_logger.warning.called, "Should log exclusion warning"


def test_prepare_forecast_data_filters_excluded_components(data_manager, mock_logger):
    """Test that excluded components within valid events are filtered."""
    # Arrange
    event = SwellEvent(
        event_id="mixed_event",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid"),
            SwellComponent(height=1.5, period=15.0, direction=320.0, quality_flag="excluded"),
        ],
        secondary_components=[
            SwellComponent(height=1.0, period=10.0, direction=310.0, quality_flag="excluded")
        ],
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        swell_events=[event],
        metadata={},
    )

    data_manager.logger = mock_logger

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert len(result["swell_events"]) == 1, "Should keep event"
    assert (
        len(result["swell_events"][0]["primary_components"]) == 1
    ), "Should filter excluded primary component"
    assert (
        result["swell_events"][0]["primary_components"][0]["direction"] == 315.0
    ), "Should keep valid component"


def test_prepare_forecast_data_excludes_event_with_no_valid_components(data_manager, mock_logger):
    """Test that events with all excluded components are removed entirely."""
    # Arrange
    event = SwellEvent(
        event_id="all_excluded",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.0,
        quality_flag="valid",  # Event is valid but all components excluded
        primary_components=[
            SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
        ],
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        swell_events=[event],
        metadata={},
    )

    data_manager.logger = mock_logger

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert len(result["swell_events"]) == 0, "Should exclude event with no valid components"
    assert mock_logger.warning.called, "Should log exclusion"


def test_prepare_forecast_data_preserves_suspect_data(data_manager):
    """Test that 'suspect' quality flag data is NOT filtered (only 'excluded')."""
    # Arrange
    suspect_event = SwellEvent(
        event_id="suspect_1",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=180.0,
        significance=0.6,
        hawaii_scale=4.5,
        quality_flag="suspect",  # Should NOT be filtered
        primary_components=[
            SwellComponent(height=1.2, period=12.0, direction=180.0, quality_flag="suspect")
        ],
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        swell_events=[suspect_event],
        metadata={},
    )

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert len(result["swell_events"]) == 1, "Should preserve suspect data"
    assert result["swell_events"][0]["event_id"] == "suspect_1", "Should keep suspect event"


def test_prepare_forecast_data_shore_filtering(data_manager):
    """Test that shore-specific events are also filtered by quality."""
    # Arrange
    valid_shore_event = SwellEvent(
        event_id="shore_valid",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=315.0,
        significance=0.8,
        hawaii_scale=6.0,
        quality_flag="valid",
        primary_components=[
            SwellComponent(height=2.0, period=14.0, direction=315.0, quality_flag="valid")
        ],
        metadata={"exposure_north_shore": 0.9},
    )

    excluded_shore_event = SwellEvent(
        event_id="shore_excluded",
        start_time="2025-10-12T00:00:00Z",
        peak_time="2025-10-12T12:00:00Z",
        primary_direction=180.0,
        significance=0.5,
        hawaii_scale=5.0,
        quality_flag="excluded",
        primary_components=[
            SwellComponent(height=1.5, period=15.0, direction=180.0, quality_flag="excluded")
        ],
    )

    location = ForecastLocation(
        name="North Shore",
        shore="North Shore",
        latitude=21.6,
        longitude=-158.0,
        facing_direction=0.0,
        swell_events=[valid_shore_event, excluded_shore_event],
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        locations=[location],
        metadata={},
    )

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert "north_shore" in result["shore_data"], "Should have north shore data"
    shore_events = result["shore_data"]["north_shore"]["swell_events"]
    assert len(shore_events) == 1, "Should filter excluded shore event"
    assert shore_events[0]["event_id"] == "shore_valid", "Should keep valid shore event"


def test_prepare_forecast_data_determines_primary_shores(data_manager, sample_swell_event):
    """Test that primary shores are determined based on activity."""
    # Arrange
    north_location = ForecastLocation(
        name="North Shore",
        shore="North Shore",
        latitude=21.6,
        longitude=-158.0,
        facing_direction=0.0,
        swell_events=[sample_swell_event],
    )

    south_location = ForecastLocation(
        name="South Shore",
        shore="South Shore",
        latitude=21.3,
        longitude=-157.8,
        facing_direction=180.0,
        swell_events=[],  # No events
    )

    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        locations=[north_location, south_location],
        metadata={},
    )

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert result["shores"] == ["North Shore"], "Should only include active shores"


def test_prepare_forecast_data_date_range(data_manager, sample_swell_forecast):
    """Test that date range is calculated correctly (today + 2 days)."""
    # Arrange
    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(sample_swell_forecast)

    # Assert
    start_date = datetime.strptime(result["start_date"], "%Y-%m-%d")
    end_date = datetime.strptime(result["end_date"], "%Y-%m-%d")

    assert (end_date - start_date).days == 2, "Forecast should span 2 days"
    assert start_date.date() == datetime.now().date(), "Start date should be today"


def test_prepare_forecast_data_with_missing_metadata(data_manager):
    """Test prepare_forecast_data handles missing metadata gracefully."""
    # Arrange
    forecast = SwellForecast(
        forecast_id="test",
        generated_time=datetime.now().isoformat(),
        swell_events=[],
        metadata={},  # No confidence or bundle_id
    )

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(forecast)

    # Assert
    assert result["confidence"] == {}, "Should handle missing confidence"
    assert result["images"] == {}, "Should handle missing bundle_id"


# ==================== filter_quality_data Tests ====================


def test_filter_quality_data_basic(data_manager, sample_fused_data):
    """Test basic quality filtering of fused data."""
    # Arrange & Act
    result = data_manager.filter_quality_data(sample_fused_data)

    # Assert
    assert len(result["buoy_observations"]) == 2, "Should filter 1 excluded buoy observation"
    assert result["buoy_observations"][0]["quality_flag"] == "valid", "Should keep valid"
    assert result["buoy_observations"][1]["quality_flag"] == "suspect", "Should keep suspect"


def test_filter_quality_data_filters_excluded_events(data_manager, sample_fused_data):
    """Test that excluded swell events are filtered from dict data."""
    # Arrange & Act
    result = data_manager.filter_quality_data(sample_fused_data)

    # Assert
    assert len(result["swell_events"]) == 2, "Should filter 1 excluded event"
    event_ids = [e["event_id"] for e in result["swell_events"]]
    assert "event1" in event_ids, "Should keep event1"
    assert "event3" in event_ids, "Should keep event3"
    assert "event2" not in event_ids, "Should exclude event2"


def test_filter_quality_data_filters_excluded_components(data_manager, sample_fused_data):
    """Test that excluded components are filtered from events."""
    # Arrange & Act
    result = data_manager.filter_quality_data(sample_fused_data)

    # Assert
    event3 = next(e for e in result["swell_events"] if e["event_id"] == "event3")
    assert len(event3["primary_components"]) == 1, "Should filter excluded primary component"
    assert event3["primary_components"][0]["height"] == 1.8, "Should keep valid component"
    assert len(event3["secondary_components"]) == 1, "Should keep suspect secondary component"


def test_filter_quality_data_excludes_events_with_no_valid_components(data_manager):
    """Test that events with all excluded components are removed."""
    # Arrange
    fused_data = {
        "swell_events": [
            {
                "event_id": "all_excluded",
                "quality_flag": "valid",
                "primary_components": [{"height": 1.5, "quality_flag": "excluded"}],
                "secondary_components": [{"height": 1.0, "quality_flag": "excluded"}],
            }
        ]
    }

    # Act
    result = data_manager.filter_quality_data(fused_data)

    # Assert
    assert len(result["swell_events"]) == 0, "Should exclude event with no valid components"


def test_filter_quality_data_preserves_original(data_manager, sample_fused_data):
    """Test that filter_quality_data does not modify original data."""
    # Arrange
    original_buoy_count = len(sample_fused_data["buoy_observations"])
    original_event_count = len(sample_fused_data["swell_events"])

    # Act
    result = data_manager.filter_quality_data(sample_fused_data)

    # Assert
    assert (
        len(sample_fused_data["buoy_observations"]) == original_buoy_count
    ), "Original should be unchanged"
    assert (
        len(sample_fused_data["swell_events"]) == original_event_count
    ), "Original should be unchanged"
    assert result is not sample_fused_data, "Should return a copy"


def test_filter_quality_data_logs_filtering(data_manager, sample_fused_data, mock_logger):
    """Test that filtering actions are logged."""
    # Arrange
    data_manager.logger = mock_logger

    # Act
    data_manager.filter_quality_data(sample_fused_data)

    # Assert
    assert mock_logger.info.called, "Should log filtering actions"


def test_filter_quality_data_empty_input(data_manager):
    """Test filter_quality_data handles empty input gracefully."""
    # Arrange
    empty_data = {}

    # Act
    result = data_manager.filter_quality_data(empty_data)

    # Assert
    assert result == {}, "Should handle empty dict"


# ==================== collect_bundle_images Tests ====================


def test_collect_bundle_images_all_types(data_manager):
    """Test collecting images of all types from bundle."""
    # Arrange
    bundle_id = "test_bundle_123"

    chart_metadata = [
        {"status": "success", "file_path": "data/test_bundle_123/charts/pressure_0hr.png"},
        {"status": "success", "file_path": "data/test_bundle_123/charts/pressure_24hr.png"},
        {"status": "success", "file_path": "data/test_bundle_123/charts/sst_anomaly.png"},
    ]

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(chart_metadata))),
        patch("pathlib.Path.glob") as mock_glob,
    ):

        # Mock satellite and wave model images
        mock_glob.side_effect = [
            [Path("data/test_bundle_123/satellite/satellite/sat1.png")],
            [],  # No jpg satellite
            [Path("data/test_bundle_123/models/wave1.png")],
            [],  # No jpg wave models
        ]

        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert len(result["pressure_charts"]) == 2, "Should collect 2 pressure charts"
    assert len(result["sst_charts"]) == 1, "Should collect 1 SST chart"
    assert len(result["satellite"]) == 1, "Should collect 1 satellite image"
    assert len(result["wave_models"]) == 1, "Should collect 1 wave model image"


def test_collect_bundle_images_separates_sst_from_pressure(data_manager):
    """Test that SST charts are separated from pressure charts."""
    # Arrange
    bundle_id = "test_bundle"

    chart_metadata = [
        {"status": "success", "file_path": "charts/pressure.png"},
        {"status": "success", "file_path": "charts/sea_surface_temp.png"},
        {"status": "success", "file_path": "charts/sst_chart.png"},
    ]

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(chart_metadata))),
        patch("pathlib.Path.glob", return_value=[]),
    ):

        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert len(result["pressure_charts"]) == 1, "Should have 1 pressure chart"
    assert len(result["sst_charts"]) == 2, "Should have 2 SST charts"
    assert "pressure.png" in result["pressure_charts"][0], "Pressure should contain pressure.png"


def test_collect_bundle_images_missing_charts_dir(data_manager, mock_logger):
    """Test handling of missing charts directory."""
    # Arrange
    bundle_id = "test_bundle"
    data_manager.logger = mock_logger

    with patch("pathlib.Path.exists", return_value=False):
        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert result["pressure_charts"] == [], "Should return empty list for pressure charts"
    assert result["sst_charts"] == [], "Should return empty list for SST charts"


def test_collect_bundle_images_invalid_metadata(data_manager, mock_logger):
    """Test handling of invalid metadata.json."""
    # Arrange
    bundle_id = "test_bundle"
    data_manager.logger = mock_logger

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", side_effect=json.JSONDecodeError("Invalid", "", 0)),
    ):

        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert result["pressure_charts"] == [], "Should handle invalid JSON gracefully"
    assert mock_logger.warning.called, "Should log warning"


def test_collect_bundle_images_skips_failed_charts(data_manager):
    """Test that failed chart downloads are skipped."""
    # Arrange
    bundle_id = "test_bundle"

    chart_metadata = [
        {"status": "success", "file_path": "charts/pressure.png"},
        {"status": "failed", "file_path": "charts/missing.png"},  # Should skip
        {"status": "success", "file_path": None},  # Should skip (no path)
    ]

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=json.dumps(chart_metadata))),
        patch("pathlib.Path.glob", return_value=[]),
    ):

        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert len(result["pressure_charts"]) == 1, "Should only include successful charts with paths"


def test_collect_bundle_images_logs_summary(data_manager, mock_logger):
    """Test that image collection is logged."""
    # Arrange
    bundle_id = "test_bundle"
    data_manager.logger = mock_logger

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data="[]")),
        patch("pathlib.Path.glob", return_value=[]),
    ):

        # Act
        data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert mock_logger.info.called, "Should log collection summary"


# ==================== select_critical_images Tests ====================


def test_select_critical_images_prioritization(data_manager, sample_images_dict):
    """Test that images are selected in correct priority order."""
    # Arrange & Act
    result = data_manager.select_critical_images(sample_images_dict, max_images=10)

    # Assert
    assert (
        len(result) == 9
    ), "Should select 9 total images (4 pressure + 3 wave + 1 satellite + 1 sst)"

    # Verify priority order
    assert result[0]["type"] == "pressure_chart", "First should be pressure chart"
    assert result[4]["type"] == "wave_model", "After 4 pressure, should be wave models"
    assert result[7]["type"] == "satellite", "After waves, should be satellite"
    assert result[8]["type"] == "sst_chart", "Last should be SST"


def test_select_critical_images_max_limit_enforcement(data_manager, sample_images_dict):
    """Test that max_images limit is enforced."""
    # Arrange & Act
    result = data_manager.select_critical_images(sample_images_dict, max_images=5)

    # Assert
    assert len(result) <= 5, "Should not exceed max_images limit"
    assert all(
        img["type"] == "pressure_chart" for img in result[:4]
    ), "Should prioritize pressure charts"


def test_select_critical_images_detail_levels(data_manager, sample_images_dict):
    """Test that correct detail levels are applied to each image type."""
    # Arrange & Act
    result = data_manager.select_critical_images(sample_images_dict, max_images=10)

    # Assert
    pressure_images = [img for img in result if img["type"] == "pressure_chart"]
    wave_images = [img for img in result if img["type"] == "wave_model"]
    satellite_images = [img for img in result if img["type"] == "satellite"]
    sst_images = [img for img in result if img["type"] == "sst_chart"]

    assert all(img["detail"] == "high" for img in pressure_images), "Pressure should be 'high'"
    assert all(img["detail"] == "auto" for img in wave_images), "Wave should be 'auto'"
    assert all(img["detail"] == "auto" for img in satellite_images), "Satellite should be 'auto'"
    assert all(img["detail"] == "low" for img in sst_images), "SST should be 'low'"


def test_select_critical_images_uses_config_default(data_manager, sample_images_dict):
    """Test that configured max_images is used when not provided."""
    # Arrange
    data_manager.max_images = 3

    # Act
    result = data_manager.select_critical_images(sample_images_dict)  # No max_images arg

    # Assert
    assert len(result) == 3, "Should use configured max_images"


def test_select_critical_images_hard_cap_10(data_manager, sample_images_dict):
    """Test that hard cap of 10 images is enforced."""
    # Arrange & Act
    result = data_manager.select_critical_images(sample_images_dict, max_images=20)

    # Assert
    assert len(result) <= 10, "Should enforce hard cap of 10 images"


def test_select_critical_images_empty_input(data_manager):
    """Test handling of empty images dictionary."""
    # Arrange
    empty_images = {"pressure_charts": [], "satellite": [], "wave_models": [], "sst_charts": []}

    # Act
    result = data_manager.select_critical_images(empty_images)

    # Assert
    assert result == [], "Should return empty list for no images"


def test_select_critical_images_includes_descriptions(data_manager, sample_images_dict):
    """Test that image descriptions are included."""
    # Arrange & Act
    result = data_manager.select_critical_images(sample_images_dict, max_images=10)

    # Assert
    assert all("description" in img for img in result), "All images should have descriptions"
    assert any("T+0hr" in img["description"] for img in result), "Should include timestep info"


# ==================== get_seasonal_context Tests ====================


def test_get_seasonal_context_winter():
    """Test seasonal context for winter months (Nov-Mar)."""
    # Arrange
    manager = ForecastDataManager()

    # Test December (winter)
    with patch("src.forecast_engine.data_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 12, 15)

        # Act
        result = manager.get_seasonal_context()

    # Assert
    assert result["current_season"] == "winter", "December should be winter"
    assert result["month"] == 12, "Should return month 12"
    assert "north_shore" in result["seasonal_patterns"], "Should have north shore patterns"
    assert (
        result["seasonal_patterns"]["north_shore"]["quality"] == "High"
    ), "North Shore should be prime in winter"
    assert (
        result["seasonal_patterns"]["south_shore"]["quality"] == "Low"
    ), "South Shore should be low in winter"


def test_get_seasonal_context_summer():
    """Test seasonal context for summer months (Jun-Aug)."""
    # Arrange
    manager = ForecastDataManager()

    # Test July (summer)
    with patch("src.forecast_engine.data_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 7, 15)

        # Act
        result = manager.get_seasonal_context()

    # Assert
    assert result["current_season"] == "summer", "July should be summer"
    assert (
        result["seasonal_patterns"]["south_shore"]["quality"] == "High"
    ), "South Shore should be prime in summer"
    assert (
        result["seasonal_patterns"]["north_shore"]["quality"] == "Low"
    ), "North Shore should be low in summer"


def test_get_seasonal_context_spring():
    """Test seasonal context for spring months (Apr-May)."""
    # Arrange
    manager = ForecastDataManager()

    # Test April (spring)
    with patch("src.forecast_engine.data_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 4, 15)

        # Act
        result = manager.get_seasonal_context()

    # Assert
    assert result["current_season"] == "spring", "April should be spring"
    assert (
        "transition" in result["seasonal_patterns"]["north_shore"]["typical_conditions"].lower()
    ), "Should indicate transition"


def test_get_seasonal_context_fall():
    """Test seasonal context for fall months (Sep-Oct)."""
    # Arrange
    manager = ForecastDataManager()

    # Test September (fall)
    with patch("src.forecast_engine.data_manager.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 9, 15)

        # Act
        result = manager.get_seasonal_context()

    # Assert
    assert result["current_season"] == "fall", "September should be fall"
    assert (
        "transition" in result["seasonal_patterns"]["north_shore"]["typical_conditions"].lower()
    ), "Should indicate transition"


# ==================== estimate_tokens Tests ====================


def test_estimate_tokens_basic(data_manager):
    """Test basic token estimation with text and images."""
    # Arrange
    forecast_data = {
        "swell_events": [{"event_id": "event1", "hawaii_scale": 6.0, "primary_components": []}],
        "shore_data": {"north_shore": {"swell_events": []}},
        "images": {
            "pressure_charts": ["chart1.png", "chart2.png"],
            "wave_models": ["wave1.png"],
            "satellite": ["sat1.png"],
            "sst_charts": ["sst1.png"],
        },
    }

    # Act
    result = data_manager.estimate_tokens(forecast_data)

    # Assert
    assert result > 0, "Should return positive token count"
    # 2 pressure (high=3000 each) + 1 wave (auto=1500) + 1 sat (auto=1500) + 1 sst (low=500) = 9500
    # Plus base 5000 + text + output 10000 = ~24500+
    assert result > 20000, "Should include all token components"


def test_estimate_tokens_image_detail_high(mock_logger):
    """Test token estimation with high detail images."""
    # Arrange
    manager = ForecastDataManager(
        image_detail_pressure="high", image_detail_wave="high", logger=mock_logger
    )

    forecast_data = {
        "swell_events": [],
        "shore_data": {},
        "images": {
            "pressure_charts": ["chart1.png"],
            "wave_models": ["wave1.png"],
            "satellite": [],
            "sst_charts": [],
        },
    }

    # Act
    result = manager.estimate_tokens(forecast_data)

    # Assert
    # 1 pressure high (3000) + 1 wave high (3000) + base 5000 + output 10000 = 21000
    assert result >= 21000, "High detail should use 3000 tokens per image"


def test_estimate_tokens_image_detail_auto(mock_logger):
    """Test token estimation with auto detail images."""
    # Arrange
    manager = ForecastDataManager(
        image_detail_pressure="auto",
        image_detail_wave="auto",
        image_detail_satellite="auto",
        logger=mock_logger,
    )

    forecast_data = {
        "swell_events": [],
        "shore_data": {},
        "images": {
            "pressure_charts": ["chart1.png"],
            "wave_models": ["wave1.png"],
            "satellite": ["sat1.png"],
            "sst_charts": [],
        },
    }

    # Act
    result = manager.estimate_tokens(forecast_data)

    # Assert
    # 3 images auto (1500 each) = 4500 + base 5000 + output 10000 = 19500
    assert result >= 19500, "Auto detail should use 1500 tokens per image"


def test_estimate_tokens_image_detail_low(mock_logger):
    """Test token estimation with low detail images."""
    # Arrange
    manager = ForecastDataManager(
        image_detail_pressure="low",
        image_detail_wave="low",
        image_detail_satellite="low",
        image_detail_sst="low",
        logger=mock_logger,
    )

    forecast_data = {
        "swell_events": [],
        "shore_data": {},
        "images": {
            "pressure_charts": ["chart1.png"],
            "wave_models": ["wave1.png"],
            "satellite": ["sat1.png"],
            "sst_charts": ["sst1.png"],
        },
    }

    # Act
    result = manager.estimate_tokens(forecast_data)

    # Assert
    # 4 images low (500 each) = 2000 + base 5000 + output 10000 = 17000
    assert result >= 17000, "Low detail should use 500 tokens per image"


def test_estimate_tokens_respects_image_limits(data_manager, mock_logger):
    """Test that token estimation respects 4 image limits per type."""
    # Arrange
    data_manager.logger = mock_logger

    forecast_data = {
        "swell_events": [],
        "shore_data": {},
        "images": {
            "pressure_charts": [
                "p1.png",
                "p2.png",
                "p3.png",
                "p4.png",
                "p5.png",
            ],  # 5 but only 4 counted
            "wave_models": [
                "w1.png",
                "w2.png",
                "w3.png",
                "w4.png",
                "w5.png",
                "w6.png",
            ],  # 6 but only 4 counted
            "satellite": ["sat1.png", "sat2.png"],  # Only 1 counted
            "sst_charts": ["sst1.png", "sst2.png"],  # Only 1 counted
        },
    }

    # Act
    result = data_manager.estimate_tokens(forecast_data)

    # Assert
    # Should count: 4 pressure (high=3000) + 4 wave (auto=1500) + 1 sat (auto=1500) + 1 sst (low=500)
    # = 12000 + 6000 + 1500 + 500 = 20000 + base 5000 + output 10000 = 35000
    assert result >= 35000, "Should respect image count limits"


def test_estimate_tokens_no_images(data_manager):
    """Test token estimation with no images."""
    # Arrange
    forecast_data = {"swell_events": [], "shore_data": {}, "images": {}}

    # Act
    result = data_manager.estimate_tokens(forecast_data)

    # Assert
    # Only base 5000 + output 10000 + minimal text = ~15000
    assert result >= 15000, "Should still estimate tokens for text"
    assert result < 20000, "Should not include image tokens"


def test_estimate_tokens_logs_breakdown(data_manager, mock_logger):
    """Test that token estimation logs breakdown."""
    # Arrange
    data_manager.logger = mock_logger

    forecast_data = {
        "swell_events": [],
        "shore_data": {},
        "images": {"pressure_charts": ["chart1.png"]},
    }

    # Act
    data_manager.estimate_tokens(forecast_data)

    # Assert
    assert mock_logger.info.called, "Should log token breakdown"
    log_call = str(mock_logger.info.call_args_list[-1])
    assert "text" in log_call, "Should mention text tokens"
    assert "images" in log_call, "Should mention image tokens"
    assert "output" in log_call, "Should mention output tokens"


# ==================== Edge Cases & Error Handling ====================


def test_prepare_forecast_data_empty_forecast(data_manager):
    """Test prepare_forecast_data with empty forecast."""
    # Arrange
    empty_forecast = SwellForecast(
        forecast_id="empty",
        generated_time=datetime.now().isoformat(),
        swell_events=[],
        locations=[],
        metadata={},
    )

    with patch("src.forecast_engine.data_manager.build_context") as mock_context:
        mock_context.return_value = {"data_digest": "", "shore_digests": {}}

        # Act
        result = data_manager.prepare_forecast_data(empty_forecast)

    # Assert
    assert result["swell_events"] == [], "Should handle empty swell events"
    assert result["shores"] == [], "Should have no primary shores"


def test_collect_bundle_images_exception_handling(data_manager, mock_logger):
    """Test that exceptions during image collection are handled gracefully."""
    # Arrange
    bundle_id = "test_bundle"
    data_manager.logger = mock_logger

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.glob", side_effect=OSError("Permission denied")),
    ):

        # Act
        result = data_manager.collect_bundle_images(bundle_id)

    # Assert
    assert result["satellite"] == [], "Should handle exception gracefully"
    assert mock_logger.warning.called, "Should log warning on exception"
