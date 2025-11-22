"""
Source Scorer for SurfCastAI.

Assigns reliability scores to data sources based on multiple factors including
source tier, data freshness, completeness, and historical accuracy. This enables
data-driven weighting in the fusion pipeline.

Reference: CONSOLIDATION_EXECUTION_PLAN.md Phase 3, Task 3.1
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class SourceTier(Enum):
    """Source reliability tiers based on data quality and authority."""

    TIER_1 = 1.0  # Official NOAA/Government
    TIER_2 = 0.9  # Research/Academic
    TIER_3 = 0.7  # International Government
    TIER_4 = 0.5  # Commercial APIs
    TIER_5 = 0.3  # Surf Forecasting Sites


@dataclass
class ScoringWeights:
    """Weights for different scoring factors."""

    source_tier: float = 0.50  # Base reliability from tier
    data_freshness: float = 0.20  # Recency of data
    completeness: float = 0.20  # Fields present vs expected
    historical_accuracy: float = 0.10  # From validation results


@dataclass
class SourceScore:
    """Complete scoring information for a data source."""

    source_name: str
    overall_score: float
    tier_score: float
    freshness_score: float
    completeness_score: float
    accuracy_score: float
    tier: SourceTier
    metadata: dict[str, Any]


class SourceScorer:
    """
    Assigns reliability scores to data sources for weighted fusion.

    Features:
    - Five-tier reliability hierarchy (1.0 to 0.3)
    - Multi-factor scoring (tier, freshness, completeness, accuracy)
    - Transparent logging for auditability
    - Integration with data fusion system

    Scoring Formula:
    overall_score = (tier * 0.50) + (freshness * 0.20) +
                    (completeness * 0.20) + (accuracy * 0.10)
    """

    # Source tier mapping: source_name -> SourceTier
    SOURCE_TIER_MAP: dict[str, SourceTier] = {
        # Tier 1 (1.0) - Official NOAA/Government
        "ndbc": SourceTier.TIER_1,
        "ndbc_buoy": SourceTier.TIER_1,
        "noaa_buoy": SourceTier.TIER_1,
        # Specific NDBC Hawaii buoy stations (Tier 1 - Government/Scientific)
        "51001": SourceTier.TIER_1,  # NW Hawaii (24.4N 162.3W)
        "51002": SourceTier.TIER_1,  # SW Hawaii (17.2N 157.8W)
        "51003": SourceTier.TIER_1,  # West Hawaii (19.2N 160.7W)
        "51004": SourceTier.TIER_1,  # SE Hawaii (17.5N 152.4W)
        "51101": SourceTier.TIER_1,  # Hanalei, Kauai (22.1N 159.4W)
        "51201": SourceTier.TIER_1,  # Waimea Bay, Oahu (21.7N 158.1W)
        "51202": SourceTier.TIER_1,  # Mokapu Point, Oahu (21.4N 157.8W)
        "51207": SourceTier.TIER_1,  # Kauai (22.0N 160.2W)
        "51211": SourceTier.TIER_1,  # Hilo, Hawaii (19.7N 154.9W)
        "51212": SourceTier.TIER_1,  # Kaneohe, Oahu (21.5N 157.8W)
        "tgftp": SourceTier.TIER_1,
        "nws": SourceTier.TIER_1,
        "opc": SourceTier.TIER_1,
        "ocean_prediction_center": SourceTier.TIER_1,
        "nhc": SourceTier.TIER_1,
        "national_hurricane_center": SourceTier.TIER_1,
        "noaa": SourceTier.TIER_1,
        # Tier 2 (0.9) - Research/Academic
        "pacioos": SourceTier.TIER_2,
        "cdip": SourceTier.TIER_2,
        "cdip_buoy": SourceTier.TIER_2,
        "swan": SourceTier.TIER_2,
        "wavewatch3": SourceTier.TIER_2,
        "ww3": SourceTier.TIER_2,
        # Tier 3 (0.7) - International Government
        "ecmwf": SourceTier.TIER_3,
        "bom": SourceTier.TIER_3,
        "bureau_of_meteorology": SourceTier.TIER_3,
        "ukmo": SourceTier.TIER_3,
        "jma": SourceTier.TIER_3,
        # Tier 4 (0.5) - Commercial APIs
        "stormglass": SourceTier.TIER_4,
        "windy": SourceTier.TIER_4,
        "open_meteo": SourceTier.TIER_4,
        "openmeteo": SourceTier.TIER_4,
        "weatherapi": SourceTier.TIER_4,
        # Tier 5 (0.3) - Surf Forecasting Sites
        "surfline": SourceTier.TIER_5,
        "magicseaweed": SourceTier.TIER_5,
        "swellnet": SourceTier.TIER_5,
        "windfinder": SourceTier.TIER_5,
    }

    # Expected fields by data type for completeness scoring
    EXPECTED_FIELDS: dict[str, list[str]] = {
        "buoy": [
            "wave_height",
            "dominant_period",
            "wave_direction",
            "wind_speed",
            "wind_direction",
            "timestamp",
        ],
        "weather": ["temperature", "wind_speed", "wind_direction", "forecast_periods", "timestamp"],
        "model": [
            "wave_height",
            "wave_period",
            "wave_direction",
            "run_time",
            "forecast_hour",
            "points",
        ],
        "default": ["timestamp", "latitude", "longitude"],
    }

    def __init__(self, weights: ScoringWeights | None = None):
        """
        Initialize the source scorer.

        Args:
            weights: Optional custom scoring weights
        """
        self.logger = logging.getLogger("processing.source_scorer")
        self.weights = weights or ScoringWeights()
        self._validation_cache: dict[str, float] = {}

        self.logger.info(
            f"SourceScorer initialized with weights: "
            f"tier={self.weights.source_tier}, "
            f"freshness={self.weights.data_freshness}, "
            f"completeness={self.weights.completeness}, "
            f"accuracy={self.weights.historical_accuracy}"
        )

    def score_sources(self, fusion_data: dict[str, Any]) -> dict[str, SourceScore]:
        """
        Score all data sources in fusion input.

        Args:
            fusion_data: Data dictionary with buoy_data, weather_data, model_data

        Returns:
            Dictionary mapping source identifiers to SourceScore objects
        """
        scores = {}

        # Score buoy data sources
        for buoy_data in fusion_data.get("buoy_data", []):
            source_id = self._extract_source_id(buoy_data, "buoy")
            score = self.score_single_source(source_id, buoy_data, "buoy")
            scores[source_id] = score
            self.logger.info(
                f"Buoy source '{source_id}': {score.overall_score:.3f} "
                f"(tier={score.tier_score:.2f}, fresh={score.freshness_score:.2f}, "
                f"complete={score.completeness_score:.2f}, accuracy={score.accuracy_score:.2f})"
            )

        # Score weather data sources
        for weather_data in fusion_data.get("weather_data", []):
            source_id = self._extract_source_id(weather_data, "weather")
            score = self.score_single_source(source_id, weather_data, "weather")
            scores[source_id] = score
            self.logger.info(
                f"Weather source '{source_id}': {score.overall_score:.3f} "
                f"(tier={score.tier_score:.2f}, fresh={score.freshness_score:.2f}, "
                f"complete={score.completeness_score:.2f}, accuracy={score.accuracy_score:.2f})"
            )

        # Score model data sources
        for model_data in fusion_data.get("model_data", []):
            source_id = self._extract_source_id(model_data, "model")
            score = self.score_single_source(source_id, model_data, "model")
            scores[source_id] = score
            self.logger.info(
                f"Model source '{source_id}': {score.overall_score:.3f} "
                f"(tier={score.tier_score:.2f}, fresh={score.freshness_score:.2f}, "
                f"complete={score.completeness_score:.2f}, accuracy={score.accuracy_score:.2f})"
            )

        self.logger.info(f"Scored {len(scores)} data sources")
        return scores

    def score_single_source(
        self, source_name: str, data: Any, data_type: str = "default"
    ) -> SourceScore:
        """
        Calculate reliability score for a single data source.

        Args:
            source_name: Name/identifier of the data source
            data: The data object or dictionary
            data_type: Type of data (buoy, weather, model, default)

        Returns:
            SourceScore object with detailed scoring breakdown
        """
        # Get component scores
        tier_score = self.get_tier_score(source_name)
        freshness_score = self.calculate_freshness(data)
        completeness_score = self.calculate_completeness(data, data_type)
        accuracy_score = self.get_historical_accuracy(source_name)

        # Calculate weighted overall score
        overall_score = (
            tier_score * self.weights.source_tier
            + freshness_score * self.weights.data_freshness
            + completeness_score * self.weights.completeness
            + accuracy_score * self.weights.historical_accuracy
        )

        # Determine tier
        tier = self._get_source_tier(source_name)

        return SourceScore(
            source_name=source_name,
            overall_score=overall_score,
            tier_score=tier_score,
            freshness_score=freshness_score,
            completeness_score=completeness_score,
            accuracy_score=accuracy_score,
            tier=tier,
            metadata={
                "data_type": data_type,
                "weights": {
                    "tier": self.weights.source_tier,
                    "freshness": self.weights.data_freshness,
                    "completeness": self.weights.completeness,
                    "accuracy": self.weights.historical_accuracy,
                },
            },
        )

    def get_tier_score(self, source_name: str) -> float:
        """
        Get base reliability score from source tier.

        Args:
            source_name: Name/identifier of the data source

        Returns:
            Tier score (0.3 to 1.0)
        """
        tier = self._get_source_tier(source_name)
        return tier.value

    def _get_source_tier(self, source_name: str) -> SourceTier:
        """
        Determine source tier from source name.

        Args:
            source_name: Name/identifier of the data source

        Returns:
            SourceTier enum value
        """
        # Normalize source name for matching
        normalized = source_name.lower().replace("-", "_").replace(" ", "_")

        # Check for exact match
        if normalized in self.SOURCE_TIER_MAP:
            return self.SOURCE_TIER_MAP[normalized]

        # Check for partial matches (e.g., "ndbc_51001" matches "ndbc")
        for key, tier in self.SOURCE_TIER_MAP.items():
            if key in normalized or normalized.startswith(key):
                return tier

        # Default to mid-tier if unknown
        self.logger.warning(f"Unknown source '{source_name}', defaulting to Tier 4 (Commercial)")
        return SourceTier.TIER_4

    def calculate_freshness(self, data: Any) -> float:
        """
        Calculate data freshness score based on age.

        Formula: 1.0 - (age_hours / 24)
        - 0 hours old = 1.0
        - 12 hours old = 0.5
        - 24+ hours old = 0.0

        Args:
            data: Data object or dictionary

        Returns:
            Freshness score (0.0 to 1.0)
        """
        try:
            # Extract timestamp from various data structures
            timestamp = self._extract_timestamp(data)

            if timestamp is None:
                self.logger.debug("No timestamp found, using neutral freshness (0.5)")
                return 0.5

            # Parse timestamp
            if isinstance(timestamp, str):
                # Handle various timestamp formats
                if timestamp.endswith("Z"):
                    timestamp = timestamp.replace("Z", "+00:00")
                dt = datetime.fromisoformat(timestamp)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                self.logger.debug(f"Unknown timestamp type {type(timestamp)}, using neutral")
                return 0.5

            # Ensure timezone awareness
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)

            # Calculate age in hours
            now = datetime.now(UTC)
            age_hours = (now - dt).total_seconds() / 3600

            # Calculate freshness score (1.0 for recent, 0.0 after 24 hours)
            freshness = max(0.0, min(1.0, 1.0 - (age_hours / 24.0)))

            self.logger.debug(f"Data age: {age_hours:.1f}h, freshness: {freshness:.3f}")

            return freshness

        except Exception as e:
            self.logger.warning(f"Error calculating freshness: {e}")
            return 0.5  # Neutral score on error

    def calculate_completeness(self, data: Any, data_type: str = "default") -> float:
        """
        Calculate data completeness score.

        Formula: fields_present / fields_expected

        Args:
            data: Data object or dictionary
            data_type: Type of data (buoy, weather, model, default)

        Returns:
            Completeness score (0.0 to 1.0)
        """
        try:
            # Get expected fields for this data type
            expected_fields = self.EXPECTED_FIELDS.get(data_type, self.EXPECTED_FIELDS["default"])

            # Extract fields from data
            present_fields = self._extract_fields(data)

            # Count how many expected fields are present and non-null
            fields_present = 0
            for field in expected_fields:
                if field in present_fields and present_fields[field] is not None:
                    fields_present += 1

            # Calculate completeness ratio
            completeness = fields_present / len(expected_fields)

            self.logger.debug(
                f"Completeness: {fields_present}/{len(expected_fields)} = {completeness:.3f}"
            )

            return completeness

        except Exception as e:
            self.logger.warning(f"Error calculating completeness: {e}")
            return 0.5  # Neutral score on error

    def get_historical_accuracy(self, source_name: str) -> float:
        """
        Get historical accuracy score from validation cache.

        This would integrate with the validation system to retrieve
        past accuracy metrics for the source. Currently returns a
        default value but can be enhanced with actual validation data.

        Args:
            source_name: Name/identifier of the data source

        Returns:
            Historical accuracy score (0.0 to 1.0)
        """
        # Check cache first
        if source_name in self._validation_cache:
            return self._validation_cache[source_name]

        # Default to neutral until validation system integration
        # In future: query validation database for source accuracy
        default_accuracy = 0.7

        self.logger.debug(
            f"No historical accuracy data for '{source_name}', " f"using default {default_accuracy}"
        )

        return default_accuracy

    def set_historical_accuracy(self, source_name: str, accuracy: float) -> None:
        """
        Update historical accuracy cache for a source.

        This allows the validation system to feed accuracy data
        back into the scorer for future forecasts.

        Args:
            source_name: Name/identifier of the data source
            accuracy: Accuracy score (0.0 to 1.0)
        """
        if not 0.0 <= accuracy <= 1.0:
            raise ValueError(f"Accuracy must be between 0.0 and 1.0, got {accuracy}")

        self._validation_cache[source_name] = accuracy
        self.logger.info(f"Updated accuracy cache for '{source_name}': {accuracy:.3f}")

    def _extract_source_id(self, data: Any, data_type: str) -> str:
        """Extract source identifier from data object."""
        if isinstance(data, dict):
            # Try common source identifier fields
            for field in [
                "source",
                "source_name",
                "provider",
                "station_id",
                "model_id",
                "buoy_id",
                "name",
            ]:
                if field in data and data[field]:
                    return str(data[field])
            return f"{data_type}_unknown"

        # Try object attributes
        for attr in [
            "source",
            "source_name",
            "provider",
            "station_id",
            "model_id",
            "buoy_id",
            "name",
        ]:
            if hasattr(data, attr):
                value = getattr(data, attr)
                if value:
                    return str(value)

        return f"{data_type}_unknown"

    def _extract_timestamp(self, data: Any) -> str | None:
        """Extract timestamp from data object or dictionary."""
        if isinstance(data, dict):
            # Try common timestamp fields
            for field in [
                "timestamp",
                "time",
                "date",
                "issued",
                "run_time",
                "observation_time",
                "forecast_time",
                "generated_time",
            ]:
                if field in data and data[field]:
                    return data[field]

            # Check nested structures
            if "metadata" in data and isinstance(data["metadata"], dict):
                for field in ["timestamp", "time", "date"]:
                    if field in data["metadata"]:
                        return data["metadata"][field]

            # Check observations array
            if "observations" in data and isinstance(data["observations"], list):
                if data["observations"] and isinstance(data["observations"][0], dict):
                    for field in ["timestamp", "time", "date"]:
                        if field in data["observations"][0]:
                            return data["observations"][0][field]

            return None

        # Try object attributes
        for attr in [
            "timestamp",
            "time",
            "date",
            "issued",
            "run_time",
            "observation_time",
            "forecast_time",
            "generated_time",
        ]:
            if hasattr(data, attr):
                value = getattr(data, attr)
                if value:
                    return value

        # Check nested objects
        if hasattr(data, "metadata") and hasattr(data.metadata, "timestamp"):
            return data.metadata.timestamp

        if hasattr(data, "observations") and data.observations:
            first_obs = data.observations[0]
            if hasattr(first_obs, "timestamp"):
                return first_obs.timestamp

        return None

    def _extract_fields(self, data: Any) -> dict[str, Any]:
        """Extract all fields from data object or dictionary."""
        if isinstance(data, dict):
            return data

        # Convert object to dictionary
        fields = {}
        for attr in dir(data):
            if not attr.startswith("_"):
                try:
                    value = getattr(data, attr)
                    if not callable(value):
                        fields[attr] = value
                except Exception:
                    pass

        return fields
