"""
Pydantic schemas for specialist data contracts.

This module defines explicit data contracts between specialists to replace
unstructured dictionaries with validated, self-documenting models.

All specialists (BuoyAnalyst, PressureAnalyst, SeniorForecaster) should use
these schemas for their output data to ensure consistency, validation, and
type safety throughout the forecasting pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# ENUMS (String Literals for Type Safety)
# =============================================================================


class TrendType(str, Enum):
    """Types of trends detected in time-series data."""

    STEADY = "steady"
    INCREASING_STRONG = "increasing_strong"
    INCREASING_MODERATE = "increasing_moderate"
    INCREASING_SLIGHT = "increasing_slight"
    DECREASING_STRONG = "decreasing_strong"
    DECREASING_MODERATE = "decreasing_moderate"
    DECREASING_SLIGHT = "decreasing_slight"
    INSUFFICIENT_DATA = "insufficient_data"


class SeverityLevel(str, Enum):
    """Severity levels for anomalies and issues."""

    HIGH = "high"
    MODERATE = "moderate"


class QualityFlag(str, Enum):
    """Quality flags for data validation."""

    EXCLUDED = "excluded"
    SUSPECT = "suspect"
    VALID = "valid"


class AgreementLevel(str, Enum):
    """Levels of agreement between data sources."""

    EXCELLENT_AGREEMENT = "excellent_agreement"
    GOOD_AGREEMENT = "good_agreement"
    MODERATE_AGREEMENT = "moderate_agreement"
    POOR_AGREEMENT = "poor_agreement"
    VERY_POOR_AGREEMENT = "very_poor_agreement"


class SystemType(str, Enum):
    """Types of weather systems."""

    LOW_PRESSURE = "low_pressure"
    HIGH_PRESSURE = "high_pressure"


class FrontType(str, Enum):
    """Types of frontal boundaries."""

    COLD_FRONT = "cold_front"
    WARM_FRONT = "warm_front"


class FetchQuality(str, Enum):
    """Quality assessment of fetch windows."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class IntensificationTrend(str, Enum):
    """Trend in weather system intensity."""

    STRENGTHENING = "strengthening"
    WEAKENING = "weakening"
    STEADY = "steady"


class ImpactLevel(str, Enum):
    """Impact level for contradictions and issues."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ShoreConditions(str, Enum):
    """Surf conditions descriptions."""

    CLEAN = "clean"
    FAIR = "fair"
    CHOPPY = "choppy"
    MIXED_AND_CHOPPY = "mixed and choppy"
    FAIR_TO_CHOPPY = "fair to choppy"
    SMALL_AND_CLEAN = "small and clean"


# =============================================================================
# BUOY ANALYST MODELS
# =============================================================================


class BuoyTrend(BaseModel):
    """
    Trend analysis for a single buoy station.

    Captures wave height, period, and direction trends over time,
    along with current conditions and observation metadata.
    """

    buoy_id: str = Field(..., description="Buoy station identifier")
    buoy_name: str = Field(..., description="Human-readable buoy name")
    height_trend: TrendType = Field(..., description="Wave height trend classification")
    height_slope: float = Field(..., description="Linear slope of height trend (m/observation)")
    height_current: float | None = Field(None, description="Current wave height in meters")
    period_trend: TrendType = Field(..., description="Wave period trend classification")
    period_slope: float = Field(..., description="Linear slope of period trend (s/observation)")
    period_current: float | None = Field(None, description="Current dominant period in seconds")
    direction_trend: TrendType = Field(..., description="Wave direction trend classification")
    direction_current: float | None = Field(
        None, description="Current wave direction in degrees (0-360)"
    )
    observations_count: int = Field(..., ge=0, description="Number of observations analyzed")

    @field_validator("height_slope", "period_slope")
    @classmethod
    def round_slope(cls, v: float) -> float:
        """Round slope values to 4 decimal places."""
        return round(v, 4)

    @field_validator("height_current", "period_current")
    @classmethod
    def round_measurements(cls, v: float | None) -> float | None:
        """Round measurement values to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @field_validator("direction_current")
    @classmethod
    def validate_direction(cls, v: float | None) -> float | None:
        """Validate direction is within 0-360 degrees."""
        if v is not None and not (0 <= v <= 360):
            raise ValueError(f"Direction must be between 0 and 360 degrees, got {v}")
        return v


