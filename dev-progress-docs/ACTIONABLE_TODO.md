# SurfCastAI Actionable Checklist (2025-10-16)

## Owner: Zack (actions only you can drive)

| ID | Task | Details & Deliverables | Dependencies |
|----|-------|-------------------------|---------------|
| Z1 | **Secure reliable UH climatology access** | • Contact UH Sea Level Center or mirror the “Oahu Surf Climatology” page that’s returning DNS failures.<br>• Provide Code with a stable HTTPS endpoint or an archived HTML dump so the ClimatologyAgent can ingest percentile tables.<br>• Upload any credentials/API keys via `.env` (not committed). | Needed by Code for R1 (climatology context). |
| Z2 | **Request CDIP authenticated API/mirror** | • Reach out to CDIP administrators for sustained HTTPS or THREDDS access to directional spectra (stations 106/225/239/249).<br>• If authentication tokens/certs are needed, obtain and share securely via `.env`/1Password.<br>• Optional: negotiate with PacIOOS for a maintained JSON mirror. | Enables Code task R2 (robust nearshore ingestion). |
| Z3 | **Provision compute/storage for validation archive** | • Confirm there’s ample disk/backup strategy for nightly validation DB growth (~100 MB/day with detailed buoy logs).<br>• If using external object storage (S3/GCS), provide bucket credentials.<br>• Let Code know retention policy (e.g., keep 90 days). | Required before Code implements the expanded validation loop (R4). |
| Z4 | **Schedule/approve operational cron** | • Approve or create a systemd/cron job (midnight HST) that runs full collect→process→forecast and validation pipeline.<br>• If running on production server, ensure firewall rules and uptime monitors are in place.<br>• Provide Code with the exact execution window or automation constraints. | Needed for Code task R6 (automation). |
| Z5 | **Stakeholder review of swell-scaling model** | • Once Code delivers the calibrated scaling (R3), review the output trends and sign off on acceptable MAE/RMSE targets.<br>• Decide acceptable alert thresholds for auto-adjustment (e.g., flag >1.0 ft bias). | Depends on Code completing R3. |
| Z6 | **Gather human observation sources** | • Curate access to beach cams or lifeguard report feeds we can legally scrape or consume (Surfline, HONsurfreport, etc.).<br>• Provide authentication/API details if required.<br>• Confirm terms of use for ingesting these feeds into the validation module. | Enables Code’s R4 (validation blending). |

## Owner: Code (Assistant)

| ID | Task | Details & Deliverables | Dependencies |
|----|-------|-------------------------|---------------|
| R1 | **Integrate climatology percentiles** | • When Z1 delivers a stable endpoint, parse daily percentile values and surface them in `context_builder` and formatted forecast (matching Caldwell’s stats mentions).<br>• Add regression tests to `tests/unit/forecast_engine`. | Wait for Z1. |
| R2 | **Finalize nearshore/CDIP ingestion** | • Add retry logic plus streaming download support for large netCDFs.<br>• Parse spectra and directional energy, attach to metadata + narrative.<br>• Write tests for fallback to NDBC mirror when CDIP throttles.<br>• Requires Z2 for durable endpoint. | Wait for Z2. |
| R3 | **Calibrate Hawaiian-scale conversion** | • Build reef/direction/period-specific scaling tables from historical 5120x vs. source buoys, embed in fusion/formatter.<br>• Add tests showing corrected H1/3/H1/10 vs. Pat benchmarks.<br>• After Z5 review, lock thresholds. | No external dependency (but review in Z5). |
| R4 | **Expand validation loop** | • Store hindcast errors (MAE/RMSE) per shore + swell class, log to dashboard.<br>• Blend lifeguard/climatology data when available.<br>• Requires storage from Z3 and observation feeds from Z6. | Wait for Z3, Z6. |
| R5 | **Implement phase classifier + narrative** | • Use storm detector + WW3 + altimetry to label events (“Phase 1/2/3”), update prompts to mirror Caldwell’s multi-phase storytelling.<br>• Provide tests and example contexts. | Relies on R2, R3, R4 data improvements but can start now. |
| R6 | **Automate nightly pipeline & monitoring** | • Add CLI/tooling for cron, integrate with health checks, send Slack/email alerts on failures.<br>• Requires Z4 (schedule/approval) and Z3 (storage). | Wait for Z3, Z4. |
| R7 | **Bias-aware narrative adjustments** | • Once R4 captures bias metrics, auto-adjust narrative tone/height to prevent overstatement.<br>• Provide configuration knobs so Zack can set acceptable error thresholds. | Depends on R3 + R4. |

## Joint (need both)

| ID | Task | What we each do | Trigger |
|----|------|------------------|---------|
| J1 | **WW3 calibration review** | Code prepares sample forecasts post-R3; Zack reviews and signs off (Z5). | After R3. |
| J2 | **Validation dashboard sign-off** | Code builds dashboard (R4/R6); Zack verifies availability & approves ops flow. | After R4 & R6. |
| J3 | **Data access updates** | Zack obtains credentials (Z1/Z2/Z6); Code integrates them and confirms success. | As soon as Zack completes each data task. |

> Keep this checklist updated as tasks complete. Each dependency arrow should prompt a quick sync before work starts.
