"""
Example: Parsing Forecast Predictions

This example demonstrates how to use the ForecastParser to extract
structured predictions from forecast markdown files for validation.

Usage:
    python examples/parse_forecast_example.py
    python examples/parse_forecast_example.py <forecast_file.md>
    python examples/parse_forecast_example.py <forecast_directory>

Author: SurfCastAI Team
Created: October 2025
"""

import sys
import json
from pathlib import Path
from src.validation.forecast_parser import ForecastParser


def format_prediction(pred):
    """Format a prediction for display"""
    return (
        f"  {pred.shore} - Day {pred.day_number} "
        f"({pred.valid_time.strftime('%Y-%m-%d')})\n"
        f"    Height: {pred.height_min}-{pred.height_max} ft Hawaiian "
        f"(avg: {pred.height:.1f} ft)\n"
        f"    Period: {pred.period_min}-{pred.period_max} s "
        f"(avg: {pred.period:.1f} s)" if pred.period else "    Period: N/A\n"
        f"    Direction: {pred.direction or 'N/A'}\n"
        f"    Category: {pred.category}\n"
        f"    Confidence: {pred.confidence:.2f}\n"
    )


def parse_single_file(file_path: Path):
    """Parse a single forecast file and display results"""
    parser = ForecastParser()

    print(f"\nParsing: {file_path.name}")
    print("=" * 70)

    try:
        predictions = parser.parse_forecast_file(file_path)

        if not predictions:
            print("No predictions extracted from this file.")
            return

        print(f"\nExtracted {len(predictions)} predictions:")
        print(f"Forecast issued: {predictions[0].forecast_time.strftime('%Y-%m-%d %H:%M')}")

        # Group by shore
        shores = {}
        for pred in predictions:
            if pred.shore not in shores:
                shores[pred.shore] = []
            shores[pred.shore].append(pred)

        # Display by shore
        for shore, shore_preds in shores.items():
            print(f"\n{shore} ({len(shore_preds)} predictions):")
            print("-" * 70)

            for pred in sorted(shore_preds, key=lambda p: (p.day_number, p.height)):
                print(format_prediction(pred))

        # Summary statistics
        print("\nSummary Statistics:")
        print("-" * 70)
        avg_confidence = sum(p.confidence for p in predictions) / len(predictions)
        print(f"Average confidence: {avg_confidence:.2f}")

        with_period = sum(1 for p in predictions if p.period is not None)
        print(f"Predictions with period data: {with_period}/{len(predictions)} "
              f"({100*with_period/len(predictions):.1f}%)")

        with_direction = sum(1 for p in predictions if p.direction is not None)
        print(f"Predictions with direction: {with_direction}/{len(predictions)} "
              f"({100*with_direction/len(predictions):.1f}%)")

    except Exception as e:
        print(f"Error parsing file: {e}")
        import traceback
        traceback.print_exc()


def parse_directory(directory: Path):
    """Parse all forecast files in a directory"""
    parser = ForecastParser()

    print(f"\nParsing forecast directory: {directory}")
    print("=" * 70)

    try:
        results = parser.parse_multiple_forecasts(directory)

        if not results:
            print("No forecast files found in directory.")
            return

        print(f"\nFound {len(results)} forecast files:")

        total_predictions = 0
        successful_files = 0

        for filename, predictions in sorted(results.items()):
            status = "OK" if predictions else "FAILED"
            print(f"  [{status}] {filename}: {len(predictions)} predictions")

            if predictions:
                successful_files += 1
                total_predictions += len(predictions)

        print(f"\nSummary:")
        print(f"  Successfully parsed: {successful_files}/{len(results)} files")
        print(f"  Total predictions: {total_predictions}")

        if successful_files > 0:
            avg_per_file = total_predictions / successful_files
            print(f"  Average per file: {avg_per_file:.1f} predictions")

    except Exception as e:
        print(f"Error parsing directory: {e}")
        import traceback
        traceback.print_exc()


def export_to_json(file_path: Path, output_path: Path):
    """Parse a forecast and export to JSON"""
    parser = ForecastParser()

    try:
        predictions = parser.parse_forecast_file(file_path)

        # Convert to dictionaries
        data = {
            'forecast_file': file_path.name,
            'parsed_at': predictions[0].forecast_time.isoformat() if predictions else None,
            'prediction_count': len(predictions),
            'predictions': [p.to_dict() for p in predictions]
        }

        # Write JSON
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\nExported {len(predictions)} predictions to: {output_path}")

    except Exception as e:
        print(f"Error exporting to JSON: {e}")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

        if not path.exists():
            print(f"Error: Path does not exist: {path}")
            sys.exit(1)

        if path.is_file():
            parse_single_file(path)

            # Optionally export to JSON
            if '--json' in sys.argv or '-j' in sys.argv:
                output_path = path.parent / f"{path.stem}_parsed.json"
                export_to_json(path, output_path)

        elif path.is_dir():
            parse_directory(path)

        else:
            print(f"Error: Path is neither a file nor directory: {path}")
            sys.exit(1)

    else:
        # Default: find and parse the most recent forecast
        output_dir = Path('output')

        if not output_dir.exists():
            print("Error: output/ directory not found")
            print("\nUsage:")
            print("  python examples/parse_forecast_example.py <forecast_file.md>")
            print("  python examples/parse_forecast_example.py <forecast_directory>")
            sys.exit(1)

        # Find most recent forecast
        forecast_dirs = sorted(
            [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('forecast_')],
            reverse=True
        )

        if not forecast_dirs:
            print("No forecast directories found in output/")
            sys.exit(1)

        # Get the most recent forecast file
        latest_dir = forecast_dirs[0]
        md_files = list(latest_dir.glob('forecast_*.md'))

        if not md_files:
            print(f"No markdown files found in {latest_dir}")
            sys.exit(1)

        parse_single_file(md_files[0])


if __name__ == '__main__':
    main()
