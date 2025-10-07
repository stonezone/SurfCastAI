# SurfCastAI API Documentation

## Table of Contents

- [Overview](#overview)
- [Core Modules](#core-modules)
- [Data Collection](#data-collection)
- [Data Processing](#data-processing)
- [Forecast Engine](#forecast-engine)
- [Validation System](#validation-system)
- [Data Structures](#data-structures)
- [Error Handling](#error-handling)
- [Extension Points](#extension-points)

## Overview

SurfCastAI is organized into modular components that can be used independently or composed together. This document provides API documentation for all major modules, data structures, and extension points.

### Module Organization

```
src/
├── core/                    # Core components (HTTP, config, rate limiting)
├── agents/                  # Data collection agents
├── processing/              # Data processing and fusion
├── forecast_engine/         # Forecast generation
├── validation/              # Validation system
└── web/                     # Web viewer
```

### Import Conventions

```python
# Core components
from src.core import Config, load_config, HTTPClient, DataCollector

# Data processing
from src.processing import BuoyProcessor, WeatherProcessor, DataFusionSystem

# Forecast generation
from src.forecast_engine import ForecastEngine, ForecastFormatter

# Validation
from src.validation import ValidationDatabase, ForecastValidator

# Data models
from src.processing.models import SwellForecast, SwellEvent, SwellComponent
```

## Core Modules

### Config

Configuration management system with hierarchical loading.

#### Class: Config

**Purpose:** Load and manage application configuration from YAML files and environment variables.

**Constructor:**
```python
Config(config_dict: dict)
```

**Methods:**

**`get(section: str, key: str, default: Any = None) -> Any`**
```python
config = Config(config_dict)
log_level = config.get('general', 'log_level', 'INFO')
```
- Get configuration value with fallback to default
- Returns value from config dict or default if not found

**`set(section: str, key: str, value: Any) -> None`**
```python
config.set('openai', 'model', 'gpt-4o-mini')
```
- Set configuration value at runtime
- Creates section if it doesn't exist

**`__getattr__(name: str) -> Any`**
```python
log_level = config.general.log_level  # Attribute-style access
```
- Convenience method for attribute-style access

#### Function: load_config

**Purpose:** Load configuration from YAML file with environment variable overrides.

**Signature:**
```python
def load_config(config_path: Optional[str] = None) -> Config
```

**Parameters:**
- `config_path`: Path to YAML config file (default: `config/config.yaml`)

**Returns:** Config object with loaded configuration

**Example:**
```python
from src.core import load_config

# Load default config
config = load_config()

# Load custom config
config = load_config('config/production.yaml')

# Environment variables override config values
# OPENAI_API_KEY env var overrides config.openai.api_key
```

**Environment Variables:**
- `OPENAI_API_KEY`: OpenAI API key (highest priority)
- `SURFCAST_OUTPUT_DIR`: Override output directory
- `SURFCAST_DATA_DIR`: Override data directory

### HTTPClient

Robust HTTP client with rate limiting, retries, and error handling.

#### Class: HTTPClient

**Purpose:** Download files from URLs with rate limiting and retry logic.

**Constructor:**
```python
HTTPClient(
    config: Config,
    rate_limiter: Optional[RateLimiter] = None,
    session: Optional[aiohttp.ClientSession] = None
)
```

**Parameters:**
- `config`: Configuration object
- `rate_limiter`: Optional rate limiter (created automatically if not provided)
- `session`: Optional aiohttp session (created automatically if not provided)

**Methods:**

**`async download_file(url: str, destination: Path, timeout: int = 30) -> DownloadResult`**
```python
client = HTTPClient(config)
result = await client.download_file(
    url="https://www.ndbc.noaa.gov/data/realtime2/51201.txt",
    destination=Path("data/buoy_51201.txt"),
    timeout=30
)

if result.success:
    print(f"Downloaded {result.size_bytes} bytes")
else:
    print(f"Error: {result.error}")
```

**Returns:** DownloadResult with status, size, and error information

**Features:**
- Automatic retries with exponential backoff
- Per-domain rate limiting
- Validates URL safety
- Sanitizes file paths
- Handles redirects

**`async close() -> None`**
```python
await client.close()
```
- Clean up resources (session, rate limiter)
- Call when done with client

#### Class: DownloadResult

**Purpose:** Result object for download operations.

**Attributes:**
- `success: bool` - Whether download succeeded
- `url: str` - URL that was downloaded
- `destination: Path` - Where file was saved
- `size_bytes: int` - Size of downloaded file
- `duration: float` - Download duration in seconds
- `status_code: Optional[int]` - HTTP status code
- `error: Optional[str]` - Error message if failed

**Example:**
```python
if result.success:
    print(f"✓ {result.url} → {result.size_bytes} bytes in {result.duration:.2f}s")
else:
    print(f"✗ {result.url}: {result.error}")
```

### RateLimiter

Token bucket rate limiter for respectful API usage.

#### Class: RateLimiter

**Purpose:** Enforce per-domain rate limits using token bucket algorithm.

**Constructor:**
```python
RateLimiter(config: Config)
```

**Methods:**

**`async wait_if_needed(domain: str) -> None`**
```python
rate_limiter = RateLimiter(config)
await rate_limiter.wait_if_needed("www.ndbc.noaa.gov")
# Proceeds when rate limit allows
```
- Blocks until domain rate limit allows request
- Uses token bucket algorithm with burst support

**`get_bucket(domain: str) -> TokenBucket`**
```python
bucket = rate_limiter.get_bucket("www.ndbc.noaa.gov")
print(f"Available tokens: {bucket.tokens}")
```
- Get token bucket for specific domain
- Creates bucket if doesn't exist

#### Class: TokenBucket

**Purpose:** Token bucket for rate limiting algorithm.

**Constructor:**
```python
TokenBucket(rate: float, capacity: int)
```

**Parameters:**
- `rate`: Tokens per second (e.g., 0.5 = 1 token every 2 seconds)
- `capacity`: Maximum tokens (burst size)

**Methods:**

**`async consume(tokens: int = 1) -> None`**
```python
bucket = TokenBucket(rate=0.5, capacity=3)
await bucket.consume(1)  # Wait if needed
```
- Consume tokens from bucket
- Blocks if insufficient tokens

**`refill() -> None`**
```python
bucket.refill()
```
- Refill bucket based on elapsed time
- Called automatically by consume()

### DataCollector

Orchestrates data collection from all agents.

#### Class: DataCollector

**Purpose:** Coordinate data collection from multiple sources (buoys, weather, models, etc.).

**Constructor:**
```python
DataCollector(config: Config)
```

**Methods:**

**`async collect_data(region: str = "Hawaii") -> Dict[str, Any]`**
```python
collector = DataCollector(config)
results = await collector.collect_data(region="Hawaii")

print(f"Bundle ID: {results['bundle_id']}")
print(f"Total files: {results['stats']['total_files']}")
print(f"Successful: {results['stats']['successful_files']}")
```

**Returns:** Dictionary with:
- `bundle_id`: Unique bundle identifier
- `timestamp`: Collection timestamp
- `region`: Region collected
- `stats`: Collection statistics
- `agent_results`: Per-agent results

**Features:**
- Parallel data collection from all enabled agents
- Automatic bundle creation and organization
- Metadata tracking
- Error aggregation

### BundleManager

Manages data bundles (timestamped collections).

#### Class: BundleManager

**Purpose:** Organize and retrieve data bundles.

**Constructor:**
```python
BundleManager(data_directory: str = "data")
```

**Methods:**

**`list_bundles() -> List[Dict[str, Any]]`**
```python
manager = BundleManager("data")
bundles = manager.list_bundles()

for bundle in bundles:
    print(f"{bundle['bundle_id']}: {bundle['timestamp']}")
```

**`get_latest_bundle() -> Optional[str]`**
```python
latest_id = manager.get_latest_bundle()
```

**`get_bundle_metadata(bundle_id: str) -> Optional[Dict[str, Any]]`**
```python
metadata = manager.get_bundle_metadata("24e7eaad-...")
print(f"Created: {metadata['timestamp']}")
print(f"Files: {metadata['stats']['total_files']}")
```

**`get_bundle_file_list(bundle_id: str) -> List[Dict[str, Any]]`**
```python
files = manager.get_bundle_file_list("24e7eaad-...")
for file in files:
    print(f"{file['name']}: {file['size_bytes']} bytes")
```

## Data Collection

### Base Agent

All data collection agents inherit from `BaseAgent`.

#### Class: BaseAgent

**Purpose:** Base class for all data collection agents.

**Constructor:**
```python
BaseAgent(
    name: str,
    config: Config,
    http_client: Optional[HTTPClient] = None
)
```

**Methods:**

**`async collect(region: str, bundle_path: Path) -> Dict[str, Any]`**
```python
class MyAgent(BaseAgent):
    async def collect(self, region: str, bundle_path: Path) -> Dict[str, Any]:
        # Download data
        urls = self._get_urls(region)
        results = []

        for url in urls:
            result = await self.http_client.download_file(
                url,
                bundle_path / self.name / self._get_filename(url)
            )
            results.append(result)

        return {
            "agent": self.name,
            "total": len(results),
            "successful": sum(1 for r in results if r.success)
        }
```

**Abstract method** - Must be implemented by subclasses

### BuoyAgent

Collects buoy data from NDBC.

#### Class: BuoyAgent

**Inherits:** BaseAgent

**Data Collected:**
- Standard meteorological data (.txt)
- Spectral wave data (.spec)
- Continuous wind data (.cwind)

**Configuration:**
```yaml
data_sources:
  buoys:
    enabled: true
    urls:
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.txt"
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.spec"
```

**Usage:**
```python
from src.agents import BuoyAgent

agent = BuoyAgent(config)
results = await agent.collect("Hawaii", bundle_path)
```

### WeatherAgent

Collects weather forecasts from NWS.

#### Class: WeatherAgent

**Inherits:** BaseAgent

**Data Collected:**
- Gridpoint forecasts (JSON)
- 7-day forecasts
- Wind conditions

**Configuration:**
```yaml
data_sources:
  weather:
    enabled: true
    urls:
      - "https://api.weather.gov/gridpoints/HNL/12,52/forecast"
```

**Usage:**
```python
from src.agents import WeatherAgent

agent = WeatherAgent(config)
results = await agent.collect("Hawaii", bundle_path)
```

## Data Processing

### Data Processors

All processors inherit from `DataProcessor`.

#### Class: DataProcessor

**Purpose:** Base class for data processing with validation.

**Constructor:**
```python
DataProcessor(config: Config)
```

**Methods:**

**`process(data: Any) -> ProcessResult`**
```python
processor = DataProcessor(config)
result = processor.process(raw_data)

if result.success:
    print(f"Processed: {result.data}")
else:
    print(f"Error: {result.error}")
```

**Abstract method** - Must be implemented by subclasses

**`validate(data: Any) -> bool`**
```python
is_valid = processor.validate(data)
```

**`process_bundle(bundle_id: str, pattern: str) -> List[ProcessResult]`**
```python
results = processor.process_bundle("24e7eaad-...", "buoy/*.txt")
```

#### Class: ProcessResult

**Purpose:** Result object for data processing.

**Attributes:**
- `success: bool` - Processing success
- `data: Any` - Processed data
- `metadata: Dict[str, Any]` - Processing metadata
- `error: Optional[str]` - Error message if failed
- `warnings: List[str]` - Warning messages

### BuoyProcessor

Processes buoy observation data.

#### Class: BuoyProcessor

**Inherits:** DataProcessor

**Processing:**
- Parses NDBC text format
- Quality validation
- Anomaly detection
- Trend analysis

**Methods:**

**`process(data: Dict[str, Any]) -> ProcessResult`**
```python
processor = BuoyProcessor(config)
result = processor.process({
    "buoy_id": "51201",
    "raw_data": buoy_text
})

if result.success:
    buoy_data = result.data  # BuoyData object
    print(f"Wave height: {buoy_data.wave_height} m")
    print(f"Period: {buoy_data.dominant_period} s")
    print(f"Direction: {buoy_data.mean_wave_direction}°")
```

**Features:**
- Unit conversion (meters, feet, knots)
- Missing data handling
- Quality scoring
- Historical comparison

### WaveModelProcessor

Processes wave model outputs and detects swell events.

#### Class: WaveModelProcessor

**Inherits:** DataProcessor

**Processing:**
- Parses model data (GFS, Multi-Grid)
- Swell event detection
- Component separation (NW, W, SW, etc.)

**Methods:**

**`process(data: Dict[str, Any]) -> ProcessResult`**
```python
processor = WaveModelProcessor(config)
result = processor.process({
    "model": "GFS",
    "raw_data": model_output
})

if result.success:
    model_data = result.data  # ModelData object
    print(f"Detected {len(model_data.swell_events)} swell events")
```

**Swell Detection:**
- Minimum height threshold (0.5m default)
- Minimum period threshold (8.0s default)
- Minimum significance (40% energy)

### DataFusionSystem

Combines data from multiple sources into a unified forecast.

#### Class: DataFusionSystem

**Purpose:** Fuse buoy, weather, and model data with confidence weighting.

**Constructor:**
```python
DataFusionSystem(config: Config)
```

**Methods:**

**`process(fusion_data: Dict[str, Any]) -> ProcessResult`**
```python
fusion_system = DataFusionSystem(config)

result = fusion_system.process({
    "metadata": bundle_metadata,
    "buoy_data": [buoy1, buoy2, ...],
    "weather_data": [weather1, ...],
    "model_data": [model1, ...]
})

if result.success:
    swell_forecast = result.data  # SwellForecast object
```

**`save_result(result: ProcessResult, path: Path, overwrite: bool = False) -> None`**
```python
fusion_system.save_result(
    result,
    Path("data/bundle/processed/fused_forecast.json"),
    overwrite=True
)
```

**Fusion Algorithm:**
1. Weight data sources by reliability (buoy > model > weather)
2. Detect swell events across sources
3. Combine overlapping swells
4. Calculate confidence scores
5. Generate shore-specific predictions

## Forecast Engine

### ForecastEngine

AI-powered forecast generation with iterative refinement.

#### Class: ForecastEngine

**Purpose:** Generate surf forecasts using GPT models.

**Constructor:**
```python
ForecastEngine(config: Config)
```

**Methods:**

**`async generate_forecast(swell_forecast: SwellForecast) -> Dict[str, Any]`**
```python
engine = ForecastEngine(config)
forecast = await engine.generate_forecast(swell_forecast)

print(forecast['forecast_text'])
print(f"Confidence: {forecast['confidence']}")
print(f"Cost: ${forecast.get('cost', 0):.3f}")
```

**Returns:** Dictionary with:
- `forecast_id`: Unique forecast identifier
- `forecast_text`: Generated forecast text
- `confidence`: Overall confidence score (0.0-1.0)
- `created_at`: Timestamp
- `model`: Model used
- `cost`: Estimated API cost
- `tokens`: Token usage

**Features:**
- Iterative refinement (configurable cycles)
- Quality assessment
- Pat Caldwell style matching
- Multi-shore analysis
- Seasonal context

**`async refine_forecast(initial_forecast: str, feedback: str) -> Dict[str, Any]`**
```python
refined = await engine.refine_forecast(
    initial_forecast=forecast_text,
    feedback="Add more detail about swell timing"
)
```

### ForecastFormatter

Format forecasts into multiple output formats.

#### Class: ForecastFormatter

**Purpose:** Convert forecast data into markdown, HTML, and PDF.

**Constructor:**
```python
ForecastFormatter(config: Config)
```

**Methods:**

**`format_forecast(forecast: Dict[str, Any]) -> Dict[str, Path]`**
```python
formatter = ForecastFormatter(config)
outputs = formatter.format_forecast(forecast)

print(f"Markdown: {outputs['markdown']}")
print(f"HTML: {outputs['html']}")
print(f"PDF: {outputs['pdf']}")
```

**Returns:** Dictionary with paths to generated files

**Formats:**
- **Markdown:** Plain text, git-friendly
- **HTML:** Responsive, mobile-friendly, includes charts
- **PDF:** Print-ready, includes all assets

**`generate_charts(forecast: Dict[str, Any], output_dir: Path) -> Dict[str, Path]`**
```python
charts = formatter.generate_charts(forecast, Path("output/assets"))
# Returns: {"swell_mix": Path, "shore_focus": Path}
```

## Validation System

### ValidationDatabase

SQLite database for storing forecasts and validation results.

#### Class: ValidationDatabase

**Purpose:** Manage validation database schema and queries.

**Constructor:**
```python
ValidationDatabase(db_path: str = "data/validation.db")
```

**Methods:**

**`store_forecast(forecast_id: str, predictions: List[ForecastPrediction], metadata: Dict[str, Any]) -> None`**
```python
db = ValidationDatabase()
db.store_forecast(
    forecast_id="forecast_20251007_120000",
    predictions=[
        ForecastPrediction(
            shore="North Shore",
            height=8.0,
            period=12.0,
            direction=330.0
        ),
        # ... more shores
    ],
    metadata={"model": "gpt-4o", "confidence": 0.8}
)
```

**`get_forecasts_needing_validation(hours_after: int = 24) -> List[Dict[str, Any]]`**
```python
pending = db.get_forecasts_needing_validation(hours_after=24)
for forecast in pending:
    print(f"Validate: {forecast['forecast_id']}")
```

**`store_validation_result(forecast_id: str, validation_results: List[Dict[str, Any]]) -> None`**
```python
db.store_validation_result(
    forecast_id="forecast_20251007_120000",
    validation_results=[{
        "shore": "North Shore",
        "observed_height": 7.5,
        "observed_period": 11.5,
        "observed_direction": 335.0,
        "mae": 0.5,
        "rmse": 0.5,
        "category_match": True,
        "direction_error": 5.0
    }]
)
```

### ForecastValidator

Validates forecasts against actual observations.

#### Class: ForecastValidator

**Purpose:** Compare forecasts to buoy observations and calculate accuracy metrics.

**Constructor:**
```python
ForecastValidator(database: ValidationDatabase, buoy_fetcher: Optional[BuoyDataFetcher] = None)
```

**Methods:**

**`async validate_forecast(forecast_id: str, hours_after: int = 24) -> Dict[str, Any]`**
```python
validator = ForecastValidator(database)
results = await validator.validate_forecast(
    forecast_id="forecast_20251007_120000",
    hours_after=24
)

print(f"MAE: {results['metrics']['mae']:.2f} ft")
print(f"RMSE: {results['metrics']['rmse']:.2f} ft")
print(f"Categorical: {results['metrics']['categorical_accuracy']*100:.1f}%")
```

**Returns:** Dictionary with:
- `forecast_id`: Forecast identifier
- `validated_at`: Validation timestamp
- `predictions_total`: Total predictions
- `predictions_validated`: Successfully validated
- `metrics`: Accuracy metrics (MAE, RMSE, categorical, direction)

### BuoyDataFetcher

Fetches buoy observations for validation.

#### Class: BuoyDataFetcher

**Purpose:** Retrieve historical buoy data for specific time windows.

**Methods:**

**`async fetch_observations(buoy_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]`**
```python
fetcher = BuoyDataFetcher()
observations = await fetcher.fetch_observations(
    buoy_id="51201",
    start_time=datetime(2025, 10, 7, 12, 0),
    end_time=datetime(2025, 10, 7, 18, 0)
)

for obs in observations:
    print(f"{obs['timestamp']}: {obs['wave_height']} m")
```

**Returns:** List of observations with:
- `timestamp`: Observation time
- `wave_height`: Significant wave height (meters)
- `dominant_period`: Dominant wave period (seconds)
- `mean_wave_direction`: Mean direction (degrees)

## Data Structures

### SwellComponent

Individual swell component.

```python
from src.processing.models import SwellComponent

swell = SwellComponent(
    height=2.5,          # meters
    period=12.0,         # seconds
    direction=330.0,     # degrees
    energy=15.5,         # m²
    significance=0.65    # 0.0-1.0
)
```

**Attributes:**
- `height: float` - Swell height in meters
- `period: float` - Swell period in seconds
- `direction: float` - Direction in degrees (0-360)
- `energy: float` - Energy in m²
- `significance: float` - Ratio of swell energy to total (0.0-1.0)

### SwellEvent

Swell event spanning multiple time steps.

```python
from src.processing.models import SwellEvent

event = SwellEvent(
    start_time=datetime(2025, 10, 7, 0, 0),
    end_time=datetime(2025, 10, 9, 0, 0),
    peak_time=datetime(2025, 10, 8, 6, 0),
    components=[swell1, swell2],
    max_height=3.5
)
```

**Attributes:**
- `start_time: datetime` - Event start
- `end_time: datetime` - Event end
- `peak_time: datetime` - Time of maximum height
- `components: List[SwellComponent]` - Swell components
- `max_height: float` - Maximum height during event

### ForecastLocation

Shore-specific forecast.

```python
from src.processing.models import ForecastLocation

location = ForecastLocation(
    name="North Shore",
    coordinates=(21.6389, -158.0583),
    dominant_swell=swell_component,
    secondary_swells=[swell2, swell3],
    conditions="Good",
    rating=8.5
)
```

**Attributes:**
- `name: str` - Shore name
- `coordinates: Tuple[float, float]` - (latitude, longitude)
- `dominant_swell: SwellComponent` - Primary swell
- `secondary_swells: List[SwellComponent]` - Additional swells
- `conditions: str` - Text description
- `rating: float` - Quality rating (0-10)

### SwellForecast

Complete forecast data structure.

```python
from src.processing.models import SwellForecast

forecast = SwellForecast(
    bundle_id="24e7eaad-...",
    timestamp=datetime.now(),
    locations=[north_shore, south_shore, west_shore, east_shore],
    swell_events=[event1, event2],
    weather_conditions={},
    confidence=0.8,
    metadata={}
)
```

**Attributes:**
- `bundle_id: str` - Data bundle identifier
- `timestamp: datetime` - Forecast creation time
- `locations: List[ForecastLocation]` - Per-shore forecasts
- `swell_events: List[SwellEvent]` - Detected swell events
- `weather_conditions: Dict[str, Any]` - Weather data
- `confidence: float` - Overall confidence (0.0-1.0)
- `metadata: Dict[str, Any]` - Additional metadata

**Methods:**

**`to_dict() -> Dict[str, Any]`**
```python
forecast_dict = forecast.to_dict()
json.dump(forecast_dict, file)
```

**`from_dict(data: Dict[str, Any]) -> SwellForecast`**
```python
forecast = SwellForecast.from_dict(json.load(file))
```

## Error Handling

### Custom Exceptions

```python
from src.utils.exceptions import (
    SurfCastError,          # Base exception
    ConfigurationError,     # Config issues
    DataCollectionError,    # Collection failures
    ProcessingError,        # Processing failures
    ForecastError,          # Forecast generation failures
    ValidationError         # Validation failures
)
```

### Exception Hierarchy

```
SurfCastError (base)
├── ConfigurationError
├── DataCollectionError
│   ├── NetworkError
│   └── RateLimitError
├── ProcessingError
│   ├── DataValidationError
│   └── FusionError
├── ForecastError
│   ├── ModelError
│   └── RefinementError
└── ValidationError
    ├── DatabaseError
    └── BuoyDataError
```

### Usage

```python
from src.utils.exceptions import DataCollectionError

try:
    results = await collector.collect_data("Hawaii")
except DataCollectionError as e:
    logger.error(f"Collection failed: {e}")
    # Handle error
except SurfCastError as e:
    logger.error(f"Unexpected error: {e}")
    # Handle generic error
```

## Extension Points

### Custom Data Agent

Implement your own data collection agent:

```python
from src.agents import BaseAgent
from pathlib import Path

class MyCustomAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(name="my_agent", config=config)

    async def collect(self, region: str, bundle_path: Path) -> Dict[str, Any]:
        """Collect custom data."""
        # Get URLs for this region
        urls = self._get_urls(region)

        # Download data
        results = []
        for url in urls:
            result = await self.http_client.download_file(
                url,
                bundle_path / self.name / self._filename_from_url(url)
            )
            results.append(result)

        # Return summary
        return {
            "agent": self.name,
            "total": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success)
        }

    def _get_urls(self, region: str) -> List[str]:
        """Get URLs for region."""
        return self.config.get('data_sources', 'my_agent', {}).get('urls', [])
```

**Register Agent:**
```python
# In src/core/data_collector.py
from src.agents import MyCustomAgent

class DataCollector:
    def __init__(self, config: Config):
        self.agents = [
            BuoyAgent(config),
            WeatherAgent(config),
            MyCustomAgent(config),  # Add your agent
        ]
```

### Custom Data Processor

Implement your own data processor:

```python
from src.processing import DataProcessor, ProcessResult

class MyCustomProcessor(DataProcessor):
    def __init__(self, config):
        super().__init__(config)

    def process(self, data: Dict[str, Any]) -> ProcessResult:
        """Process custom data."""
        try:
            # Validate input
            if not self.validate(data):
                return ProcessResult(
                    success=False,
                    error="Validation failed"
                )

            # Process data
            processed_data = self._transform(data)

            # Return result
            return ProcessResult(
                success=True,
                data=processed_data,
                metadata={"processor": "my_custom"}
            )

        except Exception as e:
            return ProcessResult(
                success=False,
                error=str(e)
            )

    def validate(self, data: Any) -> bool:
        """Validate input data."""
        return isinstance(data, dict) and 'required_field' in data

    def _transform(self, data: Dict[str, Any]) -> Any:
        """Transform data to desired format."""
        # Your transformation logic
        return transformed_data
```

### Custom Forecast Formatter

Add a new output format:

```python
from src.forecast_engine import ForecastFormatter

class MyCustomFormatter(ForecastFormatter):
    def format_forecast(self, forecast: Dict[str, Any]) -> Dict[str, Path]:
        """Format forecast with custom output."""
        outputs = super().format_forecast(forecast)

        # Add custom format
        custom_path = self._create_custom_format(forecast)
        outputs['custom'] = custom_path

        return outputs

    def _create_custom_format(self, forecast: Dict[str, Any]) -> Path:
        """Create custom format output."""
        output_path = self.output_dir / f"{forecast['forecast_id']}.custom"

        # Generate custom format
        with open(output_path, 'w') as f:
            f.write(self._generate_custom(forecast))

        return output_path

    def _generate_custom(self, forecast: Dict[str, Any]) -> str:
        """Generate custom format content."""
        # Your custom formatting logic
        return custom_content
```

## Summary

This API documentation covers:
- **Core Modules:** Config, HTTPClient, RateLimiter, DataCollector, BundleManager
- **Data Collection:** BaseAgent, BuoyAgent, WeatherAgent, ModelAgent
- **Data Processing:** DataProcessor, BuoyProcessor, WaveModelProcessor, DataFusionSystem
- **Forecast Engine:** ForecastEngine, ForecastFormatter
- **Validation:** ValidationDatabase, ForecastValidator, BuoyDataFetcher
- **Data Structures:** SwellComponent, SwellEvent, ForecastLocation, SwellForecast
- **Error Handling:** Custom exception hierarchy
- **Extension Points:** Custom agents, processors, formatters

For usage examples and configuration, see:
- [README.md](README.md) - Quick start and basic usage
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md) - Validation system details
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment

All modules follow consistent patterns:
- Constructor accepts `Config` object
- Async methods for I/O operations
- Result objects for success/failure handling
- Type hints for all parameters and returns
- Comprehensive error handling with custom exceptions
