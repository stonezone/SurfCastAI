#!/usr/bin/env python3
"""
Source Scorer Demo

Demonstrates the SourceScorer functionality with example data sources.
Shows how different tiers and data quality affect reliability scores.
"""

from datetime import datetime, timezone, timedelta
from src.processing.source_scorer import SourceScorer, SourceTier


def main():
    """Run source scorer demonstration."""
    print("=" * 80)
    print("SurfCastAI Source Scorer Demo")
    print("=" * 80)
    print()

    # Initialize scorer
    scorer = SourceScorer()
    print("Initialized SourceScorer with default weights:")
    print(f"  - Source Tier: {scorer.weights.source_tier:.0%}")
    print(f"  - Data Freshness: {scorer.weights.data_freshness:.0%}")
    print(f"  - Completeness: {scorer.weights.completeness:.0%}")
    print(f"  - Historical Accuracy: {scorer.weights.historical_accuracy:.0%}")
    print()

    # Demo 1: Perfect Tier 1 Source (NDBC Buoy)
    print("-" * 80)
    print("Demo 1: Perfect Tier 1 Source (NDBC Buoy)")
    print("-" * 80)

    now = datetime.now(timezone.utc)
    ndbc_data = {
        'source': 'ndbc',
        'station_id': '51001',
        'wave_height': 2.5,
        'dominant_period': 12.0,
        'wave_direction': 315.0,
        'wind_speed': 5.0,
        'wind_direction': 45.0,
        'timestamp': now.isoformat()
    }

    score = scorer.score_single_source('ndbc', ndbc_data, 'buoy')
    print_score_details(score)
    print()

    # Demo 2: Tier 2 Research Source (PacIOOS SWAN Model)
    print("-" * 80)
    print("Demo 2: Tier 2 Research Source (PacIOOS SWAN Model)")
    print("-" * 80)

    swan_data = {
        'model_id': 'swan',
        'wave_height': 3.0,
        'wave_period': 12.0,
        'wave_direction': 270.0,
        'run_time': now.isoformat(),
        'forecast_hour': 24,
        'points': []
    }

    score = scorer.score_single_source('swan', swan_data, 'model')
    print_score_details(score)
    print()

    # Demo 3: Tier 4 Commercial API (Stormglass)
    print("-" * 80)
    print("Demo 3: Tier 4 Commercial API (Stormglass)")
    print("-" * 80)

    stormglass_data = {
        'provider': 'stormglass',
        'wave_height': 2.0,
        'wave_period': 10.0,
        'wave_direction': 280.0,
        'timestamp': now.isoformat()
    }

    score = scorer.score_single_source('stormglass', stormglass_data, 'model')
    print_score_details(score)
    print()

    # Demo 4: Tier 5 Surf Site (Surfline)
    print("-" * 80)
    print("Demo 4: Tier 5 Surf Site (Surfline)")
    print("-" * 80)

    surfline_data = {
        'source': 'surfline',
        'wave_height': 4.0,
        'timestamp': now.isoformat()
    }

    score = scorer.score_single_source('surfline', surfline_data, 'buoy')
    print_score_details(score)
    print()

    # Demo 5: Degraded Data Quality (Old + Incomplete)
    print("-" * 80)
    print("Demo 5: Degraded Data Quality (12 hours old, incomplete)")
    print("-" * 80)

    twelve_hours_ago = now - timedelta(hours=12)
    degraded_data = {
        'source': 'ndbc',
        'wave_height': 2.0,  # Only 2 out of 6 expected fields
        'timestamp': twelve_hours_ago.isoformat()
    }

    score = scorer.score_single_source('ndbc', degraded_data, 'buoy')
    print_score_details(score)
    print()

    # Demo 6: Multiple Sources Comparison
    print("=" * 80)
    print("Demo 6: Multiple Sources Comparison")
    print("=" * 80)

    fusion_data = {
        'buoy_data': [ndbc_data],
        'weather_data': [{
            'provider': 'nws',
            'temperature': 25.0,
            'wind_speed': 10.0,
            'wind_direction': 90.0,
            'forecast_periods': [],
            'timestamp': now.isoformat()
        }],
        'model_data': [swan_data, stormglass_data]
    }

    scores = scorer.score_sources(fusion_data)

    print(f"\nScored {len(scores)} sources:\n")

    # Sort by overall score
    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1].overall_score,
        reverse=True
    )

    print(f"{'Source':<20} {'Tier':<10} {'Overall':<10} {'Tier':<8} {'Fresh':<8} {'Complete':<10}")
    print("-" * 80)

    for source_id, score in sorted_scores:
        print(
            f"{source_id:<20} "
            f"{score.tier.name:<10} "
            f"{score.overall_score:.3f}      "
            f"{score.tier_score:.2f}     "
            f"{score.freshness_score:.2f}     "
            f"{score.completeness_score:.2f}"
        )

    print()
    print("=" * 80)
    print("Key Insights:")
    print("=" * 80)
    print("1. Tier 1 sources (NOAA) score highest even with same data quality")
    print("2. Data freshness significantly impacts scores (12h old = ~50% fresh score)")
    print("3. Completeness affects scores (missing fields reduce reliability)")
    print("4. Higher tier sources provide more confidence in forecasts")
    print("5. All scores are transparent and auditable in logs")
    print()


def print_score_details(score):
    """Print detailed score breakdown."""
    print(f"Source: {score.source_name}")
    print(f"Tier: {score.tier.name} ({score.tier.value})")
    print()
    print(f"Score Breakdown:")
    print(f"  Tier Score:       {score.tier_score:.3f}  (weight: 50%)")
    print(f"  Freshness:        {score.freshness_score:.3f}  (weight: 20%)")
    print(f"  Completeness:     {score.completeness_score:.3f}  (weight: 20%)")
    print(f"  Accuracy:         {score.accuracy_score:.3f}  (weight: 10%)")
    print(f"  " + "-" * 50)
    print(f"  Overall Score:    {score.overall_score:.3f}")
    print()

    # Visual score bar
    bar_length = int(score.overall_score * 50)
    bar = "█" * bar_length + "░" * (50 - bar_length)
    print(f"  [{bar}] {score.overall_score:.1%}")
    print()

    # Interpretation
    if score.overall_score >= 0.9:
        interpretation = "EXCELLENT - Highly reliable source"
    elif score.overall_score >= 0.7:
        interpretation = "GOOD - Reliable source"
    elif score.overall_score >= 0.5:
        interpretation = "FAIR - Moderately reliable"
    elif score.overall_score >= 0.3:
        interpretation = "POOR - Low reliability"
    else:
        interpretation = "VERY POOR - Minimal reliability"

    print(f"  Interpretation: {interpretation}")


if __name__ == '__main__':
    main()
