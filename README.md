# SurfCastAI: AI-Powered Oahu Surf Forecasting System

A comprehensive, automated, AI-powered surf forecasting system for Oahu, Hawaii. SurfCastAI combines robust data collection from multiple marine and weather sources, sophisticated data processing, advanced AI techniques, and automated validation to generate accurate, detailed surf forecasts in the style of veteran Hawaiian forecasters.

## Features

- **Automated Data Collection** from 30+ marine and weather sources
  - Real-time buoy observations (NDBC)
  - Weather forecasts (NWS/NOAA)
  - Wave model outputs (GFS, Multi-Grid Wave Model)
  - Satellite imagery (GOES-17)
  - Tropical weather updates
  - Surface pressure charts
- **Intelligent Data Processing** with quality validation and anomaly detection
- **AI-Powered Forecast Generation** using GPT-4o/GPT-5 models
- **Pat Caldwell-Style Output** with detailed swell analysis and shore breakdowns
- **Automated Validation System** with buoy-driven accuracy metrics (MAE, RMSE, categorical)
- **Multi-Format Output** (Markdown, HTML, PDF) with responsive mobile design
- **Visualization Assets** (swell mix charts, shore focus graphs)
- **Web Viewer** for browsing generated forecasts locally
- **Confidence Scoring** based on data quality and source reliability

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/surfCastAI.git
cd surfCastAI

# Run the setup script
./setup.sh
# This will:
# - Create a virtual environment
# - Install dependencies
# - Set up necessary directories
# - Create configuration files
#
# Tip: if your shell sources conda/pyenv in login shells, point PYTHON at a
# concrete interpreter before running the script, e.g.
#   export PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3
#   ./setup.sh --force
# See docs/PYTHON_ENVIRONMENT.md for more details.

# Activate the virtual environment
source venv/bin/activate

# Configure your API keys (see Configuration below)
cp config/config.example.yaml config/config.yaml
echo "OPENAI_API_KEY=your-api-key-here" > .env

# Setup can be rerun safely; use `./setup.sh --force` to recreate the virtualenv and configs if needed.
```

### Basic Usage

#### 🏄 Tubular CLI Launcher (Recommended!)

For a radical, 80s-themed interactive experience:

```bash
python scripts/surf_launcher.py
```

Features:
- Totally tubular 80s surf theme with ASCII art
- Color-coded menus and status
- Easy model switching (GPT-5-nano/mini/5)
- Bundle selection and management
- Built-in help with surf tips
- Fun 80s slang throughout!

#### Command Line Interface

```bash
# Validate configuration before running
python src/main.py validate-config      # Check config for errors

# Generate a complete forecast
python src/main.py run --mode full

# Or run individual steps
python src/main.py run --mode collect   # Collect data only
python src/main.py run --mode process   # Process collected data
python src/main.py run --mode forecast  # Generate forecast from processed data

# View your forecasts
python src/main.py list                 # List all forecasts
python src/main.py info --bundle ID     # Show bundle details
```

### Validation Commands

```bash
# Validate a specific forecast
python src/main.py validate --forecast forecast_20251007_120000
python src/main.py validate-config

# Validate all pending forecasts (24+ hours old)
python src/main.py validate-all

# Generate accuracy report
python src/main.py accuracy-report --days 30
python src/main.py validate-config
```

## Security

SurfCastAI implements multiple layers of security to protect sensitive credentials and prevent common vulnerabilities.

### API Key Security

**IMPORTANT:** API keys MUST be stored in environment variables only. Never commit API keys to version control.

```bash
# Create .env file for local development
echo "OPENAI_API_KEY=your-key-here" > .env

# The system will load this automatically
python src/main.py run --mode forecast
```

**Security Features:**
- API keys enforced from environment variables only (not config files)
- `.env` file automatically excluded from git
- Configuration validation fails if API key missing
- Secure secrets management required in production

### SSRF Protection

All data source URLs are validated to prevent Server-Side Request Forgery attacks:
- Private IP ranges blocked (RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local addresses blocked (169.254.0.0/16)
- Loopback addresses blocked (127.0.0.0/8)
- IPv6 private ranges blocked (fc00::/7, fe80::/10, ::1/128)
- Only public internet URLs allowed for data sources

### Archive Security

Protection against malicious archive files:
- **Zip bomb detection:** Rejects files with compression ratio > 100:1
- **Path traversal protection:** Validates all archive member paths
- **File size limits:** Max 100MB per file, 1GB total per archive
- Atomic extraction with rollback on failure

### Data Validation

Physical constraints enforced on all buoy data:
- Wave height: 0-30 meters
- Dominant period: 4-30 seconds (filters phantom swells)
- Wind speed: 0-150 knots
- Pressure: 900-1100 millibars
- Water temperature: -2 to 35°C

## Configuration

SurfCastAI uses a secure configuration system with environment variables for sensitive credentials.

### Required Setup

1. **Copy the configuration template:**
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. **Create a `.env` file in the project root:**
   ```bash
   echo "OPENAI_API_KEY=your-actual-api-key-here" > .env
   ```

   **Note:** The `api_key` field has been removed from config.yaml for security. API keys must come from environment variables only.

### Configuration Validation

Configuration is validated at startup to catch errors early (fail-fast principle):

```bash
# Validate configuration manually
python src/main.py validate-config

