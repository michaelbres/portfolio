"""
The Odds API integration for MLB player HR props.

Free tier: 500 requests/month. Returns player-level HR Over/Under
lines from DraftKings, FanDuel, and other US sportsbooks.

API key stored in THE_ODDS_API_KEY environment variable.
"""

from __future__ import annotations

import logging
import os
import unicodedata
from typing import Optional

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "baseball_mlb"
TIMEOUT = 15


def _normalize_name(name: str) -> str:
    """Normalize player name for matching: strip accents, lowercase, handle Jr/Sr."""
    # Strip unicode accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase and strip suffixes
    result = ascii_name.lower().strip()
    for suffix in (" jr.", " jr", " sr.", " sr", " ii", " iii", " iv"):
        result = result.replace(suffix, "")
    return result.strip()


def get_hr_props() -> list[dict]:
    """
    Fetch current MLB player HR prop odds from The Odds API.

    Returns a list of dicts:
        {
            "player_name": "Aaron Judge",
            "player_name_normalized": "aaron judge",
            "market_hr_prob": 0.182,
            "market_hr_odds": +450,
            "source": "draftkings",
        }

    Returns empty list if API key is missing or request fails.
    """
    api_key = os.environ.get("THE_ODDS_API_KEY")
    if not api_key:
        log.info("THE_ODDS_API_KEY not set — skipping market odds fetch")
        return []

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/{SPORT}/events",
            params={"apiKey": api_key},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        events = resp.json()
    except Exception as exc:
        log.warning("Failed to fetch MLB events from The Odds API: %s", exc)
        return []

    if not events:
        return []

    # Fetch HR props for each event
    all_props: list[dict] = []
    event_ids = [e["id"] for e in events]

    for event_id in event_ids:
        try:
            resp = requests.get(
                f"{BASE_URL}/sports/{SPORT}/events/{event_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": "batter_home_runs",
                    "oddsFormat": "american",
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.debug("Failed to fetch HR props for event %s: %s", event_id, exc)
            continue

        # Parse bookmaker odds
        for bookmaker in data.get("bookmakers", []):
            source = bookmaker.get("key", "unknown")
            for market in bookmaker.get("markets", []):
                if market.get("key") != "batter_home_runs":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == "Over" and outcome.get("point", 0) == 0.5:
                        player_name = outcome.get("description", "")
                        odds = outcome.get("price", 0)
                        if player_name and odds:
                            prob = _american_to_prob(odds)
                            all_props.append({
                                "player_name": player_name,
                                "player_name_normalized": _normalize_name(player_name),
                                "market_hr_prob": round(prob, 4),
                                "market_hr_odds": odds,
                                "source": source,
                            })

    # Deduplicate: keep DraftKings first, then FanDuel, then others
    seen: dict[str, dict] = {}
    source_priority = {"draftkings": 0, "fanduel": 1}
    for prop in sorted(all_props, key=lambda p: source_priority.get(p["source"], 99)):
        key = prop["player_name_normalized"]
        if key not in seen:
            seen[key] = prop

    result = list(seen.values())
    log.info("Fetched %d unique player HR props from The Odds API", len(result))
    return result


def match_market_odds(player_name: str, market_props: list[dict]) -> Optional[dict]:
    """
    Find market HR odds for a player by normalized name matching.

    Returns the matched prop dict or None.
    """
    if not market_props:
        return None

    normalized = _normalize_name(player_name)

    # Exact match first
    for prop in market_props:
        if prop["player_name_normalized"] == normalized:
            return prop

    # Partial match: try last name only
    parts = normalized.split()
    if len(parts) >= 2:
        last_name = parts[-1]
        first_initial = parts[0][0] if parts[0] else ""
        candidates = []
        for prop in market_props:
            prop_parts = prop["player_name_normalized"].split()
            if len(prop_parts) >= 2 and prop_parts[-1] == last_name:
                if prop_parts[0][0] == first_initial:
                    candidates.append(prop)
        if len(candidates) == 1:
            return candidates[0]

    return None


def _american_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)
