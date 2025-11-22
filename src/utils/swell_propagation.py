"""
Swell Propagation Calculator

Calculates wave travel times from source storms to Hawaii using
deep water wave physics and great circle distance.

This is how professional forecasters like Pat Caldwell calculate
swell arrival timing from distant storms.
"""

import math
from datetime import datetime, timedelta
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Hawaii reference point (approximate center of main islands)
HAWAII_LAT = 21.0
HAWAII_LON = -157.5  # 157.5°W

# Physical constants
GRAVITY = 9.81  # m/s²
KNOTS_TO_MS = 0.514444  # conversion factor
NAUTICAL_MILE_TO_KM = 1.852


class SwellPropagationCalculator:
    """
    Calculate swell propagation timing from source storms to Hawaii.

    Based on deep water wave group velocity:
    Cg = (g * T) / (4π)

    Where:
    - Cg = group velocity (wave energy travel speed)
    - g = gravitational acceleration (9.81 m/s²)
    - T = wave period (seconds)
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_group_velocity(self, period_seconds: float) -> float:
        """
        Calculate deep water wave group velocity.

        Args:
            period_seconds: Wave period in seconds

        Returns:
            Group velocity in m/s
        """
        # Cg = (g * T) / (4π)
        return (GRAVITY * period_seconds) / (4 * math.pi)

    def haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate great circle distance between two points.

        Args:
            lat1, lon1: First point (degrees)
            lat2, lon2: Second point (degrees)

        Returns:
            Distance in nautical miles
        """
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon = math.radians(lon2 - lon1)
        dlat = math.radians(lat2 - lat1)

        # Haversine formula
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in km
        earth_radius_km = 6371.0
        distance_km = earth_radius_km * c

        # Convert to nautical miles
        distance_nm = distance_km / NAUTICAL_MILE_TO_KM

        return distance_nm

    def calculate_travel_time(
        self,
        source_lat: float,
        source_lon: float,
        period_seconds: float,
        target_lat: float = HAWAII_LAT,
        target_lon: float = HAWAII_LON
    ) -> Tuple[float, float, float]:
        """
        Calculate swell travel time from source to target.

        Args:
            source_lat: Storm latitude (degrees)
            source_lon: Storm longitude (degrees, negative for West)
            period_seconds: Dominant wave period (seconds)
            target_lat: Target latitude (default: Hawaii)
            target_lon: Target longitude (default: Hawaii)

        Returns:
            Tuple of (travel_time_hours, distance_nm, group_velocity_knots)
        """
        # Calculate distance
        distance_nm = self.haversine_distance(
            source_lat, source_lon,
            target_lat, target_lon
        )

        # Calculate group velocity
        group_velocity_ms = self.calculate_group_velocity(period_seconds)
        group_velocity_knots = group_velocity_ms / KNOTS_TO_MS

        # Calculate travel time
        travel_time_hours = distance_nm / group_velocity_knots

        self.logger.debug(
            f"Swell propagation: {source_lat}°N {source_lon}°E → Hawaii\n"
            f"  Distance: {distance_nm:.0f} nm\n"
            f"  Period: {period_seconds}s → Group velocity: {group_velocity_knots:.1f} kt\n"
            f"  Travel time: {travel_time_hours:.1f} hours ({travel_time_hours/24:.1f} days)"
        )

        return travel_time_hours, distance_nm, group_velocity_knots

    def calculate_arrival(
        self,
        source_lat: float,
        source_lon: float,
        period_seconds: float,
        generation_time: datetime,
        target_lat: float = HAWAII_LAT,
        target_lon: float = HAWAII_LON
    ) -> Tuple[datetime, dict]:
        """
        Calculate when swell will arrive at target location.

        Args:
            source_lat: Storm latitude (degrees)
            source_lon: Storm longitude (degrees)
            period_seconds: Dominant wave period (seconds)
            generation_time: When the swell was generated
            target_lat: Target latitude (default: Hawaii)
            target_lon: Target longitude (default: Hawaii)

        Returns:
            Tuple of (arrival_time, details_dict)
        """
        travel_hours, distance_nm, velocity_kt = self.calculate_travel_time(
            source_lat, source_lon, period_seconds,
            target_lat, target_lon
        )

        arrival_time = generation_time + timedelta(hours=travel_hours)

        details = {
            'source_location': {'lat': source_lat, 'lon': source_lon},
            'target_location': {'lat': target_lat, 'lon': target_lon},
            'distance_nm': distance_nm,
            'period_seconds': period_seconds,
            'group_velocity_knots': velocity_kt,
            'travel_time_hours': travel_hours,
            'generation_time': generation_time.isoformat(),
            'arrival_time': arrival_time.isoformat(),
        }

        return arrival_time, details

    def estimate_period_from_storm(
        self,
        wind_speed_kt: float,
        fetch_length_nm: Optional[float] = None,
        duration_hours: Optional[float] = None
    ) -> float:
        """
        Estimate dominant wave period from storm characteristics.

        Uses empirical relationships from wave forecasting.

        Args:
            wind_speed_kt: Wind speed in knots
            fetch_length_nm: Fetch length in nautical miles (optional)
            duration_hours: Storm duration in hours (optional)

        Returns:
            Estimated period in seconds
        """
        # Improved empirical formula based on wave forecasting
        # For wind speed in m/s: T ≈ 0.4 * U (for fully developed seas)
        wind_speed_ms = wind_speed_kt * KNOTS_TO_MS

        # Base period from wind speed (empirical relationship)
        # T ≈ 0.4 * U for fully developed seas
        base_period = 0.4 * wind_speed_ms

        # Adjust for fetch if provided
        if fetch_length_nm:
            # Longer fetch allows longer periods to develop
            # Fetch factor: small fetch (100nm) = 1.0, large fetch (1000nm) = 1.5
            fetch_factor = min(1.8, 1.0 + (fetch_length_nm / 500) * 0.4)
            base_period *= fetch_factor

        # Adjust for duration if provided
        if duration_hours:
            # Longer duration = more fully developed seas
            # Short duration (12hr) = 1.0, multi-day (72hr) = 1.4
            duration_factor = min(1.5, 1.0 + (duration_hours / 48) * 0.4)
            base_period *= duration_factor

        # Clamp to reasonable range for Pacific swells
        # Short-period: 8-11s, Mid-period: 11-14s, Long-period: 14-18s
        period = max(8.0, min(20.0, base_period))

        self.logger.debug(
            f"Estimated period: {wind_speed_kt}kt wind, {fetch_length_nm or 'default'}nm fetch, "
            f"{duration_hours or 'default'}hr duration → {period:.1f}s period"
        )

        return period


