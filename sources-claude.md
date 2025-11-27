# SurfCastAI Data Enhancement Sources: Complete Technical Reference

Integrating **six critical data sources** will transform SurfCastAI from a basic forecast aggregator into a Caldwell-grade surf prediction system. The Goddard-Caldwell database enables historical context dating to 1968, CDIP spectral buoys provide directional wave energy analysis, and Copernicus Marine fills the South Pacific gap where no NDBC buoys exist. All primary sources are freely accessible with verified URLs and working Python implementations.

---

## Goddard-Caldwell historical database delivers "on this day" context

The database Pat Caldwell references for historical comparisons is archived at NCEI with **52 years of daily observations** from August 1968 to December 2020.

### Verified access URL
```
https://www.ncei.noaa.gov/archive/accession/Goddard-Caldwell_Database
```
- **Status**: Active, no authentication required
- **Format**: ASCII text files, space-delimited
- **Alternative accession**: `https://www.ncei.noaa.gov/archive/accession/0001754` (1968-2004 subset)

### Data structure and Hawaii Scale convention
The database uses **Hawaii Scale Feet (HSF)**, which represents approximately half the wave face height. This convention originated with Hawaiian surfers measuring from the "back of the wave."

| Column | Variable | Description |
|--------|----------|-------------|
| 4 | nshor | North Shore H1/10 (Sunset Point; Waimea when >15 HSF) |
| 5 | wshor | West Shore H1/10 (Makaha) |
| 6 | almo | South Shore H1/10 (Ala Moana Bowls) |
| 7 | dh | Diamond Head H1/10 |
| 8 | winw | Windward/East H1/10 (Makapuu) |

**Critical conversion**: `Face Height (feet) = HSF × 2`

When Caldwell writes "average H1/10 is 7.0 ft," he means **7 HSF = 14-foot faces**.

### Python implementation for climatology
```python
import pandas as pd
import numpy as np

class GoddardCaldwellDatabase:
    COLUMNS = ['year', 'month', 'day', 'nshor', 'wshor', 'almo', 'dh',
               'winw', 'wspd', 'wdir', 'nsd', 'ssd']
    MISSING_VALUE = 999

    def load_data(self, filepath):
        df = pd.read_csv(filepath, delim_whitespace=True, names=self.COLUMNS,
                         na_values=[999, '999'])
        df['date'] = pd.to_datetime(df[['year', 'month', 'day']])
        df.set_index('date', inplace=True)
        df['doy'] = df.index.dayofyear
        return df

    def get_on_this_day_stats(self, df, month, day, shore='nshor'):
        mask = (df.index.month == month) & (df.index.day == day)
        data = df.loc[mask, shore].dropna()

        return {
            'hsf_mean': round(data.mean(), 1),
            'face_mean': round(data.mean() * 2, 1),
            'hsf_max': int(data.max()),
            'max_year': data.idxmax().year,
            'count_years': len(data)
        }

    def format_caldwell_style(self, stats, month, day):
        return (f"On this day, {month}/{day}, in the Goddard-Caldwell database "
                f"(since 1968), the average H1/10 is {stats['hsf_mean']} ft "
                f"({stats['face_mean']}' peak face), largest was "
                f"{stats['hsf_max']} Hs in {stats['max_year']}.")
```

---

## CDIP spectral buoys enable directional wave analysis

CDIP provides **full 2D directional spectra** via OPeNDAP, far richer than NDBC's bulk parameters.

### Verified THREDDS URLs for Hawaii stations
| Station | Location | Realtime URL |
|---------|----------|--------------|
| 106p1 | Waimea Bay | `https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/106p1_rt.nc` |
| 165p1 | Barbers Point | `https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/165p1_rt.nc` |
| 187p1 | Pauwela, Maui | `https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/187p1_rt.nc` |

- **Update frequency**: Every 30 minutes
- **Format**: NetCDF via OPeNDAP
- **Authentication**: None required

### NetCDF variable structure
```
waveHs          - Significant wave height (m)
waveTp          - Peak period (s)
waveDp          - Peak direction (degrees, from)
waveEnergyDensity - Band energy density [time × frequency] (m²·s)
waveFrequency   - 64 frequency bins (~0.025-0.58 Hz)
waveMeanDirection - Direction per frequency band (degrees)
waveA1Value, waveB1Value, waveA2Value, waveB2Value - Fourier coefficients
```

