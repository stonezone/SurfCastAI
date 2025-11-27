"""Utility helpers for building rich prompt context for the forecast engine."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:  # Python 3.9+
    from zoneinfo import ZoneInfo

    HAWAII_TZ = ZoneInfo("Pacific/Honolulu")
except Exception:  # pragma: no cover - fallback on platforms without zoneinfo
    ZoneInfo = None  # type: ignore
    HAWAII_TZ = None  # type: ignore

# Path to climatology lookup file
CLIMATOLOGY_LOOKUP_PATH = Path(__file__).parent.parent.parent / "data" / "climatology_lookup.json"


def build_context(forecast_data: dict[str, Any]) -> dict[str, Any]:
    """Construct structured context strings to feed into LLM prompts."""

    metadata = forecast_data.get("metadata", {})
    swell_events: list[dict[str, Any]] = forecast_data.get("swell_events", [])
    shore_data: dict[str, dict[str, Any]] = forecast_data.get("shore_data", {})
    confidence = forecast_data.get("confidence", {})

    overview = _build_overview(metadata, confidence, swell_events)
    swell_matrix = _build_swell_matrix(swell_events)
    timeline = _build_timeline_section(swell_events)
    weather = _build_weather_section(metadata)
    tides = _build_tide_section(metadata)
    tropical = _build_tropical_section(metadata)
    gaps = _build_data_gap_section(metadata)
    upper_air = _build_upper_air_section(metadata)
    climatology = _build_climatology_section(metadata)

    shore_digests = {
        shore: _build_shore_digest(shore_info) for shore, shore_info in shore_data.items()
    }

    sections = [
        "=== DATA QUALITY & CONFIDENCE ===",
        overview,
        gaps,
        "",
        "=== SWELL MATRIX (HST) ===",
        swell_matrix,
        "",
        "=== 3-DAY TIMELINE ESTIMATE (HST) ===",
        timeline,
        "",
        "=== WEATHER SNAPSHOT ===",
        weather,
        "",
        "=== TIDES ===",
        tides,
        "",
        "=== UPPER-AIR DIAGNOSTICS ===",
        upper_air,
        "",
        "=== CLIMATOLOGY REFERENCES ===",
        climatology,
        "",
        "=== TROPICAL & SYNOPTIC NOTES ===",
        tropical,
    ]

    data_digest = "\n".join(line for line in sections if line)

    return {
        "data_digest": data_digest,
        "shore_digests": shore_digests,
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_overview(
    metadata: dict[str, Any],
    confidence: dict[str, Any],
    swell_events: list[dict[str, Any]],
) -> str:
    score = confidence.get("overall_score")
    category = confidence.get("category", "Unknown")

    if score is not None:
        score_line = f"Confidence: {score:.2f}/1.00 ({category})."
    else:
        score_line = "Confidence: unavailable."

    source_counts = metadata.get("agent_results", {})
    if source_counts:
        parts = []
        for name in sorted(source_counts):
            stats = source_counts[name]
            total = stats.get("total", 0)
            success = stats.get("successful", 0)
            parts.append(f"{name}: {success}/{total} successful")
        coverage_line = ", ".join(parts)
    else:
        coverage_line = "No agent result stats provided."

    event_count = len(swell_events)

    lines = [
        score_line,
        f"Source coverage: {coverage_line}.",
        f"Detected swell events: {event_count} (pre-filtered and fused).",
    ]

    return "\n".join(lines)


def _build_swell_matrix(swell_events: Iterable[dict[str, Any]]) -> str:
    rows: list[str] = []

    sorted_events = sorted(
        swell_events,
        key=lambda e: (e.get("hawaii_scale") or 0.0),
        reverse=True,
    )

    for event in sorted_events[:12]:
        meta = event.get("metadata", {})
        direction = event.get("primary_direction_cardinal") or _deg_to_cardinal(
            event.get("primary_direction")
        )
        direction_deg = event.get("primary_direction")
        height = event.get("hawaii_scale") or 0.0
        period = _extract_period(event)
        start = _format_hst(event.get("start_time"))
        peak = _format_hst(event.get("peak_time"))
        exposure = _format_exposures(meta)
        source_details = meta.get("source_details", {})
        source = (
            source_details.get("buoy_id")
            or source_details.get("source_type")
            or event.get("source", "unknown")
        )
        signif = event.get("significance")

        h10 = _estimate_h10(height)

        rows.append(
            f"• {direction} ({direction_deg:.0f}°) {height:.1f}ft H1/3 ≈ {h10:.1f}ft H1/10, "
            f"period {period:.1f}s. Window: {start} → {peak}. Source: {source}. {exposure}"
            + (f" Significance: {signif:.2f}." if signif is not None else "")
        )

    return "\n".join(rows) if rows else "No swell events available."


def _build_timeline_section(swell_events: Iterable[dict[str, Any]]) -> str:
    timeline: dict[datetime, list[dict[str, Any]]] = defaultdict(list)

    for event in swell_events:
        for ts in filter(
            None, [event.get("start_time"), event.get("peak_time"), event.get("end_time")]
        ):
            dt = _parse_datetime(ts)
            if not dt:
                continue
            hst = _to_hst(dt)
            day = datetime(hst.year, hst.month, hst.day)
            timeline[day].append(event)

    if not timeline:
        return "Timeline data unavailable; buoy feeds lacked temporal metadata."

    lines: list[str] = []
    for day in sorted(timeline.keys())[:6]:
        events = timeline[day]
        dominant = max(events, key=lambda e: e.get("hawaii_scale") or 0.0)
        height = dominant.get("hawaii_scale") or 0.0
        h10 = _estimate_h10(height)
        direction = dominant.get("primary_direction_cardinal") or _deg_to_cardinal(
            dominant.get("primary_direction")
        )
        period = _extract_period(dominant)
        day_string = day.strftime("%a %b %d")

        secondary = [
            _summarise_secondary(e)
            for e in events
            if e is not dominant and (e.get("hawaii_scale") or 0) >= 1.0
        ]
        secondary_text = "; ".join(filter(None, secondary))

        line = f"{day_string}: dominant {direction} {height:.1f}ft H1/3 ({h10:.1f}ft H1/10 est) @ {period:.1f}s."
        if secondary_text:
            line += f" Secondary energy: {secondary_text}."

        lines.append(line)

    return "\n".join(lines)


def _build_weather_section(metadata: dict[str, Any]) -> str:
    weather = metadata.get("weather", {})
    if not weather:
        return "Weather data unavailable."

    wind_dir = weather.get("wind_direction") or weather.get("wind_direction_deg")
    wind_speed_ms = weather.get("wind_speed_ms")
    wind_speed_kt = weather.get("wind_speed_kt")
    if wind_speed_ms is not None and wind_speed_kt is None:
        wind_speed_kt = wind_speed_ms * 1.94384
    if wind_speed_kt is not None:
        wind_part = f"Wind {wind_dir}° at {wind_speed_kt:.1f} kt"
    else:
        wind_part = f"Wind direction {wind_dir}° (speed n/a)"

    metar = weather.get("metar", {})
    cond = metar.get("metar") or weather.get("conditions") or "Conditions n/a"
    issued = _format_hst(metar.get("issued")) if metar.get("issued") else "Time n/a"

    return f"{wind_part}. METAR issued {issued}: {cond}."


def _build_tide_section(metadata: dict[str, Any]) -> str:
    tides = metadata.get("tides", {})
    if not tides:
        return "Tide data unavailable."

    highs = [
        f"{_format_hst(time)} ({height:.2f} ft)" for time, height in tides.get("high_tide", [])
    ][:3]
    lows = [f"{_format_hst(time)} ({height:.2f} ft)" for time, height in tides.get("low_tide", [])][
        :3
    ]

    lines = []
    if highs:
        lines.append("High: " + ", ".join(highs))
    if lows:
        lines.append("Low: " + ", ".join(lows))
    station = tides.get("station")
    if station:
        lines.append(f"NOAA Station: {station}")

    latest = tides.get("latest_water_level")
    if latest:
        lines.append(
            f"Latest obs { _format_hst(latest.get('time')) }: {latest.get('height_ft', 'n/a')} ft"
        )

    return "\n".join(lines)


def _build_tropical_section(metadata: dict[str, Any]) -> str:
    tropical = metadata.get("tropical", {})
    entries = tropical.get("entries", []) if tropical else []
    summary_parts: list[str] = []
    for entry in entries[:2]:
        summary = entry.get("summary") or ""
        summary_parts.append(_strip_html(summary).strip())

    headline = tropical.get("headline") if tropical else None
    if not summary_parts and not headline:
        return "No active tropical advisories impacting the forecast window."

    lines = []
    if headline:
        lines.append(headline)
    lines.extend(summary_parts)
    return "\n".join(line for line in lines if line)


def _build_upper_air_section(metadata: dict[str, Any]) -> str:
    products = _extract_metadata_list(
        metadata,
        [
            "upper_air",
            "upper_air_products",
            "upper_air_charts",
        ],
    )
    if not products:
        return "Upper-air analyses unavailable."

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in products:
        if not isinstance(entry, dict):
            continue
        level = str(entry.get("analysis_level") or entry.get("level") or "unknown")
        grouped.setdefault(level, []).append(entry)

    lines: list[str] = []
    for level in sorted(grouped.keys(), key=_sort_pressure_level):
        descriptors = []
        for item in grouped[level]:
            descriptor = item.get("product_type") or item.get("source_id") or "analysis"
            descriptors.append(descriptor.replace("_", " ").title())
        joined = ", ".join(descriptors)
        lines.append(f"{level} hPa: {joined} available.")

    return "\n".join(lines)


def _build_climatology_section(metadata: dict[str, Any]) -> str:
    """Build historical climatology context in Caldwell style."""
    lines: list[str] = []

    # Load the climatology lookup data
    historical_context = _load_historical_climatology()
    if historical_context:
        lines.append(historical_context)

    # Also include any collected climatology references
    references = _extract_metadata_list(
        metadata,
        [
            "climatology",
            "climatology_references",
            "climatology_stats",
        ],
    )

    if references:
        lines.append("")
        lines.append("Available climatology references:")
        for entry in references:
            if not isinstance(entry, dict):
                continue
            source_id = entry.get("source_id") or entry.get("name") or "unknown source"
            description = entry.get("description") or entry.get("summary") or "reference dataset"
            fmt = entry.get("format") or entry.get("type") or "text"
            lines.append(f"  - {source_id}: {description} (format: {fmt}).")

    if not lines:
        return "Climatology references unavailable."

    return "\n".join(lines)


def _load_historical_climatology() -> str:
    """Load historical climatology data and generate Caldwell-style context for today's date."""
    if not CLIMATOLOGY_LOOKUP_PATH.exists():
        return ""

    try:
        with open(CLIMATOLOGY_LOOKUP_PATH) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return ""

    # Get current date in Hawaii time
    now = datetime.now()
    if HAWAII_TZ:
        now = datetime.now(HAWAII_TZ)

    month_names = {
        1: "january",
        2: "february",
        3: "march",
        4: "april",
        5: "may",
        6: "june",
        7: "july",
        8: "august",
        9: "september",
        10: "october",
        11: "november",
        12: "december",
    }
    month_name = month_names.get(now.month, "november")
    day_str = str(now.day)

    lines = ["HISTORICAL CONTEXT (Goddard-Caldwell Database, 1968-present):"]
    lines.append(f"Date: {now.strftime('%B %d')} ({month_name.title()})")

    # North Shore historical data
    ns_data = data.get("north_shore", {}).get(month_name, {})
    if ns_data:
        ns_daily = ns_data.get("daily", {}).get(day_str, {})
        ns_avg = ns_daily.get("avg", ns_data.get("monthly_average_h1_10", 0))
        ns_max = ns_daily.get("max", ns_data.get("monthly_record_h1_10", 0))
        ns_max_year = ns_daily.get("max_year", ns_data.get("monthly_record_year", ""))

        # Calculate peak face (approximately 2x H1/10 for big surf)
        ns_avg_face = round(ns_avg * 2, 0) if ns_avg else 0
        ns_max_face = round(ns_max * 2, 0) if ns_max else 0

        lines.append("")
        lines.append(f"NORTH SHORE on {now.strftime('%b %d')}:")
        lines.append(
            f"  • Historical H1/10 average: {ns_avg:.1f} ft ({int(ns_avg_face)}' peak face)"
        )
        lines.append(
            f"  • Largest on this date: {ns_max:.0f} ft H1/10 ({int(ns_max_face)}' peak face) in {ns_max_year}"
        )

        # Monthly category breakdown if available
        categories = ns_data.get("days_by_category", {})
        if categories:
            lines.append(f"  • {month_name.title()} typical distribution:")
            lines.append(
                f"    Small (<8'): {categories.get('small_under_8ft', 'n/a')} days, "
                f"Medium (8-14'): {categories.get('medium_8_14ft', 'n/a')} days, "
                f"High (15-24'): {categories.get('high_15_24ft', 'n/a')} days, "
                f"XL (25+): {categories.get('extra_large_25_39ft', 0) + categories.get('giant_40_plus_ft', 0)} days"
            )

    # South Shore historical data
    ss_data = data.get("south_shore", {}).get(month_name, {})
    if ss_data:
        ss_daily = ss_data.get("daily", {}).get(day_str, {})
        ss_avg = ss_daily.get("avg", ss_data.get("monthly_average_h1_10", 0))
        ss_max = ss_daily.get("max", ss_data.get("monthly_record_h1_10", 0))
        ss_max_year = ss_daily.get("max_year", ss_data.get("monthly_record_year", ""))

        ss_avg_face = round(ss_avg * 2, 0) if ss_avg else 0
        ss_max_face = round(ss_max * 2, 0) if ss_max else 0

        lines.append("")
        lines.append(f"SOUTH SHORE on {now.strftime('%b %d')}:")
        lines.append(
            f"  • Historical H1/10 average: {ss_avg:.1f} ft (~{int(ss_avg_face)}' peak face)"
        )
        lines.append(
            f"  • Largest on this date: {ss_max:.0f} ft H1/10 ({int(ss_max_face)}' peak face) in {ss_max_year}"
        )

        notes = ss_data.get("notes")
        if notes:
            lines.append(f"  • Note: {notes}")

    return "\n".join(lines)


