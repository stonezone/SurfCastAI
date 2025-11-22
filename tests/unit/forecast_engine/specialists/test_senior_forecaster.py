"""
Unit tests for SeniorForecaster specialist module.

Tests cover all critical functionality including:
- Contradiction detection between specialist reports
- Specialist agreement calculation
- Shore forecast generation (North, South, East, West)
- Swell breakdown synthesis with source attribution
- Direction matching logic with tolerance
- Timing analysis (future/near arrival detection)
- Integration workflow with Pydantic models

Test Structure:
- Tests are organized by functionality area
- Each test follows AAA pattern (Arrange-Act-Assert)
- Mocked dependencies (config, engine, OpenAI client, specialists)
- Isolated tests (no interdependencies)
"""

from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest

from src.forecast_engine.specialists.schemas import (
    AgreementLevel,
    AnalysisSummary,
    BuoyAnalystData,
    BuoyAnalystOutput,
    BuoyTrend,
    Contradiction,
    CrossValidation,
    FetchQuality,
    ImpactLevel,
    IntensificationTrend,
    PredictedSwell,
    PressureAnalystData,
    PressureAnalystOutput,
    QualityFlag,
    SeniorForecasterInput,
    SeniorForecasterOutput,
    ShoreForecast,
    SummaryStats,
    SwellBreakdown,
    Synthesis,
    SystemType,
    TrendType,
    WeatherSystem,
)
from src.forecast_engine.specialists.senior_forecaster import SeniorForecaster

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.get.return_value = "fake-api-key"
    config.getint.side_effect = lambda section, key, fallback=None: {
        "max_tokens": 2000,
        "require_minimum_specialists": 2,
    }.get(key, fallback)
    return config


@pytest.fixture
def mock_engine():
    """Create a mock forecast engine with OpenAI client."""
    engine = Mock()
    engine.openai_client = Mock()
    engine.openai_client.call_openai_api = AsyncMock(
        return_value="Test Pat Caldwell-style forecast narrative"
    )
    return engine


@pytest.fixture
def senior_forecaster(mock_config, mock_engine):
    """Create a SeniorForecaster instance with mocked dependencies."""
    return SeniorForecaster(config=mock_config, model_name="gpt-4o-mini", engine=mock_engine)


@pytest.fixture
def sample_buoy_analysis():
    """Create sample BuoyAnalystOutput with trends."""
    trend = BuoyTrend(
        buoy_id="51001",
        buoy_name="NW Hawaii",
        height_trend=TrendType.INCREASING_MODERATE,
        height_slope=0.08,
        height_current=3.5,
        period_trend=TrendType.STEADY,
        period_slope=0.01,
        period_current=14.0,
        direction_trend=TrendType.STEADY,
        direction_current=315.0,
        observations_count=10,
    )

    data = BuoyAnalystData(
        trends=[trend],
        anomalies=[],
        quality_flags={"51001": QualityFlag.VALID},
        cross_validation=CrossValidation(
            agreement_score=0.9,
            height_agreement=0.9,
            period_agreement=0.9,
            num_buoys_compared=2,
            interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
        ),
        summary_stats=SummaryStats(
            avg_wave_height=3.5,
            max_wave_height=4.0,
            min_wave_height=3.0,
            avg_period=14.0,
            max_period=15.0,
            min_period=13.0,
        ),
    )

    return BuoyAnalystOutput(
        confidence=0.85,
        data=data,
        narrative="Buoy analysis shows moderate building trend from NW.",
        metadata={"timestamp": datetime.now().isoformat()},
    )


@pytest.fixture
def sample_pressure_analysis():
    """Create sample PressureAnalystOutput with predicted swells."""
    predicted_swell = PredictedSwell(
        source_system="low_45N_165W",
        source_lat=45.0,
        source_lon=-165.0,
        direction="NNW",
        direction_degrees=330,
        arrival_time="2025-10-12T18:00Z",
        estimated_height="6-8ft",
        estimated_period="13-15s",
        confidence=0.75,
    )

    system = WeatherSystem(
        type=SystemType.LOW_PRESSURE,
        location="45N 165W",
        location_lat=45.0,
        location_lon=-165.0,
        pressure_mb=985,
        wind_speed_kt=45,
        movement="SE at 25kt",
        intensification=IntensificationTrend.STRENGTHENING,
    )

    data = PressureAnalystData(
        systems=[system],
        predicted_swells=[predicted_swell],
        frontal_boundaries=[],
        analysis_summary=AnalysisSummary(
            num_low_pressure=1, num_high_pressure=0, num_predicted_swells=1, region="North Pacific"
        ),
    )

    return PressureAnalystOutput(
        confidence=0.80,
        data=data,
        narrative="Strong low-pressure system generating NNW swell.",
        metadata={"timestamp": datetime.now().isoformat()},
    )


@pytest.fixture
def sample_dict_buoy_analysis():
    """Create sample buoy analysis in dict format (legacy compatibility)."""
    return {
        "confidence": 0.85,
        "data": {
            "trends": [
                {
                    "buoy_id": "51001",
                    "buoy_name": "NW Hawaii",
                    "height_trend": "increasing_moderate",
                    "height_slope": 0.08,
                    "height_current": 3.5,
                    "period_current": 14.0,
                    "direction_current": 315.0,
                }
            ]
        },
        "narrative": "Buoy analysis shows moderate building trend from NW.",
    }


