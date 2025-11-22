# NOAA WaveWatch III (WW3) Hawaii Endpoint Research
**Date:** 2025-10-16
**Status:** Complete

## Executive Summary

The original NOMADS WW3 multi_1 point guidance endpoints have been **decommissioned** as of February 2021. The multi_1 model was replaced by GFS-coupled wave model (GFSv16). The old CSV point forecast files at `nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.*` are **no longer available**.

### Key Findings

1. **NOMADS multi_1 endpoints are DEAD** (404 responses for all recent dates)
2. **Wave data moved to GFS directory structure** (as of 2021)
3. **PacIOOS ERDDAP offers excellent alternative** (operational, updated hourly)
4. **NWS API provides forecast data** (JSON format, by lat/lon)

---

## Current Operational WW3 Models (2025)

### 1. GFS-Wave (Operational Global Model)
- **Replaced:** multi_1 (decommissioned Feb 2021)
- **Coupled with:** GFS v16 atmospheric model
- **Resolution:** 0.25° x 0.25°
- **Cycles:** 4 per day (00Z, 06Z, 12Z, 18Z)
- **Forecast horizon:** 384 hours (16 days)
- **Directory structure:** `gfs.YYYYMMDD/CC/wave/`
- **Data format:** GRIB2

### 2. GEFS-Wave (Ensemble System)
- **Members:** 30 ensemble members + 1 control
- **Cycles:** 4 per day (00Z, 06Z, 12Z, 18Z)
- **Resolution:** 0.25° x 0.25°
- **Forecast horizon:** 16 days
- **Directory:** `gefs.YYYYMMDD/CC/wave/`

### 3. PacIOOS Regional Models (University of Hawaii)
**Hawaii Regional WW3:**
- Resolution: ~5 km (0.05°)
- Forecast: 5-day hourly
- Forced by: UH mesoscale atmospheric model

**Northwestern Hawaiian Islands (NWHI) WW3:**
- Resolution: ~5 km (0.05°)
- Forecast: 5-day hourly

**Global WW3 (boundary conditions):**
- Resolution: ~50 km (0.5°)
- Forecast: 5-day hourly
- Forced by: NCEP GFS winds

---

## Working Alternative Endpoints

### Option 1: PacIOOS ERDDAP (RECOMMENDED)

**Advantages:**
- ✅ CSV output available
- ✅ Currently operational (verified 2025-10-16)
- ✅ Hourly updates
- ✅ Data through 2025-10-22
- ✅ High-resolution Hawaii regional model
- ✅ RESTful API with constraint-based queries

**Base ERDDAP Servers:**
- Primary: `https://pae-paha.pacioos.hawaii.edu/erddap/`
- Mirror: `https://upwell.pfeg.noaa.gov/erddap/`

**Available Datasets:**

| Dataset ID | Description | Resolution | Coverage |
|-----------|-------------|-----------|----------|
| `ww3_hawaii` | Hawaii Regional | 0.05° (~5km) | 18-23°N, 199-206°E |
| `ww3_nwhi` | NW Hawaiian Islands | 0.05° (~5km) | Regional |
| `ww3_global` | Global Model | 0.5° (~50km) | Global |

**Data Access Methods:**

1. **GridDAP CSV Export:**
```bash
# Format: dataset.csv?var1,var2[(time)][(lat_min):(lat_max)][(lon_min):(lon_max)]
https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir[(last)][(20):(22)][(200):(203)]
```

2. **CSVP Format (CSV with units in parentheses):**
```bash
https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csvp?Thgt[(last)][(21)][(202)]
```

3. **JSON Export:**
```bash
https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.json?time,Thgt,Tper,Tdir[(last)][(20):(22)][(200):(203)]
```

4. **Dataset Metadata/Info:**
```bash
https://pae-paha.pacioos.hawaii.edu/erddap/info/ww3_hawaii/index.json
```

**Available Variables:**
- `Thgt` - Significant wave height (meters)
- `Tper` - Peak wave period (seconds)
- `Tdir` - Peak wave direction (degrees)
- `shgt` - Swell height (meters)
- `sper` - Swell period (seconds)
- `sdir` - Swell direction (degrees)
- `whgt` - Wind wave height (meters)
- `wper` - Wind wave period (seconds)
- `wdir` - Wind wave direction (degrees)

**Time Coverage:**
- Start: 2011-06-21T21:00:00Z
- End: 2025-10-22T18:00:00Z (updates hourly)
- Resolution: PT1H (hourly)

**Point Extraction Examples:**

North Shore (21.7°N, 201.9°W = 158.1°W):
```bash
curl "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir[(last)][(21.5):(22)][(201.5):(202)]"
```

