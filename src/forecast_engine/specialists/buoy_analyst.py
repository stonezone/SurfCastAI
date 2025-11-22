"""
Buoy data analyst specialist for SurfCastAI forecast engine.

This module analyzes buoy observations from multiple stations,
detecting trends, anomalies, and cross-buoy agreement patterns.
"""

import logging
import os
from datetime import datetime
from statistics import mean, stdev
from typing import Any

from ...processing.models.buoy_data import BuoyData, BuoyObservation
from .base_specialist import BaseSpecialist
from .schemas import (
    BuoyAnalystData,
    BuoyAnalystOutput,
    BuoyAnomaly,
    BuoyTrend,
    CrossValidation,
    SummaryStats,
)


class BuoyAnalyst(BaseSpecialist):
    """
    Specialist for analyzing buoy observation data.

    Features:
    - Trend analysis (height, period, direction) over 48hr history
    - Anomaly detection using Z-score analysis
    - Cross-buoy agreement scoring
    - AI-generated narrative analysis using GPT-5-nano

    Input format:
        {
            'buoy_data': [list of BuoyData objects or dicts],
            'metadata': {optional metadata}
        }

    Output format:
        {
            'confidence': 0.0-1.0,
            'data': {
                'trends': [trend objects],
                'anomalies': [anomaly objects],
                'cross_validation': {agreement metrics}
            },
            'narrative': '500-1000 word analysis'
        }
    """

    def __init__(
        self,
        config: Any | None = None,
        model_name: str | None = None,
        engine: Any | None = None,
    ):
        """
        Initialize the buoy analyst.

        Args:
            config: Optional configuration object with OpenAI settings
            model_name: The specific OpenAI model this specialist instance should use (REQUIRED)
            engine: Reference to ForecastEngine for centralized API calls and cost tracking
        """
        super().__init__(config, model_name, engine)
        self.logger = logging.getLogger("specialist.buoy_analyst")

        # Validate engine parameter is provided
        if engine is None:
            raise ValueError(
                f"{self.__class__.__name__} requires engine parameter for API access. "
                "Template mode removed to prevent quality degradation."
            )
        self.engine = engine

        # Load OpenAI configuration
        # Note: model_name is now set by BaseSpecialist from config
        if config:
            self.openai_api_key = config.get("openai", "api_key") or os.environ.get(
                "OPENAI_API_KEY"
            )
            self.max_tokens = config.getint("openai", "max_tokens", 2000)
        else:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
            self.max_tokens = 2000

        # Anomaly detection threshold (standard deviations)
        self.anomaly_threshold = 2.0

    async def analyze(self, data: dict[str, Any]) -> BuoyAnalystOutput:
        """
        Analyze buoy data and return structured insights.

        Args:
            data: Dictionary with 'buoy_data' key containing list of buoy readings

        Returns:
            SpecialistOutput with trends, anomalies, cross-validation, and narrative

        Raises:
            ValueError: If input data is invalid
        """
        # Validate input
        self._validate_input(data, ["buoy_data"])

        buoy_data_list = data["buoy_data"]
        if not isinstance(buoy_data_list, list) or len(buoy_data_list) == 0:
            raise ValueError("buoy_data must be a non-empty list")

        self._log_analysis_start(f"{len(buoy_data_list)} buoys")

        try:
            # Convert dict format to BuoyData objects if needed
            buoy_objects = self._normalize_buoy_data(buoy_data_list)

            # Analyze trends for each buoy
            trends = self._analyze_trends(buoy_objects)

            # Detect anomalies
            anomalies = self._detect_anomalies(buoy_objects)

            # Assign quality flags based on anomalies and trends
            quality_flags = self._assign_quality_flags(buoy_objects, anomalies, trends)

            # Calculate cross-buoy agreement
            cross_validation = self._calculate_cross_validation(buoy_objects)

            # Calculate confidence based on data quality
            confidence = self._calculate_analysis_confidence(
                buoy_objects, trends, anomalies, cross_validation
            )

            # Prepare summary stats
            summary_stats_dict = self._calculate_summary_stats(buoy_objects)

            # Convert lists of dicts to Pydantic model instances
            buoy_trends = [BuoyTrend(**trend) for trend in trends]
            buoy_anomalies = [BuoyAnomaly(**anomaly) for anomaly in anomalies]
            cross_validation_obj = CrossValidation(**cross_validation)
            summary_stats_obj = SummaryStats(**summary_stats_dict)

            # Create BuoyAnalystData instance
            structured_data = BuoyAnalystData(
                trends=buoy_trends,
                anomalies=buoy_anomalies,
                quality_flags=quality_flags,
                cross_validation=cross_validation_obj,
                summary_stats=summary_stats_obj,
            )

            # Generate AI narrative (pass dict version for backward compatibility)
            narrative = await self._generate_narrative(
                {
                    "trends": trends,
                    "anomalies": anomalies,
                    "quality_flags": quality_flags,
                    "cross_validation": cross_validation,
                    "summary_stats": summary_stats_dict,
                },
                buoy_objects,
            )

            # Create metadata
            metadata = {
                "num_buoys": len(buoy_objects),
                "total_observations": sum(len(b.observations) for b in buoy_objects),
                "analysis_method": "trend_anomaly_cross_validation",
                "timestamp": datetime.now().isoformat(),
            }

            self._log_analysis_complete(confidence, metadata["total_observations"])

            # Return Pydantic model instead of SpecialistOutput
            return BuoyAnalystOutput(
                confidence=confidence, data=structured_data, narrative=narrative, metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error in buoy analysis: {e}")
            raise

    def _normalize_buoy_data(self, buoy_data_list: list[Any]) -> list[BuoyData]:
        """
        Convert mixed format buoy data to BuoyData objects.

        Args:
            buoy_data_list: List of BuoyData objects or dicts

        Returns:
            List of BuoyData objects
        """
        normalized = []
        for item in buoy_data_list:
            if isinstance(item, BuoyData):
                normalized.append(item)
            elif isinstance(item, dict):
                # Convert dict to BuoyData
                buoy = BuoyData(
                    station_id=item.get("station_id", "unknown"),
                    name=item.get("name"),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                    metadata=item.get("metadata", {}),
                )

                # Add observations
                for obs_dict in item.get("observations", []):
                    if isinstance(obs_dict, BuoyObservation):
                        buoy.observations.append(obs_dict)
                    elif isinstance(obs_dict, dict):
                        buoy.observations.append(
                            BuoyObservation(
                                timestamp=obs_dict.get("timestamp", ""),
                                wave_height=obs_dict.get("wave_height"),
                                dominant_period=obs_dict.get("dominant_period"),
                                average_period=obs_dict.get("average_period"),
                                wave_direction=obs_dict.get("wave_direction"),
                                wind_speed=obs_dict.get("wind_speed"),
                                wind_direction=obs_dict.get("wind_direction"),
                                air_temperature=obs_dict.get("air_temperature"),
                                water_temperature=obs_dict.get("water_temperature"),
                                pressure=obs_dict.get("pressure"),
                                raw_data=obs_dict.get("raw_data", {}),
                            )
                        )

                normalized.append(buoy)
            else:
                self.logger.warning(f"Skipping unknown buoy data type: {type(item)}")

        return normalized

    def _analyze_trends(self, buoy_data: list[BuoyData]) -> list[dict[str, Any]]:
        """
        Analyze trends in wave height, period, and direction.

        Args:
            buoy_data: List of BuoyData objects

        Returns:
            List of trend dictionaries
        """
        trends = []

        for buoy in buoy_data:
            if len(buoy.observations) < 2:
                continue

            # Extract time series data
            heights = []
            periods = []
            directions = []
            timestamps = []

            for obs in buoy.observations:
                if obs.wave_height is not None:
                    heights.append(obs.wave_height)
                    timestamps.append(obs.timestamp)
                if obs.dominant_period is not None:
                    periods.append(obs.dominant_period)
                if obs.wave_direction is not None:
                    directions.append(obs.wave_direction)

            # Calculate trends (simple linear slope)
            height_trend = self._calculate_trend(heights)
            period_trend = self._calculate_trend(periods)
            direction_trend = self._calculate_trend(directions)

            trend = {
                "buoy_id": buoy.station_id,
                "buoy_name": buoy.name or buoy.station_id,
                "height_trend": height_trend["description"],
                "height_slope": height_trend["slope"],
                "height_current": heights[-1] if heights else None,
                "period_trend": period_trend["description"],
                "period_slope": period_trend["slope"],
                "period_current": periods[-1] if periods else None,
                "direction_trend": direction_trend["description"],
                "direction_current": directions[-1] if directions else None,
                "observations_count": len(buoy.observations),
            }

            trends.append(trend)

        return trends

    def _calculate_trend(self, values: list[float]) -> dict[str, Any]:
        """
        Calculate simple linear trend.

        Args:
            values: List of values in chronological order

        Returns:
            Dictionary with slope and description
        """
        if len(values) < 2:
            return {"slope": 0.0, "description": "insufficient_data"}

        # Simple slope calculation: (last - first) / (n - 1)
        slope = (values[-1] - values[0]) / (len(values) - 1)

        # Categorize trend
        if abs(slope) < 0.01:
            description = "steady"
        elif slope > 0.1:
            description = "increasing_strong"
        elif slope > 0.05:
            description = "increasing_moderate"
        elif slope > 0:
            description = "increasing_slight"
        elif slope < -0.1:
            description = "decreasing_strong"
        elif slope < -0.05:
            description = "decreasing_moderate"
        else:
            description = "decreasing_slight"

        return {"slope": round(slope, 4), "description": description}

    def _detect_anomalies(self, buoy_data: list[BuoyData]) -> list[dict[str, Any]]:
        """
        Detect anomalies using Z-score analysis.

        Args:
            buoy_data: List of BuoyData objects

        Returns:
            List of anomaly dictionaries
        """
        anomalies = []

        # Calculate global statistics for comparison
        all_heights = []
        all_periods = []

        for buoy in buoy_data:
            for obs in buoy.observations:
                if obs.wave_height is not None:
                    all_heights.append(obs.wave_height)
                if obs.dominant_period is not None:
                    all_periods.append(obs.dominant_period)

        if len(all_heights) < 3 or len(all_periods) < 3:
            return anomalies  # Not enough data for meaningful statistics

        height_mean = mean(all_heights)
        height_std = stdev(all_heights)
        period_mean = mean(all_periods)
        period_std = stdev(all_periods)

        # Check each buoy for anomalies
        for buoy in buoy_data:
            latest_obs = buoy.latest_observation
            if not latest_obs:
                continue

            # Check wave height anomaly
            if latest_obs.wave_height is not None and height_std > 0:
                height_zscore = abs((latest_obs.wave_height - height_mean) / height_std)
                if height_zscore > self.anomaly_threshold:
                    anomalies.append(
                        {
                            "buoy_id": buoy.station_id,
                            "buoy_name": buoy.name or buoy.station_id,
                            "issue": "wave_height_anomaly",
                            "severity": "high" if height_zscore > 3.0 else "moderate",
                            "details": f"Height {latest_obs.wave_height}m is {height_zscore:.1f} std devs from mean {height_mean:.2f}m",
                            "z_score": round(height_zscore, 2),
                        }
                    )

            # Check period anomaly
            if latest_obs.dominant_period is not None and period_std > 0:
                period_zscore = abs((latest_obs.dominant_period - period_mean) / period_std)
                if period_zscore > self.anomaly_threshold:
                    anomalies.append(
                        {
                            "buoy_id": buoy.station_id,
                            "buoy_name": buoy.name or buoy.station_id,
                            "issue": "period_anomaly",
                            "severity": "high" if period_zscore > 3.0 else "moderate",
                            "details": f"Period {latest_obs.dominant_period}s is {period_zscore:.1f} std devs from mean {period_mean:.2f}s",
                            "z_score": round(period_zscore, 2),
                        }
                    )

        return anomalies

    def _assign_quality_flags(
        self,
        buoy_data: list[BuoyData],
        anomalies: list[dict[str, Any]],
        trends: list[dict[str, Any]],
    ) -> dict[str, str]:
        """
        Assign quality flags to each buoy based on anomalies and trends.

        Quality flag rules:
        - "excluded": High severity anomaly (Z-score > 3.0) OR single-scan spike
        - "suspect": Moderate anomaly OR strong declining trend with anomaly
        - "valid": Normal data with no significant issues

        Args:
            buoy_data: List of BuoyData objects
            anomalies: Detected anomalies
            trends: Trend analysis results

        Returns:
            Dictionary mapping buoy_id to quality_flag string
        """
        quality_flags = {}

        # Create lookup dictionaries for anomalies and trends
        anomaly_map = {}
        for anomaly in anomalies:
            buoy_id = anomaly["buoy_id"]
            severity = anomaly["severity"]
            z_score = anomaly.get("z_score", 0)

            if buoy_id not in anomaly_map:
                anomaly_map[buoy_id] = []
            anomaly_map[buoy_id].append(
                {"severity": severity, "z_score": z_score, "issue": anomaly["issue"]}
            )

        trend_map = {t["buoy_id"]: t for t in trends}

        # Assign quality flags for each buoy
        for buoy in buoy_data:
            buoy_id = buoy.station_id
            buoy_anomalies = anomaly_map.get(buoy_id, [])
            buoy_trend = trend_map.get(buoy_id, {})

            # Check for single-scan spike (only 1-2 observations OR large spike with declining trend)
            is_single_scan = len(buoy.observations) <= 2
            height_trend_desc = buoy_trend.get("height_trend", "")
            is_declining_strongly = (
                "decreasing_strong" in height_trend_desc
                or "decreasing_moderate" in height_trend_desc
            )

            # Determine quality flag
            if buoy_anomalies:
                # Check for high severity or single-scan spike
                has_high_severity = any(a["severity"] == "high" for a in buoy_anomalies)
                has_moderate_severity = any(a["severity"] == "moderate" for a in buoy_anomalies)

                if has_high_severity or (is_single_scan and buoy_anomalies):
                    # EXCLUDED: High severity anomaly or single-scan spike
                    quality_flags[buoy_id] = "excluded"
                    self.logger.warning(
                        f"Buoy {buoy_id} marked as EXCLUDED: "
                        f"{'high severity anomaly' if has_high_severity else 'single-scan spike'}"
                    )
                elif has_moderate_severity and is_declining_strongly:
                    # EXCLUDED: Moderate anomaly on declining trend (likely bad data from dying swell)
                    quality_flags[buoy_id] = "excluded"
                    self.logger.warning(
                        f"Buoy {buoy_id} marked as EXCLUDED: "
                        f"moderate anomaly on strongly declining trend"
                    )
                elif has_moderate_severity:
                    # SUSPECT: Moderate anomaly but not declining
                    quality_flags[buoy_id] = "suspect"
                    self.logger.info(f"Buoy {buoy_id} marked as SUSPECT: moderate anomaly")
                else:
                    # Default to valid if only minor issues
                    quality_flags[buoy_id] = "valid"
            else:
                # No anomalies = valid data
                quality_flags[buoy_id] = "valid"

        return quality_flags

    def _calculate_cross_validation(self, buoy_data: list[BuoyData]) -> dict[str, Any]:
        """
        Calculate agreement between buoys.

        Args:
            buoy_data: List of BuoyData objects

        Returns:
            Dictionary with agreement metrics
        """
        # Get latest observations from all buoys
        latest_heights = []
        latest_periods = []
        latest_directions = []

        for buoy in buoy_data:
            latest = buoy.latest_observation
            if latest:
                if latest.wave_height is not None:
                    latest_heights.append(latest.wave_height)
                if latest.dominant_period is not None:
                    latest_periods.append(latest.dominant_period)
                if latest.wave_direction is not None:
                    latest_directions.append(latest.wave_direction)

        # Calculate coefficient of variation (lower is better agreement)
        def calculate_agreement(values: list[float]) -> float:
            if len(values) < 2:
                return 0.0
            avg = mean(values)
            if avg == 0:
                return 0.0
            cv = stdev(values) / avg
            # Convert CV to agreement score (0-1, where 1 is perfect agreement)
            return max(0.0, 1.0 - min(cv, 1.0))

        height_agreement = calculate_agreement(latest_heights)
        period_agreement = calculate_agreement(latest_periods)

        # Overall agreement (weighted average)
        overall_agreement = height_agreement * 0.6 + period_agreement * 0.4

        return {
            "agreement_score": round(overall_agreement, 3),
            "height_agreement": round(height_agreement, 3),
            "period_agreement": round(period_agreement, 3),
            "num_buoys_compared": len(buoy_data),
            "interpretation": self._interpret_agreement(overall_agreement),
        }

    def _interpret_agreement(self, score: float) -> str:
        """Interpret agreement score."""
        if score >= 0.9:
            return "excellent_agreement"
        elif score >= 0.75:
            return "good_agreement"
        elif score >= 0.6:
            return "moderate_agreement"
        elif score >= 0.4:
            return "poor_agreement"
        else:
            return "very_poor_agreement"

    def _calculate_summary_stats(self, buoy_data: list[BuoyData]) -> dict[str, Any]:
        """
        Calculate summary statistics across all buoys.

        Args:
            buoy_data: List of BuoyData objects

        Returns:
            Dictionary with summary statistics
        """
        all_heights = []
        all_periods = []

        for buoy in buoy_data:
            for obs in buoy.observations:
                if obs.wave_height is not None:
                    all_heights.append(obs.wave_height)
                if obs.dominant_period is not None:
                    all_periods.append(obs.dominant_period)

        stats = {
            "avg_wave_height": round(mean(all_heights), 2) if all_heights else None,
            "max_wave_height": round(max(all_heights), 2) if all_heights else None,
            "min_wave_height": round(min(all_heights), 2) if all_heights else None,
            "avg_period": round(mean(all_periods), 2) if all_periods else None,
            "max_period": round(max(all_periods), 2) if all_periods else None,
            "min_period": round(min(all_periods), 2) if all_periods else None,
        }

        return stats

    def _calculate_analysis_confidence(
        self,
        buoy_data: list[BuoyData],
        trends: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        cross_validation: dict[str, Any],
    ) -> float:
        """
        Calculate overall confidence in the analysis.

        Args:
            buoy_data: List of BuoyData objects
            trends: Detected trends
            anomalies: Detected anomalies
            cross_validation: Cross-validation results

        Returns:
            Confidence score (0.0-1.0)
        """
        # Data completeness: how many buoys have data
        total_buoys = len(buoy_data)
        buoys_with_data = sum(1 for b in buoy_data if len(b.observations) > 0)
        completeness = buoys_with_data / max(total_buoys, 1)

        # Data consistency: based on cross-validation agreement
        consistency = cross_validation.get("agreement_score", 0.5)

        # Data quality: inverse of anomaly rate (fewer anomalies = higher quality)
        anomaly_rate = len(anomalies) / max(total_buoys, 1)
        quality = max(0.0, 1.0 - anomaly_rate)

        return self._calculate_confidence(completeness, consistency, quality)

    async def _generate_narrative(
        self, structured_data: dict[str, Any], buoy_data: list[BuoyData]
    ) -> str:
        """
        Generate AI narrative analysis using GPT-5-nano.

        Args:
            structured_data: Structured analysis data
            buoy_data: Original buoy data

        Returns:
            Natural language narrative (500-1000 words)
        """
        try:
            # Build analysis prompt
            prompt = self._build_analysis_prompt(structured_data, buoy_data)

            system_prompt = """You are an expert surf forecaster and oceanographer analyzing buoy data.
Your task is to provide a comprehensive analysis of buoy observations, focusing on:
1. Current wave conditions across all buoys
2. Trends in wave height, period, and direction
3. Any anomalies or unusual readings
4. Agreement between buoys and data reliability
5. Implications for surf forecasting

Write a 500-1000 word narrative analysis that is:
- Technical but accessible
- Focused on actionable insights
- Specific about locations and measurements
- Clear about confidence levels and uncertainties"""

            # Use engine's centralized OpenAI client for cost tracking
            self.logger.info(f"Calling {self.model_name} for buoy analysis narrative...")
            narrative = await self.engine.openai_client.call_openai_api(
                system_prompt=system_prompt, user_prompt=prompt
            )

            if narrative and len(narrative) > 0:
                self.logger.info("Generated AI narrative successfully")
                return narrative
            else:
                self.logger.error("No content returned from OpenAI API")
                raise ValueError("OpenAI API returned empty content")

        except Exception as e:
            self.logger.error(f"Error generating AI narrative: {e}")
            raise

    def _build_analysis_prompt(
        self, structured_data: dict[str, Any], buoy_data: list[BuoyData]
    ) -> str:
        """Build the analysis prompt for GPT."""
        trends = structured_data.get("trends", [])
        anomalies = structured_data.get("anomalies", [])
        cross_val = structured_data.get("cross_validation", {})
        stats = structured_data.get("summary_stats", {})

        prompt = f"""Analyze the following buoy data from {len(buoy_data)} stations around Oahu:

SUMMARY STATISTICS:
- Average wave height: {stats.get('avg_wave_height')}m (range: {stats.get('min_wave_height')}-{stats.get('max_wave_height')}m)
- Average period: {stats.get('avg_period')}s (range: {stats.get('min_period')}-{stats.get('max_period')}s)

TRENDS DETECTED:
"""

        for trend in trends:
            prompt += f"\n{trend['buoy_name']} ({trend['buoy_id']}):\n"
            prompt += f"  - Height: {trend['height_trend']} (current: {trend['height_current']}m, slope: {trend['height_slope']})\n"
            prompt += f"  - Period: {trend['period_trend']} (current: {trend['period_current']}s)\n"
            prompt += f"  - Direction: {trend['direction_trend']} (current: {trend['direction_current']}°)\n"

        prompt += f"\nANOMALIES DETECTED: {len(anomalies)}\n"
        for anomaly in anomalies:
            prompt += f"  - {anomaly['buoy_name']}: {anomaly['issue']} ({anomaly['severity']}) - {anomaly['details']}\n"

        prompt += "\nCROSS-BUOY VALIDATION:\n"
        prompt += f"  - Overall agreement: {cross_val.get('agreement_score')} ({cross_val.get('interpretation')})\n"
        prompt += f"  - Height agreement: {cross_val.get('height_agreement')}\n"
        prompt += f"  - Period agreement: {cross_val.get('period_agreement')}\n"

        prompt += "\nProvide a comprehensive analysis of these observations and their implications for surf forecasting."

        return prompt

    def _generate_template_narrative(self, structured_data: dict[str, Any]) -> str:
        """Generate a template narrative when AI is unavailable."""
        trends = structured_data.get("trends", [])
        anomalies = structured_data.get("anomalies", [])
        cross_val = structured_data.get("cross_validation", {})
        stats = structured_data.get("summary_stats", {})

        narrative = f"""BUOY ANALYSIS SUMMARY

Current conditions show an average wave height of {stats.get('avg_wave_height', 'N/A')}m
across {len(trends)} reporting buoys, with periods averaging {stats.get('avg_period', 'N/A')}s.

TREND ANALYSIS:
"""

        for trend in trends:
            narrative += f"\n{trend['buoy_name']}: "
            narrative += f"Height {trend['height_trend']}, Period {trend['period_trend']}"

        narrative += "\n\nDATA QUALITY:\n"
        narrative += f"Cross-buoy agreement: {cross_val.get('interpretation', 'unknown')}\n"
        narrative += f"Anomalies detected: {len(anomalies)}\n"

        if anomalies:
            narrative += "\nANOMALY DETAILS:\n"
            for anomaly in anomalies:
                narrative += (
                    f"- {anomaly['buoy_name']}: {anomaly['issue']} ({anomaly['severity']})\n"
                )

        narrative += (
            "\n(Note: This is a template narrative. Configure OpenAI API for detailed AI analysis.)"
        )

        return narrative
