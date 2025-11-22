# Upper Air Analysis URLs - Quick Reference

## Working Endpoints Summary

### 250mb Jet Stream Analysis
```
Primary:   https://www.spc.noaa.gov/obswx/maps/250_YYMMDD_00.gif
Alternate: https://www.spc.noaa.gov/obswx/maps/250_YYMMDD_00.pdf
```

### 500mb Height Analysis
```
Primary:   https://www.spc.noaa.gov/obswx/maps/500_YYMMDD_00.gif
Alternate: https://www.spc.noaa.gov/obswx/maps/500_YYMMDD_00.pdf
```

### Date Format: YYMMDD
- YY = 2-digit year (25 = 2025)
- MM = 2-digit month (01-12)
- DD = 2-digit day (01-31)

### Examples
```
2025-10-16: 251016
2025-10-15: 251015
2025-01-01: 250101
2024-12-25: 241225
```

## Live Testing

### Test Today's Analysis
```bash
DATE=$(date +%y%m%d)
curl -I "https://www.spc.noaa.gov/obswx/maps/250_${DATE}_00.gif"
curl -I "https://www.spc.noaa.gov/obswx/maps/500_${DATE}_00.gif"
```

### Download Today's Images
```bash
DATE=$(date +%y%m%d)
curl -o 250mb_${DATE}.gif "https://www.spc.noaa.gov/obswx/maps/250_${DATE}_00.gif"
curl -o 500mb_${DATE}.gif "https://www.spc.noaa.gov/obswx/maps/500_${DATE}_00.gif"
```

## Key Facts

- **Provider:** SPC (Storm Prediction Center) - NOAA/NCEP
- **Update Frequency:** Daily (00Z cycle only)
- **Available Times:** 00Z only (06Z/12Z/18Z not available)
- **Archive:** Back to 2011-01-08 minimum
- **File Format:** GIF (48 KB) or PDF
- **No Auth Required:** Public access
- **No Rate Limiting:** Observed

## Deprecation

### Old Broken Endpoints (DO NOT USE)
```
https://www.wpc.ncep.noaa.gov/noaa/noaa250_curr.gif  ✗ 404
https://www.wpc.ncep.noaa.gov/noaa/noaa500_curr.gif  ✗ 404
```

## Implementation Template

### Python

```python
from datetime import datetime

def get_upper_air_url(level: int, date: datetime = None) -> str:
    """Get SPC upper air analysis URL for 250mb or 500mb"""
    if date is None:
        date = datetime.utcnow()

    date_str = date.strftime("%y%m%d")
    return f"https://www.spc.noaa.gov/obswx/maps/{level}_{date_str}_00.gif"

# Usage
url_250 = get_upper_air_url(250)  # Today's 250mb
url_500 = get_upper_air_url(500)  # Today's 500mb
```

### Bash

```bash
#!/bin/bash
DATE=$(date +%y%m%d)
LEVEL=${1:-250}

echo "https://www.spc.noaa.gov/obswx/maps/${LEVEL}_${DATE}_00.gif"

# Usage
# ./get_upper_air.sh 250  # Get 250mb URL
# ./get_upper_air.sh 500  # Get 500mb URL
```

## Status History

| Status | Date | Details |
|--------|------|---------|
| ✓ Working | 2025-10-16 | SPC endpoints confirmed operational |
| ✗ Broken | 2025-10-16 | Original WPC endpoints (noaa250_curr.gif, noaa500_curr.gif) return 404 |

## Support / Questions

See `/docs/upper_air_analysis_endpoints.md` for full technical documentation.

Contact: SPC at https://www.spc.noaa.gov/ or WPC at https://www.wpc.ncep.noaa.gov/