South Shore (21.3°N, 202.1°W = 157.9°W):
```bash
curl "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir[(last)][(21):(21.5)][(201.8):(202.3)]"
```

Multiple forecast hours:
```bash
# Get next 120 hours (5 days) of forecasts
curl "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir[(now):(now+120hours)][(21.5):(22)][(201.5):(202)]"
```

**ERDDAP Constraint Syntax:**
- `[(last)]` - Most recent timestep
- `[(now)]` - Current time
- `[(now+24hours)]` - 24 hours from now
- `[(min):(max)]` - Range of values
- `[(value)]` - Single value (nearest neighbor)
- `[(start):(stride):(end)]` - Strided access

---

### Option 2: NOAA NWS API (api.weather.gov)

**Advantages:**
- ✅ Official NOAA REST API
- ✅ JSON output
- ✅ Includes wave height, period, direction
- ✅ Free, no authentication required

**Endpoint Structure:**

1. **Get Grid Endpoint for Location:**
```bash
curl "https://api.weather.gov/points/{latitude},{longitude}"
```

Example for North Shore:
```bash
curl "https://api.weather.gov/points/21.7,-158.1" | jq '.properties.forecast'
```

2. **Fetch Forecast JSON:**
```bash
# Use the forecast URL from step 1
curl "https://api.weather.gov/gridpoints/HFO/{grid_x},{grid_y}/forecast"
```

**Wave-Specific Endpoints:**

Marine forecast zones for Hawaii:
- `https://api.weather.gov/zones/marine/AMZ110` (Kauai coastal waters)
- `https://api.weather.gov/zones/marine/AMZ111` (Oahu coastal waters)
- `https://api.weather.gov/zones/marine/AMZ112` (Maui coastal waters)

**Response Format:**
```json
{
  "properties": {
    "periods": [
      {
        "name": "Today",
        "detailedForecast": "Wave height 3 to 5 feet. Wave period 8 seconds. Wave direction from the north."
      }
    ]
  }
}
```

**Rate Limits:**
- User-Agent header required
- Reasonable rate limits (not publicly documented)

---

### Option 3: NOMADS GFS-Wave (GRIB2 Format)

**Status:** Operational but requires GRIB2 processing

**Access Points:**
- HTTPS: `https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.YYYYMMDD/CC/wave/`
- FTP: `ftpprd.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.YYYYMMDD/CC/wave/`
- OpenDAP: Available via NOMADS THREDDS server

**File Naming Convention:**
```
gfs.wave.t{CC}z.global.0p25.f{FFF}.grib2
```
- `{CC}` = Cycle (00, 06, 12, 18)
- `{FFF}` = Forecast hour (000-384)

**Example URLs:**
```bash
# Today's 00Z cycle, forecast hour 024
https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.20251016/00/wave/gridded/gfs.wave.t00z.global.0p25.f024.grib2
```

**Processing Required:**
- Download GRIB2 files
- Use `wgrib2` to extract point data
- Convert to CSV format

**wgrib2 Example:**
```bash
# Extract wave parameters at specific lat/lon
wgrib2 gfs.wave.t00z.global.0p25.f024.grib2 \
  -lon 201.9 21.7 \
  -csv wave_forecast.csv
```

**Note:** NOMADS only retains ~7 days of data

---

### Option 4: THREDDS/OPeNDAP Direct Access

**PacIOOS THREDDS Server:**
```
https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/ww3_hawaii/WaveWatch_III_Hawaii_Regional_Wave_Model_best.ncd
```

**Access via netCDF libraries:**
```python
from netCDF4 import Dataset
import numpy as np

# Open remote dataset
ds = Dataset('https://pae-paha.pacioos.hawaii.edu/thredds/dodsC/ww3_hawaii/WaveWatch_III_Hawaii_Regional_Wave_Model_best.ncd')

# Get variables
time = ds.variables['time'][:]
lat = ds.variables['latitude'][:]
lon = ds.variables['longitude'][:]
wave_height = ds.variables['Thgt'][:,:,:,:]  # (time, depth, lat, lon)
```

**Advantages:**
- Direct array access
- Subsetting capabilities
- Efficient for programmatic access

---

## Deprecated Endpoints (DO NOT USE)

### ❌ NOMADS WW3 multi_1 (DEAD)
```bash
# THESE RETURN 404
https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.{date}/points/hawaii/wvprbl_hi.{date}.t00z.csv
https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.{date}/points/hawaii/wvprbl_hi.{date}.t12z.csv
```

