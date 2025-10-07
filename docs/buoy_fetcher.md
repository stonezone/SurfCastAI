# BuoyDataFetcher Documentation

## Overview

`BuoyDataFetcher` is a robust, asynchronous buoy data fetcher for retrieving real-time wave observations from NDBC (National Data Buoy Center) buoys. It's designed specifically for forecast validation by comparing AI-generated forecasts against actual buoy measurements.

## Features

- **Async/await support**: Efficient concurrent fetching from multiple buoys
- **Rate limiting**: Respects NDBC courtesy limit (0.5 req/s)
- **Error handling**: Graceful handling of network errors and missing data
- **Data validation**: Parses and validates NDBC text format
- **Unit conversion**: Automatic conversion from meters to feet
- **Missing data handling**: Properly handles NDBC 'MM' missing value markers
- **Database integration**: Seamless integration with ValidationDatabase
- **Shore-specific fetching**: Organized by North Shore and South Shore buoys

## Buoy Mappings

### North Shore Buoys
- **51001**: Northwest Hawaii (23.4°N, 162.3°W)
- **51101**: Northwest Molokai (24.3°N, 162.1°W)

### South Shore Buoys
- **51003**: Southeast Hawaii (19.2°N, 160.7°W)
- **51004**: Southeast Hawaii (17.5°N, 152.3°W)

## Installation

BuoyDataFetcher is part of the validation module:

```python
from src.validation import BuoyDataFetcher
```

## Basic Usage

### Fetch Observations for a Shore

```python
import asyncio
from datetime import datetime, timedelta
from src.validation import BuoyDataFetcher

async def fetch_north_shore():
    # Define time range (last 24 hours)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    # Fetch observations
    async with BuoyDataFetcher() as fetcher:
        observations = await fetcher.fetch_observations(
            shore='north_shore',
            start_time=start_time,
            end_time=end_time
        )

    # Process observations
    for obs in observations:
        print(f"Buoy {obs['buoy_id']} @ {obs['observation_time']}")
        print(f"  Wave Height: {obs['wave_height']:.1f} ft")
        print(f"  Period: {obs['dominant_period']} sec")
        print(f"  Direction: {obs['direction']}°")

asyncio.run(fetch_north_shore())
```

### Save to Database

```python
from src.validation import BuoyDataFetcher, ValidationDatabase

async def fetch_and_save():
    db = ValidationDatabase("data/validation.db")

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    async with BuoyDataFetcher() as fetcher:
        observations = await fetcher.fetch_observations(
            'north_shore', start_time, end_time
        )

        for obs in observations:
            db.save_actual(
                buoy_id=obs['buoy_id'],
                observation_time=obs['observation_time'],
                wave_height=obs['wave_height'],
                dominant_period=obs['dominant_period'],
                direction=obs['direction'],
                source=obs['source']
            )

asyncio.run(fetch_and_save())
```

### Custom HTTP Client and Rate Limiter

```python
from src.core import HTTPClient, RateLimiter, RateLimitConfig

# Create custom rate limiter (slower for testing)
rate_limiter = RateLimiter(
    default_config=RateLimitConfig(
        requests_per_second=0.25,  # Slower than default
        burst_size=1
    )
)

# Create custom HTTP client
http_client = HTTPClient(
    rate_limiter=rate_limiter,
    timeout=60,  # Longer timeout
    max_concurrent=3
)

# Use custom client
async with BuoyDataFetcher(http_client=http_client) as fetcher:
    observations = await fetcher.fetch_observations(...)
```

## API Reference

### Class: BuoyDataFetcher

#### `__init__(http_client=None, rate_limiter=None, timeout=30)`

Initialize the buoy data fetcher.

**Parameters:**
- `http_client` (HTTPClient, optional): Custom HTTP client instance
- `rate_limiter` (RateLimiter, optional): Custom rate limiter instance
- `timeout` (int): Request timeout in seconds (default: 30)

