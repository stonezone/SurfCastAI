# Transaction Isolation Quick Reference Guide

## Overview

The validation database uses explicit transaction isolation levels to prevent race conditions and ensure data consistency. This guide explains when and how to use each transaction type.

## Transaction Types

### IMMEDIATE Transactions (Write Operations)

**When to Use:**
- INSERT operations
- UPDATE operations
- DELETE operations
- Any operation that modifies data

**Pattern:**
```python
from src.validation.database import connect_with_retry, immediate_transaction

conn = connect_with_retry(db_path)
try:
    with immediate_transaction(conn):
        cursor = conn.cursor()
        cursor.execute("INSERT INTO forecasts (...) VALUES (...)", data)
        result = cursor.lastrowid  # Get inserted ID if needed
finally:
    conn.close()
```

**Benefits:**
- Acquires exclusive write lock immediately at BEGIN
- Prevents write-write conflicts
- Other writers block and retry automatically
- Clear transaction boundaries

### DEFERRED Transactions (Read Operations)

**When to Use:**
- SELECT queries
- Read-only operations
- Query operations that don't modify data

**Pattern:**
```python
from src.validation.database import connect_with_retry, deferred_transaction

conn = connect_with_retry(db_path)
try:
    with deferred_transaction(conn):
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM forecasts WHERE ...", params)
        rows = cursor.fetchall()
finally:
    conn.close()
```

**Note:** DEFERRED is SQLite's default, so you can also use:
```python
with connect_with_retry(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM forecasts WHERE ...", params)
    rows = cursor.fetchall()
```

### EXCLUSIVE Transactions (Schema Operations)

**When to Use:**
- CREATE TABLE operations
- ALTER TABLE operations
- Schema migrations
- Database initialization

**Pattern:**
```python
from src.validation.database import connect_with_retry

conn = connect_with_retry(db_path)
conn.execute("BEGIN EXCLUSIVE")
try:
    conn.executescript(schema_sql)
    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

**Benefits:**
- Blocks ALL other connections during schema changes
- Prevents corruption during migrations
- Only use for schema operations (slow!)

## Batch Operations

### Best Practice: Single Transaction Per Batch

**❌ Bad: Multiple Transactions**
```python
for item in items:
    conn = connect_with_retry(db_path)
    with immediate_transaction(conn):
        cursor.execute("INSERT ...", item)
    conn.close()
```

**✓ Good: Single Transaction**
```python
conn = connect_with_retry(db_path, timeout=60.0)
try:
    with immediate_transaction(conn):
        cursor = conn.cursor()
        cursor.executemany("INSERT ...", items)
finally:
    conn.close()
```

**Benefits:**
- 10-100x faster for batches
- Single lock acquisition
- Atomic batch insertion
- Automatic rollback on any failure

## Error Handling

### Automatic Retry on Lock Contention

The `connect_with_retry()` function handles transient lock errors:

```python
conn = connect_with_retry(
    db_path,
    timeout=30.0,      # Connection timeout
    max_retries=3,     # Retry attempts
    retry_delay=0.1    # Initial delay (exponential backoff)
)
```

**Retry Logic:**
- Retries on: 'locked', 'busy', 'timeout', 'disk i/o' errors
- Exponential backoff: 0.1s → 0.2s → 0.4s
- Fails after 3 attempts with clear error

### Transaction Context Managers Handle Rollback

```python
try:
    with immediate_transaction(conn):
        # Any exception here triggers automatic rollback
        cursor.execute("INSERT ...", data)
except sqlite3.IntegrityError as e:
    # Transaction already rolled back
    logger.error(f"Constraint violation: {e}")
except Exception as e:
    # Transaction already rolled back
    logger.error(f"Database error: {e}")
    raise
```

## Common Patterns

### Pattern 1: Single Insert with IMMEDIATE

```python
def save_forecast(self, forecast_data: Dict[str, Any]) -> str:
    conn = connect_with_retry(str(self.db_path))
    try:
        with immediate_transaction(conn):
            cursor = conn.cursor()
            cursor.execute("INSERT INTO forecasts (...) VALUES (...)", data)
            return cursor.lastrowid
    finally:
        conn.close()
```

### Pattern 2: Batch Insert with IMMEDIATE

```python
def save_predictions(self, forecast_id: str, predictions: List[Dict]) -> None:
    conn = connect_with_retry(str(self.db_path), timeout=60.0)
    try:
        with immediate_transaction(conn):
            cursor = conn.cursor()
            batch_data = [(forecast_id, pred['height'], ...) for pred in predictions]
            cursor.executemany("INSERT INTO predictions (...) VALUES (...)", batch_data)
    finally:
        conn.close()
