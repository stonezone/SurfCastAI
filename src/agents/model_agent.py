"""
Model Agent for collecting wave model data from PacIOOS, NOAA, and other sources.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.http_client import HTTPClient
from .base_agent import BaseAgent


class ModelAgent(BaseAgent):
    """
    Agent for collecting wave model data from various sources.

    Features:
    - Collects data from PacIOOS SWAN, WaveWatch III, and other wave models
    - Supports both direct data downloads and web scraping
    - Processes model imagery and data files
    - Extracts model run metadata
    """

    def __init__(self, config: Config, http_client: HTTPClient | None = None):
        """Initialize the ModelAgent."""
        super().__init__(config, http_client)
        self.logger = logging.getLogger("agent.model")

    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        """
        Collect wave model data from configured sources.

        Args:
            data_dir: Directory to store collected data

        Returns:
            List of metadata dictionaries
        """
        # Use the provided data_dir directly (already agent-specific)
        model_dir = data_dir

        # Get model URLs from config
        model_urls = self.config.get_data_source_urls("models").get("models", [])

        if not model_urls:
            self.logger.warning("No wave model URLs configured")
            return []

        # Ensure HTTP client is available
        await self.ensure_http_client()

        # Create tasks for all model URLs
        tasks = []
        for url in model_urls:
            tasks.append(self.process_model_url(url, model_dir))

        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        metadata_list: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing model data: {result}")
            elif isinstance(result, dict):
                metadata_list.append(result)

        return metadata_list

    async def process_model_url(self, url: str, model_dir: Path) -> dict[str, Any]:
        """
        Process a single wave model URL.

        Args:
            url: URL to the model data
            model_dir: Directory to store model data

        Returns:
            Metadata dictionary
        """
        last_error = None
        for resolved_url in self._expand_url_templates(url):
            try:
                # Determine model type from URL (use resolved URL for better hints)
                model_type = self._determine_model_type(resolved_url)
                location = self._extract_location(resolved_url, model_type)

                self.logger.info(
                    "Processing %s model data for %s (%s)", model_type, location, resolved_url
                )

                # Check for image formats
                if resolved_url.endswith((".png", ".jpg", ".gif")):
                    result = await self._process_model_image(
                        resolved_url, model_dir, model_type, location
                    )
                # Check for data files - handle both direct extensions and query string formats (ERDDAP)
                elif (
                    resolved_url.endswith((".json", ".txt", ".csv"))
                    or ".csv?" in resolved_url
                    or ".json?" in resolved_url
                    or ".txt?" in resolved_url
                ):
                    result = await self._process_model_data_file(
                        resolved_url, model_dir, model_type, location
                    )
                else:
                    result = await self._process_model_page(
                        resolved_url, model_dir, model_type, location
                    )

                if result.get("status") == "success":
                    if resolved_url != url:
                        result.setdefault("template_url", url)
                    result.setdefault("resolved_url", resolved_url)
                    return result

                last_error = result.get("error") or last_error
            except Exception as e:
                last_error = str(e)
                self.logger.warning("Failed model URL %s: %s", resolved_url, e)
                continue

        # All attempts failed; report the final error state
        self.logger.error(f"Error processing model data from {url}: {last_error}")
        return self.create_metadata(
            name="model_unknown_unknown",
            description="Failed to process model data",
            data_type="unknown",
            source_url=url,
            error=last_error or "No candidates succeeded",
        )

    async def _process_model_image(
        self, url: str, model_dir: Path, model_type: str, location: str
    ) -> dict[str, Any]:
        """Process a direct model image URL."""
        # Generate filename from URL
        filename = f"model_{model_type}_{location}_{url.split('/')[-1]}"

        # Download the image
        result = await self.http_client.download(
            url, save_to_disk=True, custom_file_path=model_dir / filename
        )

        if result.success:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"{model_type} wave model image for {location}",
                data_type="image",
                source_url=url,
                file_path=str(result.file_path),
                model_type=model_type,
                location=location,
                content_type=result.content_type,
                size_bytes=result.size_bytes,
            )
        else:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model image for {location}",
                data_type="image",
                source_url=url,
                error=result.error,
            )

    async def _process_model_data_file(
        self, url: str, model_dir: Path, model_type: str, location: str
    ) -> dict[str, Any]:
        """Process a direct model data file URL."""
        # Generate filename from URL - handle query strings for ERDDAP
        url_base = url.split("?")[0]  # Remove query string for filename
        base_filename = url_base.split("/")[-1]

        # Determine extension from URL pattern
        if ".csv" in url:
            extension = ".csv"
        elif ".json" in url:
            extension = ".json"
        elif ".txt" in url:
            extension = ".txt"
        else:
            extension = ""

        # Ensure base filename has proper extension
        if extension and not base_filename.endswith(extension):
            base_filename = base_filename + extension

        filename = f"model_{model_type}_{location}_{base_filename}"

        # Download the data file
        result = await self.http_client.download(
            url, save_to_disk=True, custom_file_path=model_dir / filename
        )

        if result.success:
            # Determine data type from URL pattern or content type
            if ".json" in url or "application/json" in (result.content_type or ""):
                data_type = "json"
            elif ".csv" in url or "text/csv" in (result.content_type or ""):
                data_type = "csv"
            else:
                data_type = "text"

            # Extract model run metadata if possible
            model_metadata = {}
            parsed_summary = {}
            if data_type == "json":
                try:
                    content = result.content.decode("utf-8", errors="ignore")
                    data = json.loads(content)
                    model_metadata = self._extract_model_metadata(data, model_type)
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning(f"Failed to extract model metadata: {e}")
            elif data_type == "csv":
                try:
                    parsed_summary = self._parse_ww3_csv(Path(result.file_path))
                except Exception as e:  # pragma: no cover - defensive
                    self.logger.warning(f"Failed to parse WW3 CSV {url}: {e}")

            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"{model_type} wave model data for {location}",
                data_type=data_type,
                source_url=url,
                file_path=str(result.file_path),
                model_type=model_type,
                location=location,
                content_type=result.content_type,
                size_bytes=result.size_bytes,
                model_metadata=model_metadata,
                parsed_summary=parsed_summary,
            )
        else:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model data for {location}",
                data_type="unknown",
                source_url=url,
                error=result.error,
            )

    async def _process_model_page(
        self, url: str, model_dir: Path, model_type: str, location: str
    ) -> dict[str, Any]:
        """Process a model web page URL to extract data and images."""
        # Download the page content
        result = await self.http_client.download(url)

        if not result.success:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model page for {location}",
                data_type="html",
                source_url=url,
                error=result.error,
            )

        # Save the original page
        page_filename = f"model_{model_type}_{location}_page.html"
        page_path = model_dir / page_filename

        with open(page_path, "wb") as f:
            f.write(result.content)

        # Extract image URLs from the page
        image_urls = self._extract_image_urls(result.content.decode("utf-8", errors="ignore"), url)

        # Download images
        image_metadata = []
        for img_url in image_urls:
            try:
                # Generate filename from URL
                img_filename = f"model_{model_type}_{location}_{img_url.split('/')[-1]}"

                # Download the image
                img_result = await self.http_client.download(
                    img_url, save_to_disk=True, custom_file_path=model_dir / img_filename
                )

                if img_result.success:
                    image_metadata.append(
                        {
                            "url": img_url,
                            "file_path": str(img_result.file_path),
                            "content_type": img_result.content_type,
                            "size_bytes": img_result.size_bytes,
                        }
                    )
            except Exception as e:
                self.logger.warning(f"Failed to download image {img_url}: {e}")

        return self.create_metadata(
            name=f"model_{model_type}_{location}",
            description=f"{model_type} wave model data for {location}",
            data_type="html",
            source_url=url,
            file_path=str(page_path),
            model_type=model_type,
            location=location,
            image_count=len(image_metadata),
            images=image_metadata,
        )

    def _determine_model_type(self, url: str) -> str:
        """Determine the type of wave model from the URL."""
        url_lower = url.lower()

        if "erddap" in url_lower:
            if "ww3" in url_lower or "wavewatch" in url_lower:
                return "ww3"
            return "erddap"
        elif "swan" in url_lower:
            return "swan"
        elif "ww3" in url_lower or "wavewatch" in url_lower:
            return "ww3"
        elif "cdip" in url_lower:
            return "cdip"
        elif "pacioos" in url_lower:
            return "pacioos"
        elif "surfline" in url_lower:
            return "surfline"
        else:
            return "unknown"

    def _extract_location(self, url: str, model_type: str) -> str:
        """Extract location information from the URL."""
        url_lower = url.lower()

        # Handle ERDDAP URLs - check more specific patterns first
        if "erddap" in url_lower:
            # Check for 'global' before 'hawaii' to avoid 'hawaii' substring in 'pae-paha.pacioos.hawaii.edu'
            if "ww3_global" in url_lower:
                return "global"
            elif "ww3_hawaii" in url_lower or "/hawaii" in url_lower:
                return "hawaii"
            elif "pacific" in url_lower:
                return "pacific"

        # Extract location based on model type and URL patterns
        if model_type == "swan":
            if "oahu" in url_lower:
                return "oahu"
            elif "hawaii" in url_lower:
                return "hawaii"
            else:
                # Try to extract location from URL segments
                parts = url.split("/")
                for part in parts:
                    if part.lower() in ["oahu", "hawaii", "maui", "kauai"]:
                        return part.lower()

        elif model_type == "ww3":
            if "pacific" in url_lower:
                if "north" in url_lower:
                    return "north_pacific"
                elif "south" in url_lower:
                    return "south_pacific"
                else:
                    return "pacific"
            elif "hawaii" in url_lower:
                return "hawaii"

        # Default fallback - extract location from any geographic terms
        geo_terms = ["oahu", "hawaii", "maui", "kauai", "pacific", "atlantic"]
        for term in geo_terms:
            if term in url_lower:
                return term

        return "unknown"

    def _extract_image_urls(self, html_content: str, base_url: str) -> list[str]:
        """Extract image URLs from HTML content."""
        # Basic regex for image URLs
        img_patterns = [
            r'<img[^>]+src="([^"]+\.(jpg|jpeg|png|gif))"',
            r'<a[^>]+href="([^"]+\.(jpg|jpeg|png|gif))"',
        ]

        image_urls = []
        for pattern in img_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                img_url = match[0]

                # Handle relative URLs
                if not img_url.startswith(("http://", "https://")):
                    # Remove any leading '/' from img_url
                    img_url = img_url.lstrip("/")

                    # Add base URL
                    if base_url.endswith("/"):
                        img_url = base_url + img_url
                    else:
                        img_url = base_url + "/" + img_url

                image_urls.append(img_url)

        return image_urls

    def _expand_url_templates(self, url: str) -> list[str]:
        """Expand template placeholders in configured URLs.

        Supports:
        - {date}: YYYYMMDD format (today and yesterday)
        - {hour}: Synoptic hours (00, 06, 12, 18) - tries most recent first
        """
        # If no templates, return as-is
        if "{date}" not in url and "{hour}" not in url:
            return [url]

        now = datetime.utcnow()

        # Generate date candidates (today, yesterday)
        date_candidates = [now.strftime("%Y%m%d"), (now - timedelta(days=1)).strftime("%Y%m%d")]

        # Generate hour candidates (most recent synoptic time first)
        # WW3 runs at 00Z, 06Z, 12Z, 18Z
        current_hour = now.hour
        synoptic_hours = ["00", "06", "12", "18"]

        # Find most recent synoptic hour
        hour_candidates = []
        for h in reversed(synoptic_hours):
            h_int = int(h)
            if current_hour >= h_int:
                hour_candidates.append(h)
        # Add remaining hours from previous day
        for h in reversed(synoptic_hours):
            h_int = int(h)
            if current_hour < h_int:
                hour_candidates.append(h)

        # Expand URLs with all combinations
        expanded = []

        if "{date}" in url and "{hour}" in url:
            # Both placeholders - try combinations
            for date_val in date_candidates:
                for hour_val in hour_candidates:
                    expanded_url = url.replace("{date}", date_val).replace("{hour}", hour_val)
                    expanded.append(expanded_url)
        elif "{date}" in url:
            # Only date placeholder
            for date_val in date_candidates:
                expanded.append(url.replace("{date}", date_val))
        elif "{hour}" in url:
            # Only hour placeholder
            for hour_val in hour_candidates:
                expanded.append(url.replace("{hour}", hour_val))

        return expanded

    def _extract_model_metadata(self, data: dict[str, Any], model_type: str) -> dict[str, Any]:
        """Extract metadata from model data."""
        metadata = {
            "model_type": model_type,
            "run_time": None,
            "forecast_hours": None,
            "parameters": [],
        }

        try:
            # Different extraction logic based on model type
            if model_type == "swan":
                # SWAN metadata extraction
                if "metadata" in data:
                    meta = data["metadata"]
                    metadata["run_time"] = meta.get("run_time")
                    metadata["forecast_hours"] = meta.get("forecast_hours")

                # Extract parameters
                if "parameters" in data:
                    metadata["parameters"] = list(data["parameters"].keys())

            elif model_type == "ww3":
                # WW3 metadata extraction
                if "header" in data:
                    header = data["header"]
                    metadata["run_time"] = header.get("refTime")
                    metadata["forecast_hours"] = header.get("forecastTime")

                # Extract parameters
                if "parameters" in data:
                    metadata["parameters"] = [p.get("name") for p in data["parameters"]]

        except Exception as e:
            self.logger.warning(f"Error extracting model metadata: {e}")

        return metadata

    def _parse_ww3_csv(self, file_path: Path) -> dict[str, Any]:
        """
        Parse WW3 point output CSV into structured summary.

        Supports two formats:
        1. NOMADS point output: time,Hs,Tp,Dp (with # comments)
        2. ERDDAP gridded output: time,depth,latitude,longitude,Thgt,Tper,Tdir,shgt,sper,sdir (with units row)
        """
        summary: dict[str, Any] = {"rows": 0, "events": [], "format": "unknown"}

        if not file_path.exists():
            return summary

        header: list[str] | None = None
        records: list[dict[str, str]] = []
        station_meta: dict[str, Any] = {}
        is_erddap = False
        units_row_found = False

        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue

                if line.startswith("#") or line.startswith("!"):
                    # Capture metadata lines of the form "# KEY: value"
                    cleaned = line.lstrip("#!").strip()
                    if ":" in cleaned:
                        key, value = (part.strip() for part in cleaned.split(":", 1))
                        key_normalized = key.lower().replace(" ", "_")
                        station_meta[key_normalized] = value
                    continue

                if header is None:
                    header = [h.strip() for h in line.split(",") if h.strip()]

                    # Detect ERDDAP format by column structure
                    if "latitude" in header and "longitude" in header and "depth" in header:
                        is_erddap = True
                        summary["format"] = "erddap"
                    else:
                        summary["format"] = "nomads"
                    continue

                # Check if this is the units row (ERDDAP format)
                if is_erddap and not units_row_found:
                    # Units row has entries like "UTC", "m", "degrees_north", "degrees_east", "meters"
                    if any(
                        unit in line
                        for unit in ["UTC", "degrees_north", "degrees_east", "meters", "m"]
                    ):
                        units_row_found = True
                        continue

                row = [value.strip() for value in line.split(",")]
                if header and len(row) >= len(header):
                    record = {header[i]: row[i] for i in range(len(header))}
                    records.append(record)

        summary["rows"] = len(records)
        if station_meta:
            summary["metadata"] = station_meta

        if not records:
            return summary

        if is_erddap:
            # ERDDAP format: aggregate grid points by time
            return self._parse_erddap_records(records, summary)
        else:
            # NOMADS format: time-series at single point
            return self._parse_nomads_records(records, summary)

    def _parse_erddap_records(
        self, records: list[dict[str, str]], summary: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse ERDDAP gridded WW3 CSV records."""
        # Group by time and aggregate statistics
        time_groups: dict[str, list[dict[str, Any]]] = {}

        for record in records:
            timestamp = record.get("time")
            if not timestamp:
                continue

            if timestamp not in time_groups:
                time_groups[timestamp] = []

            # Extract wave parameters (ERDDAP uses different names)
            point_data = {
                "lat": self._to_float(record.get("latitude")),
                "lon": self._to_float(record.get("longitude")),
                "depth": self._to_float(record.get("depth")),
                "thgt": self._to_float(record.get("Thgt")),  # Total significant height
                "tper": self._to_float(record.get("Tper")),  # Peak period
                "tdir": self._to_float(record.get("Tdir")),  # Peak direction
                "shgt": self._to_float(record.get("shgt")),  # Swell height
                "sper": self._to_float(record.get("sper")),  # Swell period
                "sdir": self._to_float(record.get("sdir")),  # Swell direction
            }
            time_groups[timestamp].append(point_data)

        # Compute summary statistics across grid
        events: list[dict[str, Any]] = []
        all_thgt: list[float] = []
        all_tper: list[float] = []
        all_tdir: list[float] = []
        all_shgt: list[float] = []

        for timestamp in sorted(time_groups.keys())[:12]:  # Keep first 12 time steps
            points = time_groups[timestamp]

            # Extract valid values
            thgt_vals = [p["thgt"] for p in points if p["thgt"] is not None]
            tper_vals = [p["tper"] for p in points if p["tper"] is not None]
            tdir_vals = [p["tdir"] for p in points if p["tdir"] is not None]
            shgt_vals = [p["shgt"] for p in points if p["shgt"] is not None]

            all_thgt.extend(thgt_vals)
            all_tper.extend(tper_vals)
            all_tdir.extend(tdir_vals)
            all_shgt.extend(shgt_vals)

            if thgt_vals:
                event = {
                    "timestamp": timestamp,
                    "thgt_mean_m": sum(thgt_vals) / len(thgt_vals),
                    "thgt_max_m": max(thgt_vals),
                    "thgt_min_m": min(thgt_vals),
                    "grid_points": len(points),
                }

                if tper_vals:
                    event["tper_mean_s"] = sum(tper_vals) / len(tper_vals)
                if tdir_vals:
                    event["tdir_mean_deg"] = sum(tdir_vals) / len(tdir_vals)
                if shgt_vals:
                    event["shgt_mean_m"] = sum(shgt_vals) / len(shgt_vals)

                events.append(event)

        # Overall statistics
        if all_thgt:
            summary["total_height_max_m"] = max(all_thgt)
            summary["total_height_min_m"] = min(all_thgt)
            summary["total_height_mean_m"] = sum(all_thgt) / len(all_thgt)
        if all_tper:
            summary["peak_period_range_s"] = [min(all_tper), max(all_tper)]
        if all_tdir:
            summary["peak_direction_range_deg"] = [min(all_tdir), max(all_tdir)]
        if all_shgt:
            summary["swell_height_max_m"] = max(all_shgt)
            summary["swell_height_mean_m"] = sum(all_shgt) / len(all_shgt)

        summary["events"] = events
        summary["time_steps"] = len(time_groups)
        summary["grid_points_per_time"] = len(records) // len(time_groups) if time_groups else 0

        return summary

    def _parse_nomads_records(
        self, records: list[dict[str, str]], summary: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse NOMADS point WW3 CSV records (legacy format)."""
        hs_values: list[float] = []
        tp_values: list[float] = []
        dp_values: list[float] = []
        events: list[dict[str, Any]] = []

        for record in records:
            hs = self._to_float(record.get("Hs") or record.get("Significant Wave Height"))
            tp = self._to_float(record.get("Tp") or record.get("Peak Period"))
            dp = self._to_float(record.get("Dp") or record.get("Peak Direction"))
            timestamp = record.get("time") or record.get("Time") or record.get("Date")

            if hs is not None:
                hs_values.append(hs)
            if tp is not None:
                tp_values.append(tp)
            if dp is not None:
                dp_values.append(dp)

            if timestamp:
                event = {"timestamp": timestamp, "hs_m": hs, "tp_s": tp, "dp_deg": dp}
                events.append(event)

        if hs_values:
            summary["significant_height_max"] = max(hs_values)
            summary["significant_height_min"] = min(hs_values)
        if tp_values:
            summary["peak_period_range"] = [min(tp_values), max(tp_values)]
        if dp_values:
            summary["peak_direction_range"] = [min(dp_values), max(dp_values)]

        summary["events"] = events[:12]  # keep first dozen entries for downstream prompts
        return summary

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
