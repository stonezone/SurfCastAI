#!/usr/bin/env python3
"""
Models for swell events and forecast data.

This module defines the data models for swell events, components,
and forecast data used throughout the system.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class SwellComponent:
    """
    Represents a component of a swell event.

    A swell can have multiple components with different
    characteristics (e.g. primary NW swell with secondary W component).

    quality_flag values:
    - "valid": Data passes all quality checks (use in forecast)
    - "suspect": Data looks unusual but not clearly wrong (use with caution)
    - "excluded": Data is anomalous and should NOT be used in forecasts
    """
    height: float
    period: float
    direction: float
    confidence: float = 0.7
    source: str = "model"
    quality_flag: str = "valid"  # valid, suspect, or excluded
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwellEvent:
    """
    Represents a distinct swell event.

    A swell event has a lifecycle (start, peak, end times),
    directional characteristics, and one or more components.

    quality_flag values:
    - "valid": Data passes all quality checks (use in forecast)
    - "suspect": Data looks unusual but not clearly wrong (use with caution)
    - "excluded": Data is anomalous and should NOT be used in forecasts
    """
    event_id: str
    start_time: str
    peak_time: str
    primary_direction: float
    significance: float
    hawaii_scale: float
    end_time: str = ''
    source: str = 'model'
    quality_flag: str = "valid"  # valid, suspect, or excluded
    primary_components: List[SwellComponent] = field(default_factory=list)
    secondary_components: List[SwellComponent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure we always have an end time value."""
        if not self.end_time:
            self.end_time = self.peak_time

    @property
    def primary_direction_cardinal(self) -> str:
        """Get cardinal direction from degrees."""
        dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        ix = round(self.primary_direction / 22.5) % 16
        return dirs[ix]

    @property
    def dominant_period(self) -> float:
        """Get dominant period from primary components."""
        if not self.primary_components:
            return 0.0
        return max(c.period for c in self.primary_components)


@dataclass
class ForecastLocation:
    """
    Represents a location for which forecasts are generated.

    Different locations (e.g. North Shore vs South Shore) have
    different exposures to swell events.
    """
    name: str
    shore: str
    latitude: float
    longitude: float
    facing_direction: float
    swell_events: List[SwellEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SwellForecast:
    """
    Represents a complete swell forecast.

    A forecast includes multiple swell events and their impacts
    on different locations.
    """
    forecast_id: str
    generated_time: str
    swell_events: List[SwellEvent] = field(default_factory=list)
    locations: List[ForecastLocation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


def dict_to_swell_forecast(data: Dict[str, Any]) -> SwellForecast:
    """
    Convert dictionary to SwellForecast object.

    Args:
        data: Dictionary data from JSON

    Returns:
        SwellForecast object
    """
    forecast = SwellForecast(
        forecast_id=data.get('forecast_id', ''),
        generated_time=data.get('generated_time', ''),
        metadata=data.get('metadata', {})
    )

    # Convert swell events
    for event_data in data.get('swell_events', []):
        event = SwellEvent(
            event_id=event_data.get('event_id', ''),
            start_time=event_data.get('start_time', ''),
            peak_time=event_data.get('peak_time', ''),
            end_time=event_data.get('end_time', ''),
            primary_direction=event_data.get('primary_direction', 0.0),
            significance=event_data.get('significance', 0.0),
            hawaii_scale=event_data.get('hawaii_scale', 0.0),
            source=event_data.get('source', ''),
            quality_flag=event_data.get('quality_flag', 'valid'),
            metadata=event_data.get('metadata', {})
        )

        # Add primary components
        for comp_data in event_data.get('primary_components', []):
            component = SwellComponent(
                height=comp_data.get('height', 0.0),
                period=comp_data.get('period', 0.0),
                direction=comp_data.get('direction', 0.0),
                confidence=comp_data.get('confidence', 0.7),
                source=comp_data.get('source', 'model'),
                quality_flag=comp_data.get('quality_flag', 'valid')
            )
            event.primary_components.append(component)

        # Add secondary components
        for comp_data in event_data.get('secondary_components', []):
            component = SwellComponent(
                height=comp_data.get('height', 0.0),
                period=comp_data.get('period', 0.0),
                direction=comp_data.get('direction', 0.0),
                confidence=comp_data.get('confidence', 0.7),
                source=comp_data.get('source', 'model'),
                quality_flag=comp_data.get('quality_flag', 'valid')
            )
            event.secondary_components.append(component)

        forecast.swell_events.append(event)

    # Convert locations
    for loc_data in data.get('locations', []):
        location = ForecastLocation(
            name=loc_data.get('name', ''),
            shore=loc_data.get('shore', ''),
            latitude=loc_data.get('latitude', 0.0),
            longitude=loc_data.get('longitude', 0.0),
            facing_direction=loc_data.get('facing_direction', 0.0),
            metadata=loc_data.get('metadata', {})
        )

        # Add location-specific swell events
        for event_data in loc_data.get('swell_events', []):
            event = SwellEvent(
                event_id=event_data.get('event_id', ''),
                start_time=event_data.get('start_time', ''),
                peak_time=event_data.get('peak_time', ''),
                end_time=event_data.get('end_time', ''),
                primary_direction=event_data.get('primary_direction', 0.0),
                significance=event_data.get('significance', 0.0),
                hawaii_scale=event_data.get('hawaii_scale', 0.0),
                source=event_data.get('source', ''),
                quality_flag=event_data.get('quality_flag', 'valid'),
                metadata=event_data.get('metadata', {})
            )

            # Add primary components (same as main swell events)
            for comp_data in event_data.get('primary_components', []):
                component = SwellComponent(
                    height=comp_data.get('height', 0.0),
                    period=comp_data.get('period', 0.0),
                    direction=comp_data.get('direction', 0.0),
                    confidence=comp_data.get('confidence', 0.7),
                    source=comp_data.get('source', 'model'),
                    quality_flag=comp_data.get('quality_flag', 'valid')
                )
                event.primary_components.append(component)

            # Add secondary components
            for comp_data in event_data.get('secondary_components', []):
                component = SwellComponent(
                    height=comp_data.get('height', 0.0),
                    period=comp_data.get('period', 0.0),
                    direction=comp_data.get('direction', 0.0),
                    confidence=comp_data.get('confidence', 0.7),
                    source=comp_data.get('source', 'model'),
                    quality_flag=comp_data.get('quality_flag', 'valid')
                )
                event.secondary_components.append(component)

            location.swell_events.append(event)

        forecast.locations.append(location)

    return forecast
