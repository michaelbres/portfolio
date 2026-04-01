"""
Thin wrapper around the free MLB Stats API (statsapi.mlb.com).

Endpoints used — all public, no API key required:
  Schedule:  /api/v1/schedule
  Boxscore:  /api/v1/game/{gamePk}/boxscore
  Roster:    /api/v1/teams/{teamId}/roster
"""

import logging
from datetime import date
from typing import Optional

import requests

log = logging.getLogger(__name__)

BASE = "https://statsapi.mlb.com"
TIMEOUT = 10   # seconds


def _get(path: str, params: dict | None = None) -> dict:
    url = BASE + path
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Schedule ──────────────────────────────────────────────────────────────────

def get_schedule(game_date: date) -> list[dict]:
    """
    Returns a list of game dicts for regular-season games on *game_date*.

    Each dict has at minimum:
        game_pk, game_time_utc, home_team, away_team, venue,
        home_sp_id, home_sp_name, home_sp_hand,
        away_sp_id, away_sp_name, away_sp_hand
    """
    date_str = game_date.strftime("%Y-%m-%d")
    data = _get("/api/v1/schedule", {
        "sportId": 1,
        "date": date_str,
        "gameType": "R",
        "hydrate": "probablePitcher(note),team,linescore",
    })

    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            game_pk = g.get("gamePk")
            status = g.get("status", {}).get("abstractGameState", "")

            home = g.get("teams", {}).get("home", {})
            away = g.get("teams", {}).get("away", {})

            def sp_info(side: dict) -> tuple:
                sp = side.get("probablePitcher")
                if not sp:
                    return None, None, None
                pid = sp.get("id")
                name = sp.get("fullName")
                # Handedness not always in schedule hydrate; fetch separately if needed
                hand = sp.get("pitchHand", {}).get("code") if isinstance(sp.get("pitchHand"), dict) else None
                return pid, name, hand

            home_sp_id, home_sp_name, home_sp_hand = sp_info(home)
            away_sp_id, away_sp_name, away_sp_hand = sp_info(away)

            games.append({
                "game_pk": game_pk,
                "game_date": game_date,
                "game_time_utc": g.get("gameDate"),   # ISO 8601
                "status": status,
                "home_team_id": home.get("team", {}).get("id"),
                "home_team": home.get("team", {}).get("abbreviation", ""),
                "away_team_id": away.get("team", {}).get("id"),
                "away_team": away.get("team", {}).get("abbreviation", ""),
                "venue": g.get("venue", {}).get("name", ""),
                "home_sp_id": home_sp_id,
                "home_sp_name": home_sp_name,
                "home_sp_hand": home_sp_hand,
                "away_sp_id": away_sp_id,
                "away_sp_name": away_sp_name,
                "away_sp_hand": away_sp_hand,
            })

    return games


# ── Pitcher handedness (supplementary) ────────────────────────────────────────

def get_pitcher_hand(player_id: int) -> Optional[str]:
    """Returns 'R' or 'L' for the pitcher's throwing hand."""
    try:
        data = _get(f"/api/v1/people/{player_id}")
        people = data.get("people", [])
        if people:
            return people[0].get("pitchHand", {}).get("code")
    except Exception as exc:
        log.warning("Could not fetch hand for player %s: %s", player_id, exc)
    return None


# ── Lineups ───────────────────────────────────────────────────────────────────

def get_boxscore_lineups(game_pk: int) -> dict[str, list[dict]]:
    """
    Fetches the boxscore for *game_pk* and returns:
        {
            "home": [{"player_id": ..., "player_name": ...,
                       "batting_order": 1, "batter_hand": "R"}, ...],
            "away": [...]
        }

    Returns empty lists for each side if the lineup isn't posted yet.
    """
    try:
        data = _get(f"/api/v1/game/{game_pk}/boxscore")
    except Exception as exc:
        log.warning("Boxscore unavailable for game %s: %s", game_pk, exc)
        return {"home": [], "away": []}

    result: dict[str, list[dict]] = {"home": [], "away": []}

    for side in ("home", "away"):
        team_data = data.get("teams", {}).get(side, {})
        batters = team_data.get("batters", [])        # ordered list of player IDs
        players = team_data.get("players", {})

        for order, pid in enumerate(batters[:9], start=1):
            key = f"ID{pid}"
            p = players.get(key, {})
            person = p.get("person", {})
            hand = p.get("batSide", {}).get("code") \
                or person.get("batSide", {}).get("code")

            result[side].append({
                "player_id": pid,
                "player_name": person.get("fullName", ""),
                "batting_order": order,
                "batter_hand": hand,
            })

    return result


# ── Kalshi market lines (free, no auth required) ──────────────────────────────

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def get_kalshi_mlb_lines(game_date: date) -> list[dict]:
    """
    Attempts to fetch MLB moneyline markets from Kalshi's public API.
    Returns a list of:
        {"home_team": str, "away_team": str,
         "home_yes_price": float,   # 0-1 probability implied by best bid
         "away_yes_price": float}

    Returns empty list on any error (Kalshi availability is not guaranteed).
    """
    date_str = game_date.strftime("%Y%m%d")
    try:
        resp = requests.get(
            f"{KALSHI_BASE}/events",
            params={"status": "open", "series_ticker": "MLBM", "limit": 100},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        events = resp.json().get("events", [])
    except Exception as exc:
        log.debug("Kalshi fetch failed: %s", exc)
        return []

    lines = []
    for event in events:
        ticker: str = event.get("event_ticker", "")
        # Expected format: MLBM-YYYYMMDD-AWAYTEAM-HOMETEAM
        if date_str not in ticker:
            continue
        try:
            markets = event.get("markets", [])
            if len(markets) < 2:
                continue
            # Kalshi shows both sides; find home/away from subtitle or title
            title: str = event.get("title", "")
            # Very rough: split on ' @ ' or ' vs '
            if " @ " in title:
                away_name, home_name = [t.strip() for t in title.split(" @ ", 1)]
            elif " vs " in title.lower():
                away_name, home_name = [t.strip() for t in title.lower().split(" vs ", 1)]
            else:
                continue

            # Use yes_bid price (best buy) as implied probability
            prices = {m.get("subtitle", "").lower(): m.get("yes_bid", 50) / 100
                      for m in markets}

            lines.append({
                "home_team": home_name,
                "away_team": away_name,
                "home_yes_price": prices.get("home", None),
                "away_yes_price": prices.get("away", None),
                "source": "kalshi",
            })
        except Exception:
            continue

    return lines
