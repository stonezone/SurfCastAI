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
You are Pat Caldwell, a veteran Hawaiian surf forecaster with decades of experience. 
Your forecasts are highly respected for their technical accuracy, detailed swell analysis, 
and precise timing information. You write in a distinctive, concise style that blends technical 
meteorological information with practical surf insights.

Follow these principles in your forecast:
1. Focus on swell direction, period, and size as primary factors
2. Provide specific timing for swell arrivals, peaks, and declines
3. Include relevant weather and wind conditions affecting surf quality
4. Differentiate between North Shore and South Shore conditions
5. Use Hawaiian scale for wave heights (roughly half the face height)
6. Include technical details like swell period, direction in degrees, and origins
7. Keep to a concise, information-dense style with minimal fluff
8. Reference specific surf breaks when relevant to the forecast

Your forecast should have these sections:
- SUMMARY: Brief overview of the main swell(s)
- DETAILS: Technical breakdown of swell components with timing
- NORTH SHORE: Specific conditions and expectations
- SOUTH SHORE: Specific conditions and expectations
- OUTLOOK: Brief mention of upcoming conditions beyond the forecast period
""",
                "user_prompt": """
Please generate a comprehensive surf forecast for Hawaii (Oahu) for {start_date} to {end_date}.

Primary swell information:
{swell_details}

Current seasonal context: {seasonal_context}

Weather conditions: {weather_conditions}

Tide information: {tide_info}

Focus particularly on breaks at {primary_shores}.
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
Please generate a North Shore-specific surf forecast for {start_date} to {end_date}.

Current North Shore swells:
{north_shore_swells}

Weather conditions:
{weather_conditions}

Notable North Shore breaks: {popular_breaks}
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
Please generate a South Shore-specific surf forecast for {start_date} to {end_date}.

Current South Shore swells:
{south_shore_swells}

Weather conditions:
{weather_conditions}

Notable South Shore breaks: {popular_breaks}
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
Please generate a daily surf report for {region} for {start_date}.

Current swells: {current_swells}

Weather: {weather_conditions}

Tides: {tide_info}
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
            swell_details.append(
                f"- {swell.get('primary_direction_cardinal', 'Unknown')} swell at "
                f"{swell.get('hawaii_scale', 0):.1f}ft (Hawaiian), "
                f"period: {swell.get('dominant_period', 0):.1f}s, "
                f"arriving: {swell.get('start_time', '')}, "
                f"peaking: {swell.get('peak_time', '')}"
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
        weather_conditions = (
            f"Wind: {weather.get('wind_direction', 'Unknown')} at {weather.get('wind_speed', 0)} knots. "
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
            
            shore_swells.append(
                f"- {swell.get('primary_direction_cardinal', 'Unknown')} swell at "
                f"{swell.get('hawaii_scale', 0):.1f}ft (Hawaiian), "
                f"period: {swell.get('dominant_period', 0):.1f}s, "
                f"{effect} effect on {shore.replace('_', ' ').title()}"
            )
        
        # Format weather conditions
        weather = forecast_data.get('metadata', {}).get('weather', {})
        weather_conditions = (
            f"Wind: {weather.get('wind_direction', 'Unknown')} at {weather.get('wind_speed', 0)} knots. "
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