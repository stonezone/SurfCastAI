# Repository Guidelines

## Project Structure & Module Organization
SurfCastAI uses an `src`-first layout. Core orchestration sits in `src/main.py`, collectors in `src/agents`, shared services in `src/core`, forecast formatting/visuals in `src/forecast_engine`, and the FastAPI viewer in `src/web`. Config templates live in `config/`; generated artifacts go to `data/`, `output/`, and `logs/`. Tests live in `tests/` (seed suite in `tests/unit/forecast_engine`), while tooling such as `benchmark_forecast_engine.py` and `show_demo.py` stays at the project root.

## Build, Test, and Development Commands
Run `./setup.sh` once to provision `venv/`, install dependencies, and seed configs. Activate the environment with `source venv/bin/activate`. Execute the full pipeline via `python src/main.py run --mode full`, or switch to `collect`/`forecast` for partial runs. `python -m unittest discover -s tests` covers the suite, `python test_forecast_engine.py` exercises formatter flows, and `python benchmark_forecast_engine.py --component engine` profiles throughput. Launch the web viewer locally with `uvicorn src.web.app:app --reload` to browse rendered forecasts and charts.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation, type hints, and docstrings that mirror existing modules. Modules should stay single-purpose; place shared helpers in `src/utils`. Use `snake_case` for functions and variables, `CamelCase` for classes, and reserve inheritance from `BaseAgent` for reused cross-source behavior. Surface new defaults through `Config` instead of hardcoding literal values.

## Testing Guidelines
Add tests beside the feature they cover, e.g., `tests/unit/forecast_engine/test_new_component.py`. Stick with `unittest`; if pytest-only helpers are needed, guard them so `python -m unittest` still runs. Keep synthetic fixtures lean and reuse helpers in `test_forecast_engine.py` for forecast scaffolding. Point test writes to `output/test` via `config/test_config.yaml`, and rerun any affected benchmarks before submitting.

## Commit & Pull Request Guidelines
Git history favors Conventional Commits (`feat:`, `docs:`), so keep subjects under 72 characters and describe the behavior change. PR descriptions should call out touched data sources, test coverage, and config updates (e.g., new keys in `config/config.yaml`). Attach before/after artifacts when generated forecasts or benchmarks change, and request review whenever pipelines, rate limiting, or scoring logic is modified.

## Configuration & Secrets
Do not hardcode API keys; place them in `.env` or `config/config.yaml` following the template created by `setup.sh`. Enable the offline rule-based writer by keeping `forecast.use_local_generator: true` whenever OpenAI credentials are missing. Confirm `config/test_config.yaml` remains CI-safe before pushing. Logs accumulate in `logs/`; prune oversized files pre-commit. When wiring new services, document retry and timeout settings in `config/config.example.yaml`, and advertise new environment knobs such as `SURFCAST_OUTPUT_DIR` when running the FastAPI viewer. Always run `verify_dependencies.py` after dependency changes.
