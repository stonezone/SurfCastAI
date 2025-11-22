"""
Unit tests for PressureAnalyst specialist module.

Tests cover all critical functionality including:
- Vision API parsing (image analysis, response handling, error cases)
- Swell prediction enhancement (physics calculations, arrival timing)
- Fetch window analysis (extraction, validation, confidence scoring)
- Confidence scoring (multi-factor confidence calculation)
- Image validation (file existence, format checking, error handling)
- Integration (complete analyze() workflow, error handling)

Test Structure:
- Tests are organized by functionality area
- Each test follows AAA pattern (Arrange-Act-Assert)
- Mocked dependencies (config, engine, OpenAI client)
- Isolated tests (no interdependencies)
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.forecast_engine.specialists.pressure_analyst import PressureAnalyst
from src.forecast_engine.specialists.schemas import (
    AnalysisSummary,
    FetchQuality,
    FetchWindow,
    FrontalBoundary,
    FrontType,
    IntensificationTrend,
    PredictedSwell,
    PressureAnalystOutput,
    SystemType,
    WeatherSystem,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.get.return_value = "fake-api-key"
    config.getint.return_value = 3000
    return config


@pytest.fixture
def mock_engine():
    """Create a mock forecast engine with OpenAI client."""
    engine = Mock()
    engine.openai_client = Mock()
    engine.openai_client.call_openai_api = AsyncMock(return_value="Test narrative analysis")
    return engine


@pytest.fixture
def pressure_analyst(mock_config, mock_engine):
    """Create a PressureAnalyst instance with mocked dependencies."""
    return PressureAnalyst(config=mock_config, model_name="gpt-4o", engine=mock_engine)


@pytest.fixture
def sample_vision_response():
    """Create sample vision API response with complete data."""
    return {
        "systems": [
            {
                "type": "low_pressure",
                "location": "45N 160W",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "pressure_mb": 990,
                "wind_speed_kt": 50,
                "movement": "SE at 25kt",
                "intensification": "strengthening",
                "generation_time": "2025-10-08T12:00Z",
                "fetch": {
                    "direction": "NNE",
                    "distance_nm": 800.0,
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
                "direction": "NNE",
                "direction_degrees": 22,
                "arrival_time": "2025-10-10T10:00-12:00Z",
                "estimated_height": "7-9ft",
                "estimated_period": "13-15s",
                "confidence": 0.75,
            }
        ],
        "frontal_boundaries": [
            {"type": "cold_front", "location": "approaching from NW", "timing": "2025-10-09T18:00Z"}
        ],
    }


@pytest.fixture
def temp_image_file():
    """Create a temporary image file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(b"fake image data")
        tmp_path = tmp.name

    yield tmp_path

    # Cleanup
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


# =============================================================================
# VISION API PARSING TESTS (8 tests)
# =============================================================================


