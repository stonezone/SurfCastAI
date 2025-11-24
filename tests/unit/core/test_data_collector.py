"""Tests for DataCollector metrics resets."""

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.config import Config
from src.core.data_collector import DataCollector


class _DummyAgent:
    """Simple agent stub that returns preset metadata."""

    def __init__(self) -> None:
        self.metadata = []

    async def collect(self, agent_dir: Path):
        agent_dir.mkdir(exist_ok=True)
        # Return shallow copies so chained runs cannot mutate past data
        return [dict(item) for item in self.metadata]


class TestDataCollectorStatsReset(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = TemporaryDirectory()

        config = Config()
        config._config = {
            "general": {
                "data_directory": self.temp_dir.name,
            },
            "data_sources": {
                "dummy": {"enabled": True},
            },
        }

        self.collector = DataCollector(config)
        self.agent = _DummyAgent()
        self.collector.agents = {"dummy": self.agent}

    async def asyncTearDown(self) -> None:
        await asyncio.sleep(0)
        self.temp_dir.cleanup()

    async def test_stats_reset_between_runs(self) -> None:
        """Test that stats are correctly calculated for each run without carryover."""
        first_metadata = [
            {"status": "success", "size_bytes": 512},
            {"status": "success", "size_bytes": 256},
            {"status": "error", "size_bytes": 0},
        ]
        self.agent.metadata = first_metadata

        first_result = await self.collector.collect_data()

        # Verify first run stats
        self.assertEqual(first_result["stats"]["total_files"], 3)
        self.assertEqual(first_result["stats"]["successful_files"], 2)
        self.assertEqual(first_result["stats"]["failed_files"], 1)

        second_metadata = [
            {"status": "success", "size_bytes": 1024},
            {"status": "success", "size_bytes": 2048},
        ]
        self.agent.metadata = second_metadata

        second_result = await self.collector.collect_data()

        # Verify second run stats are independent (not cumulative)
        expected_total = len(second_metadata)
        expected_success = sum(1 for item in second_metadata if item["status"] == "success")
        expected_failed = expected_total - expected_success
        expected_size = sum(item["size_bytes"] for item in second_metadata)

        # Check returned stats from second run
        self.assertEqual(second_result["stats"]["total_files"], expected_total)
        self.assertEqual(second_result["stats"]["successful_files"], expected_success)
        self.assertEqual(second_result["stats"]["failed_files"], expected_failed)
        self.assertEqual(second_result["stats"]["total_size_bytes"], expected_size)

        # Check agent-specific stats
        self.assertEqual(second_result["stats"]["agents"]["dummy"]["total"], expected_total)
        self.assertEqual(second_result["stats"]["agents"]["dummy"]["successful"], expected_success)
        self.assertEqual(second_result["stats"]["agents"]["dummy"]["failed"], expected_failed)


if __name__ == "__main__":
    unittest.main()
