"""
Prompt templates for the forecast engine.

This module provides prompt templates for generating
forecasts in different styles.
"""

import os
import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger('forecast.templates')


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
    
    def __init__(self, templates_dir: Optional[str] = None):
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
            'caldwell': 'caldwell_template.json',
            'north_shore': 'north_shore_template.json',
            'south_shore': 'south_shore_template.json',
            'daily': 'daily_template.json'
        }
        
        for template_name, filename in template_files.items():
            file_path = os.path.join(self.templates_dir, filename)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r') as f:
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
        self._use_default_template('caldwell')
        self._use_default_template('north_shore')
        self._use_default_template('south_shore')
        self._use_default_template('daily')
    
    def _use_default_template(self, template_name: str):
        """
        Use a default template for a specific forecast type.
        
        Args:
            template_name: Name of the template
        """
        if template_name == 'caldwell':
            self.templates[template_name] = {
                "system_prompt": """
You are Pat Caldwell, the veteran Hawaiian surf forecaster. You write actual surf forecasts, not instructions about forecasting.

Your task: Write a complete surf forecast using the provided data.

YOUR STYLE:
- Technical accuracy with detailed swell analysis
- Precise timing for swell arrivals, peaks, and declines
- Focus on swell direction (degrees), period (seconds), and size (Hawaiian scale)
- Differentiate North Shore vs South Shore conditions
- Include weather/wind effects on surf quality
- Concise, information-dense, minimal fluff
- Reference specific breaks when relevant

REQUIRED SECTIONS:
1. SUMMARY - Brief overview of main swell(s)
2. DETAILS - Technical breakdown of swell components with timing
3. NORTH SHORE - Specific conditions and expectations
4. SOUTH SHORE - Specific conditions and expectations
5. OUTLOOK - Upcoming conditions beyond forecast period

CRITICAL: You must write the actual forecast text now. Do not write instructions about how to write a forecast. Do not ask for more information. Write the complete forecast using the data provided in the user message.

ABSOLUTELY CRITICAL:
- You MUST write the complete forecast text in your response
- Do NOT say you need more information
- Do NOT provide a template or instructions
- Do NOT ask the user to paste anything
- Do NOT return an empty response
- WRITE THE ACTUAL FORECAST NOW using ONLY the data provided in the user message

EXAMPLE OUTPUT FORMAT:
SUMMARY
North-northwest swell 10-12ft arriving Wednesday morning, peaking Thursday. Light offshore winds Wednesday AM.

DETAILS
Primary NNW swell (320°) at 10-12ft Hawaiian scale, 12-15 second period. Peaks Thursday 6AM-2PM with clean conditions.

NORTH SHORE
Best conditions Thursday morning with offshore winds. Pipeline 8-12ft faces, Sunset 10-15ft. Watch for strong currents at exposed breaks.

SOUTH SHORE
Minimal swell activity, 1-2ft background south swell. Best spots: Ala Moana, Diamond Head for longboarding.

OUTLOOK
Swell declining Friday, next NW system arriving Sunday with potential for 12-15ft faces.
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

Write the complete forecast now using the Pat Caldwell style with SUMMARY, DETAILS, NORTH SHORE, SOUTH SHORE, and OUTLOOK sections.
"""
            }
        elif template_name == 'north_shore':
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

Write the complete North Shore forecast now using Pat Caldwell's technical style.
"""
            }
        elif template_name == 'south_shore':
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

Write the complete South Shore forecast now using Pat Caldwell's technical style.
"""
            }
        elif template_name == 'daily':
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

