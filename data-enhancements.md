SurfCastAI Enhancement Report: Historical Climatology, Spectral Validation, and Narrative Generation1. Executive SummaryThis technical report delineates the architectural and meteorological enhancements required to elevate SurfCastAI from a standard numerical model interpreter to an expert-tier forecasting system. The core objective is to emulate the cognitive and analytical depth of a veteran human forecaster—specifically modeling the style and methodology of Pat Caldwell, the NOAA Data Center liaison whose forecasts are the gold standard for Hawaiian surf climatology. The investigation validates the accessibility of critical historical datasets, identifies superior real-time data streams for spectral analysis, and establishes a robust framework for narrative generation using Large Language Models (LLMs).Our analysis confirms that the Goddard-Caldwell Historical Database (NCEI Accession 0001754) is fully accessible via NOAA archives and serves as the requisite "memory" for the system, allowing for the bias-correction of modern wave models against over fifty years of human observations.1 For real-time validation, the Coastal Data Information Program (CDIP) spectral buoys provide the necessary ground truth, offering granular directional spectra that outperform standard bulk parameters.3 A critical operational pivot is recommended for Southern Hemisphere forecasting: the current reliance on the Tahiti Buoy (51407) must be abandoned, as it is a tsunami-specific DART station incapable of resolving swell spectra.5 Instead, we propose an integration with Copernicus Marine Service global wave models and satellite altimetry to track south swell generation in the Tasman and South Pacific regions.6Furthermore, the report details the Prompt Engineering strategy required to synthesize these data streams into the "Caldwell Narrative." By analyzing the linguistic structures of National Weather Service (NWS) discussions—specifically the use of confidence markers, causal reasoning, and the unique "Hawaii Scale"—we define a Few-Shot Prompting architecture that guides LLMs to produce text indistinguishable from expert analysis.7 The following sections provide exhaustive technical specifications, Python implementation strategies, and data governance protocols for each priority area.2. Priority 1: Goddard-Caldwell Historical Database AccessThe "Goddard-Caldwell Daily Visual Surf Observation Database" represents a singular climatological asset. While modern buoy networks provide precise offshore energy readings, they lack the multi-decadal continuity and "surf-zone reality" captured in this dataset. Integrating this database allows SurfCastAI to bridge the gap between "model height" (offshore significant wave height) and "observed surf" (breaking wave face height), applying a human-calibrated bias correction that is otherwise impossible to automate.2.1 Access Methodology and VerificationThe research confirms that the database is archived at the National Centers for Environmental Information (NCEI) under Accession 0001754. It is not available via a modern, queryable REST API, but rather through the traditional NCEI archival file server system. This distinction is crucial for the engineering pipeline: the data ingestion engine must be designed to periodically scrape and parse static ASCII files rather than query a dynamic endpoint.Verified Archive URL: https://www.ncei.noaa.gov/archive/accession/0001754 2Direct File Access Protocol: The data files are accessible via HTTPS direct download. While FTP access (ftp.ncei.noaa.gov) exists, it is deprecated in modern browsers and requires specific client configurations. The HTTPS route is robust and recommended for the production pipeline.2Update Frequency: The dataset is updated irregularly, typically annually or semi-annually, as it relies on the manual compilation and quality control of visual observations.10Authentication: The archive is public domain; no authentication tokens or API keys are required for download.22.2 Data Structure and File FormatsThe database is comprised of ASCII text files, typically segmented by year or concatenated into multi-year blocks. The files utilize a fixed-width or space-delimited format that has remained consistent to preserve historical integrity. Understanding the column structure is vital for accurate parsing, particularly given the nuances of the "Hawaii Scale."2.2.1 Column Definitions and MetadataBased on the NCEI metadata and analysis of the file headers, the data structure is defined as follows 10:Variable NameData TypeDescriptionDateISO-8601 (Derived)Composite of Year, Month, Day columns.Location CodeString (2-char)Identifier for the observation zone (e.g., NS for North Shore, SS for South Shore).Observation HeightFloatThe reported surf height in Hawaii Scale. This value represents the visual estimate of the breaker.Swell DirectionString / IntegerThe dominant direction of the swell source (e.g., NW or degrees).Quality FlagInteger (Optional)Indicators for observation confidence or interpolation (present in newer files).Critical Observation Nuance: The recorded daily value represents the "upper end of the reported height range." Pat Caldwell notes that this value is roughly equivalent to H1/10 (the average height of the highest 10% of waves) for the observing time and location. This statistical definition is significantly more aggressive than the standard Significant Wave Height ($H_s$ or H1/3) used in buoy physics, implying that the human observers are intuitively filtering for the "sets" rather than the average sea state.102.3 The "Hawaii Scale" Convention and CalibrationA fundamental requirement for SurfCastAI is the correct algorithmic handling of the "Hawaii Scale." The database values are recorded exclusively in this local convention, which systematically underestimates the physical trough-to-crest height ($H_{phys}$).Conversion Formula: $H_{phys} \approx 2.0 \times H_{HI}$Physical Interpretation: A recorded value of "10 feet" in the Goddard-Caldwell database corresponds to a physical wave face of approximately 20 feet.Implications for AI Training: If SurfCastAI were to train its predictive models using raw GFS-Wave output (meters, physical) against this database without applying the 0.5x scalar (or 2.0x inverse), the model would chronically under-predict surf heights by 50%.Cultural Context: The "Hawaii Scale" convention, while scientifically disputed, became the primary means of communicating surf size in the late 1960s. To generate authentic narratives, SurfCastAI must internalize this conversion: calculating in physics (meters) but communicating in "local scale" (feet/2) when generating user-facing text for Hawaiian audiences.2.4 Geographic Coverage and Observation NodesThe database aggregates observations from specific "indicator breaks" that are representative of the entire coastline.10 The ingestion logic must map these historical nodes to the corresponding virtual forecast points:North Shore (Oahu):Primary Node: Sunset Beach (West Peak/Point). This location is chosen because it focuses swell energy and is visible from the coastal highway.Extreme Event Node: Waimea Bay. When surf heights exceed 15 ft (Hawaii Scale), observations shift to Waimea Bay because Sunset Beach "washes through" and becomes unrideable/unobservable at those sizes. The AI must account for this sensor-switching logic in extreme swell events.South Shore (Oahu):Primary Node: Ala Moana Bowls. A reliable indicator for south and southwest swells, less shadowed than Waikiki.Secondary Node: Diamond Head (occasionally referenced for trade wind swell).West Shore (Oahu):Primary Node: Makaha. Captures wrap-around North swell and direct West swell.East Shore (Oahu):Primary Node: Makapuu. The standard for trade-wind generated windswell.2.5 Python Implementation: The Climatology EngineTo operationalize this data, SurfCastAI requires a dedicated ETL (Extract, Transform, Load) pipeline. The following Python code demonstrates how to fetch the dataset, parse the ASCII format, handle the Hawaii Scale conversion, and compute the "On This Day" climatology statistics requested for the narrative engine.Pythonimport pandas as pd
import requests
import io
import datetime