def _build_data_gap_section(metadata: dict[str, Any]) -> str:
    agent_results = metadata.get("agent_results", {})
    missing = [name for name, stats in agent_results.items() if stats.get("successful", 0) == 0]
    if not agent_results:
        return "Data coverage notes unavailable (agent telemetry missing)."
    if not missing:
        return "All configured collectors reported successfully."
    return "Missing feeds: " + ", ".join(sorted(missing)) + "."


def _build_shore_digest(shore_info: dict[str, Any]) -> str:
    shore_name = shore_info.get("name") or shore_info.get("shore")
    events = sorted(
        shore_info.get("swell_events", []),
        key=lambda e: (e.get("hawaii_scale") or 0.0),
        reverse=True,
    )

    if not events:
        return f"{shore_name}: No active swell events in fused dataset."

    lines = [f"{shore_name} active swell drivers:"]
    for event in events[:6]:
        direction = event.get("primary_direction_cardinal") or _deg_to_cardinal(
            event.get("primary_direction")
        )
        height = event.get("hawaii_scale") or 0.0
        period = _extract_period(event)
        window = f"{_format_hst(event.get('start_time'))} → {_format_hst(event.get('peak_time'))}"
        exposure = event.get("exposure_factor") or event.get("metadata", {}).get(
            f"exposure_{(shore_name or '').lower().replace(' ', '_')}",
            0.0,
        )
        lines.append(
            f"- {direction} {height:.1f}ft (H1/3) @ {period:.1f}s, window {window}, exposure weight {exposure:.2f}"
        )

    meta = shore_info.get("metadata", {})
    quality = meta.get("overall_quality")
    if quality is not None:
        lines.append(f"Quality index: {quality:.2f} (1.0 = premium conditions).")
    breaks = meta.get("popular_breaks") or []
    if breaks:
        lines.append("Key breaks: " + ", ".join(breaks))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _extract_metadata_list(
    metadata: dict[str, Any], candidate_keys: list[str]
) -> list[dict[str, Any]]:
    for key in candidate_keys:
        value = metadata.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            entries = value.get("entries") or value.get("items") or value.get("products")
            if isinstance(entries, list):
                return entries
    return []