Write the complete daily report now in a concise, practical style.
"""
            }
    
    def get_template(self, template_name: str) -> Dict[str, Any]:
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
    
    def _get_swell_period(self, swell: Dict[str, Any]) -> float:
        """
        Extract dominant period from swell event.
        
        Args:
            swell: Swell event dictionary
            
        Returns:
            Dominant period in seconds
        """
        # Try direct field first
        if 'dominant_period' in swell and swell['dominant_period']:
            return float(swell['dominant_period'])
        
        # Try primary components
        primary_components = swell.get('primary_components', [])
        if primary_components:
            # Filter out None values and convert to float
            periods = [float(c['period']) for c in primary_components if c.get('period') is not None]
            if periods:
                return max(periods)
        
        return 0.0
    
    def get_caldwell_prompt(self, forecast_data: Dict[str, Any]) -> str:
        """
        Generate a prompt for Caldwell-style forecast.
        
        Args:
            forecast_data: Data for the forecast
            
        Returns:
            Formatted prompt string
        """
        template = self.get_template('caldwell')
        user_prompt = template.get('user_prompt', '')
        
        # Format swell details
        swell_details = []
        for swell in forecast_data.get('swell_events', []):
            period = self._get_swell_period(swell)
            
            # Extract source attribution
            metadata = swell.get('metadata', {})
            source_details = metadata.get('source_details', {})
            source_info = ""
            if source_details:
                buoy_id = source_details.get('buoy_id', '')
                obs_time = source_details.get('observation_time', '')
                source_type = source_details.get('source_type', '')
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
        seasonal_context = forecast_data.get('seasonal_context', {})
        season = seasonal_context.get('current_season', 'unknown').title()
        seasonal_patterns = seasonal_context.get('seasonal_patterns', {})
        
        seasonal_info = f"{season} season - "
        for shore, patterns in seasonal_patterns.items():
            shore_name = shore.replace('_', ' ').title()
            conditions = patterns.get('typical_conditions', '')
            seasonal_info += f"{shore_name}: {conditions}. "
        
        # Format weather conditions
        weather = forecast_data.get('metadata', {}).get('weather', {})
        wind_dir = weather.get('wind_direction')
        wind_speed = weather.get('wind_speed')
        if wind_dir is not None and wind_speed is not None:
            wind_str = f"Wind: {wind_dir}° at {wind_speed} knots"
        elif wind_dir is not None:
            wind_str = f"Wind: {wind_dir}° (speed unavailable)"
        else:
            wind_str = "Wind: Variable/Light"
        
        weather_conditions = (
            f"{wind_str}. "
            f"Conditions: {weather.get('conditions', 'Unknown')}. "
            f"Temperature: {weather.get('temperature', 0)}°C."
        )
        
        # Format tide info
        tides = forecast_data.get('metadata', {}).get('tides', {})
        high_tides = tides.get('high_tide', [])
        low_tides = tides.get('low_tide', [])
        
        tide_info = "Tides: "
        if high_tides:
            tide_info += "High: " + ", ".join([f"{time} ({height}ft)" for time, height in high_tides]) + ". "
        if low_tides:
            tide_info += "Low: " + ", ".join([f"{time} ({height}ft)" for time, height in low_tides]) + "."
        
        # Format primary shores
        primary_shores = ", ".join(forecast_data.get('shores', ['North Shore', 'South Shore']))
        
        # Format prompt
        formatted_prompt = user_prompt.format(
            start_date=forecast_data.get('start_date', ''),
            end_date=forecast_data.get('end_date', ''),
            swell_details="\n".join(swell_details),
            seasonal_context=seasonal_info,
            weather_conditions=weather_conditions,
            tide_info=tide_info,
            primary_shores=primary_shores
        )
        
        return formatted_prompt
    
    def get_shore_prompt(self, shore: str, forecast_data: Dict[str, Any]) -> str:
        """
        Generate a prompt for shore-specific forecast.
        
        Args:
            shore: Shore name ('north_shore' or 'south_shore')
            forecast_data: Data for the forecast
            
        Returns:
            Formatted prompt string
        """
        template_name = shore if shore in ['north_shore', 'south_shore'] else 'north_shore'
        template = self.get_template(template_name)
        user_prompt = template.get('user_prompt', '')
        
        # Get shore data
        shore_data = forecast_data.get('shore_data', {}).get(shore, {})
        if not shore_data:
            logger.warning(f"No data found for {shore}")
            return f"Generate a {shore.replace('_', ' ').title()} forecast for {forecast_data.get('start_date', '')}."
        
        # Format shore-specific swells
        shore_swells = []
        for swell in shore_data.get('swell_events', []):
            exposure = swell.get('metadata', {}).get(f'exposure_{shore}', 0.5)
            effect = "strong" if exposure > 0.7 else ("moderate" if exposure > 0.4 else "minimal")
            period = self._get_swell_period(swell)
            
            shore_swells.append(
                f"- {swell.get('primary_direction_cardinal', 'Unknown')} swell at "
                f"{swell.get('hawaii_scale', 0):.1f}ft (Hawaiian), "
                f"period: {period:.1f}s, "
                f"{effect} effect on {shore.replace('_', ' ').title()}"
            )
        
        # Format weather conditions
        weather = forecast_data.get('metadata', {}).get('weather', {})
        wind_dir = weather.get('wind_direction')
        wind_speed = weather.get('wind_speed')
        if wind_dir is not None and wind_speed is not None:
            wind_str = f"Wind: {wind_dir}° at {wind_speed} knots"
        elif wind_dir is not None:
            wind_str = f"Wind: {wind_dir}° (speed unavailable)"
        else:
            wind_str = "Wind: Variable/Light"
        
        weather_conditions = (
            f"{wind_str}. "
            f"Conditions: {weather.get('conditions', 'Unknown')}."
        )
        
        # Format popular breaks
        popular_breaks = shore_data.get('metadata', {}).get('popular_breaks', [])
        popular_breaks_str = ", ".join(popular_breaks) if popular_breaks else "Various breaks"
        
        # Format prompt
        formatted_prompt = user_prompt.format(
            start_date=forecast_data.get('start_date', ''),
            end_date=forecast_data.get('end_date', ''),
            north_shore_swells="\n".join(shore_swells) if shore == 'north_shore' else "N/A",
            south_shore_swells="\n".join(shore_swells) if shore == 'south_shore' else "N/A",
            weather_conditions=weather_conditions,
            popular_breaks=popular_breaks_str
        )
        
        return formatted_prompt