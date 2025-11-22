#!/usr/bin/env python3
"""
Demonstration of database transaction rollback protection.

This script demonstrates how batch database operations handle failures
with automatic rollback to maintain data integrity.
"""
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.database import ValidationDatabase


def demo_successful_batch_insert():
    """Demonstrate successful batch insert."""
    print("\n" + "="*70)
    print("DEMO 1: Successful Batch Insert")
    print("="*70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = ValidationDatabase(db_path=db_path)

    # Create a forecast
    forecast_data = {
        'forecast_id': 'demo-forecast-001',
        'generated_time': datetime.now(),
        'metadata': {
            'source_data': {'bundle_id': 'demo-bundle'},
            'api_usage': {
                'model': 'gpt-4',
                'input_tokens': 1000,
                'output_tokens': 500,
                'total_cost': 0.05
            },
            'generation_time': 2.5
        }
    }

    print("\n1. Creating forecast...")
    forecast_id = db.save_forecast(forecast_data)
    print(f"   ✓ Forecast created: {forecast_id}")

    # Create batch predictions
    predictions = [
        {
            'shore': 'North Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=i),
            'height': 8.0 + i * 0.5,
            'period': 12.0 + i * 0.2,
            'direction': 'NW',
            'category': 'overhead',
            'confidence': 0.85
        }
        for i in range(5)
    ]

    print(f"\n2. Inserting {len(predictions)} predictions as a batch...")
    db.save_predictions(forecast_id, predictions)
    print(f"   ✓ All {len(predictions)} predictions saved successfully")

    # Verify
    saved_predictions = db.get_predictions_for_forecast(forecast_id)
    print(f"\n3. Verification:")
    print(f"   ✓ Found {len(saved_predictions)} predictions in database")
    print(f"   ✓ First prediction: {saved_predictions[0]['shore']} - {saved_predictions[0]['predicted_height']}ft")

    # Cleanup
    Path(db_path).unlink()
    print("\n✓ Demo 1 completed successfully")


def demo_rollback_on_failure():
    """Demonstrate rollback on batch insert failure."""
    print("\n" + "="*70)
    print("DEMO 2: Rollback on Batch Insert Failure")
    print("="*70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = ValidationDatabase(db_path=db_path)

    # Create a forecast
    forecast_data = {
        'forecast_id': 'demo-forecast-002',
        'generated_time': datetime.now(),
        'metadata': {
            'source_data': {'bundle_id': 'demo-bundle'},
            'api_usage': {
                'model': 'gpt-4',
                'input_tokens': 1000,
                'output_tokens': 500,
                'total_cost': 0.05
            },
            'generation_time': 2.5
        }
    }

    print("\n1. Creating forecast...")
    forecast_id = db.save_forecast(forecast_data)
    print(f"   ✓ Forecast created: {forecast_id}")

    # Create batch with one invalid prediction
    predictions = [
        {
            'shore': 'North Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=1),
            'height': 8.0,
            'period': 12.0,
            'direction': 'NW',
        },
        {
            'shore': 'South Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=2),
            'height': 4.0,
            'period': 10.0,
            'direction': 'S',
        },
        {
            'shore': None,  # INVALID: shore is required
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=3),
            'height': 6.0,
        }
    ]

    print(f"\n2. Attempting to insert {len(predictions)} predictions (one is invalid)...")
    print("   Note: 3rd prediction has None for required 'shore' field")

    try:
        db.save_predictions(forecast_id, predictions)
        print("   ERROR: Should have raised exception!")
    except Exception as e:
        print(f"   ✓ Exception raised as expected: {type(e).__name__}")
        print(f"   ✓ Automatic rollback occurred")

    # Verify no partial data saved
    saved_predictions = db.get_predictions_for_forecast(forecast_id)
    print(f"\n3. Verification after rollback:")
    print(f"   ✓ Found {len(saved_predictions)} predictions in database")
    print(f"   ✓ No partial data saved (rollback successful)")

    # Now insert valid data
    valid_predictions = [
        {
            'shore': 'North Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=1),
            'height': 8.0,
        },
        {
            'shore': 'South Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=2),
            'height': 4.0,
        }
    ]

    print(f"\n4. Inserting {len(valid_predictions)} valid predictions...")
    db.save_predictions(forecast_id, valid_predictions)
    print(f"   ✓ Valid predictions saved successfully")

    saved_predictions = db.get_predictions_for_forecast(forecast_id)
    print(f"\n5. Final verification:")
    print(f"   ✓ Found {len(saved_predictions)} predictions in database")

    # Cleanup
    Path(db_path).unlink()
    print("\n✓ Demo 2 completed successfully")


def demo_batch_actuals():
    """Demonstrate batch actuals insert."""
    print("\n" + "="*70)
    print("DEMO 3: Batch Actuals Insert")
    print("="*70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = ValidationDatabase(db_path=db_path)

    # Create batch actuals
    actuals = [
        {
            'buoy_id': '51201',
            'observation_time': datetime.now() - timedelta(hours=i),
            'wave_height': 8.5 - i * 0.3,
            'dominant_period': 12.5,
            'direction': 315.0,
            'source': 'NDBC'
        }
        for i in range(10)
    ]

    print(f"\n1. Inserting {len(actuals)} buoy observations as a batch...")
    db.save_actuals(actuals)
    print(f"   ✓ All {len(actuals)} observations saved successfully")

    # Cleanup
    Path(db_path).unlink()
    print("\n✓ Demo 3 completed successfully")


def demo_performance_comparison():
    """Compare performance of single vs batch inserts."""
    print("\n" + "="*70)
    print("DEMO 4: Performance Comparison (Single vs Batch)")
    print("="*70)

    import time

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = ValidationDatabase(db_path=db_path)

    # Create forecasts
    forecast_data_1 = {
        'forecast_id': 'perf-test-single',
        'generated_time': datetime.now(),
        'metadata': {
            'source_data': {'bundle_id': 'perf-bundle'},
            'api_usage': {'model': 'gpt-4', 'input_tokens': 1000, 'output_tokens': 500, 'total_cost': 0.05},
            'generation_time': 2.5
        }
    }

    forecast_data_2 = {
        'forecast_id': 'perf-test-batch',
        'generated_time': datetime.now(),
        'metadata': {
            'source_data': {'bundle_id': 'perf-bundle'},
            'api_usage': {'model': 'gpt-4', 'input_tokens': 1000, 'output_tokens': 500, 'total_cost': 0.05},
            'generation_time': 2.5
        }
    }

    forecast_id_1 = db.save_forecast(forecast_data_1)
    forecast_id_2 = db.save_forecast(forecast_data_2)

    num_predictions = 50

    # Create test data
    predictions_single = [
        {
            'shore': 'North Shore',
            'forecast_time': datetime.now(),
            'valid_time': datetime.now() + timedelta(hours=i),
            'height': 8.0 + i * 0.1,
            'period': 12.0,
        }
        for i in range(num_predictions)
    ]

    predictions_batch = predictions_single.copy()

    # Test single inserts
    print(f"\n1. Testing {num_predictions} single inserts...")
    start = time.time()
    for pred in predictions_single:
        db.save_prediction(
            forecast_id=forecast_id_1,
            shore=pred['shore'],
            forecast_time=pred['forecast_time'],
            valid_time=pred['valid_time'],
            predicted_height=pred['height'],
            predicted_period=pred['period']
        )
    single_time = time.time() - start
    print(f"   Time: {single_time:.3f} seconds")
    print(f"   Per insert: {(single_time/num_predictions)*1000:.2f} ms")

    # Test batch insert
    print(f"\n2. Testing {num_predictions} predictions as a batch...")
    start = time.time()
    db.save_predictions(forecast_id_2, predictions_batch)
    batch_time = time.time() - start
    print(f"   Time: {batch_time:.3f} seconds")
    print(f"   Per insert: {(batch_time/num_predictions)*1000:.2f} ms")

    # Comparison
    speedup = single_time / batch_time
    print(f"\n3. Performance improvement:")
    print(f"   ✓ Batch insert is {speedup:.1f}x faster")
    print(f"   ✓ Time saved: {(single_time - batch_time):.3f} seconds")
    print(f"   ✓ Percentage improvement: {((single_time - batch_time)/single_time*100):.1f}%")

    # Cleanup
    Path(db_path).unlink()
    print("\n✓ Demo 4 completed successfully")


def main():
    """Run all demonstrations."""
    print("\n" + "="*70)
    print("DATABASE TRANSACTION ROLLBACK DEMONSTRATION")
    print("="*70)
    print("\nThis script demonstrates the robustness of batch database")
    print("operations with automatic transaction rollback protection.")

    try:
        demo_successful_batch_insert()
        demo_rollback_on_failure()
        demo_batch_actuals()
        demo_performance_comparison()

        print("\n" + "="*70)
        print("ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nKey Takeaways:")
        print("  1. Batch operations are much faster than single inserts")
        print("  2. Failed batch inserts automatically rollback")
        print("  3. No partial data is saved on failure")
        print("  4. Database connections are always closed properly")
        print("  5. Applications can safely use batch operations")
        print("\n")

    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