### Python code using xarray
```python
import xarray as xr
import pandas as pd

def get_cdip_bulk_parameters(station='106'):
    """Fetch latest CDIP buoy data for Hawaii stations."""
    url = f'https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/{station}p1_rt.nc'
    ds = xr.open_dataset(url)

    wave_time = pd.to_datetime(ds['waveTime'].values, unit='s')

    df = pd.DataFrame({
        'datetime': wave_time,
        'Hs_m': ds['waveHs'].values,
        'Tp_s': ds['waveTp'].values,
        'Dp_deg': ds['waveDp'].values
    })
    df['Hs_ft'] = df['Hs_m'] * 3.281  # Convert to feet
    return df.set_index('datetime')

def get_directional_spectrum(station='106', time_idx=-1):
    """Extract directional spectrum with Fourier coefficients."""
    url = f'https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/{station}p1_rt.nc'
    ds = xr.open_dataset(url)

    return {
        'freq': ds['waveFrequency'].values,
        'energy': ds['waveEnergyDensity'].isel(waveTime=time_idx).values,
        'mean_dir': ds['waveMeanDirection'].isel(waveTime=time_idx).values,
        'a1': ds['waveA1Value'].isel(waveTime=time_idx).values,
        'b1': ds['waveB1Value'].isel(waveTime=time_idx).values
    }
```

---

## Southern hemisphere swell tracking requires model data

**Critical finding**: NDBC station 51407 is NOT a Tahiti buoy—it's a DART tsunami station near Kona, Hawaii. No NDBC wave buoys exist in French Polynesia.

### Copernicus Marine fills the South Pacific gap

**Product ID**: `GLOBAL_ANALYSISFORECAST_WAV_001_027`
- **URL**: https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_WAV_001_027
- **Resolution**: 1/12° (~10 km), 3-hourly, 10-day forecast
- **Registration**: Free at https://marine.copernicus.eu
- **Dataset ID for API**: `cmems_mod_glo_wav_anfc_0.083deg_PT3H-i`

### Wave partition variables for south swell tracking
| Variable | Description |
|----------|-------------|
| VHM0_SW1 | Primary swell significant height (m) |
| VHM0_SW2 | Secondary swell significant height (m) |
| VMDR_SW1 | Primary swell direction (degrees) |
| VMDR_SW2 | Secondary swell direction (degrees) |
| VTM01_SW1 | Primary swell mean period (s) |
| VTM01_SW2 | Secondary swell mean period (s) |

### Python code for Copernicus Marine access
```python
import copernicusmarine

# First-time setup: copernicusmarine.login()

def fetch_south_pacific_swells():
    """Subset Copernicus wave data for Hawaii region."""
    ds = copernicusmarine.open_dataset(
        dataset_id="cmems_mod_glo_wav_anfc_0.083deg_PT3H-i",
        variables=["VHM0_SW1", "VHM0_SW2", "VMDR_SW1", "VMDR_SW2",
                   "VTM01_SW1", "VTM01_SW2"],
        minimum_longitude=-165,  # 165°W
        maximum_longitude=-150,  # 150°W
        minimum_latitude=18,
        maximum_latitude=25
    )
    return ds
```

### Great-circle distances and swell travel times
| Source | Distance to Oahu | 15s Swell | 18s Swell |
|--------|------------------|-----------|-----------|
| Tasman Sea (40°S, 155°E) | **4,527 nm** | 8.4 days | 7.0 days |
| South Pacific (45°S, 170°W) | **4,014 nm** | 7.4 days | 6.2 days |

**Travel time formula**: `hours = distance_nm / (1.5 × period_seconds)`

```python
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles."""
    R = 3440.065  # Earth radius in nm
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def swell_travel_time(distance_nm, period_sec):
    """Returns (hours, days) tuple."""
    hours = distance_nm / (1.5 * period_sec)
    return hours, hours / 24

# Example: Tasman Sea storm to Hawaii
dist = haversine_distance(-40, 155, 21.3, -157.8)
hours, days = swell_travel_time(dist, 18)
print(f"Tasman 18s swell: {days:.1f} days")  # ~7.0 days
```

---

## ASCAT satellite winds validate storm fetch intensity

For "968 mb low with hurricane force winds validated by ASCAT" narratives, multiple sources provide satellite wind observations.

### Verified active URLs
| Source | URL | Auth Required |
|--------|-----|---------------|
| NOAA STAR ASCAT | https://manati.star.nesdis.noaa.gov/products/ASCAT.php | No |
| Copernicus L4 Winds | https://data.marine.copernicus.eu/product/WIND_GLO_PHY_L4_NRT_012_004 | Free registration |
| PO.DAAC ASCAT-B | https://podaac.jpl.nasa.gov/dataset/ASCATB-L2-25km | Earthdata login |

