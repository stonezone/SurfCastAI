"""Tests for forecast persistence into the validation database."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.core import Config
from src.main import generate_forecast
from src.validation.database import ValidationDatabase


def _build_config(temp_root: Path, db_path: Path) -> Config:
    """Create an in-memory Config tailored for the persistence test."""
    config = Config()
    config._config = {
        'general': {
            'data_directory': str(temp_root / 'data'),
            'output_directory': str(temp_root / 'output'),
            'log_file': str(temp_root / 'logs' / 'surfcastai.log'),
            'timezone': 'Pacific/Honolulu',
        },
        'forecast': {
            'use_local_generator': True,
            'formats': 'markdown,html',  # avoid pdf dependency
            'templates_dir': 'config/prompts/v1',
            'refinement_cycles': 0,
            'quality_threshold': 0.7,
            'token_budget': 150000,
            'enable_budget_enforcement': False,
        },
        'openai': {
            'model': 'gpt-5-nano',
        },
        'validation': {
            'database_path': str(db_path),
        },
    }
    return config


def _write_fused_forecast(bundle_dir: Path) -> str:
    """Populate bundle directory with a minimal fused forecast JSON."""
    processed_dir = bundle_dir / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)

    forecast_id = 'test_forecast_persistence'
    now = datetime.utcnow()
    later = now + timedelta(hours=12)
    end = now + timedelta(days=1)

    fused_payload = {
        'forecast_id': forecast_id,
        'generated_time': now.replace(microsecond=0).isoformat() + 'Z',
        'metadata': {
            'bundle_id': bundle_dir.name,
            'source': 'unit-test',
        },
        'swell_events': [
            {
                'event_id': 'global-swell-1',
                'start_time': now.isoformat() + 'Z',
                'peak_time': later.isoformat() + 'Z',
                'end_time': end.isoformat() + 'Z',
                'primary_direction': 320.0,
                'significance': 0.8,
                'hawaii_scale': 4.5,
                'source': 'fusion',
                'metadata': {
                    'confidence': 0.72,
                    'category': 'medium',
                },
                'primary_components': [
                    {
                        'height': 4.5,
                        'period': 14.0,
                        'direction': 320.0,
                        'confidence': 0.72,
                        'source': 'model',
                    }
                ],
                'secondary_components': [],
            }
        ],
        'locations': [
            {
                'name': 'Pipeline',
                'shore': 'North Shore',
                'latitude': 21.664,
                'longitude': -158.05,
                'facing_direction': 320.0,
                'metadata': {},
                'swell_events': [
                    {
                        'event_id': 'north-shore-1',
                        'start_time': now.isoformat() + 'Z',
                        'peak_time': later.isoformat() + 'Z',
                        'end_time': end.isoformat() + 'Z',
                        'primary_direction': 320.0,
                        'significance': 0.85,
                        'hawaii_scale': 6.0,
                        'source': 'fusion',
                        'metadata': {
                            'confidence': 0.78,
                            'category': 'warning',
                        },
                        'primary_components': [
                            {
                                'height': 6.0,
                                'period': 15.0,
                                'direction': 320.0,
                                'confidence': 0.78,
                                'source': 'model',
                            }
                        ],
                        'secondary_components': [],
                    }
                ],
            },
            {
                'name': 'Ala Moana',
                'shore': 'South Shore',
                'latitude': 21.27,
                'longitude': -157.85,
                'facing_direction': 180.0,
                'metadata': {},
                'swell_events': [
                    {
                        'event_id': 'south-shore-1',
                        'start_time': now.isoformat() + 'Z',
                        'peak_time': later.isoformat() + 'Z',
                        'end_time': end.isoformat() + 'Z',
                        'primary_direction': 190.0,
                        'significance': 0.5,
                        'hawaii_scale': 2.5,
                        'source': 'fusion',
                        'metadata': {
                            'confidence': 0.65,
                            'category': 'small',
                        },
                        'primary_components': [
                            {
                                'height': 2.5,
                                'period': 12.0,
                                'direction': 190.0,
                                'confidence': 0.65,
                                'source': 'model',
                            }
                        ],
                        'secondary_components': [],
                    }
                ],
            },
        ],
    }

    fused_path = processed_dir / 'fused_forecast.json'
    with open(fused_path, 'w') as handle:
        json.dump(fused_payload, handle)

    return forecast_id


class TestForecastPersistence(unittest.IsolatedAsyncioTestCase):
    async def test_generate_forecast_persists_to_validation_db(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / 'data'
            output_root = root / 'output'
            logs_root = root / 'logs'
            for directory in (data_root, output_root, logs_root):
                directory.mkdir(parents=True, exist_ok=True)

            db_path = root / 'validation.db'
            config = _build_config(root, db_path)

            bundle_id = 'test-bundle'
            bundle_dir = data_root / bundle_id
            forecast_id = _write_fused_forecast(bundle_dir)

            logger = logging.getLogger('test.forecast_persistence')
            logger.setLevel(logging.INFO)

            result = await generate_forecast(config, logger, bundle_id=bundle_id)

            self.assertEqual(result.get('status'), 'success')
            self.assertEqual(result.get('forecast_id'), forecast_id)

            database = ValidationDatabase(str(db_path))
            stored = database.get_forecast(forecast_id)
            self.assertIsNotNone(stored, 'Forecast row not persisted to validation DB')

            predictions = database.get_predictions_for_forecast(forecast_id)
            self.assertGreater(len(predictions), 0, 'Predictions were not stored for the forecast')


if __name__ == '__main__':
    unittest.main()
