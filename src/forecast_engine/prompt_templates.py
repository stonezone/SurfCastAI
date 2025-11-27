"""
Prompt templates for the forecast engine.

This module provides prompt templates for generating
forecasts in different styles.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("forecast.templates")


# Image analysis prompts for GPT-5 Vision
PRESSURE_CHART_ANALYSIS_PROMPT = """
Analyze the attached surface pressure chart for Hawaii surf forecasting:

1. **Low Pressure Systems**: Identify any lows within 1000-3000nm of Hawaii
   - Location (lat/lon estimate)
   - Pressure (mb)
   - Movement direction/speed
   - Fetch orientation relative to Hawaii

2. **High Pressure Systems**: Identify blocking highs or trade wind highs
   - Could they shadow swell from reaching Hawaii?
   - Are they enhancing/diminishing trade winds?

3. **Frontal Boundaries**: Any cold fronts generating NW swells?

4. **Pressure Gradients**: Tight gradients = strong winds = fetch for swell generation

Provide analysis in structured format:
{
  "low_pressure_systems": [
    {"location": "35N 155W", "pressure_mb": 995, "fetch_direction": "NW", "swell_potential": "high"}
  ],
  "high_pressure_systems": [...],
  "frontal_activity": [...],
  "swell_generation_zones": [
    {"zone": "NW Pacific", "confidence": "high", "arrival_days": 3-5}
  ]
}
"""

SATELLITE_IMAGE_ANALYSIS_PROMPT = """
Analyze the attached satellite imagery for Hawaii region:

1. **Cloud Patterns**:
   - Large spiral systems (tropical cyclones/lows)
   - Linear cloud bands (frontal systems)
   - Trade wind cumulus (normal pattern)

2. **Storm Systems**:
   - Location relative to Hawaii
   - Size/intensity indicators (eye, banding)
   - Direction of movement

3. **Atmospheric Rivers**: Any moisture plumes that could bring weather?

4. **Visible Swell Patterns**: Can you see swell lines in ocean areas? (subtle but visible in some imagery)

Extract actionable surf forecast information.
"""

SST_CHART_ANALYSIS_PROMPT = """
Analyze the attached Sea Surface Temperature (SST) anomaly chart for surf forecasting context:

1. **Temperature Anomalies**:
   - Identify warm/cold water regions near swell generation zones (North Pacific, South Pacific)
   - Note any El Niño/La Niña patterns (equatorial Pacific anomalies)

2. **Storm Intensity Implications**:
   - Warm anomalies (+2°C or more) can intensify low pressure systems
   - Cold anomalies can weaken storm development
   - Warmer water = stronger winds = better fetch for swell generation

3. **Swell Generation Context**:
   - Where are the warmest anomalies relative to current pressure systems?
   - Could warm water enhance storm development in swell generation zones?

4. **Seasonal Patterns**:
   - Does the SST pattern align with typical El Niño/La Niña/Neutral conditions?
   - Any unusual patterns that could affect storm tracks?