# Errors prevent startup
python src/main.py run --mode forecast  # Validates automatically
```

**Validation Checks:**
- API key presence in environment
- Model names validity (gpt-4o, gpt-4o-mini, gpt-5-nano, etc.)
- Specialist model configuration (if specialist team enabled)
- Data source URL validity (must be public internet URLs)
- Rate limit values (must be > 0)
- Required directories exist and are writable

### Configuration Priority

The system loads configuration in this order:
1. **Environment variables** (`.env` file) - Highest priority
2. **Config file** (`config/config.yaml`) - Fallback
3. **Default values** - Used if neither is available

### Key Configuration Options

See [CONFIGURATION.md](/Users/zackjordan/code/surfCastAI/CONFIGURATION.md) for complete details. Key settings include:

- **OpenAI Model Selection:** `gpt-4o`, `gpt-4o-mini`, or `gpt-5-nano`
- **Rate Limits:** Per-domain request throttling
- **Data Sources:** Enable/disable specific data sources
- **Processing:** Quality thresholds and confidence scoring
  - **Bounds Validation:** Physical constraints on wave metrics
  - **Phantom Swell Filtering:** Minimum period 4.0s (configurable)
  - **Quality Flags:** Control data filtering before analysis
- **Validation:** Accuracy targets and validation intervals
- **Prompt Loader:** `forecast.templates_dir` points to JSON prompt templates (`config/prompts/`), loaded via `src/utils/prompt_loader.py` with fallback when files are missing or invalid.
- **Multimodal Images:** `forecast.max_images` limits GPT-5 vision payloads; `forecast.image_detail_levels` configures detail for `pressure_charts`, `wave_models`, `satellite`, and `sst_charts`.

See `config/prompts/README.md` for JSON schema details and examples.

## Usage Examples

### Full Pipeline

```bash
# Run complete collection → processing → forecast → validation
python src/main.py run --mode full
```

### Data Collection Only

```bash
# Collect data from all enabled sources
python src/main.py run --mode collect

# View collected data
python src/main.py list
python src/main.py info --bundle BUNDLE_ID
```

### Forecast Generation

```bash
# Generate forecast from latest data bundle
python src/main.py run --mode forecast

# Generate forecast from specific bundle
python src/main.py run --mode forecast --bundle BUNDLE_ID
```

### Validation Workflow

```bash
# Generate a forecast
python src/main.py run --mode full

# Wait 24+ hours for actual conditions to develop

# Validate the forecast against actual buoy observations
python src/main.py validate --forecast forecast_20251007_120000

# View accuracy metrics
python src/main.py accuracy-report --days 7
```

## Validation System

SurfCastAI includes a comprehensive validation system that compares forecasts against actual buoy observations.

### How It Works

1. **Forecast Capture:** Predictions are extracted and stored in the validation database
2. **Observation Fetching:** Real buoy data is collected 24+ hours after forecast time
3. **Accuracy Calculation:** Multiple metrics computed (MAE, RMSE, categorical, direction)
4. **Reporting:** Aggregated statistics and per-shore breakdowns

### Validation Metrics

- **MAE (Mean Absolute Error):** Average error in wave height (target: < 2.0 ft)
- **RMSE (Root Mean Square Error):** Penalizes larger errors (target: < 2.5 ft)
- **Categorical Accuracy:** Correct size category (small/moderate/large) (target: > 75%)
- **Direction Accuracy:** Correct swell direction within 22.5° (target: > 80%)

### Running Validations

```bash
# Validate all forecasts that are 24+ hours old
python src/main.py validate-all

# Validate a specific forecast
python src/main.py validate --forecast forecast_20251007_120000

# Generate accuracy report for last 30 days
python src/main.py accuracy-report --days 30
```

See [VALIDATION_GUIDE.md](/Users/zackjordan/code/surfCastAI/VALIDATION_GUIDE.md) for complete validation documentation.

## Web Viewer

Launch a local web server to browse generated forecasts:

```bash
# Start the web viewer
uvicorn src.web.app:app --reload

