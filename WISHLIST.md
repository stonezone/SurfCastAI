# SurfCastAI Enhancement Wishlist

*Last updated: November 27, 2025*

This document outlines the data and knowledge needed to take SurfCastAI from "good" to "Pat Caldwell-level authoritative."

---

## Priority 1: Break-Specific Swell Translation ("The North Shore Bible")

We predict open-ocean swells accurately, but we don't know how they transform at each break. A 15ft/14s/330° swell behaves completely differently at Pipeline versus Sunset versus Waimea.

### For Each Major Break, We Need:

#### Pipeline / Backdoor
- **Optimal swell direction range**: (e.g., 305°-335° or tighter?)
- **Minimum period for quality**: Below what period does it go mushy/closeout?
- **Optimal period sweet spot**: What period makes it truly world-class?
- **Size limits**: At what H1/3 does it max out? When does second reef take over?
- **Wind tolerance**:
  - Best offshore direction (pure S? SSE? SSW?)
  - Max wind speed before it's blown out
  - How much NE trade bump can it handle?
- **Tide preferences**: Does it prefer low, mid, or high? Why?
- **Swell-to-face multiplier**: If buoy reads 10ft H1/3, what do actual faces measure?
- **Direction sensitivity**: How many degrees off-angle before it stops working?

#### Sunset Beach
- Same questions as above
- **Bowl vs Point**: Which direction/size favors which section?

#### Waimea Bay
- Same questions
- **Official "break" threshold**: What's the minimum size for Waimea to actually work?
- **Eddie Aikau threshold**: What conditions trigger the big wave alert?

#### Haleiwa
- Same questions
- **Harbor protection factor**: How much does it shelter from pure N swells?

#### Rocky Point / Gas Chambers
- Same questions
- **Frequency vs size preference**: Does it need more waves or bigger waves?

#### Velzyland / V-Land
- Same questions
- **Sensitivity to direction**: Notoriously picky—what's the magic window?

### Supporting Info
- **Island shadowing map**: Which directions get blocked by Kauai, Niihau, Molokai?
- **Outer reef effects**: When do outer reefs start catching waves and reducing inside size?
- **Local "rule of thumb" formulas**: Any magic numbers forecasters use?

---

## Priority 2: South Shore Break Knowledge

### Ala Moana Bowls
- Optimal swell direction (S? SSW? SW?)
- Period preferences
- Tide/wind effects

### Waikiki (Canoes/Queens/Publics)
- Wrap coefficients from various S swell angles
- Why does long-period S travel better than short-period?

### Diamond Head (Cliffs/Lighthouse)
- Direction windows
- When does it actually have rideable surf?

### Sunset-to-South Wrap
- At what size/direction does North Shore energy wrap to South Shore?

---

## Priority 3: Pat Caldwell Forecast Archive

To train the model to *think* like Caldwell (not just sound like him), we need his actual decision-making examples.

### Request: 20-50 Historical Caldwell Forecasts
For each, capture:
1. **Forecast date**
2. **Swell predictions** (height, period, direction, timing)
3. **Confidence language** (how certain was he?)
4. **Storm backstory** (his narrative about the generating low)
5. **Buoy data from that day** (51001, 51101 readings)
6. **What actually happened** (if available—did it verify?)

### Key Questions to Answer:
- When does Caldwell call something "epic" vs "solid" vs "modest"?
- How does he phrase uncertainty?
- What makes him raise/lower confidence?
- How does he weight model disagreement?
- His swell arrival timing methodology

---

## Priority 4: Contest/Event Trigger Data

Professional surf contest directors make expert judgment calls on "is this surfable?"

### Data We'd Love:
- **Pipeline Masters** call logs (when did they run? what were conditions?)
- **Eddie Aikau** holding periods (what buoy readings triggered "go"?)
- **Sunset Beach Pro** conditions
- **Triple Crown** historical data

This is human expert validation of "good enough to compete."

---

## Priority 5: Verification/Feedback System

We have no way to know if our forecasts are accurate.

### Needed:
- **Post-event surf reports** (Surfline, local shops)
- **Webcam screenshots** at known times matched to buoy data
- **"What actually happened"** logs for comparison

### Ideal Workflow:
1. We forecast "12-15ft faces at Pipe, Wednesday AM"
2. Someone records actual conditions Wednesday AM
3. We score ourselves and adjust

---

## Priority 6: Additional Data Sources

### Models We Don't Have Yet:
- **ECMWF WAM** (European wave model—often better for Hawaii)
- **Australian BoM** Southern Ocean tracking (for S swells)
- **JMA** (Japanese Meteorological Agency) for NW Pacific storms

### Real-Time Validation:
- **Surfline webcam API** (if accessible)
- **CDIP nearshore spectra** (more than just bulk parameters)

---

## Wildcard Ideas

### Local Expert Interview
30-60 minutes with any of:
- North Shore lifeguard
- Surf school owner who's been forecasting for clients for years
- Contest director
- Old-school local who's been reading the ocean for decades

Questions:
- "When you look at the buoy and it says X, how do you translate that to Pipe?"
- "What kills a swell that looks good on paper?"
- "What's the most common forecasting mistake people make?"

### Historical "Epic Day" Case Studies
Pick 5-10 legendary sessions (e.g., Code Red, Eddie 2016, any historic Pipe day) and reconstruct:
- What did the buoys read?
- What was the storm?
- What made it special?

This teaches the model what "epic" actually looks like in the data.

---

## Format for Submitting Break Knowledge

If you're documenting a break, here's a template:

```
### [Break Name]

**Location**: (lat/lon or description)
**Optimal Swell Direction**: X° - Y° (cardinal: e.g., NNW-NW)
**Acceptable Direction Range**: X° - Y°
**Optimal Period**: X-Y seconds
**Minimum Period**: X seconds (below this = poor quality)
**Size Range**: X-Y ft H1/3 (at what size does it max out?)
**Wave Face Multiplier**: X (e.g., "buoy H1/3 × 1.3 = typical face height")

**Wind**:
- Best: [direction] at [speed] kt
- Tolerable: [direction] at [speed] kt
- Blown out: [conditions]

**Tide**:
- Best: [low/mid/high] because [reason]
- Worst: [low/mid/high] because [reason]

**Special Notes**:
- [Any quirks, like "needs SW wind to clean up the bump"]
- [Shadowing effects]
- [Crowd factors]
- [Hazards]

**Source**: [Who provided this info? Local knowledge? Published article?]
```

---

## What This Enables

With this knowledge, SurfCastAI can evolve from:

> "NNW swell 15 ft @ 14s arriving Wednesday"

To:

> "Pipeline: 15 ft @ 14s from 330° is in Pipe's wheelhouse—expect classic
> double-overhead barrels. Light NE trades (6 kt) are tolerable but not ideal;
> dawn patrol before 8am for cleanest conditions. Sunset: Same swell but
> direction is 10° too north for the Point to connect properly—expect the
> Bowl to be the focus with some wide sets sweeping through."

That's the difference between a buoy reader and a forecaster.

---

*Let's build the most accurate Hawaii surf forecast system ever made.*
