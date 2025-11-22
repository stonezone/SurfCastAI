#!/usr/bin/env python3
"""
Demo script for presenting SurfCastAI forecasts.
"""

import os
import sys
import json
from pathlib import Path
import webbrowser

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def show_forecast():
    """Show the sample forecast in the browser."""
    forecast_path = Path('./output/sample_forecast.html')
    analysis_path = Path('./output/gpt41_analysis.txt')
    forecast_data_path = Path('./output/forecast_data.json')

    # Check if files exist
    files_exist = all([
        forecast_path.exists(),
        analysis_path.exists(),
        forecast_data_path.exists()
    ])

    if not files_exist:
        print("\nError: Sample forecast files not found.")
        print("Please make sure the following files exist:")
        print(f"- {forecast_path}")
        print(f"- {analysis_path}")
        print(f"- {forecast_data_path}")
        return 1

    # Show output locations
    print("\nSurfCastAI Forecast Demo")
    print("\nForecast files:")
    print(f"- HTML: {os.path.abspath(forecast_path)}")
    print(f"- JSON: {os.path.abspath(forecast_data_path)}")
    print(f"- Analysis: {os.path.abspath(analysis_path)}")

    # Open HTML in browser
    try:
        print("\nOpening forecast in your default browser...")
        webbrowser.open(f"file://{os.path.abspath(forecast_path)}")
        print("\nForecast displayed successfully!")
    except Exception as e:
        print(f"\nError opening browser: {e}")
        print(f"Please open {os.path.abspath(forecast_path)} manually.")

    # Open analysis file
    try:
        with open(analysis_path, 'r') as f:
            analysis = f.read()

        print("\nGPT-4.1 Analysis:")
        print("=" * 80)
        print(analysis[:500] + "...")  # Show first 500 chars
        print("=" * 80)
        print(f"\nFull analysis available at: {os.path.abspath(analysis_path)}")
    except Exception as e:
        print(f"\nError reading analysis: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(show_forecast())