class GoddardCaldwellClimatology:
    """
    Engine for managing the Goddard-Caldwell Historical Surf Database.
    Handles fetching from NCEI, parsing ASCII, and computing climatological baselines.
    """
    def __init__(self):
        # Base URL for NCEI Accession 0001754
        # Note: The specific filename changes with updates (e.g., v1.1), so scraping the index is robust.
        self.archive_url = "https://www.ncei.noaa.gov/data/oceans/archive/arc0001/0001754/data/"
        self.hawaii_scale_factor = 2.0

    def fetch_and_parse(self):
        """
        Fetches the concatenated dataset.
        In production, this should check for a local cached copy before hitting NCEI.
        """
        # Placeholder for the actual file scraping logic (BeautifulSoup or similar)
        # Assuming we have resolved the direct link to the latest annual file or master file.
        # Example structure based on NCEI ASCII format
        target_file_url = f"{self.archive_url}/0001754_latest.txt"

        try:
            # Simulated request (replace with actual requests.get)
            # response = requests.get(target_file_url)
            # response.raise_for_status()

            # Parsing logic: The files are often space-delimited without headers
            # Columns inferred from metadata: Year, Month, Day, Location, Height (HI), Direction
            cols =

            # Loading data (using a buffer for the example)
            # df = pd.read_csv(io.StringIO(response.text), sep=r'\s+', names=cols)

            # Create a mock dataframe for demonstration purposes
            data = {
                'Year':  * 10,
                'Month':  * 30,
                'Day':  * 30,
                'Location': * 30,
                'Height_HI':  * 3, # Hawaii Scale
                'Direction': * 30
            }
            df = pd.DataFrame(data)
            return df

        except Exception as e:
            print(f"Error fetching NCEI data: {e}")
            return pd.DataFrame()

    def get_climatology(self, df, month, day, location='NS'):
        """
        Computes the H1/10 stats for a specific day of the year (e.g., Nov 26)
        across the historical record.
        """
        # Filter for the specific day and location
        daily_subset = df[
            (df['Month'] == month) &
            (df == day) &
            (df['Location'] == location)
        ]

        if daily_subset.empty:
            return None

        # Compute Statistics
        mean_hi = daily_subset['Height_HI'].mean()
        max_hi = daily_subset['Height_HI'].max()
        p90_hi = daily_subset['Height_HI'].quantile(0.9) # 90th percentile

        # Convert to Physical Face Height for internal logic
        mean_face = mean_hi * self.hawaii_scale_factor
        max_face = max_hi * self.hawaii_scale_factor

        stats = {
            'mean_hi': mean_hi,
            'max_hi': max_hi,
            'p90_hi': p90_hi,
            'mean_face': mean_face,
            'max_face': max_face,
            'sample_size': len(daily_subset),
            'years': f"{daily_subset.min()}-{daily_subset.max()}"
        }

        return stats

    def generate_context_string(self, stats):
        """
        Generates the 'Caldwell-style' historical context sentence.
        """
        if not stats:
            return "Historical context unavailable."

        return (
            f"For context, on this day in the Goddard-Caldwell database (spanning {stats['years']}), "
            f"the average surf height is {stats['mean_hi']:.1f} ft (Hawaii Scale). "
            f"Today's forecast aligns with this climatology, " if stats['mean_hi'] > 5 else
            f"Today's event is significantly larger than the historical average of {stats['mean_hi']:.1f} ft, "
            f"approaching the daily record of {stats['max_hi']} ft set in previous years."
        )