# Open in browser
open http://localhost:8000
```

Set `SURFCAST_OUTPUT_DIR` environment variable if your forecasts are stored outside `./output`.

## Project Structure

```
surfCastAI/
├── config/                    # Configuration files
│   ├── config.yaml           # Main config (not in git)
│   └── config.example.yaml   # Template (in git)
├── data/                      # Downloaded and processed data
│   ├── BUNDLE_ID/            # Timestamped data bundles
│   │   ├── buoy/             # Buoy observations
│   │   ├── weather/          # Weather forecasts
│   │   ├── models/           # Wave model data
│   │   ├── satellite/        # Satellite imagery
│   │   └── processed/        # Fused forecast data
│   └── validation.db         # Validation database
├── output/                    # Generated forecasts
│   └── forecast_TIMESTAMP/   # Individual forecast outputs
│       ├── forecast_*.md     # Markdown format
│       ├── forecast_*.html   # HTML format
│       ├── forecast_*.pdf    # PDF format
│       └── assets/           # Charts and visualizations
├── src/
│   ├── agents/               # Data collection agents
│   ├── core/                 # Core components (HTTP, rate limiting, config)
│   ├── forecast_engine/      # Forecast generation and refinement
│   ├── processing/           # Data processing and fusion
│   ├── validation/           # Forecast validation system
│   ├── web/                  # Web viewer
│   └── main.py              # Main entry point
├── tests/                     # Test suite
├── scripts/                   # Utility scripts
└── logs/                      # Application logs
```

## Entry Points

SurfCastAI provides two ways to interact with the system:

### 1. Command-Line Interface (Recommended)

```bash
python src/main.py [command] [options]
```

Use this for:
- Automated/scripted workflows
- CI/CD pipelines
- Production deployments
- Direct API-style control

### 2. Interactive Cyberpunk UI

```bash
python surfcast.py
```

Use this for:
- Interactive exploration
- Development and testing
- Visual feedback and progress
- Learning the system capabilities

Both entry points access the same underlying forecast engine and data pipeline.

## Requirements

- Python 3.9+
- aiohttp
- openai
- pillow
- weasyprint (for PDF generation)
- markdown
- pyyaml
- matplotlib
- fastapi
- uvicorn

All dependencies are installed via `setup.sh` or `pip install -r requirements.txt`.

## Testing

```bash
# Run unit tests
python -m unittest discover -s tests

# Test the forecast engine
python test_forecast_engine.py

# Run performance benchmarks
python benchmark_forecast_engine.py
```

See [tests/README.md](tests/README.md) for more information on the testing framework.

## Deployment

For production deployment, see [DEPLOYMENT.md](/Users/zackjordan/code/surfCastAI/DEPLOYMENT.md) for:
- Automated scheduling with cron/systemd
- Docker containerization
- Monitoring and alerting
- Backup and recovery

## Troubleshooting

### API Key Issues

**Problem:** `OPENAI_API_KEY environment variable not set` error

**Solution:**
```bash
# Verify .env file exists and contains your key
cat .env
# Should show: OPENAI_API_KEY=sk-...

# If not, create it
echo "OPENAI_API_KEY=your-key-here" > .env

# Make sure you're not setting api_key in config.yaml
# For security, API keys MUST come from environment variables only
```

**Note:** As of the latest update, API keys cannot be stored in config.yaml. This is a security enhancement to prevent accidental exposure of credentials in version control.

### Configuration Validation Errors

**Problem:** `Configuration validation failed` on startup

**Solution:**
```bash
# Run validation manually to see specific errors
python src/main.py validate-config

# Common issues and fixes:
# - Missing OPENAI_API_KEY: Create .env file (see above)
# - Invalid model name: Check spelling in config.yaml (gpt-4o, gpt-4o-mini, gpt-5-nano)
# - Missing specialist models: Add models for all specialists if use_specialist_team=true
# - Invalid URLs: Ensure all data source URLs are valid public internet URLs
# - Invalid rate limits: Ensure requests_per_second > 0 for all domains
```

### Specialist Engine Errors

**Problem:** `Specialist requires engine parameter` internal error

**Solution:**
This is an internal error that should not occur during normal operation. If you see this:
1. Report the issue with the full error traceback
2. The system should handle specialist initialization automatically
3. As a workaround, disable the specialist team temporarily:
   ```yaml
   forecast:
     use_specialist_team: false
   ```

### Cost Tracking Inaccurate

**Problem:** API cost tracking seems incorrect or inconsistent

**Solution:**
This issue was fixed in the latest version. If you're still seeing inaccurate costs:
- Update to the latest version (includes concurrent API call synchronization)
- The fix adds proper locking around cost counter updates
- Accuracy should be within 0.1% even under concurrent load

### Data Collection Failures

**Problem:** Multiple agents failing to collect data

**Solution:**
```bash
# Check network connectivity
curl -I https://www.ndbc.noaa.gov

