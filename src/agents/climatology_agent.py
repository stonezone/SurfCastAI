"""Agent for collecting climatology reference datasets (SNN stats, UH climatology)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


@dataclass
class ClimatologySource:
    """Configuration descriptor for climatology fetches."""

    source_id: str
    url: str
    format: str = "text"
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ClimatologySource":
        if not isinstance(raw, dict):  # pragma: no cover - defensive guard
            raise ValueError("Climatology entries must be dictionaries")

        source_id = str(raw.get("id") or raw.get("source_id") or "climatology").strip()
        url = str(raw.get("url", "")).strip()
        fmt = str(raw.get("format", "text")).strip().lower() or "text"
        description = raw.get("description")

        if not source_id:
            raise ValueError("Climatology source missing 'id'")
        if not url:
            raise ValueError(f"Climatology source '{source_id}' missing 'url'")

        return cls(source_id=source_id, url=url, format=fmt, description=description)

    def filename(self) -> str:
        suffix = {
            'json': '.json',
            'csv': '.csv',
            'html': '.html',
            'text': '.txt'
        }.get(self.format, '.dat')
        return f"{self.source_id}{suffix}"


class ClimatologyAgent(BaseAgent):
    """Collect textual/statistical climate references for context enrichment."""

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        config = self.config.get("data_sources", "climatology", {})
        sources_cfg = []
        if isinstance(config, dict):
            sources_cfg = config.get("sources", [])

        sources: List[ClimatologySource] = []
        for entry in sources_cfg:
            try:
                sources.append(ClimatologySource.from_dict(entry))
            except Exception as exc:
                self.logger.error(f"Invalid climatology source configuration: {exc}")

        if not sources:
            self.logger.warning("No climatology sources configured")
            return []

        output_dir = data_dir / "climatology"
        output_dir.mkdir(exist_ok=True)

        metadata: List[Dict[str, Any]] = []
        await self.ensure_http_client()

        for source in sources:
            result = await self.http_client.download(source.url, save_to_disk=False)
            if not result.success or result.content is None:
                metadata.append(
                    self.create_metadata(
                        name=source.source_id,
                        description=f"Failed to fetch climatology resource {source.source_id}",
                        data_type="unknown",
                        source_url=source.url,
                        error=result.error or "download_failed",
                        status_code=result.status_code
                    )
                )
                continue

            try:
                entry_metadata = await self._persist_payload(output_dir, source, result.content)
                metadata.append(entry_metadata)
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.error(f"Error processing climatology source {source.source_id}: {exc}")
                metadata.append(
                    self.create_metadata(
                        name=source.source_id,
                        description="Failed to persist climatology payload",
                        data_type="unknown",
                        source_url=source.url,
                        error=str(exc)
                    )
                )

        return metadata

    async def _persist_payload(
        self,
        output_dir: Path,
        source: ClimatologySource,
        content: bytes
    ) -> Dict[str, Any]:
        """Persist fetched climatology payload according to format."""

        text = content.decode('utf-8', errors='ignore')
        file_path = output_dir / source.filename()
        summary: Dict[str, Any] = {}

        if source.format == 'json':
            data = json.loads(text)
            with open(file_path, 'w') as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            summary['record_count'] = len(data) if isinstance(data, list) else len(data.keys()) if isinstance(data, dict) else 0
            data_type = 'json'

        elif source.format == 'csv':
            with open(file_path, 'w') as fh:
                fh.write(text)
            summary['line_count'] = text.count('\n') + 1
            data_type = 'csv'

        elif source.format == 'html':
            with open(file_path, 'w') as fh:
                fh.write(text)
            summary['character_count'] = len(text)
            data_type = 'html'

        else:
            with open(file_path, 'w') as fh:
                fh.write(text)
            summary['line_count'] = text.count('\n') + 1
            data_type = 'text'

        metadata = self.create_metadata(
            name=file_path.name,
            description=source.description or f"Climatology reference {source.source_id}",
            data_type=data_type,
            source_url=source.url,
            file_path=str(file_path),
            size_bytes=file_path.stat().st_size,
            source_id=source.source_id,
            format=source.format
        )
        metadata.update(summary)
        return metadata


__all__ = ["ClimatologyAgent", "ClimatologySource"]
