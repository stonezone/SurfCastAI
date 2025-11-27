# GFS-Wave Direction Convention Solved: Web Bulletins Use "TO" Convention

**The critical 180° discrepancy between GFS-Wave (127° ESE) and Pat Caldwell (307° WNW) is explained by convention differences.** GFS-Wave web spectral bulletins use oceanographic convention (direction waves travel TO), while Caldwell uses meteorological convention (direction waves come FROM). Converting 127° + 180° = 307° (WNW) - a perfect match with Caldwell's prediction. The amplitude (17.3 ft) and period (17.5s) already matched, confirming this is the same swell event with different direction encoding.

---

## The convention puzzle decoded

NCEP Technical Product Bulletin 494 provides the definitive answer: **"In the remaining six columns individual wave fields are tracked with their wave height, peak wave period and mean wave direction (dir, direction in which waves travel relative to North)."** Critically, the document states that "the format for spectral text bulletins sent to AWIPS is generally the same as for the web, except that the direction is from (meteorological, rather than oceanographic)."

This reveals a crucial inconsistency within NOAA's own products:

| GFS-Wave Product Type | Convention | 127° Means |
|----------------------|------------|------------|
| **Web spectral bulletins** (partition tables) | Oceanographic (TO) | Waves traveling TO 127° (ESE) |
| GRIB2 gridded output | Meteorological (FROM) | Waves coming FROM 127° (ESE) |
| AWIPS text bulletins | Meteorological (FROM) | Waves coming FROM 127° (ESE) |

**For SurfCastAI's implementation**: If your system parses web spectral bulletins (the online partition tables at polar.ncep.noaa.gov), you must add 180° to all direction values to convert to the standard meteorological "coming FROM" convention that forecasters like Caldwell use. PacIOOS documentation confirms GFS-Wave spectral bulletins show "the direction that peak waves are traveling from," but this appears to be a documentation inconsistency - the actual bulletin format follows oceanographic convention per NCEP TPB 494.

ECMWF uses identical conventions: bulk wave parameters use meteorological (FROM) convention, but wave spectra in GRIB headers follow oceanographic (TO) convention. This industry-wide split between gridded products and spectral output is the root cause of confusion.

---

## Storm tracking data sources for Caldwell-style analysis

Pat Caldwell's forecast narratives include storm backstories like "968 mb low deepened near 50N, 170E, 2400 nm from Hawaii, hurricane force winds validated by ASCAT." Here are machine-readable sources to replicate this analysis:

### Surface pressure monitoring

**PacIOOS ERDDAP** provides the easiest programmatic access to GFS MSLP for the Aleutian storm generation zone:
```
https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ncep_pac.json?prmslmsl[(TIME)][(40):(55)][(150):(180)]
```
This returns JSON-formatted pressure data at 0.25° resolution with no authentication required. For bulk processing, **AWS S3 GFS bucket** (`s3://noaa-gfs-bdp-pds/`) provides anonymous access to complete GRIB2 files with **384-hour forecasts** updated 4x daily.

### ASCAT satellite wind validation

Two primary sources for validating hurricane-force fetch conditions:
- **NASA PO.DAAC** via `podaac-data-subscriber`: Near-real-time MetOp-B/C L2 wind vectors at 25km resolution, requiring free Earthdata Login
- **Copernicus Marine L4 hourly** (product `WIND_GLO_PHY_L4_NRT_012_004`): Gap-free gridded winds blending ASCAT with ECMWF, requiring free registration

NOAA STAR also provides **Ultra High Resolution storm wind products** at ~10km resolution specifically optimized for tropical cyclone analysis.

### Storm track databases

**IBTrACS** at NCEI is the primary source for tropical cyclone tracking, with an `ACTIVE` storms CSV file (`ibtracs.ACTIVE.list.v04r01.csv`) updated 3x weekly. For extratropical North Pacific lows affecting Hawaii, **NCEP/EMC cyclone tracking** at `emc.ncep.noaa.gov/mmb/gplou/emchurr/glblgen/` provides analysis and forecast tracks from GFS, ECMWF, and other models.

---

## Alternative wave models for cross-validation

Three sources offer spectral partition data capable of separating simultaneous NW and S swells:

### CMEMS Global Wave (highest priority)

Copernicus Marine Service provides **primary and secondary swell partitions** through the MFWAM model:
```python
copernicusmarine.subset(
    dataset_id="cmems_mod_glo_wav_anfc_0.083deg_PT3H-i",
    variables=["VHM0", "VHM0_SW1", "VHM0_SW2", "VMDR_SW1", "VMDR_SW2"],
    minimum_longitude=-162, maximum_longitude=-154,
    minimum_latitude=18, maximum_latitude=23
)
```
Variables **VHM0_SW1/SW2** provide primary and secondary swell heights with corresponding directions, enabling independent swell system tracking. The model runs at **1/12° (~9km) resolution** with 10-day forecasts - comparable to GFS-Wave. Free registration required at marine.copernicus.eu.

