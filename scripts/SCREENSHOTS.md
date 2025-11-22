# 🏄 SurfCastAI Launcher Screenshots

Here's what the totally tubular launcher looks like in action!

## Welcome Screen

```
╔════════════════════════════════════════════════════════════════════╗
║  🏄 SURFCASTAI LAUNCHER 🏄  [Totally Tubular Edition v1.0] 🤙    ║
║                                                                    ║
║       ___    ___    ___    ___                                   ║
║    __/   \__/   \__/   \__/   \__     Hang Ten with AI!          ║
║ ___/                            \___                          ║
║                                                                    ║
║           ~ Catching the Perfect Forecast Since 2025 ~           ║
╚════════════════════════════════════════════════════════════════════╝


Ready to shred!

           /)
      ___(//__
     /         \
    |  O     O  |
     \    ^    /
      \_______/
        |   |
        |   |
       _|   |_
      (_______)


Press ENTER to enter the main menu...
```

## Main Menu

```
╔════════════════════════════════════════════════════════════════════╗
║  🏄 SURFCASTAI LAUNCHER 🏄  [Totally Tubular Edition v1.0] 🤙    ║
║                                                                    ║
║       ___    ___    ___    ___                                   ║
║    __/   \__/   \__/   \__/   \__     Hang Ten with AI!          ║
║ ___/                            \___                          ║
║                                                                    ║
║           ~ Catching the Perfect Forecast Since 2025 ~           ║
╚════════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────┐
│ Status: Model: gpt-5-mini     │ Specialist Team: ON │ Latest Bundle: 24e7eaad│
└────────────────────────────────────────────────────────────────────┘

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MAIN MENU:

  1. 🌊 Run Full Forecast (collect + process + forecast)
  2. 📊 Collect Data Only
  3. 🤖 Generate Forecast (latest bundle)
  4. 🔍 Generate Forecast (select bundle)
  5. ⚙️  Model Settings
  6. 👥 Toggle Specialist Team (currently: ON)
  7. 📁 View Recent Forecasts
  8. 📋 List Data Bundles
  9. ❓ Help/Info
  0. 🚪 Exit (Catch you later!)

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enter your choice:
```

## Model Settings Menu

```
╔════════════════════════════════════════════════════════════════════╗
║                      MODEL SETTINGS MENU                           ║
╚════════════════════════════════════════════════════════════════════╝

Current Model: gpt-5-mini

CHOOSE YOUR AI SHREDDING POWER:

  1. [ ] GPT-5-nano
      └─ Speed:    ★★★★★ (Lightning fast!)
      └─ Cost:     ★★★★★ (Super cheap!)
      └─ Quality:  ★★★☆☆ (Good for quick forecasts)

  2. [✓] GPT-5-mini
      └─ Speed:    ★★★★☆ (Pretty fast!)
      └─ Cost:     ★★★★☆ (Reasonable)
      └─ Quality:  ★★★★☆ (Balanced - recommended!)

  3. [ ] GPT-5
      └─ Speed:    ★★★☆☆ (Slower, but worth it!)
      └─ Cost:     ★★☆☆☆ (More expensive)
      └─ Quality:  ★★★★★ (Maximum accuracy!)

  4. View Full Config
  b. Back to Main Menu

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enter your choice:
```

## Help Screen (Excerpt)

```
╔════════════════════════════════════════════════════════════════════╗
║                    🏄 SURFCASTAI HELP CENTER 🏄                    ║
╚════════════════════════════════════════════════════════════════════╝

WHAT EACH OPTION DOES:

1. Run Full Forecast
   └─ Collects fresh data, processes it, and generates a complete forecast
   └─ This is your all-in-one, totally radical option!

2. Collect Data Only
   └─ Just grab the latest buoy, weather, and satellite data
   └─ Use this if you want to collect data for later

3. Generate Forecast (latest)
   └─ Use the most recent data bundle to create a forecast
   └─ Perfect when you already collected data

4. Generate Forecast (select)
   └─ Pick a specific data bundle to forecast from
   └─ Great for comparing forecasts from different times

MODEL COMPARISON:

  GPT-5-nano:  Fast & cheap - good for testing
  GPT-5-mini:  Balanced - best value (recommended)
  GPT-5:       Slowest but most accurate

SPECIALIST TEAM:

  When enabled, uses multiple AI agents to analyze different aspects:
  • Swell Expert - analyzes wave patterns
  • Wind Specialist - checks wind conditions
  • Weather Analyst - reviews weather patterns
  • Tides Guru - evaluates tidal effects
  → Results in more detailed (but slower) forecasts!

SURF TIPS FROM THE 80s:

  • Always check North Shore in winter (November-March)
  • South Shore pumps in summer (May-September)
  • Dawn patrol = best conditions (offshore winds, glassy water)
  • When in doubt, paddle out!
  • Never turn your back on the ocean, dude!

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Press ENTER to return to main menu...
```