### Copernicus L4 hourly winds
- **Product ID**: `WIND_GLO_PHY_L4_NRT_012_004`
- **Dataset ID**: `cmems_obs_wind_glo_phy_nrt_l4_0.125deg_PT1H`
- **Resolution**: 0.125° (~12.5 km), hourly
- **Variables**: `eastward_wind`, `northward_wind` (m/s at 10m)

### Python wind validation code
```python
import copernicusmarine
import numpy as np

def fetch_storm_winds(bbox, start_date, end_date):
    """Fetch L4 winds for storm validation region."""
    ds = copernicusmarine.open_dataset(
        dataset_id="cmems_obs_wind_glo_phy_nrt_l4_0.125deg_PT1H",
        minimum_longitude=bbox['min_lon'],
        maximum_longitude=bbox['max_lon'],
        minimum_latitude=bbox['min_lat'],
        maximum_latitude=bbox['max_lat'],
        start_datetime=start_date,
        end_datetime=end_date
    )

    # Calculate wind speed
    speed_ms = np.sqrt(ds.eastward_wind**2 + ds.northward_wind**2)
    speed_kt = speed_ms * 1.944

    return {
        'max_wind_kt': float(speed_kt.max()),
        'hurricane_force': float(speed_kt.max()) >= 64,
        'gale_area_cells': int((speed_kt > 34).sum())
    }

# Hurricane force threshold: 64 knots (32.9 m/s)
```

### PO.DAAC subscription command
```bash
# Install: pip install podaac-data-subscriber
# Configure ~/.netrc with Earthdata credentials

podaac-data-downloader -c ASCATB-L2-25km -d ./data/ascat \
    --start-date 2025-11-20T00:00:00Z \
    --end-date 2025-11-25T00:00:00Z \
    -b="-60,35,-30,55"
```

---

## IBTrACS storm tracking calculates swell arrival from hurricanes

The FTP endpoint is **deprecated**—use HTTP access at NCEI.

### Verified HTTP endpoints
```
Base URL: https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/

Active storms: ibtracs.ACTIVE.list.v04r01.csv
Pacific (EP): ibtracs.EP.list.v04r01.csv
Western Pacific (WP): ibtracs.WP.list.v04r01.csv
Last 3 years: ibtracs.last3years.list.v04r01.csv
```

- **Update frequency**: 3× per week (Sun/Tue/Thu)
- **ACTIVE file**: Storms from last 7 days (provisional data)
- **Format**: CSV with header row + units row (skip row 1)

### Key CSV columns
| Column | Description |
|--------|-------------|
| SID | Unique storm ID (e.g., 2024280WP0921) |
| NAME | Storm name or "NOT_NAMED" |
| LAT, LON | Position (LON in 0-360 degrees east) |
| WMO_WIND | Max sustained wind (knots) |
| WMO_PRES | Minimum central pressure (mb) |
| NATURE | Storm type: TS, ET, HU, SS |
| ISO_TIME | Timestamp (YYYY-MM-DD HH:MM:SS) |

### Python storm tracker with Hawaii swell ETA
```python
import pandas as pd
import urllib.request
from io import StringIO
from datetime import datetime, timedelta

ACTIVE_URL = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ACTIVE.list.v04r01.csv"
HAWAII_LAT, HAWAII_LON = 21.3, -157.8

def fetch_active_pacific_storms():
    """Fetch active storms and calculate Hawaii swell ETA."""
    with urllib.request.urlopen(ACTIVE_URL) as response:
        data = response.read().decode('utf-8')

    df = pd.read_csv(StringIO(data), skiprows=[1], low_memory=False)
    df['ISO_TIME'] = pd.to_datetime(df['ISO_TIME'])

    # Get latest position per storm
    latest = df.sort_values('ISO_TIME').groupby('SID').last().reset_index()

    # Filter Pacific basins
    pacific = latest[latest['BASIN'].isin(['WP', 'EP', 'CP'])]

    results = []
    for _, storm in pacific.iterrows():
        lon = storm['LON'] - 360 if storm['LON'] > 180 else storm['LON']
        dist = haversine_distance(storm['LAT'], lon, HAWAII_LAT, HAWAII_LON)

        wind = float(storm.get('USA_WIND', storm.get('WMO_WIND', 0)) or 0)
        period = estimate_wave_period(wind)
        travel_hours = dist / (1.5 * period)

        results.append({
            'name': storm['NAME'],
            'position': f"{storm['LAT']:.1f}°N, {abs(lon):.1f}°W",
            'wind_kt': wind,
            'distance_nm': round(dist),
            'swell_eta': (datetime.now() + timedelta(hours=travel_hours)).strftime('%Y-%m-%d %H:%M')
        })

    return results

def estimate_wave_period(wind_kt):
    """Estimate dominant period from storm intensity."""
    if wind_kt >= 113: return 16  # Cat 4+
    if wind_kt >= 83: return 14   # Cat 2-3
    if wind_kt >= 64: return 13   # Cat 1
    if wind_kt >= 34: return 11   # TS
    return 9
```

