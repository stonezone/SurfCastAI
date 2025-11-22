"""
Unit tests for swell propagation calculator.

Tests physics calculations, great circle distance, travel time computation,
and period estimation from storm characteristics.
"""

import math
from datetime import datetime, timedelta
import pytest

from src.utils.swell_propagation import (
    SwellPropagationCalculator,
    GRAVITY,
    KNOTS_TO_MS,
    NAUTICAL_MILE_TO_KM,
    HAWAII_LAT,
    HAWAII_LON
)


class TestGroupVelocityCalculation:
    """Tests for deep water wave group velocity calculation."""

    def test_12_second_period_velocity(self):
        """
        Test group velocity for 12-second period swell.

        Formula: Cg = (g × T) / (4π)
        12s period → ~9.37 m/s → ~18.2 knots
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(12.0)

        expected = (GRAVITY * 12.0) / (4 * math.pi)
        assert velocity == pytest.approx(expected, rel=1e-6), \
            f"Group velocity should match formula: {velocity:.3f} m/s vs {expected:.3f} m/s"

        # Convert to knots and verify known value
        velocity_knots = velocity / KNOTS_TO_MS
        assert velocity_knots == pytest.approx(18.2, abs=0.5), \
            f"12s period should yield ~18.2 knots, got {velocity_knots:.1f} knots"

    def test_15_second_period_velocity(self):
        """
        Test group velocity for 15-second long-period swell.

        15s period → ~11.7 m/s → ~22.8 knots
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(15.0)

        velocity_knots = velocity / KNOTS_TO_MS
        assert velocity_knots == pytest.approx(22.8, abs=0.5), \
            f"15s period should yield ~22.8 knots, got {velocity_knots:.1f} knots"

    def test_8_second_period_velocity(self):
        """
        Test group velocity for 8-second short-period swell.

        8s period → ~6.25 m/s → ~12.1 knots
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(8.0)

        velocity_knots = velocity / KNOTS_TO_MS
        assert velocity_knots == pytest.approx(12.1, abs=0.5), \
            f"8s period should yield ~12.1 knots, got {velocity_knots:.1f} knots"

    def test_zero_period_returns_zero(self):
        """
        Test that zero period yields zero velocity.

        Edge case: Physics breaks down at zero period.
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(0.0)

        assert velocity == 0.0, \
            "Zero period should yield zero velocity"

    def test_negative_period_yields_negative_velocity(self):
        """
        Test negative period (unphysical but should handle gracefully).

        Edge case: Negative input should produce negative output
        (caller responsible for validation).
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(-10.0)

        assert velocity < 0, \
            "Negative period should yield negative velocity"

    @pytest.mark.parametrize("period,expected_velocity_ms", [
        (10.0, 7.81),   # Short period
        (12.0, 9.37),   # Mid period
        (14.0, 10.93),  # Long period
        (16.0, 12.49),  # Extra long period
        (18.0, 14.05),  # Very long period
    ])
    def test_various_period_velocities(self, period, expected_velocity_ms):
        """
        Test group velocity calculation across typical Pacific swell periods.

        Parametrized test for multiple realistic scenarios.
        """
        calc = SwellPropagationCalculator()
        velocity = calc.calculate_group_velocity(period)

        assert velocity == pytest.approx(expected_velocity_ms, abs=0.1), \
            f"Period {period}s should yield ~{expected_velocity_ms} m/s, got {velocity:.2f} m/s"


class TestHaversineDistance:
    """Tests for great circle distance calculation."""

    def test_hawaii_to_kamchatka_distance(self):
        """
        Test distance from Hawaii to Kamchatka Peninsula.

        Source: 45°N, 155°E → Hawaii 21°N, 157.5°W
        Actual calculated: ~2,740 nautical miles
        """
        calc = SwellPropagationCalculator()
        distance = calc.haversine_distance(
            45.0, 155.0,  # Kamchatka
            HAWAII_LAT, HAWAII_LON
        )

        assert 2700 <= distance <= 2800, \
            f"Hawaii-Kamchatka distance should be 2,700-2,800 nm, got {distance:.0f} nm"

    def test_hawaii_to_new_zealand_distance(self):
        """
        Test distance from Hawaii to New Zealand.

        Source: 40°S, 174°E → Hawaii 21°N, 157.5°W
        Actual calculated: ~3,800-4,000 nautical miles
        """
        calc = SwellPropagationCalculator()
        distance = calc.haversine_distance(
            -40.0, 174.0,  # New Zealand
            HAWAII_LAT, HAWAII_LON
        )

        assert 3800 <= distance <= 4000, \
            f"Hawaii-New Zealand distance should be 3,800-4,000 nm, got {distance:.0f} nm"

    def test_hawaii_to_alaska_distance(self):
        """
        Test distance from Hawaii to Alaska.

        Source: 55°N, 160°W → Hawaii 21°N, 157.5°W
        Actual calculated: ~2,000-2,100 nautical miles
        """
        calc = SwellPropagationCalculator()
        distance = calc.haversine_distance(
            55.0, -160.0,  # Alaska
            HAWAII_LAT, HAWAII_LON
        )

        assert 2000 <= distance <= 2100, \
            f"Hawaii-Alaska distance should be 2,000-2,100 nm, got {distance:.0f} nm"

    def test_zero_distance_same_location(self):
        """
        Test that distance is zero for identical locations.

        Edge case: Same source and destination.
        """
        calc = SwellPropagationCalculator()
        distance = calc.haversine_distance(
            HAWAII_LAT, HAWAII_LON,
            HAWAII_LAT, HAWAII_LON
        )

        assert distance == pytest.approx(0.0, abs=0.01), \
            f"Same location should yield zero distance, got {distance:.2f} nm"

    def test_equator_to_equator_distance(self):
        """
        Test distance calculation along equator.

        Simplified geometry: 10° longitude at equator ≈ 600 nm
        """
        calc = SwellPropagationCalculator()
        distance = calc.haversine_distance(
            0.0, 0.0,    # Equator, Prime Meridian
            0.0, 10.0    # Equator, 10°E
        )

        # 10° × 60 nm/degree ≈ 600 nm
        assert 580 <= distance <= 620, \
            f"10° along equator should be ~600 nm, got {distance:.0f} nm"

    def test_dateline_crossing(self):
        """
        Test distance calculation across the International Date Line.

        Should handle longitude wraparound correctly.
        """
        calc = SwellPropagationCalculator()

        # Hawaii (157.5°W) to Tokyo (140°E)
        # -157.5° to +140° = crossing date line
        distance = calc.haversine_distance(
            35.7, 140.0,   # Tokyo
            HAWAII_LAT, HAWAII_LON
        )

        assert 3300 <= distance <= 3500, \
            f"Hawaii-Tokyo distance should be 3,300-3,500 nm, got {distance:.0f} nm"

    def test_antipodal_points_maximum_distance(self):
        """
        Test distance between nearly antipodal points.

        Maximum great circle distance is ~10,800 nm (half Earth circumference).
        Hawaii vs approximate opposite side.
        """
        calc = SwellPropagationCalculator()

        # Hawaii (21°N, 157.5°W) vs opposite side (~21°S, 22.5°E)
        distance = calc.haversine_distance(
            HAWAII_LAT, HAWAII_LON,
            -HAWAII_LAT, -HAWAII_LON + 180
        )

        # Should be close to maximum possible distance (>8000 nm)
        assert distance > 8000, \
            f"Antipodal distance should be >8,000 nm, got {distance:.0f} nm"


class TestTravelTimeCalculation:
    """Tests for swell travel time calculation."""

    def test_kamchatka_12s_swell_travel_time(self):
        """
        Test travel time from Kamchatka with 12-second period.

        Distance: ~2,740 nm
        Period: 12s → velocity ~18.2 knots
        Travel time: ~2,740 / 18.2 = ~150 hours (~6.3 days)
        """
        calc = SwellPropagationCalculator()
        travel_hours, distance_nm, velocity_kt = calc.calculate_travel_time(
            45.0, 155.0,  # Kamchatka
            12.0          # 12s period
        )

        assert 2700 <= distance_nm <= 2800, \
            f"Distance should be 2,700-2,800 nm, got {distance_nm:.0f} nm"

        assert 17.5 <= velocity_kt <= 18.5, \
            f"Velocity should be 17.5-18.5 knots, got {velocity_kt:.1f} kt"

        assert 145 <= travel_hours <= 160, \
            f"Travel time should be 145-160 hours, got {travel_hours:.1f} hours"

    def test_new_zealand_15s_swell_travel_time(self):
        """
        Test travel time from New Zealand with 15-second long-period swell.

        Distance: ~3,900 nm
        Period: 15s → velocity ~22.8 knots
        Travel time: ~3,900 / 22.8 = ~171 hours (~7.1 days)
        """
        calc = SwellPropagationCalculator()
        travel_hours, distance_nm, velocity_kt = calc.calculate_travel_time(
            -40.0, 174.0,  # New Zealand
            15.0           # 15s period
        )

        assert 3800 <= distance_nm <= 4000, \
            f"Distance should be 3,800-4,000 nm, got {distance_nm:.0f} nm"

        assert 22.0 <= velocity_kt <= 23.5, \
            f"Velocity should be 22-23.5 knots, got {velocity_kt:.1f} kt"

        assert 165 <= travel_hours <= 180, \
            f"Travel time should be 165-180 hours, got {travel_hours:.1f} hours"

    def test_alaska_10s_swell_travel_time(self):
        """
        Test travel time from Alaska with 10-second short-period swell.

        Distance: ~2,045 nm
        Period: 10s → velocity ~15.2 knots
        Travel time: ~2,045 / 15.2 = ~135 hours (~5.6 days)
        """
        calc = SwellPropagationCalculator()
        travel_hours, distance_nm, velocity_kt = calc.calculate_travel_time(
            55.0, -160.0,  # Alaska
            10.0           # 10s period
        )

        assert 2000 <= distance_nm <= 2100, \
            f"Distance should be 2,000-2,100 nm, got {distance_nm:.0f} nm"

        assert 14.5 <= velocity_kt <= 16.0, \
            f"Velocity should be 14.5-16 knots, got {velocity_kt:.1f} kt"

        assert 130 <= travel_hours <= 145, \
            f"Travel time should be 130-145 hours, got {travel_hours:.1f} hours"

    def test_zero_distance_zero_travel_time(self):
        """
        Test that zero distance yields zero travel time.

        Edge case: Swell generated at destination.
        """
        calc = SwellPropagationCalculator()
        travel_hours, distance_nm, velocity_kt = calc.calculate_travel_time(
            HAWAII_LAT, HAWAII_LON,  # Source at Hawaii
            12.0                      # 12s period
        )

        assert distance_nm == pytest.approx(0.0, abs=0.01), \
            "Zero distance expected"

        assert travel_hours == pytest.approx(0.0, abs=0.01), \
            "Zero travel time expected"

    def test_custom_target_location(self):
        """
        Test travel time to custom target (not Hawaii).

        Verify function works with non-default target location.
        """
        calc = SwellPropagationCalculator()

        # Kamchatka to California (35°N, 120°W)
        travel_hours, distance_nm, velocity_kt = calc.calculate_travel_time(
            45.0, 155.0,   # Kamchatka
            12.0,          # 12s period
            target_lat=35.0,
            target_lon=-120.0
        )

        # Distance Kamchatka to California should be greater than to Hawaii
        assert 3700 <= distance_nm <= 3900, \
            f"Kamchatka-California should be 3,700-3,900 nm, got {distance_nm:.0f} nm"

        # Travel time should be proportional
        assert 200 <= travel_hours <= 220, \
            f"Travel time should be 200-220 hours, got {travel_hours:.1f} hours"


class TestArrivalCalculation:
    """Tests for swell arrival time calculation with datetime arithmetic."""

    def test_kamchatka_arrival_datetime(self):
        """
        Test arrival time calculation for Kamchatka swell.

        Based on Pat Caldwell's Oct 8, 2025 forecast:
        - Generation: Oct 8, 12:00 HST
        - Expected arrival: Oct 12 morning (~4 days later)
        - Using 16s long-period = faster travel (~3.4 days actual)
        """
        calc = SwellPropagationCalculator()

        generation_time = datetime(2025, 10, 8, 12, 0)  # Oct 8, 12:00

        arrival_time, details = calc.calculate_arrival(
            45.0, 155.0,  # Kamchatka
            16.0,         # 16s long-period swell
            generation_time
        )

        # Verify arrival is in the future
        assert arrival_time > generation_time, \
            "Arrival should be after generation"

        # Verify arrival is ~3-5 days later (16s period = ~24 kt velocity)
        delta = arrival_time - generation_time
        assert 3.0 <= delta.days <= 5.0, \
            f"Arrival should be 3-5 days later, got {delta.days} days"

        # Check details dictionary structure
        assert 'source_location' in details
        assert 'target_location' in details
        assert 'distance_nm' in details
        assert 'period_seconds' in details
        assert 'group_velocity_knots' in details
        assert 'travel_time_hours' in details
        assert 'generation_time' in details
        assert 'arrival_time' in details

        # Verify ISO format timestamps
        assert 'T' in details['generation_time']
        assert 'T' in details['arrival_time']

    def test_new_zealand_arrival_datetime(self):
        """
        Test arrival time for New Zealand swell.

        Southern Hemisphere swell with 15s period.
        Distance ~3,900 nm, velocity ~22.8 kt = ~7.1 days travel
        """
        calc = SwellPropagationCalculator()

        generation_time = datetime(2025, 6, 15, 6, 0)  # June 15, 06:00

        arrival_time, details = calc.calculate_arrival(
            -40.0, 174.0,  # New Zealand
            15.0,          # 15s period
            generation_time
        )

        # Verify arrival timing (~6-8 days for long distance)
        delta = arrival_time - generation_time
        assert 6.0 <= delta.days <= 8.0, \
            f"Arrival should be 6-8 days later, got {delta.days} days"

        # Verify details match input
        assert details['source_location']['lat'] == -40.0
        assert details['source_location']['lon'] == 174.0
        assert details['period_seconds'] == 15.0

    def test_immediate_arrival_zero_distance(self):
        """
        Test arrival time when swell is already at destination.

        Edge case: Zero travel time.
        """
        calc = SwellPropagationCalculator()

        generation_time = datetime(2025, 10, 10, 10, 0)

        arrival_time, details = calc.calculate_arrival(
            HAWAII_LAT, HAWAII_LON,  # Source at Hawaii
            12.0,
            generation_time
        )

        # Arrival should be essentially immediate
        delta = arrival_time - generation_time
        assert delta.total_seconds() < 1.0, \
            f"Arrival should be immediate, got {delta.total_seconds():.1f} seconds delay"

        assert details['travel_time_hours'] == pytest.approx(0.0, abs=0.01)

    def test_arrival_with_custom_target(self):
        """
        Test arrival calculation to custom target location.

        Verify non-default target works correctly.
        """
        calc = SwellPropagationCalculator()

        generation_time = datetime(2025, 10, 1, 0, 0)

        arrival_time, details = calc.calculate_arrival(
            45.0, 155.0,      # Kamchatka
            12.0,             # 12s period
            generation_time,
            target_lat=35.0,  # California
            target_lon=-120.0
        )

        # Verify custom target is recorded
        assert details['target_location']['lat'] == 35.0
        assert details['target_location']['lon'] == -120.0

        # Verify arrival is in the future
        assert arrival_time > generation_time


class TestPeriodEstimation:
    """Tests for empirical period estimation from storm characteristics."""

    def test_storm_force_winds_base_period(self):
        """
        Test period estimation for storm-force winds (50 knots).

        50 knots → ~25 m/s → base period ~10s
        With default adjustments: 8-20s range
        """
        calc = SwellPropagationCalculator()
        period = calc.estimate_period_from_storm(50.0)

        assert 8.0 <= period <= 20.0, \
            f"Period should be in 8-20s range, got {period:.1f}s"

    def test_moderate_winds_base_period(self):
        """
        Test period estimation for moderate winds (30 knots).

        30 knots → ~15 m/s → base period ~6s → clamped to 8s minimum
        """
        calc = SwellPropagationCalculator()
        period = calc.estimate_period_from_storm(30.0)

        assert period >= 8.0, \
            f"Period should be >=8s (minimum), got {period:.1f}s"

    def test_hurricane_force_winds_base_period(self):
        """
        Test period estimation for hurricane-force winds (70 knots).

        70 knots → ~36 m/s → base period ~14s
        """
        calc = SwellPropagationCalculator()
        period = calc.estimate_period_from_storm(70.0)

        assert 12.0 <= period <= 20.0, \
            f"Hurricane winds should yield 12-20s period, got {period:.1f}s"

    def test_large_fetch_increases_period(self):
        """
        Test that large fetch length increases estimated period.

        Longer fetch allows longer wavelengths to develop.
        """
        calc = SwellPropagationCalculator()

        # Same wind speed, different fetch
        short_fetch_period = calc.estimate_period_from_storm(50.0, fetch_length_nm=100.0)
        long_fetch_period = calc.estimate_period_from_storm(50.0, fetch_length_nm=1000.0)

        assert long_fetch_period > short_fetch_period, \
            f"Long fetch should yield longer period: {long_fetch_period:.1f}s vs {short_fetch_period:.1f}s"

        # Difference should be meaningful (at least 1 second)
        assert long_fetch_period - short_fetch_period >= 1.0, \
            f"Fetch should significantly affect period, got {long_fetch_period - short_fetch_period:.1f}s difference"

    def test_long_duration_increases_period(self):
        """
        Test that long storm duration increases estimated period.

        Longer duration = more fully developed seas.
        """
        calc = SwellPropagationCalculator()

        # Same wind speed, different duration
        short_duration_period = calc.estimate_period_from_storm(50.0, duration_hours=12.0)
        long_duration_period = calc.estimate_period_from_storm(50.0, duration_hours=72.0)

        assert long_duration_period > short_duration_period, \
            f"Long duration should yield longer period: {long_duration_period:.1f}s vs {short_duration_period:.1f}s"

    def test_combined_fetch_and_duration_effects(self):
        """
        Test combined effects of large fetch and long duration.

        Both factors should compound to produce longest periods.
        """
        calc = SwellPropagationCalculator()

        # Base case: no fetch/duration specified
        base_period = calc.estimate_period_from_storm(50.0)

        # Enhanced case: large fetch + long duration
        enhanced_period = calc.estimate_period_from_storm(
            50.0,
            fetch_length_nm=800.0,
            duration_hours=72.0
        )

        assert enhanced_period > base_period, \
            "Enhanced conditions should yield longer period"

        # Should approach upper limit (20s) but not exceed it
        assert enhanced_period <= 20.0, \
            f"Period should be clamped at 20s, got {enhanced_period:.1f}s"

    def test_period_clamped_to_minimum_8s(self):
        """
        Test that estimated period is clamped to minimum 8s.

        Even weak winds should yield at least short-period swell.
        """
        calc = SwellPropagationCalculator()

        # Very weak winds
        period = calc.estimate_period_from_storm(15.0)

        assert period == 8.0, \
            f"Minimum period should be 8s, got {period:.1f}s"

    def test_period_clamped_to_maximum_20s(self):
        """
        Test that estimated period is clamped to maximum 20s.

        Even extreme conditions should not exceed 20s limit.
        """
        calc = SwellPropagationCalculator()

        # Extreme winds with massive fetch and duration
        period = calc.estimate_period_from_storm(
            100.0,
            fetch_length_nm=2000.0,
            duration_hours=120.0
        )

        assert period == 20.0, \
            f"Maximum period should be 20s, got {period:.1f}s"

    @pytest.mark.parametrize("wind_speed,expected_range", [
        (30.0, (8.0, 9.0)),     # Moderate winds (clamped to minimum)
        (40.0, (8.0, 10.0)),    # Fresh gale
        (50.0, (10.0, 13.0)),   # Storm force
        (60.0, (12.0, 16.0)),   # Violent storm
        (70.0, (14.0, 20.0)),   # Hurricane force
    ])
    def test_period_estimation_ranges(self, wind_speed, expected_range):
        """
        Test period estimation across various wind speeds.

        Parametrized test for realistic wind speed scenarios.
        """
        calc = SwellPropagationCalculator()
        period = calc.estimate_period_from_storm(wind_speed)

        min_period, max_period = expected_range
        assert min_period <= period <= max_period, \
            f"Wind speed {wind_speed}kt should yield {min_period}-{max_period}s, got {period:.1f}s"


class TestIntegrationScenarios:
    """Integration tests for realistic swell propagation scenarios."""

    def test_pat_caldwell_kamchatka_forecast(self):
        """
        Test realistic Kamchatka swell scenario from Pat Caldwell's forecast.

        From Oct 8, 2025 forecast:
        - Storm location: ~45°N, 155°E
        - Storm-force winds (50+ knots)
        - Large fetch over multiple days
        - Expected arrival: Sunday morning Oct 12
        """
        calc = SwellPropagationCalculator()

        # Estimate period from storm characteristics
        period = calc.estimate_period_from_storm(
            wind_speed_kt=50.0,
            fetch_length_nm=500.0,
            duration_hours=72.0
        )

        # Period should be in long-period range (may hit 20s cap)
        assert 16.0 <= period <= 20.0, \
            f"Kamchatka storm should produce long-period swell (16-20s), got {period:.1f}s"

        # Calculate arrival
        generation_time = datetime(2025, 10, 8, 12, 0)
        arrival_time, details = calc.calculate_arrival(
            45.0, 155.0,
            period,
            generation_time
        )

        # Verify arrival is Sunday (Oct 12, day 6 of week, 0=Monday)
        assert arrival_time.weekday() == 6, \
            f"Pat predicted Sunday arrival, calculation shows {arrival_time.strftime('%A')}"

        # Verify arrival date is Oct 12
        assert arrival_time.month == 10 and arrival_time.day == 12, \
            f"Expected Oct 12 arrival, got {arrival_time.strftime('%b %d')}"

    def test_southern_hemisphere_winter_swell(self):
        """
        Test realistic Southern Hemisphere winter swell scenario.

        New Zealand storms during SH winter produce powerful long-period swells.
        """
        calc = SwellPropagationCalculator()

        # Powerful Southern Ocean storm
        period = calc.estimate_period_from_storm(
            wind_speed_kt=60.0,
            fetch_length_nm=700.0,
            duration_hours=60.0
        )

        # Should produce long-period swell
        assert period >= 15.0, \
            f"Southern Ocean storm should produce long-period swell (15+s), got {period:.1f}s"

        # Calculate arrival from New Zealand
        generation_time = datetime(2025, 6, 20, 0, 0)
        arrival_time, details = calc.calculate_arrival(
            -40.0, 174.0,
            period,
            generation_time
        )

        # Verify reasonable travel time (~6-8 days for long distance)
        travel_days = details['travel_time_hours'] / 24
        assert 5.0 <= travel_days <= 8.0, \
            f"Travel time should be 5-8 days, got {travel_days:.1f} days"

    def test_short_period_local_swell(self):
        """
        Test short-period swell from relatively local source (Alaska).

        Shorter fetch and distance = shorter period and faster arrival.
        """
        calc = SwellPropagationCalculator()

        # Alaska storm with moderate characteristics
        period = calc.estimate_period_from_storm(
            wind_speed_kt=40.0,
            fetch_length_nm=300.0,
            duration_hours=36.0
        )

        # Should produce mid-period swell
        assert 10.0 <= period <= 14.0, \
            f"Alaska storm should produce mid-period swell (10-14s), got {period:.1f}s"

        # Calculate arrival from Alaska
        generation_time = datetime(2025, 11, 15, 12, 0)
        arrival_time, details = calc.calculate_arrival(
            55.0, -160.0,
            period,
            generation_time
        )

        # Shorter distance = faster arrival (~4-6 days)
        travel_days = details['travel_time_hours'] / 24
        assert 4.0 <= travel_days <= 6.0, \
            f"Alaska swell should arrive in 4-6 days, got {travel_days:.1f} days"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