# Example Execution
# climatology_engine = GoddardCaldwellClimatology()
# df = climatology_engine.fetch_and_parse()
# today_stats = climatology_engine.get_climatology(df, 11, 26, 'NS')
# print(climatology_engine.generate_context_string(today_stats))
This implementation allows SurfCastAI to inject the specific phrase "On this day, November 26, in the Goddard-Caldwell database..." into the forecast, satisfying the user's primary stylistic requirement.3. Priority 2: CDIP Hawaii Spectral BuoysFor a forecasting system to move beyond generic model output, it must validate its predictions against high-fidelity ground truth. The Coastal Data Information Program (CDIP) at Scripps Institution of Oceanography manages the premier buoy network for this purpose. Unlike the standard National Data Buoy Center (NDBC) hourly reports which often provide only bulk parameters (Significant Wave Height, Dominant Period), CDIP buoys offer full spectral resolution.3.1 Buoy Identification and Strategic RelevanceThree specific stations form the "Iron Triangle" of validation for Hawaiian surf forecasting:Waimea Bay (Station 106 / 106p1):Role: The primary ground truth for North Shore winter swells.Location: Situated in deep water immediately offshore of the break. Its proximity means there is virtually no decay between the sensor and the surf zone, making it a perfect "nowcast" validation point.Barbers Point (Station 165 / 165p1):Role: The sentinel for South Shore summer swells.Strategic Value: It detects shadowing effects on the North Shore (wrap) and confirms the arrival of long-period energy from the Tasman Sea before it impacts the Ala Moana reefs.Pauwela, Maui (Station 187 / 187p1):Role: The "upstream" sensor.Strategic Value: Because of the trade wind vector (NE to SW), Pauwela often senses trade wind swell and northerly groundswells 3-6 hours before they reach Oahu. This provides a predictive window for "short-term" alerts.3.2 THREDDS and NetCDF Access ArchitectureCDIP provides sophisticated access via a THREDDS Data Server (TDS). This architecture supports OPeNDAP (Open-source Project for a Network Data Access Protocol), which allows for "lazy loading"—fetching only the specific bytes for the latest timestamp or variable without downloading the entire multi-gigabyte historical archive.3Base URL Template: https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/{station}_rt.ncValidated Endpoint (Waimea): https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/106p1_rt.ncProtocol: HTTP/HTTPS using the OPeNDAP interface (often denoted by the .dods extension in client requests or dodsC directory in THREDDS).33.3 Spectral Data Structure and Bulk Parameter ExtractionThe NetCDF files contain the full spectral density information. Accessing the full spectrum is mandatory for distinguishing "mixed seas" (e.g., a small North swell mixed with a large West swell).3.3.1 Variable TaxonomyThe spectral data is stored in multidimensional arrays 3:Variable NameDimensionsDescriptionwaveTime[time]Epoch time (seconds since 1970).waveFrequency[frequency]Center frequencies of the 64 bins (typically 0.03 Hz to 0.58 Hz).waveEnergyDensity[time, frequency]The core energy spectrum ($m^2/Hz$). Peaks here indicate swell sources.waveMeanDirection[time, frequency]The mean direction of waves for each frequency bin.waveHs[time]Bulk Significant Wave Height (meters).waveTp[time]Peak Period (seconds).waveDp[time]Peak Direction (degrees).3.3.2 Swell Partitioning LogicWhile CDIP provides pre-calculated partitions on their website (Partition 1 vs Partition 2), the raw NetCDF data often requires the user to compute these if they are not explicitly exposed as variables in the real-time file. The standard approach is to integrate the waveEnergyDensity over specific frequency bands:Swell Band: $f < 0.10 \text{ Hz}$ (Period > 10s)Wind/Chop Band: $f \ge 0.10 \text{ Hz}$ (Period < 10s)3.4 Python Code: Fetching and Parsing SpectraThe following script utilizes the xarray and netCDF4 libraries to connect to the THREDDS server, creating a robust fetcher that handles the OPeNDAP protocol natively.Pythonimport xarray as xr
import numpy as np
import pandas as pd

