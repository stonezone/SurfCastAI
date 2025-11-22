"""Tests for UpperAirAgent metadata enrichment."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import re

from src.agents.upper_air_agent import UpperAirAgent


def test_upper_air_agent_collect(tmp_path):
    config = MagicMock()
    config.get.return_value = {
        'sources': [
            {
                'id': 'wpc_250mb',
                'url': 'https://www.wpc.ncep.noaa.gov/noaa/noaa250_curr.gif',
                'level': '250',
                'type': 'jet_stream',
                'description': '250 mb jet'
            }
        ]
    }

    agent = UpperAirAgent(config)
    agent.ensure_http_client = AsyncMock()

    fake_image = tmp_path / 'wpc_250mb_250_noaa250_curr.gif'
    fake_image.write_bytes(b'GIF89a')

    agent.download_file = AsyncMock(
        return_value={
            'status': 'success',
            'file_path': str(fake_image),
            'name': fake_image.name,
            'type': 'image/gif'
        }
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry['analysis_level'] == '250'
    assert entry['product_type'] == 'jet_stream'
    assert entry['source_id'] == 'wpc_250mb'


def test_upper_air_agent_spc_date_template(tmp_path):
    """Test SPC endpoint with date template expansion."""
    config = MagicMock()
    config.get.return_value = {
        'sources': [
            {
                'id': 'spc_250mb',
                'url': 'https://www.spc.noaa.gov/obswx/maps/250_{date}_00.gif',
                'level': '250',
                'type': 'jet_stream',
                'date_format': '%y%m%d',
                'description': 'SPC 250 mb wind analysis (00Z only)'
            }
        ]
    }

    agent = UpperAirAgent(config)
    agent.ensure_http_client = AsyncMock()

    fake_image = tmp_path / 'spc_250mb_250_250_{date}_00.gif'
    fake_image.write_bytes(b'GIF89a')

    # Track the expanded URL used in download_file
    called_url = None

    async def mock_download(url, **kwargs):
        nonlocal called_url
        called_url = url
        return {
            'status': 'success',
            'file_path': str(fake_image),
            'name': fake_image.name,
            'type': 'image/gif'
        }

    agent.download_file = AsyncMock(side_effect=mock_download)

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry['analysis_level'] == '250'
    assert entry['product_type'] == 'jet_stream'
    assert entry['source_id'] == 'spc_250mb'
    assert entry['data_source'] == 'SPC'

    # Verify the URL was expanded with a date in YYMMDD format
    assert called_url is not None
    assert re.match(r'https://www\.spc\.noaa\.gov/obswx/maps/250_\d{6}_00\.gif', called_url), \
        f"URL did not match expected pattern: {called_url}"


def test_compute_most_recent_00z():
    """Test 00Z synoptic time computation logic."""
    # Test at 03:00 UTC - should use today's 00Z
    mock_time = datetime(2025, 10, 16, 3, 0, 0, tzinfo=timezone.utc)
    with patch('src.agents.upper_air_agent.datetime') as mock_dt:
        mock_dt.now.return_value = mock_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = UpperAirAgent._compute_most_recent_00z()
        assert result.date() == mock_time.date()
        assert result.hour == 0

    # Test at 01:00 UTC - should use yesterday's 00Z
    mock_time = datetime(2025, 10, 16, 1, 0, 0, tzinfo=timezone.utc)
    with patch('src.agents.upper_air_agent.datetime') as mock_dt:
        mock_dt.now.return_value = mock_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        result = UpperAirAgent._compute_most_recent_00z()
        assert result.date() == datetime(2025, 10, 15).date()
        assert result.hour == 0


def test_expand_date_template_with_format():
    """Test URL template expansion with custom date format."""
    config = MagicMock()
    agent = UpperAirAgent(config)

    # Mock logger to avoid AttributeError
    agent.logger = MagicMock()

    url = 'https://www.spc.noaa.gov/obswx/maps/250_{date}_00.gif'

    with patch.object(UpperAirAgent, '_compute_most_recent_00z') as mock_00z:
        mock_00z.return_value = datetime(2025, 10, 16, 0, 0, 0, tzinfo=timezone.utc)
        expanded = agent._expand_date_template(url, '%y%m%d')

    assert expanded == 'https://www.spc.noaa.gov/obswx/maps/250_251016_00.gif'


def test_expand_date_template_no_placeholder():
    """Test URL without date placeholder passes through unchanged."""
    config = MagicMock()
    agent = UpperAirAgent(config)
    agent.logger = MagicMock()

    url = 'https://www.wpc.ncep.noaa.gov/noaa/noaa250_curr.gif'
    expanded = agent._expand_date_template(url, '%y%m%d')

    assert expanded == url
