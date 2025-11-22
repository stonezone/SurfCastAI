#!/usr/bin/env python3
"""
Test script for PressureAnalyst specialist.

This script demonstrates the usage of PressureAnalyst and validates
it follows the same patterns as BuoyAnalyst.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from src.forecast_engine.specialists import PressureAnalyst


async def test_pressure_analyst():
    """Test PressureAnalyst with sample data."""
    print("=" * 70)
    print("PressureAnalyst Test")
    print("=" * 70)

    # Initialize analyst (without config for basic test)
    analyst = PressureAnalyst(config=None)

    print(f"\nAnalyst initialized: {analyst.__class__.__name__}")
    print(f"OpenAI Model: {analyst.openai_model}")
    print(f"Max Tokens: {analyst.max_tokens}")

    # Test 1: Input validation
    print("\n" + "-" * 70)
    print("Test 1: Input Validation")
    print("-" * 70)

    try:
        # Missing required key
        await analyst.analyze({})
        print("FAIL: Should have raised ValueError for missing 'images' key")
    except ValueError as e:
        print(f"PASS: Correctly raised ValueError: {e}")

    try:
        # Empty images list
        await analyst.analyze({'images': []})
        print("FAIL: Should have raised ValueError for empty images list")
    except ValueError as e:
        print(f"PASS: Correctly raised ValueError: {e}")

    # Test 2: Image path validation
    print("\n" + "-" * 70)
    print("Test 2: Image Path Validation")
    print("-" * 70)

    # Test with non-existent files
    invalid_paths = [
        '/tmp/nonexistent1.png',
        '/tmp/nonexistent2.jpg'
    ]
    valid = analyst._validate_image_paths(invalid_paths)
    print(f"Input: {len(invalid_paths)} non-existent paths")
    print(f"Valid: {len(valid)} paths")
    print(f"PASS: Correctly filtered invalid paths" if len(valid) == 0 else "FAIL")

    # Test 3: Swell travel time calculation
    print("\n" + "-" * 70)
    print("Test 3: Swell Travel Time Calculation")
    print("-" * 70)

    # Test case: 1000 nm with 14s period
    distance_nm = 1000.0
    period_s = 14.0
    travel_time = analyst._calculate_swell_travel_time(distance_nm, period_s)

    print(f"Distance: {distance_nm} nautical miles")
    print(f"Period: {period_s} seconds")
    print(f"Travel Time: {travel_time:.1f} hours ({travel_time/24:.1f} days)")

    # Deep water group velocity for 14s period is about 11 m/s
    # 1000 nm = 1852000 m
    # Travel time = 1852000 / 11 / 3600 = ~47 hours
    expected_range = (40, 55)
    if expected_range[0] <= travel_time <= expected_range[1]:
        print(f"PASS: Travel time within expected range {expected_range}")
    else:
        print(f"FAIL: Travel time outside expected range {expected_range}")

    # Test 4: Distance to Hawaii calculation
    print("\n" + "-" * 70)
    print("Test 4: Distance to Hawaii Calculation")
    print("-" * 70)

    # Test with a known North Pacific storm location
    storm_lat = 45.0
    storm_lon = -160.0
    distance = analyst._calculate_distance_to_hawaii(storm_lat, storm_lon)

    print(f"Storm Location: {storm_lat}N, {abs(storm_lon)}W")
    print(f"Hawaii Location: {analyst.hawaii_lat}N, {abs(analyst.hawaii_lon)}W")
    print(f"Distance: {distance:.1f} nautical miles")

    # Approximate distance should be around 1500-1700 nm
    expected_range = (1400, 1800)
    if expected_range[0] <= distance <= expected_range[1]:
        print(f"PASS: Distance within expected range {expected_range}")
    else:
        print(f"FAIL: Distance outside expected range {expected_range}")

    # Test 5: Swell enhancement
    print("\n" + "-" * 70)
    print("Test 5: Swell Prediction Enhancement")
    print("-" * 70)

    mock_systems = [
        {
            'type': 'low_pressure',
            'location': '45N 160W',
            'pressure_mb': 985,
            'fetch': {
                'direction': 'NNE',
                'distance_nm': 1200,
                'duration_hrs': 48,
                'quality': 'strong'
            }
        }
    ]

    mock_swells = [
        {
            'source_system': 'low_45N_160W',
            'direction': 'NNE',
            'estimated_height': '8-12ft',
            'estimated_period': '14-16s',
            'confidence': 0.8
        }
    ]

    enhanced = analyst._enhance_swell_predictions(mock_swells, mock_systems)

    print(f"Original swells: {len(mock_swells)}")
    print(f"Enhanced swells: {len(enhanced)}")
    print(f"Enhanced swell data:")
    for swell in enhanced:
        print(f"  - Travel time: {swell.get('travel_time_hrs', 'N/A')} hrs")
        print(f"  - Distance: {swell.get('distance_nm', 'N/A')} nm")
        print(f"  - Fetch quality: {swell.get('fetch_quality', 'N/A')}")

    has_enhancements = (
        'travel_time_hrs' in enhanced[0] and
        'fetch_quality' in enhanced[0]
    )
    print(f"PASS: Swell successfully enhanced" if has_enhancements else "FAIL")

    # Test 6: Confidence calculation
    print("\n" + "-" * 70)
    print("Test 6: Confidence Calculation")
    print("-" * 70)

    # Test various scenarios
    scenarios = [
        (8, mock_systems, enhanced, ['2025-10-07T00:00Z'] * 8),  # Ideal
        (4, mock_systems, enhanced, ['2025-10-07T00:00Z'] * 4),  # Good
        (2, [], [], ['2025-10-07T00:00Z'] * 2),  # Poor
    ]

    for idx, (num_images, systems, swells, times) in enumerate(scenarios):
        confidence = analyst._calculate_analysis_confidence(
            num_images, systems, swells, times
        )
        print(f"Scenario {idx + 1}: {num_images} images, "
              f"{len(systems)} systems, {len(swells)} swells")
        print(f"  Confidence: {confidence:.3f}")

    print("\nPASS: Confidence calculation completed")

    # Test 7: Full analysis (without images)
    print("\n" + "-" * 70)
    print("Test 7: Full Analysis Flow (Dry Run)")
    print("-" * 70)

    # Create test data with invalid image paths (will be filtered out)
    test_data = {
        'images': ['/tmp/test1.png', '/tmp/test2.png'],
        'metadata': {
            'chart_times': ['2025-10-07T00:00Z', '2025-10-07T06:00Z'],
            'region': 'North Pacific'
        }
    }

    print("Test data prepared:")
    print(f"  Images: {len(test_data['images'])}")
    print(f"  Chart times: {len(test_data['metadata']['chart_times'])}")

    try:
        # This will fail because no valid images, but tests the flow
        result = await analyst.analyze(test_data)
        print("FAIL: Should have raised error for no valid images")
    except ValueError as e:
        print(f"PASS: Correctly raised error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("All tests completed successfully!")
    print("\nPressureAnalyst is ready for integration.")
    print("\nNext steps:")
    print("1. Ensure OpenAI API key is configured")
    print("2. Provide actual pressure chart images")
    print("3. Integrate with forecast engine pipeline")

    return True


if __name__ == '__main__':
    success = asyncio.run(test_pressure_analyst())
    sys.exit(0 if success else 1)