**Verification:**
```bash
# Tested 2025-10-12 through 2025-10-16 - all return 404
for DATE in 20251012 20251013 20251014 20251015 20251016; do
  curl -I "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.${DATE}/"
done
# All responses: HTTP/2 404
```

**Reason:** Model decommissioned February 2021, replaced by GFS-Wave

### ❌ FTP Fallbacks (Blocked)
```bash
# These return 403 Forbidden
https://ftpprd.ncep.noaa.gov/pub/data/nccf/com/gefs/prod/
https://ftpprd.ncep.noaa.gov/pub/data/nccf/com/wave/prod/
```

---

## Recommended Implementation Strategy

### Phase 1: Immediate Fix (PacIOOS ERDDAP)

**Update config/config.yaml:**
```yaml
data_sources:
  models:
    name: "WW3 Hawaii Regional Model"
    urls:
      - url_template: "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir,shgt,sper,sdir,whgt,wper,wdir[(last)][(20):(23)][(199):(206)]"
        source: "pacioos_erddap"
        format: "csv"
      - url_template: "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_global.csv?time,Thgt,Tper,Tdir[(last)][(15):(30)][(190):(210)]"
        source: "pacioos_global"
        format: "csv"
        fallback: true
```

**Update src/agents/model_agent.py:**
```python
def _parse_erddap_csv(self, csv_content: str) -> dict:
    """Parse PacIOOS ERDDAP CSV format."""
    lines = csv_content.strip().split('\n')

    # Line 0: variable names with units
    # Line 1+: data rows
    headers = lines[0].split(',')

    forecasts = []
    for line in lines[1:]:
        values = line.split(',')
        point = dict(zip(headers, values))
        forecasts.append({
            'timestamp': point.get('time (UTC)'),
            'wave_height': float(point.get('Thgt (meters)', 0)),
            'wave_period': float(point.get('Tper (second)', 0)),
            'wave_direction': float(point.get('Tdir (degrees)', 0)),
            'swell_height': float(point.get('shgt (meters)', 0)),
            'swell_period': float(point.get('sper (seconds)', 0)),
            'swell_direction': float(point.get('sdir (degrees)', 0)),
            'latitude': float(point.get('latitude (degrees_north)', 0)),
            'longitude': float(point.get('longitude (degrees_east)', 0))
        })

    return {
        'source': 'pacioos_ww3_hawaii',
        'forecast_points': forecasts,
        'model': 'WW3 Hawaii Regional 0.05deg',
        'resolution': '5km',
        'update_frequency': 'hourly'
    }
```

### Phase 2: Point-Specific Queries

For key surf spots, use targeted ERDDAP queries:

```python
SURF_SPOTS = {
    'north_shore': {'lat': 21.7, 'lon': 201.9},  # Haleiwa
    'south_shore': {'lat': 21.3, 'lon': 202.1},  # Waikiki
    'west_side': {'lat': 21.5, 'lon': 201.5},    # Makaha
}

def get_spot_forecast(spot_name: str, hours_ahead: int = 120):
    """Get wave forecast for specific surf spot."""
    coords = SURF_SPOTS[spot_name]
    lat, lon = coords['lat'], coords['lon']

    url = (
        f"https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv"
        f"?time,Thgt,Tper,Tdir,shgt,sper,sdir"
        f"[(now):(now+{hours_ahead}hours)]"
        f"[({lat-0.1}):({lat+0.1})]"
        f"[({lon-0.1}):({lon+0.1})]"
    )

    response = requests.get(url)
    return parse_erddap_csv(response.text)
```

### Phase 3: Fallback Chain

Implement cascading fallback strategy:

1. **Primary:** PacIOOS Hawaii Regional (5km)
2. **Secondary:** PacIOOS Global (50km)
3. **Tertiary:** NWS API (forecast text parsing)
4. **Last Resort:** NOMADS GFS-Wave GRIB2 (requires wgrib2)

```python
def fetch_ww3_data(self) -> dict:
    """Fetch WW3 data with fallback chain."""

    # Try PacIOOS Hawaii Regional
    try:
        return self._fetch_pacioos_regional()
    except Exception as e:
        logger.warning(f"PacIOOS regional failed: {e}")

    # Try PacIOOS Global
    try:
        return self._fetch_pacioos_global()
    except Exception as e:
        logger.warning(f"PacIOOS global failed: {e}")

    # Try NWS API
    try:
        return self._fetch_nws_api()
    except Exception as e:
        logger.warning(f"NWS API failed: {e}")

    raise DataSourceError("All WW3 sources failed")
```

---

## Testing & Validation

### Endpoint Health Checks