## Running a Forecast

```
╔════════════════════════════════════════════════════════════════════╗
║                      FULL FORECAST RUN                             ║
╚════════════════════════════════════════════════════════════════════╝

This will:
  • Collect fresh data from all sources
  • Process and analyze the data
  • Generate a complete surf forecast
  • Create output files (MD, HTML, PDF)

Ready to shred? (y/n):
```

**After confirming:**

```
Shredding data...
Running: python src/main.py run --mode full

[Data collection output...]
[Processing output...]
[Forecast generation output...]

Totally radical! Full forecast completed!

Press ENTER to continue...
```

## Recent Forecasts View

```
╔════════════════════════════════════════════════════════════════════╗
║                      RECENT FORECASTS                              ║
╚════════════════════════════════════════════════════════════════════╝

Here are your most recent forecasts:

  1. forecast_20251004_232031
     └─ 2025-10-04 23:20 | Formats: MD, HTML, PDF

  2. forecast_20251004_113339
     └─ 2025-10-04 11:33 | Formats: MD, HTML

  3. forecast_20251004_113049
     └─ 2025-10-04 11:30 | Formats: MD, HTML

  4. forecast_20251003_183023
     └─ 2025-10-03 18:30 | Formats: MD, HTML, PDF

Forecast outputs are in: /Users/zackjordan/code/surfCastAI/output

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Press ENTER to continue...
```

## Data Bundles View

```
╔════════════════════════════════════════════════════════════════════╗
║                      DATA BUNDLES                                  ║
╚════════════════════════════════════════════════════════════════════╝

Available bundles (newest first):

  1. ✓ 24e7eaad-97eb-4d45-93b8-f02d3127064e...
     └─ 2025-10-04 23:15

  2. ✓ d8165cae-5dc6-4f57-93bf-061beae27304...
     └─ 2025-10-04 11:28

  3. ✓ cefed08c-64e9-4df1-87d7-13659124b82b...
     └─ 2025-10-03 18:25

  4. ✓ c27fbaeb-08a7-4ab8-90c6-5787c58557e9...
     └─ 2025-10-03 16:59

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Press ENTER to continue...
```

## Exit Screen

```


╔════════════════════════════════════════════════════════════════════╗
║                    CATCH YOU ON THE NEXT WAVE!                     ║
║                                                                    ║
║                  Thanks for using SurfCastAI! 🏄                  ║
║                                                                    ║
║           Stay stoked, keep shredding, and hang loose! 🤙        ║
╚════════════════════════════════════════════════════════════════════╝

  ~ Cowabunga, dude! ~

```

## Color Scheme (with colorama)

When colorama is installed, the launcher uses these colors:

- **Cyan**: Menus, borders, info text
- **Yellow**: Highlights, current selections, warnings
- **Green**: Success messages, active status
- **Red**: Error messages, inactive status
- **Magenta**: Emphasis, bundle IDs
- **Blue**: ASCII art waves

## Success Messages (Random Selection)

```
Totally radical! Full forecast completed!
Gnarly! Data collection complete!
Tubular! Model settings saved!
Cowabunga! Forecast generation complete!
Most excellent! Configuration updated!
Bodacious! Bundle processed!
Righteous! All systems go!
Awesome sauce! Ready to shred!
Rad to the max! Everything's working!
Stellar! Operation successful!
```

## Error Messages (Random Selection)

```
Bummer, dude! No bundles found!
Bogus! Invalid selection!
Weak sauce! Configuration error!
Major wipeout! Command failed!
Grody to the max! API key missing!
That's so lame! File not found!
Totally uncool! Network error!
Barf me out! Invalid input!
Gag me with a spoon! System error!
```

## Status Messages (Random Selection)

```
Hang loose...
Shredding data...
Carving the numbers...
Catching some waves...
Paddling out...
Getting stoked...
```

---

**Note**: All screenshots are text-based representations. The actual launcher features color-coded output when colorama is installed, making it even more rad!
