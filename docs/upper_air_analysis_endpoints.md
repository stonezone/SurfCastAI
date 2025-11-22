# WPC Upper Air Analysis Endpoint Discovery Report
**Date:** 2025-10-16
**Status:** Working Endpoints Found

## Executive Summary

Successfully identified working upper-air analysis endpoints for 250mb (jet stream) and 500mb (height analysis) from the **Storm Prediction Center (SPC)**, which is part of NOAA's National Centers for Environmental Prediction (NCEP).

**Key Finding:** The original WPC endpoints (`noaa250_curr.gif`, `noaa500_curr.gif`) are no longer available, but SPC provides current alternatives with full archive support.

---

## Primary Working Endpoints

### Storm Prediction Center (SPC)
**Status:** ✓ WORKING - HTTP 200
**Organization:** NOAA/NWS SPC
**URL Pattern:** `https://www.spc.noaa.gov/obswx/maps/{LEVEL}_{YYMMDD}_{HH}.{FORMAT}`

#### 250mb Jet Stream Analysis
```
GIF:  https://www.spc.noaa.gov/obswx/maps/250_YYMMDD_00.gif
PDF:  https://www.spc.noaa.gov/obswx/maps/250_YYMMDD_00.pdf
```

#### 500mb Height Analysis
```
GIF:  https://www.spc.noaa.gov/obswx/maps/500_YYMMDD_00.gif
PDF:  https://www.spc.noaa.gov/obswx/maps/500_YYMMDD_00.pdf
```

### Template Parameters

| Parameter | Format | Example | Notes |
|-----------|--------|---------|-------|
| YYMMDD    | 2-2-2  | 251016  | Year (25) + Month (10) + Day (16) |
| HH        | 00     | 00      | Only 00Z available (06Z/12Z/18Z = 403) |
| FORMAT    | gif/pdf | gif    | Both formats supported equally |

### Example URLs (2025-10-16)
```
250mb GIF:   https://www.spc.noaa.gov/obswx/maps/250_251016_00.gif  (HTTP 200, 48.4 KB)
500mb GIF:   https://www.spc.noaa.gov/obswx/maps/500_251016_00.gif  (HTTP 200, 41.9 KB)
250mb PDF:   https://www.spc.noaa.gov/obswx/maps/250_251016_00.pdf  (HTTP 200)
500mb PDF:   https://www.spc.noaa.gov/obswx/maps/500_251016_00.pdf  (HTTP 200)
```

---

## Availability & Archive

### Synoptic Times
- **Available:** 00Z (midnight UTC) only
- **Not Available:** 06Z, 12Z, 18Z (return HTTP 403 Forbidden)
- **Frequency:** One analysis per day (00Z cycle)

### Historical Archive
- **Archive Start:** 2011-01-08 (at minimum)
- **Format:** YYMMDD date format (YYWW notation not supported)
- **Access:** Same URL pattern with different dates

### Example Archive URLs
```
2025-10-15:  https://www.spc.noaa.gov/obswx/maps/250_251015_00.gif
2025-10-14:  https://www.spc.noaa.gov/obswx/maps/250_251014_00.gif
2025-10-13:  https://www.spc.noaa.gov/obswx/maps/250_251013_00.gif
```

---

## Testing Summary

### Current Working Endpoints (2025-10-16)
| Endpoint | Format | HTTP Status | Size |
|----------|--------|-------------|------|
| 250mb GIF | GIF | 200 OK | 48,442 bytes |
| 250mb PDF | PDF | 200 OK | - |
| 500mb GIF | GIF | 200 OK | 41,902 bytes |
| 500mb PDF | PDF | 200 OK | - |

### Unavailable Times
| Time | Format | HTTP Status | Reason |
|------|--------|-------------|--------|
| 06Z | Any | 403 Forbidden | Not produced |
| 12Z | Any | 403 Forbidden | Not produced |
| 18Z | Any | 403 Forbidden | Not produced |

### File Metadata (2025-10-16)
```
250mb GIF:
  Content-Type: image/gif
  Last-Modified: Thu, 16 Oct 2025 02:12:52 GMT
  Content-Length: 48,442 bytes

500mb GIF:
  Content-Type: image/gif
  Last-Modified: Thu, 16 Oct 2025 02:12:52 GMT
  Content-Length: 41,902 bytes
```

---

## Implementation Recommendations

### For Configuration Files

```yaml
# config/config.yaml
data_sources:
  upper_air:
    provider: "SPC (NOAA/NCEP)"
    description: "Upper air analysis maps"
    urls:
      - name: "250mb_jet_stream"
        url: "https://www.spc.noaa.gov/obswx/maps/250_{date}_00.gif"
        format: "gif"
        template_vars:
          date: "YYMMDD"
        description: "250mb jet stream analysis"
      - name: "500mb_heights"
        url: "https://www.spc.noaa.gov/obswx/maps/500_{date}_00.gif"
        format: "gif"
        template_vars:
          date: "YYMMDD"
        description: "500mb geopotential height analysis"
    update_frequency: "daily"
    synoptic_times: ["00Z"]  # Only 00Z available
    archive_available: true
    archive_start_date: "20110108"
```

### For Agent Implementation