def fetch_cdip_spectrum(station_id='106p1'):
    """
    Fetches the latest spectral data from CDIP via OPeNDAP.
    station_id: e.g., '106p1' for Waimea Bay.
    """
    # Construct the THREDDS OPeNDAP URL
    url = f"https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/realtime/{station_id}_rt.nc"

    try:
        # Open dataset remotely without downloading the full file (Lazy Loading)
        # Decode_times=True automatically parses the epoch timestamps
        ds = xr.open_dataset(url, decode_times=True)

        # Select the most recent time step
        # Note: CDIP update frequency is typically every 30 minutes
        latest_ds = ds.isel(waveTime=-1)

        # Extract Bulk Parameters
        Hs = float(latest_ds['waveHs'].values) # Significant Wave Height (m)
        Tp = float(latest_ds.values) # Peak Period (s)
        Dp = float(latest_ds.values) # Peak Direction (deg)
        timestamp = pd.to_datetime(latest_ds.values)

        # Extract Frequency Spectrum (Energy Density)
        # Dimensions: [waveFrequency]
        freqs = ds['waveFrequency'].values
        energy = latest_ds.values
        directions = latest_ds.values

        print(f"--- CDIP Station {station_id} Report ---")
        print(f"Time: {timestamp} UTC")
        print(f"Bulk Summary: {Hs:.2f}m @ {Tp:.1f}s from {Dp:.0f}°")

        return {
            'timestamp': timestamp,
            'Hs': Hs,
            'Tp': Tp,
            'Dp': Dp,
            'frequencies': freqs,
            'energy': energy,
            'directions': directions
        }

    except Exception as e:
        print(f"Error connecting to CDIP THREDDS: {e}")
        return None

def analyze_partitions(spectral_data):
    """
    Analyzes the spectrum to separate groundswell from windswell.
    """
    freqs = spectral_data['frequencies']
    energy = spectral_data['energy']
    directions = spectral_data['directions']

    # Define Swell Cutoff (e.g., 10 seconds / 0.1 Hz)
    swell_indices = np.where(freqs < 0.1)

    if len(swell_indices) > 0:
        # Find the peak energy within the swell band
        swell_energy_subset = energy[swell_indices]
        peak_idx_local = np.argmax(swell_energy_subset)
        peak_idx_global = swell_indices[peak_idx_local]

        swell_peak_freq = freqs[peak_idx_global]
        swell_period = 1.0 / swell_peak_freq
        swell_dir = directions[peak_idx_global]

        # Integrate energy to get Swell Height (approximate)
        # Hs = 4 * sqrt(m0)
        df = np.diff(freqs, prepend=0) # Frequency width
        m0_swell = np.sum(energy[swell_indices] * df[swell_indices])
        swell_height = 4 * np.sqrt(m0_swell)

        return {
            'type': 'Groundswell',
            'height_m': swell_height,
            'period_s': swell_period,
            'direction': swell_dir
        }
    return None

