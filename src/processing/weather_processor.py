"""
Weather data processor for SurfCastAI.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
from datetime import datetime, timedelta
import re

from .data_processor import DataProcessor, ProcessingResult
from .models.weather_data import WeatherData, WeatherPeriod
from .hawaii_context import HawaiiContext
from ..core.config import Config


class WindCondition:
    """
    Wind condition classification for surf forecasting.

    Attributes:
        name: Name of the condition
        description: Description of the condition
        min_speed: Minimum wind speed (m/s)
        max_speed: Maximum wind speed (m/s)
        surf_impact: Impact on surf quality (-1.0 to 1.0)
    """
    def __init__(
        self,
        name: str,
        description: str,
        min_speed: float,
        max_speed: float,
        surf_impact: float
    ):
        self.name = name
        self.description = description
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.surf_impact = surf_impact


class WeatherProcessor(DataProcessor[Dict[str, Any], WeatherData]):
    """
    Processor for weather data.

    Features:
    - Converts raw weather data to standardized WeatherData model
    - Validates data completeness and consistency
    - Analyzes wind patterns and trends relevant for surf conditions
    - Provides surf-relevant weather analysis for forecast generation
    """

    def __init__(self, config: Config):
        """
        Initialize the weather processor.

        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('processor.weather')
        self.hawaii_context = HawaiiContext()

        # Define wind conditions and their impact on surf
        self.wind_conditions = [
            WindCondition("Calm", "Calm or very light winds", 0.0, 2.5, 1.0),
            WindCondition("Light Offshore", "Light offshore winds, ideal for surf", 2.5, 5.0, 0.9),
            WindCondition("Moderate Offshore", "Moderate offshore winds, good for surf", 5.0, 7.5, 0.7),
            WindCondition("Strong Offshore", "Strong offshore winds, can blow spray", 7.5, 12.5, 0.4),
            WindCondition("Light Onshore", "Light onshore winds, slight texture", 2.5, 5.0, -0.3),
            WindCondition("Moderate Onshore", "Moderate onshore winds, choppy conditions", 5.0, 10.0, -0.6),
            WindCondition("Strong Onshore", "Strong onshore winds, poor conditions", 10.0, float('inf'), -0.9),
        ]

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate weather data.

        Args:
            data: Raw weather data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for required fields
        if 'properties' not in data:
            errors.append("Missing properties field in weather data")

        # Check for forecast periods
        properties = data.get('properties', {})
        periods = properties.get('periods', [])
        if not periods:
            errors.append("No forecast periods in weather data")

        return errors

    def process(self, data: Dict[str, Any]) -> ProcessingResult:
        """
        Process weather data.

        Args:
            data: Raw weather data

        Returns:
            ProcessingResult with processed WeatherData
        """
        try:
            # Create WeatherData from raw data
            weather_data = WeatherData.from_nws_json(data)

            # Check if we have any periods
            if not weather_data.periods:
                return ProcessingResult(
                    success=False,
                    error="No forecast periods found in weather data",
                    data=weather_data
                )

            # Standardize units if needed
            weather_data = self._standardize_units(weather_data)

            # Analyze wind patterns and surf impact
            weather_data = self._analyze_wind_patterns(weather_data)

            # Extract additional information from forecast text
            weather_data = self._extract_text_information(weather_data)

            # Classify weather patterns relevant to surf
            warnings, metadata = self._classify_weather_patterns(weather_data)

            # Add metadata from analysis
            weather_data.metadata.update(metadata)

            return ProcessingResult(
                success=True,
                data=weather_data,
                warnings=warnings,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error processing weather data: {e}")
            return ProcessingResult(
                success=False,
                error=f"Processing error: {str(e)}"
            )

    def _standardize_units(self, weather_data: WeatherData) -> WeatherData:
        """
        Standardize units across weather periods.

        Args:
            weather_data: Original weather data

        Returns:
            Weather data with standardized units
        """
        for period in weather_data.periods:
            # Convert temperature to Celsius if in Fahrenheit
            if period.temperature is not None and period.temperature_unit.upper() == 'F':
                period.temperature = (period.temperature - 32) * 5 / 9
                period.temperature_unit = 'C'

            # Convert wind speed to m/s if in other units
            if period.wind_speed is not None:
                if period.wind_speed_unit.lower() == 'mph':
                    period.wind_speed = period.wind_speed * 0.44704
                    period.wind_speed_unit = 'm/s'
                elif period.wind_speed_unit.lower() == 'knots':
                    period.wind_speed = period.wind_speed * 0.51444
                    period.wind_speed_unit = 'm/s'
                elif period.wind_speed_unit.lower() == 'km/h':
                    period.wind_speed = period.wind_speed * 0.27778
                    period.wind_speed_unit = 'm/s'

        return weather_data

    def _analyze_wind_patterns(self, weather_data: WeatherData) -> WeatherData:
        """
        Analyze wind patterns for surf relevance.

        Args:
            weather_data: Weather data to analyze

        Returns:
            Weather data with added wind analysis
        """
        # Prepare wind analysis metadata
        wind_analysis = {
            'wind_trends': {},
            'shore_impacts': {},
            'by_period': []
        }

        # Get all shores
        shores = self.hawaii_context.get_all_shores()

        # Initialize shore impacts
        for shore in shores:
            shore_name = shore.name.lower().replace(' ', '_')
            wind_analysis['shore_impacts'][shore_name] = {
                'favorable_periods': 0,
                'unfavorable_periods': 0,
                'overall_rating': 0.0
            }

        # Track wind directions and speeds
        wind_directions = []
        wind_speeds = []

        # Analyze each period
        for period in weather_data.periods:
            period_analysis = {
                'timestamp': period.timestamp,
                'conditions': {},
                'shore_impacts': {}
            }

            # Skip if no wind data
            if period.wind_speed is None or period.wind_direction is None:
                continue

            # Track directions and speeds
            wind_directions.append(period.wind_direction)
            wind_speeds.append(period.wind_speed)

            # Classify wind condition
            condition = self._classify_wind_condition(period.wind_speed)
            period_analysis['conditions']['classification'] = condition.name
            period_analysis['conditions']['description'] = condition.description
            period_analysis['conditions']['surf_impact'] = condition.surf_impact

            # Analyze impact on each shore
            for shore in shores:
                shore_name = shore.name.lower().replace(' ', '_')

                # Calculate if wind is offshore or onshore
                is_offshore = self._is_offshore_wind(shore.facing_direction, period.wind_direction)
                wind_factor = condition.surf_impact

                # Adjust factor based on offshore/onshore
                if not is_offshore and wind_factor > 0:
                    wind_factor = -wind_factor  # Flip positive impact for onshore
                elif is_offshore and wind_factor < 0:
                    wind_factor = -wind_factor * 0.5  # Reduce negative impact for offshore

                # Record impact
                period_analysis['shore_impacts'][shore_name] = {
                    'is_offshore': is_offshore,
                    'impact_factor': wind_factor
                }

                # Update shore impact counters
                if wind_factor > 0:
                    wind_analysis['shore_impacts'][shore_name]['favorable_periods'] += 1
                elif wind_factor < 0:
                    wind_analysis['shore_impacts'][shore_name]['unfavorable_periods'] += 1

            # Add period analysis
            wind_analysis['by_period'].append(period_analysis)

        # Calculate overall trends
        if wind_directions:
            wind_analysis['wind_trends']['avg_direction'] = sum(wind_directions) / len(wind_directions)
            wind_analysis['wind_trends']['direction_variability'] = max(wind_directions) - min(wind_directions)

        if wind_speeds:
            wind_analysis['wind_trends']['avg_speed'] = sum(wind_speeds) / len(wind_speeds)
            wind_analysis['wind_trends']['max_speed'] = max(wind_speeds)
            wind_analysis['wind_trends']['min_speed'] = min(wind_speeds)
            wind_analysis['wind_trends']['speed_variability'] = max(wind_speeds) - min(wind_speeds)

        # Calculate overall shore ratings
        total_periods = len(wind_analysis['by_period'])
        if total_periods > 0:
            for shore_name in wind_analysis['shore_impacts']:
                shore_impact = wind_analysis['shore_impacts'][shore_name]
                favorable = shore_impact['favorable_periods']
                unfavorable = shore_impact['unfavorable_periods']

                # Calculate weighted score
                if favorable + unfavorable > 0:
                    overall_rating = (favorable - unfavorable) / (favorable + unfavorable)
                    # Scale from -1...1 to 0...1
                    overall_rating = (overall_rating + 1) / 2
                    shore_impact['overall_rating'] = overall_rating

        # Add wind analysis to metadata
        weather_data.metadata['wind_analysis'] = wind_analysis

        return weather_data

    def _extract_text_information(self, weather_data: WeatherData) -> WeatherData:
        """
        Extract additional information from forecast text.

        Args:
            weather_data: Weather data to analyze

        Returns:
            Weather data with additional extracted information
        """
        # Initialize text extraction results
        text_extraction = {
            'mentions': {
                'rain': 0,
                'shower': 0,
                'thunder': 0,
                'storm': 0,
                'sunny': 0,
                'clear': 0,
                'cloudy': 0,
                'humid': 0,
                'dry': 0,
                'hot': 0,
                'cool': 0
            },
            'rain_probability': {},
            'weather_type': {}
        }

        # Define patterns
        rain_pattern = re.compile(r'(\d+)% chance of (rain|showers|precipitation)', re.IGNORECASE)

        # Process each period
        for i, period in enumerate(weather_data.periods):
            period_key = f'period_{i+1}'

            # Skip if no forecast text
            if not period.detailed_forecast and not period.short_forecast:
                continue

            # Combine available text
            text = ""
            if period.detailed_forecast:
                text += period.detailed_forecast.lower() + " "
            if period.short_forecast:
                text += period.short_forecast.lower()

            # Count mentions
            for key in text_extraction['mentions']:
                if key.lower() in text:
                    text_extraction['mentions'][key] += 1

            # Extract rain probability
            rain_match = rain_pattern.search(text)
            if rain_match:
                try:
                    probability = int(rain_match.group(1))
                    text_extraction['rain_probability'][period_key] = probability
                except (ValueError, IndexError):
                    pass

            # Determine primary weather type
            if 'thunder' in text or 'lightning' in text:
                text_extraction['weather_type'][period_key] = 'thunderstorm'
            elif 'rain' in text or 'shower' in text:
                text_extraction['weather_type'][period_key] = 'rain'
            elif 'cloudy' in text or 'overcast' in text:
                text_extraction['weather_type'][period_key] = 'cloudy'
            elif 'partly cloudy' in text or 'partly sunny' in text:
                text_extraction['weather_type'][period_key] = 'partly_cloudy'
            elif 'sunny' in text or 'clear' in text:
                text_extraction['weather_type'][period_key] = 'sunny'
            else:
                text_extraction['weather_type'][period_key] = 'unknown'

        # Add text extraction to metadata
        weather_data.metadata['text_extraction'] = text_extraction

        return weather_data

    def _classify_weather_patterns(self, weather_data: WeatherData) -> tuple[List[str], Dict[str, Any]]:
        """
        Classify weather patterns relevant to surf conditions.

        Args:
            weather_data: Weather data to analyze

        Returns:
            Tuple of (warnings, metadata)
        """
        warnings = []
        metadata = {
            'surf_weather': {
                'patterns': [],
                'quality_score': 1.0,
                'favorable_conditions': [],
                'unfavorable_conditions': []
            }
        }

        # Check data freshness
        if weather_data.periods:
            try:
                # Get timestamp of first period
                timestamp = weather_data.periods[0].timestamp
                forecast_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                now = datetime.now(forecast_time.tzinfo)
                hours_old = (now - forecast_time).total_seconds() / 3600

                metadata['surf_weather']['hours_since_update'] = hours_old

                if hours_old > 12:
                    warnings.append(f"Weather forecast is {hours_old:.1f} hours old")
                    metadata['surf_weather']['quality_score'] -= min(0.5, hours_old / 48)
            except (ValueError, TypeError):
                warnings.append("Could not parse forecast timestamp")

        # Get wind analysis
        wind_analysis = weather_data.metadata.get('wind_analysis', {})
        wind_trends = wind_analysis.get('wind_trends', {})

        # Check for wind patterns
        if 'avg_speed' in wind_trends:
            avg_speed = wind_trends['avg_speed']
            if avg_speed < 2.5:
                metadata['surf_weather']['patterns'].append('calm_winds')
                metadata['surf_weather']['favorable_conditions'].append('Calm winds')
            elif avg_speed > 10.0:
                metadata['surf_weather']['patterns'].append('strong_winds')
                metadata['surf_weather']['unfavorable_conditions'].append('Strong winds')

            if 'speed_variability' in wind_trends and wind_trends['speed_variability'] > 5.0:
                metadata['surf_weather']['patterns'].append('variable_winds')

        # Check for weather patterns from text extraction
        text_extraction = weather_data.metadata.get('text_extraction', {})
        mentions = text_extraction.get('mentions', {})

        if mentions.get('thunder', 0) > 0 or mentions.get('storm', 0) > 0:
            metadata['surf_weather']['patterns'].append('thunderstorms')
            metadata['surf_weather']['unfavorable_conditions'].append('Thunderstorms')
            metadata['surf_weather']['quality_score'] -= 0.3

        if mentions.get('rain', 0) > 2 or mentions.get('shower', 0) > 2:
            metadata['surf_weather']['patterns'].append('rainy')
            metadata['surf_weather']['unfavorable_conditions'].append('Rainy conditions')
            metadata['surf_weather']['quality_score'] -= 0.1

        if mentions.get('sunny', 0) > 2 or mentions.get('clear', 0) > 2:
            metadata['surf_weather']['patterns'].append('sunny')
            metadata['surf_weather']['favorable_conditions'].append('Sunny conditions')

        # Get overall shore ratings
        shore_impacts = wind_analysis.get('shore_impacts', {})
        for shore_name, impact in shore_impacts.items():
            rating = impact.get('overall_rating', 0.5)
            shore_display = shore_name.replace('_', ' ').title()

            if rating > 0.7:
                metadata['surf_weather']['favorable_conditions'].append(
                    f"Favorable winds for {shore_display}"
                )
            elif rating < 0.3:
                metadata['surf_weather']['unfavorable_conditions'].append(
                    f"Unfavorable winds for {shore_display}"
                )

        return warnings, metadata

    def _classify_wind_condition(self, wind_speed: float) -> WindCondition:
        """
        Classify wind condition based on speed.

        Args:
            wind_speed: Wind speed in m/s

        Returns:
            WindCondition object
        """
        for condition in self.wind_conditions:
            if condition.min_speed <= wind_speed < condition.max_speed:
                return condition

        # Default to strongest condition if not found
        return self.wind_conditions[-1]

    def _is_offshore_wind(self, shore_direction: float, wind_direction: float) -> bool:
        """
        Check if wind is offshore for a specific shore.

        Args:
            shore_direction: Direction the shore faces (degrees)
            wind_direction: Wind direction (degrees)

        Returns:
            True if wind is offshore, False otherwise
        """
        # Calculate the opposite direction of shore
        offshore_direction = (shore_direction + 180) % 360

        # Calculate the difference between wind direction and offshore direction
        diff = abs(wind_direction - offshore_direction)
        if diff > 180:
            diff = 360 - diff

        # Consider wind offshore if within 90 degrees of offshore direction
        # For a north-facing shore (0°), winds from south (180°) are offshore
        # For an east-facing shore (90°), winds from west (270°) are offshore
        return diff < 90

    def get_surf_quality_factor(self, weather_data: WeatherData, shore_name: str) -> float:
        """
        Calculate surf quality factor based on weather for a specific shore.

        Args:
            weather_data: Weather data
            shore_name: Name of the shore

        Returns:
            Surf quality factor (0.0-1.0)
        """
        # Default quality is neutral
        quality = 0.5

        # Get wind analysis
        wind_analysis = weather_data.metadata.get('wind_analysis', {})
        shore_impacts = wind_analysis.get('shore_impacts', {})

        # Get specific shore impact
        shore_name_normalized = shore_name.lower().replace(' ', '_')
        shore_impact = shore_impacts.get(shore_name_normalized, {})
        overall_rating = shore_impact.get('overall_rating', 0.5)

        # Wind impact has high weight
        quality = overall_rating * 0.7 + 0.15  # Scale from 0.15 to 0.85

        # Check for unfavorable weather conditions
        surf_weather = weather_data.metadata.get('surf_weather', {})
        patterns = surf_weather.get('patterns', [])

        if 'thunderstorms' in patterns:
            quality -= 0.3
        elif 'rainy' in patterns:
            quality -= 0.1

        if 'sunny' in patterns:
            quality += 0.1

        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, quality))
