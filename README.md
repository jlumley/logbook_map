# Great Circle Route Map

Generate a flight route map from a pilot logbook CSV. Routes are drawn as great circle arcs with intensity scaled by frequency — fly a route more often and it glows hotter.

## Getting Started (From Scratch)

Never used a terminal before? No problem. Follow these steps exactly.

### 1. Open Terminal

Press `Cmd + Space`, type `Terminal`, press Enter.

You should see a blinking cursor waiting for you to type. This is where all the commands below go. Type (or paste) each command and press **Enter** to run it.

### 2. Download This Project

Go to the green **Code** button on the GitHub page and click **Download ZIP**. Unzip it somewhere you can find it (like your Desktop).

Then in Terminal, navigate to the folder. If you unzipped to your Desktop:

```bash
cd ~/Desktop/great-circle-map
```

> `cd` means "change directory" — it's how you move around in the terminal. The `~` means your home folder.

### 3. Install uv (One-Time)

```bash
make setup
```

This installs [uv](https://docs.astral.sh/uv/), a tool that manages Python and all the libraries the script needs. You only need to do this once.

> If you see `command not found: make`, run `xcode-select --install` and follow the prompts. This installs Apple's command line developer tools. Once it finishes, try `make setup` again.

### 4. Edit Your Logbook

Open `logbook.csv` in any spreadsheet app (Excel, Google Sheets, Numbers) or a text editor. Replace the sample data with your own flights. The only columns that matter are `departure` and `arrival` — fill those with ICAO airport codes (4-letter codes like CYTR, EGLL, KJFK).

Keep the header row exactly as-is:
```
date,aircraft_type,aircraft_reg,departure,arrival,flight_time_hrs,pilot_in_command,remarks
```

The other columns are optional — fill them in for your own records or leave them blank.

> Don't know an airport's ICAO code? Search "[airport name] ICAO code" — it's usually the first result.

### 5. Generate Your Map

```bash
make map
```

This creates `map.png` and opens it. Done.

Every time you add new flights to `logbook.csv`, just run `make map` again.

### If Something Goes Wrong

| Problem | Fix |
|---|---|
| `command not found: make` | Install dev tools (see step 3) |
| `command not found: uv` | Run `make setup` again, then restart Terminal |
| `Warning: no coordinates for {'XXXX'}` | The script doesn't know that airport's location. Open `great_circle_map.py`, find the `AIRPORT_COORDS` dictionary near the top, and add a line like `"XXXX": (latitude, longitude),` — you can find coordinates on Wikipedia or Google Maps |
| Map looks empty | Check that your `logbook.csv` has the correct column names (`departure`, `arrival`) and valid ICAO codes |

---

## Quick Start

```bash
make setup   # install uv (one-time)
make map     # generate map.png and open it
```

## Setup

The only prerequisite is [uv](https://docs.astral.sh/uv/). The `make setup` target installs it:

```bash
make setup
```

This runs the official uv install script. All Python dependencies (cartopy, matplotlib, numpy) are handled automatically by uv via PEP 723 inline script metadata — no virtualenv, no pip install, no requirements.txt.

## Make Targets

| Target | Description |
|---|---|
| `make` | Print usage help |
| `make setup` | Install uv |
| `make map` | Generate `map.png` from `logbook.csv` and open it |

## Usage

Via make:

```bash
make map
```

Or directly:

```bash
uv run great_circle_map.py logbook.csv                        # auto-detect home base
uv run great_circle_map.py logbook.csv CYTR                   # explicit home base
uv run great_circle_map.py logbook.csv -o map.png             # custom output path
uv run great_circle_map.py logbook.csv --label-min 5          # label airports with 5+ legs
uv run great_circle_map.py --help                             # full usage info
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `logbook` | Yes | Path to CSV file with `departure` and `arrival` columns |
| `home` | No | Home base ICAO code. Auto-detected as the most frequent departure if omitted |
| `-o`, `--output` | No | Output PNG path. Default: `great_circle_route.png` |
| `--label-min` | No | Minimum flight count to show an ICAO label on the map. Default: `10` |

## Files

| File | Purpose |
|---|---|
| `great_circle_map.py` | The script. Reads a CSV, draws a map, saves a PNG. |
| `logbook.csv` | The input data. A pilot logbook with flight legs. |
| `Makefile` | Build targets for setup and map generation. |

## logbook.csv Format

Standard pilot logbook CSV. The script only cares about two columns: `departure` and `arrival`. Everything else is ignored for mapping but kept for logbook completeness.

```
date,aircraft_type,aircraft_reg,departure,arrival,flight_time_hrs,pilot_in_command,remarks
2025-01-05,CC-177,177704,CYTR,EGLL,7.2,Smith,Strat airlift
```

**Required columns:** `departure`, `arrival` (ICAO codes, case-insensitive)

**Ignored columns:** `date`, `aircraft_type`, `aircraft_reg`, `flight_time_hrs`, `pilot_in_command`, `remarks` — include whatever you want, the script won't touch them.

---

## How It Works

### 1. Parse the CSV (`load_logbook`)

Reads every row. Extracts the `departure` and `arrival` ICAO codes. Returns a list of tuples like `[("CYTR", "EGLL"), ("EGLL", "CYTR"), ...]`.

### 2. Find Home Base (`find_home`)

Counts which airport appears most often as a departure. That's your home base. In our case, CYTR (CFB Trenton) dominates.

### 3. Count Route Frequencies (`count_routes`)

Iterates every leg. If the departure is home, the arrival is the destination. If the arrival is home, the departure is the destination. Counts how many times each destination appears. This means `CYTR -> EGLL` and `EGLL -> CYTR` both count toward the EGLL route.

Result is a `Counter` like: `{"EGLL": 16, "LICZ": 14, "KSEA": 10, ...}`

### 4. Airport Coordinate Lookup (`AIRPORT_COORDS`)

A hardcoded dictionary mapping ICAO codes to `(lat, lon)`. If a code from the CSV isn't in this dict, the script prints a warning and skips that route. To add a new airport, add a line to the dict:

```python
"WXYZ": (12.3456, -78.9012),  # Airport Name
```

### 5. Great Circle Math (`great_circle_points`)

A great circle is the shortest path between two points on a sphere — which is why flights from North America to Europe arc up toward the pole instead of going straight east on a flat map.

The math:
- Convert lat/lon to radians
- Compute the angular distance `d` between the two points using the spherical law of cosines
- Generate 100 evenly-spaced fractional positions along the arc (0.0 to 1.0)
- For each fraction, use SLERP (spherical linear interpolation) to find the intermediate 3D cartesian point
- Convert back to lat/lon

The `np.clip` on the arccos input prevents floating point errors from producing NaN when points are nearly identical or antipodal.

### 6. Drawing the Map

Uses **cartopy** for the map projection and **matplotlib** for rendering. Map data is 50m resolution Natural Earth.

**Projection:** `PlateCarree` — equirectangular/rectangular. Longitude maps linearly to X, latitude maps linearly to Y.

**Base map layers** (bottom to top):
1. Ocean fill (`#0d1321` — near-black navy)
2. Land fill (`#1a1f2e` — dark slate)
3. Coastlines (`#2a3a5c` — muted blue, thin)
4. Country borders (`#1e2a45` — very subtle)
5. Grid lines (faint, no labels)

### 7. Route Rendering

Routes are sorted by frequency and drawn lowest-first so the hottest routes render on top.

Each route's intensity `t` is `frequency / max_frequency`, normalized to 0.0–1.0.

**Color ramp** (computed per-route):
```python
r = int(80 + 175 * t)    # 80 -> 255
g = int(30 + 15 * t * t) # 30 -> 45  (stays low = no green)
b = int(120 + 135 * (1 - t * 0.3))  # 120 -> 160ish
```
At `t=0`: dim purple `#501e78`. At `t=1`: hot pink `#ff2dba`. The quadratic on green keeps it from looking washed out.

**Glow effect:** Each route is drawn 4 times:
- 3 "glow" passes: wide, semi-transparent lines at decreasing widths (8, 5, 3 pixels), each scaled by `glow_scale = 0.3 + 0.7 * t`. Low-frequency routes get thin, barely-visible glows. High-frequency routes get fat, bright glows.
- 1 "core" pass: the actual line, width `0.8 + 1.5 * t`, alpha `0.5 + 0.5 * t`.

The `transform=ccrs.Geodetic()` tells cartopy to interpret the coordinates as geographic and handle the projection. This is what makes the lines curve correctly on the flat map.

### 8. Airport Markers

**Destinations:** Two concentric dots (cyan glow + white core) sized proportionally to route frequency. ICAO label shown only if the route has `--label-min` or more flights (default: 10).

**Home base:** Three concentric dots (large dim gold glow, medium gold, small white core) + bold gold label. Drawn at highest z-order so it's always on top.

### 9. Output

`plt.savefig` at 400 DPI with the dark background color, tight bounding box.

---

## Defaults

Configurable at the top of `great_circle_map.py`:

```python
DEFAULT_OUTPUT = "great_circle_route.png"
DEFAULT_DPI = 400
DEFAULT_FIGSIZE = (16, 8)
DEFAULT_LABEL_MIN_FLIGHTS = 10
```

## Adding New Airports

1. Find the ICAO code and coordinates for your airport
2. Add it to `AIRPORT_COORDS` in the script
3. Add flights to/from it in your `logbook.csv`
4. `make map`

## Changing the Look

- **Colors:** Edit the hex values in the "Dark theme" section of `main()`
- **Route color ramp:** Edit the RGB formula in the route rendering loop
- **Projection:** Change `ccrs.PlateCarree()` to any cartopy projection (e.g. `ccrs.Robinson()`, `ccrs.Orthographic()`)
- **Resolution:** Change `DEFAULT_DPI` at the top of the script
- **Figure size:** Change `DEFAULT_FIGSIZE` at the top of the script
