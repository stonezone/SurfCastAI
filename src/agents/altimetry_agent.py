"""Altimetry agent downloads sea-surface height products for verification."""

from __future__ import annotations

import gzip
import shutil
import zipfile
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class AltimetryAgent(BaseAgent):
    """Fetch satellite altimetry quick-look products and summaries."""

    ARCHIVE_SUFFIXES = {".zip"}
    COMPRESSED_SUFFIXES = {".gz"}

    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        data_dir.mkdir(exist_ok=True)
        urls = self.config.get_data_source_urls("altimetry").get("altimetry", [])
        if not urls:
            self.logger.warning("No altimetry URLs configured")
            return []

        metadata: list[dict[str, Any]] = []
        await self.ensure_http_client()

        # Try each URL in order (primary and fallback for ERDDAP endpoints)
        success = False
        for idx, url in enumerate(urls):
            # Detect if this is an ERDDAP graph endpoint (returns PNG directly)
            is_erddap_graph = "erddap/griddap" in url and ".graph?" in url

            if is_erddap_graph:
                # Extract descriptive source name from URL
                if "upwell.pfeg.noaa.gov" in url:
                    source = "ERDDAP_Upwell"
                elif "polarwatch.noaa.gov" in url:
                    source = "ERDDAP_PolarWatch"
                else:
                    source = "ERDDAP_Unknown"

                filename = f"ssh_hawaii_{source}.png"
                description = f"Sea Surface Height (SSH) from {source}"
            else:
                # Legacy format (NetCDF, ZIP archives, etc.)
                filename = url.split("/")[-1] or "altimetry.dat"
                description = f"Altimetry product {filename}"
                source = None

            result = await self.download_file(
                url, filename=filename, data_dir=data_dir, description=description
            )

            if result.get("status") == "success":
                file_path = Path(result.get("file_path", ""))
                if file_path.exists():
                    if is_erddap_graph:
                        # ERDDAP graph endpoints return PNG directly - no extraction needed
                        result["type"] = "png_image"
                        result["size_bytes"] = file_path.stat().st_size
                        result["source"] = source
                        result["data_product"] = "nesdisSSH1day"
                        result["region"] = "Hawaiian Islands (15-30N, 165-150W)"
                        result["variable"] = "Sea Level Anomaly (sla)"
                        success = True
                        self.logger.info(f"Successfully downloaded SSH from {source}")
                        metadata.append(result)
                        break  # Success - no need to try fallback
                    else:
                        # Legacy format - apply postprocessing
                        post_process = self._postprocess_file(file_path, data_dir)
                        if post_process:
                            result.update(post_process)
                            if "type" in post_process:
                                result["type"] = post_process["type"]
                        result["size_bytes"] = file_path.stat().st_size
                        metadata.append(result)
                        success = True
                else:
                    if source:
                        result["source"] = source
                    metadata.append(result)
            else:
                if source:
                    result["source"] = source
                metadata.append(result)
                if is_erddap_graph:
                    self.logger.warning(
                        f"Failed to download from {source}, trying fallback if available"
                    )

        if not success and urls:
            self.logger.error("All altimetry URLs failed")

        return metadata

    def _postprocess_file(self, file_path: Path, data_dir: Path) -> dict[str, Any]:
        """Handle archives and compressed altimetry formats."""
        metadata: dict[str, Any] = {}
        suffixes = [suffix.lower() for suffix in file_path.suffixes]

        if not suffixes:
            return metadata

        # Handle ZIP archives containing imagery/NetCDF assets
        if file_path.suffix.lower() in self.ARCHIVE_SUFFIXES and zipfile.is_zipfile(file_path):
            extract_dir = data_dir / file_path.stem
            extract_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(file_path) as archive:
                archive.extractall(extract_dir)
                metadata["extracted_files"] = sorted(archive.namelist())
            metadata["extracted_dir"] = str(extract_dir)
            metadata["type"] = "archive"
            return metadata

        # Handle gzip-compressed NetCDF quick looks (e.g., *.nc.gz)
        if file_path.suffix.lower() in self.COMPRESSED_SUFFIXES:
            target_path = file_path.with_suffix("")
            with gzip.open(file_path, "rb") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            metadata["extracted_file"] = str(target_path)
            metadata["type"] = "netcdf" if target_path.suffix.lower() == ".nc" else "binary"
            metadata.update(self._summarise_netcdf(target_path))
            return metadata

        # Raw NetCDF output
        if file_path.suffix.lower() == ".nc":
            metadata["type"] = "netcdf"
            metadata.update(self._summarise_netcdf(file_path))

        return metadata

    def _summarise_netcdf(self, file_path: Path) -> dict[str, Any]:
        """Extract lightweight summary info from NetCDF when possible."""
        summary: dict[str, Any] = {}
        if not file_path.exists():
            return summary

        try:
            from netCDF4 import Dataset  # type: ignore

            with Dataset(file_path, mode="r") as dataset:
                summary["netcdf_dimensions"] = {
                    name: len(dim) for name, dim in dataset.dimensions.items()
                }
                summary["netcdf_variables"] = list(dataset.variables.keys())
                attrs: dict[str, Any] = {}
                for attr in ("title", "institution", "source", "references", "history"):
                    if hasattr(dataset, attr):
                        attrs[attr] = getattr(dataset, attr)
                if attrs:
                    summary["netcdf_attributes"] = attrs
        except ImportError:
            summary["netcdf_summary"] = "netCDF4 not installed"
        except Exception as exc:  # pragma: no cover - defensive
            summary["netcdf_summary_error"] = str(exc)

        return summary
