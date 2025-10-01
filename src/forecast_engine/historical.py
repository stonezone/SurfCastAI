"""Helpers for comparing the current forecast to the most recent archived run."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class HistoricalComparator:
    """Loads the previous forecast artifact and calculates headline changes."""

    def __init__(self, output_root: Path, logger: Optional[logging.Logger] = None) -> None:
        self.output_root = output_root
        self.logger = logger or logging.getLogger("forecast.history")

    def build_summary(self, current_id: str, current_dir: Path, current_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a historical comparison summary if an earlier forecast exists."""
        previous = self._load_previous_forecast(current_id, current_dir)
        if not previous:
            return None

        prev_data, prev_path = previous
        summary: Dict[str, Any] = {
            "previous_id": prev_data.get("forecast_id"),
            "previous_generated": prev_data.get("generated_time"),
        }

        summary["confidence_change"] = self._delta(
            current_data.get("metadata", {}).get("confidence", {}).get("overall_score"),
            prev_data.get("metadata", {}).get("confidence", {}).get("overall_score"),
        )

        summary["hawaiian_avg_change"] = self._delta(
            self._average_height(current_data),
            self._average_height(prev_data),
        )

        summary["dominant_shift"] = self._dominant_shift(current_data, prev_data)
        summary["summary_lines"] = self._build_summary_lines(summary)
        summary["source_path"] = str(prev_path)
        return summary

    def _load_previous_forecast(self, current_id: str, current_dir: Path) -> Optional[tuple[Dict[str, Any], Path]]:
        candidates = []
        for item in self.output_root.iterdir():
            if not item.is_dir() or item.name == current_id or item == current_dir:
                continue
            data_path = item / "forecast_data.json"
            if data_path.exists():
                candidates.append(data_path)

        if not candidates:
            return None

        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        latest = candidates[0]
        try:
            with open(latest, "r") as fh:
                payload = json.load(fh)
        except Exception as exc:  # pragma: no cover - best effort only
            self.logger.warning("Failed to load historical forecast %s: %s", latest, exc)
            return None
        return payload, latest

    @staticmethod
    def _average_height(payload: Dict[str, Any]) -> Optional[float]:
        events = payload.get("swell_events", [])
        heights = [event.get("hawaii_scale") for event in events if event.get("hawaii_scale") is not None]
        if not heights:
            return None
        return sum(heights) / len(heights)

    @staticmethod
    def _delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
        if current is None or previous is None:
            return None
        return round(current - previous, 2)

    @staticmethod
    def _dominant_shift(current: Dict[str, Any], previous: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current_events = current.get("swell_events", [])
        previous_events = previous.get("swell_events", [])
        if not current_events or not previous_events:
            return None

        top_current = max(current_events, key=lambda e: e.get("hawaii_scale", 0.0))
        top_previous = max(previous_events, key=lambda e: e.get("hawaii_scale", 0.0))
        return {
            "current_direction": top_current.get("primary_direction_cardinal"),
            "current_height": top_current.get("hawaii_scale"),
            "previous_direction": top_previous.get("primary_direction_cardinal"),
            "previous_height": top_previous.get("hawaii_scale"),
        }

    def _build_summary_lines(self, summary: Dict[str, Any]) -> list[str]:
        lines = []
        conf_delta = summary.get("confidence_change")
        if conf_delta is not None:
            direction = "up" if conf_delta >= 0 else "down"
            lines.append(f"Confidence {direction} {abs(conf_delta):.2f} since the previous run.")

        height_delta = summary.get("hawaiian_avg_change")
        if height_delta is not None:
            direction = "higher" if height_delta >= 0 else "lower"
            lines.append(f"Average Hawaiian scale is {abs(height_delta):.2f} ft {direction} overall.")

        dominant = summary.get("dominant_shift")
        if dominant:
            lines.append(
                "Primary swell shifted from {prev_dir} ({prev_ht:.1f}ft) to {cur_dir} ({cur_ht:.1f}ft).".format(
                    prev_dir=dominant.get("previous_direction"),
                    prev_ht=dominant.get("previous_height", 0.0),
                    cur_dir=dominant.get("current_direction"),
                    cur_ht=dominant.get("current_height", 0.0),
                )
            )
        return lines


__all__ = ["HistoricalComparator"]
