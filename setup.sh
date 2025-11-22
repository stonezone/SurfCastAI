#!/bin/bash
# Setup script for SurfCastAI

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./setup.sh [--force]

Options:
  --force   Recreate the virtual environment and overwrite existing configs.
EOF
}

FORCE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

PYTHON_BIN=${PYTHON:-python3}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Unable to find a usable python interpreter. Set PYTHON to an absolute python path (e.g. /opt/homebrew/Caskroom/miniforge/base/bin/python3)." >&2
    exit 1
fi

PYTHON_CHECK=$("$PYTHON_BIN" - <<'PY'
import sys
major, minor = sys.version_info[:2]
if major != 3 or minor < 9:
    print(f"Python 3.9 or newer (but <4.0) required. Detected {sys.version.split()[0]}")
    sys.exit(1)
if major >= 4:
    print(f"Python <4.0 required. Detected {sys.version.split()[0]}")
    sys.exit(1)
PY
)
if [[ $? -ne 0 ]]; then
    echo "$PYTHON_CHECK"
    exit 1
fi

echo "Python version check passed."

if [[ -d venv && $FORCE == true ]]; then
    echo "--force supplied: removing existing venv/"
    rm -rf venv
fi

SETUP_ENV=false
if [[ ! -d venv ]]; then
    echo "Creating virtual environment..."
    "$PYTHON_BIN" -m venv venv
    SETUP_ENV=true
else
    echo "venv/ already exists. Skipping creation (use --force to recreate)."
fi

if [[ $SETUP_ENV == true ]]; then
    echo "Activating virtual environment..."
    # shellcheck disable=SC1091
    source venv/bin/activate
    VENV_PYTHON="$VIRTUAL_ENV/bin/python"

    echo "Bootstrapping pip..."
    if ! "$VENV_PYTHON" -m ensurepip --upgrade >/dev/null 2>&1; then
        echo "ensurepip not available; extracting bundled pip wheel manually."
        "$VENV_PYTHON" - <<'PY'
import sys
import zipfile
import pathlib
import importlib.util

spec = importlib.util.find_spec('ensurepip')
if spec is None or not spec.submodule_search_locations:
    raise RuntimeError('ensurepip module missing; cannot bootstrap pip')

bundled_path = pathlib.Path(spec.submodule_search_locations[0]) / '_bundled'
pip_wheels = sorted(p for p in bundled_path.glob('pip-*.whl'))
if not pip_wheels:
    raise RuntimeError(f'No pip wheel found in {bundled_path}')

wheel = pip_wheels[-1]
site_packages = pathlib.Path(sys.prefix) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
site_packages.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(wheel) as zf:
    zf.extractall(site_packages)
PY
    fi

    echo "Installing project dependencies..."
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r requirements.txt
else
    echo "Skipping dependency installation (venv already present)."
fi

echo "Creating directories..."
mkdir -p data
mkdir -p output
mkdir -p output/benchmarks
mkdir -p logs
mkdir -p tests/unit/forecast_engine

copy_config() {
    local source=$1
    local target=$2
    local label=$3

    if [[ -f "$target" && $FORCE != true ]]; then
        echo "$label already exists. Skipping (use --force to overwrite)."
        return
    fi

    cp "$source" "$target"
    echo "$label provisioned from template."
}

echo "Setting up configuration..."
copy_config config/config.example.yaml config/config.yaml "config/config.yaml"

echo "Setting up test configuration..."
if [[ ! -f config/test_config.yaml || $FORCE == true ]]; then
    cat > config/test_config.yaml <<'EOL'
# Test configuration for SurfCastAI

general:
  log_level: INFO
  log_file: logs/surfcastai_test.log
  output_directory: output/test

openai:
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4000

forecast:
  templates_dir: config/prompts/v1
  refinement_cycles: 1  # Set to 1 for faster tests
  quality_threshold: 0.7
  formats: markdown,html  # Exclude PDF for faster tests
EOL
    echo "config/test_config.yaml refreshed."
else
    echo "config/test_config.yaml already exists. Skipping (use --force to overwrite)."
fi

echo "Setting up test scaffolding..."
if [[ ! -f tests/unit/forecast_engine/__init__.py ]]; then
    mkdir -p tests/unit/forecast_engine
    touch tests/unit/forecast_engine/__init__.py
fi

if [[ ! -f tests/unit/forecast_engine/test_formatter.py ]]; then
    cat > tests/unit/forecast_engine/test_formatter.py <<'EOL'
"""
Unit tests for the ForecastFormatter class.
"""

import unittest
from pathlib import Path
import tempfile
import shutil
import os

from src.core import Config
from src.forecast_engine import ForecastFormatter


class TestForecastFormatter(unittest.TestCase):
    """Test cases for ForecastFormatter."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        # Create config
        self.config = Config()
        self.config._config.add_section('general')
        self.config._config.set('general', 'output_directory', self.test_dir)

        self.config._config.add_section('forecast')
        self.config._config.set('forecast', 'formats', 'markdown,html')

        # Create formatter
        self.formatter = ForecastFormatter(self.config)

        # Test forecast data
        self.forecast_data = {
            'forecast_id': 'test_forecast',
            'generated_time': '2023-01-01T00:00:00Z',
            'main_forecast': 'This is a test forecast for Hawaii.',
            'north_shore': 'North Shore forecast: Waves are 5-7 feet.',
            'south_shore': 'South Shore forecast: Waves are 1-3 feet.',
            'daily': 'Daily forecast: Good surfing conditions.',
            'metadata': {
                'confidence': {
                    'overall_score': 0.8,
                    'factors': {
                        'data_freshness': 0.9,
                        'source_diversity': 0.7
                    }
                }
            }
        }

    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)

    def test_format_forecast(self):
        """Test format_forecast method."""
        # Format forecast
        result = self.formatter.format_forecast(self.forecast_data)

        # Check if output files exist
        self.assertIn('markdown', result)
        self.assertIn('html', result)
        self.assertIn('json', result)

        # Check if files were created
        markdown_path = Path(result['markdown'])
        html_path = Path(result['html'])
        json_path = Path(result['json'])

        self.assertTrue(markdown_path.exists())
        self.assertTrue(html_path.exists())
        self.assertTrue(json_path.exists())

        # Check file content
        with open(markdown_path, 'r') as f:
            markdown_content = f.read()
            self.assertIn('Hawaii Surf Forecast', markdown_content)
            self.assertIn('North Shore', markdown_content)
            self.assertIn('South Shore', markdown_content)

        with open(html_path, 'r') as f:
            html_content = f.read()
            self.assertIn('<html', html_content)
            self.assertIn('Hawaii Surf Forecast', html_content)
            self.assertIn('North Shore', html_content)
            self.assertIn('South Shore', html_content)

        with open(json_path, 'r') as f:
            import json
            json_content = json.load(f)
            self.assertEqual(json_content['forecast_id'], 'test_forecast')
            self.assertIn('main_forecast', json_content)
            self.assertIn('north_shore', json_content)
            self.assertIn('south_shore', json_content)
EOL
    echo "Basic forecast formatter test scaffold created."
fi

cat <<'EOF'

========================================
Setup complete!
Next steps:
  1. source venv/bin/activate
  2. export OPENAI_API_KEY="sk-..."  (or edit config/config.yaml)
  3. python src/main.py run --mode full

Happy forecasting!
========================================
EOF