Provide brief, actionable insights for how SST anomalies may affect swell generation and storm intensity.
"""


class PromptTemplates:
    """
    Manages prompt templates for forecast generation.

    Provides methods to load templates from files or use defaults,
    and generate prompts for different forecast types.
    """

    def __init__(self, templates_dir: str | None = None):
        """
        Initialize the prompt templates.

        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = templates_dir
        self.templates = {}

        # Load templates if directory provided
        if templates_dir and os.path.isdir(templates_dir):
            self._load_templates()
        else:
            logger.warning("No template files found, using default templates")
            self._use_default_templates()

    def _load_templates(self):
        """Load templates from files."""
        template_files = {
            "caldwell": "caldwell_template.json",
            "north_shore": "north_shore_template.json",
            "south_shore": "south_shore_template.json",
            "daily": "daily_template.json",
        }

        for template_name, filename in template_files.items():
            file_path = os.path.join(self.templates_dir, filename)
            if os.path.isfile(file_path):
                try:
                    with open(file_path) as f:
                        self.templates[template_name] = json.load(f)
                    logger.info(f"Loaded template: {template_name}")
                except Exception as e:
                    logger.error(f"Error loading template {template_name}: {e}")
            else:
                logger.warning(f"Template file not found: {filename}")
                # Use default for this template
                self._use_default_template(template_name)

    def _use_default_templates(self):
        """Use default templates."""
        self._use_default_template("caldwell")
        self._use_default_template("north_shore")
        self._use_default_template("south_shore")
        self._use_default_template("east_shore")
        self._use_default_template("west_shore")
        self._use_default_template("daily")

    def _use_default_template(self, template_name: str):
        """
        Use a default template for a specific forecast type.

        Args:
            template_name: Name of the template
        """
        if template_name == "caldwell":
            self.templates[template_name] = {
                "system_prompt": """
You are Pat Caldwell, Hawaii's preeminent surf forecaster with 30+ years at NOAA.
You maintain the Goddard-Caldwell database (1968-present) and are THE authority on Hawaiian surf climatology.

METHODOLOGY (how you analyze):
1. Analyze synoptic patterns for swell-generating storms (lows, fronts, fetch areas)
2. Track fetch position, intensity (MSLP in mb), and duration
3. Calculate swell arrival: Distance(nm) / (1.5 × Period(s)) = hours
4. Compare to historical H1/10 observations from the Goddard-Caldwell database
5. Apply calibrated confidence language based on model agreement

WRITING STYLE (per sources-claude.md analysis):
- Open with brief, colorful summary ("Hefty hunks of NW energy for the Country...")
- Organize by shore facing (north → east → south → west)
- Tell the "storm backstory" - trace each swell to its source storm
- Use directions in degrees AND compass (315°/NW)
- Reference buoys by number (51001, 51002)
- Compare to seasonal averages ("On this day since 1968, average H1/10 is X ft")
- End long-range outlook with uncertainty qualifier

HEIGHT CONVENTIONS:
- Hawaii Scale Feet (HSF): The LOCAL convention used by Hawaiian surfers
- Face Height = HSF × 2 (e.g., "10 ft Hawaiian" = 20-foot faces)
- H1/10 = average of highest 10% of waves (what experienced eyes observe)
- When stating heights, use Hawaii Scale for the audience, but note face height for context

CONFIDENCE SPECTRUM (in order of certainty):
- "expected" / "will" = High confidence (model agreement, clear synoptic setup)
- "likely" = Moderate-high confidence
- "possible" / "could" = Moderate confidence (some model spread)
- "subject to major revisions" = Low confidence (models disagree)

REQUIRED SECTIONS:
1. HEADLINE - Brief, evocative summary (one punchy sentence)
2. STORM BACKSTORY - Where did this swell come from? (lat/lon, pressure, fetch details)
3. NORTH SHORE - Detailed analysis with break specifics (Pipeline, Sunset, Waimea)
4. SOUTH SHORE - Town surf analysis (Waikiki, Ala Moana, Diamond Head)
5. EAST/WEST SHORES - Trade wind swell and wrap analysis
6. OUTLOOK - Extended forecast with appropriate uncertainty language
7. HISTORICAL CONTEXT - "On this day in the Goddard-Caldwell database..."

CRITICAL RULES:
- You MUST write the actual forecast text in your response
- Do NOT say you need more information - use what's provided
- Do NOT provide a template or ask for clarification
- WRITE THE COMPLETE FORECAST NOW using the data provided
- Include specific buoy readings and model data to support your analysis
- Always mention the swell direction in BOTH degrees and compass (307°/WNW)
""",
                "user_prompt": """
Generate a comprehensive surf forecast for Hawaii (Oahu) covering {start_date} to {end_date}.

SWELL DATA:
{swell_details}

SEASONAL CONTEXT:
{seasonal_context}

WEATHER:
{weather_conditions}

TIDES:
{tide_info}

PRIMARY SHORES:
{primary_shores}

DATA DIGEST:
{data_digest}

Write the complete forecast now using the Pat Caldwell style with SUMMARY, DETAILS, NORTH SHORE, SOUTH SHORE, and OUTLOOK sections.
""",
            }
        elif template_name == "north_shore":
            self.templates[template_name] = {
                "system_prompt": """
Generate a detailed North Shore-specific surf forecast in Pat Caldwell's style. Focus on:

1. Wave heights in Hawaiian scale
2. Swell direction and period analysis
3. Wind and weather effects specific to North Shore
4. Timing information (building, peaking, dropping)
5. Break-specific details for Pipeline, Sunset Beach, Waimea Bay and other notable spots
6. Comparison to recent and normal conditions for this time of year

Keep technical accuracy as the top priority while providing practical information for surfers of all levels.
""",
                "user_prompt": """
Generate a detailed North Shore surf forecast for {start_date} to {end_date}.

NORTH SHORE SWELLS:
{north_shore_swells}

WEATHER:
{weather_conditions}

NOTABLE BREAKS:
{popular_breaks}

DATA DIGEST:
{data_digest}

SHORE SNAPSHOT:
{shore_digest}

Write the complete North Shore forecast now using Pat Caldwell's technical style.
""",
            }
        elif template_name == "south_shore":
            self.templates[template_name] = {
                "system_prompt": """
Generate a detailed South Shore-specific surf forecast in Pat Caldwell's style. Focus on:

1. Wave heights in Hawaiian scale
2. Swell direction and period analysis
3. Wind and weather effects specific to South Shore
4. Timing information (building, peaking, dropping)
5. Break-specific details for Waikiki, Ala Moana, and other notable town spots
6. Comparison to recent and normal conditions for this time of year

Keep technical accuracy as the top priority while providing practical information for surfers of all levels.
""",
                "user_prompt": """
Generate a detailed South Shore surf forecast for {start_date} to {end_date}.

SOUTH SHORE SWELLS:
{south_shore_swells}

WEATHER:
{weather_conditions}

NOTABLE BREAKS:
{popular_breaks}

DATA DIGEST:
{data_digest}

SHORE SNAPSHOT:
{shore_digest}

Write the complete South Shore forecast now using Pat Caldwell's technical style.
""",
            }
        elif template_name == "east_shore":
            self.templates[template_name] = {
                "system_prompt": """
Generate a detailed East Shore (Windward)-specific surf forecast in Pat Caldwell's style. Focus on:

1. Wave heights in Hawaiian scale
2. Trade wind swell analysis (primary source for East Shore)
3. Wind and weather effects specific to Windward/East Shore
4. Timing information (building, peaking, dropping)
5. Break-specific details for Makapuu, Sandy Beach, and other notable East side spots
6. Trade wind patterns and their effect on surf quality

The East Shore receives primarily trade wind swell from 60-90 degrees. Keep technical accuracy as the top priority while providing practical information for surfers.
""",
                "user_prompt": """
Generate a detailed East Shore surf forecast for {start_date} to {end_date}.

EAST SHORE SWELLS:
{east_shore_swells}

WEATHER:
{weather_conditions}

NOTABLE BREAKS:
{popular_breaks}

DATA DIGEST:
{data_digest}

SHORE SNAPSHOT:
{shore_digest}

Write the complete East Shore forecast now using Pat Caldwell's technical style.
""",
            }
        elif template_name == "west_shore":
            self.templates[template_name] = {
                "system_prompt": """
Generate a detailed West Shore (Leeward)-specific surf forecast in Pat Caldwell's style. Focus on:

1. Wave heights in Hawaiian scale
2. NW swell wrap analysis (secondary to North Shore but can be significant)
3. Wind and weather effects specific to Leeward/West Shore
4. Timing information (building, peaking, dropping)
5. Break-specific details for Makaha, Yokohama, and other notable West side spots
6. Shadow effects from neighboring islands and how they affect swell arrival

The West Shore receives NW-WNW swell wrap from 270-315 degrees, typically smaller than direct North Shore hits. Keep technical accuracy as the top priority while providing practical information for surfers.
""",
                "user_prompt": """
Generate a detailed West Shore surf forecast for {start_date} to {end_date}.

WEST SHORE SWELLS:
{west_shore_swells}

WEATHER:
{weather_conditions}

NOTABLE BREAKS:
{popular_breaks}

DATA DIGEST:
{data_digest}

SHORE SNAPSHOT:
{shore_digest}

Write the complete West Shore forecast now using Pat Caldwell's technical style.
""",
            }
        elif template_name == "daily":
            self.templates[template_name] = {
                "system_prompt": """
Generate a concise daily surf report for Hawaii. Focus on:

1. Current conditions for the day
2. Wave heights in Hawaiian scale for different shores
3. Wind and weather conditions
4. Tide information relevant to surfing
5. Best spots for the day given the conditions
6. Brief mention of changing conditions through the day if applicable

Make this practical, surfer-focused, and actionable for someone planning their surf session today.
""",
                "user_prompt": """
Generate a daily surf report for {region} on {start_date}.

SWELLS:
{current_swells}

WEATHER:
{weather_conditions}

TIDES:
{tide_info}

DATA DIGEST:
{data_digest}

Write the complete daily report now in a concise, practical style.
""",
            }

    def get_template(self, template_name: str) -> dict[str, Any]:
        """
        Get a specific template.

        Args:
            template_name: Name of the template

        Returns:
            Template dictionary
        """
        if template_name not in self.templates:
            logger.warning(f"Template not found: {template_name}, using default")
            self._use_default_template(template_name)

        return self.templates[template_name]

    def get_all_templates(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all loaded templates."""
        return {key: dict(value) for key, value in self.templates.items()}

    def update_templates(self, updates: dict[str, dict[str, Any]]) -> None:
        """Merge external templates into the current collection."""
        for key, value in updates.items():
            if isinstance(value, dict):
                self.templates[key] = dict(value)

    def _get_swell_period(self, swell: dict[str, Any]) -> float:
        """
        Extract dominant period from swell event.

        Args:
            swell: Swell event dictionary

        Returns:
            Dominant period in seconds
        """
        # Try direct field first
        if "dominant_period" in swell and swell["dominant_period"]:
            return float(swell["dominant_period"])

        # Try primary components
        primary_components = swell.get("primary_components", [])
        if primary_components:
            # Filter out None values and convert to float
            periods = [
                float(c["period"]) for c in primary_components if c.get("period") is not None
            ]
            if periods:
                return max(periods)

        return 0.0

    def get_caldwell_prompt(self, forecast_data: dict[str, Any]) -> str:
        """
        Generate a prompt for Caldwell-style forecast.

        Args:
            forecast_data: Data for the forecast

        Returns:
            Formatted prompt string
        """
        template = self.get_template("caldwell")
        user_prompt = template.get("user_prompt", "")

        # Format swell details
        swell_details = []
        for swell in forecast_data.get("swell_events", []):
            period = self._get_swell_period(swell)

            # Extract source attribution
            metadata = swell.get("metadata", {})
            source_details = metadata.get("source_details", {})
            source_info = ""
            if source_details:
                buoy_id = source_details.get("buoy_id", "")
                obs_time = source_details.get("observation_time", "")
                source_type = source_details.get("source_type", "")
                if buoy_id and source_type:
                    source_info = f" (Source: {source_type} Buoy {buoy_id})"

            swell_details.append(
                f"- {swell.get('primary_direction_cardinal', 'Unknown')} swell at "
                f"{swell.get('hawaii_scale', 0):.1f}ft (Hawaiian), "
                f"period: {period:.1f}s, "
                f"arriving: {swell.get('start_time', '')}, "
                f"peaking: {swell.get('peak_time', '')}{source_info}"
            )

        # Format seasonal context
        seasonal_context = forecast_data.get("seasonal_context", {})
        season = seasonal_context.get("current_season", "unknown").title()
        seasonal_patterns = seasonal_context.get("seasonal_patterns", {})

        seasonal_info = f"{season} season - "
        for shore, patterns in seasonal_patterns.items():
            shore_name = shore.replace("_", " ").title()
            conditions = patterns.get("typical_conditions", "")
            seasonal_info += f"{shore_name}: {conditions}. "

        weather_conditions = self._format_weather(forecast_data)
        tide_info = self._format_tides(forecast_data)

        # Format primary shores
        primary_shores = ", ".join(forecast_data.get("shores", ["North Shore", "South Shore"]))

        # Format prompt
        formatted_prompt = user_prompt.format(
            start_date=forecast_data.get("start_date", ""),
            end_date=forecast_data.get("end_date", ""),
            swell_details="\n".join(swell_details),
            seasonal_context=seasonal_info,
            weather_conditions=weather_conditions,
            tide_info=tide_info,
            primary_shores=primary_shores,
            data_digest=forecast_data.get("data_digest", "Data digest unavailable."),
        )

        return formatted_prompt

    def get_shore_prompt(self, shore: str, forecast_data: dict[str, Any]) -> str:
        """
        Generate a prompt for shore-specific forecast.

        Args:
            shore: Shore name ('north_shore' or 'south_shore')
            forecast_data: Data for the forecast

        Returns:
            Formatted prompt string
        """
        template_name = shore if shore in ["north_shore", "south_shore"] else "north_shore"
        template = self.get_template(template_name)
        user_prompt = template.get("user_prompt", "")

        # Get shore data
        shore_data = forecast_data.get("shore_data", {}).get(shore, {})
        if not shore_data:
            logger.warning(f"No data found for {shore}")
            return f"Generate a {shore.replace('_', ' ').title()} forecast for {forecast_data.get('start_date', '')}."

        # Format shore-specific swells
        shore_swells = []
        for swell in shore_data.get("swell_events", []):
            exposure = swell.get("metadata", {}).get(f"exposure_{shore}", 0.5)
            effect = "strong" if exposure > 0.7 else ("moderate" if exposure > 0.4 else "minimal")
            period = self._get_swell_period(swell)

            shore_swells.append(
                f"- {swell.get('primary_direction_cardinal', 'Unknown')} swell at "
                f"{swell.get('hawaii_scale', 0):.1f}ft (Hawaiian), "
                f"period: {period:.1f}s, "
                f"{effect} effect on {shore.replace('_', ' ').title()}"
            )

        weather_conditions = self._format_weather(forecast_data)

        # Format popular breaks
        popular_breaks = shore_data.get("metadata", {}).get("popular_breaks", [])
        popular_breaks_str = ", ".join(popular_breaks) if popular_breaks else "Various breaks"

        # Format prompt
        formatted_prompt = user_prompt.format(
            start_date=forecast_data.get("start_date", ""),
            end_date=forecast_data.get("end_date", ""),
            north_shore_swells="\n".join(shore_swells) if shore == "north_shore" else "N/A",
            south_shore_swells="\n".join(shore_swells) if shore == "south_shore" else "N/A",
            weather_conditions=weather_conditions,
            popular_breaks=popular_breaks_str,
            data_digest=forecast_data.get("data_digest", "Data digest unavailable."),
            shore_digest=forecast_data.get("shore_digests", {}).get(
                shore, "No shore-specific digest available."
            ),
        )

        return formatted_prompt

    def get_daily_prompt(self, forecast_data: dict[str, Any]) -> str:
        """Generate the daily report prompt."""

        template = self.get_template("daily")
        user_prompt = template.get("user_prompt", "")

        region = forecast_data.get("region", "Oahu")
        start_date = forecast_data.get("start_date", "")

        # Summarise leading swell events for quick reference
        swells = []
        for swell in forecast_data.get("swell_events", [])[:6]:
            direction = swell.get("primary_direction_cardinal", "Unknown")
            faces = swell.get("hawaii_scale", 0.0)
            period = self._get_swell_period(swell)
            peak = swell.get("peak_time", "n/a")
            swells.append(f"- {direction} {faces:.1f}ft (H1/3) @{period:.1f}s, peak {peak}")
        current_swells = "\n".join(swells) if swells else "- No significant swell signals received."

        # Reuse weather/tide formatting
        weather_conditions = self._format_weather(forecast_data)
        tide_info = self._format_tides(forecast_data)

        formatted_prompt = user_prompt.format(
            region=region,
            start_date=start_date,
            current_swells=current_swells,
            weather_conditions=weather_conditions,
            tide_info=tide_info,
            data_digest=forecast_data.get("data_digest", "Data digest unavailable."),
        )

        return formatted_prompt

    # ------------------------------------------------------------------
    # Shared formatting helpers
    # ------------------------------------------------------------------

    def _format_weather(self, forecast_data: dict[str, Any]) -> str:
        weather = forecast_data.get("metadata", {}).get("weather", {})
        wind_dir = weather.get("wind_direction")
        wind_speed = weather.get("wind_speed") or weather.get("wind_speed_kt")
        if wind_speed is None and weather.get("wind_speed_ms") is not None:
            wind_speed = weather["wind_speed_ms"] * 1.94384
        if wind_dir is not None and wind_speed is not None:
            wind_str = f"Wind: {wind_dir}° at {wind_speed:.1f} kt"
        elif wind_dir is not None:
            wind_str = f"Wind: {wind_dir}° (speed unavailable)"
        else:
            wind_str = "Wind: Variable/Light"

        metar = weather.get("metar", {})
        conditions = weather.get("conditions") or metar.get("metar") or "Conditions unavailable"
        issued = metar.get("issued", "n/a")

        return f"{wind_str}. Conditions: {conditions}. METAR issued: {issued}."

    def _format_tides(self, forecast_data: dict[str, Any]) -> str:
        tides = forecast_data.get("metadata", {}).get("tides", {})
        if not tides:
            return "Tides: unavailable."

        highs = ", ".join(
            [f"{time} ({height}ft)" for time, height in tides.get("high_tide", [])[:3]]
        )
        lows = ", ".join([f"{time} ({height}ft)" for time, height in tides.get("low_tide", [])[:3]])

        components = []
        if highs:
            components.append(f"High: {highs}")
        if lows:
            components.append(f"Low: {lows}")
        latest = tides.get("latest_water_level")
        if latest:
            components.append(
                f"Latest obs: {latest.get('time')} -> {latest.get('height_ft', 'n/a')} ft"
            )

        return "Tides: " + "; ".join(components) if components else "Tides: unavailable."