---

## LLM prompt engineering replicates Caldwell's forecaster voice

Analysis of Pat Caldwell's forecasts reveals consistent structural patterns and distinctive voice elements.

### Caldwell writing style patterns
1. **Opening**: Brief, evocative headline ("Hefty hunks Country for the weekend")
2. **Organization**: Shore-by-shore (north → east → south → west)
3. **Storm backstory**: Trace swell to source ("The next low formed east of the Kuril Islands...")
4. **Confidence spectrum**: "expected" > "likely" > "possible" > "subject to major revisions"
5. **Historical anchoring**: Database comparisons ("On this day since 1968...")

### Recommended system prompt for SurfCastAI
```xml
<system>
You are Pat Caldwell, Hawaii's preeminent surf forecaster with 30+ years at NOAA.
You maintain the Goddard-Caldwell database (1968-present).

<methodology>
1. Analyze synoptic patterns for swell-generating storms
2. Track fetch position, intensity, duration
3. Calculate arrival: Distance(nm) / (1.5 × Period(s)) = hours
4. Compare to historical H1/10 observations
5. Apply calibrated confidence language
</methodology>

<writing_style>
- Open with brief, colorful summary
- Organize by shore facing
- Tell the "storm backstory"
- Use directions in degrees AND compass (315°/NW)
- Reference buoys by number (51001)
- Compare to seasonal averages
- End long-range with uncertainty qualifier
</writing_style>

<conventions>
- Heights: feet, wave face (H1/10 = average of highest 10%)
- Face height = HSF × 2
- Directions: degrees from true north (where swell comes FROM)
- Distances: nautical miles
</conventions>
</system>
```

### Chain-of-thought prompting structure
```xml
<instructions>
Before generating the forecast, analyze in <thinking> tags:
1. What are the primary swell sources?
2. For each: fetch distance, timing, period?
3. How do swells interact with island geography?
4. Confidence level based on model agreement?
5. Comparison to seasonal climatology?

Then provide forecast in <forecast> tags with:
- Summary headline
- Shore-by-shore discussion
- Storm backstory narrative
- Long-range outlook with uncertainty
</instructions>
```

### Evaluation criteria
| Criterion | Measurement |
|-----------|-------------|
| Height accuracy | Predicted H1/10 vs observed ±20% |
| Timing accuracy | Onset/peak within ±6 hours |
| Direction accuracy | ±15° |
| Structural completeness | All sections present |
| Confidence calibration | Qualifiers match uncertainty |

---

## Implementation summary and data source comparison

| Source | URL Verified | Auth | Update | Format | Key Use |
|--------|--------------|------|--------|--------|---------|
| Goddard-Caldwell | ✓ NCEI | None | Static (1968-2020) | ASCII | Historical context |
| CDIP Spectral | ✓ THREDDS | None | 30 min | NetCDF | Directional spectra |
| Copernicus Waves | ✓ Marine.Copernicus | Free | 3-hourly | NetCDF | South Pacific swells |
| Copernicus Winds | ✓ Marine.Copernicus | Free | Hourly | NetCDF | ASCAT validation |
| IBTrACS | ✓ NCEI HTTP | None | 3×/week | CSV | Hurricane tracking |
| NOAA STAR ASCAT | ✓ manati.star | None | ~4 hours | PNG/NetCDF | Wind imagery |

### Integration priority order

1. **Goddard-Caldwell + CDIP**: Enable historical comparisons and directional analysis immediately
2. **Copernicus Marine**: Fill South Pacific model gap for summer season forecasts
3. **IBTrACS**: Automate hurricane swell calculations for tropical season
4. **ASCAT winds**: Add storm validation narratives for premium forecast quality
5. **LLM prompting**: Deploy Caldwell-style templates once data pipeline complete

All code examples use standard Python libraries (pandas, xarray, numpy) with no proprietary dependencies. The copernicusmarine library requires free registration but provides programmatic access to global wave and wind products unavailable elsewhere.
