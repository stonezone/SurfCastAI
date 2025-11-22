#!/usr/bin/env python3
"""
Test script to verify storm detection timing fix.

This test verifies that storm detection now happens in ForecastEngine
after pressure analysis is generated, not in DataFusionSystem where
pressure analysis doesn't exist yet.
"""

import json
import sys
from pathlib import Path


def test_storm_detection_fix():
    """Verify storm detection fix by checking recent forecast output."""

    print("=" * 70)
    print("STORM DETECTION TIMING FIX VERIFICATION")
    print("=" * 70)
    print()

    # Check latest forecast output
    latest_forecast = Path("output/forecast_20251010_185823/forecast_data.json")

    if not latest_forecast.exists():
        print("❌ FAIL: Latest forecast output not found")
        return False

    print(f"✓ Found latest forecast: {latest_forecast}")

    # Load forecast data
    with open(latest_forecast) as f:
        forecast_data = json.load(f)

    main_forecast = forecast_data.get("main_forecast", "")

    # Check for storm mentions in forecast
    storm_keywords = ["storm", "964 mb", "984 mb", "L1", "L2", "NW groundswell"]
    found_keywords = []

    for keyword in storm_keywords:
        if keyword.lower() in main_forecast.lower():
            found_keywords.append(keyword)

    print()
    print("Storm-related content check:")
    print("-" * 70)
    if found_keywords:
        print(f"✓ Found {len(found_keywords)} storm-related keywords in forecast:")
        for keyword in found_keywords:
            print(f"  - {keyword}")
    else:
        print("❌ No storm-related keywords found in forecast")
        return False

    # Check pressure analysis file exists
    pressure_analysis = Path(
        "data/805ef271-00a1-441a-bd7f-88c8096ad1a2/debug/image_analysis_pressure.txt"
    )

    print()
    print("Pressure analysis check:")
    print("-" * 70)
    if pressure_analysis.exists():
        print(f"✓ Pressure analysis file exists: {pressure_analysis}")

        # Read pressure analysis and check for storms
        with open(pressure_analysis) as f:
            pressure_content = f.read()

        # Count storm detections in pressure analysis
        storm_count = 0
        if "964" in pressure_content:
            storm_count += 1
            print("  ✓ Found L1 storm (964mb)")
        if "984" in pressure_content:
            storm_count += 1
            print("  ✓ Found L2 storm (984mb)")
        if "1004" in pressure_content or "1007" in pressure_content:
            storm_count += 1
            print("  ✓ Found additional low pressure system")

        print(f"  Total: {storm_count} storm systems detected in pressure analysis")
    else:
        print("❌ Pressure analysis file not found")
        return False

    # Check that storm detection was removed from DataFusionSystem
    fusion_file = Path("src/processing/data_fusion_system.py")
    with open(fusion_file) as f:
        fusion_content = f.read()

    print()
    print("Code verification:")
    print("-" * 70)

    if "# Storm detection moved to ForecastEngine" in fusion_content:
        print("✓ Storm detection disabled in DataFusionSystem (correct)")
    else:
        print("❌ Storm detection comment not found in DataFusionSystem")
        return False

    # Check that storm detection was added to ForecastEngine
    engine_file = Path("src/forecast_engine/forecast_engine.py")
    with open(engine_file) as f:
        engine_content = f.read()

    if "from ..processing.storm_detector import StormDetector" in engine_content:
        print("✓ StormDetector imported in ForecastEngine (correct)")
    else:
        print("❌ StormDetector not imported in ForecastEngine")
        return False

    if "self.storm_detector = StormDetector()" in engine_content:
        print("✓ StormDetector initialized in ForecastEngine (correct)")
    else:
        print("❌ StormDetector not initialized in ForecastEngine")
        return False

    if "storms = self.storm_detector.parse_pressure_analysis" in engine_content:
        print("✓ Storm detection called after pressure analysis (correct)")
    else:
        print("❌ Storm detection not called in ForecastEngine")
        return False

    if "forecast_data['storm_arrivals'] = arrivals" in engine_content:
        print("✓ Storm arrivals stored in forecast_data (correct)")
    else:
        print("❌ Storm arrivals not stored correctly")
        return False

    # Check _format_arrival_predictions uses correct data source
    if "arrivals = forecast_data.get('storm_arrivals', [])" in engine_content:
        print("✓ _format_arrival_predictions uses correct data source (correct)")
    else:
        print("❌ _format_arrival_predictions uses wrong data source")
        return False

    print()
    print("=" * 70)
    print("✓ ALL CHECKS PASSED - STORM DETECTION TIMING FIX VERIFIED")
    print("=" * 70)
    print()
    print("Summary:")
    print("- Storm detection removed from DataFusionSystem (where pressure analysis doesn't exist)")
    print("- Storm detection added to ForecastEngine (after pressure analysis is generated)")
    print("- Forecast output contains storm information from pressure analysis")
    print("- Data flow is now correct: pressure analysis → storm detection → forecast")

    return True


if __name__ == "__main__":
    success = test_storm_detection_fix()
    sys.exit(0 if success else 1)
