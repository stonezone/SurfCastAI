"""Nearshore buoy agent for CDIP/PacIOOS directional spectra and wave stats."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


@dataclass
class NearshoreSource:
    """Configuration descriptor for a single nearshore buoy source."""

    station_id: str
    url: str
    format: str = "json"
    description: Optional[str] = None
    ndbc_fallback: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "NearshoreSource":
        if not isinstance(raw, dict):  # pragma: no cover - defensive guard
            raise ValueError("Nearshore source entries must be dictionaries")

        station_id = str(raw.get("id") or raw.get("station") or "unknown").strip()
        url = str(raw.get("url", "")).strip()
        fmt = str(raw.get("format", "json")).strip().lower()
        description = raw.get("description")
        ndbc_fallback = raw.get("ndbc_fallback")

        if not station_id:
            raise ValueError("Nearshore source missing 'id'")
        if not url:
            raise ValueError(f"Nearshore source '{station_id}' missing 'url'")

        return cls(
            station_id=station_id,
            url=url,
            format=fmt,
            description=description,
            ndbc_fallback=ndbc_fallback
        )


class CDIPAgent(BaseAgent):
    """Collect nearshore buoy data (CDIP THREDDS netCDF + NDBC fallback) for shoreline translation."""

    SUPPORTED_FORMATS = {"json", "cdip_json", "cdip_netcdf", "csv", "text", "ndbc_text"}

    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        """Fetch configured nearshore buoy feeds (netCDF primary, NDBC text fallback)."""

        config = self.config.get("data_sources", "nearshore_buoys", {})
        sources_cfg = []
        if isinstance(config, dict):
            sources_cfg = config.get("sources", [])

        sources: List[NearshoreSource] = []
        for entry in sources_cfg:
            try:
                sources.append(NearshoreSource.from_dict(entry))
            except Exception as exc:
                self.logger.error(f"Invalid nearshore source configuration: {exc}")

        if not sources:
            self.logger.warning("No nearshore buoy sources configured")
            return []

        await self.ensure_http_client()

        output_dir = data_dir / "nearshore_buoys"
        output_dir.mkdir(exist_ok=True)

        metadata: List[Dict[str, Any]] = []

        for source in sources:
            if source.format not in self.SUPPORTED_FORMATS:
                metadata.append(
                    self.create_metadata(
                        name=source.station_id,
                        description=f"Unsupported format '{source.format}' for nearshore source",
                        data_type="unknown",
                        source_url=source.url,
                        error="unsupported_format"
                    )
                )
                continue

            # Try primary URL first
            result_meta = await self._fetch_and_parse(source, output_dir, primary=True)
            
            # If primary failed and we have a fallback, try it
            if result_meta.get("error") and hasattr(source, "ndbc_fallback") and source.ndbc_fallback:
                self.logger.warning(f"Primary source failed for {source.station_id}, trying NDBC fallback")
                fallback_source = NearshoreSource(
                    station_id=source.station_id,
                    url=source.ndbc_fallback,
                    format="ndbc_text",
                    description=f"{source.description} (NDBC fallback)"
                )
                result_meta = await self._fetch_and_parse(fallback_source, output_dir, primary=False)
            
            metadata.append(result_meta)

        return metadata

    async def _fetch_and_parse(
        self, source: NearshoreSource, output_dir: Path, primary: bool
    ) -> Dict[str, Any]:
        """Fetch and parse a single nearshore source, returning metadata."""
        
        result = await self.http_client.download(source.url, save_to_disk=False)
        if not result.success or result.content is None:
            return self.create_metadata(
                name=source.station_id,
                description=f"Failed to fetch nearshore buoy {source.station_id}",
                data_type="unknown",
                source_url=source.url,
                error=result.error or "download_failed",
                status_code=result.status_code,
                fallback_used=not primary
            )

        try:
            parsed, data_type = self._parse_content(result.content, source, output_dir)
            file_path = output_dir / f"{source.station_id}.{data_type}"

            if data_type == "json":
                with open(file_path, "w") as fh:
                    json.dump(parsed, fh, ensure_ascii=False, indent=2)
            elif data_type in {"csv", "txt"}:
                with open(file_path, "w") as fh:
                    fh.write(parsed)
            else:
                # For netCDF, file is already written
                pass

            enriched_metadata = self._build_success_metadata(
                file_path=file_path,
                source=source,
                data_type=data_type,
                source_url=source.url,
                content_type=result.content_type,
                parsed_payload=parsed,
                fallback_used=not primary
            )
            return enriched_metadata

        except Exception as exc:
            self.logger.error(f"Error processing nearshore source {source.station_id}: {exc}", exc_info=True)
            return self.create_metadata(
                name=source.station_id,
                description=f"Failed to parse nearshore buoy content: {exc}",
                data_type="unknown",
                source_url=source.url,
                error=str(exc),
                fallback_used=not primary
            )

    def _parse_content(
        self, content: bytes, source: NearshoreSource, output_dir: Path
    ) -> tuple[Any, str]:
        """Parse content based on source format (netCDF, JSON, NDBC text, CSV)."""
        
        if source.format == "cdip_netcdf":
            return self._parse_netcdf(content, source, output_dir)
        
        if source.format == "ndbc_text":
            return self._parse_ndbc_text(content, source)
        
        text = content.decode("utf-8", errors="ignore")

        if source.format in {"json", "cdip_json"}:
            payload = json.loads(text)
            if source.format == "cdip_json":
                payload = self._normalise_cdip(payload)
            return payload, "json"

        if source.format == "csv":
            return text, "csv"

        return text, "txt"

    def _parse_netcdf(
        self, content: bytes, source: NearshoreSource, output_dir: Path
    ) -> tuple[Dict[str, Any], str]:
        """Parse CDIP THREDDS netCDF file using xarray."""
        try:
            import xarray as xr
            import tempfile
            
            # Write to temp file for xarray to open
            with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                ds = xr.open_dataset(tmp_path)
                
                # Extract wave parameters (CDIP convention)
                parsed = {
                    "source_format": "cdip_netcdf",
                    "station": {
                        "id": source.station_id,
                        "name": ds.attrs.get("station_name", source.station_id),
                        "lat": float(ds.attrs.get("latitude", 0)) if "latitude" in ds.attrs else None,
                        "lon": float(ds.attrs.get("longitude", 0)) if "longitude" in ds.attrs else None,
                    }
                }
                
                # Extract latest wave summary
                if "waveHs" in ds.variables:
                    hs_vals = ds["waveHs"].values
                    parsed["wave_summary"] = {
                        "significant_height": float(hs_vals[-1]) if len(hs_vals) > 0 else None,
                    }
                elif "Hs" in ds.variables:
                    hs_vals = ds["Hs"].values
                    parsed["wave_summary"] = {
                        "significant_height": float(hs_vals[-1]) if len(hs_vals) > 0 else None,
                    }
                
                if parsed.get("wave_summary") and "waveTp" in ds.variables:
                    tp_vals = ds["waveTp"].values
                    parsed["wave_summary"]["peak_period"] = float(tp_vals[-1]) if len(tp_vals) > 0 else None
                elif parsed.get("wave_summary") and "Tp" in ds.variables:
                    tp_vals = ds["Tp"].values
                    parsed["wave_summary"]["peak_period"] = float(tp_vals[-1]) if len(tp_vals) > 0 else None
                
                if parsed.get("wave_summary") and "waveDp" in ds.variables:
                    dp_vals = ds["waveDp"].values
                    parsed["wave_summary"]["peak_direction"] = float(dp_vals[-1]) if len(dp_vals) > 0 else None
                elif parsed.get("wave_summary") and "Dp" in ds.variables:
                    dp_vals = ds["Dp"].values
                    parsed["wave_summary"]["peak_direction"] = float(dp_vals[-1]) if len(dp_vals) > 0 else None
                
                # Extract time
                if "waveTime" in ds.variables:
                    time_vals = ds["waveTime"].values
                    if len(time_vals) > 0:
                        parsed["wave_summary"]["timestamp"] = str(time_vals[-1])
                elif "time" in ds.variables:
                    time_vals = ds["time"].values
                    if len(time_vals) > 0:
                        parsed["wave_summary"]["timestamp"] = str(time_vals[-1])
                
                # Extract spectral data if available
                if "waveFrequency" in ds.variables:
                    freqs = ds["waveFrequency"].values.tolist()
                    parsed["spectra"] = {"frequencies": freqs}
                    
                    if "waveEnergyDensity" in ds.variables:
                        energy = ds["waveEnergyDensity"].values
                        if len(energy.shape) > 1:
                            # Take latest time slice
                            parsed["spectra"]["energies"] = energy[-1].tolist()
                        else:
                            parsed["spectra"]["energies"] = energy.tolist()
                
                # Quality flags
                if "waveQuality" in ds.variables:
                    quality = ds["waveQuality"].values
                    parsed["quality_flags"] = {"quality": int(quality[-1]) if len(quality) > 0 else None}
                
                ds.close()
                
                # Copy netCDF to output directory
                final_path = output_dir / f"{source.station_id}.nc"
                import shutil
                shutil.copy(tmp_path, final_path)
                
                return parsed, "nc"
                
            finally:
                import os
                os.unlink(tmp_path)
                
        except ImportError:
            raise RuntimeError("xarray or netCDF4 not installed - required for cdip_netcdf format")
        except Exception as exc:
            raise RuntimeError(f"Failed to parse netCDF file: {exc}")

    def _parse_ndbc_text(self, content: bytes, source: NearshoreSource) -> tuple[Any, str]:
        """Parse NDBC standard meteorological text format as fallback."""
        text = content.decode("utf-8", errors="ignore")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if len(lines) < 3:
            raise ValueError("NDBC text format incomplete - less than 3 lines")
        
        # NDBC format: line 0 = header comments, line 1 = column headers, line 2 = units, line 3+ = data
        # Example columns: #YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS TIDE
        
        header_line = None
        data_lines = []
        
        for line in lines:
            if line.startswith("#"):
                if "YY" in line or "WDIR" in line:
                    header_line = line.lstrip("#").strip()
            elif not line.startswith("MM") and header_line:
                # Skip units line
                if all(c in "mtsfhdegC-/" for c in line.replace(" ", "").replace(".", "")):
                    continue
                data_lines.append(line)
        
        if not header_line or not data_lines:
            raise ValueError("Could not parse NDBC text format - no valid data found")
        
        headers = header_line.split()
        latest_data = data_lines[0].split()
        
        if len(latest_data) < len(headers):
            raise ValueError(f"NDBC data row has {len(latest_data)} fields but header has {len(headers)}")
        
        # Build dictionary
        data_dict = dict(zip(headers, latest_data))
        
        parsed = {
            "source_format": "ndbc_text",
            "station": {
                "id": source.station_id,
                "name": source.station_id,
            },
            "wave_summary": {
                "significant_height": _safe_float(data_dict.get("WVHT")),
                "peak_period": _safe_float(data_dict.get("DPD")),  # Dominant period
                "peak_direction": _safe_float(data_dict.get("MWD")),  # Mean wave direction
                "timestamp": f"{data_dict.get('YY', '')}-{data_dict.get('MM', '')}-{data_dict.get('DD', '')} {data_dict.get('hh', '')}:{data_dict.get('mm', '')}:00Z"
            },
            "raw_data": data_dict,
            "raw_text": text
        }
        
        # Return parsed dict (will be written as JSON) with json extension
        return parsed, "json"

    def _normalise_cdip(self, payload: Any) -> Dict[str, Any]:
        """Extract a compact summary from CDIP JSON payloads."""
        if not isinstance(payload, dict):
            return {"raw": payload}

        summary: Dict[str, Any] = {"raw": payload}

        station_info = payload.get("station")
        if isinstance(station_info, dict):
            summary["station"] = {
                "id": station_info.get("id") or station_info.get("station_id"),
                "name": station_info.get("name"),
                "lat": station_info.get("latitude"),
                "lon": station_info.get("longitude"),
            }

        spectra = payload.get("spectra") or payload.get("data")
        if isinstance(spectra, dict):
            frequencies = spectra.get("frequencies") or spectra.get("frequency")
            energies = spectra.get("energy") or spectra.get("densities")
            summary["spectra"] = {
                "frequencies": frequencies,
                "energies": energies,
            }

        waves = payload.get("wave") or payload.get("waves")
        if isinstance(waves, dict):
            summary["wave_summary"] = {
                "significant_height": waves.get("Hs") or waves.get("significant_wave_height"),
                "peak_period": waves.get("Tp") or waves.get("peak_period"),
                "peak_direction": waves.get("Dp") or waves.get("peak_direction"),
                "timestamp": waves.get("time") or waves.get("timestamp"),
            }

        return summary

    def _build_success_metadata(
        self,
        *,
        file_path: Path,
        source: NearshoreSource,
        data_type: str,
        source_url: str,
        content_type: Optional[str],
        parsed_payload: Any,
        fallback_used: bool = False,
    ) -> Dict[str, Any]:
        """Compose success metadata with enriched CDIP/NDBC attributes."""

        metadata = self.create_metadata(
            name=file_path.name,
            description=source.description or f"Nearshore spectra for {source.station_id}",
            data_type=data_type,
            source_url=source_url,
            file_path=str(file_path),
            size_bytes=file_path.stat().st_size,
            station_id=source.station_id,
            content_type=content_type,
            retrieved_format=source.format,
            fallback_used=fallback_used,
        )

        if isinstance(parsed_payload, dict):
            metadata["source_format"] = parsed_payload.get("source_format", source.format)
            
            station = parsed_payload.get("station")
            if isinstance(station, dict):
                metadata['station_name'] = station.get('name')
                metadata['station_lat'] = station.get('lat')
                metadata['station_lon'] = station.get('lon')

            wave_summary = parsed_payload.get("wave_summary")
            if isinstance(wave_summary, dict):
                metadata['significant_height_m'] = _safe_float(wave_summary.get('significant_height'))
                metadata['peak_period_s'] = _safe_float(wave_summary.get('peak_period'))
                metadata['peak_direction_deg'] = _safe_float(wave_summary.get('peak_direction'))
                metadata['observation_timestamp'] = wave_summary.get('timestamp')

            spectra = parsed_payload.get("spectra")
            if isinstance(spectra, dict):
                frequencies = spectra.get("frequencies")
                if isinstance(frequencies, list) and len(frequencies) > 1:
                    spacing = _frequency_spacing(frequencies)
                    if spacing is not None:
                        metadata['spectral_frequency_spacing'] = spacing
                if isinstance(frequencies, list):
                    metadata['spectral_bins'] = len(frequencies)

            raw_payload = parsed_payload.get("raw")
            if isinstance(raw_payload, dict):
                quality = raw_payload.get("wave", {}).get("quality")
                if quality is not None:
                    metadata['quality_flags'] = quality
                meta_section = raw_payload.get("meta")
                if isinstance(meta_section, dict):
                    metadata['raw_last_updated'] = meta_section.get("last_update") or meta_section.get("last_observation")
            
            # Handle quality from netCDF
            quality_flags = parsed_payload.get("quality_flags")
            if quality_flags:
                metadata['quality_flags'] = quality_flags

        return metadata


def _safe_float(value: Any) -> Optional[float]:
    """Convert values to float where possible."""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _frequency_spacing(frequencies: Any) -> Optional[float]:
    """Compute approximate spectral frequency spacing."""
    try:
        freqs = [float(f) for f in frequencies[:2]]  # type: ignore[index]
        if len(freqs) < 2:
            return None
        spacing = freqs[1] - freqs[0]
        return round(spacing, 4)
    except Exception:
        return None
