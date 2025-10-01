"""Minimal FastAPI app that serves generated SurfCastAI forecasts."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

OUTPUT_ROOT = Path(os.getenv("SURFCAST_OUTPUT_DIR", "output"))
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SurfCastAI", description="Local forecast viewer", version="1.0.0")


def _forecast_dirs() -> List[Path]:
    candidates = [p for p in OUTPUT_ROOT.iterdir() if p.is_dir()]
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    rows = []
    for directory in _forecast_dirs():
        forecast_id = directory.name
        meta_path = directory / "forecast_data.json"
        generated = "Unknown"
        if meta_path.exists():
            try:
                payload = json.loads(meta_path.read_text())
                generated = payload.get("generated_time", generated)
            except Exception:
                pass
        rows.append((forecast_id, generated))

    if not rows:
        body = "<p>No forecasts generated yet. Run the pipeline to create one.</p>"
    else:
        items = "".join(
            f"<li><a href=\"/forecasts/{fid}\">{fid}</a> <small>({generated})</small></li>"
            for fid, generated in rows
        )
        body = f"<ul>{items}</ul>"

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>SurfCastAI Forecasts</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0 auto; max-width: 640px; padding: 24px; background: #f5f7fa; }}
    h1 {{ text-align: center; color: #0066cc; }}
    ul {{ list-style: none; padding: 0; }}
    li {{ background: #fff; margin-bottom: 12px; padding: 12px; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    a {{ color: #0066cc; text-decoration: none; font-weight: 600; }}
    a:hover {{ text-decoration: underline; }}
    small {{ color: #666; }}
  </style>
</head>
<body>
  <h1>SurfCastAI Forecasts</h1>
  {body}
</body>
</html>"""
    return HTMLResponse(html)


@app.get("/forecasts/{forecast_id}", response_class=HTMLResponse)
async def serve_forecast(forecast_id: str) -> HTMLResponse:
    forecast_dir = OUTPUT_ROOT / forecast_id
    html_path = forecast_dir / f"{forecast_id}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Forecast not found")
    return HTMLResponse(content=html_path.read_text())


@app.get("/api/forecasts/latest", response_class=JSONResponse)
async def latest_forecast() -> JSONResponse:
    directories = _forecast_dirs()
    if not directories:
        raise HTTPException(status_code=404, detail="No forecasts available")
    latest_dir = directories[0]
    json_path = latest_dir / "forecast_data.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Forecast data missing")
    payload = json.loads(json_path.read_text())
    return JSONResponse(payload)


@app.get("/api/forecasts/{forecast_id}", response_class=JSONResponse)
async def forecast_detail(forecast_id: str) -> JSONResponse:
    json_path = OUTPUT_ROOT / forecast_id / "forecast_data.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Forecast data missing")
    payload = json.loads(json_path.read_text())
    return JSONResponse(payload)


@app.get("/assets/{forecast_id}/{path:path}")
async def serve_asset(forecast_id: str, path: str) -> FileResponse:
    asset_path = OUTPUT_ROOT / forecast_id / "assets" / path
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset_path)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "forecasts": len(_forecast_dirs()),
    }
