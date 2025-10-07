# SurfCastAI Configuration Guide

## Table of Contents

- [Overview](#overview)
- [Configuration Files](#configuration-files)
- [General Settings](#general-settings)
- [OpenAI Settings](#openai-settings)
- [Data Collection Settings](#data-collection-settings)
- [Rate Limits](#rate-limits)
- [Data Sources](#data-sources)
- [Processing Settings](#processing-settings)
- [Forecast Settings](#forecast-settings)
- [Validation Settings](#validation-settings)
- [Environment Variables](#environment-variables)
- [Advanced Configuration](#advanced-configuration)

## Overview

SurfCastAI uses a hierarchical configuration system:

1. **Environment Variables** (`.env` file) - Highest priority, for secrets
2. **YAML Configuration** (`config/config.yaml`) - Main configuration
3. **Default Values** - Hardcoded fallbacks in source code

### Configuration Priority

```
.env (OPENAI_API_KEY)
    ↓ (overrides)
config.yaml (openai.api_key)
    ↓ (overrides)
Default values in code
```

### Quick Setup

```bash
# 1. Copy template
cp config/config.example.yaml config/config.yaml

# 2. Set API key in .env
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# 3. Remove API key from config.yaml (security best practice)
# Edit config/config.yaml and delete the api_key line

# 4. Customize other settings as needed
nano config/config.yaml
```

## Configuration Files

### config.yaml

Main configuration file (not committed to git).

**Location:** `config/config.yaml`

**Structure:**
```yaml
general:           # Logging, paths, timezone
openai:            # AI model settings
data_collection:   # HTTP client settings
rate_limits:       # Per-domain request throttling
data_sources:      # URLs for buoys, weather, models, etc.
processing:        # Data processing thresholds
forecast:          # Forecast generation settings
validation:        # Validation system settings (optional)
```

### config.example.yaml

Template with safe example values (committed to git).

**Location:** `config/config.example.yaml`

**Purpose:**
- Reference for all available settings
- Safe to share (no secrets)
- Copy to create `config.yaml`

### .env

Environment variables for sensitive credentials (not committed to git).

**Location:** `.env` (project root)

**Contents:**
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

**Security:**
- Already in `.gitignore`
- Never commit to version control
- Use for all API keys and secrets

## General Settings

Controls logging, file paths, and timezone.

```yaml
general:
  log_level: INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_file: logs/surfcastai.log  # Log file path
  output_directory: output     # Forecast output directory
  data_directory: data         # Data collection directory
  timezone: Pacific/Honolulu   # Timezone for timestamps
```

### log_level

Controls verbosity of logging.

**Options:**
- `DEBUG`: Detailed diagnostic info (for development)
- `INFO`: General informational messages (recommended for production)
- `WARNING`: Warning messages only
- `ERROR`: Error messages only
- `CRITICAL`: Critical errors only

**Example:**
```yaml
general:
  log_level: DEBUG  # See all HTTP requests, data processing details
```

**Use Cases:**
- Development: `DEBUG`
- Production: `INFO`
- Troubleshooting: `DEBUG`
- Quiet operation: `WARNING`

### log_file

Path to log file (relative to project root).

**Default:** `logs/surfcastai.log`

**Example:**
```yaml
general:
  log_file: /var/log/surfcastai/app.log  # Absolute path
```

**Notes:**
- Parent directory must exist
- Log file rotates automatically when large
- Also logs to console (stdout)

### output_directory

Directory for generated forecasts.

**Default:** `output`

**Structure:**
```
output/
└── forecast_20251007_120000/
    ├── forecast_20251007_120000.md
    ├── forecast_20251007_120000.html
    ├── forecast_20251007_120000.pdf
    ├── assets/
    │   ├── swell_mix.png
    │   └── shore_focus.png
    └── metadata.json
```

### data_directory

Directory for collected data bundles.

**Default:** `data`

**Structure:**
```
data/
├── BUNDLE_ID/
│   ├── buoy/
│   ├── weather/
│   ├── models/
│   ├── satellite/
│   └── processed/
│       └── fused_forecast.json
└── validation.db
```

### timezone

Timezone for timestamps in forecasts and logs.

**Default:** `Pacific/Honolulu`

**Options:** Any IANA timezone (e.g., `America/Los_Angeles`, `UTC`)

## OpenAI Settings

Configuration for OpenAI API and model selection.

```yaml
openai:
  model: gpt-4o                          # Model to use
  api_key: your-openai-api-key-here     # API key (use .env instead!)
  temperature: 0.7                       # Creativity (0.0-1.0)
  max_tokens: 4000                       # Max response tokens
```

### model

OpenAI model to use for forecast generation.

**Recommended Options:**

| Model | Cost | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| `gpt-4o` | High | Excellent | Fast | Production, best quality |
| `gpt-4o-mini` | Low | Good | Fast | Development, cost-sensitive |
| `gpt-5-nano` | Medium | Excellent | Medium | Production, balanced |

**Example:**
```yaml
openai:
  model: gpt-4o  # Best quality, higher cost (~$0.05/forecast)
```

**Cost Estimates (per forecast):**
- `gpt-4o`: $0.03-0.07
- `gpt-4o-mini`: $0.01-0.02
- `gpt-5-nano`: $0.02-0.04

**Quality Comparison:**
- `gpt-4o`: Best swell analysis, natural language, Pat Caldwell style
- `gpt-4o-mini`: Good but less detailed, occasionally generic
- `gpt-5-nano`: Excellent balance, handles complex multi-swell scenarios

### temperature

Controls randomness/creativity in generated text.

**Range:** 0.0 (deterministic) to 1.0 (creative)

**Default:** 0.7

**Guidelines:**
- `0.0-0.3`: Focused, consistent, less creative (technical documentation)
- `0.4-0.7`: Balanced (recommended for forecasts)
- `0.8-1.0`: Creative, varied, less predictable (experimental)

**Example:**
```yaml
openai:
  temperature: 0.5  # More consistent forecast style
```

### max_tokens

Maximum tokens in the generated response.

**Default:** 4000

**Guidelines:**
- Minimum: 2000 (short forecasts)
- Recommended: 4000-6000 (full forecasts with details)
- Maximum: 16000 (gpt-4o supports up to 16k output tokens)

**Token Estimation:**
- Short forecast: ~1500 tokens
- Standard forecast: ~3000 tokens
- Detailed forecast: ~5000 tokens
- 1 token ≈ 0.75 words

**Example:**
```yaml
openai:
  max_tokens: 6000  # Longer, more detailed forecasts
```

## Data Collection Settings

HTTP client configuration for data fetching.

```yaml
data_collection:
  max_concurrent: 10      # Max simultaneous requests
  timeout: 30             # Request timeout (seconds)
  retry_attempts: 3       # Retry failed requests
  user_agent: "SurfCastAI/1.0 (+https://github.com/yourusername/surfCastAI)"
```

### max_concurrent

Maximum number of simultaneous HTTP requests.

**Default:** 10

**Guidelines:**
- Lower (5-10): Conservative, respectful of servers
- Higher (15-20): Faster collection, more aggressive
- Very high (30+): Risk of rate limiting

**Example:**
```yaml
data_collection:
  max_concurrent: 15  # Faster data collection
```

### timeout

Request timeout in seconds.

**Default:** 30

**Guidelines:**
- Short (10-15s): Fast failure, retry quickly
- Medium (30s): Recommended for most sources
- Long (60s+): Slow connections, large files

**Example:**
```yaml
data_collection:
  timeout: 45  # Wait longer for slow servers
```

### retry_attempts

Number of retry attempts for failed requests.

**Default:** 3

**Behavior:**
- Exponential backoff (1s, 2s, 4s, 8s...)
- Only retries on network errors, not 4xx errors
- Respects rate limits between retries

**Example:**
```yaml
data_collection:
  retry_attempts: 5  # More persistent retries
```

## Rate Limits

Per-domain rate limiting to respect server constraints.

```yaml
rate_limits:
  "www.ndbc.noaa.gov":
    requests_per_second: 0.5  # 1 request every 2 seconds
    burst_size: 3             # Allow 3 rapid requests
  "api.weather.gov":
    requests_per_second: 0.25
    burst_size: 2
  default:
    requests_per_second: 0.2
    burst_size: 2
```

### How Rate Limiting Works

SurfCastAI uses a **token bucket algorithm**:

1. Each domain has a bucket with `burst_size` tokens
2. Tokens refill at `requests_per_second` rate
3. Each request consumes 1 token
4. If no tokens available, request waits

**Example:**
```yaml
rate_limits:
  "www.ndbc.noaa.gov":
    requests_per_second: 0.5  # Refill 1 token every 2 seconds
    burst_size: 3             # Bucket holds 3 tokens max
```

**Timeline:**
```
t=0s:  Bucket has 3 tokens, make 3 rapid requests → Bucket empty
t=2s:  Bucket has 1 token (refilled), make 1 request → Bucket empty
t=4s:  Bucket has 1 token (refilled), make 1 request → Bucket empty
t=6s:  Bucket has 1 token (refilled), make 1 request → Bucket empty
```

### Domain-Specific Settings

**NDBC (Buoy Data):**
```yaml
"www.ndbc.noaa.gov":
  requests_per_second: 0.5  # 1 request per 2 seconds
  burst_size: 3             # Allow initial burst of 3
```

**NOAA Weather API:**
```yaml
"api.weather.gov":
  requests_per_second: 0.25  # 1 request per 4 seconds
  burst_size: 2
```

**NOAA Model Data:**
```yaml
"nomads.ncep.noaa.gov":
  requests_per_second: 0.15  # 1 request per 6-7 seconds
  burst_size: 2
```

**Conservative (Slow Servers):**
```yaml
"ocean.weather.gov":
  requests_per_second: 0.1  # 1 request per 10 seconds
  burst_size: 1
```

### Tuning Rate Limits

**More Aggressive (faster collection):**
```yaml
rate_limits:
  "www.ndbc.noaa.gov":
    requests_per_second: 1.0  # Doubled
    burst_size: 5             # Larger burst
```

**More Conservative (respectful):**
```yaml
rate_limits:
  "www.ndbc.noaa.gov":
    requests_per_second: 0.25  # Slower
    burst_size: 1              # No burst
```

**Signs of Rate Limiting Issues:**
- 429 errors in logs
- Consistent timeouts
- Slow data collection

## Data Sources

URLs for data collection agents.

```yaml
data_sources:
  buoys:
    enabled: true
    urls:
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.txt"
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.spec"
      # ... more buoys
  weather:
    enabled: true
    urls:
      - "https://api.weather.gov/gridpoints/HNL/12,52/forecast"
  # ... more source types
```

### Buoy Sources

**Standard Text Files (.txt):**
- Recent observations (last 45 days)
- Wave height, period, direction
- Updated hourly

**Spectral Files (.spec):**
- Detailed swell components
- Energy density by frequency/direction
- Updated hourly

**Key Buoys for Oahu:**

| Buoy | Location | Coverage | Priority |
|------|----------|----------|----------|
| 51201 | NW Hawaii (220nm) | North Shore | High |
| 51202 | Molokai (40nm) | South Shore | High |
| 51001 | NW Hawaii (350nm) | Long-range NW | Medium |
| 51004 | SE Hawaii (80nm) | South/East | Medium |
| 51101 | Hilo (55nm) | East Shore | Low |
| 51207 | Kaneohe Bay | North/East | Medium |

**Example - Enable/Disable Buoys:**
```yaml
data_sources:
  buoys:
    enabled: true  # Set to false to disable all buoys
    urls:
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.txt"  # Keep
      - "https://www.ndbc.noaa.gov/data/realtime2/51201.spec"  # Keep
      # Comment out or remove unwanted buoys
```

### Weather Sources

**NWS Gridpoint Forecasts:**
- 7-day forecasts
- Wind speed/direction
- Weather conditions

**Locations:**
- HNL/12,52: North Shore (Haleiwa area)
- HNL/8,65: Honolulu (South Shore)

### METAR Sources

**Aviation Weather:**
- Current conditions
- Wind speed/direction
- Visibility, pressure

**Stations:**
- PHNL: Honolulu International Airport
- PHJR: Kalaeloa (Barbers Point)

### Tide Sources

**NOAA Tides & Currents API:**
- Water levels
- Tide predictions

**Station:**
- 1612340: Honolulu Harbor

### Model Sources

**Wave Models:**
- GFS Wave Model (global)
- Multi-Grid Wave Model (global)
- SWAN Oahu Model (local)

**Update Frequency:** Every 6 hours

### Satellite Sources

**GOES-17 Imagery:**
- Geocolor satellite images
- 24-hour loops
- Cloud patterns

### Tropical Sources

**NHC Tropical Outlook:**
- Central Pacific storms
- 2-day and 5-day outlooks

## Processing Settings

Data quality thresholds and processing parameters.

```yaml
processing:
  buoy:
    min_confidence: 0.7        # Minimum buoy data confidence
    anomaly_threshold: 3.0     # Sigma threshold for anomalies
  weather:
    min_confidence: 0.6
  model:
    min_confidence: 0.7
    swell_detection:
      min_height: 0.5          # Minimum swell height (meters)
      min_period: 8.0          # Minimum swell period (seconds)
      min_significance: 0.4    # Minimum swell significance
  fusion:
    weight_buoy: 0.7           # Buoy data weight
    weight_model: 0.6          # Model data weight
    weight_weather: 0.5        # Weather data weight
    min_combined_confidence: 0.6
```

### Buoy Processing

**min_confidence:**
- Minimum quality score to accept buoy data
- Range: 0.0-1.0
- Default: 0.7 (70%)

**anomaly_threshold:**
- Standard deviations for anomaly detection
- Range: 1.0-5.0
- Default: 3.0 (99.7% confidence interval)

**Example:**
```yaml
processing:
  buoy:
    min_confidence: 0.8  # Stricter quality requirements
    anomaly_threshold: 2.5  # More sensitive to anomalies
```

### Swell Detection

**min_height:**
- Minimum wave height to consider as swell
- Units: meters
- Default: 0.5m (~1.5 ft)

**min_period:**
- Minimum period to distinguish swell from wind waves
- Units: seconds
- Default: 8.0s

**min_significance:**
- Minimum ratio of swell energy to total energy
- Range: 0.0-1.0
- Default: 0.4 (40% of total energy)

**Example - Detect Only Significant Swells:**
```yaml
processing:
  model:
    swell_detection:
      min_height: 1.0      # Only swells > 1m (3 ft)
      min_period: 10.0     # Only long-period swells
      min_significance: 0.5  # Dominant swells only
```

### Data Fusion Weights

Relative importance of each data source in the fusion process.

**Default Weights:**
- Buoy: 0.7 (most reliable, direct observations)
- Model: 0.6 (good coverage, forecast capability)
- Weather: 0.5 (context, wind conditions)

**Tuning Guidelines:**
- Increase buoy weight if buoy data very reliable
- Increase model weight if buoy coverage sparse
- Decrease weights if data source frequently incorrect

**Example - Trust Buoys More:**
```yaml
processing:
  fusion:
    weight_buoy: 0.9    # High trust in buoy data
    weight_model: 0.5   # Lower trust in models
    weight_weather: 0.4  # Weather for context only
```

## Forecast Settings

Forecast generation and refinement parameters.

```yaml
forecast:
  templates_dir: src/forecast_engine/templates
  refinement_cycles: 2           # Number of refinement iterations
  quality_threshold: 0.8         # Minimum quality score
  use_local_generator: false     # Use rule-based fallback
  formats: markdown,html,pdf     # Output formats
  max_images: 10                 # Max images for GPT-5
  token_budget: 150000           # Token budget for context
  warn_threshold: 200000         # Warning threshold
  enable_budget_enforcement: true
  image_detail_levels:
    pressure_charts: high        # 3000 tokens each
    wave_models: auto            # 1500 tokens each
    satellite: auto              # 1500 tokens each
    sst_charts: low              # 500 tokens each
```

### refinement_cycles

Number of iterative refinement passes for forecast generation.

**Range:** 0-5

**Default:** 2

**Behavior:**
1. Generate initial forecast
2. Assess quality (completeness, detail, style)
3. If below threshold, refine with feedback
4. Repeat up to `refinement_cycles` times

**Example:**
```yaml
forecast:
  refinement_cycles: 3  # More refinement, higher quality, higher cost
```

**Trade-offs:**
- More cycles: Better quality, higher cost, slower
- Fewer cycles: Faster, cheaper, potentially lower quality

### quality_threshold

Minimum quality score (0.0-1.0) to accept a forecast without refinement.

**Default:** 0.8

**Criteria:**
- Completeness (all shores covered)
- Detail level (specific numbers, timing, confidence)
- Style match (Pat Caldwell-like analysis)

**Example:**
```yaml
forecast:
  quality_threshold: 0.9  # Stricter quality requirements
```

### use_local_generator

Use rule-based fallback generator instead of OpenAI API.

**Default:** false

**Use Cases:**
- Development without API costs
- Offline operation
- Fallback if API unavailable

**Example:**
```yaml
forecast:
  use_local_generator: true  # No API calls, free operation
```

**Note:** Local generator produces basic forecasts without AI refinement.

### formats

Output formats for generated forecasts.

**Options:** `markdown`, `html`, `pdf`

**Default:** `markdown,html,pdf`

**Examples:**
```yaml
forecast:
  formats: markdown  # Markdown only

forecast:
  formats: markdown,html  # Markdown and HTML, skip PDF
```

**Use Cases:**
- Markdown: Git-friendly, plain text
- HTML: Web viewer, mobile-friendly
- PDF: Print-ready, archival

### max_images

Maximum number of images to include in GPT-5 context.

**Default:** 10

**GPT-5 Limit:** 10 images per request

**Recommendations:**
- Full analysis: 10 images
- Cost-conscious: 6-8 images
- Text-only: 0 images

**Example:**
```yaml
forecast:
  max_images: 6  # Reduce cost by limiting images
```

### token_budget

Maximum tokens for entire context (text + images).

**Default:** 150000

**GPT-5 Context Window:** 200,000 tokens

**Token Breakdown:**
- Prompt text: ~5,000 tokens
- Buoy data: ~2,000 tokens
- Weather data: ~1,000 tokens
- High-res image: ~3,000 tokens
- Auto-res image: ~1,500 tokens
- Low-res image: ~500 tokens

**Example:**
```yaml
forecast:
  token_budget: 100000  # More conservative budget
```

### image_detail_levels

Specify detail level for each image type.

**Options:** `high`, `auto`, `low`

**Token Costs:**
- `high`: ~3,000 tokens per image
- `auto`: ~1,500 tokens per image
- `low`: ~500 tokens per image

**Default Configuration:**
```yaml
forecast:
  image_detail_levels:
    pressure_charts: high     # Critical for swell forecasting
    wave_models: auto         # Important but not critical
    satellite: auto           # Validation and context
    sst_charts: low           # Context only
```

**Cost Optimization:**
```yaml
forecast:
  image_detail_levels:
    pressure_charts: auto     # Reduce critical images to auto
    wave_models: low          # Reduce to low detail
    satellite: low            # Reduce to low detail
    sst_charts: low           # Keep at low
```

## Validation Settings

Configuration for the validation system (optional).

```yaml
validation:
  database_path: data/validation.db
  buoy_mapping:
    "North Shore": "51201"
    "South Shore": "51202"
    "West Shore": "51201"
    "East Shore": "51004"
  accuracy_targets:
    mae: 2.0        # Maximum MAE (feet)
    rmse: 2.5       # Maximum RMSE (feet)
    categorical: 0.75  # Minimum categorical accuracy
    direction: 0.80    # Minimum direction accuracy
  validation_window:
    min_hours: 24   # Minimum hours after forecast
    max_hours: 48   # Maximum hours after forecast
```

### database_path

Path to SQLite validation database.

**Default:** `data/validation.db`

**Example:**
```yaml
validation:
  database_path: /var/lib/surfcastai/validation.db
```

### buoy_mapping

Map forecast shores to validation buoys.

**Default Mapping:**
- North Shore → 51201 (NW Hawaii)
- South Shore → 51202 (Molokai)
- West Shore → 51201 (NW Hawaii)
- East Shore → 51004 (SE Hawaii)

**Custom Mapping:**
```yaml
validation:
  buoy_mapping:
    "North Shore": "51207"  # Use Kaneohe Bay instead
    "South Shore": "51202"
    "West Shore": "51001"   # Use far NW buoy
    "East Shore": "51101"   # Use Hilo buoy
```

### accuracy_targets

Target metrics for forecast accuracy.

**Defaults:**
```yaml
validation:
  accuracy_targets:
    mae: 2.0         # Mean Absolute Error < 2.0 ft
    rmse: 2.5        # Root Mean Square Error < 2.5 ft
    categorical: 0.75  # 75% categorical accuracy
    direction: 0.80    # 80% direction accuracy
```

**Stricter Targets:**
```yaml
validation:
  accuracy_targets:
    mae: 1.5         # Tighter error tolerance
    rmse: 2.0        # Tighter RMSE
    categorical: 0.85  # Higher category accuracy
    direction: 0.85    # Higher direction accuracy
```

### validation_window

Time window for comparing forecast to observations.

**Default:**
```yaml
validation:
  validation_window:
    min_hours: 24  # Don't validate before 24 hours
    max_hours: 48  # Don't validate after 48 hours
```

**Use Cases:**
- Short-term: min_hours=12, max_hours=24
- Long-term: min_hours=48, max_hours=72

## Environment Variables

Sensitive configuration via environment variables.

### .env File Format

```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx

# Optional: Override output directory
SURFCAST_OUTPUT_DIR=/path/to/output

# Optional: Override data directory
SURFCAST_DATA_DIR=/path/to/data
```

### Supported Variables

**OPENAI_API_KEY:**
- Required for AI-powered forecasts
- Get from: https://platform.openai.com/api-keys
- Format: `sk-proj-...` or `sk-...`

**SURFCAST_OUTPUT_DIR:**
- Override default output directory
- Useful for web viewer deployment

**SURFCAST_DATA_DIR:**
- Override default data directory
- Useful for shared storage

### Security Best Practices

1. **Never commit .env to git**
   ```bash
   # Verify .env is in .gitignore
   grep .env .gitignore
   ```

2. **Use restrictive permissions**
   ```bash
   chmod 600 .env
   ```

3. **Rotate keys regularly**
   - OpenAI: Rotate every 90 days
   - Revoke old keys after rotation

4. **Use separate keys for dev/prod**
   ```bash
   # .env.development
   OPENAI_API_KEY=sk-dev-key-here

   # .env.production
   OPENAI_API_KEY=sk-prod-key-here
   ```

## Advanced Configuration

### Multiple Configuration Files

Use different configs for different environments:

```bash
# Development
python src/main.py --config config/dev.yaml run

# Production
python src/main.py --config config/prod.yaml run

# Testing
python src/main.py --config config/test.yaml run
```

### Config Templates

**config/dev.yaml:**
```yaml
general:
  log_level: DEBUG
openai:
  model: gpt-4o-mini  # Cheaper for development
forecast:
  refinement_cycles: 1  # Faster iteration
  formats: markdown  # Skip slow PDF generation
```

**config/prod.yaml:**
```yaml
general:
  log_level: INFO
openai:
  model: gpt-4o  # Best quality
forecast:
  refinement_cycles: 2
  formats: markdown,html,pdf
```

### Dynamic Configuration

Override config values at runtime:

```python
from src.core import load_config

# Load config
config = load_config('config/config.yaml')

# Override specific values
config.set('openai', 'model', 'gpt-4o-mini')
config.set('forecast', 'refinement_cycles', 1)

# Use modified config
forecast_engine = ForecastEngine(config)
```

### Validation-Only Configuration

For validation-focused deployments:

```yaml
general:
  log_level: WARNING  # Quiet operation

data_collection:
  max_concurrent: 5  # Slower, less aggressive

data_sources:
  buoys:
    enabled: true  # Only enable buoys
  weather:
    enabled: false
  models:
    enabled: false
  satellite:
    enabled: false

forecast:
  enabled: false  # Skip forecast generation

validation:
  enabled: true
  validation_window:
    min_hours: 24
    max_hours: 24  # Validate exactly 24 hours after
```

### Performance Tuning

**Fast Collection (parallel):**
```yaml
data_collection:
  max_concurrent: 20  # More parallelism

rate_limits:
  default:
    requests_per_second: 1.0  # Faster rate
    burst_size: 5
```

**Memory-Constrained:**
```yaml
forecast:
  max_images: 4  # Fewer images
  token_budget: 50000  # Smaller context

data_collection:
  max_concurrent: 3  # Less memory usage
```

**Cost-Optimized:**
```yaml
openai:
  model: gpt-4o-mini  # Cheapest model

forecast:
  refinement_cycles: 0  # No refinement
  max_images: 0  # No images (text-only)
  formats: markdown  # Skip PDF
```

## Summary

SurfCastAI's configuration system provides:
- **Hierarchical priority:** Environment variables → YAML → Defaults
- **Security:** API keys in `.env`, not in git
- **Flexibility:** Override any setting for dev/test/prod
- **Tuning:** Adjust quality, cost, speed, accuracy targets
- **Safety:** Rate limiting, retry logic, error handling

Key configuration areas:
1. **OpenAI:** Model selection, cost vs quality trade-offs
2. **Data Collection:** Parallelism, rate limits, retries
3. **Processing:** Quality thresholds, anomaly detection, fusion weights
4. **Forecast:** Refinement, image handling, token budgets
5. **Validation:** Accuracy targets, buoy mapping, time windows

For questions or issues, see [README.md](README.md) troubleshooting section.
