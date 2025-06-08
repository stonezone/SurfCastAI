"""
Buoy data processor for SurfCastAI.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
from datetime import datetime, timedelta

from .data_processor import DataProcessor, ProcessingResult
from .models.buoy_data import BuoyData, BuoyObservation
from ..core.config import Config


class BuoyProcessor(DataProcessor[Dict[str, Any], BuoyData]):
    """
    Processor for buoy data.
    
    Features:
    - Converts raw buoy data to standardized BuoyData model
    - Validates data completeness and consistency
    - Analyzes wave patterns and trends
    - Provides cleaned and normalized data for further processing
    """
    
    def __init__(self, config: Config):
        """
        Initialize the buoy processor.
        
        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('processor.buoy')
    
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate buoy data.
        
        Args:
            data: Raw buoy data
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check for required fields
        if 'station_id' not in data:
            errors.append("Missing station_id field")
        
        # Check for observations
        if 'observations' not in data or not data['observations']:
            errors.append("No observations in buoy data")
        
        return errors
    
    def process(self, data: Dict[str, Any]) -> ProcessingResult:
        """
        Process buoy data.
        
        Args:
            data: Raw buoy data
            
        Returns:
            ProcessingResult with processed BuoyData
        """
        try:
            # Create BuoyData from raw data
            buoy_data = BuoyData.from_ndbc_json(data)
            
            # Check if we have any observations
            if not buoy_data.observations:
                return ProcessingResult(
                    success=False,
                    error="No observations found in buoy data",
                    data=buoy_data
                )
            
            # Clean and normalize data
            buoy_data = self._clean_observations(buoy_data)
            
            # Analyze data for quality and special conditions
            warnings, metadata = self._analyze_buoy_data(buoy_data)
            
            # Add metadata from analysis
            buoy_data.metadata.update(metadata)
            
            return ProcessingResult(
                success=True,
                data=buoy_data,
                warnings=warnings,
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Error processing buoy data: {e}")
            return ProcessingResult(
                success=False,
                error=f"Processing error: {str(e)}"
            )
    
    def _clean_observations(self, buoy_data: BuoyData) -> BuoyData:
        """
        Clean and normalize buoy observations.
        
        Args:
            buoy_data: Original buoy data
            
        Returns:
            Cleaned buoy data
        """
        # Filter out observations with missing essential data
        valid_observations = []
        for obs in buoy_data.observations:
            # Skip observations with no wave height or period
            if obs.wave_height is None and obs.dominant_period is None:
                continue
            
            # Clean up invalid values
            if obs.wave_height is not None and obs.wave_height < 0:
                obs.wave_height = None
            
            if obs.dominant_period is not None and obs.dominant_period < 0:
                obs.dominant_period = None
            
            if obs.wave_direction is not None and (obs.wave_direction < 0 or obs.wave_direction > 360):
                obs.wave_direction = None
            
            valid_observations.append(obs)
        
        # Sort observations by timestamp (newest first)
        valid_observations.sort(
            key=lambda obs: datetime.fromisoformat(obs.timestamp.replace('Z', '+00:00')) 
            if 'T' in obs.timestamp else datetime.now(),
            reverse=True
        )
        
        # Update buoy data with cleaned observations
        buoy_data.observations = valid_observations
        
        return buoy_data
    
    def _analyze_buoy_data(self, buoy_data: BuoyData) -> tuple[List[str], Dict[str, Any]]:
        """
        Analyze buoy data for quality and special conditions.
        
        Args:
            buoy_data: Buoy data to analyze
            
        Returns:
            Tuple of (warnings, metadata)
        """
        warnings = []
        metadata = {
            'analysis': {
                'timestamp': datetime.now().isoformat(),
                'quality_score': 1.0,
                'trends': {},
                'special_conditions': []
            }
        }
        
        # Check data freshness
        if buoy_data.observations:
            latest_obs = buoy_data.observations[0]
            try:
                obs_time = datetime.fromisoformat(latest_obs.timestamp.replace('Z', '+00:00'))
                now = datetime.now(obs_time.tzinfo)
                hours_old = (now - obs_time).total_seconds() / 3600
                
                metadata['analysis']['hours_since_update'] = hours_old
                
                if hours_old > 6:
                    warnings.append(f"Buoy data is {hours_old:.1f} hours old")
                    metadata['analysis']['quality_score'] -= min(0.5, hours_old / 24)
            except (ValueError, TypeError):
                warnings.append("Could not parse observation timestamp")
        
        # Check for data gaps
        if len(buoy_data.observations) >= 2:
            gap_found = False
            for i in range(len(buoy_data.observations) - 1):
                try:
                    current = datetime.fromisoformat(buoy_data.observations[i].timestamp.replace('Z', '+00:00'))
                    next_obs = datetime.fromisoformat(buoy_data.observations[i+1].timestamp.replace('Z', '+00:00'))
                    gap = (current - next_obs).total_seconds() / 3600
                    
                    if gap > 3:  # More than 3 hours between observations
                        gap_found = True
                        break
                except (ValueError, TypeError):
                    continue
            
            if gap_found:
                warnings.append("Gaps found in buoy data time series")
                metadata['analysis']['quality_score'] -= 0.2
        
        # Analyze wave height trends
        if len(buoy_data.observations) >= 3:
            heights = []
            for obs in buoy_data.observations[:12]:  # Use up to 12 recent observations
                if obs.wave_height is not None:
                    heights.append(obs.wave_height)
            
            if heights:
                # Calculate trend
                if len(heights) >= 3:
                    if heights[0] > heights[-1]:
                        trend = "increasing"
                    elif heights[0] < heights[-1]:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                    
                    metadata['analysis']['trends']['wave_height'] = trend
                
                # Calculate stats
                metadata['analysis']['trends']['max_height'] = max(heights)
                metadata['analysis']['trends']['min_height'] = min(heights)
                metadata['analysis']['trends']['avg_height'] = sum(heights) / len(heights)
        
        # Check for special conditions
        latest = buoy_data.latest_observation
        if latest:
            # Check for large swell
            if latest.wave_height is not None and latest.wave_height > 4.0:  # 4m ~ 13ft
                metadata['analysis']['special_conditions'].append("large_swell")
            
            # Check for long period swell
            if latest.dominant_period is not None and latest.dominant_period > 16.0:
                metadata['analysis']['special_conditions'].append("long_period_swell")
            
            # Check for storm conditions
            if (latest.wind_speed is not None and latest.wind_speed > 15.0 and 
                latest.wave_height is not None and latest.wave_height > 3.0):
                metadata['analysis']['special_conditions'].append("storm_conditions")
        
        return warnings, metadata
    
    def get_hawaii_scale(self, meters: float) -> float:
        """
        Convert wave height from meters to Hawaiian scale (face height in feet).
        
        Args:
            meters: Wave height in meters
            
        Returns:
            Wave height in Hawaiian scale (feet)
        """
        # Hawaiian scale is approximately 2x the significant height in feet
        return meters * 2 * 3.28084  # 1m = 3.28084ft