def example_kamchatka_swell():
    """
    Example: Kamchatka storm from Pat Caldwell's Oct 8, 2025 forecast.

    Pat described:
    - "Long-lived Kamchatka corner pattern 10/8-12"
    - "Deepening low-pressure area modelled to drop central pressure below 970 mb 10/9"
    - "Storm-force winds midday 10/8 (HST) hugging Kurils"
    - "Long-period onset is due Sunday morning" (10/12)

    Storm location: ~45°N, 155°E (Kamchatka/Kuril area)
    Generation: Oct 8, 2025 12:00 HST
    Expected arrival: Oct 12, 2025 morning
    """
    calc = SwellPropagationCalculator()

    # Storm parameters
    source_lat = 45.0  # Kamchatka/Kuril Islands
    source_lon = 155.0  # East longitude

    # Estimate period from storm characteristics
    wind_speed_kt = 50  # Storm-force winds
    fetch_nm = 500  # Large fetch over several days
    duration_hours = 72  # 3+ days of generation

    period = calc.estimate_period_from_storm(wind_speed_kt, fetch_nm, duration_hours)

    # Generation time
    generation_time = datetime(2025, 10, 8, 12, 0)  # Oct 8, 12:00 HST

    # Calculate arrival
    arrival, details = calc.calculate_arrival(
        source_lat, source_lon, period, generation_time
    )

    print("=" * 60)
    print("KAMCHATKA SWELL EXAMPLE (Pat Caldwell Oct 8, 2025)")
    print("=" * 60)
    print(f"Storm Location: {source_lat}°N, {source_lon}°E")
    print(f"Generation Time: {generation_time.strftime('%a %b %d, %I:%M %p')}")
    print(f"Wind Speed: {wind_speed_kt} kt (storm-force)")
    print(f"Estimated Period: {period:.1f}s")
    print(f"\nDistance to Hawaii: {details['distance_nm']:.0f} nm")
    print(f"Group Velocity: {details['group_velocity_knots']:.1f} kt")
    print(f"Travel Time: {details['travel_time_hours']:.1f} hours ({details['travel_time_hours']/24:.1f} days)")
    print(f"\nArrival Time: {arrival.strftime('%a %b %d, %I:%M %p')}")
    print(f"\nPat Caldwell predicted: 'Sunday morning' (Oct 12)")
    print(f"Our calculation: {arrival.strftime('%A %p')} (Oct {arrival.day})")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    example_kamchatka_swell()
