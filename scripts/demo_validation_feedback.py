#!/usr/bin/env python3
"""
Demonstration of ValidationFeedback system.

This script shows how to:
1. Query recent forecast performance from validation database
2. Generate performance reports with Pydantic models
3. Create adaptive prompt context for GPT-5

Usage:
    python scripts/demo_validation_feedback.py
    python scripts/demo_validation_feedback.py --lookback 14  # 14-day lookback
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.validation_feedback import ValidationFeedback


def main():
    """Run validation feedback demonstration."""
    parser = argparse.ArgumentParser(
        description="Demonstrate ValidationFeedback system for adaptive forecasting"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/validation.db",
        help="Path to validation database (default: data/validation.db)",
    )
    parser.add_argument(
        "--lookback", type=int, default=7, help="Number of days to analyze (default: 7)"
    )
    args = parser.parse_args()

    print("=" * 80)
    print("ValidationFeedback System Demonstration")
    print("=" * 80)
    print()

    # Initialize feedback system
    print(f"Database: {args.db_path}")
    print(f"Lookback: {args.lookback} days")
    print()

    feedback = ValidationFeedback(db_path=args.db_path, lookback_days=args.lookback)

    # Query recent performance
    print("Querying recent performance...")
    try:
        report = feedback.get_recent_performance()
    except Exception as e:
        print(f"Error querying database: {e}")
        return 1

    # Display results
    if not report.has_recent_data:
        print()
        print("No recent validation data found.")
        print("This is expected if you haven't run any validation jobs yet.")
        print()
        print("To populate the database:")
        print("  1. Generate forecasts: python src/main.py run --mode forecast")
        print("  2. Wait 24+ hours for observations")
        print("  3. Run validation: python scripts/validate_forecasts.py")
        return 0

    print()
    print("=" * 80)
    print("PERFORMANCE REPORT")
    print("=" * 80)
    print()

    # Overall metrics
    total_validations = sum(sp.validation_count for sp in report.shore_performance)
    print(f"Report Date: {report.report_date}")
    print(f"Total Validations: {total_validations}")
    print()
    print(f"Overall MAE:  {report.overall_mae:.1f} ft")
    print(f"Overall RMSE: {report.overall_rmse:.1f} ft")
    print(f"Categorical Accuracy: {int(report.overall_categorical * 100)}%")
    print()

    # Per-shore breakdown
    if report.shore_performance:
        print("Per-Shore Performance:")
        print("-" * 80)
        for sp in report.shore_performance:
            print(f"\n{sp.shore}:")
            print(f"  Validations: {sp.validation_count}")
            print(f"  MAE:  {sp.avg_mae:.1f} ft")
            print(f"  RMSE: {sp.avg_rmse:.1f} ft")
            print(f"  Bias: {sp.avg_bias:+.1f} ft", end="")

            # Add interpretation
            if sp.avg_bias > 0.5:
                print(" (overpredicting) ⚠️")
            elif sp.avg_bias < -0.5:
                print(" (underpredicting) ⚠️")
            elif abs(sp.avg_bias) < 0.2:
                print(" (well-calibrated) ✓")
            else:
                print()

            print(f"  Categorical Accuracy: {int(sp.categorical_accuracy * 100)}%")

    print()
    print("=" * 80)
    print("ADAPTIVE PROMPT CONTEXT")
    print("=" * 80)
    print()
    print("This context can be injected into GPT-5 system prompts:")
    print()

    # Generate prompt context
    context = feedback.generate_prompt_context(report)
    print(context)

    print()
    print("=" * 80)
    print("USAGE IN FORECAST ENGINE")
    print("=" * 80)
    print()
    print("To integrate this feedback into your forecast engine:")
    print()
    print("```python")
    print("from src.utils.validation_feedback import ValidationFeedback")
    print()
    print("# In your forecast generation code:")
    print("feedback = ValidationFeedback()")
    print("report = feedback.get_recent_performance()")
    print("adaptive_context = feedback.generate_prompt_context(report)")
    print()
    print("# Append to your system prompt:")
    print("system_prompt = base_prompt + '\\n\\n' + adaptive_context")
    print("```")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