class BuoyAnomaly(BaseModel):
    """
    Detected anomaly in buoy data.

    Uses Z-score analysis to identify statistical outliers in wave height
    or period measurements that may indicate data quality issues.
    """

    buoy_id: str = Field(..., description="Buoy station identifier")
    buoy_name: str = Field(..., description="Human-readable buoy name")
    issue: str = Field(..., description="Type of anomaly (e.g., 'wave_height_anomaly')")
    severity: SeverityLevel = Field(..., description="Severity of the anomaly")
    details: str = Field(..., description="Human-readable description of the anomaly")
    z_score: float = Field(..., description="Z-score of the anomalous value")

    @field_validator("z_score")
    @classmethod
    def round_z_score(cls, v: float) -> float:
        """Round Z-score to 2 decimal places."""
        return round(v, 2)


class CrossValidation(BaseModel):
    """
    Cross-validation metrics between buoys.

    Measures agreement between multiple buoy stations to assess
    data reliability and consistency.
    """

    agreement_score: float = Field(..., ge=0.0, le=1.0, description="Overall agreement score (0-1)")
    height_agreement: float = Field(..., ge=0.0, le=1.0, description="Wave height agreement score")
    period_agreement: float = Field(..., ge=0.0, le=1.0, description="Wave period agreement score")
    num_buoys_compared: int = Field(..., ge=0, description="Number of buoys in comparison")
    interpretation: AgreementLevel = Field(
        ..., description="Qualitative interpretation of agreement"
    )

    @field_validator("agreement_score", "height_agreement", "period_agreement")
    @classmethod
    def round_scores(cls, v: float) -> float:
        """Round agreement scores to 3 decimal places."""
        return round(v, 3)


class SummaryStats(BaseModel):
    """
    Summary statistics across all buoy observations.

    Provides aggregate wave height and period statistics for
    overall swell characterization.
    """

    avg_wave_height: float | None = Field(None, description="Average wave height in meters")
    max_wave_height: float | None = Field(None, description="Maximum wave height in meters")
    min_wave_height: float | None = Field(None, description="Minimum wave height in meters")
    avg_period: float | None = Field(None, description="Average dominant period in seconds")
    max_period: float | None = Field(None, description="Maximum period in seconds")
    min_period: float | None = Field(None, description="Minimum period in seconds")

    @field_validator(
        "avg_wave_height",
        "max_wave_height",
        "min_wave_height",
        "avg_period",
        "max_period",
        "min_period",
    )
    @classmethod
    def round_stats(cls, v: float | None) -> float | None:
        """Round statistics to 2 decimal places."""
        return round(v, 2) if v is not None else None


class BuoyAnalystData(BaseModel):
    """
    Structured data output from BuoyAnalyst.

    Contains all analytical results including trends, anomalies,
    quality assessments, and summary statistics.
    """

    trends: list[BuoyTrend] = Field(
        default_factory=list, description="Trend analysis for each buoy"
    )
    anomalies: list[BuoyAnomaly] = Field(
        default_factory=list, description="Detected data anomalies"
    )
    quality_flags: dict[str, QualityFlag] = Field(
        default_factory=dict, description="Quality flags for each buoy (buoy_id -> flag)"
    )
    cross_validation: CrossValidation = Field(..., description="Cross-buoy validation metrics")
    summary_stats: SummaryStats = Field(..., description="Aggregate statistics")