@pytest.fixture
def sample_dict_pressure_analysis():
    """Create sample pressure analysis in dict format (legacy compatibility)."""
    return {
        "confidence": 0.80,
        "data": {
            "systems": [
                {
                    "type": "low_pressure",
                    "location": "45N 165W",
                    "fetch": {
                        "direction": "NNW",
                        "distance_nm": 1200.0,
                        "duration_hrs": 24.0,
                        "fetch_length_nm": 500.0,
                        "quality": "strong",
                    },
                }
            ],
            "predicted_swells": [
                {
                    "source_system": "low_45N_165W",
                    "direction": "NNW",
                    "arrival_time": (datetime.now() + timedelta(hours=6)).isoformat() + "Z",
                    "estimated_height": "6-8ft",
                    "estimated_period": "13-15s",
                    "confidence": 0.75,
                }
            ],
        },
        "narrative": "Strong low-pressure system generating NNW swell.",
    }


# =============================================================================
# CONTRADICTION DETECTION TESTS (8 tests)
# =============================================================================


class TestSeniorForecasterContradictions:
    """Tests for contradiction detection functionality."""

    def test_identify_contradictions_none_in_consistent_data(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test no contradictions detected when specialists agree."""
        # Arrange: Both specialists predict NW/NNW swell (within tolerance)

        # Act
        contradictions = senior_forecaster._identify_contradictions(
            sample_buoy_analysis, sample_pressure_analysis
        )

        # Assert: No contradictions (directions match, trends align)
        assert isinstance(contradictions, list)
        assert len(contradictions) == 0

    def test_identify_contradictions_buoy_signal_without_pressure_support(self, senior_forecaster):
        """Test contradiction detected for buoy signal without pressure support."""
        # Arrange: Buoy shows strong increase, but no pressure system in that direction
        buoy_trend = BuoyTrend(
            buoy_id="51002",
            buoy_name="South Hawaii",
            height_trend=TrendType.INCREASING_STRONG,
            height_slope=0.15,
            height_current=4.0,
            period_trend=TrendType.INCREASING_MODERATE,
            period_slope=0.08,
            period_current=12.0,
            direction_trend=TrendType.STEADY,
            direction_current=180.0,  # South
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="South swell building"
        )

        # Pressure analysis shows only NW systems
        pressure_system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 165W",
            location_lat=45.0,
            location_lon=-165.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STRENGTHENING,
        )

        pressure_data = PressureAnalystData(
            systems=[pressure_system],
            predicted_swells=[],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=1,
                num_high_pressure=0,
                num_predicted_swells=0,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.80, data=pressure_data, narrative="NW low pressure"
        )

        # Act
        contradictions = senior_forecaster._identify_contradictions(
            buoy_analysis, pressure_analysis
        )

        # Assert: Contradiction detected (buoy shows S swell but no S pressure support)
        assert len(contradictions) >= 1
        contradiction = contradictions[0]
        assert "no supporting pressure system" in contradiction["issue"]
        assert contradiction["impact"] in ["medium", "high"]

    def test_identify_contradictions_predicted_swell_without_buoy_confirmation(
        self, senior_forecaster
    ):
        """Test contradiction detected for predicted swell without buoy signal."""
        # Arrange: Pressure predicts swell but buoys show no signal
        buoy_trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=2.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=10.0,
            direction_trend=TrendType.STEADY,
            direction_current=270.0,  # West (not NW)
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Steady conditions"
        )

        # Pressure predicts strong NW swell
        predicted_swell = PredictedSwell(
            source_system="low_50N_170W",
            source_lat=50.0,
            source_lon=-170.0,
            direction="NW",
            direction_degrees=315,
            arrival_time="2025-10-12T12:00Z",
            estimated_height="8-10ft",
            estimated_period="15-17s",
            confidence=0.85,
        )

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[predicted_swell],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=1,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.80, data=pressure_data, narrative="NW swell predicted"
        )

        # Act
        contradictions = senior_forecaster._identify_contradictions(
            buoy_analysis, pressure_analysis
        )

        # Assert: Contradiction detected
        assert len(contradictions) >= 1
        contradiction = contradictions[0]
        assert "buoys show no current signal" in contradiction["issue"]

    def test_identify_contradictions_timing_mismatch(self, senior_forecaster):
        """Test contradiction detected for timing discrepancies."""
        # Arrange: Pressure predicts future NW swell, but buoy shows decreasing NW trend
        buoy_trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.DECREASING_STRONG,
            height_slope=-0.12,
            height_current=2.5,
            period_trend=TrendType.DECREASING_MODERATE,
            period_slope=-0.08,
            period_current=12.0,
            direction_trend=TrendType.STEADY,
            direction_current=315.0,
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="NW swell declining"
        )

        # Pressure predicts incoming NW swell (future arrival)
        future_time = (datetime.now() + timedelta(hours=24)).isoformat() + "Z"
        predicted_swell = PredictedSwell(
            source_system="low_45N_165W",
            source_lat=45.0,
            source_lon=-165.0,
            direction="NW",
            direction_degrees=315,
            arrival_time=future_time,
            estimated_height="7-9ft",
            estimated_period="14-16s",
            confidence=0.80,
        )

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[predicted_swell],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=1,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.80, data=pressure_data, narrative="NW swell arriving tomorrow"
        )

        # Act
        contradictions = senior_forecaster._identify_contradictions(
            buoy_analysis, pressure_analysis
        )

        # Assert: Contradiction detected (decreasing trend vs predicted arrival)
        assert len(contradictions) >= 1
        timing_contradiction = next(
            (c for c in contradictions if "decreasing trend" in c["issue"]), None
        )
        assert timing_contradiction is not None
        assert timing_contradiction["impact"] == "medium"

    def test_identify_contradictions_no_specialists(self, senior_forecaster):
        """Test contradiction detection with missing specialists."""
        # Act
        contradictions = senior_forecaster._identify_contradictions(None, None)

        # Assert: Empty list when no specialists available
        assert contradictions == []

    def test_identify_contradictions_only_buoy_specialist(
        self, senior_forecaster, sample_buoy_analysis
    ):
        """Test contradiction detection with only buoy specialist."""
        # Act
        contradictions = senior_forecaster._identify_contradictions(sample_buoy_analysis, None)

        # Assert: Empty list (can't cross-validate with one specialist)
        assert contradictions == []

    def test_identify_contradictions_only_pressure_specialist(
        self, senior_forecaster, sample_pressure_analysis
    ):
        """Test contradiction detection with only pressure specialist."""
        # Act
        contradictions = senior_forecaster._identify_contradictions(None, sample_pressure_analysis)

        # Assert: Empty list (can't cross-validate with one specialist)
        assert contradictions == []

    def test_identify_contradictions_multiple_simultaneous(self, senior_forecaster):
        """Test detection of multiple simultaneous contradictions."""
        # Arrange: Buoy shows S building, NW declining; Pressure predicts only NW
        buoy_trends = [
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.DECREASING_MODERATE,
                height_slope=-0.08,
                height_current=2.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=11.0,
                direction_trend=TrendType.STEADY,
                direction_current=315.0,
                observations_count=10,
            ),
            BuoyTrend(
                buoy_id="51002",
                buoy_name="South Hawaii",
                height_trend=TrendType.INCREASING_STRONG,
                height_slope=0.15,
                height_current=4.5,
                period_trend=TrendType.INCREASING_MODERATE,
                period_slope=0.08,
                period_current=13.0,
                direction_trend=TrendType.STEADY,
                direction_current=180.0,
                observations_count=10,
            ),
        ]

        buoy_data = BuoyAnalystData(
            trends=buoy_trends,
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID, "51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.7,
                height_agreement=0.7,
                period_agreement=0.7,
                num_buoys_compared=2,
                interpretation=AgreementLevel.GOOD_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(confidence=0.80, data=buoy_data, narrative="Mixed trends")

        # Pressure predicts only NW swell
        future_time = (datetime.now() + timedelta(hours=12)).isoformat() + "Z"
        predicted_swell = PredictedSwell(
            source_system="low_45N_165W",
            source_lat=45.0,
            source_lon=-165.0,
            direction="NW",
            direction_degrees=315,
            arrival_time=future_time,
            estimated_height="5-7ft",
            estimated_period="13-15s",
            confidence=0.75,
        )

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[predicted_swell],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=1,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.75, data=pressure_data, narrative="NW swell predicted"
        )

        # Act
        contradictions = senior_forecaster._identify_contradictions(
            buoy_analysis, pressure_analysis
        )

        # Assert: Multiple contradictions detected
        assert len(contradictions) >= 2
        # S buoy shows building but no S pressure support
        # NW buoy shows decreasing but pressure predicts NW arrival


# =============================================================================
# SPECIALIST AGREEMENT CALCULATION TESTS (6 tests)
# =============================================================================


class TestSeniorForecasterAgreement:
    """Tests for specialist agreement calculation functionality."""

    def test_calculate_specialist_agreement_perfect_match(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test perfect agreement (all metrics match)."""
        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(
            sample_buoy_analysis, sample_pressure_analysis
        )

        # Assert: High agreement (directions match, both predict NW)
        assert 0.0 <= agreement_score <= 1.0
        assert agreement_score > 0.5  # At least moderate agreement

    def test_calculate_specialist_agreement_partial_match(self, senior_forecaster):
        """Test partial agreement (some metrics match)."""
        # Arrange: Buoy shows NW, Pressure predicts NE (partial directional match)
        buoy_trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.INCREASING_MODERATE,
            height_slope=0.08,
            height_current=3.5,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=14.0,
            direction_trend=TrendType.STEADY,
            direction_current=315.0,  # NW
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="NW swell building"
        )

        predicted_swell = PredictedSwell(
            source_system="low_40N_170W",
            source_lat=40.0,
            source_lon=-170.0,
            direction="NE",
            direction_degrees=45,  # NE (90° different from NW)
            arrival_time="2025-10-12T18:00Z",
            estimated_height="5-7ft",
            estimated_period="12-14s",
            confidence=0.70,
        )

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[predicted_swell],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=1,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.80, data=pressure_data, narrative="NE swell predicted"
        )

        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(
            buoy_analysis, pressure_analysis
        )

        # Assert: Lower agreement due to direction mismatch
        assert 0.0 <= agreement_score <= 1.0
        assert agreement_score < 0.8

    def test_calculate_specialist_agreement_strong_disagreement(self, senior_forecaster):
        """Test strong disagreement (no metrics match)."""
        # Arrange: Buoy shows S declining, Pressure predicts N building
        buoy_trend = BuoyTrend(
            buoy_id="51002",
            buoy_name="South Hawaii",
            height_trend=TrendType.DECREASING_MODERATE,
            height_slope=-0.08,
            height_current=2.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=10.0,
            direction_trend=TrendType.STEADY,
            direction_current=180.0,  # S
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.50, data=buoy_data, narrative="S swell declining"  # Low confidence
        )

        predicted_swell = PredictedSwell(
            source_system="low_50N_160W",
            source_lat=50.0,
            source_lon=-160.0,
            direction="N",
            direction_degrees=0,  # N (180° opposite)
            arrival_time="2025-10-12T18:00Z",
            estimated_height="8-10ft",
            estimated_period="15-17s",
            confidence=0.90,  # High confidence
        )

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[predicted_swell],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=1,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.90, data=pressure_data, narrative="Strong N swell predicted"
        )

        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(
            buoy_analysis, pressure_analysis
        )

        # Assert: Very low agreement
        assert 0.0 <= agreement_score <= 1.0
        assert agreement_score < 0.5

    def test_calculate_specialist_agreement_missing_buoy(
        self, senior_forecaster, sample_pressure_analysis
    ):
        """Test agreement calculation with missing buoy analyst."""
        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(
            None, sample_pressure_analysis
        )

        # Assert: Returns 0.0 when specialist missing
        assert agreement_score == 0.0

    def test_calculate_specialist_agreement_missing_pressure(
        self, senior_forecaster, sample_buoy_analysis
    ):
        """Test agreement calculation with missing pressure analyst."""
        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(
            sample_buoy_analysis, None
        )

        # Assert: Returns 0.0 when specialist missing
        assert agreement_score == 0.0

    def test_calculate_specialist_agreement_no_specialists(self, senior_forecaster):
        """Test agreement calculation with no specialists provided."""
        # Act
        agreement_score = senior_forecaster._calculate_specialist_agreement(None, None)

        # Assert: Returns 0.0 when no specialists
        assert agreement_score == 0.0