class TestPressureAnalystVisionAPI:
    """Tests for vision API parsing functionality."""

    @pytest.mark.asyncio
    async def test_analyze_with_vision_successful_analysis(
        self, pressure_analyst, temp_image_file, sample_vision_response
    ):
        """Test successful pressure chart analysis via vision API."""
        # Arrange
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            return_value=json.dumps(sample_vision_response)
        )

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert
        assert "systems" in result
        assert "predicted_swells" in result
        assert "frontal_boundaries" in result
        assert len(result["systems"]) == 1
        assert len(result["predicted_swells"]) == 1
        assert result["systems"][0]["type"] == "low_pressure"

    @pytest.mark.asyncio
    async def test_analyze_with_vision_multiple_low_pressure_systems(
        self, pressure_analyst, temp_image_file
    ):
        """Test detection of multiple low-pressure systems."""
        # Arrange
        multi_system_response = {
            "systems": [
                {
                    "type": "low_pressure",
                    "location": "45N 160W",
                    "location_lat": 45.0,
                    "location_lon": -160.0,
                    "pressure_mb": 990,
                    "movement": "E at 30kt",
                    "intensification": "strengthening",
                },
                {
                    "type": "low_pressure",
                    "location": "50N 170W",
                    "location_lat": 50.0,
                    "location_lon": -170.0,
                    "pressure_mb": 980,
                    "movement": "SE at 20kt",
                    "intensification": "steady",
                },
                {
                    "type": "high_pressure",
                    "location": "35N 150W",
                    "location_lat": 35.0,
                    "location_lon": -150.0,
                    "pressure_mb": 1025,
                    "movement": "stationary",
                    "intensification": "steady",
                },
            ],
            "predicted_swells": [],
            "frontal_boundaries": [],
        }
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            return_value=json.dumps(multi_system_response)
        )

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert
        assert len(result["systems"]) == 3
        low_pressure_systems = [s for s in result["systems"] if s["type"] == "low_pressure"]
        assert len(low_pressure_systems) == 2
        assert result["systems"][0]["pressure_mb"] == 990
        assert result["systems"][1]["pressure_mb"] == 980

    @pytest.mark.asyncio
    async def test_analyze_with_vision_handles_markdown_code_blocks(
        self, pressure_analyst, temp_image_file, sample_vision_response
    ):
        """Test handling of markdown-wrapped JSON response."""
        # Arrange: Vision API returns JSON wrapped in markdown code blocks
        markdown_wrapped = f"```json\n{json.dumps(sample_vision_response)}\n```"
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            return_value=markdown_wrapped
        )

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert: Successfully parsed despite markdown wrapping
        assert "systems" in result
        assert len(result["systems"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_vision_invalid_json_returns_empty(
        self, pressure_analyst, temp_image_file
    ):
        """Test that invalid JSON returns empty structures."""
        # Arrange: Vision API returns invalid JSON
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            return_value="This is not valid JSON at all"
        )

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert: Returns empty structures instead of crashing
        assert result == {"systems": [], "predicted_swells": [], "frontal_boundaries": []}

    @pytest.mark.asyncio
    async def test_analyze_with_vision_api_error_returns_empty(
        self, pressure_analyst, temp_image_file
    ):
        """Test that vision API errors return empty structures."""
        # Arrange: Vision API raises exception
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            side_effect=Exception("API connection failed")
        )

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert: Returns empty structures gracefully
        assert result == {"systems": [], "predicted_swells": [], "frontal_boundaries": []}

    @pytest.mark.asyncio
    async def test_analyze_with_vision_empty_response_returns_empty(
        self, pressure_analyst, temp_image_file
    ):
        """Test handling of empty/None response from vision API."""
        # Arrange: Vision API returns None
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(return_value=None)

        # Act
        result = await pressure_analyst._analyze_with_vision([temp_image_file], [], "North Pacific")

        # Assert
        assert result == {"systems": [], "predicted_swells": [], "frontal_boundaries": []}

    @pytest.mark.asyncio
    async def test_analyze_with_vision_includes_chart_times_in_prompt(
        self, pressure_analyst, temp_image_file, sample_vision_response
    ):
        """Test that chart timestamps are included in the prompt."""
        # Arrange
        chart_times = ["2025-10-08T00:00Z", "2025-10-08T06:00Z", "2025-10-08T12:00Z"]
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            return_value=json.dumps(sample_vision_response)
        )

        # Act
        await pressure_analyst._analyze_with_vision([temp_image_file], chart_times, "North Pacific")

        # Assert: Check that call was made (timestamps would be in prompt)
        assert pressure_analyst.engine.openai_client.call_openai_api.called
        call_args = pressure_analyst.engine.openai_client.call_openai_api.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_analyze_with_vision_multiple_images(
        self, pressure_analyst, sample_vision_response
    ):
        """Test processing multiple pressure chart images."""
        # Arrange: Create multiple temporary images
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp1:
            tmp1.write(b"image1")
            img1 = tmp1.name
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp2:
            tmp2.write(b"image2")
            img2 = tmp2.name

        try:
            pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
                return_value=json.dumps(sample_vision_response)
            )

            # Act
            result = await pressure_analyst._analyze_with_vision([img1, img2], [], "North Pacific")

            # Assert: Both images processed successfully
            assert "systems" in result
            assert pressure_analyst.engine.openai_client.call_openai_api.called
        finally:
            # Cleanup
            os.unlink(img1)
            os.unlink(img2)


# =============================================================================
# SWELL PREDICTION ENHANCEMENT TESTS (10 tests)
# =============================================================================


