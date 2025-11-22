"""Integration smoke test for forecast generation with local generator."""

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.core import Config
from src.main import generate_forecast
from src.validation.database import ValidationDatabase


def _build_config(root: Path) -> Config:
    config = Config()
    config._config = {
        'general': {
            'data_directory': str(root / 'data'),
            'output_directory': str(root / 'output'),
            'log_file': str(root / 'logs' / 'surfcastai.log'),
        },
        'forecast': {
            'use_local_generator': True,
            'templates_dir': str(root / 'config' / 'prompts'),
            'formats': 'markdown,html',
            'refinement_cycles': 0,
        },
        'openai': {
            'model': 'gpt-5-nano',
        },
        'validation': {
            'database_path': str(root / 'data' / 'validation.db'),
        },
    }
    return config


def _seed_bundle(root: Path) -> tuple[str, Path]:
    data_root = root / 'data'
    bundle_id = 'test-bundle'
    bundle_dir = data_root / bundle_id
    processed_dir = bundle_dir / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)

    fused_payload = {
        'forecast_id': 'forecast_test_bundle',
        'generated_time': '2025-10-08T12:00:00Z',
        'metadata': {
            'bundle_id': bundle_id,
        },
        'swell_events': [],
        'locations': [
            {
                'name': 'Pipeline',
                'shore': 'North Shore',
                'swell_events': [
                    {
                        'event_id': 'ns-1',
                        'start_time': '2025-10-08T06:00:00Z',
                        'peak_time': '2025-10-08T18:00:00Z',
                        'end_time': '2025-10-09T06:00:00Z',
                        'primary_direction': 320.0,
                        'hawaii_scale': 6.0,
                        'dominant_period': 14.0,
                        'primary_direction_cardinal': 'NNW',
                        'metadata': {
                            'confidence': 0.75,
                            'category': 'solid',
                        },
                        'primary_components': [
                            {
                                'height': 6.0,
                                'period': 14.0,
                                'direction': 320.0,
                                'confidence': 0.75,
                                'source': 'model',
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with open(processed_dir / 'fused_forecast.json', 'w') as f:
        json.dump(fused_payload, f)

    return bundle_id, bundle_dir


class TestMinimalPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_generate_forecast_offline(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'logs').mkdir(parents=True, exist_ok=True)
            (root / 'config' / 'prompts').mkdir(parents=True, exist_ok=True)

            config = _build_config(root)
            bundle_id, _ = _seed_bundle(root)

            logger = logging.getLogger('test.minimal_pipeline')
            logger.setLevel(logging.INFO)

            result = await generate_forecast(config, logger, bundle_id=bundle_id)

            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['bundle_id'], bundle_id)

            output_dir = Path(config.output_directory)
            forecast_dir = output_dir / result['forecast_id']
            self.assertTrue((forecast_dir / 'forecast_data.json').exists())
            markdown_path = forecast_dir / f"{result['forecast_id']}.md"
            self.assertTrue(markdown_path.exists())

            database = ValidationDatabase(config.get('validation', 'database_path'))
            stored_forecast = database.get_forecast(result['forecast_id'])
            self.assertIsNotNone(stored_forecast)
            stored_predictions = database.get_predictions_for_forecast(result['forecast_id'])
            self.assertGreater(len(stored_predictions), 0)


if __name__ == '__main__':
    unittest.main()
