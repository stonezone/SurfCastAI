# Database Retry Logic - Quick Reference

## Overview

The validation database layer includes automatic retry logic with exponential backoff to handle transient failures gracefully.

## Key Features

- **Automatic Retries:** 3 attempts with exponential backoff (0.1s → 0.2s → 0.4s)
- **Configurable Timeouts:** 30s default, 60s for batch operations
- **Smart Error Detection:** Only retries transient errors (locked, busy, timeout, I/O)
- **Production Logging:** Clear audit trail of retry attempts

## Usage

### Standard Connection (30s timeout)

```python
from src.validation.database import connect_with_retry

# Automatic retry with default settings
conn = connect_with_retry('data/validation.db')

# Use connection normally
cursor = conn.cursor()
cursor.execute("SELECT * FROM forecasts")

# Clean up
conn.close()
```

### Extended Timeout (60s+)

For batch operations or slow queries:

```python
from src.validation.database import connect_with_retry

# Extended timeout for batch insert
conn = connect_with_retry('data/validation.db', timeout=60.0)

cursor = conn.cursor()
cursor.executemany("INSERT INTO predictions VALUES (?, ?, ?)", large_batch)
conn.commit()
conn.close()
```

### Context Manager (Automatic Cleanup)

```python
from src.validation.database import extended_timeout_connection

# Automatically handles connection lifecycle
with extended_timeout_connection('data/validation.db', timeout=120.0) as conn:
    cursor = conn.cursor()
    cursor.executemany("INSERT ...", huge_batch)
    conn.commit()
# Connection closed automatically
```

### Custom Retry Settings

```python
# More aggressive retry strategy
conn = connect_with_retry(
    db_path='data/validation.db',
    timeout=45.0,           # 45-second timeout
    max_retries=5,          # 5 retry attempts
    retry_delay=0.2         # Start with 0.2s delay
)
```

## Configuration Constants

Located in `src/validation/database.py`:

```python
DB_TIMEOUT = 30.0                    # Default timeout (seconds)
MAX_RETRIES = 3                      # Max retry attempts
RETRY_DELAY = 0.1                    # Initial delay (seconds)
RETRY_BACKOFF_MULTIPLIER = 2.0       # Exponential backoff rate
```

**To adjust system-wide:** Edit these constants in database.py

## Error Handling

### Transient Errors (Will Retry)

- `database is locked` - SQLite EXCLUSIVE lock
- `database is busy` - SQLite operation in progress
- `database timeout` - Query exceeded timeout
- `disk i/o error` - Temporary I/O failure

**Behavior:** Retry with exponential backoff, log warnings

### Non-Transient Errors (Fail Immediately)

- File not found
- Permission denied
- Disk full
- Invalid path
- Schema errors

**Behavior:** Raise exception immediately, no retries

## Logging

### Retry Warnings

```
WARNING: Database connection attempt 1/3 failed: database is locked. Retrying in 0.10s...
WARNING: Database connection attempt 2/3 failed: database is locked. Retrying in 0.20s...
```

**Action:** Normal under light contention, investigate if frequent

### Final Failure

```
ERROR: Failed to connect to database after 3 attempts: database is locked
```

**Action:** Critical - check for long transactions, deadlocks, or disk issues

## Performance

### Typical Overhead

- **Successful connection:** ~1ms (PRAGMA execution)
- **Single retry:** +0.1s (first backoff delay)
- **Max retries:** ~2.1s (3 × timeout + backoff)

### Batch Operation Timeouts

| Operation | Records | Timeout | Rationale |
|-----------|---------|---------|-----------|
| save_predictions | <100 | 30s | Fast insert |
| save_predictions | 100-1000 | 60s | Medium batch |
| save_actuals | <100 | 30s | Fast insert |
| save_actuals | 100-1000 | 60s | Medium batch |
| save_validations | <100 | 30s | Fast insert |
| save_validations | 100-1000 | 60s | Medium batch |

## Troubleshooting

### Problem: Frequent Retry Warnings

**Symptoms:**
```
WARNING: Database connection attempt 1/3 failed: database is locked. Retrying...
```

**Possible Causes:**
- Long-running transactions
- High concurrent access
- Slow disk I/O

**Solutions:**
1. Reduce transaction duration
2. Add connection pooling
3. Upgrade disk/storage
4. Increase MAX_RETRIES

### Problem: Connection Failures After Retries

**Symptoms:**
```
ERROR: Failed to connect to database after 3 attempts
```

**Possible Causes:**
- Database deadlock
- Disk full
- Permission issues
- File corruption

**Solutions:**
1. Check disk space: `df -h`
2. Check permissions: `ls -la data/validation.db`
3. Check for zombie processes: `lsof data/validation.db`
4. Run integrity check: `sqlite3 data/validation.db "PRAGMA integrity_check"`