def _sort_pressure_level(level: str) -> float:
    try:
        return float(level)
    except (TypeError, ValueError):
        return float("inf")


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    iso = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _to_hst(dt: datetime) -> datetime:
    if HAWAII_TZ:
        return dt.astimezone(HAWAII_TZ)
    # Fallback: subtract 10 hours (approximate HST) if tzinfo present
    if dt.tzinfo is None:
        return dt
    return (dt - timedelta(hours=10)).replace(tzinfo=None)


def _format_hst(value: Any) -> str:
    dt = _parse_datetime(value)
    if not dt:
        return "n/a"
    hst = _to_hst(dt)
    return hst.strftime("%Y-%m-%d %H:%M HST")


def _deg_to_cardinal(deg: Any) -> str:
    if deg is None:
        return "Unknown"
    try:
        deg = float(deg) % 360
    except (TypeError, ValueError):
        return "Unknown"

    directions = [
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
    idx = int((deg + 11.25) / 22.5) % 16
    return directions[idx]


def _extract_period(event: dict[str, Any]) -> float:
    period = event.get("dominant_period")
    if period:
        try:
            return float(period)
        except (TypeError, ValueError):
            pass

    components = event.get("primary_components", [])
    values = [
        float(comp.get("period")) for comp in components if comp.get("period") not in (None, "")
    ]
    return max(values) if values else 0.0


def _format_exposures(meta: dict[str, Any]) -> str:
    exposures = []
    for key, value in meta.items():
        if not key.startswith("exposure_"):
            continue
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        shore_name = key.replace("exposure_", "").replace("_", " ").title()
        exposures.append(f"{shore_name} ({val:.2f})")

    return "Exposure: " + ", ".join(exposures) if exposures else "Exposure weights unavailable."


def _estimate_h10(h13: float) -> float:
    if h13 <= 0:
        return 0.0
    # Empirical relationship: H1/10 ≈ 1.3 * H1/3 for mixed seas
    return round(h13 * 1.3, 1)


def _summarise_secondary(event: dict[str, Any]) -> str:
    direction = event.get("primary_direction_cardinal") or _deg_to_cardinal(
        event.get("primary_direction")
    )
    height = event.get("hawaii_scale") or 0.0
    period = _extract_period(event)
    return f"{direction} {height:.1f}ft @{period:.0f}s"


def _strip_html(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value)
    return re.sub(r"<[^>]+>", "", text)
