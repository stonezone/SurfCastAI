"""
Buoy data processor for SurfCastAI.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from ..core.config import Config
from .data_processor import DataProcessor, ProcessingResult
from .models.buoy_data import BuoyData


class BuoyProcessor(DataProcessor[dict[str, Any], BuoyData]):
    """
    Processor for buoy data.

    Features:
    - Converts raw buoy data to standardized BuoyData model
    - Validates data completeness and consistency
    - Analyzes wave patterns and trends
    - Provides cleaned and normalized data for further processing
    """

    def __init__(self, config: Config):
        """
        Initialize the buoy processor.

        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger("processor.buoy")

    def validate(self, data: dict[str, Any]) -> list[str]:
        """
        Validate buoy data.

        Args:
            data: Raw buoy data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for required fields
        if "station_id" not in data:
            errors.append("Missing station_id field")

        # Check for observations
        if "observations" not in data or not data["observations"]:
            errors.append("No observations in buoy data")

        return errors

    def process(self, data: dict[str, Any]) -> ProcessingResult:
        """
        Process buoy data.

        Args:
            data: Raw buoy data or saved JSON format

        Returns:
            ProcessingResult with processed BuoyData
        """
        try:
            # Check if this is already saved JSON format (has 'station_id' and 'observations' keys)
            # or raw NDBC format
            import json

            if "station_id" in data and "observations" in data:
                # Already in saved format, use from_json
                buoy_data = BuoyData.from_json(json.dumps(data))
            else:
                # Raw NDBC format, use from_ndbc_json
                buoy_data = BuoyData.from_ndbc_json(data)

            # Check if we have any observations
            if not buoy_data.observations:
                return ProcessingResult(
                    success=False, error="No observations found in buoy data", data=buoy_data
                )

            # Clean and normalize data
            buoy_data = self._clean_observations(buoy_data)

            # Analyze data for quality and special conditions
            warnings, metadata = self._analyze_buoy_data(buoy_data)

            # Add metadata from analysis
            buoy_data.metadata.update(metadata)

            return ProcessingResult(
                success=True, data=buoy_data, warnings=warnings, metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error processing buoy data: {e}")
            return ProcessingResult(success=False, error=f"Processing error: {str(e)}")

    def process_file(self, file_path: str | Path) -> ProcessingResult:
        """
        Process data from a file, with spec file detection.

        Args:
            file_path: Path to the buoy data file

        Returns:
            ProcessingResult with processed BuoyData
        """
        # Call parent's process_file to load and process the data
        result = super().process_file(file_path)

        # If processing was successful and we have BuoyData, try to link spec file
        if result.success and isinstance(result.data, BuoyData):
            buoy_data = result.data
            station_id = buoy_data.station_id

            # Look for corresponding .spec file in www_ndbc_noaa_gov directory
            # The spec files are in the root data directory, not in bundles
            data_dir = Path(self.config.data_directory)
            spec_file = data_dir / "www_ndbc_noaa_gov" / f"{station_id}.spec"

            if spec_file.exists():
                buoy_data.spec_file_path = str(spec_file)
                self.logger.info(f"Found spectral data for buoy {station_id}: {spec_file}")
            else:
                self.logger.debug(f"No spectral data found for buoy {station_id} at {spec_file}")

        return result

    def detect_trend(self, buoy_data: BuoyData, hours: int = 24) -> dict[str, Any]:
        """
        Detect trends in wave height over the specified time period.

        Uses linear regression to calculate slope and determine trend direction.
        Threshold: slope > 0.2 feet/hour is considered increasing/decreasing.

        Args:
            buoy_data: Buoy data to analyze
            hours: Number of hours to look back (default: 24)

        Returns:
            Dictionary with trend information:
            - direction: 'increasing', 'decreasing', or 'stable'
            - slope: Rate of change in feet/hour
            - confidence: Confidence in trend (0.0-1.0)
            - r_squared: R-squared value of linear regression
        """
        # Extract wave heights and timestamps for the specified period
        cutoff_time = datetime.now() - timedelta(hours=hours)

        heights = []
        timestamps = []

        for obs in buoy_data.observations:
            if obs.wave_height is None:
                continue

            try:
                obs_time = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
                if obs_time >= cutoff_time.replace(tzinfo=obs_time.tzinfo):
                    # Convert meters to feet for slope calculation
                    heights.append(obs.wave_height * 3.28084)
                    timestamps.append(obs_time.timestamp())
            except (ValueError, TypeError):
                continue

        # Need at least 3 points for meaningful regression
        if len(heights) < 3:
            return {
                "direction": "unknown",
                "slope": 0.0,
                "confidence": 0.0,
                "r_squared": 0.0,
                "sample_size": len(heights),
            }

        # Convert timestamps to hours since first observation
        timestamps = np.array(timestamps)
        hours_elapsed = (timestamps - timestamps[0]) / 3600.0
        heights = np.array(heights)

        # Perform linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(hours_elapsed, heights)

        # Determine trend direction
        # Threshold: slope > 0.2 feet/hour = increasing (about 2.4 feet over 12 hours)
        # This is reasonable for detecting significant swell changes
        if slope > 0.2:
            direction = "increasing"
        elif slope < -0.2:
            direction = "decreasing"
        else:
            direction = "stable"

        # Calculate confidence based on r_squared and sample size
        r_squared = r_value**2
        sample_factor = min(1.0, len(heights) / 24.0)  # More samples = higher confidence
        confidence = r_squared * sample_factor

        return {
            "direction": direction,
            "slope": float(slope),
            "confidence": float(confidence),
            "r_squared": float(r_squared),
            "sample_size": len(heights),
            "p_value": float(p_value),
            "std_error": float(std_err),
        }

    def detect_anomalies(self, buoy_data: BuoyData, threshold: float = 2.0) -> dict[str, Any]:
        """
        Detect anomalous readings in buoy data using z-score method.

        Flags readings that are more than threshold standard deviations from the mean.

        Args:
            buoy_data: Buoy data to analyze
            threshold: Z-score threshold (default: 2.0)

        Returns:
            Dictionary with anomaly information:
            - anomalies: List of anomalous observation indices
            - anomaly_count: Number of anomalies detected
            - mean_height: Mean wave height
            - std_height: Standard deviation of wave height
            - z_scores: Z-scores for all observations
        """
        # Extract wave heights
        heights = []
        valid_indices = []

        for i, obs in enumerate(buoy_data.observations):
            if obs.wave_height is not None:
                heights.append(obs.wave_height)
                valid_indices.append(i)

        if len(heights) < 3:
            return {
                "anomalies": [],
                "anomaly_count": 0,
                "mean_height": 0.0,
                "std_height": 0.0,
                "z_scores": [],
                "sample_size": len(heights),
            }

        # Calculate z-scores
        heights_array = np.array(heights)
        mean_height = np.mean(heights_array)
        std_height = np.std(heights_array, ddof=1)  # Sample standard deviation

        # Avoid division by zero
        if std_height == 0:
            return {
                "anomalies": [],
                "anomaly_count": 0,
                "mean_height": float(mean_height),
                "std_height": 0.0,
                "z_scores": [0.0] * len(heights),
                "sample_size": len(heights),
            }

        z_scores = (heights_array - mean_height) / std_height

        # Find anomalies (|z-score| > threshold)
        anomaly_mask = np.abs(z_scores) > threshold
        anomalies = [valid_indices[i] for i in range(len(valid_indices)) if anomaly_mask[i]]

        # Log warnings for anomalies
        if anomalies:
            self.logger.warning(
                f"Detected {len(anomalies)} anomalous readings in buoy {buoy_data.station_id}"
            )
            for idx in anomalies:
                obs = buoy_data.observations[idx]
                z_score = z_scores[valid_indices.index(idx)]
                self.logger.debug(
                    f"Anomaly at {obs.timestamp}: wave_height={obs.wave_height}m, z-score={z_score:.2f}"
                )

        return {
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
            "mean_height": float(mean_height),
            "std_height": float(std_height),
            "z_scores": [float(z) for z in z_scores],
            "sample_size": len(heights),
            "threshold": threshold,
        }

    def calculate_quality_score(self, buoy_data: BuoyData) -> dict[str, Any]:
        """
        Calculate a quality score for buoy data based on freshness, completeness, and consistency.

        Score components:
        - Freshness: Based on age of latest observation (< 1 hour = 1.0)
        - Completeness: Percentage of observations with all fields present
        - Consistency: Based on lack of sudden jumps in values

        Args:
            buoy_data: Buoy data to score

        Returns:
            Dictionary with quality score information:
            - overall_score: Overall quality score (0.0-1.0)
            - freshness_score: Freshness score (0.0-1.0)
            - completeness_score: Completeness score (0.0-1.0)
            - consistency_score: Consistency score (0.0-1.0)
        """
        scores = {
            "overall_score": 0.0,
            "freshness_score": 0.0,
            "completeness_score": 0.0,
            "consistency_score": 0.0,
        }

        if not buoy_data.observations:
            return scores

        # 1. Calculate freshness score
        latest_obs = buoy_data.observations[0]
        try:
            obs_time = datetime.fromisoformat(latest_obs.timestamp.replace("Z", "+00:00"))
            now = datetime.now(obs_time.tzinfo)
            hours_old = (now - obs_time).total_seconds() / 3600

            # Score decreases linearly from 1.0 at 0 hours to 0.0 at 6 hours
            if hours_old <= 1.0:
                scores["freshness_score"] = 1.0
            elif hours_old >= 6.0:
                scores["freshness_score"] = 0.0
            else:
                scores["freshness_score"] = 1.0 - (hours_old - 1.0) / 5.0
        except (ValueError, TypeError):
            scores["freshness_score"] = 0.5  # Unknown freshness

        # 2. Calculate completeness score
        essential_fields = ["wave_height", "dominant_period", "wave_direction"]
        optional_fields = ["wind_speed", "wind_direction", "water_temperature"]
        all_fields = essential_fields + optional_fields

        complete_count = 0
        partial_count = 0

        for obs in buoy_data.observations:
            # Check essential fields
            essential_present = sum(
                1 for field in essential_fields if getattr(obs, field) is not None
            )

            if essential_present == len(essential_fields):
                # Check optional fields
                optional_present = sum(
                    1 for field in optional_fields if getattr(obs, field) is not None
                )
                if optional_present == len(optional_fields):
                    complete_count += 1
                else:
                    partial_count += 1
            else:
                partial_count += 1

        total_obs = len(buoy_data.observations)
        scores["completeness_score"] = (complete_count + 0.5 * partial_count) / total_obs

        # 3. Calculate consistency score (check for sudden jumps)
        if len(buoy_data.observations) < 2:
            scores["consistency_score"] = 1.0
        else:
            jump_count = 0
            checked_pairs = 0

            for i in range(len(buoy_data.observations) - 1):
                current = buoy_data.observations[i]
                next_obs = buoy_data.observations[i + 1]

                # Check wave height consistency
                if current.wave_height is not None and next_obs.wave_height is not None:
                    checked_pairs += 1
                    # Flag as jump if change is more than 2 meters between observations
                    height_diff = abs(current.wave_height - next_obs.wave_height)
                    if height_diff > 2.0:
                        jump_count += 1

            if checked_pairs > 0:
                scores["consistency_score"] = 1.0 - (jump_count / checked_pairs)
            else:
                scores["consistency_score"] = 1.0

        # 4. Calculate overall score (weighted average)
        scores["overall_score"] = (
            0.4 * scores["freshness_score"]
            + 0.3 * scores["completeness_score"]
            + 0.3 * scores["consistency_score"]
        )

        return scores

    def _clean_observations(self, buoy_data: BuoyData) -> BuoyData:
        """
        Clean and normalize buoy observations.

        Args:
            buoy_data: Original buoy data

        Returns:
            Cleaned buoy data
        """
        # Filter out observations with missing essential data
        valid_observations = []
        for obs in buoy_data.observations:
            # Skip observations with no wave height or period
            if obs.wave_height is None and obs.dominant_period is None:
                continue

            # Clean up invalid values
            if obs.wave_height is not None and obs.wave_height < 0:
                obs.wave_height = None

            if obs.dominant_period is not None and obs.dominant_period < 0:
                obs.dominant_period = None

            if obs.wave_direction is not None and (
                obs.wave_direction < 0 or obs.wave_direction > 360
            ):
                obs.wave_direction = None

            valid_observations.append(obs)

        # Sort observations by timestamp (newest first)
        valid_observations.sort(
            key=lambda obs: (
                datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
                if "T" in obs.timestamp
                else datetime.now()
            ),
            reverse=True,
        )

        # Update buoy data with cleaned observations
        buoy_data.observations = valid_observations

        return buoy_data

    def _analyze_buoy_data(self, buoy_data: BuoyData) -> tuple[list[str], dict[str, Any]]:
        """
        Analyze buoy data for quality and special conditions.

        Enhanced with:
        - Trend detection (linear regression)
        - Anomaly detection (z-scores)
        - Quality scoring (freshness, completeness, consistency)

        Args:
            buoy_data: Buoy data to analyze

        Returns:
            Tuple of (warnings, metadata)
        """
        warnings = []
        metadata = {
            "analysis": {
                "timestamp": datetime.now().isoformat(),
                "quality_score": 1.0,
                "trends": {},
                "anomalies": {},
                "quality_details": {},
                "special_conditions": [],
            }
        }

        # Run enhanced analysis methods
        try:
            # 1. Detect trends
            trend_info = self.detect_trend(buoy_data, hours=24)
            metadata["analysis"]["trends"] = trend_info

            # Log trend information
            if trend_info["confidence"] > 0.5:
                trend_msg = (
                    f"Wave height trend: {trend_info['direction']} "
                    f"(slope: {trend_info['slope']:.3f} ft/hr, "
                    f"confidence: {trend_info['confidence']:.2f})"
                )
                self.logger.info(trend_msg)

                # Add warning for significant trends
                if trend_info["direction"] == "increasing" and abs(trend_info["slope"]) > 1.0:
                    warnings.append(
                        f"Rapidly increasing wave heights detected ({trend_info['slope']:.2f} ft/hr)"
                    )
                elif trend_info["direction"] == "decreasing" and abs(trend_info["slope"]) > 1.0:
                    warnings.append(
                        f"Rapidly decreasing wave heights detected ({trend_info['slope']:.2f} ft/hr)"
                    )

        except Exception as e:
            self.logger.warning(f"Failed to detect trends: {e}")

        try:
            # 2. Detect anomalies
            anomaly_info = self.detect_anomalies(buoy_data, threshold=2.0)
            metadata["analysis"]["anomalies"] = anomaly_info

            # Adjust quality score based on anomaly count
            if anomaly_info["anomaly_count"] > 0:
                anomaly_ratio = anomaly_info["anomaly_count"] / max(1, anomaly_info["sample_size"])
                anomaly_penalty = min(0.5, anomaly_ratio * 2.0)  # Max 0.5 penalty
                metadata["analysis"]["quality_score"] -= anomaly_penalty

                warnings.append(
                    f"Detected {anomaly_info['anomaly_count']} anomalous readings - "
                    f"data reliability reduced"
                )

        except Exception as e:
            self.logger.warning(f"Failed to detect anomalies: {e}")

        try:
            # 3. Calculate quality score
            quality_info = self.calculate_quality_score(buoy_data)
            metadata["analysis"]["quality_details"] = quality_info

            # Use the detailed quality score as the overall score
            metadata["analysis"]["quality_score"] = quality_info["overall_score"]

            # Add warnings for low quality scores
            if quality_info["overall_score"] < 0.4:
                warnings.append(
                    f"Poor data quality (score: {quality_info['overall_score']:.2f}) - "
                    f"use with caution"
                )
            elif quality_info["overall_score"] < 0.6:
                warnings.append(
                    f"Moderate data quality (score: {quality_info['overall_score']:.2f})"
                )

            # Specific warnings for quality components
            if quality_info["freshness_score"] < 0.5:
                warnings.append("Data is not fresh - may not reflect current conditions")
            if quality_info["completeness_score"] < 0.5:
                warnings.append("Incomplete data - missing essential fields")
            if quality_info["consistency_score"] < 0.7:
                warnings.append("Inconsistent data - sudden jumps detected")

        except Exception as e:
            self.logger.warning(f"Failed to calculate quality score: {e}")

        # Store weight for data fusion based on quality score
        metadata["analysis"]["weight"] = metadata["analysis"]["quality_score"]

        # Check data freshness
        if buoy_data.observations:
            latest_obs = buoy_data.observations[0]
            try:
                obs_time = datetime.fromisoformat(latest_obs.timestamp.replace("Z", "+00:00"))
                now = datetime.now(obs_time.tzinfo)
                hours_old = (now - obs_time).total_seconds() / 3600

                metadata["analysis"]["hours_since_update"] = hours_old

                if hours_old > 6:
                    warnings.append(f"Buoy data is {hours_old:.1f} hours old")
                    metadata["analysis"]["quality_score"] -= min(0.5, hours_old / 24)
            except (ValueError, TypeError):
                warnings.append("Could not parse observation timestamp")

        # Check for data gaps
        if len(buoy_data.observations) >= 2:
            gap_found = False
            for i in range(len(buoy_data.observations) - 1):
                try:
                    current = datetime.fromisoformat(
                        buoy_data.observations[i].timestamp.replace("Z", "+00:00")
                    )
                    next_obs = datetime.fromisoformat(
                        buoy_data.observations[i + 1].timestamp.replace("Z", "+00:00")
                    )
                    gap = (current - next_obs).total_seconds() / 3600

                    if gap > 3:  # More than 3 hours between observations
                        gap_found = True
                        break
                except (ValueError, TypeError):
                    continue

            if gap_found:
                warnings.append("Gaps found in buoy data time series")
                metadata["analysis"]["quality_score"] -= 0.2

        # Analyze wave height trends
        if len(buoy_data.observations) >= 3:
            heights = []
            for obs in buoy_data.observations[:12]:  # Use up to 12 recent observations
                if obs.wave_height is not None:
                    heights.append(obs.wave_height)

            if heights:
                # Calculate trend
                if len(heights) >= 3:
                    if heights[0] > heights[-1]:
                        trend = "increasing"
                    elif heights[0] < heights[-1]:
                        trend = "decreasing"
                    else:
                        trend = "stable"

                    metadata["analysis"]["trends"]["wave_height"] = trend

                # Calculate stats
                metadata["analysis"]["trends"]["max_height"] = max(heights)
                metadata["analysis"]["trends"]["min_height"] = min(heights)
                metadata["analysis"]["trends"]["avg_height"] = sum(heights) / len(heights)

        # Check for special conditions
        latest = buoy_data.latest_observation
        if latest:
            # Check for large swell
            if latest.wave_height is not None and latest.wave_height > 4.0:  # 4m ~ 13ft
                metadata["analysis"]["special_conditions"].append("large_swell")

            # Check for long period swell
            if latest.dominant_period is not None and latest.dominant_period > 16.0:
                metadata["analysis"]["special_conditions"].append("long_period_swell")

            # Check for storm conditions
            if (
                latest.wind_speed is not None
                and latest.wind_speed > 15.0
                and latest.wave_height is not None
                and latest.wave_height > 3.0
            ):
                metadata["analysis"]["special_conditions"].append("storm_conditions")

        return warnings, metadata

    def get_hawaii_scale(self, meters: float) -> float:
        """
        Convert wave height from meters to Hawaiian scale.

        Hawaiian scale measures wave height from the back of the wave,
        approximately equal to the significant wave height (not face height).
        Face height is typically 1.5-2x the Hawaiian scale.

        Args:
            meters: Significant wave height in meters

        Returns:
            Wave height in Hawaiian scale (feet)
        """
        # Hawaiian scale ≈ Hs in feet (back height)
        # DO NOT multiply by 2 - that would give face height
        return meters * 3.28084  # 1m = 3.28084ft  # 1m = 3.28084ft
