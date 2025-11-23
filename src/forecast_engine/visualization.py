"""Utilities for rendering visual assets that accompany SurfCastAI forecasts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:  # matplotlib is optional during runtime but required for charts
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - handled gracefully at runtime
    plt = None


def degrees_to_cardinal(degrees):
    """Convert degrees to cardinal direction."""
    if degrees is None:
        return "?"
    dirs = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    ix = round(degrees / 22.5) % 16
    return dirs[ix]


class ForecastVisualizer:
    """Generate simple charts that highlight the swell mix for a forecast."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("forecast.visualizer")
        self.available = plt is not None
        if not self.available:
            self.logger.warning("Matplotlib not installed; skipping visualization generation")

    def generate_all(self, forecast_data: dict[str, Any], output_dir: Path) -> dict[str, str]:
        """Create all supported visualizations for a forecast."""
        if not self.available:
            return {}

        assets_dir = output_dir / "assets"
        assets_dir.mkdir(exist_ok=True)

        charts: dict[str, str] = {}
        swell_chart = self._build_swell_mix_chart(forecast_data, assets_dir)
        if swell_chart:
            charts["swell_mix"] = swell_chart

        shore_chart = self._build_shore_focus_chart(forecast_data, assets_dir)
        if shore_chart:
            charts["shore_focus"] = shore_chart

        return charts

    def _build_swell_mix_chart(self, forecast_data: dict[str, Any], assets_dir: Path) -> str | None:
        """Plot Hawaiian scale heights for each detected swell event."""
        try:
            events = forecast_data.get("swell_events", [])
            if not events:
                return None

            labels = []
            heights = []
            periods = []
            for event in events:
                height = event.get("hawaii_scale")
                if height is None:
                    continue

                # Extract direction from primary_direction (numeric degrees)
                direction_deg = event.get("primary_direction")
                direction = degrees_to_cardinal(direction_deg)

                # Extract period from primary_components
                period = None
                primary_components = event.get("primary_components", [])
                if primary_components and len(primary_components) > 0:
                    period = primary_components[0].get("period")

                # Build label with null check for period
                if period is not None:
                    labels.append(f"{direction}\n{period:.0f}s")
                else:
                    labels.append(f"{direction}\n?s")

                heights.append(height)
                periods.append(period)

            if not heights:
                return None

            fig, ax = plt.subplots(figsize=(8, 4.5))
            bars = ax.bar(range(len(heights)), heights, color="#0077b6")
            ax.set_title("Primary Swell Mix (Hawaiian Scale)")
            ax.set_ylabel("Height (ft)")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            ymax = max(heights) * 1.2
            ax.set_ylim(0, ymax or 1)
            ax.grid(axis="y", linestyle="--", alpha=0.4)

            for bar, period in zip(bars, periods, strict=False):
                if period is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.2,
                        f"{period:.0f}s",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

            fig.tight_layout()
            output_path = assets_dir / "swell_mix.png"
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return str(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate swell mix chart: {e}")
            return None

    def _build_shore_focus_chart(
        self, forecast_data: dict[str, Any], assets_dir: Path
    ) -> str | None:
        """Summarise expected face heights per shore based on event exposure."""
        try:
            # Support both formats: locations (list) and shore_data (dict)
            locations = forecast_data.get("locations", [])
            shore_data = forecast_data.get("shore_data", {})

            # Convert shore_data dict to locations list format if needed
            if not locations and shore_data:
                locations = list(shore_data.values())

            if not locations:
                return None

            shore_labels = []
            face_ranges = []
            for location in locations:
                if not isinstance(location, dict):
                    continue

                display = location.get("name", "Unknown Shore")
                events = location.get("swell_events", [])
                if not events:
                    continue

                # Calculate average height from swell events
                total_height = 0.0
                valid_events = 0
                for event in events:
                    height = event.get("hawaii_scale")
                    if height is not None:
                        total_height += height
                        valid_events += 1

                if valid_events == 0:
                    continue

                avg_height = total_height / valid_events
                # Convert Hawaiian scale to approximate face height range
                face_low = max(1, round(avg_height * 2))
                face_high = max(face_low + 1, round(avg_height * 3))
                shore_labels.append(display)
                face_ranges.append((face_low, face_high))

            if not shore_labels:
                return None

            lows = [low for low, _ in face_ranges]
            highs = [high for _, high in face_ranges]

            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.bar(shore_labels, highs, color="#00b4d8", alpha=0.7, label="Upper range")
            ax.bar(shore_labels, lows, color="#03045e", alpha=0.9, label="Lower range")
            ax.set_ylabel("Face Height (ft)")
            ax.set_title("Projected Face Heights by Shore")
            ax.legend()
            ax.grid(axis="y", linestyle="--", alpha=0.3)
            fig.tight_layout()

            output_path = assets_dir / "shore_faces.png"
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            return str(output_path)
        except Exception as e:
            self.logger.error(f"Failed to generate shore focus chart: {e}")
            return None


__all__ = ["ForecastVisualizer"]
