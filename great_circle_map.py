#!/usr/bin/env python3
"""Plot great circle route map from a pilot logbook CSV.

Usage: uv run great_circle_map.py logbook.csv [HOME_ICAO]

CSV expected columns: departure, arrival (ICAO codes).
Other columns (date, aircraft_type, flight_time_hrs, etc.) are ignored for mapping.
If HOME_ICAO is not provided, the most frequent departure airport is used.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT = "great_circle_route.png"
DEFAULT_DPI = 400
DEFAULT_FIGSIZE = (16, 8)
DEFAULT_LABEL_MIN_FLIGHTS = 10  # only label airports with >= this many legs

# Known airport coordinates: ICAO -> (lat, lon)
# Add entries here for any airports not yet listed.
AIRPORT_COORDS = {
    "CYTR": (44.1189, -77.5281),
    "KSEA": (47.4502, -122.3088),
    "EGLL": (51.4775, -0.4614),
    "GOBD": (14.6707, -17.0733),
    "LICZ": (37.4017, 14.9222),
    "CYLT": (82.5178, -62.2806),
    "CYYC": (51.1225, -114.0133),
    "CYUL": (45.4706, -73.7408),
    "CYHZ": (44.8808, -63.5086),
    "CYQX": (48.9369, -54.5681),
    "BIKF": (63.9850, -22.6056),
    "EDDF": (50.0333, 8.5706),
    "LTBA": (40.9769, 28.8146),
    "ORBI": (33.2625, 44.2346),
    "OAKB": (34.5659, 69.2124),
    "CYMJ": (50.3303, -105.5592),
    "CYEG": (53.3097, -113.5797),
    "CYOW": (45.3225, -75.6692),
    "RJTT": (35.5533, 139.7811),  # Tokyo Haneda
    "LFPG": (49.0097, 2.5479),  # Paris CDG
    "CYFB": (63.7561, -68.5558),  # Iqaluit
    "OMDB": (25.2528, 55.3644),  # Dubai
    "CYYR": (53.3192, -60.4258),  # Goose Bay
    "PHNL": (21.3187, -157.9224),  # Honolulu
    "CYWG": (49.9100, -97.2399),  # Winnipeg
    "RPLL": (14.5086, 121.0198),  # Manila
    "PGUA": (13.5840, 144.9298),  # Andersen AFB, Guam
}


def load_logbook(csv_path):
    """Parse logbook CSV and return list of (departure, arrival) pairs."""
    legs = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dep = row["departure"].strip().upper()
            arr = row["arrival"].strip().upper()
            if dep and arr:
                legs.append((dep, arr))
    return legs


def find_home(legs):
    """Return the most frequent departure airport."""
    departures = Counter(dep for dep, _ in legs)
    return departures.most_common(1)[0][0]


def count_routes(legs, home):
    """Count how many times each route (home <-> destination) was flown."""
    route_counts = Counter()
    for dep, arr in legs:
        if dep == home:
            route_counts[arr] += 1
        elif arr == home:
            route_counts[dep] += 1
    return route_counts


def great_circle_points(lat1, lon1, lat2, lon2, n=100):
    """Generate points along a great circle route."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    d = np.arccos(
        np.clip(
            np.sin(lat1) * np.sin(lat2)
            + np.cos(lat1) * np.cos(lat2) * np.cos(lon2 - lon1),
            -1,
            1,
        )
    )
    if d < 1e-10:
        return np.full(n, np.degrees(lat1)), np.full(n, np.degrees(lon1))
    fracs = np.linspace(0, 1, n)
    a = np.sin((1 - fracs) * d) / np.sin(d)
    b = np.sin(fracs * d) / np.sin(d)
    x = a * np.cos(lat1) * np.cos(lon1) + b * np.cos(lat2) * np.cos(lon2)
    y = a * np.cos(lat1) * np.sin(lon1) + b * np.cos(lat2) * np.sin(lon2)
    z = a * np.sin(lat1) + b * np.sin(lat2)
    lats = np.degrees(np.arctan2(z, np.sqrt(x**2 + y**2)))
    lons = np.degrees(np.arctan2(y, x))
    return lats, lons


