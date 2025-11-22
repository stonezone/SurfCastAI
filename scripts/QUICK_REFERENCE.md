# 🏄 SurfCastAI Launcher - Quick Reference Card

## Launch Command
```bash
python scripts/surf_launcher.py
```

## Main Menu Quick Keys

| Key | Action | Description |
|-----|--------|-------------|
| `1` | Full Forecast | Collect + Process + Forecast (all-in-one) |
| `2` | Collect Only | Grab fresh data without forecasting |
| `3` | Forecast Latest | Use most recent data bundle |
| `4` | Forecast Select | Choose specific bundle |
| `5` | Model Settings | Switch AI models (nano/mini/5) |
| `6` | Specialist Team | Toggle multi-agent mode (ON/OFF) |
| `7` | Recent Forecasts | View generated forecasts |
| `8` | List Bundles | Show data collections |
| `9` | Help | Complete help + surf tips |
| `0` | Exit | Catch you later! |

## Model Settings Keys

| Key | Model | Speed | Cost | Quality |
|-----|-------|-------|------|---------|
| `1` | GPT-5-nano | ★★★★★ | ★★★★★ | ★★★☆☆ |
| `2` | GPT-5-mini | ★★★★☆ | ★★★★☆ | ★★★★☆ |
| `3` | GPT-5 | ★★★☆☆ | ★★☆☆☆ | ★★★★★ |
| `4` | View Config | - | - | - |
| `b` | Back | - | - | - |

## Universal Commands

| Key | Action | Available |
|-----|--------|-----------|
| `b` | Back | All submenus |
| `0` | Exit/Cancel | All menus |
| `Ctrl+C` | Emergency Exit | Anywhere |

## Status Bar

```
┌────────────────────────────────────────────────────┐
│ Model: [current] │ Specialist: [ON/OFF] │ Bundle: [ID] │
└────────────────────────────────────────────────────┘
```

**Shows:**
- Current AI model (nano/mini/5)
- Specialist team status (ON/OFF)
- Latest bundle ID (first 10 chars)

## Specialist Team

| Mode | Speed | Cost | Analysis | Best For |
|------|-------|------|----------|----------|
| OFF (Single) | ⚡ Fast | 💰 Cheap | 👤 One AI | Daily |
| ON (Team) | 🐌 Slow | 💸 Expensive | 👥 Four AIs | Important |

**Team Members:**
- Swell Expert (wave patterns)
- Wind Specialist (wind conditions)
- Weather Analyst (weather patterns)
- Tides Guru (tidal effects)

## File Locations

| Type | Path | Contents |
|------|------|----------|
| Config | `config/config.yaml` | Settings |
| Bundles | `data/[bundle-id]/` | Collected data |
| Forecasts | `output/forecast_*/` | Generated forecasts |
| Logs | `logs/surfcastai.log` | System logs |

## Output Formats

Each forecast generates:
- `forecast.md` - Markdown format
- `forecast.html` - Web format (mobile-friendly)
- `forecast.pdf` - Printable format
- `visualizations/` - Charts and graphs

## Common Workflows

### First Time Setup
1. Install colorama: `pip install colorama`
2. Configure API key in `.env`
3. Launch: `python scripts/surf_launcher.py`
4. Press `9` for help

### Quick Forecast
1. Launch launcher
2. Press `1` (Full Forecast)
3. Press `y` to confirm
4. Wait for completion
5. Check `output/` directory

### Model Testing
1. Press `5` (Model Settings)
2. Press `1` (GPT-5-nano)
3. Press `b` (Back)
4. Press `1` (Full Forecast)
5. Compare with other models

### Bundle Comparison
1. Press `8` (List Bundles)
2. Note bundle IDs
3. Press ENTER
4. Press `4` (Select Bundle)
5. Choose bundle number
6. Compare forecasts

## Slang Translator

### Success = Rad!
- "Totally radical!" ✅
- "Gnarly!" ✅
- "Tubular!" ✅
- "Cowabunga!" ✅
- "Most excellent!" ✅

### Errors = Bummer!
- "Bummer, dude!" ❌
- "Bogus!" ❌
- "Weak sauce!" ❌
- "Major wipeout!" ❌

### Processing = Hang Loose!
- "Shredding data..." ⏳
- "Catching waves..." ⏳
- "Paddling out..." ⏳

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No colors | `pip install colorama` |
| No bundles | Press `2` to collect data |
| Config error | Check `config/config.yaml` exists |
| API error | Add key to `.env` file |
| Forecast fails | Ensure data is collected first |

## Configuration Files

### `.env` (API Key)
```bash
OPENAI_API_KEY=sk-your-key-here
```

### `config/config.yaml` (Model)
```yaml
openai:
  model: gpt-5-mini  # or gpt-5-nano, gpt-5
```

## Command Line Equivalents

Launcher automates these commands:

| Launcher | Command Line |
|----------|-------------|
| Menu → 1 | `python src/main.py run --mode full` |
| Menu → 2 | `python src/main.py run --mode collect` |
| Menu → 3 | `python src/main.py run --mode forecast` |
| Menu → 4 | `python src/main.py run --mode forecast --bundle ID` |
| Menu → 7 | `python src/main.py list` |
| Menu → 8 | `ls data/` |

## Documentation Links

| Doc | Purpose |
|-----|---------|
| `QUICK_START_LAUNCHER.md` | Getting started |
| `scripts/README.md` | Full launcher docs |
| `scripts/LAUNCHER_FEATURES.md` | Feature list |
| `scripts/SCREENSHOTS.md` | Visual examples |
| `README.md` | Main project docs |

## Keyboard Shortcuts

| Key | Function |
|-----|----------|
| `Enter` | Confirm/Continue |
| `0` | Exit/Cancel |
| `b` | Back |
| `1-9` | Menu selection |
| `y/n` | Yes/No prompts |
| `Ctrl+C` | Emergency exit |

## Pro Tips

1. **Start with nano** - Test with fast model first
2. **Collect once** - Reuse bundles for testing
3. **Check status bar** - Always verify settings
4. **Use help** - Press `9` for detailed info
5. **Bundle selection** - Compare different times

## ASCII Art Preview

```
╔════════════════════════════════════════╗
║  🏄 SURFCASTAI LAUNCHER 🏄           ║
║     ___    ___    ___    ___          ║
║  __/   \__/   \__/   \__/   \__       ║
║___/                        \___       ║
╚════════════════════════════════════════╝
```

## Color Scheme

| Color | Usage |
|-------|-------|
| Cyan | Menus, info |
| Green | Success |
| Red | Errors |
| Yellow | Warnings, highlights |
| Magenta | Emphasis |
| Blue | ASCII art |

## Quick Start (30 Seconds)

```bash
# 1. Install colors (optional)
pip install colorama

# 2. Launch
python scripts/surf_launcher.py

# 3. Press ENTER at welcome

# 4. Press 9 for help
# 5. Press 1 for full forecast
# 6. Press y to confirm

# Done! Check output/ directory
```

## One-Liner Commands

```bash
# Full forecast (non-interactive)
python src/main.py run --mode full

# Launch tubular interface
python scripts/surf_launcher.py

# View demo
bash scripts/launcher_demo.sh
```

## Support

- **Built-in Help**: Menu → 9
- **Documentation**: See links above
- **Code**: `scripts/surf_launcher.py` (well-commented)

---

**Print this card for quick reference!**

*Hang loose and keep shredding!* 🏄🤙
