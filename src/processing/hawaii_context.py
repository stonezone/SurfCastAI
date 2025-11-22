"""
Hawaii-specific geographic context processor for SurfCastAI.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
import json
import math
from datetime import datetime

from .data_processor import DataProcessor, ProcessingResult
from .models.swell_event import SwellComponent, SwellEvent, ForecastLocation, SwellForecast
from ..core.config import Config


@dataclass
class HawaiiShoreData:
    """
    Data about a specific Hawaiian shore.

    Attributes:
        name: Shore name
        location: Location name
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        facing_direction: Direction the shore faces in degrees
        swell_exposure: List of swell direction ranges that affect this shore
        quality_directions: List of swell direction ranges that produce quality waves
        seasonal_rating: Seasonal quality rating by month (1-12)
    """
    name: str
    location: str
    latitude: float
    longitude: float
    facing_direction: float
    swell_exposure: List[Tuple[float, float]] = field(default_factory=list)
    quality_directions: List[Tuple[float, float]] = field(default_factory=list)
    seasonal_rating: Dict[int, float] = field(default_factory=dict)


class HawaiiContext:
    """
    Hawaii-specific geographic context for surf forecasting.

    Features:
    - Provides geographic information about Hawaiian shores
    - Contains location-specific knowledge about swell exposure
    - Offers seasonal patterns and historical context
    - Supports assessment of swell impact on specific locations
    """

    def __init__(self):
        """Initialize Hawaii context with geographic data."""
        self.logger = logging.getLogger('processor.hawaii_context')

        # Initialize shore data for Oahu
        self.shores = {
            'north_shore': HawaiiShoreData(
                name='North Shore',
                location='Oahu',
                latitude=21.6639,
                longitude=-158.0529,
                facing_direction=0,  # North-facing
                swell_exposure=[(270, 360), (0, 90)],  # NW to NE
                quality_directions=[(305, 340)],  # NW to NNW (optimal direction)
                seasonal_rating={
                    1: 0.9, 2: 0.8, 3: 0.7, 4: 0.5, 5: 0.3, 6: 0.2,  # Jan-Jun
                    7: 0.1, 8: 0.1, 9: 0.2, 10: 0.5, 11: 0.7, 12: 0.9  # Jul-Dec
                }
            ),
            'south_shore': HawaiiShoreData(
                name='South Shore',
                location='Oahu',
                latitude=21.2749,
                longitude=-157.8238,
                facing_direction=180,  # South-facing
                swell_exposure=[(90, 270)],  # SE to SW
                quality_directions=[(170, 200)],  # S to SSW (optimal direction)
                seasonal_rating={
                    1: 0.2, 2: 0.3, 3: 0.4, 4: 0.6, 5: 0.8, 6: 0.9,  # Jan-Jun
                    7: 0.9, 8: 0.9, 9: 0.7, 10: 0.5, 11: 0.3, 12: 0.2  # Jul-Dec
                }
            ),
            'west_shore': HawaiiShoreData(
                name='West Shore',
                location='Oahu',
                latitude=21.4152,
                longitude=-158.1928,
                facing_direction=270,  # West-facing
                swell_exposure=[(210, 330)],  # SSW to NNW
                quality_directions=[(270, 310)],  # W to NW (optimal direction)
                seasonal_rating={
                    1: 0.8, 2: 0.7, 3: 0.6, 4: 0.5, 5: 0.4, 6: 0.3,  # Jan-Jun
                    7: 0.2, 8: 0.3, 9: 0.4, 10: 0.5, 11: 0.6, 12: 0.7  # Jul-Dec
                }
            ),
            'east_shore': HawaiiShoreData(
                name='East Shore',
                location='Oahu',
                latitude=21.4813,
                longitude=-157.7040,
                facing_direction=90,  # East-facing
                swell_exposure=[(30, 150)],  # NE to SE
                quality_directions=[(60, 90)],  # ENE to E (optimal direction)
                seasonal_rating={
                    1: 0.7, 2: 0.8, 3: 0.8, 4: 0.7, 5: 0.6, 6: 0.5,  # Jan-Jun
                    7: 0.5, 8: 0.5, 9: 0.6, 10: 0.6, 11: 0.7, 12: 0.7  # Jul-Dec
                }
            )
        }

    def get_shore_data(self, shore_name: str) -> Optional[HawaiiShoreData]:
        """
        Get data for a specific shore.

        Args:
            shore_name: Name of the shore (north_shore, south_shore, etc.)

        Returns:
            HawaiiShoreData for the shore or None if not found
        """
        normalized_name = shore_name.lower().replace(' ', '_')
        return self.shores.get(normalized_name)

    def get_all_shores(self) -> List[HawaiiShoreData]:
        """
        Get data for all shores.

        Returns:
            List of HawaiiShoreData for all shores
        """
        return list(self.shores.values())

    def is_in_range(self, direction: float, range_tuple: Tuple[float, float]) -> bool:
        """
        Check if a direction is within a range.

        Args:
            direction: Direction in degrees (0-360)
            range_tuple: Tuple of (min_direction, max_direction)

        Returns:
            True if direction is within range, False otherwise
        """
        start, end = range_tuple

        # Handle ranges that cross the 0/360 boundary
        if start > end:
            return direction >= start or direction <= end
        else:
            return start <= direction <= end

    def is_exposed_to_direction(self, shore_name: str, direction: float) -> bool:
        """
        Check if a shore is exposed to a specific swell direction.

        Args:
            shore_name: Name of the shore
            direction: Swell direction in degrees (0-360)

        Returns:
            True if shore is exposed to the direction, False otherwise
        """
        shore = self.get_shore_data(shore_name)
        if not shore:
            return False

        # Check if direction is within any exposure range
        for range_tuple in shore.swell_exposure:
            if self.is_in_range(direction, range_tuple):
                return True

        return False

    def get_exposure_factor(self, shore_name: str, direction: float) -> float:
        """
        Get exposure factor for a specific shore and direction.

        Args:
            shore_name: Name of the shore
            direction: Swell direction in degrees (0-360)

        Returns:
            Exposure factor (0-1), where 1 is optimal exposure
        """
        shore = self.get_shore_data(shore_name)
        if not shore:
            return 0.0

        # Check if direction is within quality range (optimal)
        for range_tuple in shore.quality_directions:
            if self.is_in_range(direction, range_tuple):
                # Calculate how centered it is in the quality range
                start, end = range_tuple
                if start > end:  # Range crosses 0/360 boundary
                    if direction >= start:
                        midpoint = (start + 360 + end) / 2 % 360
                        distance = min(abs(direction - midpoint), abs(direction - midpoint + 360))
                    else:
                        midpoint = (start + end) / 2
                        distance = min(abs(direction - midpoint), abs(direction - midpoint - 360))
                else:
                    midpoint = (start + end) / 2
                    distance = abs(direction - midpoint)

                # Convert distance to factor (1.0 at midpoint, 0.8 at edges)
                range_width = (end - start) % 360
                normalized_distance = distance / (range_width / 2)
                return max(0.8, 1.0 - normalized_distance * 0.2)

        # Check if direction is within general exposure range
        for range_tuple in shore.swell_exposure:
            if self.is_in_range(direction, range_tuple):
                # Less optimal but still exposed
                return 0.5

        # Not exposed
        return 0.0

    def get_seasonal_factor(self, shore_name: str, date: Optional[datetime] = None) -> float:
        """
        Get seasonal factor for a specific shore and date.

        Args:
            shore_name: Name of the shore
            date: Date to check (defaults to current date)

        Returns:
            Seasonal factor (0-1), where 1 is optimal season
        """
        shore = self.get_shore_data(shore_name)
        if not shore:
            return 0.5

        # Use current date if not provided
        if date is None:
            date = datetime.now()

        # Get month and return corresponding seasonal rating
        month = date.month
        return shore.seasonal_rating.get(month, 0.5)

    def create_forecast_location(self, shore_name: str) -> Optional[ForecastLocation]:
        """
        Create a ForecastLocation for a specific shore.

        Args:
            shore_name: Name of the shore

        Returns:
            ForecastLocation object or None if shore not found
        """
        shore = self.get_shore_data(shore_name)
        if not shore:
            return None

        return ForecastLocation(
            name=shore.location + ' ' + shore.name,
            shore=shore.name,
            latitude=shore.latitude,
            longitude=shore.longitude,
            facing_direction=shore.facing_direction,
            metadata={
                'swell_exposure': [(start, end) for start, end in shore.swell_exposure],
                'quality_directions': [(start, end) for start, end in shore.quality_directions],
                'seasonal_rating': shore.seasonal_rating
            }
        )


class HawaiiContextProcessor(DataProcessor[Dict[str, Any], SwellForecast]):
    """
    Processor that applies Hawaii-specific context to swell forecasts.

    Features:
    - Enriches swell forecast data with Hawaii-specific knowledge
    - Calculates impact of swells on different Hawaiian shores
    - Adjusts forecast based on seasonal patterns
    - Provides location-specific forecast data
    """

    def __init__(self, config: Config):
        """
        Initialize the Hawaii context processor.

        Args:
            config: Application configuration
        """
        super().__init__(config)
        self.logger = logging.getLogger('processor.hawaii_context')
        self.hawaii_context = HawaiiContext()

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate input data.

        Args:
            data: Input swell forecast data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for required fields
        if 'swell_events' not in data or not data['swell_events']:
            errors.append("Missing or empty swell_events field")

        return errors

    def process(self, data: Dict[str, Any]) -> ProcessingResult:
        """
        Process swell forecast data with Hawaii-specific context.

        Args:
            data: Input swell forecast data

        Returns:
            ProcessingResult with processed SwellForecast
        """
        try:
            # Create SwellForecast instance if not already
            if isinstance(data, SwellForecast):
                forecast = data
            else:
                # Create from dictionary
                forecast = SwellForecast(
                    forecast_id=data.get('forecast_id', 'forecast_' + datetime.now().strftime('%Y%m%d_%H%M%S')),
                    generated_time=data.get('generated_time', datetime.now().isoformat()),
                    metadata=data.get('metadata', {})
                )

                # Add swell events
                for event_data in data.get('swell_events', []):
                    event = SwellEvent(
                        event_id=event_data.get('event_id', 'event_' + datetime.now().strftime('%Y%m%d_%H%M%S')),
                        start_time=event_data.get('start_time', ''),
                        peak_time=event_data.get('peak_time'),
                        end_time=event_data.get('end_time'),
                        primary_direction=event_data.get('primary_direction', 0.0),
                        significance=event_data.get('significance', 0.5),
                        hawaii_scale=event_data.get('hawaii_scale'),
                        source=event_data.get('source'),
                        metadata=event_data.get('metadata', {})
                    )

                    # Add components
                    for comp_data in event_data.get('primary_components', []):
                        event.primary_components.append(SwellComponent(
                            height=comp_data.get('height', 0.0),
                            period=comp_data.get('period', 0.0),
                            direction=comp_data.get('direction', 0.0),
                            energy=comp_data.get('energy'),
                            confidence=comp_data.get('confidence', 1.0),
                            source=comp_data.get('source')
                        ))

                    forecast.swell_events.append(event)

            # Enrich forecast with Hawaii-specific locations
            self._add_hawaii_locations(forecast)

            # Calculate impact of swells on each location
            self._calculate_location_impacts(forecast)

            # Apply seasonal adjustments
            self._apply_seasonal_factors(forecast)

            return ProcessingResult(
                success=True,
                data=forecast
            )

        except Exception as e:
            self.logger.error(f"Error processing forecast with Hawaii context: {e}")
            return ProcessingResult(
                success=False,
                error=f"Processing error: {str(e)}"
            )

    def _add_hawaii_locations(self, forecast: SwellForecast) -> None:
        """
        Add Hawaii-specific locations to the forecast.

        Args:
            forecast: Swell forecast to modify
        """
        # Add main Hawaiian shores if not already present
        shore_names = ['north_shore', 'south_shore', 'west_shore', 'east_shore']

        # Check which shores are already in the forecast
        existing_shores = set()
        for location in forecast.locations:
            shore = location.shore.lower().replace(' ', '_')
            existing_shores.add(shore)

        # Add missing shores
        for shore_name in shore_names:
            if shore_name not in existing_shores:
                location = self.hawaii_context.create_forecast_location(shore_name)
                if location:
                    forecast.locations.append(location)

    def _calculate_location_impacts(self, forecast: SwellForecast) -> None:
        """
        Calculate impact of swell events on each location.

        Args:
            forecast: Swell forecast to modify
        """
        # For each location, calculate which swell events affect it
        for location in forecast.locations:
            # Get shore name
            shore_name = location.shore.lower().replace(' ', '_')

            # Clear existing swell events
            location.swell_events = []

            # Calculate exposure to each swell event
            for event in forecast.swell_events:
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

    def _apply_seasonal_factors(self, forecast: SwellForecast) -> None:
        """
        Apply seasonal adjustments to the forecast.

        Args:
            forecast: Swell forecast to modify
        """
        # Get the forecast date from the generated_time or current date
        forecast_date = None
        try:
            forecast_date = datetime.fromisoformat(forecast.generated_time.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            forecast_date = datetime.now()

        # For each location, adjust significance based on seasonal factors
        for location in forecast.locations:
            # Get shore name
            shore_name = location.shore.lower().replace(' ', '_')

            # Get seasonal factor
            seasonal_factor = self.hawaii_context.get_seasonal_factor(shore_name, forecast_date)

            # Add seasonal factor to location metadata
            location_metadata = location.metadata.copy()
            location_metadata['seasonal_factor'] = seasonal_factor
            location.metadata = location_metadata

            # Adjust significance of each swell event for this location
            for event in location.swell_events:
                # Get exposure factor
                exposure_factor = event.metadata.get(f'exposure_{shore_name}', 0.5)

                # Adjust significance based on seasonal factor
                adjusted_significance = event.significance * exposure_factor * seasonal_factor

                # Update event metadata with adjusted significance for this location
                event_metadata = event.metadata.copy()
                event_metadata[f'adjusted_significance_{shore_name}'] = adjusted_significance
                event.metadata = event_metadata
