"""Local, rule-based fallback generator for producing surf forecasts without OpenAI.

This module offers deterministic text generation that leverages the processed
forecast data to craft readable forecasts. It is intentionally conservative and
focused on surf-relevant details so automated tests and CLI workflows can run in
offline or air-gapped environments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover - fallback for platforms without zoneinfo
    ZoneInfo = None  # type: ignore


class LocalForecastGenerator:
    """Compose deterministic surf forecast text from structured swell data."""

    def __init__(self, forecast_data: dict[str, Any]):
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
        tabular = self._build_tabular_summary()
        buoy_readings = self._build_buoy_readings_section()
        storm_backstory = self._build_storm_backstory()
        historical = self._build_historical_comparison()
        summary = self._build_summary_text()
        details = self._build_detail_lines()
        north_snapshot = self._shore_snapshot("north_shore")
        south_snapshot = self._shore_snapshot("south_shore")
        east_snapshot = self._shore_snapshot("east_shore")
        west_snapshot = self._shore_snapshot("west_shore")
        outlook = self._build_outlook_text()
        extended_outlook = self._build_extended_outlook()

        sections = [
            "SWELL FORECAST TABLE:",
            tabular,
            "",
            "CURRENT BUOY OBSERVATIONS:",
            buoy_readings,
            "",
            "STORM ORIGINS:",
            storm_backstory,
            "",
            "HISTORICAL CONTEXT:",
            historical,
            "",
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
            "EAST SHORE SNAPSHOT:",
            east_snapshot,
            "",
            "WEST SHORE SNAPSHOT:",
            west_snapshot,
            "",
            "SHORT-RANGE OUTLOOK (DAYS 1-5):",
            outlook,
            "",
            "EXTENDED OUTLOOK (DAYS 6-10):",
            extended_outlook,
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
            f"and {lead['hawaiian']} scale surf through {lead['peak_phrase']}."
        )

        secondary_lines = []
        for item in secondary:
            secondary_lines.append(
                f"Secondary energy from {item['direction']} holds {item['faces']} faces "
                f"({item['hawaiian']}) with the best window {item['window']}"
            )

        breaks = ", ".join(shore_info.get("metadata", {}).get("popular_breaks", []))
        breaks_line = (
            f"Focus on {breaks} for the cleanest lines on the incoming tide."
            if breaks
            else "Mix of reefs and sandbars respond similarly today."
        )

        confidence_line = f"Overall confidence checks in at {self.confidence:.1f}/1.0; expect typical seasonal variability."

        advice = (
            "Morning sessions stay smoother before afternoon trades add texture."
            if "morning" not in wind_line.lower()
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

        action_line = "Target dawn patrol for clean faces before trades rise after lunch; town reefs handle winds best."

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
    def _map_event_exposures(self) -> dict[str, list[dict[str, Any]]]:
        exposures: dict[str, list[dict[str, Any]]] = {}
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
        for event in sorted(self.events, key=lambda e: e.get("hawaii_scale", 0.0), reverse=True)[
            1:3
        ]:
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
        lines: list[str] = []
        for event in sorted(
            self.events,
            key=lambda e: (e.get("significance", 0.0), e.get("hawaii_scale", 0.0)),
            reverse=True,
        ):
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

    def _shore_activity(self, shore_key: str) -> list[dict[str, Any]]:
        shore_info = self.shore_data.get(shore_key, {})
        records: list[dict[str, Any]] = []
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
        north_hint = (
            "North"
            if any(e for e in self.events if self._event_has_shore(e, "north_shore"))
            else "North"
        )
        south_hint = (
            "South"
            if any(e for e in self.events if self._event_has_shore(e, "south_shore"))
            else "South"
        )
        return (
            f"Expect {season_phrase} patterns to hold. {north_hint} Shore stays active through the next couple of days "
            f"while {south_hint} Shore trends toward seasonal background. Monitor new NDBC runs for updates."
        )

    def _build_tabular_summary(self) -> str:
        """Build Pat Caldwell-style tabular summary of swell conditions.

        Format (matching Pat Caldwell's SwellCaldWell table):
        | DATE      | HGT | DIR  | PER  | H1/3 | H1/10 | TREND | PROB | WIND | W_DIR |

        Where:
        - HGT: Deepwater swell height (feet)
        - DIR: Swell direction (cardinal)
        - PER: Swell period (seconds)
        - H1/3: Surf breaker height average of highest 1/3
        - H1/10: Surf breaker height average of highest 1/10
        - TREND: UP/DOWN/HOLD
        - PROB: Probability/confidence (LOW/MED/HIGH)
        - WIND: Wind speed (knots)
        - W_DIR: Wind direction
        """
        if not self.events:
            return "No swell data available for tabular summary."

        # Build header (Pat Caldwell style)
        header = "| DATE      | HGT | DIR  | PER  | H1/3 | H1/10 | TREND | PROB | WIND  | W_DIR |"
        separator = "|-----------|-----|------|------|------|-------|-------|------|-------|-------|"

        rows = []
        seen_dates = set()

        # Get wind data
        wind_speed = self.weather.get("wind_speed", 15) if self.weather else 15
        wind_dir = self.weather.get("wind_direction", "E")
        if isinstance(wind_dir, (int, float)):
            wind_dir = self._degrees_to_cardinal(wind_dir)
        wind_str = f"{wind_speed:.0f}-{wind_speed + 5:.0f}"

        # Sort events by time
        sorted_events = sorted(
            self.events,
            key=lambda e: e.get("peak_time", "") or e.get("start_time", "")
        )

        for event in sorted_events:
            # Get date from peak_time or start_time
            peak_time = event.get("peak_time") or event.get("start_time")
            if not peak_time:
                continue

            try:
                date_str = self._format_date_short(peak_time)
            except Exception:
                date_str = "Unknown"

            # Skip duplicate dates for the same direction
            direction = event.get("primary_direction_cardinal", "UNK")
            date_key = f"{date_str}_{direction}"
            if date_key in seen_dates:
                continue
            seen_dates.add(date_key)

            # Get deepwater swell height (meters to feet)
            # This is the raw swell height before shoaling/refraction
            swell_height_m = event.get("significant_height", 0)
            if not swell_height_m:
                # Estimate from hawaii_scale (reverse the conversion)
                h13 = event.get("hawaii_scale", 0)
                swell_height_m = h13 / 3.28084 if h13 else 0
            swell_height_ft = swell_height_m * 3.28084 if swell_height_m else 0
            hgt_str = f"{swell_height_ft:.0f}" if swell_height_ft else "---"

            # Get period
            period = event.get("dominant_period", 0)
            per_str = f"{period:.0f}s" if period else "---"

            # Get H1/3 (Hawaiian scale surf face) and calculate H1/10
            h13 = event.get("hawaii_scale", 0)
            h110 = h13 * 1.5 if h13 else 0
            h13_str = f"{h13:.0f}" if h13 else "---"
            h110_str = f"{h110:.0f}" if h110 else "---"

            # Calculate trend
            trend = self._calculate_swell_trend(event)

            # Get probability/confidence
            significance = event.get("significance", 0.5)
            if significance >= 0.7:
                prob = "HIGH"
            elif significance >= 0.4:
                prob = "LOW"
            else:
                prob = "LOW"

            row = f"| {date_str:<9} | {hgt_str:>3} | {direction:<4} | {per_str:<4} | {h13_str:>4} | {h110_str:>5} | {trend:<5} | {prob:<4} | {wind_str:>5} | {wind_dir:<5} |"
            rows.append(row)

        if not rows:
            return "No swell data available for tabular summary."

        return "\n".join([header, separator] + rows)
    
    def _format_date_short(self, raw: str | None) -> str:
        """Format datetime to short date string like 'Mon 11/24'."""
        if not raw:
            return "Unknown"
        try:
            clean = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo and ZoneInfo:
                dt = dt.astimezone(ZoneInfo("Pacific/Honolulu"))
            elif ZoneInfo:
                dt = dt.replace(tzinfo=ZoneInfo("Pacific/Honolulu"))
            return dt.strftime("%a %m/%d")
        except Exception:
            return raw[:10] if len(raw) >= 10 else raw
    
    def _swell_name_from_direction(self, cardinal: str) -> str:
        """Convert cardinal direction to swell type name."""
        north_dirs = {"N", "NNE", "NNW", "NE", "NW"}
        south_dirs = {"S", "SSE", "SSW", "SE", "SW"}
        east_dirs = {"E", "ENE", "ESE"}
        west_dirs = {"W", "WNW", "WSW"}
        
        if cardinal in north_dirs:
            return "NW"
        elif cardinal in south_dirs:
            return "S"
        elif cardinal in east_dirs:
            return "E"
        elif cardinal in west_dirs:
            return "W"
        return "MIX"
    
    def _calculate_swell_trend(self, event: dict) -> str:
        """Calculate swell trend (UP/DOWN/HOLD) based on event data."""
        # Look at metadata for trend info
        metadata = event.get("metadata", {})
        if "trend" in metadata:
            return metadata["trend"]
        
        # Try to infer from timing - if we're before peak, UP; after peak, DOWN
        start_time = event.get("start_time")
        peak_time = event.get("peak_time")
        end_time = event.get("end_time")
        
        try:
            now = datetime.now()
            if peak_time:
                peak_clean = peak_time.replace("Z", "+00:00") if peak_time.endswith("Z") else peak_time
                peak_dt = datetime.fromisoformat(peak_clean)
                if peak_dt.tzinfo:
                    peak_dt = peak_dt.replace(tzinfo=None)
                
                if now < peak_dt:
                    return "UP"
                elif end_time:
                    end_clean = end_time.replace("Z", "+00:00") if end_time.endswith("Z") else end_time
                    end_dt = datetime.fromisoformat(end_clean)
                    if end_dt.tzinfo:
                        end_dt = end_dt.replace(tzinfo=None)
                    if now < end_dt:
                        return "DOWN"
        except Exception:
            pass
        
        return "HOLD"

    def _build_buoy_readings_section(self) -> str:
        """Build a section showing current buoy readings like Pat Caldwell.
        
        Format: "Buoy 51001: 6.2ft @ 14s NNW (320°)"
        """
        buoy_lines = []
        
        for event in self.events:
            metadata = event.get("metadata", {})
            source = event.get("source", "")
            
            # Only include buoy-sourced events
            if "buoy" not in source.lower():
                continue
            
            station_id = metadata.get("station_id", "")
            buoy_name = metadata.get("buoy_name", "")
            
            # Get wave parameters from primary components
            components = event.get("primary_components", [])
            if components:
                comp = components[0]
                height_m = comp.get("height", 0)
                period = comp.get("period", 0)
                direction_deg = comp.get("direction", 0)
            else:
                # Fall back to event-level data
                height_m = event.get("hawaii_scale", 0) / 3.28084 if event.get("hawaii_scale") else 0
                period = event.get("dominant_period", 0)
                direction_deg = event.get("primary_direction", 0)
            
            # Convert height to feet
            height_ft = height_m * 3.28084 if height_m else 0
            
            # Get cardinal direction
            cardinal = event.get("primary_direction_cardinal", "")
            if not cardinal and direction_deg:
                cardinal = self._degrees_to_cardinal(direction_deg)
            
            # Format buoy name
            display_name = buoy_name if buoy_name else f"Buoy {station_id}"
            
            # Build the line
            if height_ft > 0 and period > 0:
                line = f"  {display_name}: {height_ft:.1f}ft @ {period:.0f}s {cardinal}"
                if direction_deg:
                    line += f" ({int(direction_deg)}°)"
                buoy_lines.append(line)
        
        if not buoy_lines:
            return "No real-time buoy readings available."
        
        return "\n".join(buoy_lines)

    def _build_storm_backstory(self) -> str:
        """Build Pat Caldwell-style storm backstory section.
        
        Format: "Low formed near Kamchatka 11/18, 968mb, currently 2400nm NW..."
        """
        metadata = self.data.get("metadata", {})
        storm_detections = metadata.get("storm_detections", [])
        swell_arrivals = metadata.get("swell_arrivals", {})
        pressure_analysis = metadata.get("pressure_chart_analysis", "")
        
        if not storm_detections and not pressure_analysis:
            # Try to infer from swell events
            stories = []
            for event in self.events:
                if event.get("significance", 0) > 0.5:
                    direction = event.get("primary_direction_cardinal", "")
                    hawaii_scale = event.get("hawaii_scale", 0)
                    
                    # Estimate storm origin based on direction
                    if direction in ("NW", "NNW", "WNW"):
                        origin = "Aleutian low"
                        region = "North Pacific"
                    elif direction in ("N", "NNE"):
                        origin = "North Pacific system"
                        region = "central North Pacific"
                    elif direction in ("S", "SSW", "SSE"):
                        origin = "Southern Hemisphere low"
                        region = "Tasman Sea or south of New Zealand"
                    elif direction in ("E", "ENE", "ESE"):
                        origin = "Trade wind fetch"
                        region = "northeast trades"
                    else:
                        origin = "Distant storm"
                        region = "mid-Pacific"
                    
                    if hawaii_scale >= 4:
                        strength = "strong"
                    elif hawaii_scale >= 2:
                        strength = "moderate"
                    else:
                        strength = "modest"
                    
                    stories.append(
                        f"  {direction} swell originates from {strength} {origin} "
                        f"in the {region}."
                    )
            
            if stories:
                return "\n".join(stories[:3])  # Top 3 most significant
            return "No significant storm activity detected in the forecast window."
        
        # Build from detected storms
        lines = []
        for storm in storm_detections[:3]:  # Top 3 storms
            storm_id = storm.get("storm_id", "Unknown")
            lat = storm.get("latitude")
            lon = storm.get("longitude")
            pressure = storm.get("pressure_mb")
            wind_speed = storm.get("wind_speed_kt")
            fetch_nm = storm.get("fetch_nm")
            
            # Build description
            parts = [f"  Storm {storm_id}:"]
            if lat and lon:
                parts.append(f"at {lat:.0f}N/{abs(lon):.0f}W")
            if pressure:
                parts.append(f"{pressure}mb")
            if wind_speed:
                parts.append(f"{wind_speed}kt winds")
            if fetch_nm:
                parts.append(f"{fetch_nm}nm fetch")
            
            # Add arrival info if available
            if storm_id in swell_arrivals:
                arrival = swell_arrivals[storm_id]
                arrival_time = arrival.get("arrival_time_hst")
                if arrival_time:
                    parts.append(f"arriving {arrival_time}")
            
            lines.append(" ".join(parts))
        
        if lines:
            return "\n".join(lines)
        
        return "Storm systems being tracked but details unavailable."

    def _build_historical_comparison(self) -> str:
        """Build 'on this day' historical comparison like Pat Caldwell.
        
        Format: "On this day: Average Hs is 6.2 ft, record was 18 ft (1975)."
        """
        metadata = self.data.get("metadata", {})
        climatology = metadata.get("climatology", [])
        climatology_summary = metadata.get("climatology_summary", "")
        
        # Get current date
        now = datetime.now()
        month_day = now.strftime("%B %d")
        
        if climatology_summary:
            return f"  Historical context ({month_day}): {climatology_summary}"
        
        if climatology:
            # Try to extract relevant data
            for entry in climatology:
                if "average" in str(entry).lower() or "record" in str(entry).lower():
                    return f"  Historical context ({month_day}): {entry}"
        
        # Fall back to seasonal context
        seasonal = self.seasonal
        if seasonal:
            season = seasonal.get("season", "")
            typical = seasonal.get("typical_conditions", "")
            if season and typical:
                return f"  Historical context: {season} typically brings {typical}."
        
        return f"  Historical context ({month_day}): Climatology data unavailable for precise comparison."

    def _build_extended_outlook(self) -> str:
        """Build 7-10 day long-range outlook like Pat Caldwell."""
        metadata = self.data.get("metadata", {})
        
        # Check for model forecasts extending beyond 5 days
        long_range_events = []
        for event in self.events:
            # Check if event is in the extended forecast window (5-10 days)
            peak_time = event.get("peak_time")
            if not peak_time:
                continue
            try:
                clean = peak_time.replace("Z", "+00:00") if peak_time.endswith("Z") else peak_time
                peak_dt = datetime.fromisoformat(clean)
                if peak_dt.tzinfo:
                    peak_dt = peak_dt.replace(tzinfo=None)
                days_out = (peak_dt - datetime.now()).days
                if 5 <= days_out <= 10:
                    long_range_events.append({
                        "event": event,
                        "days_out": days_out
                    })
            except Exception:
                continue
        
        if long_range_events:
            lines = ["  Days 6-10 outlook:"]
            for lr in sorted(long_range_events, key=lambda x: x["days_out"])[:3]:
                event = lr["event"]
                days = lr["days_out"]
                direction = event.get("primary_direction_cardinal", "Unknown")
                h13 = event.get("hawaii_scale", 0)
                lines.append(
                    f"    Day {days}: {direction} swell potential, ~{h13:.0f}ft Hawaiian scale"
                )
            return "\n".join(lines)
        
        # Fall back to general outlook based on seasonal patterns
        month = datetime.now().month
        if month in (11, 12, 1, 2):  # Winter - North Pacific active
            return "  Days 6-10: North Pacific storm track remains active; expect additional NW-NNW swell events."
        elif month in (3, 4, 5):  # Spring - Transition
            return "  Days 6-10: Spring transition pattern; diminishing NW swell with occasional trade pulses."
        elif month in (6, 7, 8):  # Summer - South swells
            return "  Days 6-10: Watch for Southern Hemisphere long-period south swells; trades remain consistent."
        else:  # Fall
            return "  Days 6-10: Fall pattern developing; monitor for first significant NW swells of the season."

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _wind_summary(self) -> str:
        if not self.weather:
            return "Trade winds trend moderate with typical island breezes."
        direction = self.weather.get("wind_direction", "ENE")
        # Convert numeric direction to cardinal if needed
        if isinstance(direction, (int, float)):
            direction = self._degrees_to_cardinal(direction)
        speed = self.weather.get("wind_speed", 15)
        gusts = self.weather.get("wind_gusts")
        gust_part = f" gusting {gusts} kt" if gusts else ""
        return f"Trade winds from the {direction} at {speed} kt{gust_part} keep mornings cleaner than afternoons."

    @staticmethod
    def _degrees_to_cardinal(degrees: float) -> str:
        """Convert degrees to 16-point cardinal direction."""
        if degrees is None:
            return "VAR"
        dirs = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
        ]
        ix = round(degrees / 22.5) % 16
        return dirs[ix]

    def _wind_sentence_for_shore(self, shore_key: str) -> str:
        if not self.weather:
            return (
                "Light local winds allow for glassy sessions early, with a mild bump by afternoon."
            )
        direction = self.weather.get("wind_direction", "ENE")
        # Convert numeric direction to cardinal if needed
        if isinstance(direction, (int, float)):
            direction = self._degrees_to_cardinal(direction)
        speed = self.weather.get("wind_speed", 15)
        shoreline = self._shore_title(shore_key)
        return f"{shoreline} sees {direction} trades around {speed} kt; aim for morning windows before onshores roughen the faces."

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

    def _face_range(self, hawaiian_height: float) -> list[int]:
        """Convert Hawaiian scale (H1/3) to face height range (H1/3 to H1/10).

        Per Pat Caldwell: H1/3 surf face ≈ Hawaiian scale, H1/10 ≈ 1.5x Hawaiian.
        """
        base = max(hawaiian_height, 0.5)
        low = max(1, int(round(base)))  # H1/3 surf face
        high = max(low + 1, int(round(base * 1.5)))  # H1/10 surf face
        return [low, high]

    def _faces_score(self, faces_text: str) -> float:
        try:
            low_str, _ = faces_text.replace(" ft", "").split("-")
            return float(low_str)
        except ValueError:
            return 0.0

    def _timing_phrase(self, event: dict[str, Any]) -> str:
        start = self._format_time(event.get("start_time"))
        peak = self._format_time(event.get("peak_time"))
        if start and peak:
            return f"building {start} and peaking {peak}"
        if peak:
            return f"peaking {peak}"
        if start:
            return f"arriving {start}"
        return "on tap all period"

    def _window_phrase(self, event: dict[str, Any]) -> str:
        start = self._format_time(event.get("start_time"))
        peak = self._format_time(event.get("peak_time"))
        end = self._format_time(event.get("end_time"))
        if start and end:
            return f"{start}-{end}"
        if peak:
            return f"around {peak}"
        return "through the period"

    def _peak_phrase(self, event: dict[str, Any]) -> str:
        peak = self._format_time(event.get("peak_time"))
        return peak if peak else "the daylight hours"

    def _format_time(self, raw: str | None) -> str | None:
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

    def _format_tide_list(self, tide_data: Any) -> str | None:
        if not tide_data:
            return None
        if (
            isinstance(tide_data, (list, tuple))
            and tide_data
            and not isinstance(tide_data[0], (list, tuple))
        ):
            # Single pair stored as [time, height]
            time_str, height = tide_data
            return f"at {time_str} ({height:.1f} ft)"
        entries = []
        for time_str, height in tide_data:
            entries.append(f"at {time_str} ({height:.1f} ft)")
        return " and ".join(entries)

    def _event_shore_focus(self, event_id: str | None) -> str:
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

    def _event_has_shore(self, event: dict[str, Any], shore_key: str) -> bool:
        exposures = self.event_exposures.get(event.get("event_id"), [])
        return any(exp.get("shore") == shore_key for exp in exposures)

    def _event_has_any_shore(self, event_id: str | None) -> bool:
        return bool(self.event_exposures.get(event_id or "", []))

    def _confidence_text(self, event_id: str | None) -> str:
        if not self._event_has_any_shore(event_id):
            return "moderate"
        base = self.confidence
        if base >= 0.8:
            return "high"
        if base >= 0.6:
            return "moderate"
        return "low"

    def _shore_title(self, shore_key: str) -> str:
        titles = {
            "north_shore": "North Shore",
            "south_shore": "South Shore",
            "east_shore": "East Shore",
            "west_shore": "West Shore",
        }
        return titles.get(shore_key, shore_key.replace("_", " ").title())

    def _seasonal_phrase(self) -> str:
        season = self.seasonal.get("current_season", "seasonal").title()
        patterns = self.seasonal.get("seasonal_patterns", {})
        north = patterns.get("north_shore", {}).get("typical_conditions", "steady trade swell")
        south = patterns.get("south_shore", {}).get(
            "typical_conditions", "occasional background pulses"
        )
        return f"{season} pattern with {north.lower()} up north and {south.lower()} in town"


__all__ = ["LocalForecastGenerator"]
