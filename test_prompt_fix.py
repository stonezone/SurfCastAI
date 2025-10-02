#!/usr/bin/env python3
"""
Quick test to verify prompt construction after fixes.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.forecast_engine.prompt_templates import PromptTemplates
from src.processing.models.swell_event import SwellForecast, dict_to_swell_forecast

# Load the fused forecast data
forecast_path = Path('data/24e7eaad-97eb-4d45-93b8-f02d3127064e/processed/fused_forecast.json')
with open(forecast_path) as f:
    data = json.load(f)

# Convert to SwellForecast object
swell_forecast = dict_to_swell_forecast(data)

# Create templates
templates = PromptTemplates()

# Prepare forecast data (simplified version)
from datetime import datetime, timedelta

start_date = datetime.now().strftime('%Y-%m-%d')
end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')

swell_events = []
for event in swell_forecast.swell_events:
    swell_events.append({
        'event_id': event.event_id,
        'start_time': event.start_time,
        'peak_time': event.peak_time,
        'end_time': event.end_time,
        'primary_direction': event.primary_direction,
        'primary_direction_cardinal': event.primary_direction_cardinal,
        'significance': event.significance,
        'hawaii_scale': event.hawaii_scale,
        'source': event.source,
        'dominant_period': event.dominant_period
    })

forecast_data = {
    'forecast_id': swell_forecast.forecast_id,
    'start_date': start_date,
    'end_date': end_date,
    'region': 'Oahu',
    'shores': ['North Shore', 'South Shore'],
    'swell_events': swell_events,
    'shore_data': {},
    'confidence': {},
    'metadata': {},
    'seasonal_context': {}
}

# Get the Caldwell prompt
prompt = templates.get_caldwell_prompt(forecast_data)

print("=" * 80)
print("CALDWELL PROMPT (after fixes):")
print("=" * 80)
print(prompt)
print("\n" + "=" * 80)
print("\nChecking for problematic phrases:")
print("=" * 80)

# Check for the old problematic phrasing
if "Please generate" in prompt:
    print("❌ FOUND: 'Please generate' - this is the old soft phrasing")
else:
    print("✅ GOOD: No 'Please generate' found")

if "Write the complete forecast now" in prompt:
    print("✅ GOOD: Found directive 'Write the complete forecast now'")
else:
    print("❌ MISSING: No clear directive found")

# Check system prompt
template = templates.get_template('caldwell')
system_prompt = template.get('system_prompt', '')

print("\n" + "=" * 80)
print("SYSTEM PROMPT (first 500 chars):")
print("=" * 80)
print(system_prompt[:500])
print("\n" + "=" * 80)

if "CRITICAL: You must write the actual forecast text now" in system_prompt:
    print("✅ GOOD: Found critical directive in system prompt")
else:
    print("❌ MISSING: No critical directive in system prompt")