### Problem: Slow Batch Operations

**Symptoms:**
- Batch inserts timing out
- Operations taking >30s

**Solutions:**
1. Use extended_timeout_connection:
   ```python
   with extended_timeout_connection(db_path, timeout=120.0) as conn:
       cursor.executemany("INSERT ...", batch)
   ```

2. Reduce batch size:
   ```python
   # Instead of 1000 records at once
   for i in range(0, len(records), 100):
       batch = records[i:i+100]
       cursor.executemany("INSERT ...", batch)
       conn.commit()
   ```

3. Increase timeout:
   ```python
   DB_TIMEOUT = 60.0  # In database.py
   ```

## Best Practices

### DO

✅ Use connect_with_retry() for all database connections
✅ Use extended timeouts (60s+) for batch operations
✅ Use context managers for automatic cleanup
✅ Log and monitor retry warnings
✅ Handle exceptions appropriately
✅ Close connections in finally blocks

### DON'T

❌ Use raw sqlite3.connect() (bypasses retry logic)
❌ Ignore retry warnings in logs
❌ Set timeout <30s for production
❌ Set max_retries <3 (may fail on transient contention)
❌ Forget to close connections
❌ Use same timeout for all operations

## Examples

### Example 1: Save Forecast with Retry

```python
from src.validation.database import ValidationDatabase

db = ValidationDatabase('data/validation.db')

try:
    forecast_id = db.save_forecast({
        'forecast_id': 'fcst-123',
        'generated_time': datetime.now(),
        'metadata': {...}
    })
    print(f'Saved forecast: {forecast_id}')
except sqlite3.OperationalError as e:
    # Failed after retries
    logger.error(f'Could not save forecast: {e}')
    # Handle gracefully (e.g., queue for later)
```

### Example 2: Batch Insert with Extended Timeout

```python
from src.validation.database import ValidationDatabase

db = ValidationDatabase('data/validation.db')

# Large batch of predictions
predictions = [...]  # 500 records

try:
    db.save_predictions('fcst-123', predictions)
    print(f'Saved {len(predictions)} predictions')
except sqlite3.OperationalError as e:
    logger.error(f'Batch insert failed: {e}')
    # Consider smaller batches or manual retry
```

### Example 3: Custom Retry Strategy

```python
from src.validation.database import connect_with_retry
import sqlite3

# High-contention environment
conn = connect_with_retry(
    'data/validation.db',
    timeout=45.0,        # Longer timeout
    max_retries=5,       # More retries
    retry_delay=0.2      # Longer initial delay
)

try:
    # Your operations here
    cursor = conn.cursor()
    cursor.execute("INSERT ...")
    conn.commit()
finally:
    conn.close()
```

## Monitoring

### Key Metrics

Track these in production:

1. **Retry Rate**
   - Formula: `retry_attempts / total_connections`
   - Normal: <1%
   - Warning: 1-5%
   - Critical: >5%

2. **Connection Time**
   - Normal: <10ms
   - Warning: 100-1000ms
   - Critical: >2s

3. **Failure Rate**
   - Formula: `failed_connections / total_connections`
   - Normal: 0%
   - Warning: <0.1%
   - Critical: >0.1%

### Log Patterns to Watch

```bash
# Count retry attempts in last hour
grep "Database connection attempt" logs/app.log | grep "$(date +%Y-%m-%d-%H)" | wc -l

# Count final failures in last 24h
grep "Failed to connect to database after" logs/app.log | grep "$(date +%Y-%m-%d)" | wc -l

# Show most recent retry attempts
grep "Database connection attempt" logs/app.log | tail -n 10
```

## Migration from Old Code

### Before (No Retry Logic)

```python
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")
```

### After (With Retry Logic)

```python
conn = connect_with_retry(db_path)
# PRAGMAs applied automatically
```

**Migration Steps:**
1. Replace `sqlite3.connect(db_path)` with `connect_with_retry(db_path)`
2. Remove manual PRAGMA calls (handled automatically)
3. Add try/except for graceful failure handling
4. Test with locked database simulation

## Related Documentation

- Full implementation details: `TASK_1_4_COMPLETION_REPORT.md`
- Database schema: `src/validation/schema.sql`
- Test suite: `tests/unit/validation/test_database_rollback.py`
- Performance analysis: `DATABASE_AUDIT_REPORT.md`

## Support

For issues or questions:
1. Check logs for retry warnings/errors
2. Review troubleshooting section above
3. Run integrity check: `sqlite3 data/validation.db "PRAGMA integrity_check"`
4. Check disk space and permissions
5. Review DATABASE_AUDIT_REPORT.md for optimization suggestions