#### Template Expansion Logic
```python
from datetime import datetime, timedelta

def expand_upper_air_url(template_url: str, date: datetime = None) -> str:
    """
    Expand SPC upper air URL template with current or specified date.

    Args:
        template_url: URL with {date} placeholder (format: "YYMMDD")
        date: Optional specific date (defaults to today UTC)

    Returns:
        Expanded URL with actual date
    """
    if date is None:
        date = datetime.utcnow()

    # Format as YYMMDD
    date_str = date.strftime("%y%m%d")
    return template_url.replace("{date}", date_str)

# Example usage
template = "https://www.spc.noaa.gov/obswx/maps/250_{date}_00.gif"
url = expand_upper_air_url(template)
# Returns: https://www.spc.noaa.gov/obswx/maps/250_251016_00.gif
```

#### Date Resolution for Fallback
```python
def get_most_recent_upper_air_analysis(date: datetime = None) -> datetime:
    """
    Get the most recent 00Z analysis before or on specified date.

    Args:
        date: Target date (defaults to today UTC)

    Returns:
        Date of most recent analysis in UTC
    """
    if date is None:
        date = datetime.utcnow()

    # Analysis only available at 00Z
    # If current time < 02:00 UTC, use yesterday's 00Z analysis
    if date.hour < 2:
        date = date - timedelta(days=1)

    # Return midnight UTC of the analysis day
    return date.replace(hour=0, minute=0, second=0, microsecond=0)

# Example: If current time is 2025-10-16 01:30 UTC
# Returns: 2025-10-15 00:00 UTC (yesterday's analysis)
```

---

## Alternative Sources (Reference)

### Weather.gov Upper Air Archives
- **Status:** Limited/Alternative
- **URL:** https://www.weather.gov/jetstream
- **Content:** Educational resources on upper air charts
- **Note:** More for educational than real-time operational use

### Colorado State University Archive
- **Source:** WPC page references (not directly tested)
- **Pattern:** `http://archive.atmos.colostate.edu/data/misc/QHTA11/{YY}/{MM}/{YYMMDD}QHTA11.png`
- **Status:** Legacy/reference only

### NCEP GDAS (Global Data Assimilation System)
- **Status:** Raw model analysis data (not pre-rendered images)
- **URL:** Via NOAA Air Resources Lab or UCAR archive
- **Note:** Would require additional processing/visualization

---

## Comparison with Old Endpoints

### Previous (Now Broken)
```
https://www.wpc.ncep.noaa.gov/noaa/noaa250_curr.gif  (HTTP 404)
https://www.wpc.ncep.noaa.gov/noaa/noaa500_curr.gif  (HTTP 404)
```

### Replacement (Working)
```
https://www.spc.noaa.gov/obswx/maps/250_YYMMDD_00.gif  (HTTP 200)
https://www.spc.noaa.gov/obswx/maps/500_YYMMDD_00.gif  (HTTP 200)
```

### Key Differences
| Aspect | Old (WPC) | New (SPC) |
|--------|-----------|----------|
| Organization | WPC | SPC |
| Update Frequency | Unknown | Daily at 00Z |
| Archive Support | Limited | Full support |
| Date Format | Implicit (current) | Explicit YYMMDD |
| Synoptic Times | Unknown | 00Z only |
| File Format | GIF only | GIF & PDF |

---

## Production Deployment Notes

### Validation Checklist
- [x] Endpoints return HTTP 200
- [x] File sizes reasonable (41-48 KB for GIFs)
- [x] Last-Modified timestamps current
- [x] Archive accessible for historical dates
- [x] Proper MIME types (image/gif, application/pdf)
- [x] No authentication required
- [x] No rate limiting observed

### Error Handling
```python
# Fallback strategy
PRIMARY_URLS = [
    "https://www.spc.noaa.gov/obswx/maps/250_{date}_00.gif",
    "https://www.spc.noaa.gov/obswx/maps/250_{date}_00.pdf",
]

FALLBACK_URLS = [
    # Use previous day if current day fails
    "https://www.spc.noaa.gov/obswx/maps/250_{date_minus_1}_00.gif",
]
```

### Rate Limiting / Caching
- No observed rate limiting
- Recommend HTTP 304 caching headers if available
- Archive is static (old files won't change)

---

## Testing Commands

### Quick Validation
```bash
# Test current 250mb GIF
curl -I "https://www.spc.noaa.gov/obswx/maps/250_$(date +%y%m%d)_00.gif"

# Test current 500mb GIF
curl -I "https://www.spc.noaa.gov/obswx/maps/500_$(date +%y%m%d)_00.gif"

# Download image
curl -o 250mb_analysis.gif "https://www.spc.noaa.gov/obswx/maps/250_$(date +%y%m%d)_00.gif"
```

### Archive Testing
```bash
# Test October 15, 2025
curl -I "https://www.spc.noaa.gov/obswx/maps/250_251015_00.gif"

# Test October 1, 2025
curl -I "https://www.spc.noaa.gov/obswx/maps/250_251001_00.gif"

# Test January 8, 2011 (earliest confirmed date)
curl -I "https://www.spc.noaa.gov/obswx/maps/250_110108_00.gif"
```

---

## References

- **SPC Upper Air Maps:** https://www.spc.noaa.gov/obswx/maps/
- **WPC Upper Air Page:** https://www.wpc.ncep.noaa.gov/sfc/upper-air.html
- **NOAA Weather Prediction Center:** https://www.wpc.ncep.noaa.gov/
- **Storm Prediction Center:** https://www.spc.noaa.gov/

---

## Document History

| Date | Change |
|------|--------|
| 2025-10-16 | Initial discovery and testing; SPC endpoints identified as working replacements |