```

### Pattern 3: Read with Context Manager

```python
def get_forecast(self, forecast_id: str) -> Optional[Dict]:
    with connect_with_retry(str(self.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM forecasts WHERE forecast_id = ?", (forecast_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
```

### Pattern 4: Extended Timeout for Complex Operations

```python
from src.validation.database import extended_timeout_connection

with extended_timeout_connection(db_path, timeout=120.0) as conn:
    with immediate_transaction(conn):
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO actuals (...) VALUES (...)", large_batch)
```

## Performance Tips

### 1. Use WAL Mode (Already Enabled)

```python
conn.execute("PRAGMA journal_mode = WAL")
```

**Benefits:**
- Concurrent reads during writes
- Better write performance
- Automatic crash recovery

### 2. Batch Operations

- Use `executemany()` for batches > 10 rows
- Single transaction per batch
- Extended timeout for large batches

### 3. Connection Pooling (Future)

For high-throughput applications, consider connection pooling:

```python
# Future enhancement
pool = ConnectionPool(db_path, max_connections=5)
with pool.get_connection() as conn:
    with immediate_transaction(conn):
        ...
```

### 4. Monitor Lock Contention

```python
# Log warnings for retry attempts (already implemented)
logger.warning(
    f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. "
    f"Retrying in {current_delay:.2f}s..."
)
```

## Debugging

### Check Active Transactions

```sql
-- SQLite query to see active transactions
PRAGMA busy_timeout;  -- Check timeout setting
PRAGMA journal_mode;  -- Should be WAL
```

### Enable Debug Logging

```python
import logging
logging.getLogger('src.validation.database').setLevel(logging.DEBUG)
```

### Test Concurrent Writes

```python
import threading

def concurrent_write_test():
    threads = [
        threading.Thread(target=lambda: db.save_forecast(data))
        for _ in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
```

## Troubleshooting

### "Database is locked" Errors

**Cause:** Write contention between threads
**Solution:** Already handled by retry logic

### "Database disk image is malformed"

**Cause:** Corruption (rare with WAL mode)
**Solution:** Restore from backup, enable WAL mode

### Slow Writes

**Cause:** Too many individual transactions
**Solution:** Use batch operations with single transaction

### High Memory Usage

**Cause:** Large batch operations
**Solution:** Use streaming or chunk large batches

## Migration Guide

### Converting Existing Code to Use Transaction Isolation

**Before:**
```python
conn = connect_with_retry(db_path)
cursor = conn.cursor()
try:
    cursor.execute("INSERT ...", data)
    conn.commit()
except Exception as e:
    conn.rollback()
    raise
finally:
    conn.close()
```

**After:**
```python
conn = connect_with_retry(db_path)
try:
    with immediate_transaction(conn):
        cursor = conn.cursor()
        cursor.execute("INSERT ...", data)
finally:
    conn.close()
```

**Changes:**
- Add `with immediate_transaction(conn):` wrapper
- Remove explicit `conn.commit()` and `conn.rollback()`
- Automatic rollback on exception

## References

- SQLite Transaction Documentation: https://www.sqlite.org/lang_transaction.html
- WAL Mode: https://www.sqlite.org/wal.html
- Python sqlite3 module: https://docs.python.org/3/library/sqlite3.html

## Summary

| Operation | Transaction Type | Pattern |
|-----------|-----------------|---------|
| INSERT | IMMEDIATE | `with immediate_transaction(conn):` |
| UPDATE | IMMEDIATE | `with immediate_transaction(conn):` |
| DELETE | IMMEDIATE | `with immediate_transaction(conn):` |
| SELECT | DEFERRED | `with connect_with_retry(db_path) as conn:` |
| CREATE TABLE | EXCLUSIVE | `conn.execute("BEGIN EXCLUSIVE")` |
| ALTER TABLE | EXCLUSIVE | `conn.execute("BEGIN EXCLUSIVE")` |
| Batch INSERT | IMMEDIATE | `with immediate_transaction(conn):` + `executemany()` |

**Key Takeaways:**
- Always use IMMEDIATE transactions for writes
- Use single transaction per batch operation
- Let retry logic handle lock contention
- Use context managers for automatic cleanup
- Enable WAL mode for better concurrency
