# AI Research Prompt: Fix SurfCastAI Data Feed Issues

## Context
I'm building a Hawaii surf forecasting system (SurfCastAI) that uses NOAA buoy data, wave models, and pressure charts to generate AI-powered surf forecasts. **Critical data feeds are failing**, causing my forecasts to miss major swell events like a 40-foot "Giant" swell that Pat Caldwell (professional forecaster) correctly predicted.

## Current Problem
The WW3 (WaveWatch III) Hawaii point forecast data is returning 404 errors from NOMADS:
```
https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.{YYYYMMDD}/points/hawaii/wvprbl_hi.{YYYYMMDD}.t{HH}z.csv
```

Without this data, the system cannot forecast beyond 3 days, missing critical extended events.

## Research Tasks

### 1. Find Working WW3 Hawaii Point Forecast URLs (CRITICAL)
Search for current, working URLs that provide WW3 wave model point forecasts for Hawaii. Look for:
- **NOMADS alternatives**: Has the path structure changed? Is there a new directory layout?
- **AWS Open Data**: NOAA hosts GFS and wave data on `noaa-gfs-bdp-pds.s3.amazonaws.com` - is WW3 Hawaii data available?
- **FTPPRD backup**: `https://ftpprd.ncep.noaa.gov/data/nccf/com/wave/prod/` - what's the current structure?
- **NCEP direct**: Any direct NCEP wave model archives?

I need CSV or NetCDF files with:
- Location: Hawaii region (roughly 19-23°N, 154-161°W)
- Parameters: Significant wave height (Hs), peak period (Tp), wave direction
- Forecast horizon: 7-14 days ahead
- Update frequency: Every 6 hours (00Z, 06Z, 12Z, 18Z)

### 2. Find Alternative Wave Model Data Sources
If WW3 NOMADS is truly down, find alternatives:
- **Copernicus Marine Service (CMEMS)** - Do they have Pacific wave forecasts?
- **PacIOOS** (Pacific Islands Ocean Observing System) - Hawaii-specific wave forecasts?
- **Surfline/LOLA model** - Any public API access?
- **Open-Meteo Marine API** - Already using, but does it have extended forecasts?
- **ECMWF WAM** - European wave model with Pacific coverage?

### 3. Storm/Pressure Data Sources
To improve storm backstory (like "968 mb low at 50N, 170E"), find:
- **GFS surface pressure analysis** in machine-readable format (not just images)
- **ASCAT satellite wind data** for fetch validation
- **JMA (Japan Meteorological Agency)** surface analysis for NW Pacific storms
- Real-time North Pacific storm tracking databases

### 4. Historical Climatology Enhancement
Find additional sources for Hawaii surf climatology:
- **CDIP (Coastal Data Information Program)** historical wave statistics
- **NDBC historical archives** for multi-decade trends
- Any academic datasets on Hawaiian surf history (1968-present preferred)

## Output Format
For each data source found, provide:
1. **URL/Endpoint**: Exact working URL with any required parameters
2. **Data format**: JSON, CSV, NetCDF, GRIB2, etc.
3. **Update frequency**: How often is data refreshed?
4. **Forecast horizon**: How many days ahead?
5. **Authentication**: API key required? Free tier limits?
6. **Sample request**: Example curl command or API call
7. **Coverage**: Does it cover Hawaii specifically?

## Priority Order
1. **WW3 Hawaii point forecasts** (CRITICAL - without this, extended forecasts fail)
2. **Alternative wave models** with 7+ day forecasts
3. **Storm tracking/pressure data**
4. **Historical climatology**

## Example of What I Need
```yaml
source_name: "NOAA WW3 Hawaii Points"
url_template: "https://[NEW-WORKING-URL]/{date}/hawaii/wvprbl_hi.{date}.t{hour}z.csv"
format: CSV
update_frequency: "6 hours (00Z, 06Z, 12Z, 18Z)"
forecast_horizon: "180 hours (7.5 days)"
authentication: "None required"
sample_curl: "curl -O 'https://...'"
coverage: "Hawaii region point forecasts"
status: "WORKING as of [date]"
```

## Current Working Feeds (for reference)
These are already working in my system:
- NDBC buoys: `https://www.ndbc.noaa.gov/data/realtime2/{station}.txt` ✓
- Open-Meteo Marine: `https://marine-api.open-meteo.com/v1/marine?...` ✓
- NWS weather: `https://api.weather.gov/gridpoints/HFO/...` ✓
- NOAA tides: `https://api.tidesandcurrents.noaa.gov/...` ✓

## Additional Context
- Pat Caldwell's professional forecasts use WW3 model guidance extensively
- The system needs to predict swells 5-7 days out to catch major events
- Hawaii is ~2400 nautical miles from NW Pacific storm generation zones
- Swell travel time from Aleutians to Hawaii is approximately 3-4 days

Please search thoroughly and provide working URLs I can test immediately.
