"""Local, rule-based fallback generator for producing surf forecasts without OpenAI.

This module offers deterministic text generation that leverages the processed
forecast data to craft readable forecasts. It is intentionally conservative and
focused on surf-relevant details so automated tests and CLI workflows can run in
offline or air-gapped environments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover - fallback for platforms without zoneinfo
    ZoneInfo = None  # type: ignore


class LocalForecastGenerator:
    """Compose deterministic surf forecast text from structured swell data."""

    def __init__(self, forecast_data: Dict[str, Any]):
        self.data = forecast_data
        self.weather = forecast_data.get("metadata", {}).get("weather", {})
        self.tides = forecast_data.get("metadata", {}).get("tides", {})
        self.seasonal = forecast_data.get("seasonal_context", {})
        self.confidence = forecast_data.get("confidence", {}).get("overall_score", 0.7)
        self.shore_data = forecast_data.get("shore_data", {})
        self.events = forecast_data.get("swell_events", [])
        self.event_index = {event.get("event_id"): event for event in self.events}
        self.event_exposures = self._map_event_exposures()

    # ------------------------------------------------------------------
    # Public builders
    # ------------------------------------------------------------------
    def build_main_forecast(self) -> str:
        summary = self._build_summary_text()
        details = self._build_detail_lines()
        north_snapshot = self._shore_snapshot("north_shore")
        south_snapshot = self._shore_snapshot("south_shore")
        outlook = self._build_outlook_text()

        sections = [
            "SUMMARY:",
            summary,
            "",
            "DETAILS:",
            details,
            "",
            "NORTH SHORE SNAPSHOT:",
            north_snapshot,
            "",
            "SOUTH SHORE SNAPSHOT:",
            south_snapshot,
            "",
            "OUTLOOK:",
            outlook,
        ]

        # Remove trailing empty lines while keeping structure readable
        return "\n".join(part for part in sections if part is not None)

    def build_shore_forecast(self, shore_key: str) -> str:
        shore_info = self.shore_data.get(shore_key)
        if not shore_info:
            friendly_name = shore_key.replace("_", " ").title()
            return f"No {friendly_name} data available for this run."

        shore_name = shore_info.get("name", shore_key.replace("_", " ").title())
        activity = self._shore_activity(shore_key)
        if not activity:
            return (
                f"{shore_name} stays near-flat with only trace wrap; monitor background pulses "
                "but expect knee-high surf at best."
            )

        lead = activity[0]
        secondary = activity[1:] if len(activity) > 1 else []

        wind_line = self._wind_sentence_for_shore(shore_key)
        summary = (
            f"{shore_name} leans on a {lead['direction']} swell delivering {lead['faces']} faces "
            f"and {lead['hawaiian']} Hawaiian scale surf through {lead['peak_phrase']}."
        )

        secondary_lines = []
        for item in secondary:
            secondary_lines.append(
                f"Secondary energy from {item['direction']} holds {item['faces']} faces "
                f"({item['hawaiian']} Hawaiian) with the best window {item['window']}"
            )

        breaks = ", ".join(shore_info.get("metadata", {}).get("popular_breaks", []))
        breaks_line = (
            f"Focus on {breaks} for the cleanest lines on the incoming tide."
            if breaks
            else "Mix of reefs and sandbars respond similarly today."
        )

        confidence_line = (
            f"Overall confidence checks in at {self.confidence:.1f}/1.0; expect typical seasonal variability."
        )

        advice = (
            "Morning sessions stay smoother before afternoon trades add texture." if "morning" not in wind_line.lower()
            else wind_line
        )

        paragraphs = [
            summary,
            wind_line,
            " ".join(secondary_lines) if secondary_lines else "",
            breaks_line,
            advice,
            confidence_line,
        ]

        return "\n".join(line for line in paragraphs if line)

    def build_daily_forecast(self) -> str:
        season_phrase = self._seasonal_phrase()
        north = self._shore_activity("north_shore")
        south = self._shore_activity("south_shore")
        north_line = (
            f"North Shore: {north[0]['faces']} faces from the {north[0]['direction']} swell, peak window {north[0]['window']}."
            if north
            else "North Shore: Waist-high or less with modest trade swell."
        )
        south_line = (
            f"South Shore: {south[0]['faces']} faces with {south[0]['direction']} energy, best mid-morning {south[0]['window']}."
            if south
            else "South Shore: Knee-to-thigh wrap only; expect long waits."
        )

        wind = self._wind_summary()
        tide_line = self._tide_summary()

        action_line = (
            "Target dawn patrol for clean faces before trades rise after lunch; town reefs handle winds best."
        )

        parts = [
            f"Today ({self.data.get('start_date')}): {season_phrase}",
            north_line,
            south_line,
            wind,
            tide_line,
            action_line,
        ]

        return "\n".join(part for part in parts if part)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _map_event_exposures(self) -> Dict[str, List[Dict[str, Any]]]:
        exposures: Dict[str, List[Dict[str, Any]]] = {}
        for shore_key, shore_info in self.shore_data.items():
            for event in shore_info.get("swell_events", []):
                event_id = event.get("event_id")
                if not event_id:
                    continue
                data = {
                    "shore": shore_key,
                    "exposure": event.get("exposure_factor", 0.5),
                    "hawaii_scale": event.get("hawaii_scale", 0.0),
                    "direction": event.get("primary_direction_cardinal", "Unknown"),
                    "period": event.get("dominant_period", 0.0),
                    "start": event.get("start_time"),
                    "peak": event.get("peak_time"),
                    "end": event.get("end_time"),
                }
                exposures.setdefault(event_id, []).append(data)
        return exposures

    def _build_summary_text(self) -> str:
        if not self.events:
            return "Model guidance is unavailable; expect seasonally typical surf with minimal variation."

        primary = max(self.events, key=lambda e: e.get("hawaii_scale", 0.0))
        timing = self._timing_phrase(primary)
        faces = self._faces_text(primary.get("hawaii_scale", 0.0))
        direction = primary.get("primary_direction_cardinal", "Unknown")
        shore_focus = self._event_shore_focus(primary.get("event_id"))
        wind = self._wind_summary()

        secondary_mentions = []
        for event in sorted(self.events, key=lambda e: e.get("hawaii_scale", 0.0), reverse=True)[1:3]:
            secondary_mentions.append(
                f"Secondary {event.get('primary_direction_cardinal', 'Unknown')} lines hold {self._faces_text(event.get('hawaii_scale', 0.0))} faces {self._timing_phrase(event)}."
            )

        summary_parts = [
            f"Primary {direction} swell {timing} keeps the {shore_focus} in the {faces} zone.",
            " ".join(secondary_mentions) if secondary_mentions else "",
            wind,
            f"Forecast confidence sits at {self.confidence:.1f}/1.0 with good data coverage.",
        ]

        return " ".join(part for part in summary_parts if part)

    def _build_detail_lines(self) -> str:
        lines: List[str] = []
        for event in sorted(self.events, key=lambda e: (e.get("significance", 0.0), e.get("hawaii_scale", 0.0)), reverse=True):
            event_id = event.get("event_id")
            direction = event.get("primary_direction_cardinal", "Unknown")
            period = event.get("dominant_period", 0.0)
            faces = self._faces_text(event.get("hawaii_scale", 0.0))
            timing = self._timing_phrase(event)
            shore_focus = self._event_shore_focus(event_id)
            lines.append(
                f"- {direction} swell ({period:.0f}s) delivers {faces} faces {timing} with strongest impact on {shore_focus}."
            )
        return "\n".join(lines)

    def _shore_snapshot(self, shore_key: str) -> str:
        activity = self._shore_activity(shore_key)
        if not activity:
            return "Seasonally tiny; ankle-to-knee high with no distinct pulses."

        top = activity[0]
        extras = activity[1:] if len(activity) > 1 else []
        lines = [
            f"{top['direction']} energy keeps {top['faces']} faces {top['window']} with {top['confidence']} confidence.",
        ]
        for item in extras:
            lines.append(
                f"Watch for {item['direction']} background lines around {item['window']} holding {item['faces']} faces."
            )
        return " ".join(lines)

    def _shore_activity(self, shore_key: str) -> List[Dict[str, Any]]:
        shore_info = self.shore_data.get(shore_key, {})
        records: List[Dict[str, Any]] = []
        for event in shore_info.get("swell_events", []):
            hawaiian = event.get("hawaii_scale", 0.0)
            faces_text = self._faces_text(hawaiian)
            window = self._window_phrase(event)
            records.append(
                {
                    "event_id": event.get("event_id"),
                    "hawaiian": self._hawaiian_text(hawaiian),
                    "faces": faces_text,
                    "direction": event.get("primary_direction_cardinal", "Unknown"),
                    "window": window,
                    "peak_phrase": self._peak_phrase(event),
                    "confidence": self._confidence_text(event.get("event_id")),
                }
            )
        records.sort(key=lambda r: self._faces_score(r["faces"]), reverse=True)
        return records

    def _build_outlook_text(self) -> str:
        season_phrase = self._seasonal_phrase()
        north_hint = "North" if any(e for e in self.events if self._event_has_shore(e, "north_shore")) else "North"
        south_hint = "South" if any(e for e in self.events if self._event_has_shore(e, "south_shore")) else "South"
        return (
            f"Expect {season_phrase} patterns to hold. {north_hint} Shore stays active through the next couple of days "
            f"while {south_hint} Shore trends toward seasonal background. Monitor new NDBC runs for updates."
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _wind_summary(self) -> str:
        if not self.weather:
            return "Trade winds trend moderate with typical island breezes."
        direction = self.weather.get("wind_direction", "ENE")
        speed = self.weather.get("wind_speed", 15)
        gusts = self.weather.get("wind_gusts")
        gust_part = f" gusting {gusts} kt" if gusts else ""
        return f"Trade winds from the {direction} at {speed} kt{gust_part} keep mornings cleaner than afternoons."

    def _wind_sentence_for_shore(self, shore_key: str) -> str:
        if not self.weather:
            return "Light local winds allow for glassy sessions early, with a mild bump by afternoon."
        direction = self.weather.get("wind_direction", "ENE")
        speed = self.weather.get("wind_speed", 15)
        shoreline = "North Shore" if shore_key == "north_shore" else "South Shore"
        return (
            f"{shoreline} sees {direction} trades around {speed} kt; aim for morning windows before onshores roughen the faces."
        )

    def _tide_summary(self) -> str:
        high = self._format_tide_list(self.tides.get("high_tide"))
        low = self._format_tide_list(self.tides.get("low_tide"))
        if not high and not low:
            return "Tides sit near seasonal averages; no major swings expected."
        pieces = []
        if high:
            pieces.append(f"High tide {high}")
        if low:
            pieces.append(f"low tide {low}")
        return ", ".join(pieces) + "."

    def _faces_text(self, hawaiian_height: float) -> str:
        low, high = self._face_range(hawaiian_height)
        return f"{low}-{high} ft"

    @staticmethod
    def _hawaiian_text(hawaiian_height: float) -> str:
        return f"{hawaiian_height:.1f}ft Hawaiian"

    def _face_range(self, hawaiian_height: float) -> List[int]:
        base = max(hawaiian_height, 0.5)
        low = max(1, int(round(base * 2)))
        high = max(low + 1, int(round(base * 3)))
        return [low, high]

    def _faces_score(self, faces_text: str) -> float:
        try:
            low_str, _ = faces_text.replace(" ft", "").split("-")
            return float(low_str)
        except ValueError:
            return 0.0

    def _timing_phrase(self, event: Dict[str, Any]) -> str:
        start = self._format_time(event.get("start_time"))
        peak = self._format_time(event.get("peak_time"))
        if start and peak:
            return f"building {start} and peaking {peak}"
        if peak:
            return f"peaking {peak}"
        if start:
            return f"arriving {start}"
        return "on tap all period"

    def _window_phrase(self, event: Dict[str, Any]) -> str:
        start = self._format_time(event.get("start_time"))
        peak = self._format_time(event.get("peak_time"))
        end = self._format_time(event.get("end_time"))
        if start and end:
            return f"{start}-{end}"
        if peak:
            return f"around {peak}"
        return "through the period"

    def _peak_phrase(self, event: Dict[str, Any]) -> str:
        peak = self._format_time(event.get("peak_time"))
        return peak if peak else "the daylight hours"

    def _format_time(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        try:
            clean = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo and ZoneInfo:
                dt = dt.astimezone(ZoneInfo("Pacific/Honolulu"))
            elif ZoneInfo:
                dt = dt.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
            return dt.strftime("%a %H:%M HST")
        except Exception:
            return raw

    def _format_tide_list(self, tide_data: Any) -> Optional[str]:
        if not tide_data:
            return None
        if isinstance(tide_data, (list, tuple)) and tide_data and not isinstance(tide_data[0], (list, tuple)):
            # Single pair stored as [time, height]
            time_str, height = tide_data
            return f"at {time_str} ({height:.1f} ft)"
        entries = []
        for time_str, height in tide_data:
            entries.append(f"at {time_str} ({height:.1f} ft)")
        return " and ".join(entries)

    def _event_shore_focus(self, event_id: Optional[str]) -> str:
        exposures = self.event_exposures.get(event_id or "", [])
        if not exposures:
            return "both shores"
        strong = [e for e in exposures if e["exposure"] >= 0.6]
        moderate = [e for e in exposures if 0.4 <= e["exposure"] < 0.6]
        if strong:
            return ", ".join(self._shore_title(e["shore"]) for e in strong)
        if moderate:
            return ", ".join(self._shore_title(e["shore"]) for e in moderate)
        return "exposed coasts"

    def _event_has_shore(self, event: Dict[str, Any], shore_key: str) -> bool:
        exposures = self.event_exposures.get(event.get("event_id"), [])
        return any(exp.get("shore") == shore_key for exp in exposures)

    def _event_has_any_shore(self, event_id: Optional[str]) -> bool:
        return bool(self.event_exposures.get(event_id or "", []))

    def _confidence_text(self, event_id: Optional[str]) -> str:
        if not self._event_has_any_shore(event_id):
            return "moderate"
        base = self.confidence
        if base >= 0.8:
            return "high"
        if base >= 0.6:
            return "moderate"
        return "low"

    def _shore_title(self, shore_key: str) -> str:
        return "North Shore" if shore_key == "north_shore" else "South Shore"

    def _seasonal_phrase(self) -> str:
        season = self.seasonal.get("current_season", "seasonal").title()
        patterns = self.seasonal.get("seasonal_patterns", {})
        north = patterns.get("north_shore", {}).get("typical_conditions", "steady trade swell")
        south = patterns.get("south_shore", {}).get("typical_conditions", "occasional background pulses")
        return f"{season} pattern with {north.lower()} up north and {south.lower()} in town"


__all__ = ["LocalForecastGenerator"]