### PacIOOS WW3 Hawaii (regional detail)

Already partially used by SurfCastAI, PacIOOS separates **swell (shgt, sper, sdir) from wind waves (whgt, wper, wdir)** at 5km resolution via ERDDAP:
```
https://pae-paha.pacioos.hawaii.edu/erddap/griddap/ww3_hawaii.json?shgt,sper,sdir,whgt,wper,wdir[(TIME)][(19):(22)][(203):(206)]
```
No authentication required, with 7-day forecasts updated hourly.

### CDIP spectral observations (ground truth)

Hawaii buoys operated by CDIP provide **full 2D directional spectra** (64 frequency bins × 72 directions) for model validation:
- **Waimea Bay (106p1)**: North Shore ground truth
- **Pauwela (187p1)**: Maui north coast
- **Barbers Point (165p1)**: South Shore approach

THREDDS access at `thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/106p1_rt.nc` provides 30-minute updates with wave field partition products available at `cdip.ucsd.edu/m/products/partition/`.

---

## The Goddard-Caldwell database found

The historical climatology source Caldwell references is **publicly archived at NCEI**: `https://www.ncei.noaa.gov/archive/accession/Goddard-Caldwell_Database`. This ASCII dataset contains:

- **Daily H1/10 observations** from August 1968 to December 2020
- **Coverage**: North Shore (Sunset Point, Waimea Bay), South Shore (Ala Moana, Diamond Head), West (Makaha), East (Makapuu)
- **Direction data** available since 1990
- **Hawaii Scale** convention: divide trough-to-crest by 2 (multiply by 2 to convert to peak face height)

This is precisely the source for Caldwell's "On this day, November 26, in the Goddard-Caldwell database (since 1968), the average H1/10 is 7.0 ft" statements. To replicate: filter by month-day across all years and calculate mean H1/10.

---

## Buoy network for upstream swell tracking

### North Pacific swell path (3-4 days before Hawaii arrival)

| Buoy | Location | Distance | Travel Time |
|------|----------|----------|-------------|
| **46001** | Gulf of Alaska (56.3°N, 148.0°W) | ~2400 nm | 3-4 days |
| **46035** | Central Bering Sea (57.0°N, 177.5°W) | ~2500 nm | 3-4 days |
| **46072** | Central Aleutians (51.6°N, 172.1°W) | ~2400 nm | 3-4 days |
| **46066** | S Kodiak Island (52.8°N, 155.0°W) | ~2100 nm | 2.5-3 days |
| **51001** | NW Hawaii (23.4°N, 162.3°W) | 188 nm | **12-24 hours** |

Buoy **51001** is the critical final-approach detector for NW swells - the last checkpoint before North Shore impact.

### Southern hemisphere tracking (ESE swells at 127°)

For the 127° direction swell (if it were actually coming FROM 127°, not TO), key southern sources include:
- **51209** (American Samoa, 14.3°S): 2,300 nm south, 5-7 day travel time
- **BOM AUSWAVE model**: Global wave model tracking Southern Ocean storm systems
- Australian buoys via AODN, particularly Cape Sorell (55026) in Tasmania

---

## Implementation recommendations

**Immediate fix for direction discrepancy**:
1. Determine which GFS-Wave product SurfCastAI parses (web bulletins vs GRIB2)
2. If using web spectral bulletins: add 180° to direction values
3. If using GRIB2 directly: directions should already be "FROM" convention

**Cross-validation pipeline**:
1. Pull CMEMS SW1/SW2 partitions for independent swell tracking
2. Validate against CDIP Waimea (106p1) spectral observations
3. Compare timing using 51001 buoy as 12-24 hour advance warning

**Storm backstory automation**:
1. Monitor GFS MSLP via PacIOOS ERDDAP for lows < 980 mb in Aleutian region
2. Pull ASCAT winds via Copernicus Marine for fetch validation
3. Calculate great-circle distance and swell travel time (roughly 500-600 nm/day for 17-second period)

**Historical context**:
1. Ingest Goddard-Caldwell database from NCEI
2. Build daily climatology lookup tables
3. Include H1/10 averages and maximum events for forecast context

The direction convention discovery resolves the core mystery - the 127° GFS-Wave value represents waves **traveling toward** ESE, which means they are **coming from** WNW (307°), exactly matching Caldwell's professional forecast.
