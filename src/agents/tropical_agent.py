"""Agent for Central Pacific tropical outlooks and advisories."""

from __future__ import annotations

import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .base_agent import BaseAgent
from ..core.config import Config


class TropicalAgent(BaseAgent):
    """Fetches NHC/NWS tropical outlook feeds relevant to Hawaii."""

    def __init__(self, config: Config):
        super().__init__(config)

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        urls = self.config.get_data_source_urls('tropical').get('tropical', [])
        if not urls:
            self.logger.info("No tropical URLs configured")
            return []

        await self.ensure_http_client()
        tasks = [self._process_url(url, data_dir) for url in urls]
        results: List[Dict[str, Any]] = []
        for future in asyncio.as_completed(tasks):
            results.append(await future)
        return results

    async def _process_url(self, url: str, data_dir: Path) -> Dict[str, Any]:
        response = await self.http_client.download(url)
        if not response.success:
            return self.create_metadata(
                name='tropical_outlook',
                description='Failed to download tropical outlook',
                data_type='xml',
                source_url=url,
                error=response.error
            )

        content = response.content.decode('utf-8', errors='ignore')
        outlook = self._parse_outlook(content)
        outlook['source_url'] = url
        outlook['fetched_at'] = datetime.now(timezone.utc).isoformat()

        output_path = data_dir / 'tropical_outlook.json'
        with open(output_path, 'w') as fh:
            json.dump(outlook, fh, indent=2)

        return self.create_metadata(
            name='tropical_outlook.json',
            description='Central Pacific tropical outlook summary',
            data_type='json',
            source_url=url,
            file_path=str(output_path),
            size_bytes=output_path.stat().st_size,
            headline=outlook.get('headline')
        )

    def _parse_outlook(self, xml_text: str) -> Dict[str, Any]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return {
                'headline': 'Unable to parse tropical outlook',
                'entries': [],
                'raw_text': xml_text
            }

        entries: List[Dict[str, Any]] = []
        headline = None

        # Many NOAA XML feeds use the Atom namespace
        for item in root.findall('.//{*}item'):
            title = item.findtext('{*}title')
            summary = item.findtext('{*}summary') or item.findtext('{*}description')
            link = item.findtext('{*}link')
            if not headline and title:
                headline = title
            entries.append({
                'title': title,
                'summary': summary,
                'link': link
            })

        if not entries:
            # Fall back to entire text content
            text = ''.join(root.itertext()).strip()
            entries.append({'title': 'Outlook', 'summary': text})
            headline = headline or 'Central Pacific Outlook'

        return {
            'headline': headline or 'Central Pacific Tropical Outlook',
            'entries': entries
        }
