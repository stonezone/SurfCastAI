"""Tests for ModelAgent WW3 CSV parsing."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.model_agent import ModelAgent
from src.core.config import Config


def _build_agent(tmp_path: Path) -> ModelAgent:
    config = MagicMock(spec=Config)
    agent = ModelAgent(config)
    agent.ensure_http_client = AsyncMock()
    return agent


def _create_nomads_csv(tmp_path: Path) -> Path:
    """Create a NOMADS-style WW3 CSV file."""
    content = """# Station ID: 51001
# Run Time: 2025-10-15T00:00Z
time,Hs,Tp,Dp
2025-10-15T00:00Z,2.5,14,320
2025-10-15T06:00Z,3.1,16,325
"""
    csv_path = tmp_path / "ww3_nomads.csv"
    csv_path.write_text(content)
    return csv_path


def _create_erddap_csv(tmp_path: Path) -> Path:
    """Create an ERDDAP-style WW3 CSV file with gridded data."""
    content = """time,depth,latitude,longitude,Thgt,Tper,Tdir,shgt,sper,sdir
UTC,m,degrees_north,degrees_east,meters,seconds,degrees,meters,seconds,degrees
2025-10-22T18:00:00Z,0.0,21.0,200.0,2.45,12.5,315,1.8,14.2,310
2025-10-22T18:00:00Z,0.0,21.0,200.05,2.43,12.3,318,1.75,14.0,312
2025-10-22T18:00:00Z,0.0,21.05,200.0,2.46,12.6,316,1.82,14.3,311
2025-10-22T18:00:00Z,0.0,21.05,200.05,2.44,12.4,317,1.78,14.1,313
2025-10-23T00:00:00Z,0.0,21.0,200.0,2.75,13.2,320,2.1,15.0,315
2025-10-23T00:00:00Z,0.0,21.0,200.05,2.72,13.0,322,2.05,14.8,317
"""
    csv_path = tmp_path / "ww3_erddap.csv"
    csv_path.write_text(content)
    return csv_path


def test_model_agent_parses_nomads_ww3_csv(tmp_path):
    """Test parsing NOMADS-style WW3 CSV format."""
    agent = _build_agent(tmp_path)

    csv_path = _create_nomads_csv(tmp_path)
    download_result = SimpleNamespace(
        success=True,
        file_path=str(csv_path),
        content=b"",
        content_type="text/csv",
        size_bytes=csv_path.stat().st_size,
    )

    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=download_result))

    metadata = asyncio.run(
        agent._process_model_data_file(
            "https://example.com/ww3_point.csv", tmp_path, "ww3", "hawaii"
        )
    )

    assert metadata["type"] == "csv"
    summary = metadata["parsed_summary"]
    assert summary["format"] == "nomads"
    assert summary["rows"] == 2
    assert summary["significant_height_max"] == pytest.approx(3.1)
    assert summary["events"][0]["timestamp"] == "2025-10-15T00:00Z"


def test_model_agent_parses_erddap_ww3_csv(tmp_path):
    """Test parsing ERDDAP-style WW3 CSV format with gridded data."""
    agent = _build_agent(tmp_path)

    csv_path = _create_erddap_csv(tmp_path)
    download_result = SimpleNamespace(
        success=True,
        file_path=str(csv_path),
        content=b"",
        content_type="text/csv",
        size_bytes=csv_path.stat().st_size,
    )

    agent.http_client = SimpleNamespace(download=AsyncMock(return_value=download_result))

    metadata = asyncio.run(
        agent._process_model_data_file(
            "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv",
            tmp_path,
            "ww3",
            "hawaii",
        )
    )

    assert metadata["type"] == "csv"
    summary = metadata["parsed_summary"]
    assert summary["format"] == "erddap"
    assert summary["rows"] == 6
    assert summary["time_steps"] == 2
    assert summary["grid_points_per_time"] == 3

    # Check aggregated statistics
    assert "total_height_max_m" in summary
    assert summary["total_height_max_m"] == pytest.approx(2.75)
    assert "total_height_mean_m" in summary
    assert "swell_height_max_m" in summary
    assert summary["swell_height_max_m"] == pytest.approx(2.1)

    # Check time-aggregated events
    assert len(summary["events"]) == 2
    first_event = summary["events"][0]
    assert first_event["timestamp"] == "2025-10-22T18:00:00Z"
    assert "thgt_mean_m" in first_event
    assert "thgt_max_m" in first_event
    assert first_event["grid_points"] == 4


def test_model_agent_recognizes_erddap_urls():
    """Test that ERDDAP URLs are properly identified."""
    agent = _build_agent(Path("/tmp"))

    erddap_url = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv"
    model_type = agent._determine_model_type(erddap_url)
    location = agent._extract_location(erddap_url, model_type)

    assert model_type == "ww3"
    assert location == "hawaii"

    global_url = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csv"
    model_type_global = agent._determine_model_type(global_url)
    location_global = agent._extract_location(global_url, model_type_global)

    assert model_type_global == "ww3"
    assert location_global == "global"
