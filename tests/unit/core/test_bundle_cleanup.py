"""Tests for bundle retention and cleanup behavior."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.core import BundleManager, Config


def _create_bundle(root: Path, bundle_id: str, *, complete: bool, age_days: int) -> Path:
    """Create a bundle directory with optional processed data and age offset."""
    bundle_dir = root / bundle_id
    processed_dir = bundle_dir / 'processed'
    bundle_dir.mkdir(parents=True, exist_ok=True)

    metadata = bundle_dir / 'bundle_metadata.json'
    metadata.write_text('{"bundle_id": "%s"}' % bundle_id)

    if complete:
        processed_dir.mkdir(parents=True, exist_ok=True)
        fused = processed_dir / 'fused_forecast.json'
        fused.write_text('{}')

    # adjust modification time into the past by age_days
    past = datetime.now() - timedelta(days=age_days)
    ts = past.timestamp()
    for path in [bundle_dir, metadata] + list(processed_dir.rglob('*')):
        if path.exists():
            os.utime(path, (ts, ts))

    return bundle_dir


class TestBundleRetention(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.data_root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_get_bundle_age_returns_timedelta(self) -> None:
        manager = BundleManager(self.data_root)
        bundle = _create_bundle(self.data_root, 'age-check', complete=True, age_days=2)

        age = manager.get_bundle_age(bundle.name)
        self.assertGreaterEqual(age.total_seconds(), 0)

    def test_cleanup_uses_retention_setting_and_skips_incomplete(self) -> None:
        config = Config()
        config._config = {
            'general': {
                'data_directory': str(self.data_root),
                'data_retention_days': 1,
            }
        }

        manager = BundleManager(self.data_root)
        old_complete = _create_bundle(self.data_root, 'old-complete', complete=True, age_days=10)
        old_incomplete = _create_bundle(self.data_root, 'old-incomplete', complete=False, age_days=10)
        _create_bundle(self.data_root, 'recent-complete', complete=True, age_days=0)

        removed = manager.cleanup_old_bundles_using_config(config)

        removed_ids = {item['bundle_id'] for item in removed}
        self.assertIn(old_complete.name, removed_ids)
        self.assertNotIn(old_incomplete.name, removed_ids)


if __name__ == '__main__':
    unittest.main()