# =============================================================================
# SHORE FORECAST GENERATION TESTS (10 tests)
# =============================================================================


class TestSeniorForecasterShoreForecasts:
    """Tests for shore-specific forecast generation functionality."""

    def test_generate_shore_forecasts_north_shore_winter(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test North Shore forecast generation in winter season."""
        # Arrange: NW swell data
        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            sample_buoy_analysis, sample_pressure_analysis, shore_data, seasonal_context
        )

        # Assert: North Shore gets forecast
        assert "north_shore" in shore_forecasts
        north = shore_forecasts["north_shore"]
        assert "size_range" in north
        assert "ft" in north["size_range"]
        assert "conditions" in north
        assert "timing" in north
        assert "confidence" in north
        assert 0.0 <= north["confidence"] <= 1.0

    def test_generate_shore_forecasts_south_shore_summer(self, senior_forecaster):
        """Test South Shore forecast generation in summer season."""
        # Arrange: S swell data
        buoy_trend = BuoyTrend(
            buoy_id="51002",
            buoy_name="South Hawaii",
            height_trend=TrendType.INCREASING_MODERATE,
            height_slope=0.08,
            height_current=3.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=15.0,
            direction_trend=TrendType.STEADY,
            direction_current=180.0,  # S
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="S swell building"
        )

        shore_data = {}
        seasonal_context = {"season": "summer"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: South Shore gets favorable forecast in summer
        assert "south_shore" in shore_forecasts
        south = shore_forecasts["south_shore"]
        assert "size_range" in south
        assert "ft" in south["size_range"]

    def test_generate_shore_forecasts_east_shore(self, senior_forecaster):
        """Test East Shore forecast generation."""
        # Arrange: E swell data
        buoy_trend = BuoyTrend(
            buoy_id="51003",
            buoy_name="East Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=2.5,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=8.0,  # Short period (trade swell)
            direction_trend=TrendType.STEADY,
            direction_current=90.0,  # E
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51003": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="E trade swell steady"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: East Shore gets forecast
        assert "east_shore" in shore_forecasts

    def test_generate_shore_forecasts_west_shore(self, senior_forecaster):
        """Test West Shore forecast generation."""
        # Arrange: W swell data
        buoy_trend = BuoyTrend(
            buoy_id="51004",
            buoy_name="West Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=2.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=11.0,
            direction_trend=TrendType.STEADY,
            direction_current=270.0,  # W
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51004": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="W swell steady"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: West Shore gets forecast
        assert "west_shore" in shore_forecasts

    def test_generate_shore_forecasts_no_swell_data(self, senior_forecaster):
        """Test shore forecast with no swell data."""
        # Arrange: Empty buoy data
        buoy_data = BuoyAnalystData(
            trends=[],
            anomalies=[],
            quality_flags={},
            cross_validation=CrossValidation(
                agreement_score=0.5,
                height_agreement=0.5,
                period_agreement=0.5,
                num_buoys_compared=0,
                interpretation=AgreementLevel.MODERATE_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(confidence=0.50, data=buoy_data, narrative="No data")

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: All shores get flat forecasts
        for shore in ["north_shore", "south_shore", "east_shore", "west_shore"]:
            assert shore in shore_forecasts
            assert (
                "1-" in shore_forecasts[shore]["size_range"]
                or "2-" in shore_forecasts[shore]["size_range"]
            )

    def test_generate_shore_forecasts_shadowed_swell(self, senior_forecaster):
        """Test shore forecast with shadowed swell (wrong direction for shore)."""
        # Arrange: S swell (shadowed from North Shore)
        buoy_trend = BuoyTrend(
            buoy_id="51002",
            buoy_name="South Hawaii",
            height_trend=TrendType.INCREASING_STRONG,
            height_slope=0.12,
            height_current=5.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=16.0,
            direction_trend=TrendType.STEADY,
            direction_current=180.0,  # S (shadowed from N Shore)
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="S swell building"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: North Shore gets small forecast (shadowed)
        north = shore_forecasts["north_shore"]
        assert "1-" in north["size_range"] or "2-" in north["size_range"]
        # South Shore gets large forecast
        south = shore_forecasts["south_shore"]
        size_parts = south["size_range"].replace("ft", "").split("-")
        min_size = int(size_parts[0])
        assert min_size >= 3  # Should be larger

    def test_generate_shore_forecasts_multiple_overlapping_swells(self, senior_forecaster):
        """Test shore forecast with multiple overlapping swells."""
        # Arrange: NW and N swells (both hit North Shore)
        trends = [
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.INCREASING_MODERATE,
                height_slope=0.08,
                height_current=3.5,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=14.0,
                direction_trend=TrendType.STEADY,
                direction_current=315.0,  # NW
                observations_count=10,
            ),
            BuoyTrend(
                buoy_id="51005",
                buoy_name="North Hawaii",
                height_trend=TrendType.INCREASING_MODERATE,
                height_slope=0.08,
                height_current=3.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=13.0,
                direction_trend=TrendType.STEADY,
                direction_current=0.0,  # N
                observations_count=10,
            ),
        ]

        buoy_data = BuoyAnalystData(
            trends=trends,
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID, "51005": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.85,
                height_agreement=0.85,
                period_agreement=0.85,
                num_buoys_compared=2,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Multiple N sector swells"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: North Shore forecast reflects multiple swells
        north = shore_forecasts["north_shore"]
        assert "size_range" in north
        # Size should be larger due to multiple swells

    def test_generate_shore_forecasts_size_range_formatting(
        self, senior_forecaster, sample_buoy_analysis
    ):
        """Test size range formatting in shore forecasts."""
        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            sample_buoy_analysis, None, {}, {"season": "winter"}
        )

        # Assert: Size range properly formatted
        for shore, forecast in shore_forecasts.items():
            size_range = forecast["size_range"]
            assert "ft" in size_range
            assert "-" in size_range
            # Extract numbers
            parts = size_range.replace("ft", "").split("-")
            assert len(parts) == 2
            min_size = int(parts[0])
            max_size = int(parts[1])
            assert min_size > 0
            assert max_size > min_size

    def test_generate_shore_forecasts_quality_descriptors(self, senior_forecaster):
        """Test quality descriptors in shore forecasts."""
        # Arrange: Long-period groundswell
        buoy_trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=4.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=16.0,  # Long period = clean
            direction_trend=TrendType.STEADY,
            direction_current=315.0,
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Long-period groundswell"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: North Shore has quality descriptor
        north = shore_forecasts["north_shore"]
        assert "conditions" in north
        assert north["conditions"] in [
            "clean",
            "fair",
            "choppy",
            "mixed and choppy",
            "fair to choppy",
            "small and clean",
        ]

    def test_generate_shore_forecasts_timing_descriptors(self, senior_forecaster):
        """Test timing descriptors in shore forecasts."""
        # Arrange: Building trend
        buoy_trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.INCREASING_STRONG,
            height_slope=0.15,
            height_current=3.0,
            period_trend=TrendType.INCREASING_MODERATE,
            period_slope=0.08,
            period_current=13.0,
            direction_trend=TrendType.STEADY,
            direction_current=315.0,
            observations_count=10,
        )

        buoy_data = BuoyAnalystData(
            trends=[buoy_trend],
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.9,
                height_agreement=0.9,
                period_agreement=0.9,
                num_buoys_compared=1,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Swell building"
        )

        shore_data = {}
        seasonal_context = {"season": "winter"}

        # Act
        shore_forecasts = senior_forecaster._generate_shore_forecasts(
            buoy_analysis, None, shore_data, seasonal_context
        )

        # Assert: North Shore has timing descriptor
        north = shore_forecasts["north_shore"]
        assert "timing" in north
        assert isinstance(north["timing"], str)
        assert len(north["timing"]) > 0


# =============================================================================
# SWELL BREAKDOWN SYNTHESIS TESTS (6 tests)
# =============================================================================


class TestSeniorForecasterSwellBreakdown:
    """Tests for swell breakdown synthesis functionality."""

    def test_generate_swell_breakdown_single_dominant_swell(
        self, senior_forecaster, sample_buoy_analysis
    ):
        """Test swell breakdown with single dominant swell."""
        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(sample_buoy_analysis, None)

        # Assert: At least one swell in breakdown
        assert len(swell_breakdown) >= 1
        swell = swell_breakdown[0]
        assert "direction" in swell
        assert "period" in swell
        assert "height" in swell
        assert "timing" in swell
        assert "confidence" in swell
        assert "source" in swell
        assert "has_buoy_confirmation" in swell

    def test_generate_swell_breakdown_multiple_concurrent_swells(self, senior_forecaster):
        """Test swell breakdown with multiple concurrent swells."""
        # Arrange: Multiple buoy trends
        trends = [
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.INCREASING_MODERATE,
                height_slope=0.08,
                height_current=3.5,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=14.0,
                direction_trend=TrendType.STEADY,
                direction_current=315.0,  # NW
                observations_count=10,
            ),
            BuoyTrend(
                buoy_id="51002",
                buoy_name="South Hawaii",
                height_trend=TrendType.STEADY,
                height_slope=0.0,
                height_current=2.5,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=15.0,
                direction_trend=TrendType.STEADY,
                direction_current=180.0,  # S
                observations_count=10,
            ),
        ]

        buoy_data = BuoyAnalystData(
            trends=trends,
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID, "51002": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.85,
                height_agreement=0.85,
                period_agreement=0.85,
                num_buoys_compared=2,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Multiple swells"
        )

        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(buoy_analysis, None)

        # Assert: Multiple swells in breakdown
        assert len(swell_breakdown) >= 2

    def test_generate_swell_breakdown_primary_and_secondary_swells(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test swell breakdown with primary and secondary swells."""
        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(
            sample_buoy_analysis, sample_pressure_analysis
        )

        # Assert: Swells sorted by confidence
        assert len(swell_breakdown) >= 1
        confidences = [s["confidence"] for s in swell_breakdown]
        # Check sorted (descending)
        assert confidences == sorted(confidences, reverse=True)

    def test_generate_swell_breakdown_overlapping_periods(self, senior_forecaster):
        """Test swell breakdown with overlapping periods."""
        # Arrange: Two swells with similar periods but different directions
        trends = [
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.STEADY,
                height_slope=0.0,
                height_current=3.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=13.5,  # Similar period
                direction_trend=TrendType.STEADY,
                direction_current=315.0,  # NW
                observations_count=10,
            ),
            BuoyTrend(
                buoy_id="51005",
                buoy_name="North Hawaii",
                height_trend=TrendType.STEADY,
                height_slope=0.0,
                height_current=2.8,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                period_current=13.8,  # Similar period
                direction_trend=TrendType.STEADY,
                direction_current=0.0,  # N
                observations_count=10,
            ),
        ]

        buoy_data = BuoyAnalystData(
            trends=trends,
            anomalies=[],
            quality_flags={"51001": QualityFlag.VALID, "51005": QualityFlag.VALID},
            cross_validation=CrossValidation(
                agreement_score=0.85,
                height_agreement=0.85,
                period_agreement=0.85,
                num_buoys_compared=2,
                interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(
            confidence=0.85, data=buoy_data, narrative="Overlapping swells"
        )

        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(buoy_analysis, None)

        # Assert: Both swells present despite overlapping periods
        assert len(swell_breakdown) >= 2
        directions = [s["direction"] for s in swell_breakdown]
        # Should have different directions
        assert len(set(directions)) >= 2

    def test_generate_swell_breakdown_direction_grouping(self, senior_forecaster):
        """Test direction grouping in swell breakdown (NW + N = Northwest sector)."""
        # Arrange: NW and NNW swells (close directions)
        predicted_swells = [
            PredictedSwell(
                source_system="low_45N_165W",
                source_lat=45.0,
                source_lon=-165.0,
                direction="NW",
                direction_degrees=315,
                arrival_time="2025-10-12T18:00Z",
                estimated_height="6-8ft",
                estimated_period="13-15s",
                confidence=0.75,
            ),
            PredictedSwell(
                source_system="low_48N_168W",
                source_lat=48.0,
                source_lon=-168.0,
                direction="NNW",
                direction_degrees=330,
                arrival_time="2025-10-12T20:00Z",
                estimated_height="5-7ft",
                estimated_period="12-14s",
                confidence=0.70,
            ),
        ]

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=predicted_swells,
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=2,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.80, data=pressure_data, narrative="NW sector swells"
        )

        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(None, pressure_analysis)

        # Assert: Both swells in breakdown
        assert len(swell_breakdown) >= 2

    def test_generate_swell_breakdown_no_swell_data(self, senior_forecaster):
        """Test swell breakdown with no swell data (edge case)."""
        # Arrange: Empty data
        buoy_data = BuoyAnalystData(
            trends=[],
            anomalies=[],
            quality_flags={},
            cross_validation=CrossValidation(
                agreement_score=0.5,
                height_agreement=0.5,
                period_agreement=0.5,
                num_buoys_compared=0,
                interpretation=AgreementLevel.MODERATE_AGREEMENT,
            ),
            summary_stats=SummaryStats(),
        )

        buoy_analysis = BuoyAnalystOutput(confidence=0.50, data=buoy_data, narrative="No data")

        pressure_data = PressureAnalystData(
            systems=[],
            predicted_swells=[],
            frontal_boundaries=[],
            analysis_summary=AnalysisSummary(
                num_low_pressure=0,
                num_high_pressure=0,
                num_predicted_swells=0,
                region="North Pacific",
            ),
        )

        pressure_analysis = PressureAnalystOutput(
            confidence=0.50, data=pressure_data, narrative="No predictions"
        )

        # Act
        swell_breakdown = senior_forecaster._generate_swell_breakdown(
            buoy_analysis, pressure_analysis
        )

        # Assert: Empty breakdown
        assert len(swell_breakdown) == 0


# =============================================================================
# DIRECTION MATCHING LOGIC TESTS (4 tests)
# =============================================================================


class TestSeniorForecasterDirectionMatching:
    """Tests for direction matching logic functionality."""

    def test_directions_match_exact_match(self, senior_forecaster):
        """Test exact direction match."""
        # Act
        result = senior_forecaster._directions_match("315", "315", tolerance=30.0)

        # Assert: Exact match
        assert result is True

    def test_directions_match_within_tolerance(self, senior_forecaster):
        """Test direction match within tolerance (±15°)."""
        # Act: 315° and 330° are 15° apart
        result = senior_forecaster._directions_match("315", "330", tolerance=30.0)

        # Assert: Within tolerance
        assert result is True

    def test_directions_match_outside_tolerance(self, senior_forecaster):
        """Test direction mismatch outside tolerance."""
        # Act: 315° (NW) and 180° (S) are 135° apart
        result = senior_forecaster._directions_match("315", "180", tolerance=30.0)

        # Assert: Outside tolerance
        assert result is False

    def test_directions_match_wrapping_360(self, senior_forecaster):
        """Test directional wrapping (350° matches 10°)."""
        # Act: 350° and 10° are 20° apart (wrapping around 0°)
        result = senior_forecaster._directions_match("350", "10", tolerance=30.0)

        # Assert: Wrapping works correctly
        assert result is True


# =============================================================================
# TIMING ANALYSIS TESTS (4 tests)
# =============================================================================


class TestSeniorForecasterTimingAnalysis:
    """Tests for timing analysis functionality."""

    def test_is_future_arrival_more_than_12_hours(self, senior_forecaster):
        """Test future arrival detection (>12 hours out)."""
        # Arrange: Swell arriving 24 hours from now
        future_time = (datetime.now() + timedelta(hours=24)).isoformat() + "Z"
        swell = {"arrival_time": future_time}

        # Act
        result = senior_forecaster._is_future_arrival(swell)

        # Assert: Future arrival
        assert result is True

    def test_is_near_arrival_within_12_hours(self, senior_forecaster):
        """Test near arrival detection (0-12 hours)."""
        # Arrange: Swell arriving 6 hours from now
        near_time = (datetime.now() + timedelta(hours=6)).isoformat() + "Z"
        swell = {"arrival_time": near_time}

        # Act
        result = senior_forecaster._is_near_arrival(swell, hours_threshold=12.0)

        # Assert: Near arrival
        assert result is True

    def test_is_currently_arrived_negative_time(self, senior_forecaster):
        """Test currently arrived detection (negative time)."""
        # Arrange: Swell that arrived 3 hours ago
        past_time = (datetime.now() - timedelta(hours=3)).isoformat() + "Z"
        swell = {"arrival_time": past_time}

        # Act
        future = senior_forecaster._is_future_arrival(swell)
        near = senior_forecaster._is_near_arrival(swell, hours_threshold=12.0)

        # Assert: Not future, not near (already arrived)
        assert future is False
        assert near is False

    def test_is_near_arrival_exactly_at_threshold(self, senior_forecaster):
        """Test edge case: exactly at threshold."""
        # Arrange: Swell arriving exactly 12 hours from now
        threshold_time = (datetime.now() + timedelta(hours=12)).isoformat() + "Z"
        swell = {"arrival_time": threshold_time}

        # Act
        result = senior_forecaster._is_near_arrival(swell, hours_threshold=12.0)

        # Assert: At threshold = near arrival
        assert result is True


# =============================================================================
# INTEGRATION/WORKFLOW TESTS (4 tests)
# =============================================================================


class TestSeniorForecasterIntegration:
    """Integration tests for complete analyze() workflow."""

    @pytest.mark.asyncio
    async def test_analyze_complete_workflow_with_all_specialists(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test complete workflow with all specialists (Pydantic models)."""
        # Arrange
        data = SeniorForecasterInput(
            buoy_analysis=sample_buoy_analysis,
            pressure_analysis=sample_pressure_analysis,
            swell_events=[],
            shore_data={},
            seasonal_context={"season": "winter"},
            metadata={"forecast_date": "2025-10-12", "valid_period": "48hr"},
        )

        # Act
        result = await senior_forecaster.analyze(data)

        # Assert: Returns SeniorForecasterOutput
        assert isinstance(result, SeniorForecasterOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert result.data is not None
        assert result.data.synthesis is not None
        assert result.data.shore_forecasts is not None
        assert result.data.swell_breakdown is not None
        assert result.narrative is not None
        assert len(result.narrative) > 0
        assert "specialists_used" in result.metadata

    @pytest.mark.asyncio
    async def test_analyze_workflow_with_missing_buoy_analyst(
        self, senior_forecaster, sample_pressure_analysis
    ):
        """Test workflow with missing BuoyAnalyst (pressure only)."""
        # Arrange: Only pressure analysis (below minimum required)
        data = {
            "buoy_analysis": None,
            "pressure_analysis": sample_pressure_analysis,
            "swell_events": [],
            "shore_data": {},
            "seasonal_context": {"season": "winter"},
            "metadata": {"forecast_date": "2025-10-12"},
        }

        # Act & Assert: Raises ValueError (insufficient specialists)
        with pytest.raises(ValueError, match="Insufficient specialists"):
            await senior_forecaster.analyze(data)

    @pytest.mark.asyncio
    async def test_analyze_workflow_with_missing_pressure_analyst(
        self, senior_forecaster, sample_buoy_analysis
    ):
        """Test workflow with missing PressureAnalyst (buoy only)."""
        # Arrange: Only buoy analysis (below minimum required)
        data = {
            "buoy_analysis": sample_buoy_analysis,
            "pressure_analysis": None,
            "swell_events": [],
            "shore_data": {},
            "seasonal_context": {"season": "winter"},
            "metadata": {"forecast_date": "2025-10-12"},
        }

        # Act & Assert: Raises ValueError (insufficient specialists)
        with pytest.raises(ValueError, match="Insufficient specialists"):
            await senior_forecaster.analyze(data)

    @pytest.mark.asyncio
    async def test_analyze_workflow_returns_required_fields(
        self, senior_forecaster, sample_buoy_analysis, sample_pressure_analysis
    ):
        """Test workflow returns SeniorForecasterOutput with all required fields."""
        # Arrange
        data = {
            "buoy_analysis": sample_buoy_analysis,
            "pressure_analysis": sample_pressure_analysis,
            "swell_events": [],
            "shore_data": {},
            "seasonal_context": {"season": "winter"},
            "metadata": {"forecast_date": "2025-10-12"},
        }

        # Act
        result = await senior_forecaster.analyze(data)

        # Assert: All required Pydantic fields present
        assert hasattr(result, "confidence")
        assert hasattr(result, "data")
        assert hasattr(result, "narrative")
        assert hasattr(result, "metadata")
        # Check nested data structure
        assert hasattr(result.data, "synthesis")
        assert hasattr(result.data, "shore_forecasts")
        assert hasattr(result.data, "swell_breakdown")
        # Check synthesis structure
        assert hasattr(result.data.synthesis, "specialist_agreement")
        assert hasattr(result.data.synthesis, "contradictions")
        assert hasattr(result.data.synthesis, "key_findings")


# =============================================================================
# INITIALIZATION TESTS (2 tests)
# =============================================================================


class TestSeniorForecasterInitialization:
    """Tests for SeniorForecaster initialization."""

    def test_initialization_requires_engine(self, mock_config):
        """Test that SeniorForecaster requires engine parameter."""
        # Act & Assert: Missing engine raises ValueError
        with pytest.raises(ValueError, match="requires engine parameter"):
            SeniorForecaster(config=mock_config, model_name="gpt-4o-mini", engine=None)

    def test_initialization_success(self, mock_config, mock_engine):
        """Test successful initialization with all required parameters."""
        # Act
        forecaster = SeniorForecaster(
            config=mock_config, model_name="gpt-4o-mini", engine=mock_engine
        )

        # Assert
        assert forecaster.model_name == "gpt-4o-mini"
        assert forecaster.engine == mock_engine
        assert forecaster.min_specialists_required == 2
        assert forecaster.max_tokens == 2000


# =============================================================================
# DICT-TO-PYDANTIC COMPATIBILITY TESTS (2 tests)
# =============================================================================


class TestSeniorForecasterDictCompatibility:
    """Tests for backward compatibility with dict inputs."""

    @pytest.mark.asyncio
    async def test_analyze_accepts_dict_buoy_analysis(
        self, senior_forecaster, sample_dict_buoy_analysis, sample_pressure_analysis
    ):
        """Test analyze accepts dict format buoy analysis (legacy compatibility)."""
        # Arrange
        data = {
            "buoy_analysis": sample_dict_buoy_analysis,
            "pressure_analysis": sample_pressure_analysis,
            "swell_events": [],
            "shore_data": {},
            "seasonal_context": {"season": "winter"},
            "metadata": {"forecast_date": "2025-10-12"},
        }

        # Act
        result = await senior_forecaster.analyze(data)

        # Assert: Successfully processes dict input
        assert isinstance(result, SeniorForecasterOutput)
        assert result.confidence > 0.0

    @pytest.mark.asyncio
    async def test_analyze_accepts_dict_pressure_analysis(
        self, senior_forecaster, sample_buoy_analysis, sample_dict_pressure_analysis
    ):
        """Test analyze accepts dict format pressure analysis (legacy compatibility)."""
        # Arrange
        data = {
            "buoy_analysis": sample_buoy_analysis,
            "pressure_analysis": sample_dict_pressure_analysis,
            "swell_events": [],
            "shore_data": {},
            "seasonal_context": {"season": "winter"},
            "metadata": {"forecast_date": "2025-10-12"},
        }

        # Act
        result = await senior_forecaster.analyze(data)

        # Assert: Successfully processes dict input
        assert isinstance(result, SeniorForecasterOutput)
        assert result.confidence > 0.0
