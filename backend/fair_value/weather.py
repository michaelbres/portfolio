"""
Weather carry factor for MLB games.

Uses the Open-Meteo API (free, no API key) to fetch temperature and wind
at game time, then computes a run-environment multiplier applied on top of
the static park factor.

Physics
───────
  Temperature:  Warmer air is less dense → ball carries farther.
                +0.25% per °F above 72°F baseline (≈ +4.5% at 90°F).

  Wind (direction-aware):  Tailwind toward CF adds carry; headwind removes it.
                ~0.50% per mph blowing toward center field.
                Requires stadium centre-field azimuth (from home plate).

  Combined carry_factor = 1 + temp_adjustment + wind_adjustment
  Clamped to [0.88, 1.12] to prevent outlier game data from blowing up λ.

Venues
──────
Azimuths are the compass bearing from home plate → center field.
Wind blowing FROM the OPPOSITE direction means blowing TOWARD CF (tailwind).
Open-Meteo winddirection_10m is the direction the wind is coming FROM.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ── Stadium lookup ─────────────────────────────────────────────────────────────
# lat / lon  : geographic centre of the playing field (for weather API)
# cf_az      : compass bearing from home plate to centre field (degrees)
#              0° = North, 90° = East, 180° = South, 270° = West

VENUE_DATA: dict[str, dict] = {
    "ARI": {"lat": 33.4455, "lon": -112.0667, "cf_az": 315},
    "ATL": {"lat": 33.8908, "lon": -84.4681,  "cf_az":  20},
    "BAL": {"lat": 39.2838, "lon": -76.6217,  "cf_az": 320},
    "BOS": {"lat": 42.3467, "lon": -71.0972,  "cf_az":  45},
    "CHC": {"lat": 41.9484, "lon": -87.6556,  "cf_az":  55},
    "CWS": {"lat": 41.8300, "lon": -87.6339,  "cf_az":  90},
    "CIN": {"lat": 39.0979, "lon": -84.5076,  "cf_az":  30},
    "CLE": {"lat": 41.4962, "lon": -81.6852,  "cf_az": 330},
    "COL": {"lat": 39.7560, "lon": -104.9942, "cf_az":  15},
    "DET": {"lat": 42.3390, "lon": -83.0485,  "cf_az": 340},
    "HOU": {"lat": 29.7573, "lon": -95.3555,  "cf_az":  85},
    "KC":  {"lat": 39.0517, "lon": -94.4803,  "cf_az": 190},
    "LAA": {"lat": 33.8003, "lon": -117.8827, "cf_az":  80},
    "LAD": {"lat": 34.0739, "lon": -118.2400, "cf_az":   0},
    "MIA": {"lat": 25.7781, "lon": -80.2197,  "cf_az": 120},
    "MIL": {"lat": 43.0280, "lon": -87.9712,  "cf_az":   5},
    "MIN": {"lat": 44.9817, "lon": -93.2778,  "cf_az": 225},
    "NYM": {"lat": 40.7571, "lon": -73.8458,  "cf_az":  35},
    "NYY": {"lat": 40.8296, "lon": -73.9262,  "cf_az":  40},
    "OAK": {"lat": 37.7516, "lon": -122.2005, "cf_az": 230},
    "PHI": {"lat": 39.9061, "lon": -75.1665,  "cf_az":  75},
    "PIT": {"lat": 40.4468, "lon": -80.0057,  "cf_az": 345},
    "SD":  {"lat": 32.7076, "lon": -117.1570, "cf_az": 210},
    "SEA": {"lat": 47.5914, "lon": -122.3325, "cf_az": 355},
    "SF":  {"lat": 37.7786, "lon": -122.3893, "cf_az":  50},
    "STL": {"lat": 38.6226, "lon": -90.1928,  "cf_az":  15},
    "TB":  {"lat": 27.7682, "lon": -82.6534,  "cf_az": 265},
    "TEX": {"lat": 32.7512, "lon": -97.0832,  "cf_az":  90},
    "TOR": {"lat": 43.6414, "lon": -79.3894,  "cf_az":  25},
    "WSH": {"lat": 38.8730, "lon": -77.0074,  "cf_az": 130},
}

# Fallback for teams whose codes vary (Athletics relocation etc.)
_ALIAS: dict[str, str] = {
    "ATH": "OAK",   # Athletics (Las Vegas)
    "CHA": "CWS",
    "CHN": "CHC",
    "LAN": "LAD",
    "SFN": "SF",
    "SLN": "STL",
    "KCA": "KC",
    "NYA": "NYY",
    "NYN": "NYM",
    "TBA": "TB",
    "SDN": "SD",
}


def _resolve_team(team: str) -> Optional[str]:
    t = team.upper()
    return _ALIAS.get(t, t) if t not in VENUE_DATA else t


# ── Open-Meteo fetch (free, no key) ───────────────────────────────────────────

_OMETO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&hourly=temperature_2m,relativehumidity_2m,windspeed_10m,winddirection_10m"
    "&temperature_unit=fahrenheit"
    "&windspeed_unit=mph"
    "&timezone=UTC"
    "&forecast_days=2"
)


def _fetch_open_meteo(lat: float, lon: float) -> Optional[dict]:
    """Return raw hourly JSON from Open-Meteo, or None on failure."""
    import urllib.request, urllib.error, json
    url = _OMETO_URL.format(lat=round(lat, 4), lon=round(lon, 4))
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        log.warning("Open-Meteo fetch failed: %s", exc)
        return None


def _hour_index(hourly_times: list[str], target_utc: datetime) -> Optional[int]:
    """Find the index in hourly_times closest to target_utc."""
    target_str = target_utc.strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(hourly_times):
        if t.startswith(target_str[:13]):
            return i
    # Fallback: find closest
    target_ts = target_utc.timestamp()
    best_i, best_diff = None, float("inf")
    for i, t in enumerate(hourly_times):
        try:
            ts = datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
            diff = abs(ts - target_ts)
            if diff < best_diff:
                best_i, best_diff = i, diff
        except Exception:
            pass
    return best_i


# ── Carry factor computation ───────────────────────────────────────────────────

def weather_carry_factor(
    home_team:    str,
    game_time_utc: Optional[str] = None,
) -> float:
    """
    Compute the weather-based run-environment carry factor for *home_team*'s
    ballpark at the given *game_time_utc* (ISO string or None).

    Returns a multiplier intended to be applied to the static park factor:
        effective_park_factor = park_factor * weather_carry_factor

    Returns 1.0 on any error (neutral; falls back to static park factor only).
    """
    team_key = _resolve_team(home_team)
    if team_key not in VENUE_DATA:
        return 1.0

    venue = VENUE_DATA[team_key]
    lat, lon, cf_az = venue["lat"], venue["lon"], venue["cf_az"]

    # Parse game time
    game_dt: Optional[datetime] = None
    if game_time_utc:
        try:
            raw = game_time_utc.replace("Z", "+00:00")
            game_dt = datetime.fromisoformat(raw).astimezone(timezone.utc)
        except Exception:
            pass
    if game_dt is None:
        game_dt = datetime.now(timezone.utc).replace(hour=18, minute=0,
                                                      second=0, microsecond=0)

    data = _fetch_open_meteo(lat, lon)
    if not data:
        return 1.0

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    idx    = _hour_index(times, game_dt)
    if idx is None:
        return 1.0

    def _val(key: str) -> Optional[float]:
        arr = hourly.get(key, [])
        v   = arr[idx] if idx < len(arr) else None
        return float(v) if v is not None else None

    temp_f      = _val("temperature_2m")        # already °F (unit=fahrenheit)
    wind_mph    = _val("windspeed_10m")          # already mph
    wind_from_deg = _val("winddirection_10m")    # direction wind is FROM

    # ── Temperature adjustment ─────────────────────────────────────────────
    temp_adj = 0.0
    if temp_f is not None:
        temp_adj = (temp_f - 72.0) * 0.0025   # +0.25% per °F above 72°F

    # ── Wind adjustment (direction-aware) ──────────────────────────────────
    wind_adj = 0.0
    if wind_mph is not None and wind_mph > 0 and wind_from_deg is not None:
        # Direction the wind is BLOWING TOWARD (meteorological from→to)
        wind_to_deg = (wind_from_deg + 180.0) % 360.0
        # Angle between wind destination and CF azimuth
        angle_diff = (wind_to_deg - cf_az + 360.0) % 360.0
        if angle_diff > 180.0:
            angle_diff -= 360.0
        # cos(0°)=+1 → pure tailwind; cos(180°)=-1 → pure headwind
        component = wind_mph * math.cos(math.radians(angle_diff))
        wind_adj = component * 0.005          # 0.5% per mph component toward CF

    carry = 1.0 + temp_adj + wind_adj
    return max(0.88, min(1.12, round(carry, 4)))
