# SurfCastAI Follow-Up Tasks — 2025-10-16

## Caldwell Alignment Gaps
- Restore altimetry coverage: add STAR/JASON fallbacks (gridded PNG + netCDF) and parse peak SSH so forecasts can cite the >35 ft measurements Pat highlights.
- Fix CDIP nearshore ingestion: authenticate or swap to the THREDDS/JSON endpoints, persist donut spectra, and surface directional energy in fusion outputs.
- Enable WW3 point guidance: implement `{date}` templating for NOMADS URLs, cache CSV responses, and wire parsed swell trains into DataFusion so long-range phases mirror Caldwell’s timeline.
- Upper-air jet diagnostics: provide working mirrors for WPC 250 mb/500 mb charts, fall back to OPC imagery on 404, and pipe jet summaries into the context builder.

## Pipeline Stability
- Patch `DataCollector` size accounting to tolerate `size_bytes=None` (satellite agent currently throws `int(None)` and logs a hard error).
- Harden `SatelliteAgent` to retry GOES sector fallbacks when the primary URL 404s and ensure metadata fields are populated instead of left null.
- Add regression coverage in `tests/integration/collector/` so bundle stats remain consistent when new agent feeds fail or downgrade gracefully.

## Forecast Calibration
- Audit fusion-to-prompt scaling: current runs pass deepwater H1/3 directly as Hawaiian-scale faces (North Shore 20–30 ft, South 5–8 ft) contradicting Pat’s 2025-10-15 bulletin; adjust conversion heuristics and add fixtures in `tests/unit/forecast_engine/test_data_manager.py`.
- Teach the context builder/formatter to cite climatology assets now collected (Goddard–Caldwell DB, SNN monthly stats) so forecasts echo Pat’s percentile framing.
- After fixing the feed gaps, re-run GPT-5-mini and GPT-5 on bundle `20373f89-96a1-45fd-a3b8-6a9a47497ea4` and capture the deltas versus Pat’s 2025-10-15 outlook in `docs/forecast_comparison_20251015.md`.

## Next Run Checklist
1. Repair the feeds and scaling issues above.
2. Collect/process data (or reuse the fixed bundle) and regenerate GPT-5-mini plus GPT-5 forecasts with complete metadata.
3. Compare against Pat’s 2025-10-15 report, logging remaining deviations and residual data deficits.