#### `async fetch_observations(shore, start_time, end_time)`

Fetch buoy observations for a specific shore and time range.

**Parameters:**
- `shore` (str): Shore name ('north_shore' or 'south_shore')
- `start_time` (datetime): Start of time range (inclusive)
- `end_time` (datetime): End of time range (inclusive)

**Returns:**
- `List[Dict]`: List of observation dictionaries

**Observation Dictionary Structure:**
```python
{
    'buoy_id': str,           # Buoy identifier (e.g., '51201')
    'observation_time': datetime,  # UTC timestamp
    'wave_height': float,     # Wave height in feet (converted from meters)
    'dominant_period': float, # Dominant period in seconds (None if missing)
    'direction': float,       # Wave direction in degrees (None if missing)
    'source': str            # Always 'NDBC'
}
```

**Raises:**
- `ValueError`: If shore name is invalid

#### `async close()`

Close the HTTP client (if owned by this instance).

**Note:** When using `BuoyDataFetcher` as a context manager, this is called automatically.

## Data Format

### NDBC Text Format

NDBC provides real-time data in space-delimited text files:

```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2025 10 04 12 00  310  8.0  9.5  2.13  11.1   8.3 300 1015.2  24.5  25.1  22.3  8.0 -0.3  0.45
2025 10 04 11 30  315  7.5  9.0  2.29  10.8   8.1 305 1015.1  24.6  25.2  22.4  8.1 -0.2  0.48
```

**Key Columns:**
- **YY MM DD hh mm**: Timestamp (UTC)
- **WVHT**: Significant wave height (meters)
- **DPD**: Dominant wave period (seconds)
- **MWD**: Mean wave direction (degrees)

**Missing Values:**
- Marked as `MM` in the data
- Converted to `None` in Python dictionaries

### Unit Conversion

Wave heights are automatically converted from meters to feet:
```python
wave_height_feet = wave_height_meters * 3.28084
```

## Error Handling

### Network Errors

Network errors are logged and handled gracefully:

```python
async with BuoyDataFetcher() as fetcher:
    observations = await fetcher.fetch_observations(
        'north_shore', start_time, end_time
    )
    # Returns empty list if all buoys fail
    # Returns partial results if some buoys fail
```

### Missing Data

Missing values (`MM` in NDBC data) are converted to `None`:

```python
for obs in observations:
    if obs['dominant_period'] is None:
        print(f"No period data for {obs['observation_time']}")
    if obs['direction'] is None:
        print(f"No direction data for {obs['observation_time']}")
```

### Invalid Shore Names

Invalid shore names raise `ValueError`:

```python
try:
    observations = await fetcher.fetch_observations(
        'invalid_shore', start_time, end_time
    )
except ValueError as e:
    print(f"Invalid shore: {e}")
```

## Rate Limiting

BuoyDataFetcher enforces NDBC's courtesy rate limit of **0.5 requests per second**.

### Why Rate Limiting?

- Respects NDBC server resources
- Prevents HTTP 429 (Too Many Requests) errors
- Ensures reliable data access
- Community best practice

### Rate Limit Configuration

```python
# Default: 0.5 req/s, burst of 2
fetcher = BuoyDataFetcher()

# Custom: slower rate
rate_limiter = RateLimiter(
    default_config=RateLimitConfig(
        requests_per_second=0.25,
        burst_size=1
    )
)
fetcher = BuoyDataFetcher(rate_limiter=rate_limiter)
```

### Expected Fetch Times

- **1 buoy**: ~0 seconds (first request)
- **2 buoys**: ~2 seconds (rate limited)
- **4 buoys**: ~6 seconds (rate limited)

## Testing

### Unit Tests

Run unit tests (no network required):

```bash
pytest tests/test_buoy_fetcher.py::TestBuoyDataFetcher -v
```

### Live Tests

Run live tests (requires network):

```bash
pytest tests/test_buoy_fetcher.py::TestBuoyDataFetcherLive -v -m live
```

