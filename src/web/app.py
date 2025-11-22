"""Minimal FastAPI app that serves generated SurfCastAI forecasts."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import re

# Rate limiting imports
try:  # pragma: no cover - dependency optional in some environments
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except ImportError:  # Fallback when slowapi is unavailable
    _SLOWAPI_AVAILABLE = False

    class RateLimitExceeded(Exception):
        """Fallback exception when slowapi is not installed."""

    class Limiter:  # type: ignore
        def __init__(self, *args, **kwargs):
            self._default_limits = kwargs.get('default_limits', [])

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def get_remote_address(request: Request) -> str:  # type: ignore
        return request.client.host if request.client else '0.0.0.0'

    def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):  # type: ignore
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later."
            }
        )

    # Provide stub modules so downstream imports succeed
    import sys
    import types

    slowapi_module = types.ModuleType("slowapi")
    slowapi_errors_module = types.ModuleType("slowapi.errors")
    slowapi_util_module = types.ModuleType("slowapi.util")

    slowapi_module.Limiter = Limiter
    slowapi_module._rate_limit_exceeded_handler = _rate_limit_exceeded_handler
    slowapi_errors_module.RateLimitExceeded = RateLimitExceeded
    slowapi_util_module.get_remote_address = get_remote_address

    sys.modules.setdefault('slowapi', slowapi_module)
    sys.modules.setdefault('slowapi.errors', slowapi_errors_module)
    sys.modules.setdefault('slowapi.util', slowapi_util_module)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.security import SecurityError


def validate_forecast_id(forecast_id: str) -> str:
    """
    Validate and sanitize forecast_id to prevent path traversal.

    Args:
        forecast_id: User-provided forecast ID

    Returns:
        Sanitized forecast_id

    Raises:
        HTTPException: If forecast_id contains path traversal attempts
    """
    # Check for path traversal sequences
    if ".." in forecast_id or "/" in forecast_id or "\\" in forecast_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid forecast_id: path traversal not allowed"
        )

    # Check for null bytes
    if "\x00" in forecast_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid forecast_id: null bytes not allowed"
        )

    # Ensure forecast_id matches expected pattern (forecast_YYYYMMDD_HHMMSS)
    if not re.match(r'^forecast_\d{8}_\d{6}$', forecast_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid forecast_id format: must be forecast_YYYYMMDD_HHMMSS"
        )

    return forecast_id


def sanitize_and_validate_path(
    user_input: str, base_dir: Path, should_exist: bool = True
) -> Path:
    """
    Sanitize and validate a file path to prevent directory traversal.

    Args:
        user_input: User-provided path component
        base_dir: Base directory that final path must be within
        should_exist: Whether to check if the path exists

    Returns:
        Validated Path object

    Raises:
        SecurityError: If path validation fails
        HTTPException: If path doesn't exist when required
    """
    # Resolve base directory to absolute path
    base_dir = base_dir.resolve()

    # Construct the full path
    full_path = (base_dir / user_input).resolve()

    # Security check: ensure the resolved path is within base_dir
    try:
        full_path.relative_to(base_dir)
    except ValueError:
        raise SecurityError(
            f"Path traversal attempt detected: {user_input} resolves outside base directory"
        )

    # Check existence if required
    if should_exist and not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return full_path

OUTPUT_ROOT = Path(os.getenv("SURFCAST_OUTPUT_DIR", "output"))
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# Initialize rate limiter
# For production with multiple workers, use Redis: storage_uri="redis://localhost:6379"
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"],  # Default: 100 requests per hour per IP
    storage_uri="memory://",  # In-memory storage (for single-worker development)
)

app = FastAPI(title="SurfCastAI", description="Local forecast viewer", version="1.0.0")

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler with clear error messages."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else None
        },
        headers={
            "Retry-After": "3600"  # Suggest retry after 1 hour
        }
    )


def _forecast_dirs() -> List[Path]:
    candidates = [p for p in OUTPUT_ROOT.iterdir() if p.is_dir()]
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)


@app.get("/", response_class=HTMLResponse)
@limiter.limit("200 per hour")  # Index page - generous limit
async def index(request: Request) -> HTMLResponse:
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
@limiter.limit("60 per hour")  # HTML viewer - moderate limit
async def serve_forecast(forecast_id: str, request: Request) -> HTMLResponse:
    try:
        # Validate forecast_id to prevent path traversal
        forecast_id = validate_forecast_id(forecast_id)

        # Construct and validate the HTML file path
        html_path_str = f"{forecast_id}/{forecast_id}.html"
        validated_html = sanitize_and_validate_path(html_path_str, OUTPUT_ROOT, should_exist=True)

        # Additional path resolution check to ensure path is within output directory
        output_dir = OUTPUT_ROOT.resolve()
        if not validated_html.resolve().is_relative_to(output_dir):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside output directory"
            )

        return HTMLResponse(content=validated_html.read_text())
    except SecurityError as e:
        raise HTTPException(status_code=403, detail="Access denied: Invalid path")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/forecasts/latest", response_class=JSONResponse)
@limiter.limit("100 per hour")  # Latest forecast API - moderate limit
async def latest_forecast(request: Request) -> JSONResponse:
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
@limiter.limit("60 per hour")  # JSON API - moderate limit
async def forecast_detail(forecast_id: str, request: Request) -> JSONResponse:
    try:
        # Validate forecast_id to prevent path traversal
        forecast_id = validate_forecast_id(forecast_id)

        # Construct and validate the JSON file path
        json_path_str = f"{forecast_id}/forecast_data.json"
        validated_path = sanitize_and_validate_path(json_path_str, OUTPUT_ROOT, should_exist=True)

        # Additional path resolution check to ensure path is within output directory
        output_dir = OUTPUT_ROOT.resolve()
        if not validated_path.resolve().is_relative_to(output_dir):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside output directory"
            )

        payload = json.loads(validated_path.read_text())
        return JSONResponse(payload)
    except SecurityError as e:
        raise HTTPException(status_code=403, detail="Access denied: Invalid path")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/assets/{forecast_id}/{path:path}")
@limiter.limit("200 per hour")  # Assets - higher limit for page resources
async def serve_asset(forecast_id: str, path: str, request: Request) -> FileResponse:
    try:
        # Validate forecast_id to prevent path traversal
        forecast_id = validate_forecast_id(forecast_id)

        # Sanitize asset path to prevent directory traversal
        # Block any attempts to go up directories or use absolute paths
        if ".." in path or path.startswith("/") or path.startswith("\\"):
            raise HTTPException(status_code=400, detail="Invalid asset path")

        # Construct and validate the full asset path
        asset_path_str = f"{forecast_id}/assets/{path}"
        validated_path = sanitize_and_validate_path(asset_path_str, OUTPUT_ROOT, should_exist=True)

        # Additional path resolution check to ensure path is within output directory
        output_dir = OUTPUT_ROOT.resolve()
        if not validated_path.resolve().is_relative_to(output_dir):
            raise HTTPException(
                status_code=403,
                detail="Access denied: path outside output directory"
            )

        # Additional check: ensure it's a file, not a directory
        if validated_path.is_dir():
            raise HTTPException(status_code=403, detail="Cannot serve directories")

        return FileResponse(validated_path)
    except SecurityError as e:
        raise HTTPException(status_code=403, detail="Access denied: Invalid path")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "forecasts": len(_forecast_dirs()),
    }