# Check rate limits in config
cat config/config.yaml | grep -A 5 rate_limits

# Check logs for specific errors
tail -50 logs/surfcastai.log

# Verify data source URLs are valid and public
python src/main.py validate-config
```

### Validation Database Issues

**Problem:** `ValidationDatabase not found` or `table not found` errors

**Solution:**
```bash
# Database is created automatically on first validation
# If corrupted, delete and it will be recreated
rm data/validation.db

# Run validation again
python src/main.py validate-all
```

**Note:** The latest version includes transaction rollback protection to prevent database corruption during batch operations.

### Forecast Quality Issues

**Problem:** Generated forecasts seem inaccurate or generic

**Solution:**
- Check data quality: `python src/main.py info`
- Review processing logs: `tail -100 logs/surfcastai.log`
- Verify model selection in `config/config.yaml` (try `gpt-4o` for better quality)
- Check confidence scores in forecast output
- Run validation to quantify accuracy: `python src/main.py validate-all`
- Verify phantom swells are filtered (period >= 4.0s) in processing logs

### Phantom Swell Detection

**Problem:** Forecasts include unrealistic short-period swells

**Solution:**
The latest version automatically filters phantom swells (period < 4.0 seconds):
- Check processing logs for `Filtering phantom swell` messages
- Adjust minimum period threshold in config if needed:
  ```yaml
  processing:
    min_swell_period: 4.0  # seconds
  ```
- Quality-flagged data is excluded before analysis

### PDF Generation Issues

**Problem:** PDF output missing or errors

**Solution:**
```bash
# Install weasyprint dependencies (macOS)
brew install cairo pango gdk-pixbuf libffi

# Or disable PDF output in config
# Edit config/config.yaml:
# forecast:
#   formats: markdown,html
```

### Archive Security Errors

**Problem:** `SecurityError` when extracting archives

**Solution:**
The system protects against malicious archives. If you see this error:
- **Zip bomb detected:** Archive has suspicious compression ratio (> 100:1)
- **Path traversal detected:** Archive contains files with unsafe paths
- **File too large:** Individual file exceeds 100MB or total exceeds 1GB
- These are security features - do not disable them
- Verify the archive source is trustworthy before proceeding

## Development

- Use `setup.sh` to initialize the development environment
- Follow the module-based architecture for new features
- Set `forecast.use_local_generator = true` to run the rule-based fallback without OpenAI calls
- Add unit tests for all new components
- Use `uvicorn src.web.app:app --reload` to preview forecasts in a browser
- Update `CLAUDE.md` with status updates

## Documentation

- **[README.md](/Users/zackjordan/code/surfCastAI/README.md)** - This file (overview, installation, usage)
- **[VALIDATION_GUIDE.md](/Users/zackjordan/code/surfCastAI/VALIDATION_GUIDE.md)** - Complete validation system guide
- **[CONFIGURATION.md](/Users/zackjordan/code/surfCastAI/CONFIGURATION.md)** - All configuration options explained
- **[DEPLOYMENT.md](/Users/zackjordan/code/surfCastAI/DEPLOYMENT.md)** - Production deployment guide
- **[API.md](/Users/zackjordan/code/surfCastAI/API.md)** - API documentation for all modules
- **[CLAUDE.md](/Users/zackjordan/code/surfCastAI/CLAUDE.md)** - Project status and implementation notes

## Security Best Practices

### API Keys and Credentials
- ✅ **DO:** Store API keys in `.env` file (already in .gitignore)
- ✅ **DO:** Use `config.example.yaml` as a template
- ✅ **DO:** Keep `config.yaml` out of version control
- ✅ **DO:** Run `validate-config` before deploying to production
- ❌ **DON'T:** Commit `.env` or `config.yaml` with secrets
- ❌ **DON'T:** Share API keys in documentation or issues
- ❌ **DON'T:** Use the example template values in production
- ❌ **DON'T:** Set `api_key` in config.yaml (use environment variables only)

### Data Sources and URLs
- ✅ **DO:** Use only public internet URLs for data sources
- ✅ **DO:** Validate all configuration with `validate-config`
- ❌ **DON'T:** Use private IP addresses or internal network URLs
- ❌ **DON'T:** Disable SSRF protection (it's automatic and enforced)

### Archive Handling
- ✅ **DO:** Trust only official NOAA/NWS data sources
- ✅ **DO:** Let the system validate archives automatically
- ❌ **DON'T:** Extract archives manually without security checks
- ❌ **DON'T:** Disable archive security validation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

SurfCastAI was inspired by the legendary Hawaiian surf forecasting work of Pat Caldwell and aims to honor his analytical approach and detailed, actionable forecasts.
