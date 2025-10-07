"""
Data Fusion System for SurfCastAI.

This module integrates data from multiple sources (buoys, weather forecasts, wave models)
to create a unified view of current and forecasted surf conditions.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import json
from datetime import datetime, timedelta, timezone
import math
from statistics import mean, median, stdev
from collections import defaultdict

from .data_processor import DataProcessor, ProcessingResult
from .models.buoy_data import BuoyData, BuoyObservation
from .models.weather_data import WeatherData, WeatherPeriod
from .models.wave_model import ModelData, ModelForecast, ModelPoint
from .models.swell_event import SwellEvent, SwellComponent, SwellForecast, ForecastLocation
from .hawaii_context import HawaiiContext
from .source_scorer import SourceScorer
from .confidence_scorer import ConfidenceScorer
from ..core.config import Config


class DataFusionSystem(DataProcessor[Dict[str, Any], SwellForecast]):
    """
    System for fusing data from multiple sources into a unified surf forecast.
    
    Features:
    - Combines buoy observations, weather forecasts, and wave model data
    - Resolves conflicts between different data sources
    - Identifies and tracks swell events across sources
    - Generates a comprehensive surf forecast for different shores
    - Calculates confidence scores based on agreement between sources
    """
    
    def __init__(self, config: Config):
        """
        Initialize the data fusion system.

        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('processor.data_fusion')
        self.hawaii_context = HawaiiContext()
        self.source_scorer = SourceScorer()
        self.confidence_scorer = ConfidenceScorer()
    
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate input data for fusion.
        
        Args:
            data: Input data containing buoy, weather, and model data
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check for required sections
        required_keys = ['metadata']
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing {key} section in input data")
        
        # Check that at least one data source is provided
        if not any(k in data for k in ['buoy_data', 'weather_data', 'model_data']):
            errors.append("No data sources provided for fusion")
        
        return errors
    
    def process(self, data: Dict[str, Any]) -> ProcessingResult:
        """
        Process and fuse data from multiple sources.
        
        Args:
            data: Input data containing buoy, weather, and model data
            
        Returns:
            ProcessingResult with processed SwellForecast
        """
        try:
            # Extract metadata
            metadata = data.get('metadata', {})
            
            # Create forecast object
            forecast = SwellForecast(
                forecast_id=metadata.get('forecast_id', f"forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
                generated_time=datetime.now().isoformat(),
                metadata=metadata
            )
            
            # Add Hawaii locations
            self._add_hawaii_locations(forecast)
            
            # Extract and convert source data
            buoy_data = self._extract_buoy_data(data)
            weather_data = self._extract_weather_data(data)
            model_data = self._extract_model_data(data)
            metar_data = data.get('metar_data', [])
            tide_data = data.get('tide_data', [])
            tropical_data = data.get('tropical_data', [])
            chart_data = data.get('chart_data', [])

            # Score all data sources for reliability weighting
            self.logger.info("Scoring data sources for reliability weighting")
            source_scores = self.source_scorer.score_sources({
                'buoy_data': buoy_data,
                'weather_data': weather_data,
                'model_data': model_data
            })

            # Attach reliability scores and weights to data items
            self._attach_source_scores(buoy_data, weather_data, model_data, source_scores)

            # Store source scores in forecast metadata
            forecast.metadata['source_scores'] = {
                source_id: {
                    'overall_score': score.overall_score,
                    'tier': score.tier.name,
                    'tier_score': score.tier_score,
                    'freshness_score': score.freshness_score,
                    'completeness_score': score.completeness_score,
                    'accuracy_score': score.accuracy_score
                }
                for source_id, score in source_scores.items()
            }

            # Identify swell events from all sources
            swell_events = self._identify_swell_events(buoy_data, model_data)
            
            # Add events to forecast
            for event in swell_events:
                forecast.swell_events.append(event)
            
            # Calculate shore-specific impacts
            self._calculate_shore_impacts(forecast, weather_data)

            # Integrate supplemental datasets
            self._integrate_metar_data(forecast, metar_data)
            self._integrate_tide_data(forecast, tide_data)
            self._integrate_tropical_data(forecast, tropical_data)
            self._integrate_chart_data(forecast, chart_data)
            
            # Calculate confidence scores using new ConfidenceScorer
            self.logger.info("Calculating confidence scores")
            confidence_result = self.confidence_scorer.calculate_confidence(
                fusion_data={
                    'swell_events': forecast.swell_events,
                    'locations': forecast.locations,
                    'metadata': forecast.metadata,
                    'buoy_data': buoy_data,
                    'weather_data': weather_data,
                    'model_data': model_data
                },
                forecast_horizon_days=2  # Default 2-day forecast
            )

            # Update forecast metadata with confidence information
            forecast.metadata['confidence'] = {
                'overall_score': confidence_result.overall_score,
                'category': confidence_result.category.value,
                'factors': confidence_result.factors,
                'breakdown': confidence_result.breakdown
            }

            # Generate warnings based on confidence
            warnings = []
            if confidence_result.overall_score < 0.4:
                warnings.append(
                    "Very low forecast confidence due to poor data quality or high uncertainty"
                )
            elif confidence_result.overall_score < 0.6:
                warnings.append(
                    "Low forecast confidence - limited data or model disagreement present"
                )

            # Add specific factor warnings
            if confidence_result.factors['model_consensus'] < 0.5:
                warnings.append("Significant disagreement between model predictions")
            if confidence_result.factors['data_completeness'] < 0.5:
                warnings.append("Limited data sources available - missing expected data types")

            # Prepare metadata for result
            metadata = {
                'confidence': forecast.metadata['confidence'],
                'confidence_calculated_at': confidence_result.metadata['calculated_at']
            }
            
            return ProcessingResult(
                success=True,
                data=forecast,
                warnings=warnings,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Error in data fusion: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                error=f"Data fusion error: {str(e)}"
            )
    
    def _extract_buoy_data(self, data: Dict[str, Any]) -> List[BuoyData]:
        """
        Extract BuoyData objects from input data.
        
        Args:
            data: Input data dictionary
            
        Returns:
            List of BuoyData objects
        """
        buoy_data_list = []
        
        # Extract buoy data
        buoy_data_raw = data.get('buoy_data', [])
        
        # Convert to BuoyData objects if not already
        for buoy_item in buoy_data_raw:
            if isinstance(buoy_item, BuoyData):
                buoy_data_list.append(buoy_item)
            elif isinstance(buoy_item, dict):
                # Try to create BuoyData from dictionary
                # Use from_json which handles both raw NDBC and normalized formats
                try:
                    import json
                    buoy = BuoyData.from_json(json.dumps(buoy_item))
                    buoy_data_list.append(buoy)
                except Exception as e:
                    self.logger.warning(f"Failed to convert buoy data: {e}")
        
        return buoy_data_list
    
    def _extract_weather_data(self, data: Dict[str, Any]) -> List[WeatherData]:
        """
        Extract WeatherData objects from input data.
        
        Args:
            data: Input data dictionary
            
        Returns:
            List of WeatherData objects
        """
        weather_data_list = []
        
        # Extract weather data
        weather_data_raw = data.get('weather_data', [])
        
        # Convert to WeatherData objects if not already
        for weather_item in weather_data_raw:
            if isinstance(weather_item, WeatherData):
                weather_data_list.append(weather_item)
            elif isinstance(weather_item, dict):
                # Try to create WeatherData from dictionary
                try:
                    if 'properties' in weather_item:
                        # NWS format
                        weather = WeatherData.from_nws_json(weather_item)
                        weather_data_list.append(weather)
                    elif 'provider' in weather_item:
                        # Already in our format
                        weather = WeatherData.from_json(json.dumps(weather_item))
                        weather_data_list.append(weather)
                except Exception as e:
                    self.logger.warning(f"Failed to convert weather data: {e}")
        
        return weather_data_list
    
    def _extract_model_data(self, data: Dict[str, Any]) -> List[ModelData]:
        """
        Extract ModelData objects from input data.
        
        Args:
            data: Input data dictionary
            
        Returns:
            List of ModelData objects
        """
        model_data_list = []
        
        # Extract model data
        model_data_raw = data.get('model_data', [])
        
        # Convert to ModelData objects if not already
        for model_item in model_data_raw:
            if isinstance(model_item, ModelData):
                model_data_list.append(model_item)
            elif isinstance(model_item, dict):
                # Try to create ModelData from dictionary
                try:
                    if 'metadata' in model_item and 'forecasts' in model_item:
                        # SWAN format
                        model = ModelData.from_swan_json(model_item)
                        model_data_list.append(model)
                    elif 'header' in model_item and 'data' in model_item:
                        # WW3 format
                        model = ModelData.from_ww3_json(model_item)
                        model_data_list.append(model)
                    elif 'model_id' in model_item:
                        # Already in our format
                        model = ModelData.from_json(json.dumps(model_item))
                        model_data_list.append(model)
                except Exception as e:
                    self.logger.warning(f"Failed to convert model data: {e}")
        
        return model_data_list
    
    def _add_hawaii_locations(self, forecast: SwellForecast) -> None:
        """
        Add Hawaii-specific locations to the forecast.
        
        Args:
            forecast: Swell forecast to modify
        """
        # Add main Hawaiian shores
        shore_names = ['north_shore', 'south_shore', 'west_shore', 'east_shore']
        
        # Add all shores
        for shore_name in shore_names:
            location = self.hawaii_context.create_forecast_location(shore_name)
            if location:
                forecast.locations.append(location)
    
    def _identify_swell_events(self, buoy_data_list: List[BuoyData], 
                              model_data_list: List[ModelData]) -> List[SwellEvent]:
        """
        Identify swell events from multiple data sources.
        
        Args:
            buoy_data_list: List of buoy data
            model_data_list: List of model data
            
        Returns:
            List of identified swell events
        """
        swell_events = []
        
        # First, extract events from buoy data (current conditions)
        buoy_events = self._extract_buoy_events(buoy_data_list)
        swell_events.extend(buoy_events)
        
        # Then extract events from model data (forecasts)
        model_events = self._extract_model_events(model_data_list)
        
        # Merge similar events (from the same source type)
        model_events = self._merge_similar_events(model_events)
        swell_events.extend(model_events)
        
        # Sort events by time and significance
        swell_events.sort(key=lambda e: (
            e.start_time if e.start_time else e.peak_time,
            -e.significance
        ))
        
        return swell_events
    
    def _extract_buoy_events(self, buoy_data_list: List[BuoyData]) -> List[SwellEvent]:
        """
        Extract swell events from buoy data.
        
        Args:
            buoy_data_list: List of buoy data
            
        Returns:
            List of swell events
        """
        events = []
        
        for buoy_data in buoy_data_list:
            # Skip if no observations
            if not buoy_data.observations:
                continue
            
            # Use the latest observation for current conditions
            latest = buoy_data.latest_observation
            
            # Skip if missing critical data
            if not latest or latest.wave_height is None:
                continue
            
            # Create event from current buoy conditions
            event = SwellEvent(
                event_id=f"buoy_{buoy_data.station_id}_{datetime.now().strftime('%Y%m%d')}",
                start_time=latest.timestamp,
                peak_time=latest.timestamp,
                primary_direction=latest.wave_direction,
                significance=self._calculate_significance(latest.wave_height, latest.dominant_period),
                hawaii_scale=self._convert_to_hawaii_scale(latest.wave_height),
                source="buoy",
                metadata={
                    "station_id": buoy_data.station_id,
                    "buoy_name": buoy_data.name,
                    "confidence": 0.9,  # High confidence as this is observed data
                    "type": "observed",
                    "source_details": {
                        "buoy_id": buoy_data.station_id,
                        "observation_time": latest.timestamp,
                        "data_quality": "excellent" if latest.wave_height and latest.dominant_period else "good",
                        "source_type": "NDBC realtime"
                    }
                }
            )
            
            # Add primary component
            event.primary_components.append(SwellComponent(
                height=latest.wave_height or 0.0,
                period=latest.dominant_period or 0.0,
                direction=latest.wave_direction or 0.0,
                confidence=0.9,
                source="buoy"
            ))
            
            events.append(event)
        
        return events
    
    def _extract_model_events(self, model_data_list: List[ModelData]) -> List[SwellEvent]:
        """
        Extract swell events from model data.
        
        Args:
            model_data_list: List of model data
            
        Returns:
            List of swell events
        """
        events = []
        
        for model_data in model_data_list:
            # Skip if no forecasts
            if not model_data.forecasts:
                continue
            
            # Extract events from model metadata if available
            if 'swell_events' in model_data.metadata:
                model_events = model_data.metadata['swell_events']
                
                for event_data in model_events:
                    event = SwellEvent(
                        event_id=event_data.get('event_id', f"model_{model_data.model_id}_{len(events)}"),
                        start_time=event_data.get('start_time'),
                        peak_time=event_data.get('peak_time'),
                        end_time=event_data.get('end_time'),
                        primary_direction=event_data.get('peak_direction'),
                        significance=event_data.get('significance', 0.5),
                        hawaii_scale=event_data.get('hawaii_scale'),
                        source="model",
                        metadata={
                            "model_id": model_data.model_id,
                            "model_region": model_data.region,
                            "confidence": 0.7,  # Medium confidence as this is model data
                            "type": "forecast",
                            "peak_hour": event_data.get('peak_hour'),
                            "duration_hours": event_data.get('duration_hours')
                        }
                    )
                    
                    # Add primary component
                    if event_data.get('peak_height') is not None:
                        event.primary_components.append(SwellComponent(
                            height=event_data.get('peak_height'),
                            period=event_data.get('peak_period'),
                            direction=event_data.get('peak_direction'),
                            confidence=0.7,
                            source="model"
                        ))
                    
                    events.append(event)
            
            # If no pre-extracted events, try to identify them from forecast data
            elif len(events) == 0:
                # Simple approach: find the maximum wave height forecast
                max_height = 0
                max_forecast = None
                max_point = None
                
                for forecast in model_data.forecasts:
                    for point in forecast.points:
                        if point.wave_height > max_height:
                            max_height = point.wave_height
                            max_forecast = forecast
                            max_point = point
                
                if max_forecast and max_point and max_height > 0:
                    event = SwellEvent(
                        event_id=f"model_{model_data.model_id}_{datetime.now().strftime('%Y%m%d')}",
                        peak_time=max_forecast.timestamp,
                        primary_direction=max_point.wave_direction,
                        significance=self._calculate_significance(max_point.wave_height, max_point.wave_period),
                        hawaii_scale=self._convert_to_hawaii_scale(max_point.wave_height),
                        source="model",
                        metadata={
                            "model_id": model_data.model_id,
                            "model_region": model_data.region,
                            "confidence": 0.6,  # Lower confidence for simple extraction
                            "type": "forecast",
                            "forecast_hour": max_forecast.forecast_hour
                        }
                    )
                    
                    # Add primary component
                    event.primary_components.append(SwellComponent(
                        height=max_point.wave_height,
                        period=max_point.wave_period,
                        direction=max_point.wave_direction,
                        confidence=0.6,
                        source="model"
                    ))
                    
                    events.append(event)
        
        return events
    
    def _merge_similar_events(self, events: List[SwellEvent]) -> List[SwellEvent]:
        """
        Merge similar swell events.
        
        Args:
            events: List of swell events to merge
            
        Returns:
            List of merged events
        """
        if not events or len(events) <= 1:
            return events
        
        # Sort events by time
        events.sort(key=lambda e: e.peak_time if e.peak_time else "")
        
        merged_events = []
        current_event = events[0]
        
        for i in range(1, len(events)):
            next_event = events[i]
            
            # Check if events are from the same source and close in time
            if (current_event.source == next_event.source and 
                current_event.peak_time and next_event.peak_time):
                
                # Convert peak times to datetime
                try:
                    current_peak = datetime.fromisoformat(current_event.peak_time.replace('Z', '+00:00'))
                    next_peak = datetime.fromisoformat(next_event.peak_time.replace('Z', '+00:00'))
                    
                    # Check if peaks are within 24 hours
                    time_diff = abs((next_peak - current_peak).total_seconds()) / 3600
                    
                    # Check if directions are similar (within 45 degrees)
                    dir_diff = True
                    if current_event.primary_direction is not None and next_event.primary_direction is not None:
                        dir_diff = abs(current_event.primary_direction - next_event.primary_direction)
                        if dir_diff > 180:
                            dir_diff = 360 - dir_diff
                        dir_diff = dir_diff <= 45
                    
                    # Merge if time and direction are close
                    if time_diff <= 24 and dir_diff:
                        # Use the event with higher significance
                        if next_event.significance > current_event.significance:
                            current_event = next_event
                        continue
                except (ValueError, TypeError):
                    pass
            
            # If not merged, add current event and move to next
            merged_events.append(current_event)
            current_event = next_event
        
        # Add the last event
        merged_events.append(current_event)
        
        return merged_events
    
    def _integrate_metar_data(self, forecast: SwellForecast, metar_entries: List[Dict[str, Any]]):
        """Populate forecast metadata with latest METAR observations."""
        if not metar_entries:
            return
        latest = None
        latest_time = None
        for entry in metar_entries:
            issued = self._safe_parse_iso(entry.get('issued'))
            if issued is None:
                continue
            if latest_time is None or issued > latest_time:
                latest = entry
                latest_time = issued
        if not latest:
            return
        weather_meta = forecast.metadata.setdefault('weather', {})
        weather_meta['metar_station'] = latest.get('station')
        weather_meta['metar_issued'] = latest.get('issued')
        if latest.get('wind_direction_deg') is not None:
            weather_meta['wind_direction'] = latest['wind_direction_deg']
        if latest.get('wind_speed_ms') is not None:
            weather_meta['wind_speed_ms'] = latest['wind_speed_ms']
        if latest.get('wind_gust_ms') is not None:
            weather_meta['wind_gust_ms'] = latest['wind_gust_ms']
        if latest.get('temperature_c') is not None:
            weather_meta['temperature'] = latest['temperature_c']
        if latest.get('pressure_hpa') is not None:
            weather_meta['pressure_hpa'] = latest['pressure_hpa']
        weather_meta['metar'] = latest

    def _integrate_tide_data(self, forecast: SwellForecast, tide_entries: List[Dict[str, Any]]):
        """Build tide summary including upcoming highs/lows and latest observations."""
        if not tide_entries:
            return
        predictions = [entry for entry in tide_entries if entry.get('product') == 'predictions']
        water_levels = [entry for entry in tide_entries if entry.get('product') != 'predictions']
        tide_metadata: Dict[str, Any] = {}
        if predictions:
            record = predictions[0]
            units = record.get('units', 'metric')
            highs, lows = self._extract_tide_extrema(record.get('records', []), units)
            if highs:
                tide_metadata['high_tide'] = highs
            if lows:
                tide_metadata['low_tide'] = lows
            tide_metadata['station'] = record.get('station')
        if water_levels:
            latest_obs = self._select_latest_tide_observation(water_levels[0].get('records', []))
            if latest_obs:
                tide_metadata['latest_water_level'] = latest_obs
        if tide_metadata:
            forecast.metadata['tides'] = tide_metadata

    def _integrate_tropical_data(self, forecast: SwellForecast, tropical_entries: List[Dict[str, Any]]):
        """Attach tropical outlook headline and entries."""
        if not tropical_entries:
            return
        outlook = tropical_entries[0]
        forecast.metadata['tropical'] = {
            'headline': outlook.get('headline'),
            'entries': outlook.get('entries', [])
        }

    def _integrate_chart_data(self, forecast: SwellForecast, chart_entries: List[Dict[str, Any]]):
        """Reference downloaded analysis charts for downstream consumers."""
        charts = []
        for entry in chart_entries:
            file_path = entry.get('file_path') or entry.get('manifest_path')
            if not file_path:
                continue
            charts.append({
                'type': entry.get('chart_type'),
                'file_path': file_path,
                'source_url': entry.get('source_url')
            })
        if charts:
            forecast.metadata['charts'] = charts

    def _extract_tide_extrema(self, records: List[Dict[str, Any]], units: str) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
        points: List[Tuple[str, float]] = []
        for row in records:
            value = row.get('Prediction') or row.get('Water Level') or row.get('WaterLevel')
            time_str = row.get('Date Time') or row.get('Time') or row.get('Time (GMT)') or row.get('t')
            height = self._safe_float(value)
            if height is None or time_str is None:
                continue
            height_ft = round(height * 3.28084, 2) if units == 'metric' else round(height, 2)
            iso = self._parse_time_guess(time_str)
            points.append((iso, height_ft))
        if not points:
            return [], []
        highs_sorted = sorted(points, key=lambda item: item[1], reverse=True)[:3]
        lows_sorted = sorted(points, key=lambda item: item[1])[:3]
        return highs_sorted, lows_sorted

    def _select_latest_tide_observation(self, records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        latest = None
        latest_time = None
        for row in records:
            time_str = row.get('Date Time') or row.get('Time') or row.get('t')
            value = row.get('Water Level') or row.get('WaterLevel') or row.get('Observation')
            height = self._safe_float(value)
            if time_str is None or height is None:
                continue
            iso = self._parse_time_guess(time_str)
            dt = self._safe_parse_iso(iso)
            if dt is None:
                continue
            if latest is None or dt > latest_time:
                latest = {
                    'time': iso,
                    'height_ft': round(height * 3.28084, 2)
                }
                latest_time = dt
        return latest

    def _safe_parse_iso(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            if value.endswith('Z'):
                value = value.replace('Z', '+00:00')
            return datetime.fromisoformat(value)
        except Exception:
            return None

    def _parse_time_guess(self, value: str) -> str:
        patterns = ['%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M']
        for pattern in patterns:
            try:
                dt = datetime.strptime(value, pattern)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat().replace('+00:00', 'Z')
            except ValueError:
                continue
        return value

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _calculate_shore_impacts(self, forecast: SwellForecast, 
                                weather_data: List[WeatherData]) -> None:
        """
        Calculate shore-specific impacts of swell events.
        
        Args:
            forecast: Swell forecast to modify
            weather_data: List of weather data for wind impact
        """
        # For each location, calculate which swell events affect it
        for location in forecast.locations:
            shore_name = location.shore.lower().replace(' ', '_')
            
            # Clear existing swell events
            location.swell_events = []
            
            # Get seasonal factor
            seasonal_factor = self.hawaii_context.get_seasonal_factor(shore_name)
            
            # Calculate exposure to each swell event
            for event in forecast.swell_events:
                # Skip if no direction
                if event.primary_direction is None:
                    continue
                
                # Check if location is exposed to this swell direction
                exposure_factor = self.hawaii_context.get_exposure_factor(
                    shore_name, event.primary_direction
                )
                
                if exposure_factor > 0.0:
                    # Location is exposed to this swell, add it
                    location.swell_events.append(event)
                    
                    # Add exposure factor to event metadata for this location
                    event_metadata = event.metadata.copy()
                    event_metadata[f'exposure_{shore_name}'] = exposure_factor
                    event.metadata = event_metadata
            
            # Calculate wind impact if weather data available
            wind_factor = self._calculate_wind_factor(shore_name, weather_data)
            
            # Set location metadata
            location.metadata.update({
                'seasonal_factor': seasonal_factor,
                'wind_factor': wind_factor,
                'overall_quality': self._calculate_overall_quality(
                    shore_name, seasonal_factor, wind_factor, location.swell_events
                )
            })
    
    def _calculate_wind_factor(self, shore_name: str, weather_data: List[WeatherData]) -> float:
        """
        Calculate wind impact factor for a specific shore.
        
        Args:
            shore_name: Name of the shore
            weather_data: List of weather data
            
        Returns:
            Wind impact factor (0-1)
        """
        if not weather_data:
            return 0.5  # Neutral if no data
        
        # Find the most relevant weather data (closest to shore)
        shore = self.hawaii_context.get_shore_data(shore_name)
        if not shore:
            return 0.5
        
        # Calculate minimum distance to weather location
        min_distance = float('inf')
        best_weather = None
        
        for weather in weather_data:
            if weather.latitude is not None and weather.longitude is not None:
                distance = self._haversine_distance(
                    shore.latitude, shore.longitude,
                    weather.latitude, weather.longitude
                )
                
                if distance < min_distance:
                    min_distance = distance
                    best_weather = weather
        
        # If no suitable weather data found
        if not best_weather:
            return 0.5
        
        # Check if wind analysis is available
        wind_analysis = best_weather.metadata.get('wind_analysis', {})
        shore_impacts = wind_analysis.get('shore_impacts', {})
        
        # Get shore-specific impact
        shore_impact = shore_impacts.get(shore_name, {})
        overall_rating = shore_impact.get('overall_rating', 0.5)
        
        return overall_rating
    
    def _calculate_overall_quality(self, shore_name: str, seasonal_factor: float, 
                                  wind_factor: float, events: List[SwellEvent]) -> float:
        """
        Calculate overall surf quality for a specific shore.
        
        Args:
            shore_name: Name of the shore
            seasonal_factor: Seasonal quality factor
            wind_factor: Wind impact factor
            events: List of swell events affecting the shore
            
        Returns:
            Overall quality factor (0-1)
        """
        # Start with base quality from season
        quality = seasonal_factor * 0.3
        
        # Add wind factor (40% weight)
        quality += wind_factor * 0.4
        
        # Add swell factor (30% weight)
        if events:
            # Find the most significant event
            max_event = max(events, key=lambda e: e.significance)
            
            # Get exposure factor for this shore
            exposure_factor = max_event.metadata.get(f'exposure_{shore_name}', 0.5)
            
            # Calculate swell factor
            swell_factor = max_event.significance * exposure_factor
            quality += swell_factor * 0.3
        
        # Ensure result is between 0 and 1
        return max(0.0, min(1.0, quality))
    
    def _calculate_significance(self, height: Optional[float], period: Optional[float]) -> float:
        """
        Calculate significance score for a swell.
        
        Args:
            height: Wave height in meters
            period: Wave period in seconds
            
        Returns:
            Significance score (0-1)
        """
        if height is None:
            return 0.0
        
        # Base significance on height
        significance = min(1.0, height / 5.0)  # 5m (16.4ft) or higher is max significance
        
        # Adjust for period if available
        if period is not None:
            # Long period swells are more significant
            period_factor = min(1.5, period / 10.0)  # Periods >10s increase significance
            significance *= period_factor
        
        # Ensure result is between 0 and 1
        return min(1.0, significance)
    
    def _convert_to_hawaii_scale(self, meters: Optional[float]) -> Optional[float]:
        """
        Convert wave height from meters to Hawaiian scale.
        
        Hawaiian scale measures wave height from the back of the wave,
        approximately equal to the significant wave height (not face height).
        Face height is typically 1.5-2x the Hawaiian scale.
        
        Args:
            meters: Significant wave height in meters
            
        Returns:
            Wave height in Hawaiian scale (feet) or None if input is None
        """
        if meters is None:
            return None
        
        # Hawaiian scale ≈ Hs in feet (back height)
        # DO NOT multiply by 2 - that would give face height
        return meters * 3.28084  # 1m = 3.28084ft  # 1m = 3.28084ft
    
    def _attach_source_scores(
        self,
        buoy_data: List[BuoyData],
        weather_data: List[WeatherData],
        model_data: List[ModelData],
        source_scores: Dict[str, Any]
    ) -> None:
        """
        Attach reliability scores and weights to data items.

        This enables downstream processing to use weighted fusion
        based on source reliability.

        Args:
            buoy_data: List of buoy data
            weather_data: List of weather data
            model_data: List of model data
            source_scores: Dictionary of source scores from SourceScorer
        """
        # Attach scores to buoy data
        for buoy in buoy_data:
            source_id = self._get_source_id_from_data(buoy, 'buoy')
            if source_id in source_scores:
                score = source_scores[source_id]
                buoy.metadata = buoy.metadata or {}
                buoy.metadata['reliability_score'] = score.overall_score
                buoy.metadata['source_tier'] = score.tier.name
                buoy.metadata['weight'] = score.overall_score  # Weight for fusion

        # Attach scores to weather data
        for weather in weather_data:
            source_id = self._get_source_id_from_data(weather, 'weather')
            if source_id in source_scores:
                score = source_scores[source_id]
                weather.metadata = weather.metadata or {}
                weather.metadata['reliability_score'] = score.overall_score
                weather.metadata['source_tier'] = score.tier.name
                weather.metadata['weight'] = score.overall_score

        # Attach scores to model data
        for model in model_data:
            source_id = self._get_source_id_from_data(model, 'model')
            if source_id in source_scores:
                score = source_scores[source_id]
                model.metadata = model.metadata or {}
                model.metadata['reliability_score'] = score.overall_score
                model.metadata['source_tier'] = score.tier.name
                model.metadata['weight'] = score.overall_score

        self.logger.info(
            f"Attached reliability scores to {len(buoy_data)} buoy, "
            f"{len(weather_data)} weather, {len(model_data)} model sources"
        )

    def _get_source_id_from_data(self, data: Any, data_type: str) -> str:
        """
        Extract source identifier from data object.

        Args:
            data: Data object
            data_type: Type of data (buoy, weather, model)

        Returns:
            Source identifier string
        """
        # Try common source identifier fields
        for field in ['source', 'source_name', 'provider', 'station_id',
                     'model_id', 'buoy_id', 'name']:
            if hasattr(data, field):
                value = getattr(data, field)
                if value:
                    return str(value)

        return f"{data_type}_unknown"

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate Haversine distance between two points in kilometers.

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of Earth in kilometers

        return c * r