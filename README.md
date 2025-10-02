# SurfCastAI

An AI-powered Oahu surf forecasting system that automatically collects data from various marine and weather sources, analyzes patterns, and generates comprehensive surf forecasts.

## Project Structure

```
surfCastAI/
├── config/            # Configuration files
├── data/              # Downloaded and processed data
├── output/            # Generated forecasts
├── src/
│   ├── agents/        # Data collection agents for different sources
│   ├── core/          # Core components (HTTP client, rate limiter, etc.)
│   ├── forecast_engine/  # Forecast generation and refinement
│   └── utils/         # Utility functions and helpers
├── tests/             # Test suite
└── benchmark_forecast_engine.py  # Performance benchmarking
```

## Features

- Automated data collection from multiple marine and weather sources
- Per-domain rate limiting to respect API constraints
- Comprehensive error handling and retry logic
- Advanced AI-based forecast generation in Pat Caldwell style
- Quality assessment and iterative refinement
- Multi-format output (markdown, HTML, PDF), including responsive mobile HTML
- Visualization assets (swell mix, shore focus) and historical comparisons
- Lightweight FastAPI viewer for browsing generated forecasts locally
- Detailed analysis for both North Shore and South Shore conditions
- Forecast validation with quality metrics

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

## Installation

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

# Activate the virtual environment
source venv/bin/activate

# Edit the configuration file with your API keys
nano config/config.yaml
```

## Secure Configuration

### Setting Up API Keys

**IMPORTANT:** Never commit API keys to version control. SurfCastAI uses environment variables for sensitive credentials.

1. **Copy the configuration template:**
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. **Create a `.env` file in the project root:**
   ```bash
   echo "OPENAI_API_KEY=your-actual-api-key-here" > .env
   ```

3. **Remove the API key from config.yaml:**
   Edit `config/config.yaml` and delete or comment out the `api_key` line under `openai:` section.

### Configuration Priority

The system loads configuration in this order of priority:
1. **Environment variables** (`.env` file) - Highest priority
2. **Config file** (`config/config.yaml`) - Falls back if env var not found
3. **Default values** - Used if neither is available

### Security Best Practices

- ✅ **DO:** Store API keys in `.env` file (already in .gitignore)
- ✅ **DO:** Use `config.example.yaml` as a template
- ✅ **DO:** Keep `config.yaml` out of version control
- ❌ **DON'T:** Commit `.env` or `config.yaml` with secrets
- ❌ **DON'T:** Share API keys in documentation or issues
- ❌ **DON'T:** Use the example template values in production

### First-Time Setup Checklist

- [ ] Copy `config.example.yaml` to `config.yaml`
- [ ] Create `.env` with your OpenAI API key
- [ ] Remove API key from `config.yaml`
- [ ] Verify `.env` and `config.yaml` are in `.gitignore`
- [ ] Test the configuration: `python src/main.py --help`

## Usage

### Entry Points

SurfCastAI provides two ways to interact with the system:

**1. Command-Line Interface (Recommended)**
```bash
python src/main.py [command] [options]
```
Use this for:
- Automated/scripted workflows
- CI/CD pipelines
- Production deployments
- Direct API-style control

**2. Interactive Cyberpunk UI**
```bash
python surfcast.py
```
Use this for:
- Interactive exploration
- Development and testing
- Visual feedback and progress
- Learning the system capabilities

Both entry points access the same underlying forecast engine and data pipeline.

### Commands

```bash
# Run the full pipeline
python src/main.py run --mode full

# Only collect data
python src/main.py run --mode collect

# Only generate forecast
python src/main.py run --mode forecast

# List all available data bundles
python src/main.py list

# Show bundle information
python src/main.py info --bundle BUNDLE_ID

# List files in a bundle
python src/main.py files --bundle BUNDLE_ID
```

## Web Viewer

Serve the latest forecasts with the bundled FastAPI app:

```bash
uvicorn src.web.app:app --reload
```

Set `SURFCAST_OUTPUT_DIR` if your forecasts live outside `./output`. Generated charts live under `<forecast>/assets/` and are referenced automatically by the HTML viewer.

## Sample Forecast (GPT-5 Nano)

Run the helper script to produce a demo forecast via OpenAI (set `OPENAI_API_KEY` or keep it in `.env`):

```bash
python scripts/generate_sample_forecast.py --force-remote --model gpt-5-nano
```

Outputs land under `output/sample/` by default. Add `--output` to change the path.

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

## Development

- Use `setup.sh` to initialize the development environment
- Follow the module-based architecture for new features
- Set `forecast.use_local_generator = true` to run the rule-based fallback without OpenAI calls
- Add unit tests for all new components
- Use `uvicorn src.web.app:app --reload` to preview forecasts in a browser
- Update `CLAUDE.md` with status updates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.