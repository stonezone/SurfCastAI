# AltimetryAgent ERDDAP Update

**Date**: 2025-10-16
**Status**: Complete

## Overview

Updated `AltimetryAgent` to support the new NOAA ERDDAP graph endpoints that directly return PNG images of sea surface height (SSH) anomalies for the Hawaiian region.

## Changes Made

### 1. Updated Configuration (`config/config.yaml`)

Added two ERDDAP graph endpoints with fallback capability:
```yaml
altimetry:
  enabled: true
  urls:
    - "https://upwell.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day.graph?sla[(latest)][(15):(30)][(-165):(-150)]&.draw=surface&.vars=longitude|latitude|sla&.size=800|600&.png"
    - "https://polarwatch.noaa.gov/erddap/griddap/nesdisSSH1day.graph?sla[(latest)][(15):(30)][(-165):(-150)]&.draw=surface&.vars=longitude|latitude|sla&.size=800|600&.png"
```

These URLs:
- Query the `nesdisSSH1day` dataset (NESDIS 1-day SSH product)
- Use `[(latest)]` time constraint to get the most recent data
- Filter to Hawaiian region: 15-30°N, 165-150°W
- Return 800x600 PNG images directly

### 2. Updated Agent Logic (`src/agents/altimetry_agent.py`)

Modified the `collect()` method to:
- **Detect ERDDAP graph endpoints** by checking for `'erddap/griddap'` and `'.graph?'` in URL
- **Extract source names** from URL domains (Upwell vs PolarWatch)
- **Download PNG directly** without any post-processing for ERDDAP endpoints
- **Add rich metadata** including:
  - `source`: ERDDAP_Upwell or ERDDAP_PolarWatch
  - `data_product`: nesdisSSH1day
  - `region`: Hawaiian Islands (15-30N, 165-150W)
  - `variable`: Sea Level Anomaly (sla)
  - `type`: png_image
- **Implement fallback logic**: Try primary URL first, then fallback if it fails
- **Preserve legacy format support**: Still handles ZIP archives and gzipped NetCDF files

### 3. Updated Tests (`tests/unit/agents/test_altimetry_agent.py`)

Added two new test cases:
- `test_altimetry_agent_downloads_erddap_png()`: Verifies ERDDAP PNG download and metadata
- `test_altimetry_agent_fallback_to_secondary_url()`: Verifies fallback behavior when primary fails

All 4 tests pass:
```
test_altimetry_agent_downloads_erddap_png PASSED
test_altimetry_agent_fallback_to_secondary_url PASSED
test_altimetry_agent_processes_zip_payload PASSED
test_altimetry_agent_processes_netcdf_gzip PASSED
```

## Integration Test Results

Successfully tested with live ERDDAP endpoint:
```
✓ Successfully downloaded altimetry data
  File: ssh_hawaii_ERDDAP_Upwell.png
  Size: 84988 bytes
  Type: png_image
  Source: ERDDAP_Upwell
  Region: Hawaiian Islands (15-30N, 165-150W)
```

## Metadata Structure

Example metadata output:
```json
{
  "name": "ssh_hawaii_ERDDAP_Upwell.png",
  "description": "Sea Surface Height (SSH) from ERDDAP_Upwell",
  "type": "png_image",
  "source": "ERDDAP_Upwell",
  "status": "success",
  "timestamp": "2025-10-16T11:42:54.461890+00:00",
  "source_url": "https://upwell.pfeg.noaa.gov/erddap/griddap/nesdisSSH1day.graph...",
  "file_path": "/path/to/altimetry/ssh_hawaii_ERDDAP_Upwell.png",
  "size_bytes": 84988,
  "data_product": "nesdisSSH1day",
  "region": "Hawaiian Islands (15-30N, 165-150W)",
  "variable": "Sea Level Anomaly (sla)"
}
```

## Benefits

1. **More Reliable**: ERDDAP servers have better uptime than legacy STAR endpoints
2. **Automatic Fallback**: Two mirror servers for redundancy
3. **Pre-filtered Data**: URLs include geographic bounding box, so we get Hawaiian-focused imagery
4. **Latest Data**: `[(latest)]` constraint ensures most recent SSH anomaly data
5. **Direct Download**: No parsing or extraction needed - ready-to-use PNG images
6. **Backward Compatible**: Legacy ZIP and NetCDF formats still supported

## Next Steps

Per the playbook (`CLAUDE.md`), the next steps are:
1. ✓ Update AltimetryAgent for ERDDAP endpoints (COMPLETE)
2. Update nearshore buoys agent for CDIP THREDDS endpoints
3. Update WW3 model agent for NOMADS CSV endpoints
4. Update upper-air agent for SPC/WPC archive endpoints
5. Run full data collection and verify all feeds succeed
6. Process and forecast with calibrated Hawaiian-scale conversions

## Files Modified

- `src/agents/altimetry_agent.py`: Enhanced collect() method
- `tests/unit/agents/test_altimetry_agent.py`: Added ERDDAP-specific tests
- `config/config.yaml`: Updated altimetry URLs to ERDDAP endpoints
- `docs/altimetry_agent_erddap_update.md`: This documentation

## References

- ERDDAP Upwell: https://upwell.pfeg.noaa.gov/erddap/
- ERDDAP PolarWatch: https://polarwatch.noaa.gov/erddap/
- Dataset: nesdisSSH1day (NOAA/NESDIS Daily Sea Surface Height)
