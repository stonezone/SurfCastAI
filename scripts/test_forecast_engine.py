#!/usr/bin/env python3
"""
Test script for the forecast engine.
"""

import asyncio
import logging
import sys
import json
import re
from pathlib import Path
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core import Config, load_config
from src.processing import (
    BuoyProcessor,
    WeatherProcessor,
    WaveModelProcessor,
    DataFusionSystem
)
from src.forecast_engine import (
    ForecastEngine,
    ForecastFormatter
)
from src.processing.models.swell_event import SwellForecast, SwellEvent, SwellComponent, ForecastLocation


def setup_logging(config):
    """Set up logging."""
    log_level_str = config.get('general', 'log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Get log file path
    log_file = config.get('general', 'log_file', 'surfcastai.log')
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    
    logger = logging.getLogger('surfcastai')
    logger.info(f"Logging initialized at level {log_level_str}")
    
    return logger


def validate_forecast_content(forecast, logger):
    """
    Validate the content of a generated forecast.
    
    Args:
        forecast: The generated forecast data
        logger: Logger instance
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'success': True,
        'reasons': [],
        'metrics': {}
    }
    
    # Check for required sections
    required_sections = ['main_forecast', 'north_shore', 'south_shore', 'daily']
    missing_sections = [section for section in required_sections if not forecast.get(section)]
    
    if missing_sections:
        results['success'] = False
        reasons = f"Missing required forecast sections: {', '.join(missing_sections)}"
        results['reasons'].append(reasons)
        logger.error(reasons)
    
    # Check for minimum content length
    min_length = 100  # characters
    for section in required_sections:
        if section in forecast:
            content = forecast[section]
            if len(content) < min_length:
                results['success'] = False
                reason = f"Section '{section}' is too short ({len(content)} chars)"
                results['reasons'].append(reason)
                logger.error(reason)
            
            # Track content metrics
            results['metrics'][f'{section}_length'] = len(content)
            results['metrics'][f'{section}_word_count'] = len(content.split())
    
    # Check for forecast metadata
    if 'metadata' not in forecast:
        results['success'] = False
        reason = "Missing forecast metadata"
        results['reasons'].append(reason)
        logger.error(reason)
    
    # Check for shore-specific information
    shore_keywords = {
        'north_shore': ['north', 'pipeline', 'sunset', 'waimea'],
        'south_shore': ['south', 'waikiki', 'ala moana', 'town']
    }
    
    for shore, keywords in shore_keywords.items():
        if shore in forecast:
            content = forecast[shore].lower()
            found_keywords = [kw for kw in keywords if kw.lower() in content]
            keyword_ratio = len(found_keywords) / len(keywords)
            
            results['metrics'][f'{shore}_keyword_ratio'] = keyword_ratio
            
            if keyword_ratio < 0.5:  # At least half of the expected keywords should be present
                logger.warning(f"Section '{shore}' may lack specificity (keyword ratio: {keyword_ratio:.2f})")
    
    # Check for swell directional information
    directional_terms = ['north', 'south', 'east', 'west', 'nw', 'ne', 'sw', 'se', 'ene', 'ese', 'wnw', 'wsw']
    main_content = forecast.get('main_forecast', '').lower()
    
    found_directional = [term for term in directional_terms if term in main_content]
    if not found_directional:
        results['success'] = False
        reason = "Main forecast lacks directional information"
        results['reasons'].append(reason)
        logger.error(reason)
    
    # Check for wave height information (numbers followed by "ft" or "feet")
    height_pattern = r'\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*(?:ft|feet|foot)'
    height_matches = re.findall(height_pattern, main_content)
    
    if not height_matches:
        results['success'] = False
        reason = "Main forecast lacks wave height information"
        results['reasons'].append(reason)
        logger.error(reason)
    
    # Check for timing information
    timing_terms = ['today', 'tomorrow', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                   'morning', 'afternoon', 'evening', 'overnight', 'building', 'peaking', 'dropping']
    
    found_timing = [term for term in timing_terms if term in main_content]
    if not found_timing:
        results['success'] = False
        reason = "Main forecast lacks timing information"
        results['reasons'].append(reason)
        logger.error(reason)
    
    return results


def create_test_swell_forecast():
    """Create a test swell forecast for testing."""
    # Create current timestamps for more realistic testing
    now = datetime.now()
    start_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    peak_time = (now + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Create a NW swell event (primary winter swell direction)
    event = SwellEvent(
        event_id="test_event_1",
        start_time=start_time,
        peak_time=peak_time,
        end_time=end_time,
        primary_direction=315,  # NW swell
        significance=0.8,
        hawaii_scale=12.0,
        source="model",
        metadata={
            "confidence": 0.8,
            "model_id": "swan",
            "exposure_north_shore": 0.9,
            "exposure_south_shore": 0.2
        }
    )
    
    # Add primary component
    event.primary_components.append(
        SwellComponent(
            height=3.0,
            period=15.0,
            direction=315,
            confidence=0.9,
            source="model"
        )
    )
    
    # Add secondary component
    event.secondary_components.append(
        SwellComponent(
            height=1.5,
            period=10.0,
            direction=300,
            confidence=0.7,
            source="model"
        )
    )
    
    # Create a south swell event
    event2 = SwellEvent(
        event_id="test_event_2",
        start_time=start_time,
        peak_time=peak_time,
        end_time=end_time,
        primary_direction=190,  # S swell
        significance=0.5,
        hawaii_scale=4.0,
        source="model",
        metadata={
            "confidence": 0.7,
            "model_id": "swan",
            "exposure_north_shore": 0.1,
            "exposure_south_shore": 0.8
        }
    )
    
    # Add primary component
    event2.primary_components.append(
        SwellComponent(
            height=1.5,
            period=12.0,
            direction=190,
            confidence=0.8,
            source="model"
        )
    )
    
    # Create a trade wind swell (common in Hawaii)
    event3 = SwellEvent(
        event_id="test_event_3",
        start_time=start_time,
        peak_time=peak_time,
        end_time=end_time,
        primary_direction=70,  # ENE trade wind swell
        significance=0.4,
        hawaii_scale=3.0,
        source="buoy",
        metadata={
            "confidence": 0.9,
            "buoy_id": "51001",
            "exposure_north_shore": 0.5,
            "exposure_south_shore": 0.1
        }
    )
    
    # Add primary component
    event3.primary_components.append(
        SwellComponent(
            height=1.0,
            period=8.0,
            direction=70,
            confidence=0.9,
            source="buoy"
        )
    )
    
    # Create forecast locations
    north_shore = ForecastLocation(
        name="Oahu North Shore",
        shore="North Shore",
        latitude=21.6639,
        longitude=-158.0529,
        facing_direction=0,  # North-facing
        metadata={
            "seasonal_factor": 0.9,  # Winter, good for North Shore
            "wind_factor": 0.8,
            "overall_quality": 0.85,
            "popular_breaks": ["Pipeline", "Sunset Beach", "Waimea Bay"],
            "wind_exposure": {
                "N": 0.2,   # Sheltered from north winds
                "NE": 0.3,  # Somewhat sheltered from NE trades
                "E": 0.5,   # Moderate exposure to east winds
                "SE": 0.7,  # More exposed to SE winds
                "S": 0.8,   # Exposed to south winds
                "SW": 0.9,  # Very exposed to SW winds (bad)
                "W": 0.7,   # Exposed to west winds
                "NW": 0.5   # Moderate exposure to NW winds
            }
        }
    )
    
    south_shore = ForecastLocation(
        name="Oahu South Shore",
        shore="South Shore",
        latitude=21.2749,
        longitude=-157.8238,
        facing_direction=180,  # South-facing
        metadata={
            "seasonal_factor": 0.3,  # Winter, not great for South Shore
            "wind_factor": 0.7,
            "overall_quality": 0.4,
            "popular_breaks": ["Waikiki", "Ala Moana", "Kewalos"],
            "wind_exposure": {
                "N": 0.8,   # Exposed to north winds
                "NE": 0.9,  # Very exposed to NE trades (bad)
                "E": 0.8,   # Exposed to east winds
                "SE": 0.6,  # Moderate exposure to SE winds
                "S": 0.3,   # Sheltered from south winds
                "SW": 0.2,  # Sheltered from SW winds (good)
                "W": 0.4,   # Somewhat sheltered from west winds
                "NW": 0.6   # Moderate exposure to NW winds
            }
        }
    )
    
    # Add events to locations with selective exposure
    north_shore.swell_events.append(event)  # North Shore gets the NW swell (primary)
    north_shore.swell_events.append(event3)  # North Shore gets some trade wind swell
    
    south_shore.swell_events.append(event2)  # South Shore gets the S swell (primary)
    # Small component of NW wrap
    small_wrap = SwellEvent(
        event_id="test_event_1_wrap",
        start_time=start_time,
        peak_time=peak_time,
        end_time=end_time,
        primary_direction=315,
        significance=0.2,  # Reduced significance due to wrapping
        hawaii_scale=2.0,  # Much smaller on south shore
        source="model",
        metadata={"wrapped": True, "parent_event_id": "test_event_1"}
    )
    south_shore.swell_events.append(small_wrap)
    
    # Create swell forecast
    forecast = SwellForecast(
        forecast_id="test_forecast",
        generated_time=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        metadata={
            "confidence": {
                "overall_score": 0.8,
                "factors": {
                    "data_freshness": 0.9,
                    "source_diversity": 0.7,
                    "source_agreement": 0.8,
                    "model_consistency": 0.75
                }
            },
            "weather": {
                "wind_direction": "ENE",
                "wind_speed": 15,  # knots
                "wind_gusts": 20,  # knots
                "temperature": 26,  # celsius
                "conditions": "Partly cloudy with occasional showers"
            },
            "tides": {
                "high_tide": [(now + timedelta(hours=4)).strftime("%H:%M"), 2.1],  # 2.1 feet at 4 hours from now
                "low_tide": [(now + timedelta(hours=10)).strftime("%H:%M"), 0.3]   # 0.3 feet at 10 hours from now
            }
        }
    )
    
    # Add events and locations to forecast
    forecast.swell_events.extend([event, event2, event3])
    forecast.locations.extend([north_shore, south_shore])
    
    return forecast


async def test_forecast_engine(config, logger):
    """Test the forecast engine."""
    logger.info("Testing forecast engine")
    
    # Create test forecast data
    swell_forecast = create_test_swell_forecast()
    
    # Create forecast engine
    engine = ForecastEngine(config)
    
    # Generate forecast
    logger.info("Generating forecast")
    forecast = await engine.generate_forecast(swell_forecast)
    
    # Check results
    if 'error' in forecast:
        logger.error(f"Forecast generation failed: {forecast['error']}")
        return False
    
    logger.info("Forecast generated successfully")
    
    # Validate forecast content
    logger.info("Validating forecast content")
    validation_results = validate_forecast_content(forecast, logger)
    
    if not validation_results['success']:
        logger.error(f"Forecast validation failed: {validation_results['reasons']}")
        return False
    
    logger.info("Forecast content validated successfully")
    logger.info(f"Content quality metrics: {validation_results['metrics']}")
    
    # Format forecast
    formatter = ForecastFormatter(config)
    
    logger.info("Formatting forecast")
    formatted = formatter.format_forecast(forecast)
    
    # Check results
    if 'error' in formatted:
        logger.error(f"Forecast formatting failed: {formatted['error']}")
        return False
    
    logger.info("Forecast formatted successfully")
    
    # Validate that all required output formats are present
    required_formats = config.get('forecast', 'formats', 'markdown,html').split(',')
    missing_formats = [fmt for fmt in required_formats if fmt not in formatted]
    
    if missing_formats:
        logger.error(f"Missing required output formats: {', '.join(missing_formats)}")
        return False
    
    # Validate file existence
    for fmt, path in formatted.items():
        if fmt != 'error' and not Path(path).exists():
            logger.error(f"Output file for {fmt} does not exist at path: {path}")
            return False
    
    logger.info(f"Output files generated successfully: {formatted}")
    
    # Check if additional validation is needed for PDF
    if 'pdf' in formatted and Path(formatted['pdf']).exists():
        logger.info("PDF output detected, performing additional validation")
        # This could be extended with PDF-specific checks if needed
    
    return True


async def main():
    """Main function."""
    # Load configuration
    config = load_config()
    
    # Set up logging
    logger = setup_logging(config)
    
    # Test forecast engine
    success = await test_forecast_engine(config, logger)
    
    if success:
        logger.info("Test completed successfully")
        return 0
    else:
        logger.error("Test failed")
        return 1


if __name__ == "__main__":
    asyncio.run(main())