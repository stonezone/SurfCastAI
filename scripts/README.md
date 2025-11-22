# SurfCastAI Scripts

## 🏄 Surf Launcher - Totally Tubular Edition

A radical, 80s-themed CLI launcher for the SurfCastAI surf forecasting system. Because predicting waves should be as gnarly as riding them!

### Features

- **80s Surf Theme**: Radical ASCII art, retro vibes, and gnarly slang
- **Color-Coded Interface**: Green for success, red for errors, cyan for info
- **Interactive Menus**: Easy navigation with number selection
- **Model Management**: Switch between GPT-5-nano, GPT-5-mini, and GPT-5
- **Bundle Selection**: Choose specific data bundles for forecasting
- **Status Bar**: See current model, specialist team status, and latest bundle
- **Comprehensive Help**: Learn about each feature with fun explanations

### Installation

1. Install colorama for color support (optional but recommended):
```bash
pip install colorama
```

2. Make the script executable (already done):
```bash
chmod +x scripts/surf_launcher.py
```

### Usage

Run the launcher:
```bash
python scripts/surf_launcher.py
```

Or directly (if executable):
```bash
./scripts/surf_launcher.py
```

### Main Menu Options

1. **Run Full Forecast**: Collect data + process + generate forecast (all-in-one!)
2. **Collect Data Only**: Grab fresh data without generating forecast
3. **Generate Forecast (latest)**: Use most recent data bundle
4. **Generate Forecast (select)**: Pick a specific bundle
5. **Model Settings**: Switch AI models and view config
6. **Toggle Specialist Team**: Enable/disable multi-agent analysis
7. **View Recent Forecasts**: Browse generated forecast outputs
8. **List Data Bundles**: See all available data collections
9. **Help/Info**: Learn about features and get surf tips!
0. **Exit**: Catch you later!

### Model Settings

- **GPT-5-nano**: Fast & cheap - great for testing
  - Speed: ★★★★★
  - Cost: ★★★★★
  - Quality: ★★★☆☆

- **GPT-5-mini**: Balanced performance (recommended)
  - Speed: ★★★★☆
  - Cost: ★★★★☆
  - Quality: ★★★★☆

- **GPT-5**: Maximum accuracy
  - Speed: ★★★☆☆
  - Cost: ★★☆☆☆
  - Quality: ★★★★★

### Specialist Team

When enabled, uses multiple AI agents for comprehensive analysis:
- Swell Expert - wave pattern analysis
- Wind Specialist - wind condition evaluation
- Weather Analyst - weather pattern review
- Tides Guru - tidal effect assessment

Results in more detailed forecasts but takes longer to run.

### 80s Slang Guide

The launcher is packed with authentic 80s surf slang:

**Success Messages**:
- "Totally radical!"
- "Gnarly!"
- "Tubular!"
- "Cowabunga!"
- "Most excellent!"

**Error Messages**:
- "Bummer, dude!"
- "Bogus!"
- "Major wipeout!"
- "Totally uncool!"

**Status Messages**:
- "Hang loose..."
- "Shredding data..."
- "Catching some waves..."
- "Paddling out..."

### Navigation

- Enter number to select menu option
- `b` to go back to previous menu
- `0` to exit
- `Ctrl+C` for emergency exit (will display a tubular goodbye)

### Troubleshooting

**Colors not working?**
- Install colorama: `pip install colorama`
- The launcher works without it, just without colors

**Can't find config.yaml?**
- Launcher looks in `config/config.yaml`
- Make sure you're running from project root

**No bundles showing?**
- Collect data first using option 2
- Check `data/` directory exists

### Fun Facts

- The ASCII wave art uses authentic 1985 typography
- All slang terms are period-accurate to the 80s surf culture
- The surfboard ASCII art is totally tubular
- Status messages rotate randomly for variety
- Error messages are designed to be fun, not frustrating

### Contributing

Want to make it even more radical? Ideas for enhancements:

- Add more ASCII art (dolphins, sharks, palm trees)
- Implement sound effects (if terminal supports beeps)
- Add more 80s slang phrases
- Create animated wave effects
- Add forecast comparison features
- Implement bookmark system for favorite bundles

### License

Part of the SurfCastAI project - Catch you on the next wave! 🏄🤙
