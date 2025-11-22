# Prompt Templates

SurfCastAI loads prompts from versioned JSON files under `config/prompts/` using `src/utils/prompt_loader.py`.

## Layout

```
config/prompts/
├── v1/
│   ├── caldwell_main.json
│   ├── north_shore.json
│   ├── south_shore.json
│   ├── daily.json
│   └── …
└── README.md
```

Set `forecast.templates_dir` (default `config/prompts`) and the loader will pick the newest version directory (e.g., `v1/`).

## JSON Fields

Each prompt file follows this structure:

```json
{
  "version": "1.0",
  "name": "caldwell_main",
  "description": "Main narrative forecast",
  "system_prompt": "...",
  "user_prompt_template": "...",
  "variables": ["forecast_data", "seasonal_context"],
  "model_settings": {
    "temperature": 0.7,
    "max_tokens": 8000
  }
}
```

- `system_prompt`: role instructions sent to GPT.
- `user_prompt_template`: text with placeholders replaced at runtime.
- `variables`: placeholders available to the template.
- `model_settings`: optional overrides for temperature/max tokens.

## Loader & Fallback

`PromptLoader` validates JSON, caches prompts, and exposes them to `ForecastEngine`. If a JSON file is missing or invalid, the loader falls back to the default templates embedded in `src/forecast_engine/prompt_templates.py`.

### Alias Mapping

`PromptLoader.as_templates()` maps JSON names to the classic keys used by `PromptTemplates`:

| JSON name        | Alias in engine |
|------------------|-----------------|
| `caldwell_main`  | `caldwell`      |
| `north_shore`    | `north_shore`   |
| `south_shore`    | `south_shore`   |
| `daily`          | `daily`         |

## Example: `caldwell_main.json`

```json
{
  "version": "1.0",
  "name": "caldwell_main",
  "description": "Pat Caldwell-style long narrative",
  "system_prompt": "You are Pat Caldwell...",
  "user_prompt_template": "{{forecast_data.main_forecast}}\n\nConfidence: {{forecast_data.confidence.overall_score}}",
  "variables": ["forecast_data", "seasonal_context", "image_analysis"],
  "model_settings": {
    "temperature": 0.6,
    "max_tokens": 9000
  }
}
```

Customize prompts by cloning `v1/` into `v2/`, editing the JSON, and pointing `forecast.templates_dir` to the new version.
