# Data Feed Implementation Plan

## Root Cause Identified
The `wvprbl_hi.{date}.t{hour}z.csv` files were **discontinued in March 2022** when NOAA unified WaveWatch III into GFS-Wave. The old `/com/wave/prod/` path is obsolete.

## Implementation Priority

### Phase 1: PacIOOS ERDDAP (Primary - Drop-in CSV Replacement)
**Timeline: Immediate**

PacIOOS provides Hawaii-specific WW3 at 5km resolution with CSV/JSON output - perfect replacement.

```yaml
# config/config.yaml update
models:
  pacioos_ww3:
    enabled: true
    priority: 1
    urls:
      # 7-day forecast, hourly, Hawaii region
      - "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?Thgt,Tdir,Tper[(now):1:(now+7days)][(0.0)][(19):1:(23)][(-161):1:(-154)]"
    format: csv
    variables:
      - Thgt  # Significant wave height (Hs)
      - Tdir  # Wave direction
      - Tper  # Peak period
    update_frequency: "daily ~13:30 HST"
    forecast_horizon: 168  # 7 days in hours
```

**Code changes needed:**
1. `src/agents/model_agent.py` - Add PacIOOS CSV parser
2. `src/processing/wave_model_processor.py` - Handle PacIOOS format

### Phase 2: GFS-Wave GRIB2 via AWS S3 (Extended 16-day)
**Timeline: Week 1**

For extended forecasts beyond PacIOOS's 7 days:

```yaml
models:
  gfs_wave:
    enabled: true
    priority: 2
    urls:
      # AWS S3 - no NOMADS dependency
      - "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{date}/{hour}/wave/gridded/gfswave.t{hour}z.epacif.0p16.f{fhour}.grib2"
    format: grib2
    region:
      name: "Hawaii"
      lat_min: 19
      lat_max: 23
      lon_min: 199  # 360-161
      lon_max: 206  # 360-154
    forecast_hours: [0, 24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336, 360, 384]
    update_frequency: "6 hours"
    forecast_horizon: 384  # 16 days
```

**Code changes needed:**
1. Add `pygrib` or `cfgrib` dependency for GRIB2 parsing
2. Create `src/agents/gfs_wave_agent.py`

### Phase 3: Open-Meteo Marine (Backup/Redundancy)
**Timeline: Week 1**

Already partially integrated. Enhance for extended forecasts:

```yaml
models:
  open_meteo:
    enabled: true
    priority: 3
    urls:
      - "https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_period,swell_wave_direction&forecast_days=16"
    format: json
    locations:
      - {lat: 21.7, lon: -158.0, name: "North Shore"}
      - {lat: 21.3, lon: -157.9, name: "South Shore"}
      - {lat: 21.5, lon: -158.2, name: "West Shore"}
```

### Phase 4: Storm Tracking (Pressure/Backstory)
**Timeline: Week 2**

Add GFS MSLP for storm genesis backstory:

```yaml
storm_tracking:
  gfs_pressure:
    enabled: true
    urls:
      # NW Pacific storm region (30-60°N, 140-180°E)
      - "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?file=gfs.t{hour}z.pgrb2.0p25.f000&var_PRMSL=on&subregion=&leftlon=140&rightlon=180&toplat=60&bottomlat=30&dir=/gfs.{date}/{hour}/atmos"
    format: grib2
    variables:
      - PRMSL  # Mean sea level pressure
      - UGRD   # U-component wind
      - VGRD   # V-component wind
    tracking_region:
      name: "Aleutian Storm Track"
      lat_min: 40
      lat_max: 55
      lon_min: 150
      lon_max: 180
```

**Code changes needed:**
1. Create `src/agents/storm_tracker_agent.py`
2. Add storm detection algorithm (find pressure minima < 990 mb)
3. Calculate great-circle distance to Hawaii
4. Estimate swell arrival time (distance / group velocity)

---

## File Changes Required

### 1. config/config.yaml
```yaml
# ADD new data sources section
data_sources:
  models:
    # Remove old NOMADS WW3 URLs (obsolete)
    # urls:
    #   - "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.{date}..."  # OBSOLETE

    pacioos:
      enabled: true
      type: "ww3_hawaii"
      url: "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv"
      format: "csv"
      forecast_days: 7

    gfs_wave:
      enabled: true
      type: "gfs_wave_epacif"
      url: "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{date}/{hour}/wave/gridded/"
      format: "grib2"
      forecast_days: 16

    open_meteo:
      enabled: true
      type: "marine_api"
      url: "https://marine-api.open-meteo.com/v1/marine"
      format: "json"
      forecast_days: 16
```

### 2. src/agents/model_agent.py
- Remove old NOMADS WW3 CSV logic
- Add PacIOOS ERDDAP CSV parser
- Add fallback chain: PacIOOS → GFS-Wave → Open-Meteo

### 3. src/agents/pacioos_agent.py (NEW)
```python
class PacIOOSAgent:
    """Fetch Hawaii WW3 data from PacIOOS ERDDAP."""

    BASE_URL = "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii"

    async def fetch_forecast(self, days: int = 7) -> dict:
        # Build ERDDAP query for Thgt, Tdir, Tper
        # Parse CSV response
        # Return standardized wave forecast dict
```

### 4. src/agents/storm_tracker_agent.py (NEW)
```python
class StormTrackerAgent:
    """Track NW Pacific lows for storm backstory."""

    async def detect_storms(self) -> list[Storm]:
        # Fetch GFS MSLP for NW Pacific
        # Find pressure minima < 990 mb
        # Track movement and deepening
        # Calculate distance to Hawaii
        # Estimate arrival time
```

### 5. src/forecast_engine/context_builder.py
- Add storm backstory section from StormTrackerAgent
- Include: pressure (mb), location, distance (nm), fetch info

---

## Validation Tests

### Test 1: PacIOOS ERDDAP Connectivity
```bash
curl -I "https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.csv?Thgt[(last)][(0.0)][(21.5)][(-158)]"
# Expected: HTTP 200
```

### Test 2: AWS S3 GFS-Wave Access
```bash
curl -I "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.$(date -u +%Y%m%d)/00/wave/gridded/"
# Expected: HTTP 200 with directory listing
```

### Test 3: Storm Detection
```bash
# Fetch current NW Pacific MSLP and check for lows
curl "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?file=gfs.t00z.pgrb2.0p25.f000&var_PRMSL=on&subregion=&leftlon=140&rightlon=180&toplat=60&bottomlat=30&dir=/gfs.$(date -u +%Y%m%d)/00/atmos" -o test_mslp.grib2
```

---

## Success Criteria

After implementation:
1. [ ] Model feed success rate > 90% (currently 0%)
2. [ ] Forecast horizon extended to 7+ days (currently 3 days)
3. [ ] Sunday 11/30 giant swell detected in extended forecast
4. [ ] Storm backstory includes: pressure (mb), location, distance (nm)
5. [ ] Historical context ("On this day...") appears in output

---

## Dependencies to Add

```bash
# requirements.txt additions
cfgrib>=0.9.10  # GRIB2 parsing via xarray
eccodes>=1.5.0  # ECMWF GRIB library
xarray>=2023.0  # For ERDDAP/NetCDF handling
```

---

## Rollback Plan

If new feeds fail:
1. Open-Meteo Marine API is already working (basic coverage)
2. NDBC buoys provide real-time validation
3. Can fall back to buoy-only forecasts with reduced horizon

---

*Created: 2025-11-26*
*Based on research from DATA_SOURCE_RESEARCH_PROMPT.md*
