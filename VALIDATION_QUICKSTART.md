# Daily Validation Quick Start Guide
**Time Required:** 5-10 minutes per day

---

## Daily Workflow (Simple 4-Step Process)

### Step 1: Run Forecast (1 minute)
```bash
cd /Users/zackjordan/code/surfCastAI
python src/main.py run --mode forecast
```

**Record:**
- Forecast ID (shown at end)
- Cost (shown in logs)
- Tokens (shown in logs)

---

### Step 2: Extract Predictions (2 minutes)

Open the latest forecast:
```bash
# Find latest
ls -lt output/ | head -2

# Open it
open output/forecast_YYYYMMDD_HHMMSS/forecast_*.md
```

**Look for these sections and copy to validation log:**

**North Shore section:**
- Size range (e.g., "6-10 ft Hawaiian")
- Period (e.g., "11-13s")
- Direction (e.g., "NNW 320-335°")

**South Shore section:**
- Size range
- Period
- Direction

**Confidence score** (at bottom)

---

### Step 3: Check Buoy Data (3 minutes)

**Option A - Web Browser (Easier):**

Visit these URLs and record latest observations:
- [Buoy 51201](https://www.ndbc.noaa.gov/station_page.php?station=51201) - NW Hawaii
- [Buoy 51202](https://www.ndbc.noaa.gov/station_page.php?station=51202) - Molokai
- [Buoy 51001](https://www.ndbc.noaa.gov/station_page.php?station=51001) - NW Hawaii 350nm

**Look for:** "Latest observations" table
- **WVHT** = Wave Height (ft)
- **DPD** = Dominant Period (s)
- **MWD** = Wave Direction (degrees)

**Option B - Command Line (Faster):**
```bash
# Quick buoy check
curl -s "https://www.ndbc.noaa.gov/data/realtime2/51201.txt" | head -3
curl -s "https://www.ndbc.noaa.gov/data/realtime2/51202.txt" | head -3
curl -s "https://www.ndbc.noaa.gov/data/realtime2/51001.txt" | head -3
```

Look at the first data line (row 3), columns:
- Column 9 = Wave Height (m) - multiply by 3.28 for feet
- Column 10 = Dominant Period (s)
- Column 12 = Wave Direction (degrees)

---

### Step 4: Score Accuracy (2 minutes)

**Quick scoring method:**

**Size Accuracy:**
- Buoy reading within predicted range? → 10/10
- Within 1 ft? → 8/10
- Within 2 ft? → 6/10
- Within 3-4 ft? → 4/10
- More than 4 ft off? → 2/10

**Period Accuracy:**
- Within predicted range? → 10/10
- Within 1s? → 8/10
- Within 2s? → 6/10
- More than 2s off? → 4/10

**Direction Accuracy:**
- Same cardinal direction (NW, NNW, etc.)? → 10/10
- One direction off (NW vs NNW)? → 7/10
- Two directions off? → 4/10

**Overall:** Average of size + period + direction scores

---

## Pre-filled Example (Day 1)

Here's today's forecast already started for you:

```markdown
## Day 1: October 5, 2025 (Saturday)

### Forecast Generated
- **Forecast ID:** `forecast_20251005_004039`
- **Generated At:** 00:40 HST
- **Cost:** $0.025
- **Tokens:** 12,381
- **Collection Status:** 12 buoys ✅, 2 weather ✅, 2 models ✅

### SurfCastAI Predictions (North Shore)
<!-- Open output/forecast_20251005_004039/forecast_20251005_004039.md -->
<!-- Copy from "North Shore" section -->
- **Size Range:** 6-10 ft Hawaiian (12-20 ft faces)
- **Period Range:** 11-13s
- **Direction:** 330 degrees (NNW)
- **Timing:** Building Oct 5, peaking Oct 6, dropping Oct 7
- **Confidence:** 0.6/1.0

### SurfCastAI Predictions (South Shore)
- **Size Range:** 2-4 ft Hawaiian (4-8 ft faces)
- **Period Range:** 10-15s (if long period) or 6-9s (if short)
- **Direction:** 200 degrees (SSW)
- **Timing:** Building Oct 5-6
- **Confidence:** 0.6/1.0
```

**Now you just need to add:**
1. Buoy observations (from Step 3)
2. Accuracy scores (from Step 4)
3. Quick notes on what worked/didn't

---

## Helpful Resources

### Buoy Websites
- **Live data:** https://www.ndbc.noaa.gov/
- **Buoy 51201:** https://www.ndbc.noaa.gov/station_page.php?station=51201
- **Buoy 51202:** https://www.ndbc.noaa.gov/station_page.php?station=51202

### Pat Caldwell Forecasts
- **Surf News Network:** https://www.surfnewsnetwork.com/category/surf-news/pat-caldwell/
- Usually posts Tuesday, Thursday, Saturday

### Direction Reference
```
N    = 0° / 360°
NNE  = 22.5°
NE   = 45°
ENE  = 67.5°
E    = 90°
ESE  = 112.5°
SE   = 135°
SSE  = 157.5°
S    = 180°
SSW  = 202.5°
SW   = 225°
WSW  = 247.5°
W    = 270°
WNW  = 292.5°
NW   = 315°
NNW  = 337.5°
```

---

## Tips for Success

**Daily validation:**
- Best time: Afternoon or next morning (12-24 hours after forecast)
- Takes 5-10 minutes once you get the rhythm
- Can skip a day if needed, but try for 5+ days minimum

**Scoring:**
- Don't overthink it - quick gut check is fine
- Focus on "was it useful?" not "was it perfect?"
- Note anything surprising or interesting

**Comparison to Caldwell:**
- Only on days he posts (not every day)
- Look for general approach similarity, not exact numbers
- Note if SurfCastAI missed something Caldwell caught

**For Phase 1:**
- This manual validation will inform automated validation design
- Your notes on "what was off" guide priority fixes
- Patterns you notice help tune the system

---

## Automation (Optional)

If you want to automate the daily forecast:

**macOS cron:**
```bash
# Edit crontab
crontab -e

# Add this line (runs at 6 AM daily)
0 6 * * * cd /Users/zackjordan/code/surfCastAI && /usr/bin/python3 src/main.py run --mode forecast >> logs/daily_forecast.log 2>&1
```

**Or use launchd (more reliable on macOS):**
```bash
# Create plist file at ~/Library/LaunchAgents/com.surfcastai.daily.plist
# See macOS automation docs for details
```

Then you just fill out the validation log each afternoon/evening.

---

## Questions?

If any step is unclear or you want to simplify further, just ask! The goal is to make this easy enough that you'll actually do it for a week. 😊

**Remember:** Even 4-5 days of validation is better than none. Don't stress about perfection.
