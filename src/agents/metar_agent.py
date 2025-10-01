"""METAR agent for collecting near-real-time aviation observations."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .base_agent import BaseAgent
from ..core.config import Config


class MetarAgent(BaseAgent):
    """Fetch and normalize METAR bulletins for key Oahu stations."""

    METAR_PATTERN = re.compile(r"^(?P<station>[A-Z0-9]{4})\s+(?P<time>\d{6}Z)\s+(?P<body>.*)$")

    def __init__(self, config: Config):
        super().__init__(config)

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        urls = self.config.get_data_source_urls('metar').get('metar', [])
        if not urls:
            self.logger.warning("No METAR URLs configured")
            return []

        await self.ensure_http_client()
        results: List[Dict[str, Any]] = []

        tasks = [self._process_url(url, data_dir) for url in urls]
        for future in asyncio.as_completed(tasks):
            results.append(await future)

        return results

    async def _process_url(self, url: str, data_dir: Path) -> Dict[str, Any]:
        try:
            filename = url.split('/')[-1]
            station_id = filename.split('.')[0].upper()

            response = await self.http_client.download(url)
            if not response.success:
                return self.create_metadata(
                    name=f"metar_{station_id}",
                    description=f"Failed to download METAR for {station_id}",
                    data_type='text',
                    source_url=url,
                    error=response.error
                )

            content = response.content.decode('utf-8', errors='ignore')
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if not lines:
                return self.create_metadata(
                    name=f"metar_{station_id}",
                    description=f"Empty METAR file for {station_id}",
                    data_type='text',
                    source_url=url,
                    error='empty file'
                )

            metar_raw = lines[-1]
            parsed = self._parse_metar(metar_raw, station_id)
            parsed['raw_lines'] = lines
            parsed['source_url'] = url

            output_path = data_dir / f"metar_{station_id}.json"
            with open(output_path, 'w') as fh:
                json.dump(parsed, fh, indent=2)

            size_bytes = output_path.stat().st_size
            return self.create_metadata(
                name=f"metar_{station_id}.json",
                description=f"Normalized METAR observation for {station_id}",
                data_type='json',
                source_url=url,
                file_path=str(output_path),
                size_bytes=size_bytes,
                station=station_id,
                issued=parsed.get('issued')
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Error processing METAR {url}: {exc}")
            return self.create_metadata(
                name='metar_unknown',
                description='Failed to process METAR',
                data_type='text',
                source_url=url,
                error=str(exc)
            )

    def _parse_metar(self, metar: str, fallback_station: str) -> Dict[str, Any]:
        match = self.METAR_PATTERN.match(metar)
        if not match:
            return {
                'station': fallback_station,
                'metar': metar,
                'issued': datetime.now(timezone.utc).isoformat()
            }

        station = match.group('station')
        time_token = match.group('time')  # DDHHMMZ
        body = match.group('body')

        issued = self._decode_time_token(time_token)
        components = body.split()

        summary: Dict[str, Any] = {
            'station': station,
            'metar': metar,
            'issued': issued.isoformat().replace('+00:00', 'Z'),
        }

        for token in components:
            if token.endswith('KT') and token[0].isdigit():
                wind = self._parse_wind(token)
                summary['wind_direction_deg'] = wind.get('direction')
                summary['wind_speed_kt'] = wind.get('speed_kt')
                summary['wind_speed_ms'] = wind.get('speed_ms')
                if wind.get('gust_kt') is not None:
                    summary['wind_gust_kt'] = wind['gust_kt']
                    summary['wind_gust_ms'] = wind['gust_ms']
            elif token.endswith('SM') and token[:-2].replace('/', '').replace('.', '').isdigit():
                summary['visibility_sm'] = self._safe_float(token[:-2])
            elif token.count('/') == 1 and token.endswith(('C', 'M')) is False:
                temps = self._parse_temperatures(token)
                if temps:
                    summary.update(temps)
            elif token.startswith('A') and len(token) == 5 and token[1:].isdigit():
                pressure = int(token[1:]) / 100.0  # inches of mercury
                summary['pressure_inhg'] = round(pressure, 2)
                summary['pressure_hpa'] = round(pressure * 33.8639, 1)

        return summary

    def _decode_time_token(self, token: str) -> datetime:
        day = int(token[:2])
        hour = int(token[2:4])
        minute = int(token[4:6])
        now = datetime.now(timezone.utc)
        year = now.year
        month = now.month
        candidate = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        # Adjust month rollovers (e.g., METAR on last day of previous month)
        if candidate - now > timedelta(days=15):
            # Assume previous month
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            candidate = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        elif now - candidate > timedelta(days=16):
            month += 1
            if month == 13:
                month = 1
                year += 1
            candidate = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        return candidate

    def _parse_wind(self, token: str) -> Dict[str, Any]:
        match = re.match(r"(?P<dir>\d{3}|VRB)(?P<spd>\d{2,3})(?:G(?P<gust>\d{2,3}))?KT", token)
        if not match:
            return {}
        direction = None if match.group('dir') == 'VRB' else int(match.group('dir'))
        speed_kt = int(match.group('spd'))
        gust_kt = int(match.group('gust')) if match.group('gust') else None
        speed_ms = round(speed_kt * 0.514444, 2)
        gust_ms = round(gust_kt * 0.514444, 2) if gust_kt is not None else None
        return {
            'direction': direction,
            'speed_kt': speed_kt,
            'speed_ms': speed_ms,
            'gust_kt': gust_kt,
            'gust_ms': gust_ms,
        }

    def _parse_temperatures(self, token: str) -> Optional[Dict[str, Any]]:
        if '/' not in token:
            return None
        air, dew = token.split('/')
        air_c = self._decode_temperature(air)
        dew_c = self._decode_temperature(dew)
        if air_c is None and dew_c is None:
            return None
        result: Dict[str, Any] = {}
        if air_c is not None:
            result['temperature_c'] = air_c
        if dew_c is not None:
            result['dewpoint_c'] = dew_c
        return result

    def _decode_temperature(self, value: str) -> Optional[float]:
        if not value or value == '///':
            return None
        negative = value.startswith('M')
        digits = value[1:] if negative else value
        if not digits.isdigit():
            return None
        temp = int(digits)
        if negative:
            temp *= -1
        return float(temp)

    def _safe_float(self, value: str) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
