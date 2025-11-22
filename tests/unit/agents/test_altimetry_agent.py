"""Tests for the AltimetryAgent handling of ERDDAP PNG endpoints and legacy formats."""

from __future__ import annotations

import asyncio
import gzip
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.agents.altimetry_agent import AltimetryAgent


def test_altimetry_agent_downloads_erddap_png(tmp_path):
    """Test that the agent correctly downloads ERDDAP graph endpoint PNGs."""
    config = MagicMock()
    config.get_data_source_urls.return_value = {
        "altimetry": [
            "https://upwell.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day.graph?sla[(latest)][(15):(30)][(-165):(-150)]&amp;.draw=surface&amp;.vars=longitude|latitude|sla&amp;.size=800|600&amp;.png"
        ]
    }

    agent = AltimetryAgent(config)
    agent.ensure_http_client = AsyncMock()

    png_path = tmp_path / "ssh_hawaii_ERDDAP_Upwell.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-data")

    agent.download_file = AsyncMock(
        return_value={
            "status": "success",
            "file_path": str(png_path),
            "name": "ssh_hawaii_ERDDAP_Upwell.png",
        }
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["type"] == "png_image"
    assert entry["source"] == "ERDDAP_Upwell"
    assert entry["data_product"] == "nesdisSSH1day"
    assert entry["region"] == "Hawaiian Islands (15-30N, 165-150W)"
    assert entry["variable"] == "Sea Level Anomaly (sla)"
    assert entry["size_bytes"] > 0


def test_altimetry_agent_fallback_to_secondary_url(tmp_path):
    """Test that the agent tries fallback URL when primary fails."""
    config = MagicMock()
    config.get_data_source_urls.return_value = {
        "altimetry": [
            "https://upwell.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day.graph?sla[(latest)][(15):(30)][(-165):(-150)]&amp;.draw=surface&amp;.vars=longitude|latitude|sla&amp;.size=800|600&amp;.png",
            "https://polarwatch.noaa.gov/erddap/griddap/nesdisSSH1day.graph?sla[(latest)][(15):(30)][(-165):(-150)]&amp;.draw=surface&amp;.vars=longitude|latitude|sla&amp;.size=800|600&amp;.png",
        ]
    }

    agent = AltimetryAgent(config)
    agent.ensure_http_client = AsyncMock()

    png_path = tmp_path / "ssh_hawaii_ERDDAP_PolarWatch.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake-png-data")

    # Mock download_file to fail first, succeed second
    agent.download_file = AsyncMock(
        side_effect=[
            {"status": "failed", "error": "Connection timeout"},
            {
                "status": "success",
                "file_path": str(png_path),
                "name": "ssh_hawaii_ERDDAP_PolarWatch.png",
            },
        ]
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert len(metadata) == 2  # One failure, one success
    assert metadata[0]["status"] == "failed"
    assert metadata[0]["source"] == "ERDDAP_Upwell"
    assert metadata[1]["status"] == "success"
    assert metadata[1]["source"] == "ERDDAP_PolarWatch"
    assert metadata[1]["type"] == "png_image"


def test_altimetry_agent_processes_zip_payload(tmp_path):
    config = MagicMock()
    config.get_data_source_urls.return_value = {"altimetry": ["https://example.com/archive.zip"]}

    agent = AltimetryAgent(config)
    agent.ensure_http_client = AsyncMock()

    zip_path = tmp_path / "test_archive.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("quicklook.png", b"fake-bytes")

    agent.download_file = AsyncMock(
        return_value={
            "status": "success",
            "file_path": str(zip_path),
            "type": "binary",
            "name": "test_archive.zip",
        }
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["type"] == "archive"
    assert entry["extracted_files"] == ["quicklook.png"]
    assert "extracted_dir" in entry


def test_altimetry_agent_processes_netcdf_gzip(tmp_path):
    config = MagicMock()
    config.get_data_source_urls.return_value = {"altimetry": ["https://example.com/pass.nc.gz"]}

    agent = AltimetryAgent(config)
    agent.ensure_http_client = AsyncMock()

    gz_path = tmp_path / "pass.nc.gz"
    with gzip.open(gz_path, "wb") as fh:
        fh.write(b"NetCDF mock payload")

    agent.download_file = AsyncMock(
        return_value={
            "status": "success",
            "file_path": str(gz_path),
            "type": "binary",
            "name": "pass.nc.gz",
        }
    )

    metadata = asyncio.run(agent.collect(tmp_path))

    assert metadata
    entry = metadata[0]
    assert entry["type"] == "netcdf"
    assert Path(entry["extracted_file"]).exists()
    # When netCDF4 is absent we expect a friendly message; otherwise a summary dict
    assert (
        "netcdf_summary" in entry or "netcdf_dimensions" in entry or "netcdf_summary_error" in entry
    )
