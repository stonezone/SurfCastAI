# Working NOAA Chart URLs for Surf Forecasting - Pacific/Hawaii Region

**Research Date:** October 3, 2025
**Status:** All URLs verified as publicly accessible (HTTP 200)

## Summary
Found **20 working chart URLs** to replace the broken ocean.weather.gov charts. All are direct image URLs (.png, .gif) that update regularly and require no authentication.

---

## 1. SURFACE ANALYSIS CHARTS (Current Conditions)

### Pacific Ocean Surface Analysis - Current (00hr)
**Ocean Prediction Center - 3 Regional Views**

- **West Pacific Surface Analysis (Current)**
  `https://ocean.weather.gov/shtml/P_west_00hrsfc.gif`
  Shows: Surface pressure systems, fronts, isobars for western Pacific Ocean

- **Full Pacific Surface Analysis (Current)**
  `https://ocean.weather.gov/shtml/P_full_00hrsfc.gif`
  Shows: Complete Pacific Ocean surface analysis from Asia to Americas

- **East Pacific Surface Analysis (Current)**
  `https://ocean.weather.gov/shtml/P_east_00hrsfc.gif`
  Shows: Surface pressure systems for eastern Pacific near North America

### Hawaii Regional Surface Analysis

- **Hawaii Unified Surface Analysis**
  `https://ocean.weather.gov/UA/Hawaii.gif`
  Shows: Unified surface analysis focused on Hawaiian Islands region

- **Pacific Ocean Unified Analysis**
  `https://ocean.weather.gov/UA/OPC_PAC.gif`
  Shows: Ocean Prediction Center's unified Pacific surface analysis

- **Hawaii Pacific Streamline Analysis**
  `https://www.weather.gov/images/hfo/graphics/stream.gif`
  Shows: Wind streamlines and surface features around Hawaii (updated 00Z/06Z/12Z/18Z)

- **North Pacific Surface Analysis**
  `https://www.weather.gov/images/hfo/graphics/npac.gif`
  Shows: North Pacific surface pressure and fronts from Honolulu Forecast Office

- **North Pacific Surface Analysis (00Z)**
  `https://www.weather.gov/images/hfo/graphics/npac_sfc_00.gif`
  Shows: Specific 00Z analysis for North Pacific region

---

## 2. SURFACE FORECAST CHARTS (Future Conditions)

### Pacific Surface Pressure Forecasts
**Ocean Prediction Center - Updated 00Z and 12Z daily**

- **Pacific 24-Hour Surface Forecast**
  `https://ocean.weather.gov/shtml/P_24hrsfc.gif`
  Shows: Forecast surface pressure systems, fronts 24 hours ahead

- **Pacific 48-Hour Surface Forecast**
  `https://ocean.weather.gov/shtml/P_48hrsfc.gif`
  Shows: Forecast surface pressure systems 48 hours ahead

- **Pacific 72-Hour Surface Forecast**
  `https://ocean.weather.gov/shtml/P_72hrsfc.gif`
  Shows: Forecast surface pressure systems 72 hours (3 days) ahead

- **Pacific 96-Hour Surface Forecast**
  `https://ocean.weather.gov/shtml/P_96hrsfc.gif`
  Shows: Forecast surface pressure systems 96 hours (4 days) ahead

---

## 3. WIND & WAVE FORECAST CHARTS

### Pacific Wind/Wave Analysis & Forecasts
**Ocean Prediction Center - Shows significant wave heights and wind speeds**

- **Pacific Wind/Wave Analysis (Current)**
  `https://ocean.weather.gov/shtml/P_00hrww.gif`
  Shows: Current wind speeds and significant wave heights for Pacific

- **Pacific 24-Hour Wind/Wave Forecast**
  `https://ocean.weather.gov/shtml/P_24hrww.gif`
  Shows: Forecast wind speeds and wave heights 24 hours ahead

- **Pacific 48-Hour Wind/Wave Forecast**
  `https://ocean.weather.gov/shtml/P_48hrww.gif`
  Shows: Forecast wind speeds and wave heights 48 hours ahead

- **Pacific 72-Hour Wind/Wave Forecast**
  `https://ocean.weather.gov/shtml/P_72hrww.gif`
  Shows: Forecast wind speeds and wave heights 72 hours ahead

- **Pacific 96-Hour Wind/Wave Forecast**
  `https://ocean.weather.gov/shtml/P_96hrww.gif`
  Shows: Forecast wind speeds and wave heights 96 hours ahead

---

## 4. SEA SURFACE TEMPERATURE (SST) CHARTS

### Pacific SST Analysis
**National Hurricane Center - Updated daily**

- **Pacific SST Daily Analysis**
  `https://www.nhc.noaa.gov/tafb/sst_loop/14_pac.png`
  Shows: Current sea surface temperatures for Pacific Ocean (PNG format)

### Hawaii SST Anomaly Charts
**NOAA Coral Reef Watch - 5km resolution, updated daily**

- **Hawaii SST Anomaly (Current)**
  `https://coralreefwatch.noaa.gov/data_current/5km/v3.1_op/daily/png/ct5km_ssta_v3.1_hawaii_current.png`
  Shows: Current SST anomaly (deviation from normal) for Hawaii region