def main():
    parser = argparse.ArgumentParser(
        description="Generate a great circle route map from a pilot logbook CSV.",
    )
    parser.add_argument(
        "logbook",
        type=Path,
        help="Path to CSV file with 'departure' and 'arrival' columns",
    )
    parser.add_argument(
        "home",
        nargs="?",
        default=None,
        help="Home base ICAO code (auto-detected if omitted)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output PNG file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--label-min",
        type=int,
        default=DEFAULT_LABEL_MIN_FLIGHTS,
        help=f"Min flights to show ICAO label (default: {DEFAULT_LABEL_MIN_FLIGHTS})",
    )
    args = parser.parse_args()

    csv_path = args.logbook
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    legs = load_logbook(csv_path)
    print(f"Loaded {len(legs)} flight legs from {csv_path.name}")

    home = args.home.strip().upper() if args.home else find_home(legs)
    print(f"Home base: {home}")

    route_counts = count_routes(legs, home)
    if not route_counts:
        print(f"No routes found from/to {home}")
        sys.exit(1)

    # Check for missing airport coords
    all_airports = {home} | set(route_counts.keys())
    missing = all_airports - set(AIRPORT_COORDS.keys())
    if missing:
        print(f"Warning: no coordinates for {missing} — skipping these routes")
        for code in missing:
            route_counts.pop(code, None)

    print(
        f"Found {len(route_counts)} unique destinations, "
        f"{sum(route_counts.values())} total legs"
    )

    max_freq = max(route_counts.values())

    # --- Dark theme ---
    BG = "#0a0e17"
    LAND = "#1a1f2e"
    OCEAN = "#0d1321"
    COAST = "#2a3a5c"
    BORDER = "#1e2a45"
    MARKER_COLOR = "#00f0ff"
    TEXT_COLOR = "#e0e6f0"
    HOME_COLOR = "#ffaa00"

    plt.rcParams.update(
        {
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "text.color": TEXT_COLOR,
            "font.family": "monospace",
        }
    )

    fig = plt.figure(figsize=DEFAULT_FIGSIZE)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

    ax.set_global()
    ax.add_feature(
        cfeature.NaturalEarthFeature(
            "physical", "land", "50m", facecolor=LAND, edgecolor="none"
        )
    )
    ax.add_feature(
        cfeature.NaturalEarthFeature(
            "physical", "ocean", "50m", facecolor=OCEAN, edgecolor="none"
        )
    )
    ax.add_feature(
        cfeature.NaturalEarthFeature(
            "physical",
            "coastline",
            "50m",
            facecolor="none",
            edgecolor=COAST,
            linewidth=0.4,
        )
    )
    ax.add_feature(
        cfeature.NaturalEarthFeature(
            "cultural",
            "admin_0_boundary_lines_land",
            "50m",
            facecolor="none",
            edgecolor=BORDER,
            linewidth=0.2,
        )
    )
    for spine in ax.spines.values():
        spine.set_edgecolor(COAST)
        spine.set_linewidth(0.8)
    ax.gridlines(draw_labels=False, linewidth=0.3, color="#1e2a45", alpha=0.6)

    home_lat, home_lon = AIRPORT_COORDS[home]

    # Draw routes sorted by frequency (dim first, hot on top)
    for dest_code, freq in sorted(route_counts.items(), key=lambda r: r[1]):
        if dest_code not in AIRPORT_COORDS:
            continue
        t = freq / max_freq

        # Color: dim blue-purple → hot pink
        r = int(80 + 175 * t)
        g = int(30 + 15 * t * t)
        b = int(120 + 135 * (1 - t * 0.3))
        route_color = f"#{r:02x}{g:02x}{b:02x}"

        dest_lat, dest_lon = AIRPORT_COORDS[dest_code]
        gc_lats, gc_lons = great_circle_points(
            home_lat,
            home_lon,
            dest_lat,
            dest_lon,
        )

        # Glow layers scale with frequency
        glow_scale = 0.3 + 0.7 * t
        for width, alpha in [(8, 0.06), (5, 0.12), (3, 0.2)]:
            ax.plot(
                gc_lons,
                gc_lats,
                color=route_color,
                linewidth=width * glow_scale,
                alpha=alpha * glow_scale,
                transform=ccrs.Geodetic(),
                solid_capstyle="round",
            )
        ax.plot(
            gc_lons,
            gc_lats,
            color=route_color,
            linewidth=0.8 + 1.5 * t,
            alpha=0.5 + 0.5 * t,
            transform=ccrs.Geodetic(),
            solid_capstyle="round",
        )

    # Destination markers
    for dest_code, freq in route_counts.items():
        if dest_code not in AIRPORT_COORDS:
            continue
        t = freq / max_freq
        lat, lon = AIRPORT_COORDS[dest_code]
        marker_sz = 4 + 6 * t
        ax.plot(
            lon,
            lat,
            "o",
            color=MARKER_COLOR,
            markersize=marker_sz,
            alpha=0.3 + 0.4 * t,
            transform=ccrs.PlateCarree(),
            zorder=5,
        )
        ax.plot(
            lon,
            lat,
            "o",
            color="#ffffff",
            markersize=2 + 2 * t,
            transform=ccrs.PlateCarree(),
            zorder=6,
        )
        if freq >= args.label_min:
            ax.text(
                lon + 1.5,
                lat - 3.5,
                dest_code,
                transform=ccrs.PlateCarree(),
                fontsize=6 + 2 * t,
                fontweight="bold",
                color=MARKER_COLOR,
                alpha=0.5 + 0.5 * t,
                zorder=8,
            )

    # Home base marker
    ax.plot(
        hlon := home_lon,
        hlat := home_lat,
        "o",
        color=HOME_COLOR,
        markersize=22,
        alpha=0.15,
        transform=ccrs.PlateCarree(),
        zorder=9,
    )
    ax.plot(
        hlon,
        hlat,
        "o",
        color=HOME_COLOR,
        markersize=12,
        alpha=0.4,
        transform=ccrs.PlateCarree(),
        zorder=10,
    )
    ax.plot(
        hlon,
        hlat,
        "o",
        color="#ffffff",
        markersize=5,
        transform=ccrs.PlateCarree(),
        zorder=11,
    )
    ax.text(
        hlon + 2,
        hlat - 4.5,
        home,
        transform=ccrs.PlateCarree(),
        fontsize=11,
        fontweight="bold",
        color=HOME_COLOR,
        zorder=12,
    )

    ax.set_title(
        f"{home}  ///  ROUTE MAP",
        fontsize=16,
        fontweight="bold",
        color=TEXT_COLOR,
        pad=15,
        fontfamily="monospace",
    )

    plt.savefig(args.output, dpi=DEFAULT_DPI, bbox_inches="tight", facecolor=BG)
    print(f"Map saved to {args.output}")


if __name__ == "__main__":
    main()
