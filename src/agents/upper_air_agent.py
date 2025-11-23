"""Agent for fetching upper-air analysis graphics (jet stream, height fields)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


@dataclass
class UpperAirSource:
    """Configuration descriptor for an upper-air product."""

    source_id: str
    url: str
    level: str
    product_type: str = "jet_stream"
    description: str | None = None
    date_format: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> UpperAirSource:
        if not isinstance(raw, dict):  # pragma: no cover - defensive guard
            raise ValueError("Upper-air configuration entries must be dictionaries")

        source_id = str(raw.get("id") or raw.get("source_id") or "upper_air").strip()
        url = str(raw.get("url", "")).strip()
        level = str(raw.get("level", "")).strip()
        product_type = (
            str(raw.get("type", raw.get("product_type", "jet_stream"))).strip() or "jet_stream"
        )
        description = raw.get("description")
        date_format = raw.get("date_format")

        if not source_id:
            raise ValueError("Upper-air source missing 'id'")
        if not url:
            raise ValueError(f"Upper-air source '{source_id}' missing 'url'")
        if not level:
            raise ValueError(f"Upper-air source '{source_id}' missing 'level'")

        return cls(
            source_id=source_id,
            url=url,
            level=level,
            product_type=product_type,
            description=description,
            date_format=date_format,
        )

    def filename(self) -> str:
        """Derive a filename for the downloaded asset."""
        basename = self.url.split("?")[0].split("/")[-1] or f"{self.source_id}.png"
        return f"{self.source_id}_{self.level}_{basename}"


class UpperAirAgent(BaseAgent):
    """Collect SPC/NOAA upper-air analyses to capture jet stream diagnostics."""

    @staticmethod
    def _compute_most_recent_00z() -> datetime:
        """
        Compute the most recent 00Z synoptic time for SPC products.

        SPC upper-air analyses are only available at 00Z. If current time is before
        02:00 UTC, use yesterday's 00Z (to allow for processing/posting delay).

        Returns:
            datetime: The most recent 00Z timestamp (UTC).
        """
        now_utc = datetime.now(UTC)

        # If before 02:00 UTC, use yesterday's 00Z
        if now_utc.hour < 2:
            target_date = now_utc.date() - timedelta(days=1)
        else:
            target_date = now_utc.date()

        return datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=UTC)

    def _expand_date_template(self, url: str, date_format: str | None = None) -> str:
        """
        Expand {date} placeholder in URL with computed synoptic time.

        Args:
            url: URL template potentially containing {date} placeholder
            date_format: strftime format string (e.g., "%y%m%d" for YYMMDD)

        Returns:
            str: URL with date placeholder expanded, or original URL if no placeholder
        """
        if "{date}" not in url:
            return url

        if not date_format:
            self.logger.warning(
                "URL contains {date} placeholder but no date_format specified, using default %y%m%d"
            )
            date_format = "%y%m%d"

        synoptic_time = self._compute_most_recent_00z()
        date_str = synoptic_time.strftime(date_format)
        expanded_url = url.replace("{date}", date_str)

        self.logger.info(f"Expanded URL template: {url} -> {expanded_url}")
        return expanded_url

    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        config = self.config.get("data_sources", "upper_air", {})
        sources_cfg = []
        if isinstance(config, dict):
            sources_cfg = config.get("sources", [])

        sources: list[UpperAirSource] = []
        for entry in sources_cfg:
            try:
                sources.append(UpperAirSource.from_dict(entry))
            except Exception as exc:
                self.logger.error(f"Invalid upper-air source configuration: {exc}")

        if not sources:
            self.logger.warning("No upper-air sources configured")
            return []

        metadata: list[dict[str, Any]] = []
        await self.ensure_http_client()

        for source in sources:
            # Expand any date templates in the URL
            expanded_url = self._expand_date_template(source.url, source.date_format)

            filename = source.filename()
            result = await self.download_file(
                expanded_url,
                filename=filename,
                data_dir=data_dir,
                description=source.description or f"Upper-air analysis ({source.level} hPa)",
            )

            if result.get("status") == "success":
                file_path = Path(result.get("file_path", ""))
                if file_path.exists():
                    result["size_bytes"] = file_path.stat().st_size
                result["analysis_level"] = source.level
                result["product_type"] = source.product_type
                result["source_id"] = source.source_id
                result["data_source"] = "SPC" if "spc.noaa.gov" in expanded_url else "NOAA/WPC"
            metadata.append(result)

        return metadata


__all__ = ["UpperAirAgent", "UpperAirSource"]
