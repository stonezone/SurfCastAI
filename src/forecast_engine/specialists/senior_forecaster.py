"""
Senior forecaster specialist for SurfCastAI forecast engine.

This module synthesizes outputs from BuoyAnalyst and PressureAnalyst into
comprehensive Pat Caldwell-style surf forecasts with cross-validation and
contradiction detection.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

from .base_specialist import BaseSpecialist, SpecialistOutput
from .schemas import (
    BuoyAnalystOutput,
    Contradiction,
    PressureAnalystOutput,
    SeniorForecasterData,
    SeniorForecasterInput,
    SeniorForecasterOutput,
    ShoreForecast,
    SwellBreakdown,
    Synthesis,
)


class SeniorForecaster(BaseSpecialist):
    """
    Senior forecaster that synthesizes specialist reports.

    Features:
    - Cross-validation between BuoyAnalyst and PressureAnalyst
    - Contradiction detection and resolution
    - Specialist agreement scoring
    - Shore-specific forecast generation
    - Swell breakdown with source attribution
    - Pat Caldwell-style narrative synthesis using GPT-5-mini or GPT-5

    Input format:
        {
            'buoy_analysis': SpecialistOutput,  # from BuoyAnalyst
            'pressure_analysis': SpecialistOutput,  # from PressureAnalyst
            'swell_events': [...],  # from data fusion system
            'shore_data': {
                'north_shore': {...},
                'south_shore': {...},
                'east_shore': {...},
                'west_shore': {...}
            },
            'seasonal_context': {
                'season': 'winter' | 'summer',
                'typical_patterns': {...},
                'climatology': {...}
            },
            'metadata': {
                'forecast_date': '2025-10-07',
                'valid_period': '48hr',
                'bundle_id': '...'
            }
        }

    Output format:
        {
            'confidence': 0.0-1.0,
            'data': {
                'synthesis': {
                    'specialist_agreement': 0.0-1.0,
                    'contradictions': [...],
                    'key_findings': [...]
                },
                'shore_forecasts': {...},
                'swell_breakdown': [...]
            },
            'narrative': 'Pat Caldwell-style forecast',
            'metadata': {...}
        }
    """

    # Direction mapping for comparison (normalize to cardinal directions)
    DIRECTION_MAPPING = {
        "N": 0,
        "NNE": 22.5,
        "NE": 45,
        "ENE": 67.5,
        "E": 90,
        "ESE": 112.5,
        "SE": 135,
        "SSE": 157.5,
        "S": 180,
        "SSW": 202.5,
        "SW": 225,
        "WSW": 247.5,
        "W": 270,
        "WNW": 292.5,
        "NW": 315,
        "NNW": 337.5,
    }

    def __init__(
        self,
        config: Any | None = None,
        model_name: str | None = None,
        engine: Any | None = None,
    ):
        """
        Initialize the senior forecaster.

        Args:
            config: Optional configuration object with OpenAI and forecast settings
            model_name: The specific OpenAI model this specialist instance should use (REQUIRED)
            engine: Reference to ForecastEngine for centralized API calls and cost tracking
        """
        super().__init__(config, model_name, engine)
        self.logger = logging.getLogger("specialist.senior_forecaster")

        # Validate engine parameter is provided
        if engine is None:
            raise ValueError(
                f"{self.__class__.__name__} requires engine parameter for API access. "
                "Template mode removed to prevent quality degradation."
            )
        self.engine = engine

        # Load OpenAI configuration
        # Note: model_name is set by BaseSpecialist.__init__ via config
        if config:
            self.openai_api_key = config.get("openai", "api_key") or os.environ.get(
                "OPENAI_API_KEY"
            )
            self.max_tokens = config.getint("openai", "max_tokens", 2000)
            self.min_specialists_required = config.getint(
                "forecast", "require_minimum_specialists", 2
            )
        else:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
            self.max_tokens = 2000
            self.min_specialists_required = 2

    async def analyze(self, data: dict[str, Any] | SeniorForecasterInput) -> SeniorForecasterOutput:
        """
        Synthesize specialist reports into final forecast.

        Args:
            data: Either a dict (legacy) or SeniorForecasterInput (new Pydantic model)

        Returns:
            SeniorForecasterOutput with synthesized forecast

        Raises:
            ValueError: If insufficient specialists available
        """
        self._log_analysis_start("synthesizing specialist reports")

        # Convert to dict if Pydantic model (for internal processing)
        if isinstance(data, SeniorForecasterInput):
            input_dict = data.model_dump()
        else:
            input_dict = data

        # Extract specialist outputs (handle both Pydantic and dict formats)
        buoy_analysis = input_dict.get("buoy_analysis")
        pressure_analysis = input_dict.get("pressure_analysis")

        # Convert Pydantic models to dicts if needed (for internal processing)
        if isinstance(buoy_analysis, BuoyAnalystOutput):
            buoy_dict = buoy_analysis.model_dump()
            # Keep original for confidence checks
            buoy_specialist = buoy_analysis
        else:
            buoy_dict = buoy_analysis
            # Wrap in a simple object with confidence attribute for compatibility
            buoy_specialist = (
                type(
                    "obj",
                    (object,),
                    {
                        "confidence": (
                            buoy_analysis.get("confidence", 0.0) if buoy_analysis else 0.0
                        ),
                        "data": buoy_analysis.get("data", {}) if buoy_analysis else {},
                        "narrative": buoy_analysis.get("narrative", "") if buoy_analysis else "",
                    },
                )()
                if buoy_analysis
                else None
            )

        if isinstance(pressure_analysis, PressureAnalystOutput):
            pressure_dict = pressure_analysis.model_dump()
            # Keep original for confidence checks
            pressure_specialist = pressure_analysis
        else:
            pressure_dict = pressure_analysis
            # Wrap in a simple object with confidence attribute for compatibility
            pressure_specialist = (
                type(
                    "obj",
                    (object,),
                    {
                        "confidence": (
                            pressure_analysis.get("confidence", 0.0) if pressure_analysis else 0.0
                        ),
                        "data": pressure_analysis.get("data", {}) if pressure_analysis else {},
                        "narrative": (
                            pressure_analysis.get("narrative", "") if pressure_analysis else ""
                        ),
                    },
                )()
                if pressure_analysis
                else None
            )

        # Validate minimum specialists available
        specialists_available = []
        if buoy_specialist and buoy_specialist.confidence > 0.3:
            specialists_available.append("buoy")
        if pressure_specialist and pressure_specialist.confidence > 0.3:
            specialists_available.append("pressure")

        if len(specialists_available) < self.min_specialists_required:
            raise ValueError(
                f"Insufficient specialists: need {self.min_specialists_required}, "
                f"have {len(specialists_available)} with sufficient confidence"
            )

        try:
            # Cross-validate specialist predictions (use wrapped specialists)
            contradictions = self._identify_contradictions(buoy_specialist, pressure_specialist)

            # Calculate agreement score (use wrapped specialists)
            agreement_score = self._calculate_specialist_agreement(
                buoy_specialist, pressure_specialist
            )

            # Synthesize findings (use wrapped specialists)
            key_findings = self._extract_key_findings(
                buoy_specialist, pressure_specialist, input_dict.get("swell_events", [])
            )

            # Generate shore-specific forecasts (use wrapped specialists)
            shore_forecasts = self._generate_shore_forecasts(
                buoy_specialist,
                pressure_specialist,
                input_dict.get("shore_data", {}),
                input_dict.get("seasonal_context", {}),
            )

            # Generate swell breakdown (use wrapped specialists)
            swell_breakdown = self._generate_swell_breakdown(buoy_specialist, pressure_specialist)

            # Calculate overall confidence
            confidence = self._calculate_synthesis_confidence(
                agreement_score, contradictions, specialists_available
            )

            # Generate Pat Caldwell-style narrative (use wrapped specialists)
            narrative = await self._generate_caldwell_narrative(
                buoy_specialist,
                pressure_specialist,
                contradictions,
                key_findings,
                shore_forecasts,
                swell_breakdown,
                input_dict.get("seasonal_context", {}),
                input_dict.get("metadata", {}),
            )

            # Create metadata
            metadata = {
                "specialists_used": specialists_available,
                "synthesis_method": "cross_validation",
                "model": self.model_name,
                "timestamp": datetime.now().isoformat(),
                "forecast_date": input_dict.get("metadata", {}).get("forecast_date"),
                "valid_period": input_dict.get("metadata", {}).get("valid_period", "48hr"),
            }

            self._log_analysis_complete(confidence, len(specialists_available))

            # Convert lists of dicts to Pydantic model instances
            contradictions_list = [Contradiction(**c) for c in contradictions]
            shore_forecasts_dict = {
                shore: ShoreForecast(**forecast) for shore, forecast in shore_forecasts.items()
            }
            swell_breakdown_list = [SwellBreakdown(**swell) for swell in swell_breakdown]

            synthesis_obj = Synthesis(
                specialist_agreement=agreement_score,
                contradictions=contradictions_list,
                key_findings=key_findings,
            )

            # Create SeniorForecasterData instance
            structured_data = SeniorForecasterData(
                synthesis=synthesis_obj,
                shore_forecasts=shore_forecasts_dict,
                swell_breakdown=swell_breakdown_list,
            )

            # Return Pydantic model
            return SeniorForecasterOutput(
                confidence=confidence, data=structured_data, narrative=narrative, metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error in synthesis: {e}")
            raise

    def _to_dict(self, data):
        """
        Convert Pydantic model or dict to dict for internal processing.

        Args:
            data: Either a Pydantic model (with model_dump()) or dict

        Returns:
            dict representation of data
        """
        if data is None:
            return {}
        if hasattr(data, "model_dump"):
            return data.model_dump()
        return data if isinstance(data, dict) else {}

    def _identify_contradictions(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
    ) -> list[dict[str, Any]]:
        """
        Identify contradictions between specialist reports.

        Examples:
        - Buoys show NNE swell but no supporting low-pressure system
        - Pressure chart shows fetch but buoys show no signal yet
        - Specialists predict different arrival times

        Args:
            buoy_analysis: Output from BuoyAnalyst
            pressure_analysis: Output from PressureAnalyst

        Returns:
            List of contradiction dictionaries
        """
        contradictions = []

        if not buoy_analysis or not pressure_analysis:
            return contradictions

        # Convert to dicts for uniform access
        buoy_data = self._to_dict(buoy_analysis.data)
        pressure_data = self._to_dict(pressure_analysis.data)

        # Extract predictions from each specialist
        buoy_trends = buoy_data.get("trends", [])
        pressure_swells = pressure_data.get("predicted_swells", [])
        pressure_systems = pressure_data.get("systems", [])

        # Check for buoy signal without pressure support
        for trend in buoy_trends:
            # Convert trend to dict if it's a Pydantic model
            trend = self._to_dict(trend)
            if trend.get("height_trend") in ["increasing_strong", "increasing_moderate"]:
                # Check if pressure analyst predicted this swell
                supporting_swell = self._find_supporting_swell(trend, pressure_swells)

                if not supporting_swell:
                    # Check if there's at least a weather system in the right direction
                    direction = trend.get("direction_current")
                    has_system = False

                    if direction is not None:
                        for system in pressure_systems:
                            # Convert system to dict if it's a Pydantic model
                            system = self._to_dict(system)
                            if system.get("type") == "low_pressure":
                                fetch = system.get("fetch", {}) or {}
                                fetch_dir = fetch.get("direction", "")
                                if self._directions_match(str(direction), fetch_dir, tolerance=45):
                                    has_system = True
                                    break

                    if not has_system:
                        contradictions.append(
                            {
                                "issue": f"Buoy {trend['buoy_name']} shows {trend['height_trend']} "
                                f"trend but no supporting pressure system identified",
                                "resolution": "Likely local windswell or short-period energy, "
                                "not groundswell from distant storm",
                                "impact": "medium",
                                "buoy_confidence": buoy_analysis.confidence,
                                "pressure_confidence": pressure_analysis.confidence,
                            }
                        )

        # Check for predicted swells without buoy confirmation
        for swell in pressure_swells:
            # Convert swell to dict if it's a Pydantic model
            swell = self._to_dict(swell)
            if swell.get("confidence", 0) > 0.7:
                # Check if buoys show supporting signal
                confirming_buoy = self._find_confirming_buoy(swell, buoy_trends)

                if not confirming_buoy:
                    # Determine if this is a future arrival (acceptable) or current discrepancy (concerning)
                    is_future = self._is_future_arrival(swell)

                    contradictions.append(
                        {
                            "issue": f"Pressure analysis predicts {swell.get('direction')} swell "
                            f"but buoys show no current signal",
                            "resolution": f"Swell arrival expected {swell.get('arrival_time')}, "
                            f"{'buoys should show signal later' if is_future else 'may be overestimated'}",
                            "impact": "low" if is_future else "high",
                            "swell_confidence": swell.get("confidence"),
                        }
                    )

        # Check for timing discrepancies
        for swell in pressure_swells:
            # Convert swell to dict if it's a Pydantic model
            swell = self._to_dict(swell)
            swell_direction = swell.get("direction", "")
            for trend in buoy_trends:
                # Convert trend to dict if it's a Pydantic model
                trend = self._to_dict(trend)
                trend_direction = trend.get("direction_current")
                if trend_direction is not None and self._directions_match(
                    str(trend_direction), swell_direction
                ):
                    # Same direction - check if trends align with prediction
                    if trend["height_trend"] in ["decreasing_strong", "decreasing_moderate"]:
                        if self._is_future_arrival(swell):
                            contradictions.append(
                                {
                                    "issue": f"Pressure predicts incoming {swell_direction} swell "
                                    f"but {trend['buoy_name']} shows decreasing trend",
                                    "resolution": "Current swell may be fading before new swell arrives, "
                                    "or arrival timing may be later than expected",
                                    "impact": "medium",
                                    "timing": swell.get("arrival_time"),
                                }
                            )

        return contradictions

    def _find_supporting_swell(
        self, trend: dict[str, Any], predicted_swells: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Find a predicted swell that supports an observed buoy trend.

        Args:
            trend: Buoy trend dictionary
            predicted_swells: List of predicted swells from pressure analysis

        Returns:
            Matching swell or None
        """
        trend_direction = trend.get("direction_current")
        if trend_direction is None:
            return None

        trend_period = trend.get("period_current")

        for swell in predicted_swells:
            swell_direction = swell.get("direction", "")

            # Check direction match
            if self._directions_match(str(trend_direction), swell_direction):
                # Check if swell has already arrived or is arriving
                if not self._is_future_arrival(swell) or self._is_near_arrival(swell):
                    # Check period if available (groundswell vs windswell distinction)
                    if trend_period:
                        estimated_period = swell.get("estimated_period", "")
                        if self._periods_compatible(trend_period, estimated_period):
                            return swell
                    else:
                        return swell

        return None

    def _find_confirming_buoy(
        self, swell: dict[str, Any], buoy_trends: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Find a buoy trend that confirms a predicted swell.

        Args:
            swell: Predicted swell dictionary
            buoy_trends: List of buoy trends

        Returns:
            Confirming buoy trend or None
        """
        swell_direction = swell.get("direction", "")

        for trend in buoy_trends:
            trend_direction = trend.get("direction_current")
            if trend_direction is None:
                continue

            # Check direction match
            if self._directions_match(str(trend_direction), swell_direction):
                # Check if buoy shows increasing or steady trend (not decreasing)
                if trend["height_trend"] not in ["decreasing_strong", "decreasing_moderate"]:
                    return trend

        return None

    def _is_future_arrival(self, swell: dict[str, Any]) -> bool:
        """
        Determine if swell arrival is in the future.

        Args:
            swell: Swell prediction dictionary

        Returns:
            True if arrival is in the future
        """
        arrival_time_str = swell.get("arrival_time", "")
        if not arrival_time_str:
            return False

        try:
            # Parse various time formats
            # Handle ISO 8601 format: "2025-10-12T18:00Z" or "2025-10-12T18:00:00Z"
            # Remove 'Z' suffix and parse
            clean_time_str = arrival_time_str.replace("Z", "")

            # Handle time range format if present (e.g., "10:00-12:00")
            # This is rare but check for it
            if "T" in clean_time_str:
                # Split by 'T' to separate date and time
                parts = clean_time_str.split("T")
                if len(parts) == 2:
                    date_part = parts[0]
                    time_part = parts[1]
                    # If time has a range (contains second dash after date), take first time
                    if time_part.count("-") > 0:
                        # This is a time range, extract first time only
                        time_part = time_part.split("-")[0]
                    clean_time_str = f"{date_part}T{time_part}"

            arrival_time = datetime.fromisoformat(clean_time_str)
            # Handle timezone awareness
            if arrival_time.tzinfo is None:
                # Naive datetime - assume it's in local timezone (same as datetime.now())
                now = datetime.now()
            else:
                # Timezone-aware - use same timezone for now
                now = datetime.now(arrival_time.tzinfo)

            return arrival_time > now
        except Exception as e:
            self.logger.debug(f"Could not parse arrival time '{arrival_time_str}': {e}")
            return False

    def _is_near_arrival(self, swell: dict[str, Any], hours_threshold: float = 12.0) -> bool:
        """
        Determine if swell arrival is imminent (within threshold hours).

        Args:
            swell: Swell prediction dictionary
            hours_threshold: Hours within which arrival is considered near

        Returns:
            True if arrival is within threshold
        """
        arrival_time_str = swell.get("arrival_time", "")
        if not arrival_time_str:
            return False

        try:
            # Parse ISO 8601 format: "2025-10-12T18:00Z" or "2025-10-12T18:00:00Z"
            clean_time_str = arrival_time_str.replace("Z", "")

            # Handle time range format if present
            if "T" in clean_time_str:
                parts = clean_time_str.split("T")
                if len(parts) == 2:
                    date_part = parts[0]
                    time_part = parts[1]
                    if time_part.count("-") > 0:
                        time_part = time_part.split("-")[0]
                    clean_time_str = f"{date_part}T{time_part}"

            arrival_time = datetime.fromisoformat(clean_time_str)
            # Handle timezone awareness
            if arrival_time.tzinfo is None:
                # Naive datetime - assume it's in local timezone (same as datetime.now())
                now = datetime.now()
            else:
                # Timezone-aware - use same timezone for now
                now = datetime.now(arrival_time.tzinfo)

            time_until_arrival = (arrival_time - now).total_seconds() / 3600.0
            return 0 <= time_until_arrival <= hours_threshold
        except Exception:
            return False

    def _directions_match(self, dir1: str, dir2: str, tolerance: float = 30.0) -> bool:
        """
        Check if two direction strings match within tolerance.

        Args:
            dir1: First direction (can be degrees or compass)
            dir2: Second direction (can be degrees or compass)
            tolerance: Tolerance in degrees

        Returns:
            True if directions match within tolerance
        """
        angle1 = self._direction_to_degrees(dir1)
        angle2 = self._direction_to_degrees(dir2)

        if angle1 is None or angle2 is None:
            return False

        # Calculate angular difference (accounting for 360° wrap)
        diff = abs(angle1 - angle2)
        if diff > 180:
            diff = 360 - diff

        return diff <= tolerance

    def _direction_to_degrees(self, direction: str) -> float | None:
        """
        Convert direction string to degrees.

        Args:
            direction: Direction as string (e.g., "NNE", "45", "45.0")

        Returns:
            Angle in degrees (0-360) or None
        """
        if not direction:
            return None

        # Try parsing as number first
        try:
            angle = float(direction)
            return angle % 360
        except ValueError:
            pass

        # Try compass direction
        direction_upper = direction.strip().upper()
        return self.DIRECTION_MAPPING.get(direction_upper)

    def _periods_compatible(self, observed_period: float, predicted_period_str: str) -> bool:
        """
        Check if observed and predicted periods are compatible.

        Args:
            observed_period: Observed period in seconds
            predicted_period_str: Predicted period string (e.g., "13-15s")

        Returns:
            True if periods are compatible
        """
        try:
            # Parse predicted period range
            if "-" in predicted_period_str:
                parts = predicted_period_str.replace("s", "").split("-")
                min_period = float(parts[0])
                max_period = float(parts[1])
            else:
                period = float(predicted_period_str.replace("s", ""))
                min_period = period - 2
                max_period = period + 2

            # Check if observed falls within range (with some tolerance)
            return min_period - 2 <= observed_period <= max_period + 2

        except Exception as e:
            self.logger.debug(f"Could not parse period '{predicted_period_str}': {e}")
            return True  # Assume compatible if can't parse

    def _calculate_specialist_agreement(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
    ) -> float:
        """
        Calculate agreement score between specialists (0.0-1.0).

        Factors:
        - Directional agreement (are they seeing same swell directions?)
        - Timing agreement (do arrival predictions align?)
        - Magnitude agreement (do height predictions match?)
        - Trend agreement (do both see building/declining?)

        Args:
            buoy_analysis: Output from BuoyAnalyst
            pressure_analysis: Output from PressureAnalyst

        Returns:
            Agreement score (0.0-1.0)
        """
        if not buoy_analysis or not pressure_analysis:
            return 0.0

        agreement_factors = []

        # Directional agreement
        buoy_directions = self._extract_dominant_directions(buoy_analysis)
        pressure_directions = self._extract_predicted_directions(pressure_analysis)

        if buoy_directions and pressure_directions:
            dir_agreement = self._compare_directions(buoy_directions, pressure_directions)
            agreement_factors.append(dir_agreement)

        # Convert data to dicts for uniform access
        buoy_data = self._to_dict(buoy_analysis.data)
        pressure_data = self._to_dict(pressure_analysis.data)

        # Trend agreement (are both seeing increasing/decreasing patterns?)
        buoy_trends = buoy_data.get("trends", [])
        pressure_swells = pressure_data.get("predicted_swells", [])

        if buoy_trends and pressure_swells:
            trend_agreement = self._compare_trends(buoy_trends, pressure_swells)
            agreement_factors.append(trend_agreement)

        # Confidence alignment (do both have similar confidence?)
        confidence_diff = abs(buoy_analysis.confidence - pressure_analysis.confidence)
        confidence_agreement = 1.0 - min(confidence_diff, 1.0)
        agreement_factors.append(confidence_agreement)

        # Weighted average
        if agreement_factors:
            # Weight directional and trend agreement more heavily
            weights = (
                [0.4, 0.4, 0.2]
                if len(agreement_factors) == 3
                else [1.0 / len(agreement_factors)] * len(agreement_factors)
            )
            return sum(f * w for f, w in zip(agreement_factors, weights, strict=False))

        return 0.5  # Neutral if no factors available

    def _extract_dominant_directions(self, buoy_analysis: SpecialistOutput) -> list[float]:
        """
        Extract dominant wave directions from buoy analysis.

        Args:
            buoy_analysis: Output from BuoyAnalyst

        Returns:
            List of directions in degrees
        """
        directions = []
        buoy_data = self._to_dict(buoy_analysis.data)
        trends = buoy_data.get("trends", [])

        for trend in trends:
            # Convert trend to dict if it's a Pydantic model
            trend = self._to_dict(trend)
            direction = trend.get("direction_current")
            if direction is not None:
                angle = self._direction_to_degrees(str(direction))
                if angle is not None:
                    directions.append(angle)

        return directions

    def _extract_predicted_directions(self, pressure_analysis: SpecialistOutput) -> list[float]:
        """
        Extract predicted swell directions from pressure analysis.

        Args:
            pressure_analysis: Output from PressureAnalyst

        Returns:
            List of directions in degrees
        """
        directions = []
        pressure_data = self._to_dict(pressure_analysis.data)
        swells = pressure_data.get("predicted_swells", [])

        for swell in swells:
            # Convert swell to dict if it's a Pydantic model
            swell = self._to_dict(swell)
            direction_str = swell.get("direction", "")
            if direction_str:
                angle = self._direction_to_degrees(direction_str)
                if angle is not None:
                    directions.append(angle)

        return directions

    def _compare_directions(
        self, buoy_directions: list[float], pressure_directions: list[float]
    ) -> float:
        """
        Compare two sets of directions and return agreement score.

        Args:
            buoy_directions: Directions from buoy analysis
            pressure_directions: Directions from pressure analysis

        Returns:
            Agreement score (0.0-1.0)
        """
        if not buoy_directions or not pressure_directions:
            return 0.0

        # Count how many buoy directions have close pressure predictions
        matches = 0
        for buoy_dir in buoy_directions:
            for pressure_dir in pressure_directions:
                diff = abs(buoy_dir - pressure_dir)
                if diff > 180:
                    diff = 360 - diff
                if diff <= 45:  # Within 45 degrees
                    matches += 1
                    break

        return matches / len(buoy_directions)

    def _compare_trends(
        self, buoy_trends: list[dict[str, Any]], pressure_swells: list[dict[str, Any]]
    ) -> float:
        """
        Compare buoy trends with pressure predictions.

        Args:
            buoy_trends: Buoy trend data
            pressure_swells: Predicted swells

        Returns:
            Agreement score (0.0-1.0)
        """
        if not buoy_trends or not pressure_swells:
            return 0.5

        # Look for alignment between increasing trends and predicted arrivals
        alignment_count = 0
        total_checks = 0

        for trend in buoy_trends:
            # Convert trend to dict if it's a Pydantic model
            trend = self._to_dict(trend)
            trend_direction = trend.get("direction_current")
            if trend_direction is None:
                continue

            for swell in pressure_swells:
                # Convert swell to dict if it's a Pydantic model
                swell = self._to_dict(swell)
                if self._directions_match(str(trend_direction), swell.get("direction", "")):
                    total_checks += 1

                    # Check if trend aligns with prediction
                    if trend["height_trend"] in ["increasing_strong", "increasing_moderate"]:
                        # Good alignment if swell is arriving
                        if self._is_near_arrival(swell):
                            alignment_count += 1
                    elif trend["height_trend"] in ["steady"]:
                        # Neutral - acceptable
                        alignment_count += 0.5
                    # Decreasing trend with predicted arrival is a mismatch

        return alignment_count / total_checks if total_checks > 0 else 0.5

    def _extract_key_findings(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
        swell_events: list[dict[str, Any]],
    ) -> list[str]:
        """
        Extract key findings from specialist reports.

        Args:
            buoy_analysis: Output from BuoyAnalyst
            pressure_analysis: Output from PressureAnalyst
            swell_events: Detected swell events

        Returns:
            List of key finding strings
        """
        findings = []

        # Extract from buoy analysis
        if buoy_analysis:
            buoy_data = self._to_dict(buoy_analysis.data)
            trends = buoy_data.get("trends", [])
            for trend in trends:
                # Convert trend to dict if it's a Pydantic model
                trend = self._to_dict(trend)
                if trend["height_trend"] in ["increasing_strong", "increasing_moderate"]:
                    direction = trend.get("direction_current", "unknown")
                    height = trend.get("height_current")
                    period = trend.get("period_current")
                    findings.append(
                        f"{trend['buoy_name']}: {direction}° swell building "
                        f"({height}m @ {period}s)"
                    )

        # Extract from pressure analysis
        if pressure_analysis:
            pressure_data = self._to_dict(pressure_analysis.data)
            swells = pressure_data.get("predicted_swells", [])
            for swell in swells[:3]:  # Top 3 predictions
                # Convert swell to dict if it's a Pydantic model
                swell = self._to_dict(swell)
                if swell.get("confidence", 0) > 0.6:
                    findings.append(
                        f"Predicted {swell.get('direction')} swell: "
                        f"{swell.get('estimated_height')} @ {swell.get('estimated_period')}, "
                        f"arriving {swell.get('arrival_time')}"
                    )

        # Add swell event findings
        for event in swell_events[:3]:  # Top 3 events
            if event.get("confidence", 0) > 0.7:
                findings.append(
                    f"Swell event detected: {event.get('direction', 'unknown')} "
                    f"{event.get('height_range', 'N/A')} @ {event.get('period_range', 'N/A')}"
                )

        return findings[:5]  # Limit to 5 key findings

    def _generate_shore_forecasts(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
        shore_data: dict[str, Any],
        seasonal_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate shore-specific forecasts.

        Args:
            buoy_analysis: Output from BuoyAnalyst
            pressure_analysis: Output from PressureAnalyst
            shore_data: Shore-specific data
            seasonal_context: Seasonal context information

        Returns:
            Dictionary with forecasts for each shore
        """
        season = seasonal_context.get("season", "winter")
        shore_forecasts = {}

        # Define shore exposure by direction (approximate)
        shore_exposures = {
            "north_shore": {
                "directions": [315, 0, 45],
                "primary": True if season == "winter" else False,
            },
            "south_shore": {
                "directions": [135, 180, 225],
                "primary": True if season == "summer" else False,
            },
            "east_shore": {"directions": [45, 90, 135], "primary": False},
            "west_shore": {"directions": [225, 270, 315], "primary": False},
        }

        for shore_name, exposure in shore_exposures.items():
            # Get relevant swells for this shore
            relevant_swells = self._get_swells_for_shore(
                exposure["directions"], buoy_analysis, pressure_analysis
            )

            # Calculate size and conditions
            size_range = self._estimate_shore_size(relevant_swells, exposure["primary"])
            conditions = self._estimate_conditions(relevant_swells, shore_name, seasonal_context)
            timing = self._estimate_timing(relevant_swells)
            confidence = self._estimate_shore_confidence(
                relevant_swells, buoy_analysis, pressure_analysis
            )

            shore_forecasts[shore_name] = {
                "size_range": size_range,
                "conditions": conditions,
                "timing": timing,
                "confidence": round(confidence, 2),
            }

        return shore_forecasts

    def _get_swells_for_shore(
        self,
        shore_directions: list[float],
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
    ) -> list[dict[str, Any]]:
        """
        Get swells relevant to a particular shore.

        Args:
            shore_directions: Directions this shore is exposed to
            buoy_analysis: Buoy analysis output
            pressure_analysis: Pressure analysis output

        Returns:
            List of relevant swell dictionaries
        """
        relevant_swells = []

        # Check buoy observations
        if buoy_analysis:
            buoy_data = self._to_dict(buoy_analysis.data)
            trends = buoy_data.get("trends", [])
            for trend in trends:
                # Convert trend to dict if it's a Pydantic model
                trend = self._to_dict(trend)
                direction = trend.get("direction_current")
                if direction is not None:
                    for shore_dir in shore_directions:
                        if self._directions_match(str(direction), str(shore_dir), tolerance=60):
                            relevant_swells.append(
                                {
                                    "source": "buoy",
                                    "direction": direction,
                                    "height": trend.get("height_current"),
                                    "period": trend.get("period_current"),
                                    "trend": trend.get("height_trend"),
                                    "buoy_name": trend.get("buoy_name"),
                                }
                            )
                            break

        # Check pressure predictions
        if pressure_analysis:
            pressure_data = self._to_dict(pressure_analysis.data)
            swells = pressure_data.get("predicted_swells", [])
            for swell in swells:
                # Convert swell to dict if it's a Pydantic model
                swell = self._to_dict(swell)
                swell_dir_str = swell.get("direction", "")
                swell_dir = self._direction_to_degrees(swell_dir_str)
                if swell_dir is not None:
                    for shore_dir in shore_directions:
                        if abs(swell_dir - shore_dir) <= 60 or abs(swell_dir - shore_dir) >= 300:
                            relevant_swells.append(
                                {
                                    "source": "pressure",
                                    "direction": swell_dir,
                                    "height_str": swell.get("estimated_height"),
                                    "period_str": swell.get("estimated_period"),
                                    "arrival": swell.get("arrival_time"),
                                    "confidence": swell.get("confidence"),
                                }
                            )
                            break

        return relevant_swells

    def _estimate_shore_size(self, swells: list[dict[str, Any]], is_primary_shore: bool) -> str:
        """
        Estimate size range for a shore.

        Args:
            swells: Relevant swells for this shore
            is_primary_shore: Whether this is the primary shore for the season

        Returns:
            Size range string (e.g., "6-8ft")
        """
        if not swells:
            return "1-2ft" if not is_primary_shore else "2-4ft"

        # Extract heights
        heights = []
        for swell in swells:
            if "height" in swell and swell["height"] is not None:
                # Buoy height in meters, convert to feet (face height ~= 1.5-2x)
                heights.append(swell["height"] * 1.8 * 3.28)  # meters to feet, face multiplier
            elif "height_str" in swell:
                # Parse predicted height string
                try:
                    height_str = swell["height_str"].replace("ft", "")
                    if "-" in height_str:
                        parts = height_str.split("-")
                        heights.append((float(parts[0]) + float(parts[1])) / 2)
                    else:
                        heights.append(float(height_str))
                except Exception:
                    pass

        if not heights:
            return "2-4ft" if is_primary_shore else "1-3ft"

        # Calculate range
        avg_height = sum(heights) / len(heights)
        min_height = max(1, int(avg_height * 0.8))
        max_height = int(avg_height * 1.2)

        return f"{min_height}-{max_height}ft"

    def _estimate_conditions(
        self, swells: list[dict[str, Any]], shore_name: str, seasonal_context: dict[str, Any]
    ) -> str:
        """
        Estimate surf conditions.

        Args:
            swells: Relevant swells
            shore_name: Name of the shore
            seasonal_context: Seasonal context

        Returns:
            Conditions description (e.g., "clean", "fair", "choppy")
        """
        if not swells:
            return "small and clean"

        # Check for long-period groundswell vs short-period windswell
        has_groundswell = any(
            swell.get("period", 0) > 12 or ("period_str" in swell and "12" in swell["period_str"])
            for swell in swells
        )

        # Check for multiple swell directions (can create choppy conditions)
        directions = set()
        for swell in swells:
            if "direction" in swell:
                directions.add(int(swell["direction"] / 45))  # Group by 45° sectors

        if len(directions) > 2:
            return "mixed and choppy"
        elif has_groundswell:
            return "clean"
        else:
            return "fair to choppy"

    def _estimate_timing(self, swells: list[dict[str, Any]]) -> str:
        """
        Estimate timing of swell activity.

        Args:
            swells: Relevant swells

        Returns:
            Timing description
        """
        if not swells:
            return "Steady small surf throughout period"

        # Check for building trends
        building_count = sum(
            1
            for swell in swells
            if swell.get("trend", "") in ["increasing_strong", "increasing_moderate"]
        )

        # Check for arrivals
        future_arrivals = [
            swell for swell in swells if "arrival" in swell and swell.get("confidence", 0) > 0.6
        ]

        if building_count > 0:
            return "Building through the period, peak in 12-24 hours"
        elif future_arrivals:
            # Parse earliest arrival
            try:
                arrival = future_arrivals[0]["arrival"]
                return f"New swell arriving {arrival}, building thereafter"
            except Exception:
                return "New swell expected, exact timing uncertain"
        else:
            return "Steady through period"

    def _estimate_shore_confidence(
        self,
        swells: list[dict[str, Any]],
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
    ) -> float:
        """
        Estimate confidence for shore forecast.

        Args:
            swells: Relevant swells
            buoy_analysis: Buoy analysis output
            pressure_analysis: Pressure analysis output

        Returns:
            Confidence score (0.0-1.0)
        """
        if not swells:
            return 0.5  # Low confidence for flat forecasts

        # Factor 1: Number of swells (more data = higher confidence)
        data_factor = min(1.0, len(swells) / 3.0)

        # Factor 2: Source confidence
        source_confidences = []
        for swell in swells:
            if swell.get("source") == "buoy" and buoy_analysis:
                source_confidences.append(buoy_analysis.confidence)
            elif swell.get("source") == "pressure" and pressure_analysis:
                conf = swell.get("confidence", pressure_analysis.confidence)
                source_confidences.append(conf)

        if source_confidences:
            source_factor = sum(source_confidences) / len(source_confidences)
        else:
            source_factor = 0.5

        # Weighted average
        return data_factor * 0.4 + source_factor * 0.6

    def _generate_swell_breakdown(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
    ) -> list[dict[str, Any]]:
        """
        Generate detailed swell breakdown with source attribution.

        Args:
            buoy_analysis: Output from BuoyAnalyst
            pressure_analysis: Output from PressureAnalyst

        Returns:
            List of swell breakdown dictionaries
        """
        breakdown = []

        # Merge swells from both sources
        swell_map = {}  # direction -> swell info

        # Add pressure predictions
        if pressure_analysis:
            pressure_data = self._to_dict(pressure_analysis.data)
            for swell in pressure_data.get("predicted_swells", []):
                # Convert swell to dict if it's a Pydantic model
                swell = self._to_dict(swell)
                direction = swell.get("direction", "")
                if direction:
                    swell_map[direction] = {
                        "direction": direction,
                        "period": swell.get("estimated_period", "N/A"),
                        "height": swell.get("estimated_height", "N/A"),
                        "timing": swell.get("arrival_time", "TBD"),
                        "confidence": swell.get("confidence", 0.5),
                        "source": swell.get("source_system", "Unknown pressure system"),
                        "has_pressure_support": True,
                        "has_buoy_confirmation": False,
                    }

        # Add buoy observations
        if buoy_analysis:
            buoy_data = self._to_dict(buoy_analysis.data)
            for trend in buoy_data.get("trends", []):
                # Convert trend to dict if it's a Pydantic model
                trend = self._to_dict(trend)
                direction_deg = trend.get("direction_current")
                if direction_deg is not None:
                    # Convert to compass direction
                    direction = self._degrees_to_compass(direction_deg)

                    # Check if we already have this direction from pressure
                    matched = False
                    for existing_dir in list(swell_map.keys()):
                        if self._directions_match(str(direction_deg), existing_dir):
                            swell_map[existing_dir]["has_buoy_confirmation"] = True
                            swell_map[existing_dir][
                                "buoy_height"
                            ] = f"{trend.get('height_current')}m"
                            swell_map[existing_dir][
                                "buoy_period"
                            ] = f"{trend.get('period_current')}s"
                            matched = True
                            break

                    if not matched:
                        # New swell only seen by buoys
                        swell_map[direction] = {
                            "direction": direction,
                            "period": f"{trend.get('period_current')}s",
                            "height": f"{trend.get('height_current')}m",
                            "timing": "Currently observed",
                            "confidence": 0.8,  # High confidence for actual observations
                            "source": f"Observed at {trend['buoy_name']}",
                            "has_pressure_support": False,
                            "has_buoy_confirmation": True,
                        }

        # Convert to list and sort by confidence
        for swell_info in swell_map.values():
            breakdown.append(swell_info)

        breakdown.sort(key=lambda x: x["confidence"], reverse=True)

        return breakdown[:5]  # Top 5 swells

    def _degrees_to_compass(self, degrees: float) -> str:
        """
        Convert degrees to compass direction.

        Args:
            degrees: Angle in degrees

        Returns:
            Compass direction string
        """
        # Normalize to 0-360
        degrees = degrees % 360

        # Find closest compass direction
        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
        index = int((degrees + 11.25) / 22.5)
        return directions[index % 16]

    def _calculate_synthesis_confidence(
        self,
        agreement_score: float,
        contradictions: list[dict[str, Any]],
        specialists_available: list[str],
    ) -> float:
        """
        Calculate overall confidence in the synthesized forecast.

        Args:
            agreement_score: Specialist agreement score
            contradictions: List of contradictions
            specialists_available: List of available specialists

        Returns:
            Confidence score (0.0-1.0)
        """
        # Base confidence on agreement
        base_confidence = agreement_score

        # Penalize for high-impact contradictions
        high_impact_count = sum(1 for c in contradictions if c.get("impact") == "high")
        medium_impact_count = sum(1 for c in contradictions if c.get("impact") == "medium")

        contradiction_penalty = high_impact_count * 0.15 + medium_impact_count * 0.05
        base_confidence = max(0.0, base_confidence - contradiction_penalty)

        # Bonus for having multiple specialists
        if len(specialists_available) >= 3:
            base_confidence = min(1.0, base_confidence * 1.1)

        return round(base_confidence, 3)

    async def _generate_caldwell_narrative(
        self,
        buoy_analysis: SpecialistOutput | None,
        pressure_analysis: SpecialistOutput | None,
        contradictions: list[dict],
        key_findings: list[str],
        shore_forecasts: dict,
        swell_breakdown: list[dict],
        seasonal_context: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:
        """
        Generate forecast in Pat Caldwell's technical yet accessible style.

        Characteristics:
        - Technical meteorology (mentions pressure systems, fetch)
        - Specific measurements (buoy readings, periods, directions)
        - Clear timing (when swells arrive, when they peak)
        - Shore-by-shore breakdown
        - Confidence caveats when appropriate
        - Actionable for surfers

        Args:
            buoy_analysis: BuoyAnalyst output
            pressure_analysis: PressureAnalyst output
            contradictions: Detected contradictions
            key_findings: Key findings list
            shore_forecasts: Shore-specific forecasts
            swell_breakdown: Detailed swell breakdown
            seasonal_context: Seasonal context
            metadata: Forecast metadata

        Returns:
            Pat Caldwell-style narrative (500-800 words)
        """
        try:
            # Build comprehensive prompt
            forecast_date = metadata.get("forecast_date", datetime.now().strftime("%Y-%m-%d"))
            valid_period = metadata.get("valid_period", "48hr")
            season = seasonal_context.get("season", "winter")

            buoy_conf = buoy_analysis.confidence if buoy_analysis else 0.0
            pressure_conf = pressure_analysis.confidence if pressure_analysis else 0.0
            separator = "=" * 60

            prompt = f"""You are Pat Caldwell, senior surf forecaster for Hawaii.

FORECAST DATE: {forecast_date}
VALID PERIOD: {valid_period}
SEASON: {season}

You have received analysis from your specialist team:

{separator}
BUOY ANALYST REPORT (Confidence: {buoy_conf:.2f}):
{separator}
{buoy_analysis.narrative if buoy_analysis else 'Not available'}

KEY BUOY DATA:
{json.dumps(self._to_dict(buoy_analysis.data) if buoy_analysis else {}, indent=2)}

{separator}
PRESSURE ANALYST REPORT (Confidence: {pressure_conf:.2f}):
{separator}
{pressure_analysis.narrative if pressure_analysis else 'Not available'}

KEY PRESSURE DATA:
{json.dumps(self._to_dict(pressure_analysis.data) if pressure_analysis else {}, indent=2)}

{separator}
CROSS-VALIDATION FINDINGS:
{separator}

KEY FINDINGS:
{chr(10).join('- ' + f for f in key_findings)}

CONTRADICTIONS DETECTED: {len(contradictions)}
{chr(10).join(f"- {c['issue']}: {c['resolution']}" for c in contradictions) if contradictions else 'None'}

SHORE BREAKDOWN:
{json.dumps(shore_forecasts, indent=2)}

SWELL BREAKDOWN:
{json.dumps(swell_breakdown, indent=2)}

{separator}
YOUR TASK:
{separator}

1. Synthesize these specialist reports into a cohesive {valid_period} forecast
2. Address any contradictions explicitly (e.g., "The buoys show NNE signal but
   the pressure charts don't show supporting fetch—this suggests short-period
   windswell rather than groundswell")
3. Provide shore-by-shore breakdown (North, South, East, West)
4. Include specific timing, sizing, and conditions
5. State confidence levels based on specialist agreement
6. Use your signature technical yet accessible style

Write a 500-800 word forecast in your classic format. Be specific about:
- Source storms and fetch windows (cite pressure analyst findings)
- Buoy readings and trends (cite buoy analyst observations)
- Swell arrival timing and evolution
- Shore-specific conditions and recommendations
- Any uncertainties or conflicting signals

Remember: You're writing for experienced Hawaiian surfers who appreciate
technical detail but need actionable guidance."""

            system_prompt = """You are Pat Caldwell, Hawaii's legendary surf forecaster with 40+ years experience.

Your writing style:
- Technical but accessible (explain the meteorology)
- Specific measurements (cite buoy numbers, pressure values, fetch distances)
- Clear timing (be precise about when swells arrive and peak)
- Honest about uncertainty (when data conflicts, say so)
- Actionable for surfers (what shores to surf when)
- Use technical terms like "fetch window", "low-pressure center", "groundswell", "windswell"

Your credibility comes from:
- Citing actual data (buoy readings, pressure systems with locations)
- Explaining causation (this low at X location generates Y swell because Z fetch)
- Acknowledging when specialists disagree and explaining your reasoning
- Being conservative when confidence is low
- Providing shore-specific detail (N shore exposure to NW swells, shadowing effects, etc)

Format:
1. Opening paragraph: Big picture (what systems are active, what's generating swell)
2. Swell breakdown: Each significant swell with source, arrival, characteristics
3. Shore-by-shore: North, South, East, West with size/conditions/timing
4. Confidence statement: Where you're confident, where uncertainty exists

Write in first person as Pat. Use measurements in feet and compass directions."""

            # Use engine's centralized OpenAI client for cost tracking
            self.logger.info(f"Calling {self.model_name} for Caldwell-style forecast synthesis...")
            narrative = await self.engine.openai_client.call_openai_api(
                system_prompt=system_prompt, user_prompt=prompt
            )

            if narrative and len(narrative) > 0:
                self.logger.info("Generated Caldwell-style narrative successfully")
                return narrative
            else:
                self.logger.error("No content returned from OpenAI API")
                raise ValueError("OpenAI API returned empty content")

        except Exception as e:
            self.logger.error(f"Error generating Caldwell narrative: {e}")
            raise

    def _generate_template_forecast(
        self, shore_forecasts: dict, swell_breakdown: list[dict], contradictions: list[dict]
    ) -> str:
        """
        Generate template forecast when AI is unavailable.

        Args:
            shore_forecasts: Shore-specific forecasts
            swell_breakdown: Swell breakdown data
            contradictions: Detected contradictions

        Returns:
            Template forecast narrative
        """
        narrative = """OAHU SURF FORECAST - SYNTHESIZED ANALYSIS

SWELL OVERVIEW:
"""

        if swell_breakdown:
            narrative += "Multiple swell components active:\n\n"
            for swell in swell_breakdown:
                narrative += (
                    f"- {swell['direction']} swell: {swell['height']} @ {swell['period']}\n"
                )
                narrative += f"  Source: {swell['source']}\n"
                narrative += f"  Timing: {swell['timing']}\n"
                narrative += f"  Confidence: {swell['confidence']:.2f}\n\n"
        else:
            narrative += "Limited swell activity expected.\n\n"

        narrative += "\nSHORE-BY-SHORE BREAKDOWN:\n\n"

        shore_order = ["north_shore", "south_shore", "east_shore", "west_shore"]
        shore_names = {
            "north_shore": "North Shore",
            "south_shore": "South Shore",
            "east_shore": "East Shore",
            "west_shore": "West Shore",
        }

        for shore_key in shore_order:
            if shore_key in shore_forecasts:
                forecast = shore_forecasts[shore_key]
                narrative += f"{shore_names[shore_key]}: {forecast['size_range']}\n"
                narrative += f"  Conditions: {forecast['conditions']}\n"
                narrative += f"  Timing: {forecast['timing']}\n"
                narrative += f"  Confidence: {forecast['confidence']:.2f}\n\n"

        if contradictions:
            narrative += "\nDATA NOTES:\n"
            for contradiction in contradictions:
                narrative += f"- {contradiction['issue']}\n"
                narrative += f"  Resolution: {contradiction['resolution']}\n\n"

        narrative += "\n(Note: This is a template forecast. Configure OpenAI API for detailed AI-generated analysis in Pat Caldwell's style.)"

        return narrative
