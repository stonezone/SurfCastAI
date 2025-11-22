# Database Operations Guide

## Overview
The validation database (`src/validation/database.py`) provides robust transaction management with automatic rollback protection for all batch operations. This ensures data integrity even when errors occur during batch inserts.

## Batch Operations

### 1. Batch Predictions Insert
Save multiple forecast predictions efficiently using a single database transaction.

```python
from src.validation.database import ValidationDatabase

db = ValidationDatabase()

predictions = [
    {
        'shore': 'North Shore',
        'forecast_time': datetime.now(),
        'valid_time': datetime.now() + timedelta(hours=1),
        'height': 8.0,
        'period': 12.0,
        'direction': 'NW',
        'category': 'overhead',
        'confidence': 0.85
    },
    # ... more predictions
]

db.save_predictions(forecast_id='my-forecast-123', predictions=predictions)
```

### 2. Batch Actuals Insert
Save multiple buoy observations in a single transaction.

```python
actuals = [
    {
        'buoy_id': '51201',
        'observation_time': datetime.now(),
        'wave_height': 8.5,
        'dominant_period': 12.5,
        'direction': 315.0,
        'source': 'NDBC'
    },
    # ... more observations
]

db.save_actuals(actuals)
```

### 3. Batch Validations Insert
Save multiple validation results comparing predictions to actuals.

```python
validations = [
    {
        'forecast_id': 'my-forecast-123',
        'prediction_id': 1,
        'actual_id': 1,
        'height_error': 0.5,
        'period_error': 0.3,
        'direction_error': 5.0,
        'category_match': True,
        'mae': 0.4,
        'rmse': 0.5
    },
    # ... more validations
]

db.save_validations(validations)
```

## Transaction Safety

All batch operations are protected by transaction rollback:

1. **Automatic Rollback**: If any error occurs during a batch insert, all changes are rolled back
2. **Connection Management**: Database connections are always closed, even after exceptions
3. **Error Logging**: Failed operations are logged with context about what failed
4. **Exception Propagation**: Exceptions are re-raised after rollback so callers know the operation failed

### Example Error Handling

```python
try:
    db.save_predictions(forecast_id, predictions)
except Exception as e:
    # Database has been rolled back automatically
    # No partial data was saved
    logger.error(f"Failed to save predictions: {e}")
    # Handle the error appropriately
```

## Performance Benefits

Batch operations using `executemany()` provide significant performance benefits:

- **Single Transaction**: All inserts happen in one transaction, reducing overhead
- **Reduced Network Round-trips**: One database call instead of N calls
- **Atomic Operations**: Either all inserts succeed or none do (no partial data)
- **Better Resource Usage**: Fewer connection opens/closes

### Performance Comparison

```python
# Inefficient: N separate transactions
for pred in predictions:
    db.save_prediction(forecast_id, **pred)  # 100 calls = 100 transactions

# Efficient: Single transaction
db.save_predictions(forecast_id, predictions)  # 1 call = 1 transaction
```

## Best Practices

1. **Use Batch Methods**: When inserting multiple records, always use batch methods
2. **Handle Exceptions**: Wrap batch operations in try/except blocks
3. **Validate Data First**: Validate data before batch insert to avoid rollbacks
4. **Check Results**: After batch insert, verify the operation succeeded
5. **Empty Lists**: Batch methods handle empty lists gracefully

### Validation Example

```python
def save_predictions_safely(db, forecast_id, predictions):
    """Save predictions with validation."""
    # Validate data first
    if not predictions:
        logger.warning("No predictions to save")
        return

    for pred in predictions:
        if not pred.get('shore'):
            raise ValueError(f"Missing required field 'shore': {pred}")

    # Perform batch insert
    try:
        db.save_predictions(forecast_id, predictions)
        logger.info(f"Saved {len(predictions)} predictions")
    except Exception as e:
        logger.error(f"Batch insert failed: {e}")
        raise
```

## Database Schema

The validation database includes four main tables:

1. **forecasts**: Forecast metadata (model, tokens, timing)
2. **predictions**: Extracted predictions from forecasts
3. **actuals**: Observed conditions from buoys
4. **validations**: Comparison of predictions vs actuals

All tables have appropriate indexes for efficient querying.

## Testing

Comprehensive tests are available in `tests/unit/validation/test_database_rollback.py`:

```bash
# Run rollback tests
python -m pytest tests/unit/validation/test_database_rollback.py -v

# Run all validation tests
python -m pytest tests/unit/validation/ -v
```

Tests verify:
- Successful batch operations
- Rollback on invalid data
- Connection cleanup after exceptions
- Empty batch handling
- Database integrity after errors

## Monitoring and Maintenance

### Check Database Size

```python
import sqlite3
from pathlib import Path

db_path = Path("data/validation.db")
size_mb = db_path.stat().st_size / (1024 * 1024)
print(f"Database size: {size_mb:.2f} MB")
```

### Vacuum Database

```python
conn = sqlite3.connect("data/validation.db")
conn.execute("VACUUM")
conn.close()
```

### Check Record Counts

```python
db = ValidationDatabase()
conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()

for table in ['forecasts', 'predictions', 'actuals', 'validations']:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count:,} records")

conn.close()
```

## Troubleshooting

### Issue: Batch Insert Fails

**Symptoms**: Exception raised during batch insert, no data saved

**Solution**: Check logs for specific error, validate input data format

```python
# Enable debug logging
import logging
logging.getLogger('src.validation.database').setLevel(logging.DEBUG)
```

### Issue: Connection Already Closed

**Symptoms**: "Cannot operate on a closed database" error

**Solution**: Create a new database instance, check connection management

```python
# Don't reuse connections
db = ValidationDatabase()  # Creates new connection pool
```

### Issue: Slow Batch Operations

**Symptoms**: Batch inserts taking longer than expected

**Solution**: Use batch methods, check database size, consider vacuuming

```python
# Check if using batch methods
db.save_predictions(forecast_id, predictions)  # Good
for pred in predictions:
    db.save_prediction(forecast_id, **pred)  # Bad (slow)
```

## Future Enhancements

Potential improvements for database operations:

1. **Connection Pooling**: Reuse database connections for better performance
2. **Async Operations**: Support async/await for concurrent operations
3. **Bulk Updates**: Add methods for bulk updates in addition to inserts
4. **Query Builder**: Simplify complex queries with a query builder
5. **Migration System**: Add database versioning and migration support
