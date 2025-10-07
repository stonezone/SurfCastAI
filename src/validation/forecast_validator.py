"""
Forecast validation engine - compares predictions to ground truth observations.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .surf_observation import SurfObservation


class ForecastValidator:
    """
    Validates forecast accuracy against surf observations.
    
    Features:
    - Compares forecast predictions to actual surf conditions
    - Calculates error metrics (MAE, RMSE, bias)
    - Tracks accuracy over time
    - Identifies systematic errors
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize validator.
        
        Args:
            output_dir: Directory containing forecast outputs
        """
        self.output_dir = output_dir
        self.logger = logging.getLogger('validation.forecast_validator')
        
    def validate_observation(
        self,
        observation: SurfObservation,
        time_window_hours: float = 3.0
    ) -> Dict[str, Any]:
        """
        Validate a single surf observation against forecast.
        
        Args:
            observation: Ground truth surf observation
            time_window_hours: How many hours before/after to search for forecast
            
        Returns:
            Validation results with accuracy metrics
        """
        # Find forecast closest to observation time
        forecast = self._find_closest_forecast(observation.time, time_window_hours)
        
        if not forecast:
            return {
                'status': 'no_forecast_found',
                'observation': observation.to_dict(),
                'error': f'No forecast found within {time_window_hours} hours'
            }
        
        # Extract predicted height for this location
        predicted_height = self._extract_location_prediction(
            forecast,
            observation.location
        )
        
        if predicted_height is None:
            return {
                'status': 'location_not_in_forecast',
                'observation': observation.to_dict(),
                'forecast_id': forecast['forecast_id'],
                'error': f'Location {observation.location} not in forecast'
            }
        
        # Calculate error metrics
        error = predicted_height - observation.hawaiian_scale
        absolute_error = abs(error)
        percent_error = (error / observation.hawaiian_scale) * 100
        
        return {
            'status': 'validated',
            'observation': observation.to_dict(),
            'forecast_id': forecast['forecast_id'],
            'forecast_generated': forecast['generated_time'],
            'predicted_height': predicted_height,
            'observed_height': observation.hawaiian_scale,
            'error': error,
            'absolute_error': absolute_error,
            'percent_error': percent_error,
            'accuracy_grade': self._grade_accuracy(absolute_error, observation.hawaiian_scale)
        }
    
    def validate_batch(
        self,
        observations: List[SurfObservation]
    ) -> Dict[str, Any]:
        """
        Validate multiple observations and compute aggregate statistics.
        
        Args:
            observations: List of surf observations
            
        Returns:
            Aggregate validation results
        """
        results = []
        for obs in observations:
            result = self.validate_observation(obs)
            results.append(result)
        
        # Calculate aggregate metrics
        validated = [r for r in results if r['status'] == 'validated']
        
        if not validated:
            return {
                'total_observations': len(observations),
                'validated_count': 0,
                'error': 'No observations could be validated'
            }
        
        # Compute statistics
        errors = [r['error'] for r in validated]
        absolute_errors = [r['absolute_error'] for r in validated]
        percent_errors = [r['percent_error'] for r in validated]
        
        return {
            'total_observations': len(observations),
            'validated_count': len(validated),
            'failed_count': len(results) - len(validated),
            'mean_error': sum(errors) / len(errors),
            'mean_absolute_error': sum(absolute_errors) / len(absolute_errors),
            'mean_percent_error': sum(percent_errors) / len(percent_errors),
            'bias': sum(errors) / len(errors),  # Positive = overprediction
            'rmse': (sum(e**2 for e in errors) / len(errors)) ** 0.5,
            'min_error': min(errors),
            'max_error': max(errors),
            'individual_results': results
        }
    
    def _find_closest_forecast(
        self,
        target_time: datetime,
        window_hours: float
    ) -> Optional[Dict]:
        """Find forecast closest to target time."""
        window = timedelta(hours=window_hours)
        best_forecast = None
        best_delta = None
        
        # Search all forecast directories
        for forecast_dir in self.output_dir.glob('forecast_*'):
            data_file = forecast_dir / 'forecast_data.json'
            if not data_file.exists():
                continue
            
            try:
                with open(data_file) as f:
                    forecast = json.load(f)
                
                # Parse forecast generation time
                gen_time = datetime.fromisoformat(forecast['generated_time'])
                
                # Calculate time difference
                delta = abs(gen_time - target_time)
                
                # Check if within window and better than current best
                if delta <= window:
                    if best_delta is None or delta < best_delta:
                        best_forecast = forecast
                        best_delta = delta
            
            except Exception as e:
                self.logger.warning(f'Error reading {data_file}: {e}')
                continue
        
        return best_forecast
    
    def _extract_location_prediction(
        self,
        forecast: Dict,
        location: str
    ) -> Optional[float]:
        """
        Extract predicted height for a specific location from forecast.
        
        Args:
            forecast: Forecast data dict
            location: Location name (e.g., "Sunset Beach")
            
        Returns:
            Predicted height in Hawaiian scale, or None if not found
        """
        location_lower = location.lower()
        
        # Map location to shore
        location_to_shore = {
            'sunset': 'north',
            'pipeline': 'north',
            'ehukai': 'north',
            'waimea': 'north',
            'haleiwa': 'north',
            'rocky point': 'north',
            'off the wall': 'north',
            'velzyland': 'north',
            'chuns': 'north',
            'waikiki': 'south',
            'ala moana': 'south',
            'diamond head': 'south',
            'bowls': 'south',
            'queens': 'south',
            'canoes': 'south',
            'sandy': 'east',
            'makapuu': 'east',
            'makaha': 'west',
            'nanakuli': 'west'
        }
        
        # Find which shore this location is on
        shore = None
        for key, value in location_to_shore.items():
            if key in location_lower:
                shore = value
                break
        
        if not shore:
            self.logger.warning(f'Unknown location: {location}')
            return None
        
        # Get swell events and find max for this shore
        swell_events = forecast.get('metadata', {}).get('source_data', {})
        
        # Look for swell events with exposure to this shore
        max_height = 0.0
        
        # Check if we have processed swell events
        if 'swell_events' in swell_events:
            for event in forecast.get('swell_events', []):
                # Check shore exposure
                exposure_key = f'exposure_{shore}_shore'
                exposure = event.get('metadata', {}).get(exposure_key, 0.0)
                
                if exposure > 0.3:  # Significant exposure
                    height = event.get('hawaii_scale', 0.0)
                    max_height = max(max_height, height * exposure)
        
        return max_height if max_height > 0 else None
    
    def _grade_accuracy(
        self,
        absolute_error: float,
        observed_height: float
    ) -> str:
        """
        Grade forecast accuracy.
        
        Args:
            absolute_error: Absolute error in ft
            observed_height: Observed height in Hawaiian scale
            
        Returns:
            Grade: A, B, C, D, or F
        """
        # Calculate percent error
        percent_error = (absolute_error / observed_height) * 100 if observed_height > 0 else 100
        
        if percent_error < 15:
            return 'A'  # Excellent
        elif percent_error < 25:
            return 'B'  # Good
        elif percent_error < 40:
            return 'C'  # Fair
        elif percent_error < 60:
            return 'D'  # Poor
        else:
            return 'F'  # Failing