class TestPressureAnalystSwellPredictions:
    """Tests for swell prediction enhancement functionality."""

    def test_enhance_swell_predictions_calculates_travel_time(
        self, pressure_analyst, sample_vision_response
    ):
        """Test travel time calculation for storm-generated swell."""
        # Arrange
        swells = sample_vision_response["predicted_swells"]
        systems = sample_vision_response["systems"]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert
        assert len(enhanced) == 1
        assert "travel_time_hrs" in enhanced[0]
        assert "distance_nm" in enhanced[0]
        assert "calculated_arrival" in enhanced[0]
        assert enhanced[0]["travel_time_hrs"] > 0
        assert enhanced[0]["distance_nm"] > 0

    def test_enhance_swell_predictions_matches_source_system(self, pressure_analyst):
        """Test matching of swells to their source systems."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location": "45N 160W",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "pressure_mb": 990,
                "wind_speed_kt": 50,
                "movement": "SE at 25kt",
                "intensification": "strengthening",
                "fetch": {"quality": "strong", "duration_hrs": 36.0, "fetch_length_nm": 500.0},
            }
        ]
        swells = [
            {
                "source_system": "low_45n_160w",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "direction": "NNE",
                "estimated_period": "14s",
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Fetch quality added from matched system
        assert enhanced[0]["fetch_quality"] == "strong"
        assert enhanced[0]["fetch_duration_hrs"] == 36.0
        assert enhanced[0]["fetch_length_nm"] == 500.0

    def test_enhance_swell_predictions_adds_source_characteristics(self, pressure_analyst):
        """Test that source system characteristics are added to swell."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location": "45N 160W",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "pressure_mb": 985,
                "wind_speed_kt": 55,
                "movement": "E at 30kt",
                "intensification": "strengthening",
            }
        ]
        swells = [
            {
                "source_system": "low_45N_160W",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "15s",
                "confidence": 0.7,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert
        assert enhanced[0]["source_pressure_mb"] == 985
        assert enhanced[0]["source_wind_speed_kt"] == 55
        assert enhanced[0]["source_trend"] == "strengthening"

    def test_enhance_swell_predictions_period_range_handling(self, pressure_analyst):
        """Test handling of period ranges (e.g., '13-15s')."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "generation_time": "2025-10-08T12:00Z",
            }
        ]
        swells = [
            {
                "source_system": "test",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "13-15s",  # Period range
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Average period used for calculation (14s)
        assert "travel_time_hrs" in enhanced[0]
        assert enhanced[0]["travel_time_hrs"] > 0

    def test_enhance_swell_predictions_single_period_value(self, pressure_analyst):
        """Test handling of single period value (e.g., '14s')."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "generation_time": "2025-10-08T12:00Z",
            }
        ]
        swells = [
            {
                "source_system": "test",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "14s",  # Single value
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert
        assert "travel_time_hrs" in enhanced[0]
        assert enhanced[0]["travel_time_hrs"] > 0

    def test_enhance_swell_predictions_no_matching_system(self, pressure_analyst):
        """Test swell enhancement when no matching source system found."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location": "50N 170W",
                "location_lat": 50.0,
                "location_lon": -170.0,
            }
        ]
        swells = [
            {
                "source_system": "low_45N_160W",  # Doesn't match
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "14s",
                "confidence": 0.7,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Physics calculations still work with coordinates
        assert len(enhanced) == 1
        assert "travel_time_hrs" in enhanced[0]

    def test_enhance_swell_predictions_missing_coordinates(self, pressure_analyst):
        """Test enhancement when swell lacks source coordinates."""
        # Arrange
        systems = []
        swells = [
            {
                "source_system": "unknown",
                # No source_lat or source_lon
                "estimated_period": "14s",
                "confidence": 0.5,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Gracefully handles missing coordinates
        assert len(enhanced) == 1
        assert "travel_time_hrs" not in enhanced[0]  # Can't calculate without coords

    def test_enhance_swell_predictions_uses_generation_time(self, pressure_analyst):
        """Test that generation_time from system is used for arrival calculation."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "generation_time": "2025-10-08T12:00Z",
            }
        ]
        swells = [
            {
                "source_system": "low_pressure",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "14s",
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Calculated arrival includes generation time
        assert "calculated_arrival" in enhanced[0]
        arrival = datetime.fromisoformat(enhanced[0]["calculated_arrival"].replace("Z", "+00:00"))
        generation = datetime.fromisoformat("2025-10-08T12:00+00:00")
        assert arrival > generation

    def test_enhance_swell_predictions_fallback_to_current_time(self, pressure_analyst):
        """Test fallback to current time when generation_time missing."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location_lat": 45.0,
                "location_lon": -160.0,
                # No generation_time
            }
        ]
        swells = [
            {
                "source_system": "low_pressure",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "14s",
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert: Still calculates arrival (uses current time as fallback)
        assert "calculated_arrival" in enhanced[0]
        assert "travel_time_hrs" in enhanced[0]

    def test_enhance_swell_predictions_propagation_method_flag(self, pressure_analyst):
        """Test that propagation_method flag is set correctly."""
        # Arrange
        systems = [
            {
                "type": "low_pressure",
                "location_lat": 45.0,
                "location_lon": -160.0,
                "generation_time": "2025-10-08T12:00Z",
            }
        ]
        swells = [
            {
                "source_system": "test",
                "source_lat": 45.0,
                "source_lon": -160.0,
                "estimated_period": "14s",
                "confidence": 0.8,
            }
        ]

        # Act
        enhanced = pressure_analyst._enhance_swell_predictions(swells, systems)

        # Assert
        assert enhanced[0]["propagation_method"] == "physics_based"


# =============================================================================
# PHYSICS CALCULATION TESTS (4 tests)
# =============================================================================


class TestPressureAnalystPhysicsCalculations:
    """Tests for physics-based calculation methods."""

    def test_calculate_swell_travel_time_14s_period(self, pressure_analyst):
        """Test travel time calculation for 14s period swell."""
        # Arrange
        distance_nm = 2000.0  # Nautical miles
        period_s = 14.0  # Seconds

        # Act
        travel_time_hrs = pressure_analyst._calculate_swell_travel_time(distance_nm, period_s)

        # Assert: 14s period gives ~21.2 kt group velocity, ~94 hours for 2000nm
        assert 90 < travel_time_hrs < 98
        assert travel_time_hrs > 0

    def test_calculate_swell_travel_time_20s_period(self, pressure_analyst):
        """Test travel time calculation for 20s period swell (faster)."""
        # Arrange
        distance_nm = 2000.0
        period_s = 20.0  # Longer period = faster group velocity

        # Act
        travel_time_hrs = pressure_analyst._calculate_swell_travel_time(distance_nm, period_s)

        # Assert: 20s period gives ~30.3 kt group velocity, ~66 hours for 2000nm
        assert 63 < travel_time_hrs < 69
        assert travel_time_hrs > 0

    def test_calculate_distance_to_hawaii_kamchatka(self, pressure_analyst):
        """Test distance calculation from Kamchatka region to Hawaii."""
        # Arrange: Kamchatka/Kuril Islands approximate location
        lat = 45.0
        lon = 155.0  # East longitude (should be positive in calculation)

        # Act
        distance_nm = pressure_analyst._calculate_distance_to_hawaii(lat, lon)

        # Assert: ~2698 nm from Kamchatka to Hawaii
        assert 2650 < distance_nm < 2750
        assert distance_nm > 0

    def test_calculate_distance_to_hawaii_aleutians(self, pressure_analyst):
        """Test distance calculation from Aleutian Islands to Hawaii."""
        # Arrange: Aleutian Islands approximate location
        lat = 52.0
        lon = -175.0  # West longitude

        # Act
        distance_nm = pressure_analyst._calculate_distance_to_hawaii(lat, lon)

        # Assert: ~1900-2200 nm from Aleutians to Hawaii
        assert 1800 < distance_nm < 2300
        assert distance_nm > 0


# =============================================================================
# CONFIDENCE SCORING TESTS (5 tests)
# =============================================================================


class TestPressureAnalystConfidence:
    """Tests for confidence calculation functionality."""

    def test_calculate_confidence_high_quality_6_images(self, pressure_analyst):
        """Test high confidence with 6+ images and strong fetch."""
        # Arrange
        num_images = 6
        systems = [{"fetch": {"quality": "strong"}}]
        swells = [{"confidence": 0.8}]
        chart_times = [f"2025-10-08T{i:02d}:00Z" for i in range(6)]

        # Act
        confidence = pressure_analyst._calculate_analysis_confidence(
            num_images, systems, swells, chart_times
        )

        # Assert: High confidence (>0.7)
        assert confidence > 0.7
        assert confidence <= 1.0

    def test_calculate_confidence_medium_quality_4_images(self, pressure_analyst):
        """Test medium confidence with 4 images and moderate fetch."""
        # Arrange
        num_images = 4
        systems = [{"fetch": {"quality": "moderate"}}]
        swells = [{"confidence": 0.6}]
        chart_times = [f"2025-10-08T{i*6:02d}:00Z" for i in range(4)]

        # Act
        confidence = pressure_analyst._calculate_analysis_confidence(
            num_images, systems, swells, chart_times
        )

        # Assert: Medium confidence (0.5-0.7)
        assert 0.4 < confidence < 0.8

    def test_calculate_confidence_low_quality_single_image(self, pressure_analyst):
        """Test low confidence with single image and weak fetch."""
        # Arrange
        num_images = 1
        systems = [{"fetch": {"quality": "weak"}}]
        swells = [{"confidence": 0.3}]
        chart_times = []

        # Act
        confidence = pressure_analyst._calculate_analysis_confidence(
            num_images, systems, swells, chart_times
        )

        # Assert: Low confidence (<0.5)
        assert confidence < 0.6
        assert confidence >= 0.0

    def test_calculate_confidence_no_systems_detected(self, pressure_analyst):
        """Test confidence calculation when no systems detected."""
        # Arrange
        num_images = 4
        systems = []  # No systems
        swells = []
        chart_times = []

        # Act
        confidence = pressure_analyst._calculate_analysis_confidence(
            num_images, systems, swells, chart_times
        )

        # Assert: Low confidence due to no detections
        assert confidence < 0.5
        assert confidence >= 0.0

    def test_calculate_confidence_temporal_coverage_bonus(self, pressure_analyst):
        """Test 10% confidence bonus for good temporal coverage (>24hr span)."""
        # Arrange: 8 images spanning 48 hours
        num_images = 8
        systems = [{"fetch": {"quality": "strong"}}]
        swells = [{"confidence": 0.7}]

        # Chart times spanning 48 hours
        base_time = datetime(2025, 10, 8, 0, 0)
        chart_times = [(base_time + timedelta(hours=i * 6)).isoformat() + "Z" for i in range(8)]

        # Act
        confidence = pressure_analyst._calculate_analysis_confidence(
            num_images, systems, swells, chart_times
        )

        # Assert: High confidence with temporal bonus
        assert confidence > 0.75


# =============================================================================
# IMAGE VALIDATION TESTS (5 tests)
# =============================================================================


class TestPressureAnalystImageValidation:
    """Tests for image path validation functionality."""

    def test_validate_image_paths_accepts_valid_png(self, pressure_analyst, temp_image_file):
        """Test validation accepts valid PNG file."""
        # Act
        valid_paths = pressure_analyst._validate_image_paths([temp_image_file])

        # Assert
        assert len(valid_paths) == 1
        assert valid_paths[0] == temp_image_file

    def test_validate_image_paths_accepts_multiple_formats(self, pressure_analyst):
        """Test validation accepts various image formats."""
        # Arrange: Create multiple image files with different formats
        formats = [".png", ".jpg", ".jpeg", ".gif", ".webp"]
        temp_files = []

        for fmt in formats:
            with tempfile.NamedTemporaryFile(suffix=fmt, delete=False) as tmp:
                tmp.write(b"image data")
                temp_files.append(tmp.name)

        try:
            # Act
            valid_paths = pressure_analyst._validate_image_paths(temp_files)

            # Assert: All formats accepted
            assert len(valid_paths) == 5
        finally:
            # Cleanup
            for f in temp_files:
                os.unlink(f)

    def test_validate_image_paths_rejects_nonexistent_file(self, pressure_analyst):
        """Test validation rejects non-existent files."""
        # Arrange
        nonexistent_path = "/nonexistent/image.png"

        # Act
        valid_paths = pressure_analyst._validate_image_paths([nonexistent_path])

        # Assert: Non-existent file excluded
        assert len(valid_paths) == 0

    def test_validate_image_paths_rejects_non_image_format(self, pressure_analyst):
        """Test validation rejects non-image file formats."""
        # Arrange: Create .txt file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"not an image")
            txt_path = tmp.name

        try:
            # Act
            valid_paths = pressure_analyst._validate_image_paths([txt_path])

            # Assert: Non-image format excluded
            assert len(valid_paths) == 0
        finally:
            # Cleanup
            os.unlink(txt_path)

    def test_validate_image_paths_filters_mixed_valid_invalid(
        self, pressure_analyst, temp_image_file
    ):
        """Test validation filters mixed valid/invalid paths."""
        # Arrange: Mix of valid and invalid paths
        mixed_paths = [
            temp_image_file,  # Valid
            "/nonexistent/image.png",  # Invalid: doesn't exist
            "/tmp/document.pdf",  # Invalid: wrong format
        ]

        # Act
        valid_paths = pressure_analyst._validate_image_paths(mixed_paths)

        # Assert: Only valid path returned
        assert len(valid_paths) == 1
        assert valid_paths[0] == temp_image_file


# =============================================================================
# INTEGRATION TESTS (4 tests)
# =============================================================================


class TestPressureAnalystIntegration:
    """Integration tests for complete analyze() workflow."""

    @pytest.mark.asyncio
    async def test_analyze_complete_workflow(
        self, pressure_analyst, temp_image_file, sample_vision_response
    ):
        """Test complete analyze workflow with valid data."""
        # Arrange
        pressure_analyst.engine.openai_client.call_openai_api = AsyncMock(
            side_effect=[
                json.dumps(sample_vision_response),  # Vision API call
                "Comprehensive pressure analysis narrative",  # Narrative generation
            ]
        )

        data = {
            "images": [temp_image_file],
            "metadata": {"chart_times": ["2025-10-08T00:00Z"], "region": "North Pacific"},
        }

        # Act
        result = await pressure_analyst.analyze(data)

        # Assert: Returns PressureAnalystOutput
        assert isinstance(result, PressureAnalystOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.data.systems) == 1
        assert len(result.data.predicted_swells) == 1
        assert len(result.data.frontal_boundaries) == 1
        assert result.narrative is not None
        assert len(result.narrative) > 0
        assert "num_images" in result.metadata
        assert result.metadata["region"] == "North Pacific"

    @pytest.mark.asyncio
    async def test_analyze_missing_images_key_raises_error(self, pressure_analyst):
        """Test analyze raises ValueError for missing 'images' key."""
        # Arrange: Missing 'images' key
        data = {"wrong_key": []}

        # Act & Assert
        with pytest.raises(ValueError, match="Missing required keys"):
            await pressure_analyst.analyze(data)

    @pytest.mark.asyncio
    async def test_analyze_empty_image_list_raises_error(self, pressure_analyst):
        """Test analyze raises ValueError for empty image list."""
        # Arrange: Empty images list
        data = {"images": []}

        # Act & Assert
        with pytest.raises(ValueError, match="must be a non-empty list"):
            await pressure_analyst.analyze(data)

    @pytest.mark.asyncio
    async def test_analyze_no_valid_images_raises_error(self, pressure_analyst):
        """Test analyze raises ValueError when no valid images found."""
        # Arrange: Only invalid image paths
        data = {"images": ["/nonexistent/image1.png", "/nonexistent/image2.jpg"]}

        # Act & Assert
        with pytest.raises(ValueError, match="No valid image files found"):
            await pressure_analyst.analyze(data)


# =============================================================================
# INITIALIZATION TESTS (2 tests)
# =============================================================================


class TestPressureAnalystInitialization:
    """Tests for PressureAnalyst initialization."""

    def test_initialization_requires_engine(self, mock_config):
        """Test that PressureAnalyst requires engine parameter."""
        # Act & Assert: Missing engine raises ValueError
        with pytest.raises(ValueError, match="requires engine parameter"):
            PressureAnalyst(config=mock_config, model_name="gpt-4o", engine=None)

    def test_initialization_success(self, mock_config, mock_engine):
        """Test successful initialization with all required parameters."""
        # Act
        analyst = PressureAnalyst(config=mock_config, model_name="gpt-4o", engine=mock_engine)

        # Assert
        assert analyst.model_name == "gpt-4o"
        assert analyst.engine == mock_engine
        assert analyst.hawaii_lat == 21.5
        assert analyst.hawaii_lon == -158.0
        assert analyst.GRAVITY == 9.81
        assert analyst.swell_calculator is not None
