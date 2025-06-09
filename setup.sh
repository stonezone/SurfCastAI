#!/bin/bash
# Setup script for SurfCastAI

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create directories if they don't exist
echo "Creating directories..."
mkdir -p data
mkdir -p output
mkdir -p output/benchmarks
mkdir -p logs
mkdir -p tests/unit/forecast_engine

# Copy example config if not exists
echo "Setting up configuration..."
if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo "Copied example configuration to config/config.yaml"
    echo "Please edit config/config.yaml to add your API keys and configure data sources"
fi

# Set up test environment
echo "Setting up test environment..."
# Create test config if not exists
if [ ! -f config/test_config.yaml ]; then
    echo "Creating test configuration..."
    cat > config/test_config.yaml << EOL
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
  templates_dir: src/forecast_engine/templates
  refinement_cycles: 1  # Set to 1 for faster tests
  quality_threshold: 0.7
  formats: markdown,html  # Exclude PDF for faster tests
EOL
    echo "Test configuration created at config/test_config.yaml"
fi

echo "Setting up test directory..."
# Create basic test if not exists
if [ ! -f tests/unit/forecast_engine/__init__.py ]; then
    mkdir -p tests/unit/forecast_engine
    touch tests/unit/forecast_engine/__init__.py
    cat > tests/unit/forecast_engine/test_formatter.py << EOL
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
    echo "Basic unit test created at tests/unit/forecast_engine/test_formatter.py"
fi

echo "Setup complete! To activate the environment, run:"
echo "source venv/bin/activate"
echo ""
echo "To run SurfCastAI:"
echo "python src/main.py"
echo ""
echo "To run tests:"
echo "python -m unittest discover -s tests"
echo ""
echo "To run forecast engine test:"
echo "python test_forecast_engine.py"
echo ""
echo "To run benchmarks:"
echo "python benchmark_forecast_engine.py"