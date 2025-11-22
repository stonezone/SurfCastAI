#!/usr/bin/env python3
"""
Demo script for SpectralAnalyzer.

This script demonstrates how to use the SpectralAnalyzer to extract
multiple swell components from NDBC .spec files.

Usage:
    python scripts/demo_spectral_analyzer.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processing.spectral_analyzer import SpectralAnalyzer, analyze_spec_file


def main():
    """Demonstrate spectral analyzer usage."""
    print("=" * 80)
    print("NDBC Spectral Analyzer Demo")
    print("=" * 80)
    print()

    # Find .spec files in data directory
    data_dir = Path(__file__).parent.parent / 'data' / 'www_ndbc_noaa_gov'
    spec_files = list(data_dir.glob('*.spec'))

    if not spec_files:
        print("ERROR: No .spec files found in data directory")
        return

    print(f"Found {len(spec_files)} .spec file(s):")
    for spec_file in spec_files:
        print(f"  - {spec_file.name}")
    print()

    # Analyze each .spec file
    for spec_file in spec_files:
        print("-" * 80)
        print(f"Analyzing: {spec_file.name}")
        print("-" * 80)

        # Parse with default parameters
        result = analyze_spec_file(str(spec_file))

        if result is None:
            print("  ❌ Failed to parse file")
            continue

        # Display results
        print(f"  Buoy ID: {result.buoy_id}")
        print(f"  Timestamp: {result.timestamp}")
        print(f"  Total Energy: {result.total_energy:.2f} m²/Hz")
        print(f"  Components: {len(result.peaks)}")
        print()

        # Display dominant peak
        if result.dominant_peak:
            peak = result.dominant_peak
            print(f"  Dominant Component ({peak.component_type}):")
            print(f"    Height: {peak.height_meters:.2f}m ({peak.height_meters * 3.28084:.1f}ft)")
            print(f"    Period: {peak.period_seconds:.1f}s")
            print(f"    Direction: {peak.direction_degrees:.0f}° ({_direction_to_compass(peak.direction_degrees)})")
            print(f"    Energy: {peak.energy_density:.2f} m²/Hz")
            print(f"    Confidence: {peak.confidence:.2f}")
            print()

        # Display all peaks
        if len(result.peaks) > 1:
            print(f"  All Components ({len(result.peaks)}):")
            for i, peak in enumerate(result.peaks, 1):
                print(f"    {i}. {peak.component_type.upper()}:")
                print(f"       {peak.height_meters:.2f}m @ {peak.period_seconds:.1f}s from {peak.direction_degrees:.0f}°")
            print()

        # Display metadata
        if result.metadata:
            print(f"  Metadata:")
            if 'total_wave_height' in result.metadata:
                print(f"    Total Wave Height: {result.metadata['total_wave_height']:.2f}m")
            if 'average_period' in result.metadata:
                print(f"    Average Period: {result.metadata['average_period']:.1f}s")
            if 'mean_direction' in result.metadata:
                print(f"    Mean Direction: {result.metadata['mean_direction']:.0f}°")
            print()

    # Demonstrate custom parameters
    print("=" * 80)
    print("Custom Analysis (min_period=10.0s, max_components=3)")
    print("=" * 80)
    print()

    analyzer = SpectralAnalyzer(
        min_period=10.0,  # Only consider long-period swell
        max_components=3,  # Limit to 3 components
        min_separation_period=4.0  # Require larger period difference
    )

    for spec_file in spec_files[:1]:  # Just analyze first file
        result = analyzer.parse_spec_file(str(spec_file))

        if result:
            print(f"  {spec_file.name}: {len(result.peaks)} component(s) found")
            for peak in result.peaks:
                print(f"    - {peak.component_type}: {peak.period_seconds:.1f}s @ {peak.direction_degrees:.0f}°")
        else:
            print(f"  {spec_file.name}: Failed to parse")
        print()


def _direction_to_compass(degrees: float) -> str:
    """Convert degrees to compass direction."""
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    ix = round(degrees / 22.5) % 16
    return dirs[ix]


if __name__ == '__main__':
    main()