# Example Usage
# data = fetch_cdip_spectrum('106p1')
# if data:
#     swell_info = analyze_partitions(data)
#     print(f"Primary Swell Component: {swell_info['height_m']:.2f}m @ {swell_info['period_s']:.1f}s")
Insight for Narrative Generation: This spectral partitioning is what allows Pat Caldwell to say "While the buoy reads 8 feet, it is a mix of 4-foot windswell and 4-foot groundswell." A bulk reading of 8 feet implies a much more powerful surf event than the reality of two smaller, crossed swells. SurfCastAI must use this analyze_partitions logic to avoid false alarms.4. Priority 3: Southern Hemisphere Swell SourcesAccurately forecasting summer south swells for Hawaii is notoriously difficult because the source storms occur in the Tasman Sea and South Pacific, thousands of miles away. The current infrastructure reliance on the Tahiti Buoy is a critical failure point that must be addressed immediately.4.1 The Tahiti Buoy (51407) LimitationA thorough verification of NDBC Station 51407 reveals it is fundamentally unsuitable for swell forecasting. The station is a DART II (Deep-ocean Assessment and Reporting of Tsunamis) buoy.5Sensor Type: Bottom Pressure Recorder (BPR). It measures the height of the water column to detect the passage of tsunami waves.Missing Data: It does not possess an accelerometer or inclinometer to measure surface wave period or direction. It cannot distinguish between a 20-second swell and a 5-second chop.Conclusion: SurfCastAI must decouple from 51407 for surf forecasting metrics.4.2 Strategic Pivot: Copernicus Marine Service (CMEMS)To replace the observational gap left by the Tahiti buoy, we recommend a shift to satellite-derived virtual buoys and the Copernicus Global Wave Model (MFWAM). This system is open-access and provides the spectral partitioning required to track multiple swell trains generated in the Southern Ocean.Dataset ID: GLOBAL_ANALYSISFORECAST_WAV_001_027.6Model Core: MFWAM (Météo-France Wave Model), utilizing the ECWAM-IFS physics package.Key Variables for Hawaii South Swell:VHM0_SW1: Spectral significant height of the primary swell partition.6VTPK_SW1: Peak period of the primary swell.VMDR_SW1: Direction of the primary swell.VHM0_SW2: Secondary swell height (crucial for distinguishing between Tasman energy and localized trade swell).Authentication: Requires a free account registration with Copernicus Marine Service to obtain API credentials.4.3 Python Code: Fetching Global Model DataThe copernicusmarine Python library simplifies the subsetting of global data. The following snippet fetches the forecast specifically for the Hawaii region.Pythonimport copernicusmarine

def fetch_south_swell_forecast():
    """
    Fetches MFWAM wave forecast for the Hawaii region to detect incoming South Swells.
    Requires CMEMS account credentials configured in.copernicusmarine config file.
    """
    dataset_id = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"

    # Define Hawaii South Shore Bounding Box
    # Lat: 10N to 20N (Looking south of the islands)
    # Lon: 165W to 150W

    try:
        # Load dataset with specific variables to minimize transfer size
        ds = copernicusmarine.open_dataset(
            dataset_id = dataset_id,
            minimum_longitude = -165.0,
            maximum_longitude = -150.0,
            minimum_latitude = 10.0,
            maximum_latitude = 20.0,
            variables =
        )

        print("Successfully fetched CMEMS MFWAM data.")
        # Identify South Swell Criteria: Direction between 170 and 220 degrees
        south_swells = ds.where(
            (ds >= 170) & (ds <= 220),
            drop=True
        )

        if south_swells.time.size > 0:
            max_sw = south_swells.max().values
            print(f"Detected South Swell Energy: Max Height {max_sw:.2f}m")
        else:
            print("No significant South Swell energy detected in forecast window.")

        return ds

    except Exception as e:
        print(f"CMEMS Fetch Error: {e}")
        return None
