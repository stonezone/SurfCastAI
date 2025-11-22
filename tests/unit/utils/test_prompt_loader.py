"""Tests for JSON-based prompt loading and integration."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.core import Config
from src.forecast_engine import ForecastEngine


class TestPromptLoaderIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.prompt_dir = self.root / 'config' / 'prompts' / 'v1'
        self.prompt_dir.mkdir(parents=True, exist_ok=True)

        self.config = Config()
        self.config._config = {
            'forecast': {
                'templates_dir': str(self.root / 'config' / 'prompts'),
                'use_local_generator': True,
                'refinement_cycles': 0,
                'formats': 'markdown',
            },
            'openai': {
                'model': 'gpt-5-nano',
            },
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_prompt(self, name: str, *, valid: bool = True) -> Path:
        prompt_path = self.prompt_dir / f'{name}.json'
        payload = {
            'version': '1.0',
            'name': name,
            'description': f'{name} prompt',
            'system_prompt': 'System content',
            'user_prompt_template': 'User content',
            'variables': ['forecast_data'],
            'model_settings': {
                'temperature': 0.7,
                'max_tokens': 1024,
            },
        }
        if not valid:
            payload.pop('system_prompt', None)

        with open(prompt_path, 'w') as handle:
            json.dump(payload, handle)
        return prompt_path

    def test_loader_reads_prompts_from_external_files(self) -> None:
        self._write_prompt('caldwell_main')
        engine = ForecastEngine(self.config)
        self.assertTrue(engine.prompt_loader.has_prompt('caldwell_main'))

    def test_engine_falls_back_when_prompt_missing(self) -> None:
        self._write_prompt('north_shore', valid=False)
        engine = ForecastEngine(self.config)
        self.assertTrue(engine.prompt_loader.is_fallback_enabled())


if __name__ == '__main__':
    unittest.main()

