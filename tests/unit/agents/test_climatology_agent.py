"""Tests for ClimatologyAgent payload persistence."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.agents.climatology_agent import ClimatologyAgent


def test_climatology_agent_persists_text(tmp_path):
    config = MagicMock()
    config.get.return_value = {
        "sources": [
            {
                "id": "snn_nsstat10",
                "format": "text",
                "url": "https://www.surfnewsnetwork.com/nsstat10.txt",
                "description": "SNN October stats",
            }
        ]
    }

    agent = ClimatologyAgent(config)
    agent.ensure_http_client = AsyncMock()

    payload = b"DATE SURF\n10/15 6\n10/16 4\n"
    download_result = SimpleNamespace(success=True, content=payload, status_code=200, error=None)
    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=download_result))

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["format"] == "text"
    assert entry["line_count"] == 4
    assert entry["source_id"] == "snn_nsstat10"
