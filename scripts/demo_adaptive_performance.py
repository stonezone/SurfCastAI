#!/usr/bin/env python3
"""Demo script: Adaptive performance query system.

This script demonstrates the end-to-end workflow for extracting recent forecast
performance metrics and injecting them into prompts for adaptive bias correction.

Features demonstrated:
1. Database setup with performance index
2. Synthetic validation data generation
3. Performance metric extraction (3 optimized queries)
4. Human-readable context generation for prompt injection
5. Query execution time benchmarking

Usage:
    python scripts/demo_adaptive_performance.py
    python scripts/demo_adaptive_performance.py --validations 100 --benchmark
"""
import argparse
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from src.validation.performance import PerformanceAnalyzer


def create_demo_database(db_path: Path) -> None:
    """Create demo database with schema and index.

    Args:
        db_path: Path to create database at
    """
    print(f"📦 Creating demo database: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY,
                forecast_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP NOT NULL,
                model_version TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY,
                forecast_id TEXT NOT NULL,
                shore TEXT NOT NULL,
                forecast_time TIMESTAMP NOT NULL,
                valid_time TIMESTAMP NOT NULL,
                predicted_height REAL,
                predicted_period REAL,
                predicted_direction TEXT,
                predicted_category TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS actuals (
                id INTEGER PRIMARY KEY,
                buoy_id TEXT NOT NULL,
                observation_time TIMESTAMP NOT NULL,
                wave_height REAL,
                dominant_period REAL
            );

            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY,
                forecast_id TEXT NOT NULL,
                prediction_id INTEGER NOT NULL,
                actual_id INTEGER NOT NULL,
                validated_at TIMESTAMP NOT NULL,
                height_error REAL,
                period_error REAL,
                direction_error REAL,
                category_match BOOLEAN,
                mae REAL,
                rmse REAL
            );

            -- Performance-critical index
            CREATE INDEX IF NOT EXISTS idx_validations_validated_at ON validations(validated_at);
        """)

    print("   ✅ Database created with performance index")


def generate_synthetic_data(db_path: Path, num_validations: int = 50) -> None:
    """Generate synthetic validation data with realistic patterns.

    North Shore: Overprediction bias (+1.2ft average)
    South Shore: Balanced (0.0ft bias)
    West Shore: Slight underprediction (-0.5ft average)
    East Shore: Balanced with higher variance

    Args:
        db_path: Path to database
        num_validations: Number of validation records to generate
    """
    print(f"🌊 Generating {num_validations} synthetic validations...")

    shores = ['North Shore', 'South Shore', 'West Shore', 'East Shore']
    shore_biases = {
        'North Shore': 1.2,   # Overpredicting
        'South Shore': 0.0,   # Balanced
        'West Shore': -0.5,   # Underpredicting
        'East Shore': 0.1     # Mostly balanced
    }

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Insert forecast
        cursor.execute("""
            INSERT INTO forecasts (forecast_id, created_at, model_version)
            VALUES ('demo-forecast-001', ?, 'gpt-5-mini')
        """, (datetime.now().isoformat(),))

        # Generate validations over last 10 days
        for i in range(num_validations):
            shore = shores[i % len(shores)]
            bias = shore_biases[shore]

            # Vary timestamps across last 10 days
            days_ago = (i % 10) + 1
            timestamp = datetime.now() - timedelta(days=days_ago)

            # Insert prediction
            predicted_height = 6.0  # Baseline forecast
            cursor.execute("""
                INSERT INTO predictions (
                    forecast_id, shore, forecast_time, valid_time,
                    predicted_height, predicted_period, predicted_direction,
                    predicted_category, confidence
                ) VALUES ('demo-forecast-001', ?, ?, ?, ?, 12.0, 'NW', 'moderate', 0.75)
            """, (shore, timestamp.isoformat(), timestamp.isoformat(), predicted_height))
            pred_id = cursor.lastrowid

            # Insert actual observation
            actual_height = predicted_height - bias + (i % 5 - 2) * 0.2  # Add noise
            cursor.execute("""
                INSERT INTO actuals (buoy_id, observation_time, wave_height, dominant_period)
                VALUES (?, ?, ?, 12.5)
            """, (f"5120{i % 3}", timestamp.isoformat(), actual_height))
            actual_id = cursor.lastrowid

            # Insert validation
            height_error = predicted_height - actual_height
            mae = abs(height_error)
            rmse = mae * 1.15  # Simplified
            category_match = abs(height_error) < 1.5

            cursor.execute("""
                INSERT INTO validations (
                    forecast_id, prediction_id, actual_id, validated_at,
                    height_error, period_error, direction_error, category_match, mae, rmse
                ) VALUES ('demo-forecast-001', ?, ?, ?, ?, 0.3, NULL, ?, ?, ?)
            """, (pred_id, actual_id, timestamp.isoformat(), height_error,
                  category_match, mae, rmse))

        conn.commit()

    print(f"   ✅ Generated {num_validations} validations across 4 shores")
    print(f"   📊 Shore biases: North +1.2ft, South 0.0ft, West -0.5ft, East +0.1ft")


def run_performance_queries(db_path: Path, days: int = 7, benchmark: bool = False) -> Dict[str, Any]:
    """Execute performance queries and optionally benchmark.

    Args:
        db_path: Path to database
        days: Lookback window (default 7 days)
        benchmark: If True, run queries multiple times for timing

    Returns:
        Performance data dictionary
    """
    analyzer = PerformanceAnalyzer(str(db_path))

    print(f"\n📈 Running performance queries (window={days} days)...")

    if benchmark:
        print("   🔬 Benchmarking query execution time (10 iterations)...")
        times = []
        for _ in range(10):
            start = time.time()
            result = analyzer.get_recent_performance(days=days)
            elapsed_ms = (time.time() - start) * 1000
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"   ⏱️  Query time: {avg_time:.2f}ms average ({min_time:.2f}ms min, {max_time:.2f}ms max)")
    else:
        result = analyzer.get_recent_performance(days=days)

    return result


def display_results(perf_data: Dict[str, Any]) -> None:
    """Display performance results in human-readable format.

    Args:
        perf_data: Output from get_recent_performance()
    """
    if not perf_data['has_data']:
        print(f"\n❌ Insufficient data: {perf_data['metadata']['reason']}")
        return

    print("\n" + "=" * 70)
    print("PERFORMANCE ANALYSIS RESULTS")
    print("=" * 70)

    # Overall metrics
    overall = perf_data['overall']
    print(f"\n📊 Overall Performance ({overall['total_validations']} validations):")
    print(f"   MAE:  {overall['overall_mae']}ft")
    print(f"   RMSE: {overall['overall_rmse']}ft")
    print(f"   Categorical Accuracy: {overall['overall_categorical']*100:.1f}%")
    print(f"   System Bias: {overall['avg_bias']:+.2f}ft")

    # Shore-level breakdown
    print("\n🏖️  Performance by Shore:")
    for shore, metrics in perf_data['by_shore'].items():
        if metrics is None:
            print(f"   {shore:15} No validations")
        else:
            bias_icon = "⬆️" if metrics['avg_height_error'] > 0.5 else "⬇️" if metrics['avg_height_error'] < -0.5 else "✅"
            print(f"   {shore:15} MAE={metrics['avg_mae']:4.2f}ft  "
                  f"Bias={metrics['avg_height_error']:+.2f}ft {bias_icon}  "
                  f"Samples={metrics['validation_count']}")

    # Bias alerts
    if perf_data['bias_alerts']:
        print("\n⚠️  Bias Alerts (Significant Systematic Error):")
        for alert in perf_data['bias_alerts']:
            icon = "📈" if alert['bias_category'] == 'OVERPREDICTING' else "📉"
            print(f"   {icon} {alert['shore']}: {alert['bias_category']} by {abs(alert['avg_bias'])}ft "
                  f"({alert['sample_size']} samples)")
    else:
        print("\n✅ No significant bias detected")

    # Metadata
    metadata = perf_data['metadata']
    print(f"\n🔍 Query Metadata:")
    print(f"   Window: {metadata['window_days']} days")
    print(f"   Timestamp: {metadata['query_timestamp']}")


def display_prompt_context(perf_data: Dict[str, Any]) -> None:
    """Display formatted context for prompt injection.

    Args:
        perf_data: Output from get_recent_performance()
    """
    analyzer = PerformanceAnalyzer("")  # Dummy path
    context = analyzer.build_performance_context(perf_data)

    if not context:
        print("\n📝 Prompt Context: (empty - insufficient data)")
        return

    print("\n" + "=" * 70)
    print("PROMPT INJECTION CONTEXT")
    print("=" * 70)
    print("\nThis context would be injected into the GPT prompt:\n")
    print(context)
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Adaptive performance query system for prompt injection"
    )
    parser.add_argument(
        '--validations',
        type=int,
        default=50,
        help='Number of synthetic validations to generate (default: 50)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Lookback window in days (default: 7)'
    )
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run query benchmarks (10 iterations)'
    )
    parser.add_argument(
        '--db-path',
        type=Path,
        default=Path('data/demo_performance.db'),
        help='Path to demo database (default: data/demo_performance.db)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("ADAPTIVE PERFORMANCE QUERY SYSTEM - DEMO")
    print("=" * 70)

    # Clean up old demo database
    if args.db_path.exists():
        print(f"🗑️  Removing old demo database: {args.db_path}")
        args.db_path.unlink()

    # Setup
    create_demo_database(args.db_path)
    generate_synthetic_data(args.db_path, num_validations=args.validations)

    # Query
    perf_data = run_performance_queries(args.db_path, days=args.days, benchmark=args.benchmark)

    # Display
    display_results(perf_data)
    display_prompt_context(perf_data)

    # Cleanup prompt
    print("\n🧹 Clean up demo database? (y/n): ", end='')
    try:
        response = input().strip().lower()
        if response == 'y':
            args.db_path.unlink()
            print(f"   ✅ Removed {args.db_path}")
        else:
            print(f"   📂 Keeping database at {args.db_path}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n   📂 Keeping database at {args.db_path}")

    print("\n✅ Demo complete!")
    print("\nNext steps:")
    print("1. Review design doc: docs/ADAPTIVE_PERFORMANCE_QUERIES.md")
    print("2. Run unit tests: pytest tests/unit/validation/test_performance.py")
    print("3. Integrate with ForecastEngine (see design doc Section 7)")


if __name__ == "__main__":
    main()
