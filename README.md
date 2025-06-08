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
- Multi-format output (markdown, HTML, PDF)
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

## Usage

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
- Add unit tests for all new components
- Update `CLAUDE.md` with status updates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.