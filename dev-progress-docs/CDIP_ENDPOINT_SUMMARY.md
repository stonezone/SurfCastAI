# CDIP Nearshore Buoy Endpoints - Quick Reference

**Date:** 2025-10-16
**Status:** VERIFIED WORKING

---

## Problem Statement

Legacy CDIP endpoint `https://cdip.ucsd.edu/data_access/processed/{station}p1.json` returns **404 errors**.

---

## SOLUTION 1: THREDDS File Server (RECOMMENDED)

### Endpoint Pattern
```
https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/{station}p1_rt.nc
```

### Working URLs (tested 2025-10-16)
| Station | Location | URL | Status |
|---------|----------|-----|--------|
| 225 | Kaneohe Bay | https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/225p1_rt.nc | ✅ HTTP 200 |
| 106 | Waimea Bay | https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/106p1_rt.nc | ✅ HTTP 200 |
| 249 | Pauwela, Maui | https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/249p1_rt.nc | ✅ HTTP 200 |
| 239 | Barbers Point/Lanai | https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/239p1_rt.nc | ✅ HTTP 200 |

### Format & Access
- **Format:** NetCDF binary (~30-75 MB per file)
- **Update:** Every 30 minutes
- **Contains:** Full directional wave spectra, raw XYZ buoy motion, computed wave parameters
- **Protocol:** HTTPS GET (direct download)

### Python Example
```python
import xarray as xr

station = 225
url = f"https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/{station}p1_rt.nc"
ds = xr.open_dataset(url)
print(ds.variables.keys())
```

---

## SOLUTION 2: NDBC Real-Time Text (FALLBACK)

### Endpoint Pattern
```
https://www.ndbc.noaa.gov/data/realtime2/{ndbc_id}.txt
```

### Station Mapping & URLs
| CDIP | NDBC | Location | URL |
|------|------|----------|-----|
| 225 | 51207 | Kaneohe Bay | https://www.ndbc.noaa.gov/data/realtime2/51207.txt |
| 106 | 51201 | Waimea Bay | https://www.ndbc.noaa.gov/data/realtime2/51201.txt |
| 249 | 51214 | Pauwela, Maui | https://www.ndbc.noaa.gov/data/realtime2/51214.txt |
| 239 | 51213 | Barbers Point/Lanai | https://www.ndbc.noaa.gov/data/realtime2/51213.txt |

### Format & Access
- **Format:** Space-delimited ASCII (FM-13 format)
- **Update:** Every 30 minutes (CDIP → NDBC transmission)
- **Contains:** Basic wave parameters (Hs, Tp, Dp), wind, temperature
- **Protocol:** HTTPS GET (simple text file)

### Sample Output
```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
2025 10 16 10 56  MM   MM   MM   1.5    14   6.0 353     MM    MM  26.7    MM   MM   MM    MM
```

### Python Example
```python
import requests

ndbc_id = "51207"
url = f"https://www.ndbc.noaa.gov/data/realtime2/{ndbc_id}.txt"
response = requests.get(url, timeout=10)

lines = response.text.split('\n')
for line in lines[2:]:  # Skip header lines
    if line.strip():
        parts = line.split()
        print(f"Hs: {parts[8]}m, Tp: {parts[10]}s, Dp: {parts[11]}°")
        break
```

---

## SOLUTION 3: PacIOOS ERDDAP (ALTERNATIVE)

### Endpoint
```
https://pae-paha.pacioos.hawaii.edu/erddap/tabledap/cdip_wave_agg
```

### Status
- Endpoint exists and serves CDIP aggregated data
- JSON query syntax requires further investigation
- CSV and NetCDF formats available
- Contains stations 225, 106, 239 and others

### Available Variables
- `waveHs` (significant wave height, m)
- `waveTp` (peak period, s)
- `waveTa` (average period, s)
- `waveDp` (peak direction, °T)
- `wavePeakPSD` (peak spectral density, m²/Hz)
- Quality flags, station metadata, lat/lon

---

## Recommendation for SurfCastAI

**Primary:** Use THREDDS File Server
**Fallback:** Use NDBC Real-Time Text
**Future:** Investigate PacIOOS ERDDAP for JSON access

### Config Update (`config/config.yaml`)
```yaml
data_sources:
  nearshore_buoys:
    provider: "CDIP"
    primary_url: "https://thredds.cdip.ucsd.edu/thredds/fileServer/cdip/realtime/{station}p1_rt.nc"
    fallback_url: "https://www.ndbc.noaa.gov/data/realtime2/{ndbc_id}.txt"

    stations:
      - id: 225
        name: "Kaneohe Bay, Oahu"
        ndbc_id: "51207"

      - id: 106
        name: "Waimea Bay, Oahu"
        ndbc_id: "51201"

      - id: 249
        name: "Pauwela, Maui"
        ndbc_id: "51214"

      - id: 239
        name: "Barbers Point / Lanai SW"
        ndbc_id: "51213"
```

---

## Agent Implementation Notes

### For `src/agents/cdip_agent.py`:

1. **Try THREDDS first** (NetCDF format)
   - More complete spectral data
   - Requires `xarray` or `netCDF4` library

2. **Fall back to NDBC** (text format) if:
   - THREDDS returns non-200 status
   - NetCDF parsing fails
   - Only basic wave parameters needed

3. **Metadata to capture:**
   - `wave_height` (Hs, meters)
   - `peak_period` (Tp, seconds)
   - `peak_direction` (Dp, degrees True)
   - `avg_period` (Ta, seconds)
   - `timestamp` (UTC)
   - `quality_flag` (if available)
   - `spectral_data` (frequency/direction bins if using NetCDF)

---

## Testing Script

See `test_cdip_endpoints.sh` for automated verification:

```bash
bash test_cdip_endpoints.sh
```

Expected output:
- THREDDS: 4/4 stations HTTP 200 ✅
- NDBC: 4/4 stations HTTP 200 ✅

---

## Additional Resources

- Full documentation: `CDIP_WORKING_ENDPOINTS.md`
- CDIP Data Access Docs: https://cdip.ucsd.edu/m/documents/data_access.html
- THREDDS Catalog: https://thredds.cdip.ucsd.edu/thredds/catalog.html
- NDBC Station Pages: https://www.ndbc.noaa.gov/to_station.shtml
- PacIOOS Data Portal: https://www.pacioos.hawaii.edu/data/

---

**Next Steps:**

1. ✅ Update `config/config.yaml` with new THREDDS URLs
2. ✅ Modify `src/agents/cdip_agent.py` to support NetCDF parsing
3. ✅ Add NDBC text format fallback logic
4. ✅ Test with fresh data collection
5. ⏳ Investigate PacIOOS ERDDAP JSON access for future enhancement

---

*Generated: 2025-10-16*
*All endpoints verified and operational*
