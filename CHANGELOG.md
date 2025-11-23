# Changelog

All notable changes to SurfCastAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release
- AI-powered surf forecasting for Oahu, Hawaii
- Multi-source data collection (NDBC buoys, NWS weather, wave models, satellite)
- Automated forecast validation system with accuracy metrics
- Hawaiian scale wave height calculations
- Pat Caldwell-style forecast formatting
- Web viewer for browsing forecasts
- Interactive CLI launcher with 80s surf theme
- Comprehensive security features (SSRF protection, archive validation, API key management)
- SPC upper-air chart integration (250mb/500mb)

### Changed
- Fixed Hawaiian scale conversion formula (meters to feet, not face height)
- Improved data fusion with reliability scoring
- Enhanced confidence metrics based on data quality

### Security
- API keys now required via environment variables only (removed from config files)
- SSRF protection for all external URLs
- Zip bomb and path traversal protection for archives
- Physical bounds validation on all buoy data

## [0.1.0] - 2025-11-23

### Added
- Initial project structure
- Core data collection agents
- Data processing and fusion system
- OpenAI GPT-4/GPT-5 integration
- Forecast generation engine
- Validation database and accuracy tracking
- Multi-format output (Markdown, HTML, PDF)

---

For detailed development history, see individual commit messages.
