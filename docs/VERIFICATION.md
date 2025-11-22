# Manual Forecast Verification Checklist

## Quick Sweep
- Run `python src/main.py run --mode full` (ensure success message).
- Tail logs: `tail -50 logs/surfcastai.log` (check for errors).
- Inspect latest output: `ls output/ | head -3` and open the newest forecast (Markdown/HTML).
- Confirm automatic DB persistence:
  ```bash
  sqlite3 data/validation.db "SELECT forecast_id, created_at FROM forecasts ORDER BY created_at DESC LIMIT 1;"
  sqlite3 data/validation.db "SELECT COUNT(*) FROM predictions WHERE forecast_id='forecast_YYYYMMDD_HHMMSS';"
  ```

## Content Quality
- All shores covered (North/South/West/East) with swell sizes, periods, directions.
- Confidence scores present and plausible (>0.6 typical).
- Image analysis sections populated when GPT-5 Vision enabled.
- Pat Caldwell tone maintained (technical, concise, actionable).

## Troubleshooting
- **Missing DB rows:** rerun `python src/main.py validate-config` and inspect `logs/surfcastai.log` for `ValidationDatabase` errors.
- **Empty forecast sections:** confirm bundle data (`data/<bundle>/processed/fused_forecast.json`) has swell events.
- **Vision analysis absent:** verify `forecast.max_images` > 0 and images exist under `data/<bundle>/`.
- **Token overruns:** adjust `forecast.token_budget` or reduce `max_images`/detail levels.