### Test Coverage

The test suite includes:
- Data parsing accuracy (90%+ requirement)
- Time filtering
- Missing data handling
- Unit conversion
- Rate limiting enforcement
- Database integration
- Error handling

## Examples

See `examples/buoy_fetcher_example.py` for a complete working example.

Run the example:

```bash
python examples/buoy_fetcher_example.py
```

## Performance

### Parsing Accuracy

BuoyDataFetcher achieves **90%+** parsing accuracy on NDBC data:
- Handles standard NDBC format
- Gracefully handles missing values
- Robust error recovery

### Efficiency

- **Async/await**: Non-blocking concurrent fetching
- **Rate limiting**: Token bucket algorithm (O(1) operations)
- **Memory**: Minimal memory footprint (streaming data)

## Integration

### With ValidationDatabase

```python
from src.validation import BuoyDataFetcher, ValidationDatabase

async def validate_forecast(forecast_id):
    db = ValidationDatabase()

    # Get forecast predictions
    predictions = db.get_predictions(forecast_id)

    # Fetch actual observations
    async with BuoyDataFetcher() as fetcher:
        for pred in predictions:
            shore = pred['shore'].lower().replace(' ', '_')
            observations = await fetcher.fetch_observations(
                shore=shore,
                start_time=pred['valid_time'] - timedelta(minutes=30),
                end_time=pred['valid_time'] + timedelta(minutes=30)
            )

            # Find closest observation
            closest = min(
                observations,
                key=lambda o: abs(
                    (o['observation_time'] - pred['valid_time']).total_seconds()
                )
            )

            # Save actual observation
            actual_id = db.save_actual(
                buoy_id=closest['buoy_id'],
                observation_time=closest['observation_time'],
                wave_height=closest['wave_height'],
                dominant_period=closest['dominant_period'],
                direction=closest['direction']
            )

            # Calculate errors and save validation
            height_error = abs(pred['predicted_height'] - closest['wave_height'])
            db.save_validation(
                forecast_id=forecast_id,
                prediction_id=pred['id'],
                actual_id=actual_id,
                height_error=height_error
            )
```

## Troubleshooting

### No Observations Returned

**Possible causes:**
1. Time range too narrow or in the past
2. Buoy offline or not reporting
3. Network connectivity issues

**Solution:**
```python
# Use broader time range
start_time = datetime.utcnow() - timedelta(hours=48)
end_time = datetime.utcnow()

# Check individual buoys
observations = await fetcher.fetch_observations(
    'north_shore', start_time, end_time
)
print(f"Buoys with data: {set(o['buoy_id'] for o in observations)}")
```

### Rate Limit Errors

**Symptom:** Requests taking much longer than expected

**Solution:** Rate limiting is working correctly. Adjust rate limit if needed:
```python
rate_limiter = RateLimiter(
    default_config=RateLimitConfig(
        requests_per_second=1.0,  # Faster (but not recommended)
        burst_size=3
    )
)
```

### Parsing Errors

**Symptom:** Some observations have `None` values

**Explanation:** This is normal! NDBC uses `MM` for missing data.

**Solution:** Filter out missing values if needed:
```python
valid_obs = [
    obs for obs in observations
    if obs['wave_height'] is not None
    and obs['dominant_period'] is not None
]
```

## Best Practices

1. **Use context manager**: Always use `async with` for automatic cleanup
2. **Respect rate limits**: Don't override default rate limits without good reason
3. **Handle missing data**: Check for `None` values in period/direction
4. **Broad time ranges**: Use 24-48 hour windows for better data coverage
5. **Error handling**: Catch and log exceptions, don't fail silently
6. **Database transactions**: Batch saves for efficiency

## See Also

- [ValidationDatabase Documentation](validation_database.md)
- [ForecastParser Documentation](forecast_parser.md)
- [NDBC Real-time Data](https://www.ndbc.noaa.gov/)
