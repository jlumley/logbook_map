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
DEFAULT_DPI = 1000
DEFAULT_FIGSIZE = (16, 8)
DEFAULT_LABEL_MIN_FLIGHTS = 10  # only label airports with >= this many legs
DEFAULT_AIRPORTS_CSV = Path(__file__).parent / "airports.csv"


def load_airport_coords(airports_csv):
    """Load airport coordinates from OurAirports CSV.

    Returns dict: ICAO -> (lat, lon)
    """
    coords = {}
    with open(airports_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = (row.get("icao_code") or row.get("gps_code") or "").strip()
            if not icao or len(icao) != 4:
                continue
            try:
                lat = float(row["latitude_deg"])
                lon = float(row["longitude_deg"])
            except (ValueError, KeyError):
                continue
            coords[icao] = (lat, lon)
    return coords


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
    parser.add_argument(
        "--airports",
        type=Path,
        default=DEFAULT_AIRPORTS_CSV,
        help=f"Path to OurAirports CSV (default: {DEFAULT_AIRPORTS_CSV.name})",
    )
    args = parser.parse_args()

    # Load airport database
    if not args.airports.exists():
        print(f"Error: {args.airports} not found")
        sys.exit(1)
    airport_coords = load_airport_coords(args.airports)
    print(f"Loaded {len(airport_coords)} airports from {args.airports.name}")

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
    missing = all_airports - set(airport_coords.keys())
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

    home_lat, home_lon = airport_coords[home]

    # Draw routes sorted by frequency (dim first, hot on top)
    for dest_code, freq in sorted(route_counts.items(), key=lambda r: r[1]):
        if dest_code not in airport_coords:
            continue
        t = freq / max_freq

        # Color: dim blue-purple → hot pink
        r = int(80 + 175 * t)
        g = int(30 + 15 * t * t)
        b = int(120 + 135 * (1 - t * 0.3))
        route_color = f"#{r:02x}{g:02x}{b:02x}"

        dest_lat, dest_lon = airport_coords[dest_code]
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
        if dest_code not in airport_coords:
            continue
        t = freq / max_freq
        lat, lon = airport_coords[dest_code]
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
