"""
Pressure chart analyst specialist for SurfCastAI forecast engine.

This module analyzes pressure chart images using GPT vision API to identify
weather systems, fetch patterns, and predict swell generation.
"""

import os
import logging
import base64
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .base_specialist import BaseSpecialist, SpecialistOutput
from ...utils.swell_propagation import SwellPropagationCalculator
from .schemas import (
    PressureAnalystOutput,
    PressureAnalystData,
    WeatherSystem,
    PredictedSwell,
    FrontalBoundary,
    AnalysisSummary,
    FetchWindow,
    SystemType,
    FrontType,
    FetchQuality,
    IntensificationTrend
)


class PressureAnalyst(BaseSpecialist):
    """
    Specialist for analyzing pressure chart images.

    Features:
    - Multi-image temporal analysis using GPT vision API
    - Low/high pressure system identification and tracking
    - Fetch window analysis (direction, distance, duration, quality)
    - Swell travel time calculations using wave physics
    - Predicted swell arrival timing and characteristics

    Input format:
        {
            'images': [list of image file paths in temporal order],
            'metadata': {
                'chart_times': [list of ISO timestamps],
                'region': 'North Pacific'
            }
        }

    Output format:
        {
            'confidence': 0.0-1.0,
            'data': {
                'systems': [system objects],
                'predicted_swells': [swell objects],
                'frontal_boundaries': [front objects]
            },
            'narrative': '500-1000 word analysis'
        }
    """

    # Wave physics constants
    GRAVITY = 9.81  # m/s²
    NAUTICAL_MILE_TO_METERS = 1852.0

    def __init__(self, config: Optional[Any] = None, model_name: Optional[str] = None, engine: Optional[Any] = None):
        """
        Initialize the pressure analyst.

        Args:
            config: Optional configuration object with OpenAI settings
            model_name: The specific OpenAI model this specialist instance should use (REQUIRED)
            engine: Reference to ForecastEngine for centralized API calls and cost tracking
        """
        super().__init__(config, model_name, engine)
        self.logger = logging.getLogger('specialist.pressure_analyst')

        # Validate engine parameter is provided
        if engine is None:
            raise ValueError(
                f"{self.__class__.__name__} requires engine parameter for API access. "
                "Template mode removed to prevent quality degradation."
            )
        self.engine = engine

        # Load OpenAI configuration
        # Note: model_name is now passed to __init__ from BaseSpecialist
        if config:
            self.openai_api_key = config.get('openai', 'api_key') or os.environ.get('OPENAI_API_KEY')
            self.max_tokens = config.getint('openai', 'max_tokens', 3000)
        else:
            self.openai_api_key = os.environ.get('OPENAI_API_KEY')
            self.max_tokens = 3000

        # Hawaii location for distance calculations (approximate center of islands)
        self.hawaii_lat = 21.5
        self.hawaii_lon = -158.0

        # Initialize swell propagation calculator
        self.swell_calculator = SwellPropagationCalculator()

    async def analyze(self, data: Dict[str, Any]) -> PressureAnalystOutput:
        """
        Analyze pressure chart images and return structured insights.

        Args:
            data: Dictionary with 'images' key containing list of image paths

        Returns:
            PressureAnalystOutput with systems, swells, fronts, and narrative

        Raises:
            ValueError: If input data is invalid
        """
        # Validate input
        self._validate_input(data, ['images'])

        image_paths = data['images']
        if not isinstance(image_paths, list) or len(image_paths) == 0:
            raise ValueError("images must be a non-empty list")

        metadata = data.get('metadata', {})
        chart_times = metadata.get('chart_times', [])
        region = metadata.get('region', 'North Pacific')

        self._log_analysis_start(f"{len(image_paths)} pressure charts from {region}")

        try:
            # Validate image files exist
            valid_images = self._validate_image_paths(image_paths)
            if not valid_images:
                raise ValueError("No valid image files found")

            # Analyze charts using vision API
            vision_result = await self._analyze_with_vision(valid_images, chart_times, region)

            # Extract and enhance structured data
            systems = vision_result.get('systems', [])
            predicted_swells = vision_result.get('predicted_swells', [])
            frontal_boundaries = vision_result.get('frontal_boundaries', [])

            # Enhance predictions with physics-based calculations
            enhanced_swells = self._enhance_swell_predictions(predicted_swells, systems)

            # Calculate confidence
            confidence = self._calculate_analysis_confidence(
                len(valid_images),
                systems,
                enhanced_swells,
                chart_times
            )

            # Prepare structured data dictionaries
            structured_data_dict = {
                'systems': systems,
                'predicted_swells': enhanced_swells,
                'frontal_boundaries': frontal_boundaries,
                'analysis_summary': {
                    'num_low_pressure': len([s for s in systems if s.get('type') == 'low_pressure']),
                    'num_high_pressure': len([s for s in systems if s.get('type') == 'high_pressure']),
                    'num_predicted_swells': len(enhanced_swells),
                    'region': region
                }
            }

            # Generate AI narrative (needs structured_data_dict for prompt building)
            narrative = await self._generate_narrative(structured_data_dict, valid_images, region)

            # Create metadata
            analysis_metadata = {
                'num_images': len(valid_images),
                'analysis_method': 'gpt_vision',
                'model': self.model_name,
                'timestamp': datetime.now().isoformat(),
                'region': region,
                'chart_times': chart_times
            }

            self._log_analysis_complete(confidence, len(valid_images))

            # Convert lists of dicts to Pydantic model instances
            weather_systems = [WeatherSystem(**system) for system in systems]
            predicted_swells = [PredictedSwell(**swell) for swell in enhanced_swells]
            frontal_boundaries = [FrontalBoundary(**front) for front in frontal_boundaries]
            analysis_summary_obj = AnalysisSummary(**structured_data_dict['analysis_summary'])

            # Create PressureAnalystData instance
            structured_data = PressureAnalystData(
                systems=weather_systems,
                predicted_swells=predicted_swells,
                frontal_boundaries=frontal_boundaries,
                analysis_summary=analysis_summary_obj
            )

            # Return Pydantic model
            return PressureAnalystOutput(
                confidence=confidence,
                data=structured_data,
                narrative=narrative,
                metadata=analysis_metadata
            )

        except Exception as e:
            self.logger.error(f"Error in pressure chart analysis: {e}")
            raise

    def _validate_image_paths(self, image_paths: List[str]) -> List[str]:
        """
        Validate that image files exist and are readable.

        Args:
            image_paths: List of image file paths

        Returns:
            List of valid image paths
        """
        valid_paths = []

        for img_path in image_paths:
            path = Path(img_path)
            if path.exists() and path.is_file():
                # Check if file is a valid image format
                if path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
                    valid_paths.append(str(path))
                else:
                    self.logger.warning(f"Skipping non-image file: {img_path}")
            else:
                self.logger.warning(f"Image file not found: {img_path}")

        return valid_paths

    async def _analyze_with_vision(
        self,
        image_paths: List[str],
        chart_times: List[str],
        region: str
    ) -> Dict[str, Any]:
        """
        Analyze pressure charts using GPT vision API.

        Args:
            image_paths: List of valid image paths
            chart_times: List of chart timestamps
            region: Geographic region

        Returns:
            Dictionary with systems, swells, and fronts
        """
        try:
            # Build specialized prompt for pressure analysis
            system_prompt = """You are an expert surf forecaster and meteorologist analyzing pressure charts.

Your task: Analyze these pressure charts in temporal sequence and identify:
1. Low-pressure systems (storms) - location, intensity, movement
2. High-pressure systems (ridges) - blocking patterns, stability
3. Fetch windows - areas where winds blow consistently over long distances toward Hawaii
4. Swell generation potential - from each low-pressure system
5. Predicted swell arrival timing at Hawaiian Islands (21.5°N, 158°W)

Focus on North Pacific systems that can generate surf for Hawaii.
Return structured data in JSON format with NO markdown formatting or code blocks."""

            # Build detailed user prompt with timestamps if available
            user_prompt = f"""Analyze these {len(image_paths)} pressure charts from the {region} and provide:

1. SYSTEMS: List all significant low/high pressure systems
   Format for each system:
   {{
       "type": "low_pressure" or "high_pressure",
       "location": "45N 160W" (latitude/longitude as string),
       "location_lat": 45.0 (numeric latitude),
       "location_lon": 160.0 (numeric longitude - use positive for East, negative for West),
       "pressure_mb": 990 (pressure in millibars),
       "wind_speed_kt": 50 (wind speed in knots if visible),
       "movement": "SE at 25kt" (direction and speed),
       "intensification": "strengthening", "weakening", or "steady",
       "generation_time": "2025-10-08T12:00Z" (when storm generated swell - use chart timestamp as reference),
       "fetch": {{
           "direction": "NNE" (relative to Hawaii at 21.5N 158W),
           "distance_nm": 800 (nautical miles),
           "duration_hrs": 36 (hours of sustained winds),
           "fetch_length_nm": 500 (length of fetch in nautical miles),
           "quality": "strong", "moderate", or "weak"
       }}
   }}

2. SWELL PREDICTIONS: For each potential swell
   Format:
   {{
       "source_system": "low_45N_160W" (identifier),
       "source_lat": 45.0 (numeric latitude of source),
       "source_lon": 160.0 (numeric longitude of source - positive East, negative West),
       "direction": "NNE" (arrival direction at Hawaii),
       "direction_degrees": 22 (numeric direction in degrees, 0=N, 90=E, 180=S, 270=W),
       "arrival_time": "2025-10-07T10:00-12:00Z" (estimated arrival window),
       "estimated_height": "7-9ft" (wave height range),
       "estimated_period": "13-15s" (period range),
       "confidence": 0.75 (0.0-1.0)
   }}

3. FRONTAL BOUNDARIES: Any significant fronts
   Format:
   {{
       "type": "cold_front" or "warm_front",
       "location": "approaching from NW",
       "timing": "2025-10-07T18:00Z"
   }}"""

            if chart_times:
                user_prompt += f"\n\nChart timestamps: {', '.join(chart_times)}"

            user_prompt += "\n\nReturn ONLY valid JSON with no markdown formatting. Use this exact structure:\n"
            user_prompt += """{
  "systems": [...],
  "predicted_swells": [...],
  "frontal_boundaries": [...]
}"""

            # Use engine's centralized OpenAI client for cost tracking
            # OpenAI client handles image encoding internally
            self.logger.info(f"Calling {self.model_name} for pressure chart analysis ({len(image_paths)} images)...")
            content = await self.engine.openai_client.call_openai_api(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_urls=image_paths,  # Pass paths directly, client handles encoding
                detail="high"  # High detail for meteorological analysis
            )

            if content:
                # Remove markdown code blocks if present
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()

                # Parse JSON response
                result = json.loads(content)
                self.logger.info("Successfully parsed vision API response")
                return result
            else:
                self.logger.warning("No content returned from vision API")
                return {
                    'systems': [],
                    'predicted_swells': [],
                    'frontal_boundaries': []
                }

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from vision API: {e}")
            return {
                'systems': [],
                'predicted_swells': [],
                'frontal_boundaries': []
            }
        except Exception as e:
            self.logger.error(f"Error calling vision API: {e}")
            return {
                'systems': [],
                'predicted_swells': [],
                'frontal_boundaries': []
            }

    def _enhance_swell_predictions(
        self,
        swells: List[Dict[str, Any]],
        systems: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enhance swell predictions with physics-based calculations.

        Uses SwellPropagationCalculator for accurate arrival timing.

        Args:
            swells: List of predicted swells from vision API
            systems: List of weather systems

        Returns:
            Enhanced swell predictions
        """
        enhanced = []

        for swell in swells:
            enhanced_swell = swell.copy()

            # Find source system for additional context
            source_id = swell.get('source_system', '').lower()
            source_system = None
            for system in systems:
                # Try multiple matching strategies
                system_type = system.get('type', '').lower()
                system_loc = system.get('location', '').lower().replace(' ', '_')
                system_id = f"{system_type}_{system_loc}"

                # Match if either ID contains the other, or location matches
                if (source_id and system_id and
                    (source_id in system_id or system_id in source_id or
                     system_loc in source_id or source_id in system_loc)):
                    source_system = system
                    break

            # Try to get numeric coordinates from swell or system
            source_lat = swell.get('source_lat')
            source_lon = swell.get('source_lon')

            # If not in swell, try to get from source system
            if (source_lat is None or source_lon is None) and source_system:
                source_lat = source_system.get('location_lat')
                source_lon = source_system.get('location_lon')

            # Calculate physics-based arrival if we have coordinates
            if source_lat is not None and source_lon is not None:
                try:
                    # Get period estimate
                    period_str = swell.get('estimated_period', '13-15s')
                    if '-' in period_str:
                        periods = [float(p.replace('s', '')) for p in period_str.split('-')]
                        avg_period = sum(periods) / len(periods)
                    else:
                        avg_period = float(period_str.replace('s', ''))

                    # Get or estimate generation time
                    generation_time = None
                    if source_system and source_system.get('generation_time'):
                        try:
                            gen_time_str = source_system['generation_time']
                            generation_time = datetime.fromisoformat(gen_time_str.replace('Z', '+00:00'))
                        except Exception as e:
                            self.logger.debug(f"Could not parse generation_time: {e}")

                    # If no generation time, use current time as fallback
                    if generation_time is None:
                        generation_time = datetime.now()
                        self.logger.debug(f"Using current time as generation_time fallback")

                    # Calculate arrival using physics
                    arrival_time, details = self.swell_calculator.calculate_arrival(
                        source_lat=source_lat,
                        source_lon=source_lon,
                        period_seconds=avg_period,
                        generation_time=generation_time
                    )

                    # Add calculated data to swell
                    enhanced_swell['calculated_arrival'] = arrival_time.isoformat()
                    enhanced_swell['travel_time_hrs'] = round(details['travel_time_hours'], 1)
                    enhanced_swell['distance_nm'] = round(details['distance_nm'], 0)
                    enhanced_swell['group_velocity_knots'] = round(details['group_velocity_knots'], 1)
                    enhanced_swell['propagation_method'] = 'physics_based'

                    self.logger.info(
                        f"Calculated swell arrival: {source_lat}°N {source_lon}°E → Hawaii, "
                        f"period={avg_period:.1f}s, arrival={arrival_time.strftime('%a %b %d %I:%M %p')}, "
                        f"travel={details['travel_time_hours']:.1f}hrs"
                    )

                except Exception as e:
                    self.logger.warning(f"Could not calculate physics-based arrival: {e}")
                    # Fall back to original estimates if calculation fails

            # Add fetch quality and other data from source system
            if source_system:
                if 'fetch' in source_system:
                    fetch = source_system['fetch']
                    enhanced_swell['fetch_quality'] = fetch.get('quality', 'unknown')
                    enhanced_swell['fetch_duration_hrs'] = fetch.get('duration_hrs')
                    enhanced_swell['fetch_length_nm'] = fetch.get('fetch_length_nm')

                # Add storm characteristics
                if 'pressure_mb' in source_system:
                    enhanced_swell['source_pressure_mb'] = source_system['pressure_mb']
                if 'wind_speed_kt' in source_system:
                    enhanced_swell['source_wind_speed_kt'] = source_system['wind_speed_kt']
                if 'intensification' in source_system:
                    enhanced_swell['source_trend'] = source_system['intensification']

            enhanced.append(enhanced_swell)

        return enhanced

    def _calculate_swell_travel_time(self, distance_nm: float, period_s: float) -> float:
        """
        Calculate swell travel time using deep water wave group velocity.

        Args:
            distance_nm: Distance in nautical miles
            period_s: Wave period in seconds

        Returns:
            Travel time in hours
        """
        # Deep water group velocity: Cg = g * T / (4 * pi)
        # Where g is gravity (9.81 m/s²) and T is period
        group_velocity_ms = (self.GRAVITY * period_s) / (4 * math.pi)

        # Convert distance to meters
        distance_m = distance_nm * self.NAUTICAL_MILE_TO_METERS

        # Calculate travel time in seconds
        travel_time_s = distance_m / group_velocity_ms

        # Convert to hours
        travel_time_hrs = travel_time_s / 3600.0

        return travel_time_hrs

    def _calculate_distance_to_hawaii(self, lat: float, lon: float) -> float:
        """
        Calculate great circle distance from a point to Hawaii.

        Args:
            lat: Latitude of the point
            lon: Longitude of the point

        Returns:
            Distance in nautical miles
        """
        # Haversine formula
        lat1_rad = math.radians(self.hawaii_lat)
        lon1_rad = math.radians(self.hawaii_lon)
        lat2_rad = math.radians(lat)
        lon2_rad = math.radians(lon)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in nautical miles (approximately)
        earth_radius_nm = 3440.065

        distance_nm = earth_radius_nm * c
        return distance_nm

    def _calculate_analysis_confidence(
        self,
        num_images: int,
        systems: List[Dict[str, Any]],
        swells: List[Dict[str, Any]],
        chart_times: List[str]
    ) -> float:
        """
        Calculate overall confidence in the analysis.

        Args:
            num_images: Number of images analyzed
            systems: Detected weather systems
            swells: Predicted swells
            chart_times: Chart timestamps

        Returns:
            Confidence score (0.0-1.0)
        """
        # Data completeness: based on number of images (more is better)
        # Optimal is 6-8 images covering 24-48 hours
        if num_images >= 6:
            completeness = 1.0
        elif num_images >= 4:
            completeness = 0.8
        elif num_images >= 2:
            completeness = 0.6
        else:
            completeness = 0.4

        # Data consistency: based on system clarity and fetch quality
        if systems:
            fetch_qualities = []
            for system in systems:
                if 'fetch' in system:
                    quality = system['fetch'].get('quality', 'weak')
                    if quality == 'strong':
                        fetch_qualities.append(1.0)
                    elif quality == 'moderate':
                        fetch_qualities.append(0.7)
                    else:
                        fetch_qualities.append(0.4)

            if fetch_qualities:
                consistency = sum(fetch_qualities) / len(fetch_qualities)
            else:
                consistency = 0.5
        else:
            consistency = 0.3

        # Data quality: based on swell predictions and temporal coverage
        if swells:
            # Check if swells have confidence scores
            swell_confidences = [s.get('confidence', 0.5) for s in swells]
            quality = sum(swell_confidences) / len(swell_confidences)
        else:
            quality = 0.4

        # Temporal coverage bonus
        if chart_times and len(chart_times) >= num_images:
            try:
                # Check time span coverage
                times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in chart_times]
                time_span_hrs = (max(times) - min(times)).total_seconds() / 3600.0
                if time_span_hrs >= 24:
                    quality = min(1.0, quality * 1.1)  # 10% bonus for good temporal coverage
            except Exception as e:
                self.logger.debug(f"Could not parse chart times for coverage calc: {e}")

        return self._calculate_confidence(completeness, consistency, quality)

    async def _generate_narrative(
        self,
        structured_data: Dict[str, Any],
        image_paths: List[str],
        region: str
    ) -> str:
        """
        Generate AI narrative analysis using GPT.

        Args:
            structured_data: Structured analysis data
            image_paths: List of image paths
            region: Geographic region

        Returns:
            Natural language narrative (500-1000 words)
        """
        try:
            # Build narrative prompt
            prompt = self._build_narrative_prompt(structured_data, region)

            system_prompt = """You are an expert surf forecaster analyzing pressure patterns.
Your task is to provide a comprehensive narrative analysis focusing on:
1. Current pressure systems and their characteristics
2. Fetch windows and swell generation potential
3. Predicted swell arrivals at Hawaii with timing and characteristics
4. Frontal boundaries and their impact on local conditions
5. Confidence levels and uncertainties

Write a 500-1000 word narrative that is:
- Technical but accessible to experienced surfers
- Specific about locations, timing, and measurements
- Clear about confidence and uncertainty
- Actionable for surf forecast decisions"""

            # Use engine's centralized OpenAI client for cost tracking
            self.logger.info(f"Calling {self.model_name} for pressure analysis narrative...")
            narrative = await self.engine.openai_client.call_openai_api(
                system_prompt=system_prompt,
                user_prompt=prompt
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

    def _build_narrative_prompt(self, structured_data: Dict[str, Any], region: str) -> str:
        """Build the narrative prompt for GPT."""
        systems = structured_data.get('systems', [])
        swells = structured_data.get('predicted_swells', [])
        fronts = structured_data.get('frontal_boundaries', [])
        summary = structured_data.get('analysis_summary', {})

        prompt = f"""Provide a comprehensive narrative analysis of pressure patterns in the {region}.

SYSTEMS DETECTED: {summary.get('num_low_pressure', 0)} low pressure, {summary.get('num_high_pressure', 0)} high pressure

"""

        if systems:
            prompt += "DETAILED SYSTEMS:\n"
            for system in systems:
                prompt += f"\n{system.get('type', 'unknown').replace('_', ' ').title()}:\n"
                prompt += f"  - Location: {system.get('location', 'unknown')}\n"
                prompt += f"  - Pressure: {system.get('pressure_mb', 'N/A')} mb\n"
                prompt += f"  - Movement: {system.get('movement', 'unknown')}\n"
                prompt += f"  - Trend: {system.get('intensification', 'unknown')}\n"

                if 'fetch' in system:
                    fetch = system['fetch']
                    prompt += f"  - Fetch: {fetch.get('direction', 'unknown')} direction, "
                    prompt += f"{fetch.get('distance_nm', 'N/A')} nm, "
                    prompt += f"{fetch.get('duration_hrs', 'N/A')} hrs, "
                    prompt += f"{fetch.get('quality', 'unknown')} quality\n"

        prompt += f"\nPREDICTED SWELLS: {len(swells)}\n"
        if swells:
            for swell in swells:
                prompt += f"\nFrom {swell.get('source_system', 'unknown')}:\n"
                prompt += f"  - Direction: {swell.get('direction', 'unknown')}\n"
                prompt += f"  - Arrival: {swell.get('arrival_time', 'TBD')}\n"
                prompt += f"  - Height: {swell.get('estimated_height', 'N/A')}\n"
                prompt += f"  - Period: {swell.get('estimated_period', 'N/A')}\n"
                prompt += f"  - Confidence: {swell.get('confidence', 'N/A')}\n"

                if 'travel_time_hrs' in swell:
                    prompt += f"  - Travel time: {swell['travel_time_hrs']} hours\n"
                if 'fetch_quality' in swell:
                    prompt += f"  - Fetch quality: {swell['fetch_quality']}\n"

        if fronts:
            prompt += f"\nFRONTAL BOUNDARIES: {len(fronts)}\n"
            for front in fronts:
                prompt += f"  - {front.get('type', 'unknown').replace('_', ' ').title()}: "
                prompt += f"{front.get('location', 'unknown')}, "
                prompt += f"timing: {front.get('timing', 'TBD')}\n"

        prompt += "\nProvide a comprehensive analysis integrating all this information."

        return prompt

    def _generate_template_narrative(
        self,
        structured_data: Dict[str, Any],
        region: str
    ) -> str:
        """Generate a template narrative when AI is unavailable."""
        systems = structured_data.get('systems', [])
        swells = structured_data.get('predicted_swells', [])
        fronts = structured_data.get('frontal_boundaries', [])
        summary = structured_data.get('analysis_summary', {})

        narrative = f"""PRESSURE CHART ANALYSIS - {region}

OVERVIEW:
Analysis of pressure patterns shows {summary.get('num_low_pressure', 0)} low-pressure systems
and {summary.get('num_high_pressure', 0)} high-pressure systems currently active in the region.
"""

        if systems:
            narrative += "\n\nWEATHER SYSTEMS:\n"
            for system in systems:
                narrative += f"\n{system.get('type', 'unknown').replace('_', ' ').title()}: "
                narrative += f"Located at {system.get('location', 'unknown')}, "
                narrative += f"{system.get('pressure_mb', 'N/A')} mb, "
                narrative += f"moving {system.get('movement', 'unknown')}, "
                narrative += f"{system.get('intensification', 'steady')}."

                if 'fetch' in system:
                    fetch = system['fetch']
                    narrative += f"\nFetch: {fetch.get('quality', 'moderate')} quality, "
                    narrative += f"{fetch.get('direction', 'unknown')} direction, "
                    narrative += f"{fetch.get('distance_nm', 'N/A')} nm for "
                    narrative += f"{fetch.get('duration_hrs', 'N/A')} hours."

        if swells:
            narrative += "\n\nPREDICTED SWELLS:\n"
            for swell in swells:
                narrative += f"\n{swell.get('direction', 'Unknown')} swell from {swell.get('source_system', 'system')}: "
                narrative += f"{swell.get('estimated_height', 'N/A')} at "
                narrative += f"{swell.get('estimated_period', 'N/A')}, "
                narrative += f"arriving {swell.get('arrival_time', 'TBD')}."

        if fronts:
            narrative += "\n\nFRONTAL ACTIVITY:\n"
            for front in fronts:
                narrative += f"{front.get('type', 'unknown').replace('_', ' ').title()} "
                narrative += f"{front.get('location', 'unknown')}, "
                narrative += f"expected {front.get('timing', 'TBD')}.\n"

        narrative += "\n\n(Note: This is a template narrative. Configure OpenAI API for detailed AI analysis.)"

        return narrative
