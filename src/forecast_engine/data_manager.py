"""
Data preparation and management for forecast generation.

This module handles all data transformation, quality filtering, and assembly
for the forecast engine, separating data concerns from AI orchestration.
"""

import copy
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..processing.models.swell_event import SwellForecast
from .context_builder import build_context


class ForecastDataManager:
    """
    Manages data preparation and transformation for forecast generation.

    This class handles:
    - Quality filtering (excludes flagged data)
    - Image collection and selection
    - Seasonal context generation
    - Token estimation
    - Data formatting for AI consumption

    Extracted from ForecastEngine to follow Single Responsibility Principle.
    """

    def __init__(
        self,
        max_images: int = 10,
        image_detail_pressure: str = "high",
        image_detail_wave: str = "auto",
        image_detail_satellite: str = "auto",
        image_detail_sst: str = "low",
        logger: logging.Logger | None = None,
    ):
        """
        Initialize data manager with configuration.

        Args:
            max_images: Maximum number of images to include (hard cap: 10)
            image_detail_pressure: Detail level for pressure charts (high/auto/low)
            image_detail_wave: Detail level for wave models (high/auto/low)
            image_detail_satellite: Detail level for satellite imagery (high/auto/low)
            image_detail_sst: Detail level for SST charts (high/auto/low)
            logger: Logger instance for this manager
        """
        self.max_images = max_images
        self.image_detail_pressure = image_detail_pressure
        self.image_detail_wave = image_detail_wave
        self.image_detail_satellite = image_detail_satellite
        self.image_detail_sst = image_detail_sst
        self.logger = logger or logging.getLogger("forecast.data_manager")

        # Log configuration
        self.logger.info(f"Data Manager initialized: max_images={self.max_images}")
        self.logger.info(
            f"Image detail levels: pressure={self.image_detail_pressure}, "
            f"wave={self.image_detail_wave}, satellite={self.image_detail_satellite}, "
            f"sst={self.image_detail_sst}"
        )

    def prepare_forecast_data(self, swell_forecast: SwellForecast) -> dict[str, Any]:
        """
        Prepare comprehensive forecast data from SwellForecast.

        This method:
        1. Filters out excluded data (quality_flag='excluded')
        2. Builds shore-specific data
        3. Adds seasonal context
        4. Collects and organizes images
        5. Builds rich context strings for LLM prompts

        USAGE CONTEXT:
        - Called ALWAYS for both specialist and monolithic workflows
        - Filters SwellEvent objects directly before forecast generation
        - Primary quality gate ensuring excluded data never reaches AI models

        QUALITY FILTERING:
        This method performs comprehensive filtering:
        - Removes swell events with quality_flag='excluded'
        - Removes excluded components within valid events
        - Logs exclusion details for debugging
        - Ensures AI models only receive validated, high-quality data

        Args:
            swell_forecast: Processed swell forecast data

        Returns:
            Dictionary with prepared data for templates
        """
        # Calculate date range
        start_date = datetime.now().strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        # Extract confidence data
        confidence = swell_forecast.metadata.get("confidence", {})

        # FILTER EXCLUDED DATA BEFORE FORECAST GENERATION
        # Track exclusions for logging
        excluded_event_count = 0
        excluded_component_count = 0

        # Filter out events with quality_flag == "excluded"
        valid_swell_events = []
        for event in swell_forecast.swell_events:
            if event.quality_flag == "excluded":
                excluded_event_count += 1
                self.logger.warning(
                    f"Excluding swell event {event.event_id} from forecast "
                    f"(quality_flag={event.quality_flag}): "
                    f"{event.primary_direction_cardinal} {event.hawaii_scale}ft @ {event.dominant_period}s"
                )
                continue

            # Filter components within valid events
            valid_primary = [c for c in event.primary_components if c.quality_flag != "excluded"]
            valid_secondary = [
                c for c in event.secondary_components if c.quality_flag != "excluded"
            ]

            # Count excluded components
            excluded_primary = len(event.primary_components) - len(valid_primary)
            excluded_secondary = len(event.secondary_components) - len(valid_secondary)
            excluded_component_count += excluded_primary + excluded_secondary

            if excluded_primary > 0 or excluded_secondary > 0:
                self.logger.warning(
                    f"Excluding {excluded_primary} primary + {excluded_secondary} secondary components "
                    f"from event {event.event_id}"
                )

            # Only include events that still have at least one valid component
            if valid_primary or valid_secondary:
                # Create filtered event
                event.primary_components = valid_primary
                event.secondary_components = valid_secondary
                valid_swell_events.append(event)
            else:
                excluded_event_count += 1
                self.logger.warning(
                    f"Excluding event {event.event_id} - no valid components remaining after filtering"
                )

        # Log summary of exclusions
        if excluded_event_count > 0 or excluded_component_count > 0:
            self.logger.info(
                f"Quality filtering: excluded {excluded_event_count} events and "
                f"{excluded_component_count} components from forecast"
            )

        # Prepare swell events (now using filtered list)
        swell_events = []
        for event in valid_swell_events:
            swell_events.append(
                {
                    "event_id": event.event_id,
                    "start_time": event.start_time,
                    "peak_time": event.peak_time,
                    "end_time": event.end_time,
                    "primary_direction": event.primary_direction,
                    "primary_direction_cardinal": event.primary_direction_cardinal,
                    "significance": event.significance,
                    "hawaii_scale": event.hawaii_scale,
                    "source": event.source,
                    "dominant_period": event.dominant_period,
                    "primary_components": [
                        {
                            "height": c.height,
                            "period": c.period,
                            "direction": c.direction,
                            "confidence": c.confidence,
                            "source": c.source,
                        }
                        for c in event.primary_components
                    ],
                }
            )

        # Prepare shore data
        shore_data = {}
        for location in swell_forecast.locations:
            shore_name = location.shore.lower().replace(" ", "_")

            # Get shore-specific swell events (filter excluded data)
            shore_events = []
            for event in location.swell_events:
                # Skip excluded events
                if event.quality_flag == "excluded":
                    continue

                # Filter excluded components
                valid_primary = [
                    c for c in event.primary_components if c.quality_flag != "excluded"
                ]
                valid_secondary = [
                    c for c in event.secondary_components if c.quality_flag != "excluded"
                ]

                # Only include events with at least one valid component
                if not valid_primary and not valid_secondary:
                    continue
                shore_events.append(
                    {
                        "event_id": event.event_id,
                        "start_time": event.start_time,
                        "peak_time": event.peak_time,
                        "end_time": event.end_time,
                        "primary_direction": event.primary_direction,
                        "primary_direction_cardinal": event.primary_direction_cardinal,
                        "significance": event.significance,
                        "hawaii_scale": event.hawaii_scale,
                        "source": event.source,
                        "dominant_period": event.dominant_period,
                        "exposure_factor": event.metadata.get(f"exposure_{shore_name}", 0.5),
                        "primary_components": [
                            {
                                "height": c.height,
                                "period": c.period,
                                "direction": c.direction,
                                "confidence": c.confidence,
                                "source": c.source,
                            }
                            for c in valid_primary
                        ],
                    }
                )

            shore_data[shore_name] = {
                "name": location.shore,
                "swell_events": shore_events,
                "metadata": location.metadata,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "facing_direction": location.facing_direction,
            }

        # Determine primary shores based on activity
        primary_shores = []
        if shore_data.get("north_shore", {}).get("swell_events"):
            primary_shores.append("North Shore")
        if shore_data.get("south_shore", {}).get("swell_events"):
            primary_shores.append("South Shore")

        # Prepare forecast data
        forecast_data = {
            "forecast_id": swell_forecast.forecast_id,
            "start_date": start_date,
            "end_date": end_date,
            "region": "Oahu",
            "shores": primary_shores,
            "swell_events": swell_events,
            "shore_data": shore_data,
            "confidence": confidence,
            "metadata": swell_forecast.metadata,
        }

        # Add seasonal context
        forecast_data["seasonal_context"] = self.get_seasonal_context()

        # Collect available images from bundle
        bundle_id = swell_forecast.metadata.get("bundle_id")
        images = self.collect_bundle_images(bundle_id) if bundle_id else {}
        forecast_data["images"] = images

        # Build rich context strings for the LLM prompts
        context_summary = build_context(forecast_data)
        forecast_data["data_digest"] = context_summary.get("data_digest", "")
        forecast_data["shore_digests"] = context_summary.get("shore_digests", {})

        return forecast_data

    def filter_quality_data(self, fused_data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter data by quality flags before passing to specialists.

        USAGE CONTEXT:
        - Called ONLY when use_specialist_team=true
        - Currently UNUSED because specialist workflow is commented out
        - Filters dictionary-formatted data for specialist consumption
        - Complements prepare_forecast_data() filtering (which always runs)

        WHY TWO FILTERING METHODS EXIST:
        - This method: Filters dict-based data for specialist analysts (BuoyAnalyst, PressureAnalyst)
        - prepare_forecast_data(): Filters SwellEvent objects for main forecast generation
        - Different workflows require different data formats, hence different filtering methods

        FUTURE INTEGRATION:
        When specialist workflow is re-enabled, this method will provide pre-filtered
        data to specialists, ensuring they only analyze valid observations.

        Removes entries marked with quality_flag='excluded' from:
        - buoy_observations
        - swell_events (including their components)

        Args:
            fused_data: Raw fused data from DataFusionSystem

        Returns:
            Filtered copy of fused_data with excluded entries removed
        """
        # Create a deep copy to avoid modifying original
        filtered = copy.deepcopy(fused_data)

        # Filter buoy observations
        if "buoy_observations" in filtered:
            original_count = len(filtered["buoy_observations"])
            filtered["buoy_observations"] = [
                obs
                for obs in filtered["buoy_observations"]
                if obs.get("quality_flag") != "excluded"
            ]
            excluded_count = original_count - len(filtered["buoy_observations"])
            if excluded_count > 0:
                self.logger.info(
                    f"Filtered {excluded_count} excluded buoy observations "
                    f"({len(filtered['buoy_observations'])} remaining)"
                )

        # Filter swell events (including components)
        if "swell_events" in filtered:
            original_event_count = len(filtered["swell_events"])
            valid_events = []
            excluded_component_count = 0

            for event in filtered["swell_events"]:
                # Skip events marked as excluded
                if event.get("quality_flag") == "excluded":
                    continue

                # Filter components within valid events
                if "primary_components" in event:
                    original_primary = len(event["primary_components"])
                    event["primary_components"] = [
                        c
                        for c in event["primary_components"]
                        if c.get("quality_flag") != "excluded"
                    ]
                    excluded_component_count += original_primary - len(event["primary_components"])

                if "secondary_components" in event:
                    original_secondary = len(event["secondary_components"])
                    event["secondary_components"] = [
                        c
                        for c in event["secondary_components"]
                        if c.get("quality_flag") != "excluded"
                    ]
                    excluded_component_count += original_secondary - len(
                        event["secondary_components"]
                    )

                # Only include events with at least one valid component
                has_primary = event.get("primary_components", [])
                has_secondary = event.get("secondary_components", [])
                if has_primary or has_secondary:
                    valid_events.append(event)

            filtered["swell_events"] = valid_events
            excluded_event_count = original_event_count - len(valid_events)

            if excluded_event_count > 0 or excluded_component_count > 0:
                self.logger.info(
                    f"Filtered {excluded_event_count} excluded swell events and "
                    f"{excluded_component_count} excluded components "
                    f"({len(valid_events)} events remaining)"
                )

        return filtered

    def collect_bundle_images(self, bundle_id: str) -> dict[str, list[str]]:
        """
        Collect image paths from bundle directories.

        Organizes images by type:
        - pressure_charts: Surface pressure forecasts
        - satellite: Satellite imagery
        - wave_models: Wave height/direction forecasts
        - sst_charts: Sea surface temperature anomaly charts

        Args:
            bundle_id: Bundle identifier

        Returns:
            Dict with keys: 'pressure_charts', 'satellite', 'wave_models', 'sst_charts'
        """
        bundle_path = Path("data") / bundle_id
        images = {"pressure_charts": [], "satellite": [], "wave_models": [], "sst_charts": []}

        # Collect chart images and separate SST charts
        charts_dir = bundle_path / "charts"
        if charts_dir.exists():
            metadata_file = charts_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        chart_metadata = json.load(f)
                        for item in chart_metadata:
                            if item.get("status") == "success" and item.get("file_path"):
                                file_path = item["file_path"]
                                # Separate SST charts from pressure charts
                                if (
                                    "sst" in file_path.lower()
                                    or "sea_surface_temp" in file_path.lower()
                                ):
                                    images["sst_charts"].append(file_path)
                                else:
                                    images["pressure_charts"].append(file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to read chart metadata: {e}")

        # Collect satellite images
        satellite_dir = bundle_path / "satellite" / "satellite"
        if satellite_dir.exists():
            try:
                for img_path in list(satellite_dir.glob("*.png")) + list(
                    satellite_dir.glob("*.jpg")
                ):
                    images["satellite"].append(str(img_path))
            except Exception as e:
                self.logger.warning(f"Failed to collect satellite images: {e}")

        # Collect wave model images
        model_dir = bundle_path / "models"
        if model_dir.exists():
            try:
                for img_path in list(model_dir.glob("*.png")) + list(model_dir.glob("*.jpg")):
                    images["wave_models"].append(str(img_path))
            except Exception as e:
                self.logger.warning(f"Failed to collect wave model images: {e}")

        total_images = sum(len(v) for v in images.values())
        self.logger.info(
            f"Collected images: {total_images} total "
            f"(pressure: {len(images['pressure_charts'])}, sst: {len(images['sst_charts'])}, "
            f"satellite: {len(images['satellite'])}, wave_models: {len(images['wave_models'])})"
        )
        return images

    def select_critical_images(
        self, images: dict[str, list[str]], max_images: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Select most valuable images within token budget.

        OPTIMIZED FOR TEMPORAL EVOLUTION ANALYSIS (GPT-5 Vision):
        Focus on DEPTH (temporal sequences) over variety to enable AI insights
        humans can't achieve - simultaneous analysis of complete temporal evolution.

        Priority:
        1. Pressure chart evolution (configurable detail) - 4 images (0hr, 24hr, 48hr, 96hr)
           Track lows, highs, fronts over time to identify system movement patterns
        2. Wave forecast evolution (configurable detail) - 4 images (0hr, 24hr, 48hr, 96hr)
           Validate fetch predictions and swell propagation over time
        3. Satellite imagery (configurable detail) - 1 image
           Latest cloud patterns for system validation
        4. SST anomaly (configurable detail) - 1 image
           Storm intensity context (low detail sufficient for anomaly patterns)

        Args:
            images: Dict with keys 'pressure_charts', 'satellite', 'wave_models', 'sst_charts'
            max_images: Maximum number of images to select (default: from config, hard cap: 10)

        Returns:
            List of dicts: [{"url": "...", "detail": "high/auto/low", "type": "pressure_chart/satellite/wave_model/sst"}, ...]
        """
        # Use configured max_images if not provided
        if max_images is None:
            max_images = self.max_images

        # Enforce hard cap (GPT-5 limit)
        max_images = min(max_images, 10)
        selected = []

        # Priority 1: Pressure chart evolution - 4 images at configured detail
        # 0hr, 24hr, 48hr, 96hr surface forecasts showing system movement
        pressure_charts = images.get("pressure_charts", [])
        for i, chart in enumerate(pressure_charts[:4]):
            selected.append(
                {
                    "url": chart,
                    "detail": self.image_detail_pressure,
                    "type": "pressure_chart",
                    "description": f"Pressure forecast T+{i*24}hr",
                }
            )
            if len(selected) >= max_images:
                return selected

        # Priority 2: Wave forecast evolution - 4 images at configured detail
        # 0hr, 24hr, 48hr, 96hr wave heights/directions validating pressure systems
        wave_models = images.get("wave_models", [])
        for i, wave in enumerate(wave_models[:4]):
            selected.append(
                {
                    "url": wave,
                    "detail": self.image_detail_wave,
                    "type": "wave_model",
                    "description": f"Wave model T+{i*24}hr",
                }
            )
            if len(selected) >= max_images:
                return selected

        # Priority 3: Satellite imagery - 1 image at configured detail
        # Latest cloud patterns for validation
        satellite_imgs = images.get("satellite", [])
        if satellite_imgs:
            selected.append(
                {
                    "url": satellite_imgs[0],
                    "detail": self.image_detail_satellite,
                    "type": "satellite",
                    "description": "Latest satellite imagery",
                }
            )
            if len(selected) >= max_images:
                return selected

        # Priority 4: SST anomaly - 1 image at configured detail
        # Affects storm intensity - low detail sufficient for anomaly patterns
        sst_charts = images.get("sst_charts", [])
        if sst_charts:
            selected.append(
                {
                    "url": sst_charts[0],
                    "detail": self.image_detail_sst,
                    "type": "sst_chart",
                    "description": "Sea surface temperature anomaly",
                }
            )

        return selected[:max_images]

    def get_seasonal_context(self) -> dict[str, Any]:
        """
        Get seasonal context information for forecast generation.

        Returns seasonal patterns for North and South shores based on current month:
        - Winter (Nov-Mar): North Shore prime, South Shore flat
        - Summer (Jun-Aug): South Shore prime, North Shore flat
        - Spring (Apr-May): Transition with decreasing North, increasing South
        - Fall (Sep-Oct): Transition with increasing North, decreasing South

        Returns:
            Dictionary with seasonal context including:
            - current_season: 'winter', 'spring', 'summer', or 'fall'
            - month: Current month (1-12)
            - seasonal_patterns: Shore-specific patterns for current season
        """
        now = datetime.now()
        month = now.month

        # Determine season
        if 11 <= month <= 12 or 1 <= month <= 3:
            season = "winter"
        elif 4 <= month <= 5:
            season = "spring"
        elif 6 <= month <= 8:
            season = "summer"
        else:  # 9, 10
            season = "fall"

        # Seasonal patterns
        seasonal_info = {
            "winter": {
                "north_shore": {
                    "primary_swell_direction": "NW",
                    "typical_size_range": "4-12+ feet (Hawaiian)",
                    "quality": "High",
                    "consistency": "High",
                    "typical_conditions": "Consistent NW to N swells with varying wind conditions. Prime season for North Shore with frequent large swells.",
                },
                "south_shore": {
                    "primary_swell_direction": "Background S",
                    "typical_size_range": "0-2 feet (Hawaiian)",
                    "quality": "Low",
                    "consistency": "Low",
                    "typical_conditions": "Generally flat with occasional small background swells. Not prime season for South Shore.",
                },
            },
            "summer": {
                "north_shore": {
                    "primary_swell_direction": "Background NW",
                    "typical_size_range": "0-3 feet (Hawaiian)",
                    "quality": "Low",
                    "consistency": "Low",
                    "typical_conditions": "Generally flat with occasional small background swells. Not prime season for North Shore.",
                },
                "south_shore": {
                    "primary_swell_direction": "S to SW",
                    "typical_size_range": "2-5+ feet (Hawaiian)",
                    "quality": "High",
                    "consistency": "High",
                    "typical_conditions": "Consistent S to SW swells with generally favorable trade winds. Prime season for South Shore.",
                },
            },
            "spring": {
                "north_shore": {
                    "primary_swell_direction": "NW to N",
                    "typical_size_range": "3-8 feet (Hawaiian)",
                    "quality": "Medium-High",
                    "consistency": "Medium",
                    "typical_conditions": "Transition season with decreasing NW swells but generally good conditions with lighter winds.",
                },
                "south_shore": {
                    "primary_swell_direction": "S",
                    "typical_size_range": "1-3+ feet (Hawaiian)",
                    "quality": "Medium",
                    "consistency": "Medium",
                    "typical_conditions": "Beginning of south swell season with increasing activity and size.",
                },
            },
            "fall": {
                "north_shore": {
                    "primary_swell_direction": "NW to WNW",
                    "typical_size_range": "2-6+ feet (Hawaiian)",
                    "quality": "Medium",
                    "consistency": "Medium",
                    "typical_conditions": "Early season NW swells begin to arrive. Transition period with improving conditions as winter approaches.",
                },
                "south_shore": {
                    "primary_swell_direction": "S to SSW",
                    "typical_size_range": "1-3 feet (Hawaiian)",
                    "quality": "Medium-Low",
                    "consistency": "Medium-Low",
                    "typical_conditions": "End of south swell season with decreasing activity and size.",
                },
            },
        }

        return {
            "current_season": season,
            "month": month,
            "seasonal_patterns": seasonal_info[season],
        }

    def estimate_tokens(self, forecast_data: dict[str, Any]) -> int:
        """
        Estimate total token usage for forecast generation.

        This estimates tokens from:
        - Text data (swell events, shore data, prompts)
        - Images (based on detail level)
        - Expected output

        Token calculation:
        - Text: ~4 chars per token
        - Images (high detail): 3000 tokens
        - Images (auto detail): 1500 tokens
        - Images (low detail): 500 tokens
        - Base prompt overhead: 5000 tokens
        - Output estimate: 10000 tokens

        Args:
            forecast_data: Prepared forecast data

        Returns:
            Estimated token count
        """
        # Text data estimation (rough: ~4 chars per token)
        text_tokens = 0

        # Forecast data structures
        swell_events_str = str(forecast_data.get("swell_events", []))
        shore_data_str = str(forecast_data.get("shore_data", {}))
        text_tokens += len(swell_events_str) // 4
        text_tokens += len(shore_data_str) // 4

        # System prompts and templates (estimated)
        text_tokens += 5000  # Base prompt overhead including system prompts

        # Image token estimation (based on actual image detail levels configured)
        image_tokens = 0
        images = forecast_data.get("images", {})

        # Pressure charts (4 images)
        pressure_count = min(len(images.get("pressure_charts", [])), 4)
        if self.image_detail_pressure == "high":
            image_tokens += pressure_count * 3000
        elif self.image_detail_pressure == "auto":
            image_tokens += pressure_count * 1500
        else:  # low
            image_tokens += pressure_count * 500

        # Wave models (4 images)
        wave_count = min(len(images.get("wave_models", [])), 4)
        if self.image_detail_wave == "high":
            image_tokens += wave_count * 3000
        elif self.image_detail_wave == "auto":
            image_tokens += wave_count * 1500
        else:  # low
            image_tokens += wave_count * 500

        # Satellite (1 image)
        if images.get("satellite"):
            if self.image_detail_satellite == "high":
                image_tokens += 3000
            elif self.image_detail_satellite == "auto":
                image_tokens += 1500
            else:  # low
                image_tokens += 500

        # SST charts (1 image)
        if images.get("sst_charts"):
            if self.image_detail_sst == "high":
                image_tokens += 3000
            elif self.image_detail_sst == "auto":
                image_tokens += 1500
            else:  # low
                image_tokens += 500

        # Output tokens (conservative estimate for forecast generation)
        output_tokens = 10000  # Long-form forecast text

        # Total estimate
        total_tokens = text_tokens + image_tokens + output_tokens

        self.logger.info(
            f"Token estimate: {text_tokens} text + {image_tokens} images + "
            f"{output_tokens} output = {total_tokens} total"
        )

        return total_tokens
