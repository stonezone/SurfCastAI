"""Unit tests for CDIPAgent metadata enrichment and netCDF/fallback handling."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.cdip_agent import CDIPAgent


def test_cdip_agent_enriches_metadata(tmp_path):
    """Test legacy CDIP JSON format parsing."""
    config = MagicMock()
    config.get.return_value = {
        "sources": [
            {
                "id": "hanalei_225",
                "format": "cdip_json",
                "url": "https://example.com/225.json",
                "description": "CDIP Hanalei (225) processed spectra",
            }
        ]
    }

    agent = CDIPAgent(config)
    agent.ensure_http_client = AsyncMock()

    payload = {
        "station": {"id": 225, "name": "Hanalei", "latitude": 22.23, "longitude": -159.5},
        "spectra": {"frequencies": [0.05, 0.06, 0.07], "energy": [1.2, 0.9, 0.4]},
        "wave": {
            "Hs": 2.4,
            "Tp": 14.8,
            "Dp": 315,
            "time": "2025-10-15T12:00:00Z",
            "quality": {"flagged": False},
        },
        "meta": {"last_update": "2025-10-15T12:05:00Z"},
    }

    download_result = SimpleNamespace(
        success=True,
        content=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        status_code=200,
        error=None,
    )

    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=download_result))

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["station_id"] == "hanalei_225"
    assert entry["station_name"] == "Hanalei"
    assert entry["significant_height_m"] == pytest.approx(2.4)
    assert entry["peak_period_s"] == pytest.approx(14.8)
    assert entry["peak_direction_deg"] == pytest.approx(315)
    assert entry["spectral_bins"] == 3
    assert entry["spectral_frequency_spacing"] == pytest.approx(0.01)
    assert entry["quality_flags"] == {"flagged": False}
    assert entry["raw_last_updated"] == "2025-10-15T12:05:00Z"


def test_cdip_agent_netcdf_format(tmp_path):
    """Test CDIP THREDDS netCDF parsing."""
    pytest.importorskip("xarray")
    pytest.importorskip("netCDF4")

    config = MagicMock()
    config.get.return_value = {
        "sources": [
            {
                "id": "waimea_106",
                "format": "cdip_netcdf",
                "url": "https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/106p1_rt.nc",
                "description": "CDIP Waimea netCDF",
            }
        ]
    }

    agent = CDIPAgent(config)
    agent.ensure_http_client = AsyncMock()

    # Create mock netCDF content
    import tempfile

    import numpy as np
    import xarray as xr

    # Create a minimal netCDF dataset
    ds = xr.Dataset(
        {
            "waveHs": (["time"], np.array([2.1, 2.3, 2.5])),
            "waveTp": (["time"], np.array([12.5, 13.0, 14.2])),
            "waveDp": (["time"], np.array([310, 315, 320])),
            "waveTime": (
                ["time"],
                ["2025-10-15T10:00:00Z", "2025-10-15T11:00:00Z", "2025-10-15T12:00:00Z"],
            ),
            "waveFrequency": (["freq"], np.array([0.04, 0.05, 0.06, 0.07])),
            "waveEnergyDensity": (
                ["time", "freq"],
                np.array([[1.0, 1.2, 0.8, 0.4], [1.1, 1.3, 0.9, 0.5], [1.2, 1.4, 1.0, 0.6]]),
            ),
        },
        attrs={"station_name": "Waimea Bay", "latitude": 21.65, "longitude": -158.07},
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
        ds.to_netcdf(tmp.name)
        with open(tmp.name, "rb") as f:
            nc_content = f.read()

    download_result = SimpleNamespace(
        success=True,
        content=nc_content,
        content_type="application/x-netcdf",
        status_code=200,
        error=None,
    )

    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=download_result))

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["station_id"] == "waimea_106"
    assert entry["station_name"] == "Waimea Bay"
    assert entry["station_lat"] == pytest.approx(21.65)
    assert entry["station_lon"] == pytest.approx(-158.07)
    assert entry["significant_height_m"] == pytest.approx(2.5)
    assert entry["peak_period_s"] == pytest.approx(14.2)
    assert entry["peak_direction_deg"] == pytest.approx(320)
    assert entry["spectral_bins"] == 4
    assert entry["source_format"] == "cdip_netcdf"
    assert not entry.get("fallback_used", False)


def test_cdip_agent_ndbc_fallback(tmp_path):
    """Test NDBC text fallback when netCDF fails."""
    config = MagicMock()
    config.get.return_value = {
        "sources": [
            {
                "id": "hanalei_225",
                "format": "cdip_netcdf",
                "url": "https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/225p1_rt.nc",
                "ndbc_fallback": "https://www.ndbc.noaa.gov/data/realtime2/51207.txt",
                "description": "CDIP Hanalei with fallback",
            }
        ]
    }

    agent = CDIPAgent(config)
    agent.ensure_http_client = AsyncMock()

    # NDBC standard met format
    ndbc_content = """#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi   ft
2025 10 15 12 00  050  8.5 10.2   2.8  13.5  10.2 320 1015.2  24.5  25.1  22.0  9.9  MM
2025 10 15 11 50  052  8.3  9.8   2.7  13.2  10.0 318 1015.3  24.4  25.0  21.9  9.9  MM"""

    # First call (netCDF) fails
    failed_result = SimpleNamespace(
        success=False, content=None, content_type=None, status_code=404, error="not_found"
    )

    # Second call (NDBC text) succeeds
    success_result = SimpleNamespace(
        success=True,
        content=ndbc_content.encode("utf-8"),
        content_type="text/plain",
        status_code=200,
        error=None,
    )

    agent.http_client = SimpleNamespace(
        download=AsyncMock(side_effect=[failed_result, success_result])
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["station_id"] == "hanalei_225"
    assert entry["significant_height_m"] == pytest.approx(2.8)
    assert entry["peak_period_s"] == pytest.approx(13.5)
    assert entry["peak_direction_deg"] == pytest.approx(320)
    assert entry["source_format"] == "ndbc_text"
    assert entry["fallback_used"] is True
    assert "2025-10-15" in entry["observation_timestamp"]


def test_cdip_agent_both_sources_fail(tmp_path):
    """Test when both primary and fallback fail."""
    config = MagicMock()
    config.get.return_value = {
        "sources": [
            {
                "id": "test_999",
                "format": "cdip_netcdf",
                "url": "https://example.com/fail.nc",
                "ndbc_fallback": "https://example.com/also_fail.txt",
                "description": "Failing station",
            }
        ]
    }

    agent = CDIPAgent(config)
    agent.ensure_http_client = AsyncMock()

    failed_result = SimpleNamespace(
        success=False, content=None, content_type=None, status_code=500, error="server_error"
    )

    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=failed_result))

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert "error" in entry
    assert entry["fallback_used"] is True
