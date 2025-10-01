"""Chart agent to download marine analysis imagery."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any
import json

from .base_agent import BaseAgent
from ..core.config import Config


class ChartAgent(BaseAgent):
    """Download static analysis/forecast charts for supplementary context."""

    def __init__(self, config: Config):
        super().__init__(config)

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        urls = self.config.get_data_source_urls('charts').get('charts', [])
        if not urls:
            self.logger.warning("No chart URLs configured")
            return []

        metadata: List[Dict[str, Any]] = []
        await self.ensure_http_client()

        for url in urls:
            filename = url.split('/')[-1] or 'chart.png'
            result = await self.download_file(
                url,
                filename=filename,
                data_dir=data_dir,
                description=f"Marine analysis chart {filename}"
            )
            if result.get('status') == 'success':
                result['chart_type'] = filename
                file_path = Path(result.get('file_path', ''))
                if file_path.exists():
                    manifest = {
                        'chart_type': filename,
                        'file_path': str(file_path),
                        'source_url': url
                    }
                    manifest_path = data_dir / f"{filename}.json"
                    with open(manifest_path, 'w') as fh:
                        json.dump(manifest, fh, indent=2)
                    result['manifest_path'] = str(manifest_path)
                    result['size_bytes'] = file_path.stat().st_size
            metadata.append(result)
        return metadata