4.4 Travel Time and Decay CalculationsTo provide the "authentic backstory," SurfCastAI must calculate the propagation time from the source.Great Circle Distance ($d$): Calculate the Haversine distance between the storm center (e.g., New Zealand: $45^\circ S, 170^\circ E$) and Honolulu ($21.3^\circ N, 157.8^\circ W$). This is typically ~4,500 nm.Group Velocity ($C_g$): Deep water swell travels at a speed proportional to its period.Formula: $C_g \approx 1.51 \times T$ (knots).Example: For a 16-second swell, $C_g = 1.51 \times 16 = 24.16$ knots.Travel Time: $Time = Distance / C_g$.Example: $4500 \text{ nm} / 24.16 \text{ kts} \approx 186 \text{ hours}$ (approx 7.75 days).Narrative Integration: "This pulse originated from a gale passing New Zealand last Tuesday, traveling over 4,500 miles to reach our shores today."5. Priority 4: ASCAT Satellite Wind ValidationNumerical models (GFS/ECMWF) often smooth out small-scale wind features or underestimate the intensity of "bomb" cyclogenesis. To generate high-confidence storm backstories, SurfCastAI needs visual verification of the wind field strength.5.1 NOAA STAR OSPO ImageryThe NOAA Center for Satellite Applications and Research (STAR) Ocean Surface Winds Team (OSWT) provides scatterometer data. The Manati server is the verified source for ASCAT (Advanced Scatterometer) imagery.Base URL: https://manati.star.nesdis.noaa.gov/datasets/ASCATData.php.13Region Code: The site explicitly lists "Hawaii/Pacific Islands" as a coastal zone sector 14, allowing for targeted image retrieval.Data Latency: Images are typically available with a 2-4 hour latency following the satellite pass.5.2 Correlating ASCAT with Model AnalysisThe validation logic requires comparing the "Predicted" (GFS) vs. "Observed" (ASCAT) state.Fetch GFS MSLP: Retrieve the Mean Sea Level Pressure analysis for time $T-0$. Identify the pressure gradient tightness (isobar spacing).Fetch ASCAT Swath: Retrieve the scatterometer pass for the same region.Validation Check:Scenario A (Validation): GFS predicts 40kt winds; ASCAT shows 40kt wind barbs. -> "Model guidance is accurate."Scenario B (Enhancement): GFS predicts 35kt winds; ASCAT shows a swath of 50-55kt winds (red barbs). -> "Satellite confirmation reveals the storm is over-performing model expectations. Upgrade swell forecast confidence to High."This differential diagnosis is a key trait of expert forecasters and will allow SurfCastAI to issue "Forecaster Notes" that explain why a forecast has been upgraded.6. Priority 5: IBTrACS Storm Track IntegrationTropical cyclones (hurricanes/typhoons) are unique swell generators. They are often small in fetch size but extremely intense, creating "rapid rise" swell events that models can struggle to time accurately.6.1 Accessing the IBTrACS Active Storms FeedThe International Best Track Archive for Climate Stewardship (IBTrACS) provides a consolidated feed of all active tropical systems globally.Verified Data Source: https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04/access/csv/ibtracs.active.list.v04r01.csv.15Format: CSV (Comma Separated Values).Update Frequency: Near real-time (typically every 3-6 hours as agencies update their advisories).6.2 Key Variable ExtractionTo estimate swell potential, the system must extract variables that define the storm's size and intensity 15:SID: Unique Storm ID.NAME: Common Name (e.g., "LANE").USA_LAT, USA_LON: Current position.USA_WIND: Maximum sustained wind speed (knots).USA_R34_NE: Radius of 34-knot winds in the Northeast quadrant. This is a critical proxy for "Fetch Size." A tiny storm with 100kt winds generates less swell than a massive storm with 60kt winds.STORM_DIR, STORM_SPEED: Translation speed. A storm moving with the swell generation direction ("Trapped Fetch") significantly enhances wave height.6.3 Python Code: Active Storm FetchingPythonimport pandas as pd
import numpy as np

