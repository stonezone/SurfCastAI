"""Tide agent for NOAA tides and currents endpoints."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import parse_qs, urlparse

from .base_agent import BaseAgent
from ..core.config import Config


class TideAgent(BaseAgent):
    """Collect observed water levels and tide predictions."""

    def __init__(self, config: Config):
        super().__init__(config)

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        urls = self.config.get_data_source_urls('tides').get('tides', [])
        if not urls:
            self.logger.warning("No tide URLs configured")
            return []

        await self.ensure_http_client()
        tasks = [self._process_url(url, data_dir) for url in urls]
        results: List[Dict[str, Any]] = []
        for future in asyncio.as_completed(tasks):
            results.append(await future)
        return results

    async def _process_url(self, url: str, data_dir: Path) -> Dict[str, Any]:
        params = parse_qs(urlparse(url).query)
        station = params.get('station', ['unknown'])[0]
        product = params.get('product', ['unknown'])[0]

        response = await self.http_client.download(url)
        if not response.success:
            return self.create_metadata(
                name=f"tide_{station}_{product}",
                description=f"Failed to download tide data ({product}) for station {station}",
                data_type='csv',
                source_url=url,
                error=response.error
            )

        content = response.content.decode('utf-8', errors='ignore')
        records = self._parse_csv(content)
        payload = {
            'station': station,
            'product': product,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'units': params.get('units', ['metric'])[0],
            'time_zone': params.get('time_zone', ['UTC'])[0],
            'records': records,
            'source_url': url
        }

        output_path = data_dir / f"tide_{station}_{product}.json"
        with open(output_path, 'w') as fh:
            json.dump(payload, fh, indent=2)

        return self.create_metadata(
            name=output_path.name,
            description=f"NOAA tides product {product} for station {station}",
            data_type='json',
            source_url=url,
            file_path=str(output_path),
            size_bytes=output_path.stat().st_size,
            station=station,
            product=product
        )

    def _parse_csv(self, text: str) -> List[Dict[str, Any]]:
        # NOAA CSV files often start with comment lines prefixed by #
        clean_lines = [line for line in text.splitlines() if line and not line.startswith('#')]
        if not clean_lines:
            return []
        reader = csv.DictReader(clean_lines)
        rows: List[Dict[str, Any]] = []
        for row in reader:
            parsed = {k.strip(): v.strip() for k, v in row.items() if k is not None}
            rows.append(parsed)
        return rows