- **Hawaii SST Anomaly 30-Day Animation**
  `https://coralreefwatch.noaa.gov/data_current/5km/v3.1_op/animation/gif/ssta_animation_30day_hi_930x580.gif`
  Shows: Animated 30-day SST anomaly loop for Hawaii (930x580 GIF)

---

## 5. BUOY DATA CHARTS (Real-time Observations)

### NDBC Buoy Station Charts
**National Data Buoy Center - Real-time wave and wind plots**

- **Buoy 51001 Wave Height Chart**
  `https://www.ndbc.noaa.gov/show_plot.php?station=51001&meas=sght&uom=E&tz=HAST`
  Shows: 45-day wave height plot for buoy 51001 (188 NM NW of Kauai)
  *Note: Returns HTML page with embedded chart image*

---

## REPLACEMENTS FOR BROKEN URLS

### Original Broken URLs → Working Replacements

1. ❌ `https://ocean.weather.gov/P_sfc_24hr_ocean_color.png` (404)
   ✅ `https://ocean.weather.gov/shtml/P_24hrsfc.gif`

2. ❌ `https://ocean.weather.gov/P_sfc_48hr_ocean_color.png` (404)
   ✅ `https://ocean.weather.gov/shtml/P_48hrsfc.gif`

3. ❌ `https://ocean.weather.gov/P_sfc_96hr_ocean_color.png` (404)
   ✅ `https://ocean.weather.gov/shtml/P_96hrsfc.gif`

4. ❌ `https://ocean.weather.gov/P_sfc_120hr_ocean_color.png` (404)
   ✅ **No 120hr chart available** - use 96hr instead or combine with wind/wave forecast

---

## NOTES & LIMITATIONS

### Update Schedules
- **Ocean Prediction Center (OPC)** charts: Updated twice daily at 00Z and 12Z
- **Hawaii Forecast Office (HFO)** charts: Updated four times daily at 00Z, 06Z, 12Z, 18Z
- **NOAA Coral Reef Watch SST**: Updated daily around 1:30 PM HST
- **NDBC Buoy charts**: Real-time continuous updates

### Chart Format Notes
- Most charts are in **GIF format** (not PNG as in original broken URLs)
- SST charts use **PNG format**
- NDBC buoy charts are **dynamically generated** (HTML pages with embedded charts)

### WaveWatch III Charts - Not Accessible
The WaveWatch III significant wave height charts from polar.ncep.noaa.gov were found but return **403 Forbidden** for direct image access:
- `https://polar.ncep.noaa.gov/waves/WEB/gfswave.latest_run/plots/hawaii.hs.f000.png` (403)
- `https://polar.ncep.noaa.gov/waves/WEB/gfswave.latest_run/plots/pacific.hs.f000.png` (403)

**Alternative:** Use the Ocean Prediction Center wind/wave charts (`P_*hrww.gif`) instead

### 120-Hour Forecasts
- **No 120-hour surface analysis charts** available from OPC
- Maximum forecast horizon is **96 hours (4 days)** for Pacific surface and wind/wave charts
- For 5-day forecasts, consider using GFS model data or combining 96hr charts with text forecasts

---

## RECOMMENDED CHART SUBSET FOR SURF FORECASTING

For a focused surf forecasting system, these **10 core charts** provide excellent coverage:

1. `https://ocean.weather.gov/shtml/P_full_00hrsfc.gif` - Current Pacific surface
2. `https://ocean.weather.gov/shtml/P_24hrsfc.gif` - 24hr surface forecast
3. `https://ocean.weather.gov/shtml/P_48hrsfc.gif` - 48hr surface forecast
4. `https://ocean.weather.gov/shtml/P_96hrsfc.gif` - 96hr surface forecast
5. `https://ocean.weather.gov/shtml/P_24hrww.gif` - 24hr wind/wave
6. `https://ocean.weather.gov/shtml/P_48hrww.gif` - 48hr wind/wave
7. `https://ocean.weather.gov/shtml/P_96hrww.gif` - 96hr wind/wave
8. `https://www.weather.gov/images/hfo/graphics/npac.gif` - North Pacific surface
9. `https://www.nhc.noaa.gov/tafb/sst_loop/14_pac.png` - Pacific SST
10. `https://coralreefwatch.noaa.gov/data_current/5km/v3.1_op/daily/png/ct5km_ssta_v3.1_hawaii_current.png` - Hawaii SST anomaly

---

## SOURCES & DOCUMENTATION

- **Ocean Prediction Center:** https://ocean.weather.gov/
- **NWS Honolulu Forecast Office:** https://www.weather.gov/hfo/
- **National Hurricane Center SST:** https://www.nhc.noaa.gov/sst/
- **NOAA Coral Reef Watch:** https://coralreefwatch.noaa.gov/
- **NDBC Buoy Data:** https://www.ndbc.noaa.gov/

---

**Verification Method:** All URLs tested with HTTP HEAD requests on October 3, 2025. All returned HTTP 200 status codes.