def fetch_active_storms():
    """
    Retrieves the list of active tropical cyclones from IBTrACS.
    """
    url = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04/access/csv/ibtracs.active.list.v04r01.csv"

    try:
        # Read CSV directly from URL
        # Skip the second row (units) if present, depending on file version
        df = pd.read_csv(url, skiprows=, low_memory=False)

        # Filter for relevant columns
        cols =

        # Clean data: Ensure numeric types for calculations
        active_df = df[cols].copy()
        active_df = pd.to_numeric(active_df, errors='coerce')

        # Filter for significant storms (e.g., > 50 kts)
        significant_storms = active_df > 50]

        return significant_storms

    except Exception as e:
        print(f"Error fetching IBTrACS: {e}")
        return pd.DataFrame()
7. Priority 6: LLM Prompt Engineering for Surf ForecastingThe final differentiator is the narrative voice. The goal is to avoid the robotic, repetitive output typical of standard weather bots and instead achieve the nuanced, educational, and historically grounded tone of Pat Caldwell.7.1 The Caldwell Persona: Linguistic AnalysisAn analysis of forecast discussions 7 reveals distinct structural and lexical patterns:The "Synopsis" Anchor: Forecasts almost always begin with the synoptic setup (High pressure ridge, cold front positioning) before mentioning wave heights. This establishes scientific credibility.Confidence Markers: Explicit differentiation between high confidence ("will peak") and uncertainty ("models suggest," "could help maintain").The "Hawaii Scale" Filter: Surf heights are communicated in local scale, but often with a nod to the physical reality ("Advisory level surf," "Giant surf").Technical Lexicon: Frequent use of specific terms: "Reinforcing pulse," "Forerunner energy," "Shadowing," "Angular spreading," "Down trend."Historical Contextualization: Referencing "November climatology" or "Rare for this direction."7.2 Prompt Engineering Strategy: Chain-of-Thought (CoT)To replicate this, we cannot simply ask the LLM to "write a forecast." We must use a Chain-of-Thought strategy where the model first analyzes the data and then synthesizes the narrative.Recommended System Prompt Template:Role: You are an expert Marine Meteorologist specializing in Hawaiian surf climatology. Your forecasting style is authoritative, educational, and nuanced, modeled after Pat Caldwell.Objective: Write a surf forecast discussion for Oahu.Data Guidelines:Input Data: You will receive buoy data (physical units), model data (physical units), and historical stats (Hawaii Scale).Conversion Rule: When stating surf heights for the public, ALWAYS convert to Hawaii Scale (approx 50% of physical face height).Terminology: Use 'Face Height' only if explicitly clarifying open ocean power.Style Guidelines:Start Broad: Begin with the synoptic weather situation (High/Low pressure).Be Specific: Mention arrival times of 'forerunners' vs 'peak'.Use Uncertainty: If models disagree, state it.Context: Use the provided Goddard-Caldwell stats to frame the event (e.g., "This is an above-average event for November...").Input Data:Current Buoy 51101: 15ft @ 18sec (NW).Climatology: Nov 26 Avg is 7ft (Hawaii Scale).Wind: Moderate Trades.Output Structure:Synopsis:North Shore Analysis:Historical Note: [Comparison to climatology]7.3 Evaluation CriteriaTo ensure the LLM output meets the "Caldwell Quality" standard, the generated text should be evaluated against the following checklist:Factuality: Did it correctly convert the physical buoy data to reasonable Hawaii Scale estimates (e.g., 15ft@18s -> 20-25ft faces -> 10-12ft Hawaii Scale)?Tone: Did it use the passive-authoritative voice ("A reinforcing swell is expected") rather than active-casual ("You will see big waves")?Context: Did it successfully integrate the "On this day..." historical snippet?8. ConclusionBy implementing these six priorities, SurfCastAI will transition from a data-presentation tool to a decision-intelligence platform. The integration of the Goddard-Caldwell database provides the "memory" lacking in standard models. CDIP spectral data provides the "eyes" to see forecast deviations in real-time. The shift to Copernicus and IBTrACS closes the blind spot on South Swells and tropical systems. Finally, the Persona-Driven Prompting ensures the output resonates with the target audience—surfers who trust experience as much as they trust data.(End of Report)