class BuoyAnalystOutput(BaseModel):
    """
    Complete output from BuoyAnalyst specialist.

    Includes confidence score, structured data, AI-generated narrative,
    and processing metadata.
    """

    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall analysis confidence (0-1)")
    data: BuoyAnalystData = Field(..., description="Structured analytical results")
    narrative: str = Field(
        ..., min_length=1, description="AI-generated analysis narrative (500-1000 words)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Analysis metadata and provenance"
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 3 decimal places."""
        return round(v, 3)


# =============================================================================
# PRESSURE ANALYST MODELS
# =============================================================================


class FetchWindow(BaseModel):
    """
    Fetch window characteristics for swell generation.

    Describes the area where winds blow consistently over distance
    toward Hawaii, generating swell energy.
    """

    direction: str = Field(..., description="Fetch direction relative to Hawaii (e.g., 'NNE')")
    distance_nm: float = Field(..., ge=0, description="Distance to fetch in nautical miles")
    duration_hrs: float = Field(..., ge=0, description="Duration of sustained winds in hours")
    fetch_length_nm: float = Field(
        ..., ge=0, description="Length of fetch window in nautical miles"
    )
    quality: FetchQuality = Field(..., description="Quality assessment of fetch")

    @field_validator("distance_nm", "duration_hrs", "fetch_length_nm")
    @classmethod
    def round_fetch_metrics(cls, v: float) -> float:
        """Round fetch metrics to 1 decimal place."""
        return round(v, 1)


class WeatherSystem(BaseModel):
    """
    Weather system identified in pressure charts.

    Represents low or high pressure systems with their characteristics,
    movement, and swell generation potential.
    """

    type: SystemType = Field(..., description="Type of weather system")
    location: str = Field(..., description="Location as string (e.g., '45N 160W')")
    location_lat: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    location_lon: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    pressure_mb: int | None = Field(None, description="Central pressure in millibars")
    wind_speed_kt: int | None = Field(None, ge=0, description="Wind speed in knots")
    movement: str = Field(..., description="System movement (e.g., 'SE at 25kt')")
    intensification: IntensificationTrend = Field(..., description="Intensity trend")
    generation_time: str | None = Field(None, description="ISO timestamp of swell generation")
    fetch: FetchWindow | None = Field(None, description="Associated fetch window")

    @field_validator("generation_time")
    @classmethod
    def validate_timestamp(cls, v: str | None) -> str | None:
        """Validate ISO timestamp format if provided."""
        if v is not None:
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Invalid ISO timestamp: {v}")
        return v


class PredictedSwell(BaseModel):
    """
    Predicted swell with enhanced physics-based calculations.

    Combines vision API predictions with wave physics calculations
    for arrival timing, travel distance, and source attribution.
    """

    # Core predictions from vision API
    source_system: str = Field(..., description="Identifier of source weather system")
    source_lat: float = Field(..., ge=-90, le=90, description="Source latitude in degrees")
    source_lon: float = Field(..., ge=-180, le=180, description="Source longitude in degrees")
    direction: str = Field(..., description="Arrival direction at Hawaii (e.g., 'NNE')")
    direction_degrees: int | None = Field(
        None, ge=0, le=360, description="Direction in degrees (0=N, 90=E)"
    )
    arrival_time: str = Field(..., description="Estimated arrival time window")
    estimated_height: str = Field(..., description="Wave height range (e.g., '7-9ft')")
    estimated_period: str = Field(..., description="Period range (e.g., '13-15s')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Prediction confidence (0-1)")

    # Enhanced fields from physics calculations
    calculated_arrival: str | None = Field(None, description="Physics-based arrival time (ISO)")
    travel_time_hrs: float | None = Field(None, ge=0, description="Travel time in hours")
    distance_nm: float | None = Field(
        None, ge=0, description="Great circle distance in nautical miles"
    )
    group_velocity_knots: float | None = Field(None, ge=0, description="Group velocity in knots")
    propagation_method: str | None = Field(
        None, description="Calculation method (e.g., 'physics_based')"
    )

    # Source system characteristics
    fetch_quality: FetchQuality | None = Field(None, description="Quality of generating fetch")
    fetch_duration_hrs: float | None = Field(None, ge=0, description="Fetch duration in hours")
    fetch_length_nm: float | None = Field(
        None, ge=0, description="Fetch length in nautical miles"
    )
    source_pressure_mb: int | None = Field(
        None, description="Source system pressure in millibars"
    )
    source_wind_speed_kt: int | None = Field(
        None, ge=0, description="Source system wind speed in knots"
    )
    source_trend: IntensificationTrend | None = Field(
        None, description="Source system intensity trend"
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 2 decimal places."""
        return round(v, 2)

    @field_validator(
        "travel_time_hrs",
        "distance_nm",
        "group_velocity_knots",
        "fetch_duration_hrs",
        "fetch_length_nm",
    )
    @classmethod
    def round_physics_metrics(cls, v: float | None) -> float | None:
        """Round physics metrics to 1 decimal place."""
        return round(v, 1) if v is not None else None


class FrontalBoundary(BaseModel):
    """
    Frontal boundary identification from pressure charts.

    Represents cold or warm fronts that may impact local conditions.
    """

    type: FrontType = Field(..., description="Type of frontal boundary")
    location: str = Field(..., description="Location description (e.g., 'approaching from NW')")
    timing: str = Field(..., description="Expected timing (ISO timestamp or description)")


class AnalysisSummary(BaseModel):
    """
    Summary of pressure chart analysis.

    High-level counts and regional context.
    """

    num_low_pressure: int = Field(..., ge=0, description="Number of low-pressure systems")
    num_high_pressure: int = Field(..., ge=0, description="Number of high-pressure systems")
    num_predicted_swells: int = Field(..., ge=0, description="Number of predicted swells")
    region: str = Field(..., description="Geographic region analyzed (e.g., 'North Pacific')")


class PressureAnalystData(BaseModel):
    """
    Structured data output from PressureAnalyst.

    Contains weather systems, swell predictions, frontal boundaries,
    and analysis summary.
    """

    systems: list[WeatherSystem] = Field(
        default_factory=list, description="Identified weather systems"
    )
    predicted_swells: list[PredictedSwell] = Field(
        default_factory=list, description="Predicted swell arrivals"
    )
    frontal_boundaries: list[FrontalBoundary] = Field(
        default_factory=list, description="Frontal boundaries"
    )
    analysis_summary: AnalysisSummary = Field(..., description="Analysis summary")


class PressureAnalystOutput(BaseModel):
    """
    Complete output from PressureAnalyst specialist.

    Includes confidence score, structured data, AI-generated narrative,
    and processing metadata.
    """

    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall analysis confidence (0-1)")
    data: PressureAnalystData = Field(..., description="Structured analytical results")
    narrative: str = Field(
        ..., min_length=1, description="AI-generated analysis narrative (500-1000 words)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Analysis metadata and provenance"
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 3 decimal places."""
        return round(v, 3)


# =============================================================================
# SENIOR FORECASTER MODELS
# =============================================================================


class Contradiction(BaseModel):
    """
    Contradiction detected between specialist reports.

    Identifies conflicts between BuoyAnalyst and PressureAnalyst
    findings, with resolution strategy and impact assessment.
    """

    issue: str = Field(..., description="Description of the contradiction")
    resolution: str = Field(..., description="Proposed resolution or explanation")
    impact: ImpactLevel = Field(..., description="Impact level of the contradiction")
    buoy_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Buoy analyst confidence"
    )
    pressure_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Pressure analyst confidence"
    )
    swell_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Swell-specific confidence"
    )
    timing: str | None = Field(None, description="Timing context for the contradiction")

    @field_validator("buoy_confidence", "pressure_confidence", "swell_confidence")
    @classmethod
    def round_confidences(cls, v: float | None) -> float | None:
        """Round confidence values to 2 decimal places."""
        return round(v, 2) if v is not None else None


class Synthesis(BaseModel):
    """
    Synthesis of specialist findings.

    Captures agreement levels, contradictions, and key findings
    from cross-validation of specialist reports.
    """

    specialist_agreement: float = Field(
        ..., ge=0.0, le=1.0, description="Agreement score between specialists"
    )
    contradictions: list[Contradiction] = Field(
        default_factory=list, description="Detected contradictions"
    )
    key_findings: list[str] = Field(default_factory=list, description="Key findings from synthesis")

    @field_validator("specialist_agreement")
    @classmethod
    def round_agreement(cls, v: float) -> float:
        """Round agreement score to 3 decimal places."""
        return round(v, 3)


class ShoreForecast(BaseModel):
    """
    Shore-specific forecast.

    Provides size, conditions, timing, and confidence for a specific
    shore (North, South, East, or West).
    """

    size_range: str = Field(..., description="Predicted size range (e.g., '6-8ft')")
    conditions: str = Field(..., description="Conditions description (e.g., 'clean', 'choppy')")
    timing: str = Field(..., description="Timing of swell activity")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Forecast confidence (0-1)")

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 2 decimal places."""
        return round(v, 2)


class SwellBreakdown(BaseModel):
    """
    Detailed swell component breakdown.

    Merges buoy observations and pressure predictions for each
    swell direction, with source attribution and confirmation status.
    """

    direction: str = Field(..., description="Swell direction (compass or degrees)")
    period: str = Field(..., description="Period or period range (e.g., '13-15s')")
    height: str = Field(..., description="Height or height range (e.g., '7-9ft')")
    timing: str = Field(..., description="Arrival timing or current status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Swell confidence (0-1)")
    source: str = Field(..., description="Source attribution (e.g., 'low_45N_160W')")
    has_pressure_support: bool = Field(
        ..., description="Whether pressure analysis supports this swell"
    )
    has_buoy_confirmation: bool = Field(..., description="Whether buoys confirm this swell")
    buoy_height: str | None = Field(None, description="Buoy-observed height (e.g., '2.5m')")
    buoy_period: str | None = Field(None, description="Buoy-observed period (e.g., '14s')")

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 2 decimal places."""
        return round(v, 2)


class SeniorForecasterData(BaseModel):
    """
    Structured data output from SeniorForecaster.

    Contains synthesis results, shore-specific forecasts, and
    detailed swell breakdown.
    """

    synthesis: Synthesis = Field(..., description="Cross-validation synthesis")
    shore_forecasts: dict[str, ShoreForecast] = Field(
        default_factory=dict, description="Shore-specific forecasts (shore_name -> forecast)"
    )
    swell_breakdown: list[SwellBreakdown] = Field(
        default_factory=list, description="Detailed swell components"
    )


class SeniorForecasterInput(BaseModel):
    """
    Input data for SeniorForecaster analysis.

    Aggregates outputs from BuoyAnalyst and PressureAnalyst along with
    contextual data for forecast synthesis.
    """

    buoy_analysis: BuoyAnalystOutput | None = Field(None, description="BuoyAnalyst output")
    pressure_analysis: PressureAnalystOutput | None = Field(
        None, description="PressureAnalyst output"
    )
    swell_events: list[dict[str, Any]] = Field(
        default_factory=list, description="Detected swell events from fusion system"
    )
    shore_data: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Shore-specific data (north_shore, south_shore, east_shore, west_shore)",
    )
    seasonal_context: dict[str, Any] = Field(
        default_factory=dict, description="Seasonal context (season, typical_patterns, climatology)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata (forecast_date, valid_period, bundle_id)"
    )


class SeniorForecasterOutput(BaseModel):
    """
    Complete output from SeniorForecaster specialist.

    Includes confidence score, structured data, Pat Caldwell-style narrative,
    and processing metadata.
    """

    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall forecast confidence (0-1)")
    data: SeniorForecasterData = Field(..., description="Structured forecast results")
    narrative: str = Field(
        ..., min_length=1, description="Pat Caldwell-style forecast narrative (500-800 words)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Forecast metadata and provenance"
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 3 decimal places."""
        return round(v, 3)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def validate_buoy_output(output: dict[str, Any]) -> BuoyAnalystOutput:
    """
    Validate and convert dictionary to BuoyAnalystOutput.

    Args:
        output: Dictionary from BuoyAnalyst.analyze()

    Returns:
        Validated BuoyAnalystOutput instance

    Raises:
        ValidationError: If validation fails
    """
    return BuoyAnalystOutput(**output)


def validate_pressure_output(output: dict[str, Any]) -> PressureAnalystOutput:
    """
    Validate and convert dictionary to PressureAnalystOutput.

    Args:
        output: Dictionary from PressureAnalyst.analyze()

    Returns:
        Validated PressureAnalystOutput instance

    Raises:
        ValidationError: If validation fails
    """
    return PressureAnalystOutput(**output)


def validate_senior_output(output: dict[str, Any]) -> SeniorForecasterOutput:
    """
    Validate and convert dictionary to SeniorForecasterOutput.

    Args:
        output: Dictionary from SeniorForecaster.analyze()

    Returns:
        Validated SeniorForecasterOutput instance

    Raises:
        ValidationError: If validation fails
    """
    return SeniorForecasterOutput(**output)