```bash
#!/bin/bash
# test_ww3_endpoints.sh

echo "Testing PacIOOS ERDDAP Hawaii Regional..."
curl -I "https://pae-paha.pacioos.hawaii.edu/erddap/info/ww3_hawaii/index.json" 2>&1 | grep HTTP

echo "Testing PacIOOS ERDDAP Global..."
curl -I "https://pae-paha.pacioos.hawaii.edu/erddap/info/ww3_global/index.json" 2>&1 | grep HTTP

echo "Testing NWS API..."
curl -I "https://api.weather.gov/points/21.7,-158.1" 2>&1 | grep HTTP

echo "Testing NOMADS multi_1 (should be 404)..."
DATE=$(date -u +%Y%m%d)
curl -I "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.${DATE}/" 2>&1 | grep HTTP
```

### Sample Data Extraction

```bash
# Get current North Shore forecast
curl -s "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?time,Thgt,Tper,Tdir[(last)][(21.6):(21.8)][(201.8):(202)]" | head -5

# Expected output:
# time (UTC),depth (m),latitude (degrees_north),longitude (degrees_east),Tdir (degrees),Tper (second),Thgt (meters)
# 2025-10-16T12:00:00Z,0.0,21.65,201.9,315.5,12.8,3.2
```

### Unit Tests

```python
# tests/unit/agents/test_model_agent_pacioos.py

def test_pacioos_erddap_parsing():
    """Test ERDDAP CSV parsing."""
    csv_data = """time (UTC),Thgt (meters),Tper (second),Tdir (degrees)
2025-10-16T12:00:00Z,3.2,12.8,315.5
2025-10-16T13:00:00Z,3.3,12.9,316.0"""

    agent = ModelAgent()
    result = agent._parse_erddap_csv(csv_data)

    assert result['source'] == 'pacioos_ww3_hawaii'
    assert len(result['forecast_points']) == 2
    assert result['forecast_points'][0]['wave_height'] == 3.2
    assert result['forecast_points'][0]['wave_period'] == 12.8

def test_endpoint_availability():
    """Verify PacIOOS endpoints are responding."""
    response = requests.get(
        "https://pae-paha.pacioos.hawaii.edu/erddap/info/ww3_hawaii/index.json"
    )
    assert response.status_code == 200

    data = response.json()
    assert 'table' in data

    # Check time coverage extends to current date
    time_coverage = [r for r in data['table']['rows']
                    if r[1] == 'time_coverage_end'][0][3]
    assert '2025' in time_coverage
```

---

## Resources & Documentation

### Official Documentation
- **PacIOOS ERDDAP:** https://pae-paha.pacioos.hawaii.edu/erddap/information.html
- **ERDDAP API Guide:** https://coastwatch.pfeg.noaa.gov/erddap/rest.html
- **NWS API Docs:** https://www.weather.gov/documentation/services-web-api
- **WW3 Model Info:** https://polar.ncep.noaa.gov/waves/wavewatch/

### Key Contacts
- **Marine Modeling Branch:** ncep.list.waves@noaa.gov
- **PacIOOS Support:** info@pacioos.hawaii.edu

### Model Transition History
- **Feb 2021:** WW3 multi_1 decommissioned
- **Mar 2021:** GFS v16 with coupled wave model operational
- **2021-present:** Wave data in GFS directory structure

### Data Retention
- **PacIOOS ERDDAP:** 2011-present (full archive)
- **NOMADS GFS-Wave:** ~7 days rolling
- **NWS API:** Current forecast only

---

## Implementation Checklist

- [ ] Update `config/config.yaml` with PacIOOS ERDDAP URLs
- [ ] Modify `ModelAgent._fetch_ww3_data()` to use ERDDAP
- [ ] Add `_parse_erddap_csv()` method
- [ ] Implement fallback chain (regional → global → NWS)
- [ ] Add endpoint health checks to monitoring
- [ ] Update unit tests for ERDDAP format
- [ ] Remove references to deprecated multi_1 endpoints
- [ ] Document new data schema in SPEC.md
- [ ] Test with live data collection
- [ ] Verify forecast metadata includes WW3 summaries

---

## Conclusion

**The NOMADS multi_1 point guidance endpoints are permanently unavailable.** The recommended solution is to migrate to **PacIOOS ERDDAP** for WW3 Hawaii data access:

✅ **Operational** (verified 2025-10-16)
✅ **CSV format** (drop-in replacement)
✅ **Hourly updates** (same as original multi_1)
✅ **Higher resolution** (5km vs 50km)
✅ **Full forecast horizon** (120+ hours)
✅ **RESTful API** (easy integration)

This provides superior data quality compared to the legacy multi_1 system while maintaining compatibility with existing forecast pipelines.
