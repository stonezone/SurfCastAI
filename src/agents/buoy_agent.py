"""
NDBC Buoy Agent for collecting data from NOAA NDBC buoys.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from ..core.config import Config
from ..core.http_client import HTTPClient
from .base_agent import BaseAgent


class BuoyAgent(BaseAgent):
    """
    Agent for collecting buoy data from NOAA National Data Buoy Center (NDBC).

    Features:
    - Collects real-time buoy data
    - Parses tabular data into structured format
    - Extracts current conditions for quick access
    - Supports multiple buoy stations
    """

    def __init__(self, config: Config, http_client: HTTPClient | None = None):
        """Initialize the BuoyAgent."""
        super().__init__(config, http_client)
        self.base_url = "https://www.ndbc.noaa.gov"

    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        """
        Collect buoy data from NDBC.

        Args:
            data_dir: Directory to store collected data

        Returns:
            List of metadata dictionaries
        """
        # Ensure data directory exists
        buoy_dir = data_dir / "buoys"
        buoy_dir.mkdir(exist_ok=True)

        # Get buoy URLs from config
        buoy_urls = self.config.get_data_source_urls("buoys").get("buoys", [])

        if not buoy_urls:
            self.logger.warning("No buoy URLs configured")
            return []

        # Ensure HTTP client is available
        await self.ensure_http_client()

        # Create tasks for all buoy URLs
        tasks = []
        for url in buoy_urls:
            tasks.append(self.process_buoy(url, buoy_dir))

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing buoy: {result}")
            elif result:
                metadata_list.append(result)

        return metadata_list

    async def process_buoy(self, url: str, buoy_dir: Path) -> dict[str, Any]:
        """Process a single buoy endpoint (HTML, text, or spectral)."""
        station_id = "unknown"
        try:
            # Determine station from URL
            parsed = url.split("/")[-1]
            station_id = parsed.split(".")[0]
            station_id = station_id.split("?")[0]
            self.logger.info(f"Processing buoy station {station_id} -> {url}")

            result = await self.http_client.download(url)
            if not result.success:
                return self.create_metadata(
                    name=f"buoy_{station_id}",
                    description=f"Failed to fetch buoy data for station {station_id}",
                    data_type="text",
                    source_url=url,
                    error=result.error,
                )

            content_type = (result.content_type or "").lower()
            content = result.content.decode("utf-8", errors="ignore") if result.content else ""

            if url.endswith(".spec") or "spec" in parsed:
                return self._handle_spectral_buoy(station_id, url, content, buoy_dir)

            if "text" in content_type or url.endswith(".txt"):
                buoy_data = self._parse_text_buoy(content, station_id)
            else:
                # Assume HTML page with table fallback
                buoy_data = self._parse_html_buoy(content, station_id)

            if "observations" not in buoy_data or not buoy_data["observations"]:
                return self.create_metadata(
                    name=f"buoy_{station_id}",
                    description=f"No observations parsed for station {station_id}",
                    data_type="json",
                    source_url=url,
                    error="empty_observations",
                )

            file_path = buoy_dir / f"buoy_{station_id}.json"
            with open(file_path, "w") as fh:
                json.dump(buoy_data, fh, indent=2)

            return self.create_metadata(
                name=file_path.name,
                description=f"NDBC buoy observations for station {station_id}",
                data_type="json",
                source_url=url,
                file_path=str(file_path),
                size_bytes=file_path.stat().st_size,
                station_id=station_id,
                data_points=len(buoy_data["observations"]),
                current_conditions=buoy_data.get("current_conditions"),
            )

        except Exception as exc:  # pragma: no cover - defensive catch
            self.logger.error(f"Error processing buoy {url}: {exc}")
            return self.create_metadata(
                name=f"buoy_{station_id}",
                description="Failed to process buoy data",
                data_type="unknown",
                source_url=url,
                error=str(exc),
            )

    def _parse_html_buoy(self, html: str, station_id: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        data_table = soup.find("table", {"class": "dataTable"})
        if not data_table:
            return {"station_id": station_id, "observations": [], "raw_html": html}
        return self._parse_buoy_table(data_table, station_id)

    def _parse_text_buoy(self, text: str, station_id: str) -> dict[str, Any]:
        lines = [line for line in text.splitlines() if line.strip()]
        header_line = None
        data_start = 0
        for idx, line in enumerate(lines):
            if line.startswith("#") and not line.startswith("##"):
                header_line = line.lstrip("#").strip()
                data_start = idx + 1
                break
        if not header_line:
            return {"station_id": station_id, "observations": []}

        headers = header_line.split()
        observations: list[dict[str, Any]] = []
        for line in lines[data_start:]:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < len(headers):
                continue
            row = dict(zip(headers, parts, strict=False))
            iso_time = self._build_timestamp(row)
            if iso_time:
                row["Date"] = iso_time
            observations.append(row)

        data = {
            "station_id": station_id,
            "observations": observations,
            "metadata": {"source_format": "text", "columns": headers},
        }

        if observations:
            current = observations[0]
            data["current_conditions"] = {
                "wave_height": current.get("WVHT", current.get("WVHT(m)", "N/A")),
                "dominant_period": current.get("DPD", "N/A"),
                "wind_speed": current.get("WSPD", "N/A"),
                "wind_direction": current.get("WDIR", "N/A"),
                "timestamp": current.get("Date", "N/A"),
                "water_temp": current.get("WTMP", "N/A"),
                "air_temp": current.get("ATMP", "N/A"),
                "pressure": current.get("PRES", "N/A"),
            }

        return data

    def _build_timestamp(self, row: dict[str, str]) -> str | None:
        required = ["YY", "MM", "DD", "hh", "mm"]
        if not all(key in row for key in required):
            return None
        try:
            year = int(row["YY"])
            # Handle both 2-digit and 4-digit years
            if year < 100:
                # 2-digit year: 00-69 = 2000-2069, 70-99 = 1970-1999
                year += 2000 if year < 70 else 1900
            # else: already 4-digit year, use as-is
            month = int(row["MM"])
            day = int(row["DD"])
            hour = int(row["hh"])
            minute = int(row["mm"])
            dt = datetime(year, month, day, hour, minute, tzinfo=UTC)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:  # pragma: no cover - continue without timestamp
            return None

    def _handle_spectral_buoy(
        self, station_id: str, url: str, text: str, buoy_dir: Path
    ) -> dict[str, Any]:
        spectrum = self._parse_spectral_data(text)
        data = {
            "station_id": station_id,
            "spectrum": spectrum,
            "fetched_at": datetime.now(UTC).isoformat(),
            "source_url": url,
        }
        output_path = buoy_dir / f"buoy_{station_id}_spectral.json"
        with open(output_path, "w") as fh:
            json.dump(data, fh, indent=2)
        return self.create_metadata(
            name=output_path.name,
            description=f"Spectral wave data for station {station_id}",
            data_type="json",
            source_url=url,
            file_path=str(output_path),
            size_bytes=output_path.stat().st_size,
            station_id=station_id,
            spectrum_points=len(spectrum.get("frequencies", [])),
        )

    def _parse_spectral_data(self, text: str) -> dict[str, list[float]]:
        frequencies: list[float] = []
        densities: list[float] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                freq = float(parts[0])
                dens = float(parts[1])
            except ValueError:
                continue
            frequencies.append(freq)
            densities.append(dens)
        return {"frequencies": frequencies, "densities": densities}

    def _parse_buoy_table(self, table, station_id: str) -> dict[str, Any]:
        """
        Parse NDBC buoy data table into structured format.

        Args:
            table: BeautifulSoup table element
            station_id: Buoy station ID

        Returns:
            Structured buoy data dictionary
        """
        try:
            data = {"station_id": station_id, "observations": []}

            # Find all rows
            rows = table.find_all("tr")

            # Extract headers
            headers = []
            header_row = rows[0] if rows else None
            if header_row:
                headers = [th.text.strip() for th in header_row.find_all(["th", "td"])]

            # Extract data rows
            for row in rows[1:]:
                cells = row.find_all("td")
                if cells:
                    observation = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            observation[headers[i]] = cell.text.strip()
                    data["observations"].append(observation)

            # Extract current conditions if available
            if data["observations"]:
                current = data["observations"][0]
                data["current_conditions"] = {
                    "wave_height": current.get("WVHT", "N/A"),
                    "dominant_period": current.get("DPD", "N/A"),
                    "wind_speed": current.get("WSPD", "N/A"),
                    "wind_direction": current.get("WDIR", "N/A"),
                    "timestamp": current.get("Date", "N/A"),
                    "water_temp": current.get("WTMP", "N/A"),
                    "air_temp": current.get("ATMP", "N/A"),
                    "pressure": current.get("PRES", "N/A"),
                }

            return data

        except Exception as e:
            self.logger.error(f"Error parsing buoy table: {e}")
            return {"station_id": station_id, "error": str(e), "raw_html": str(table)}
