"""
Main forecast engine for SurfCastAI.

This module contains the main forecast engine responsible for
generating comprehensive surf forecasts based on processed data.
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .prompt_templates import PromptTemplates
from ..processing.models.swell_event import SwellForecast, SwellEvent, ForecastLocation
from ..core.config import Config


class ForecastEngine:
    """
    Main forecast engine for generating surf forecasts.
    
    Features:
    - Converts processed data into comprehensive surf forecasts
    - Uses AI to generate natural language forecasts
    - Supports iterative refinement for improved quality
    - Includes specialized North/South shore analysis
    - Incorporates seasonal context into forecasts
    """
    
    def __init__(self, config: Config):
        """
        Initialize the forecast engine.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger('forecast.engine')
        
        # Set up templates
        templates_dir = self.config.get('forecast', 'templates_dir', None)
        self.templates = PromptTemplates(templates_dir)
        
        # Load OpenAI configuration
        self.openai_api_key = self.config.get('openai', 'api_key', os.environ.get('OPENAI_API_KEY'))
        self.openai_model = self.config.get('openai', 'model', 'gpt-4-1106-preview')
        self.temperature = self.config.getfloat('openai', 'temperature', 0.7)
        self.max_tokens = self.config.getint('openai', 'max_tokens', 4000)
        
        # Set up iterative refinement
        self.refinement_cycles = self.config.getint('forecast', 'refinement_cycles', 2)
        self.quality_threshold = self.config.getfloat('forecast', 'quality_threshold', 0.8)
    
    async def generate_forecast(self, swell_forecast: SwellForecast) -> Dict[str, Any]:
        """
        Generate a complete surf forecast from processed data.
        
        Args:
            swell_forecast: Processed swell forecast data
            
        Returns:
            Dictionary containing generated forecasts
        """
        try:
            self.logger.info("Starting forecast generation")
            
            # Extract forecast information
            forecast_id = swell_forecast.forecast_id
            generated_time = datetime.now().isoformat()
            
            # Prepare forecast data
            forecast_data = self._prepare_forecast_data(swell_forecast)
            
            # Generate main forecast
            main_forecast = await self._generate_main_forecast(forecast_data)
            
            # Generate shore-specific forecasts
            north_shore_forecast = await self._generate_shore_forecast('north_shore', forecast_data)
            south_shore_forecast = await self._generate_shore_forecast('south_shore', forecast_data)
            
            # Generate daily forecast
            daily_forecast = await self._generate_daily_forecast(forecast_data)
            
            # Combine results
            result = {
                'forecast_id': forecast_id,
                'generated_time': generated_time,
                'main_forecast': main_forecast,
                'north_shore': north_shore_forecast,
                'south_shore': south_shore_forecast,
                'daily': daily_forecast,
                'metadata': {
                    'source_data': {
                        'swell_events': len(swell_forecast.swell_events),
                        'locations': len(swell_forecast.locations)
                    },
                    'confidence': forecast_data.get('confidence', {})
                }
            }
            
            self.logger.info(f"Forecast generation completed for forecast ID: {forecast_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating forecast: {e}")
            return {
                'error': str(e),
                'forecast_id': swell_forecast.forecast_id,
                'generated_time': datetime.now().isoformat()
            }
    
    def _prepare_forecast_data(self, swell_forecast: SwellForecast) -> Dict[str, Any]:
        """
        Prepare data for forecast generation.
        
        Args:
            swell_forecast: Processed swell forecast data
            
        Returns:
            Dictionary with prepared data for templates
        """
        # Calculate date range
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        # Extract confidence data
        confidence = swell_forecast.metadata.get('confidence', {})
        
        # Prepare swell events
        swell_events = []
        for event in swell_forecast.swell_events:
            swell_events.append({
                'event_id': event.event_id,
                'start_time': event.start_time,
                'peak_time': event.peak_time,
                'end_time': event.end_time,
                'primary_direction': event.primary_direction,
                'primary_direction_cardinal': event.primary_direction_cardinal,
                'significance': event.significance,
                'hawaii_scale': event.hawaii_scale,
                'source': event.source,
                'dominant_period': event.dominant_period
            })
        
        # Prepare shore data
        shore_data = {}
        for location in swell_forecast.locations:
            shore_name = location.shore.lower().replace(' ', '_')
            
            # Get shore-specific swell events
            shore_events = []
            for event in location.swell_events:
                shore_events.append({
                    'event_id': event.event_id,
                    'start_time': event.start_time,
                    'peak_time': event.peak_time,
                    'end_time': event.end_time,
                    'primary_direction': event.primary_direction,
                    'primary_direction_cardinal': event.primary_direction_cardinal,
                    'significance': event.significance,
                    'hawaii_scale': event.hawaii_scale,
                    'source': event.source,
                    'dominant_period': event.dominant_period,
                    'exposure_factor': event.metadata.get(f'exposure_{shore_name}', 0.5)
                })
            
            shore_data[shore_name] = {
                'name': location.shore,
                'swell_events': shore_events,
                'metadata': location.metadata,
                'latitude': location.latitude,
                'longitude': location.longitude,
                'facing_direction': location.facing_direction
            }
        
        # Determine primary shores based on activity
        primary_shores = []
        if shore_data.get('north_shore', {}).get('swell_events'):
            primary_shores.append('North Shore')
        if shore_data.get('south_shore', {}).get('swell_events'):
            primary_shores.append('South Shore')
        
        # Prepare forecast data
        forecast_data = {
            'forecast_id': swell_forecast.forecast_id,
            'start_date': start_date,
            'end_date': end_date,
            'region': 'Oahu',
            'shores': primary_shores,
            'swell_events': swell_events,
            'shore_data': shore_data,
            'confidence': confidence,
            'metadata': swell_forecast.metadata
        }
        
        # Add seasonal context
        forecast_data['seasonal_context'] = self._get_seasonal_context()
        
        return forecast_data
    
    def _get_seasonal_context(self) -> Dict[str, Any]:
        """
        Get seasonal context information.
        
        Returns:
            Dictionary with seasonal context
        """
        now = datetime.now()
        month = now.month
        
        # Determine season
        if 11 <= month <= 12 or 1 <= month <= 3:
            season = 'winter'
        elif 4 <= month <= 5:
            season = 'spring'
        elif 6 <= month <= 8:
            season = 'summer'
        else:  # 9, 10
            season = 'fall'
        
        # Seasonal patterns
        seasonal_info = {
            'winter': {
                'north_shore': {
                    'primary_swell_direction': 'NW',
                    'typical_size_range': '4-12+ feet (Hawaiian)',
                    'quality': 'High',
                    'consistency': 'High',
                    'typical_conditions': 'Consistent NW to N swells with varying wind conditions. Prime season for North Shore with frequent large swells.'
                },
                'south_shore': {
                    'primary_swell_direction': 'Background S',
                    'typical_size_range': '0-2 feet (Hawaiian)',
                    'quality': 'Low',
                    'consistency': 'Low',
                    'typical_conditions': 'Generally flat with occasional small background swells. Not prime season for South Shore.'
                }
            },
            'summer': {
                'north_shore': {
                    'primary_swell_direction': 'Background NW',
                    'typical_size_range': '0-3 feet (Hawaiian)',
                    'quality': 'Low',
                    'consistency': 'Low',
                    'typical_conditions': 'Generally flat with occasional small background swells. Not prime season for North Shore.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S to SW',
                    'typical_size_range': '2-5+ feet (Hawaiian)',
                    'quality': 'High',
                    'consistency': 'High',
                    'typical_conditions': 'Consistent S to SW swells with generally favorable trade winds. Prime season for South Shore.'
                }
            },
            'spring': {
                'north_shore': {
                    'primary_swell_direction': 'NW to N',
                    'typical_size_range': '3-8 feet (Hawaiian)',
                    'quality': 'Medium-High',
                    'consistency': 'Medium',
                    'typical_conditions': 'Transition season with decreasing NW swells but generally good conditions with lighter winds.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S',
                    'typical_size_range': '1-3+ feet (Hawaiian)',
                    'quality': 'Medium',
                    'consistency': 'Medium',
                    'typical_conditions': 'Beginning of south swell season with increasing activity and size.'
                }
            },
            'fall': {
                'north_shore': {
                    'primary_swell_direction': 'NW to WNW',
                    'typical_size_range': '2-6+ feet (Hawaiian)',
                    'quality': 'Medium',
                    'consistency': 'Medium',
                    'typical_conditions': 'Early season NW swells begin to arrive. Transition period with improving conditions as winter approaches.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S to SSW',
                    'typical_size_range': '1-3 feet (Hawaiian)',
                    'quality': 'Medium-Low',
                    'consistency': 'Medium-Low',
                    'typical_conditions': 'End of south swell season with decreasing activity and size.'
                }
            }
        }
        
        return {
            'current_season': season,
            'month': month,
            'seasonal_patterns': seasonal_info[season]
        }
    
    async def _generate_main_forecast(self, forecast_data: Dict[str, Any]) -> str:
        """
        Generate the main comprehensive forecast.
        
        Args:
            forecast_data: Prepared forecast data
            
        Returns:
            Generated forecast text
        """
        # Generate prompt
        prompt = self.templates.get_caldwell_prompt(forecast_data)
        
        # Get template
        template = self.templates.get_template('caldwell')
        system_prompt = template.get('system_prompt', '')
        
        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get('seasonal_context', {})
        season = seasonal_context.get('current_season', 'unknown')
        seasonal_patterns = seasonal_context.get('seasonal_patterns', {})
        
        system_prompt += f"\n\nCurrent Season: {season.title()}\n"
        system_prompt += f"Typical {season.title()} Patterns:\n"
        for shore, info in seasonal_patterns.items():
            system_prompt += f"- {shore.replace('_', ' ').title()}: {info.get('typical_conditions', '')}\n"
        
        # Add confidence information
        confidence = forecast_data.get('confidence', {})
        overall_confidence = confidence.get('overall_score', 0.7)
        
        system_prompt += f"\nOverall Forecast Confidence: {overall_confidence:.1f}/1.0\n"
        if overall_confidence < 0.6:
            system_prompt += "Include appropriate language indicating lower confidence in the forecast.\n"
        
        # Generate forecast
        forecast = await self._call_openai_api(system_prompt, prompt)
        
        # Apply iterative refinement if enabled
        if self.refinement_cycles > 0:
            forecast = await self._refine_forecast(forecast, forecast_data)
        
        return forecast
    
    async def _generate_shore_forecast(self, shore: str, forecast_data: Dict[str, Any]) -> str:
        """
        Generate a shore-specific forecast.
        
        Args:
            shore: Shore name ('north_shore' or 'south_shore')
            forecast_data: Prepared forecast data
            
        Returns:
            Generated shore-specific forecast text
        """
        # Generate prompt
        prompt = self.templates.get_shore_prompt(shore, forecast_data)
        
        # Get template
        template_name = 'north_shore' if 'north' in shore.lower() else 'south_shore'
        template = self.templates.get_template(template_name)
        system_prompt = template.get('system_prompt', '')
        
        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get('seasonal_context', {})
        season = seasonal_context.get('current_season', 'unknown')
        seasonal_patterns = seasonal_context.get('seasonal_patterns', {})
        
        if shore in seasonal_patterns:
            shore_info = seasonal_patterns[shore]
            system_prompt += f"\n\nCurrent Season: {season.title()}\n"
            system_prompt += f"Typical {season.title()} Patterns for {shore.replace('_', ' ').title()}:\n"
            system_prompt += f"- Primary Swell Direction: {shore_info.get('primary_swell_direction', '')}\n"
            system_prompt += f"- Typical Size Range: {shore_info.get('typical_size_range', '')}\n"
            system_prompt += f"- Typical Conditions: {shore_info.get('typical_conditions', '')}\n"
        
        # Generate forecast
        forecast = await self._call_openai_api(system_prompt, prompt)
        
        return forecast
    
    async def _generate_daily_forecast(self, forecast_data: Dict[str, Any]) -> str:
        """
        Generate a daily forecast.
        
        Args:
            forecast_data: Prepared forecast data
            
        Returns:
            Generated daily forecast text
        """
        # Get template
        template = self.templates.get_template('daily')
        system_prompt = template.get('system_prompt', '')
        
        # Build prompt
        start_date = forecast_data.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        region = forecast_data.get('region', 'Oahu')
        
        # Extract significant swell events
        swell_events = forecast_data.get('swell_events', [])
        swell_description = ""
        
        if swell_events:
            # Get the most significant event
            main_event = max(swell_events, key=lambda e: e.get('significance', 0))
            direction = main_event.get('primary_direction_cardinal', 'NW')
            
            swell_description = f"with a {direction} swell"
        
        prompt = f"Generate a daily surf forecast for {region} for {start_date}, {swell_description}."
        
        # Generate forecast
        forecast = await self._call_openai_api(system_prompt, prompt)
        
        return forecast
    
    async def _refine_forecast(self, initial_forecast: str, forecast_data: Dict[str, Any]) -> str:
        """
        Apply iterative refinement to improve forecast quality.
        
        Args:
            initial_forecast: Initial generated forecast
            forecast_data: Forecast data for context
            
        Returns:
            Refined forecast text
        """
        current_forecast = initial_forecast
        
        for i in range(self.refinement_cycles):
            self.logger.info(f"Starting refinement cycle {i+1}/{self.refinement_cycles}")
            
            # Create refinement prompt
            system_prompt = """
You are an expert surf forecaster who specializes in improving the quality and accuracy of surf forecasts.
Carefully review the provided forecast and improve it based on the following criteria:

1. Technical accuracy - ensure swell heights, periods, and directions are consistent and accurate
2. Clarity - make sure the forecast is easy to understand while maintaining technical detail
3. Completeness - ensure all relevant shores and time periods are covered
4. Consistency - check that the forecast is internally consistent throughout
5. Specificity - add precise details about timing, locations, and conditions where possible

The goal is to maintain the original style and voice while improving overall quality.
Do NOT add fictional data or contradict the original forecast's core information.
"""
            
            # Add specific improvement instructions based on refinement cycle
            if i == 0:
                system_prompt += "\nFocus particularly on technical accuracy and consistency.\n"
            elif i == 1:
                system_prompt += "\nFocus particularly on clarity and specificity of details.\n"
            
            # Add confidence indicators if confidence is low
            confidence = forecast_data.get('confidence', {}).get('overall_score', 0.7)
            if confidence < 0.6:
                system_prompt += "\nMake sure to include appropriate language indicating uncertainty where relevant.\n"
            
            # Create user prompt
            prompt = f"""
Please review and improve the following surf forecast:

---
{current_forecast}
---

Improve this forecast while maintaining its style and core information. Focus on technical accuracy, clarity, consistency, and specificity.
"""
            
            # Generate refined forecast
            refined_forecast = await self._call_openai_api(system_prompt, prompt)
            
            # Update current forecast for next cycle
            current_forecast = refined_forecast
        
        return current_forecast
    
    async def _call_openai_api(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the OpenAI API to generate text.
        
        Args:
            system_prompt: System prompt for the model
            user_prompt: User prompt containing specific request
            
        Returns:
            Generated text
        """
        # Import here to avoid dependency if OpenAI is not available
        try:
            from openai import AsyncOpenAI
        except ImportError:
            self.logger.error("OpenAI package not installed. Please install it with: pip install openai")
            return "Error: OpenAI package not installed."
        
        try:
            # Initialize client
            client = AsyncOpenAI(api_key=self.openai_api_key)
            
            # Call API
            response = await client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract and return content
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content.strip()
            else:
                self.logger.error("No content returned from OpenAI API")
                return "Error: No content returned from API."
                
        except Exception as e:
            self.logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating forecast: {str(e)}"