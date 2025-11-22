"""
Wave model data processor for SurfCastAI.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import json
from datetime import datetime, timedelta
import math
from statistics import mean, median
import numpy as np
from collections import defaultdict

from .data_processor import DataProcessor, ProcessingResult
from .models.wave_model import ModelData, ModelForecast, ModelPoint
from .hawaii_context import HawaiiContext
from ..core.config import Config


class WaveModelProcessor(DataProcessor[Dict[str, Any], ModelData]):
    """
    Processor for wave model data.

    Features:
    - Converts raw model data to standardized ModelData model
    - Validates data completeness and consistency
    - Analyzes wave patterns and trends across forecast periods
    - Provides geographic filtering and location-specific analysis
    - Detects significant swell events in the forecast
    """

    def __init__(self, config: Config):
        """
        Initialize the wave model processor.

        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('processor.wave_model')
        self.hawaii_context = HawaiiContext()

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate wave model data.

        Args:
            data: Raw wave model data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for required fields based on model type
        if 'model_id' in data:
            # Already in ModelData format
            if 'forecasts' not in data or not data['forecasts']:
                errors.append("Missing or empty forecasts field")

        elif 'metadata' in data and 'forecasts' in data:
            # SWAN format
            if not data['forecasts']:
                errors.append("No forecast time steps in SWAN data")

            # Check first forecast for points
            if data['forecasts'] and ('points' not in data['forecasts'][0] or not data['forecasts'][0]['points']):
                errors.append("No grid points in SWAN forecast data")

        elif 'header' in data and 'data' in data:
            # WW3 format
            if not data['data']:
                errors.append("No forecast time steps in WW3 data")

            # Check first time step for grid
            if data['data'] and ('grid' not in data['data'][0] or not data['data'][0]['grid']):
                errors.append("No grid points in WW3 forecast data")

        else:
            errors.append("Unknown wave model data format")

        return errors

    def process(self, data: Dict[str, Any]) -> ProcessingResult:
        """
        Process wave model data.

        Args:
            data: Raw wave model data

        Returns:
            ProcessingResult with processed ModelData
        """
        try:
            # Convert to ModelData if not already
            if isinstance(data, ModelData):
                model_data = data
            elif 'model_id' in data:
                # Data is already in our internal format, convert directly
                model_data = ModelData.from_json(json.dumps(data))
            elif 'metadata' in data and 'forecasts' in data:
                # SWAN format
                model_data = ModelData.from_swan_json(data)
            elif 'header' in data and 'data' in data:
                # WW3 format
                model_data = ModelData.from_ww3_json(data)
            else:
                return ProcessingResult(
                    success=False,
                    error="Unsupported wave model data format"
                )

            # Check if we have any forecasts
            if not model_data.forecasts:
                return ProcessingResult(
                    success=False,
                    error="No forecast time steps found in model data",
                    data=model_data
                )

            # Clean and normalize data
            model_data = self._clean_forecasts(model_data)

            # Analyze model data
            warnings, metadata = self._analyze_model_data(model_data)

            # Add metadata from analysis
            model_data.metadata.update(metadata)

            # Analyze data for Hawaii-specific shores
            shore_analysis = self._analyze_hawaii_shores(model_data)
            model_data.metadata['shore_analysis'] = shore_analysis

            # Detect potential swell events
            swell_events = self._detect_swell_events(model_data)
            model_data.metadata['swell_events'] = swell_events

            return ProcessingResult(
                success=True,
                data=model_data,
                warnings=warnings,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error processing wave model data: {e}")
            return ProcessingResult(
                success=False,
                error=f"Processing error: {str(e)}"
            )

    def _clean_forecasts(self, model_data: ModelData) -> ModelData:
        """
        Clean and normalize model forecasts.

        Args:
            model_data: Original model data

        Returns:
            Cleaned model data
        """
        # Filter out forecasts with no points
        valid_forecasts = []
        for forecast in model_data.forecasts:
            if not forecast.points:
                continue

            # Clean points in this forecast
            valid_points = []
            for point in forecast.points:
                # Skip points with no wave height
                if point.wave_height is None or point.wave_height <= 0:
                    continue

                # Clean up invalid values
                if point.wave_period is not None and point.wave_period <= 0:
                    point.wave_period = None

                if point.wave_direction is not None and (point.wave_direction < 0 or point.wave_direction > 360):
                    point.wave_direction = None

                valid_points.append(point)

            # Skip forecast if no valid points
            if not valid_points:
                continue

            # Update forecast with cleaned points
            forecast.points = valid_points
            valid_forecasts.append(forecast)

        # Sort forecasts by forecast hour
        valid_forecasts.sort(key=lambda f: f.forecast_hour)

        # Update model data with cleaned forecasts
        model_data.forecasts = valid_forecasts

        return model_data

    def _analyze_model_data(self, model_data: ModelData) -> Tuple[List[str], Dict[str, Any]]:
        """
        Analyze wave model data for quality and patterns.

        Args:
            model_data: Model data to analyze

        Returns:
            Tuple of (warnings, metadata)
        """
        warnings = []
        metadata = {
            'analysis': {
                'timestamp': datetime.now().isoformat(),
                'quality_score': 1.0,
                'forecast_range_hours': None,
                'trends': {},
                'max_conditions': {},
                'data_stats': {}
            }
        }

        # Check data freshness
        try:
            run_time = datetime.fromisoformat(model_data.run_time.replace('Z', '+00:00'))
            now = datetime.now(run_time.tzinfo)
            hours_old = (now - run_time).total_seconds() / 3600

            metadata['analysis']['hours_since_update'] = hours_old

            if hours_old > 12:
                warnings.append(f"Model data is {hours_old:.1f} hours old")
                metadata['analysis']['quality_score'] -= min(0.5, hours_old / 48)
        except (ValueError, TypeError):
            warnings.append("Could not parse model run timestamp")

        # Calculate forecast range
        if len(model_data.forecasts) >= 2:
            min_hour = min(f.forecast_hour for f in model_data.forecasts)
            max_hour = max(f.forecast_hour for f in model_data.forecasts)
            metadata['analysis']['forecast_range_hours'] = max_hour - min_hour

        # Analyze wave height trends over forecast period
        height_trend_data = self._analyze_wave_height_trend(model_data)
        metadata['analysis']['trends']['wave_height'] = height_trend_data

        # Analyze wave period trends
        period_trend_data = self._analyze_wave_period_trend(model_data)
        metadata['analysis']['trends']['wave_period'] = period_trend_data

        # Find maximum conditions across all forecasts
        max_conditions = self._find_max_conditions(model_data)
        metadata['analysis']['max_conditions'] = max_conditions

        # Calculate overall data statistics
        data_stats = self._calculate_data_statistics(model_data)
        metadata['analysis']['data_stats'] = data_stats

        # Set special flags
        special_conditions = []

        # Check for large swell
        if max_conditions.get('max_height', 0) > 3.0:  # 3m ~ 10ft
            special_conditions.append("large_swell_forecast")

        # Check for long period swell
        if max_conditions.get('max_period', 0) > 15.0:
            special_conditions.append("long_period_swell_forecast")

        metadata['analysis']['special_conditions'] = special_conditions

        return warnings, metadata

    def _analyze_wave_height_trend(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Analyze wave height trends across forecast periods.

        Args:
            model_data: Model data to analyze

        Returns:
            Trend analysis data
        """
        trend_data = {
            'increasing': False,
            'decreasing': False,
            'stable': False,
            'peaking': False,
            'values': []
        }

        # Extract average wave heights for each forecast hour
        heights_by_hour = []
        for forecast in model_data.forecasts:
            if forecast.points:
                avg_height = sum(p.wave_height for p in forecast.points if p.wave_height is not None) / len(forecast.points)
                heights_by_hour.append((forecast.forecast_hour, avg_height))

        # Sort by forecast hour
        heights_by_hour.sort(key=lambda x: x[0])

        # Extract just the heights for trend analysis
        heights = [h[1] for h in heights_by_hour]
        trend_data['values'] = heights

        # Need at least 3 points for trend analysis
        if len(heights) >= 3:
            # Calculate trend
            first_third = heights[:len(heights)//3]
            last_third = heights[-len(heights)//3:]

            first_avg = sum(first_third) / len(first_third)
            last_avg = sum(last_third) / len(last_third)

            # Determine trend type
            if last_avg > first_avg * 1.25:
                trend_data['increasing'] = True
            elif first_avg > last_avg * 1.25:
                trend_data['decreasing'] = True
            else:
                trend_data['stable'] = True

            # Check for peak pattern
            middle_third = heights[len(heights)//3:-len(heights)//3]
            if middle_third:
                middle_max = max(middle_third)
                if middle_max > max(first_avg, last_avg) * 1.25:
                    trend_data['peaking'] = True

        return trend_data

    def _analyze_wave_period_trend(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Analyze wave period trends across forecast periods.

        Args:
            model_data: Model data to analyze

        Returns:
            Trend analysis data
        """
        trend_data = {
            'increasing': False,
            'decreasing': False,
            'stable': False,
            'values': []
        }

        # Extract average wave periods for each forecast hour
        periods_by_hour = []
        for forecast in model_data.forecasts:
            valid_periods = [p.wave_period for p in forecast.points if p.wave_period is not None]
            if valid_periods:
                avg_period = sum(valid_periods) / len(valid_periods)
                periods_by_hour.append((forecast.forecast_hour, avg_period))

        # Sort by forecast hour
        periods_by_hour.sort(key=lambda x: x[0])

        # Extract just the periods for trend analysis
        periods = [p[1] for p in periods_by_hour]
        trend_data['values'] = periods

        # Need at least 3 points for trend analysis
        if len(periods) >= 3:
            # Calculate trend
            first_third = periods[:len(periods)//3]
            last_third = periods[-len(periods)//3:]

            first_avg = sum(first_third) / len(first_third)
            last_avg = sum(last_third) / len(last_third)

            # Determine trend type
            if last_avg > first_avg * 1.15:
                trend_data['increasing'] = True
            elif first_avg > last_avg * 1.15:
                trend_data['decreasing'] = True
            else:
                trend_data['stable'] = True

        return trend_data

    def _find_max_conditions(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Find maximum wave conditions across all forecasts.

        Args:
            model_data: Model data to analyze

        Returns:
            Dictionary with maximum conditions
        """
        max_conditions = {
            'max_height': 0,
            'max_period': 0,
            'max_height_hour': None,
            'max_period_hour': None
        }

        for forecast in model_data.forecasts:
            # Find max height in this forecast
            heights = [p.wave_height for p in forecast.points if p.wave_height is not None]
            if heights:
                max_height = max(heights)
                if max_height > max_conditions['max_height']:
                    max_conditions['max_height'] = max_height
                    max_conditions['max_height_hour'] = forecast.forecast_hour

            # Find max period in this forecast
            periods = [p.wave_period for p in forecast.points if p.wave_period is not None]
            if periods:
                max_period = max(periods)
                if max_period > max_conditions['max_period']:
                    max_conditions['max_period'] = max_period
                    max_conditions['max_period_hour'] = forecast.forecast_hour

        return max_conditions

    def _calculate_data_statistics(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Calculate overall statistics for model data.

        Args:
            model_data: Model data to analyze

        Returns:
            Dictionary with statistics
        """
        stats = {
            'forecast_count': len(model_data.forecasts),
            'total_points': 0,
            'height_stats': {},
            'period_stats': {},
            'direction_stats': {}
        }

        # Collect all values
        all_heights = []
        all_periods = []
        all_directions = []

        for forecast in model_data.forecasts:
            stats['total_points'] += len(forecast.points)

            for point in forecast.points:
                if point.wave_height is not None:
                    all_heights.append(point.wave_height)

                if point.wave_period is not None:
                    all_periods.append(point.wave_period)

                if point.wave_direction is not None:
                    all_directions.append(point.wave_direction)

        # Calculate height statistics
        if all_heights:
            stats['height_stats'] = {
                'min': min(all_heights),
                'max': max(all_heights),
                'mean': sum(all_heights) / len(all_heights),
                'median': sorted(all_heights)[len(all_heights) // 2],
                'count': len(all_heights)
            }

        # Calculate period statistics
        if all_periods:
            stats['period_stats'] = {
                'min': min(all_periods),
                'max': max(all_periods),
                'mean': sum(all_periods) / len(all_periods),
                'median': sorted(all_periods)[len(all_periods) // 2],
                'count': len(all_periods)
            }

        # Calculate direction statistics (circular data)
        if all_directions:
            # Convert to radians for circular statistics
            rad_directions = [math.radians(d) for d in all_directions]

            # Calculate mean direction using vector approach
            sin_sum = sum(math.sin(r) for r in rad_directions)
            cos_sum = sum(math.cos(r) for r in rad_directions)
            mean_rad = math.atan2(sin_sum, cos_sum)
            mean_deg = (math.degrees(mean_rad) + 360) % 360

            # Calculate direction spread
            unique_directions = len(set([round(d / 10) * 10 for d in all_directions]))

            stats['direction_stats'] = {
                'mean': mean_deg,
                'count': len(all_directions),
                'unique_sectors': unique_directions
            }

        return stats

    def _analyze_hawaii_shores(self, model_data: ModelData) -> Dict[str, Any]:
        """
        Analyze model data impact on Hawaii shores.

        Args:
            model_data: Model data to analyze

        Returns:
            Dictionary with shore-specific analysis
        """
        shore_analysis = {}

        # Get all shores
        shores = self.hawaii_context.get_all_shores()

        # For each shore, calculate impact
        for shore in shores:
            shore_name = shore.name.lower().replace(' ', '_')
            shore_data = {
                'impact_score': 0.0,
                'max_height': 0.0,
                'optimal_direction_match': 0.0,
                'forecast_quality': []
            }

            # For each forecast, calculate shore-specific metrics
            forecast_impacts = []
            for forecast in model_data.forecasts:
                # Find points close to this shore
                shore_points = self._find_points_near_shore(forecast.points, shore.latitude, shore.longitude)

                if not shore_points:
                    continue

                # Calculate average wave conditions
                avg_height = sum(p.wave_height for p in shore_points if p.wave_height is not None) / len(shore_points)

                # Get average direction if available
                directions = [p.wave_direction for p in shore_points if p.wave_direction is not None]
                avg_direction = None
                if directions:
                    # Convert to radians for circular mean
                    rad_directions = [math.radians(d) for d in directions]
                    sin_sum = sum(math.sin(r) for r in rad_directions)
                    cos_sum = sum(math.cos(r) for r in rad_directions)
                    mean_rad = math.atan2(sin_sum, cos_sum)
                    avg_direction = (math.degrees(mean_rad) + 360) % 360

                # Calculate exposure factor based on direction
                exposure_factor = 0.5  # Default mid-range
                if avg_direction is not None:
                    exposure_factor = self.hawaii_context.get_exposure_factor(shore_name, avg_direction)

                # Calculate seasonal factor
                seasonal_factor = self.hawaii_context.get_seasonal_factor(shore_name)

                # Calculate overall impact for this forecast
                impact = avg_height * exposure_factor * seasonal_factor

                # Track forecast quality
                forecast_impacts.append({
                    'hour': forecast.forecast_hour,
                    'height': avg_height,
                    'direction': avg_direction,
                    'exposure_factor': exposure_factor,
                    'seasonal_factor': seasonal_factor,
                    'impact': impact
                })

                # Update maximum values
                shore_data['max_height'] = max(shore_data['max_height'], avg_height)

                # Check for optimal direction match
                if avg_direction is not None:
                    for range_tuple in shore.quality_directions:
                        if self.hawaii_context.is_in_range(avg_direction, range_tuple):
                            shore_data['optimal_direction_match'] = max(
                                shore_data['optimal_direction_match'],
                                exposure_factor
                            )

            # Calculate overall impact score (average of top forecasts)
            if forecast_impacts:
                # Sort by impact
                forecast_impacts.sort(key=lambda x: x['impact'], reverse=True)

                # Take average of top 3 or all if fewer
                top_impacts = forecast_impacts[:min(3, len(forecast_impacts))]
                shore_data['impact_score'] = sum(f['impact'] for f in top_impacts) / len(top_impacts)

                # Add forecast quality data (but limit to avoid excess data)
                shore_data['forecast_quality'] = forecast_impacts[:12]  # First 12 forecasts

            # Add to overall analysis
            shore_analysis[shore_name] = shore_data

        return shore_analysis

    def _find_points_near_shore(self, points: List[ModelPoint], shore_lat: float, shore_lon: float,
                               max_distance_km: float = 50.0) -> List[ModelPoint]:
        """
        Find model points near a specific shore.

        Args:
            points: List of model points
            shore_lat: Shore latitude
            shore_lon: Shore longitude
            max_distance_km: Maximum distance in kilometers

        Returns:
            List of points near the shore
        """
        near_points = []

        for point in points:
            # Calculate distance using Haversine formula
            distance = self._haversine_distance(
                shore_lat, shore_lon,
                point.latitude, point.longitude
            )

            if distance <= max_distance_km:
                near_points.append(point)

        return near_points

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

    def _detect_swell_events(self, model_data: ModelData) -> List[Dict[str, Any]]:
        """
        Detect potential swell events in the forecast.

        Args:
            model_data: Model data to analyze

        Returns:
            List of detected swell events
        """
        swell_events = []

        # Need enough forecasts for event detection
        if len(model_data.forecasts) < 3:
            return swell_events

        # Organize forecasts by time
        forecasts_by_time = sorted(model_data.forecasts, key=lambda f: f.forecast_hour)

        # Track wave heights over time for event detection
        heights_by_time = []
        for forecast in forecasts_by_time:
            if forecast.points:
                avg_height = sum(p.wave_height for p in forecast.points if p.wave_height is not None) / len(forecast.points)
                heights_by_time.append((forecast.forecast_hour, forecast.timestamp, avg_height))

        # Find peaks in wave height
        peaks = self._find_peaks(heights_by_time)

        # For each peak, create a swell event
        for peak_idx, peak_data in enumerate(peaks):
            peak_hour, peak_time, peak_height = peak_data

            # Find forecast at peak time
            peak_forecast = next((f for f in forecasts_by_time if f.forecast_hour == peak_hour), None)
            if not peak_forecast:
                continue

            # Get average direction at peak
            directions = [p.wave_direction for p in peak_forecast.points if p.wave_direction is not None]
            avg_direction = None
            if directions:
                # Convert to radians for circular mean
                rad_directions = [math.radians(d) for d in directions]
                sin_sum = sum(math.sin(r) for r in rad_directions)
                cos_sum = sum(math.cos(r) for r in rad_directions)
                mean_rad = math.atan2(sin_sum, cos_sum)
                avg_direction = (math.degrees(mean_rad) + 360) % 360

            # Get average period at peak
            periods = [p.wave_period for p in peak_forecast.points if p.wave_period is not None]
            avg_period = sum(periods) / len(periods) if periods else None

            # Create event
            event = {
                'event_id': f"swell_{model_data.model_id}_{peak_idx+1}",
                'peak_time': peak_time,
                'peak_hour': peak_hour,
                'peak_height': peak_height,
                'peak_period': avg_period,
                'peak_direction': avg_direction,
                'significance': self._calculate_swell_significance(peak_height, avg_period),
                'hawaii_scale': self.get_hawaii_scale(peak_height) if peak_height else None
            }

            # Find start and end times for event
            # Start at first point where height is >50% of peak
            start_idx = 0
            while start_idx < len(heights_by_time) and heights_by_time[start_idx][2] < peak_height * 0.5:
                start_idx += 1

            # End at last point where height is >50% of peak
            end_idx = len(heights_by_time) - 1
            while end_idx >= 0 and heights_by_time[end_idx][2] < peak_height * 0.5:
                end_idx -= 1

            # Add start/end times if found
            if start_idx < len(heights_by_time):
                event['start_time'] = heights_by_time[start_idx][1]
                event['start_hour'] = heights_by_time[start_idx][0]

            if end_idx >= 0:
                event['end_time'] = heights_by_time[end_idx][1]
                event['end_hour'] = heights_by_time[end_idx][0]

            # Calculate duration if possible
            if 'start_hour' in event and 'end_hour' in event:
                event['duration_hours'] = event['end_hour'] - event['start_hour']

            swell_events.append(event)

        # Sort events by significance
        swell_events.sort(key=lambda e: e.get('significance', 0), reverse=True)

        return swell_events

    def _find_peaks(self, heights_by_time: List[Tuple[int, str, float]]) -> List[Tuple[int, str, float]]:
        """
        Find peaks in wave height time series.

        Args:
            heights_by_time: List of (hour, time, height) tuples

        Returns:
            List of peak (hour, time, height) tuples
        """
        if not heights_by_time or len(heights_by_time) < 3:
            return []

        peaks = []
        heights = [h[2] for h in heights_by_time]

        # Find local maxima
        for i in range(1, len(heights) - 1):
            if heights[i] > heights[i-1] and heights[i] > heights[i+1]:
                # Check if peak is significant (>20% higher than surrounding average)
                surrounding_avg = (heights[i-1] + heights[i+1]) / 2
                if heights[i] > surrounding_avg * 1.2:
                    peaks.append(heights_by_time[i])

        # If no peaks found, just use the maximum point
        if not peaks and heights:
            max_idx = heights.index(max(heights))
            peaks.append(heights_by_time[max_idx])

        return peaks

    def _calculate_swell_significance(self, height: Optional[float], period: Optional[float]) -> float:
        """
        Calculate significance score for a swell event.

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
        # Hawaiian scale approximated by doubling significant wave height in feet
        return meters * 6.56168
