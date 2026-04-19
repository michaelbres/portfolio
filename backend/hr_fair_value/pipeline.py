"""
Daily HR fair value pipeline.

Orchestrates:
  1. Fetch schedule + probable pitchers from MLB Stats API
  2. Fetch (or project) lineups
  3. Compute batter HR rates and pitcher HR-allowed rates from Statcast
  4. Calculate per-batter HR probabilities
  5. Optionally fetch market HR props from The Odds API
  6. Persist results to hr_fair_value_games + hr_fair_value_players tables

Usage (called by data_pipeline/fetch_hr_fair_value.py or API endpoint):
    from hr_fair_value.pipeline import run_hr_pipeline
    run_hr_pipeline(game_date, db)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Any

from sqlalchemy.orm import Session

from models import HRFairValueGame, HRFairValuePlayer

from fair_value.mlb_api import (
    get_schedule,
    get_boxscore_lineups,
    get_pitcher_hand,
)
from fair_value.stats_engine import (
    projected_lineup,
    batter_stats,
)
from fair_value.weather import weather_carry_factor
from fair_value.win_probability import prob_to_american
from fair_value.constants import PA_WEIGHTS, TEAM_ALIASES

from .constants import (
    MODEL_VERSION,
    hr_park_factor,
    expected_pa,
    LEAGUE_AVG_HR_PER_PA,
    HR_TEMP_COEFF_PER_F,
    HR_WIND_COEFF_PER_MPH,
    HR_TEMP_BASELINE_F,
)
from .stats_engine import batter_hr_stats, pitcher_hr_allowed_stats
from .hr_model import compute_batter_hr_prob, compute_game_hr_totals, weather_hr_factor
from .odds_api import get_hr_props, match_market_odds

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _enrich_sp_hand(sp_id: Optional[int], sp_hand: Optional[str]) -> Optional[str]:
    if sp_hand:
        return sp_hand
    if sp_id:
        return get_pitcher_hand(sp_id)
    return None


def _build_lineup(db: Session, game_pk: int, team: str,
                  sp_hand: Optional[str], is_home: bool) -> tuple[list[dict], str]:
    """Get confirmed or projected lineup. Returns (slots, source_label)."""
    box = get_boxscore_lineups(game_pk)
    confirmed_slots = box.get("home", []) if is_home else box.get("away", [])

    if len(confirmed_slots) >= 8:
        slots = []
        for s in confirmed_slots[:9]:
            order = s["batting_order"]
            slots.append({
                "player_id":   s["player_id"],
                "player_name": s["player_name"],
                "batter_hand": s["batter_hand"] or "R",
                "batting_order": order,
            })
        return slots, "confirmed"

    proj_slots = projected_lineup(db, team, sp_hand=sp_hand)
    return proj_slots, "projected"


def _weather_hr_adjustment(home_team: str, game_time_utc: Optional[str]) -> float:
    """
    Compute HR-specific weather factor.

    We use the existing weather module's raw carry factor but scale it
    for HRs. The base weather_carry_factor uses 0.25% per °F and 0.5% per mph.
    HRs are more sensitive: 1.5% per °F and 1.0% per mph.
    So we amplify the deviation from 1.0 by a factor of ~4 for temp and ~2 for wind.
    Combined: roughly 3x amplification of deviation from neutral.
    """
    base_carry = weather_carry_factor(home_team, game_time_utc)
    deviation = base_carry - 1.0
    # Amplify for HR sensitivity (HRs ~3x more sensitive to weather than overall runs)
    hr_carry = 1.0 + deviation * 3.0
    return max(0.70, min(1.40, round(hr_carry, 4)))


# ── Core pipeline ────────────────────────────────────────────────────────────

def run_hr_pipeline(game_date: date, db: Session,
                    force: bool = False) -> dict[str, Any]:
    """
    Run the HR fair value pipeline for all regular-season games on game_date.

    Returns dict with keys: games (list), games_computed (int), error (str|None).
    """
    log.info("HR fair value pipeline: %s", game_date)

    if not force:
        existing = db.query(HRFairValueGame).filter(
            HRFairValueGame.game_date == game_date
        ).count()
        if existing > 0:
            log.info("Already have %d HR games for %s; skipping", existing, game_date)
            return {"games": [], "games_computed": 0,
                    "error": f"Already computed {existing} game(s) for {game_date}. Use Force Recompute to refresh."}

    # 1. Schedule
    try:
        games = get_schedule(game_date)
    except Exception as exc:
        msg = f"MLB Stats API error: {exc}"
        log.error("Schedule fetch failed: %s", exc)
        return {"games": [], "games_computed": 0, "error": msg}

    if not games:
        msg = f"No regular-season games found on {game_date}."
        return {"games": [], "games_computed": 0, "error": msg}

    log.info("Processing %d games for HR props", len(games))

    # 2. Market odds (The Odds API)
    market_props = []
    try:
        market_props = get_hr_props()
    except Exception:
        log.warning("Market HR props fetch failed — continuing without market odds")

    results = []
    failed_errors: list[str] = []

    for g in games:
        try:
            result = _process_game(db, g, market_props)
            if result:
                results.append(result)
        except Exception as exc:
            game_pk = g["game_pk"]
            log.error("Failed HR game %s: %s", game_pk, exc, exc_info=True)
            failed_errors.append(f"{g['away_team']}@{g['home_team']}: {exc}")

    try:
        db.commit()
    except Exception as exc:
        log.error("HR pipeline DB commit failed: %s", exc, exc_info=True)
        db.rollback()
        return {"games": [], "games_computed": 0, "error": f"DB commit failed: {exc}"}

    log.info("HR pipeline complete: %d games, %d failed", len(results), len(failed_errors))

    error_msg = None
    if failed_errors and not results:
        error_msg = f"All {len(failed_errors)} games failed. First: {failed_errors[0]}"
    elif failed_errors:
        error_msg = f"{len(failed_errors)} game(s) failed: {failed_errors[0]}"

    return {"games": results, "games_computed": len(results), "error": error_msg}


def _process_game(db: Session, game: dict,
                  market_props: list[dict]) -> Optional[dict]:
    game_pk = game["game_pk"]
    home_team = game["home_team"]
    away_team = game["away_team"]

    log.info("  HR: %s @ %s (pk=%s)", away_team, home_team, game_pk)

    # Starting pitchers
    home_sp_id = game.get("home_sp_id")
    home_sp_name = game.get("home_sp_name") or "TBD"
    home_sp_hand = _enrich_sp_hand(home_sp_id, game.get("home_sp_hand"))

    away_sp_id = game.get("away_sp_id")
    away_sp_name = game.get("away_sp_name") or "TBD"
    away_sp_hand = _enrich_sp_hand(away_sp_id, game.get("away_sp_hand"))

    # Pitcher HR-allowed factors
    home_pitcher_hr = pitcher_hr_allowed_stats(db, home_sp_id) if home_sp_id else {
        "hr_factor": 1.0, "hr_rate_blended": LEAGUE_AVG_HR_PER_PA
    }
    away_pitcher_hr = pitcher_hr_allowed_stats(db, away_sp_id) if away_sp_id else {
        "hr_factor": 1.0, "hr_rate_blended": LEAGUE_AVG_HR_PER_PA
    }

    # Park + weather
    park_hr_f = hr_park_factor(home_team)
    weather_hr_f = _weather_hr_adjustment(home_team, game.get("game_time_utc"))

    # Lineups
    home_slots, home_src = _build_lineup(db, game_pk, home_team, sp_hand=away_sp_hand, is_home=True)
    away_slots, away_src = _build_lineup(db, game_pk, away_team, sp_hand=home_sp_hand, is_home=False)

    # Process each batter
    player_results = []

    for is_home, slots, opp_pitcher_hr, opp_sp_hand in [
        (True,  home_slots, away_pitcher_hr, away_sp_hand),
        (False, away_slots, home_pitcher_hr, home_sp_hand),
    ]:
        team = home_team if is_home else away_team
        for slot in slots:
            player_id = slot.get("player_id")
            player_name = slot.get("player_name", "Unknown")
            batting_order = slot.get("batting_order", 9)
            batter_hand = slot.get("batter_hand", "R")

            # Batter HR stats (split by opposing pitcher hand)
            if player_id:
                hr_stats = batter_hr_stats(db, player_id, vs_hand=opp_sp_hand)
            else:
                hr_stats = {
                    "hr_rate_full": None, "pa_full": 0, "hr_full": 0,
                    "hr_rate_recent": None, "pa_recent": 0, "hr_recent": 0,
                    "hr_rate_blended": LEAGUE_AVG_HR_PER_PA,
                }

            exp_pa = expected_pa(batting_order)

            # Compute HR probability
            hr_result = compute_batter_hr_prob(
                hr_rate_blended=hr_stats["hr_rate_blended"],
                pitcher_hr_factor=opp_pitcher_hr["hr_factor"],
                park_hr_factor=park_hr_f,
                weather_hr_factor=weather_hr_f,
                expected_pa=exp_pa,
            )

            # Match market odds
            market_match = match_market_odds(player_name, market_props) if player_name else None
            market_hr_prob = market_match["market_hr_prob"] if market_match else None
            market_hr_odds = market_match["market_hr_odds"] if market_match else None
            market_source = market_match["source"] if market_match else None
            edge = round(hr_result["model_hr_prob"] - market_hr_prob, 4) if market_hr_prob else None

            player_results.append({
                "game_pk": game_pk,
                "team": team,
                "is_home": is_home,
                "batting_order": batting_order,
                "player_id": player_id,
                "player_name": player_name,
                "batter_hand": batter_hand,
                "vs_pitcher_hand": opp_sp_hand,
                "hr_rate_full": hr_stats.get("hr_rate_full"),
                "hr_rate_recent": hr_stats.get("hr_rate_recent"),
                "hr_rate_blended": hr_stats["hr_rate_blended"],
                "pa_full": hr_stats.get("pa_full", 0),
                "pa_recent": hr_stats.get("pa_recent", 0),
                "pitcher_hr_factor": opp_pitcher_hr["hr_factor"],
                "park_hr_factor": park_hr_f,
                "weather_hr_factor": weather_hr_f,
                "expected_pa": exp_pa,
                **hr_result,
                "market_hr_prob": market_hr_prob,
                "market_hr_odds": market_hr_odds,
                "market_source": market_source,
                "edge_pp": edge,
            })

    # Game-level totals
    totals = compute_game_hr_totals(player_results)

    # ── Persist game row ─────────────────────────────────────────────────────
    existing = db.query(HRFairValueGame).filter(
        HRFairValueGame.game_pk == game_pk
    ).first()

    if existing:
        row = existing
    else:
        row = HRFairValueGame(game_pk=game_pk)
        db.add(row)

    row.game_date = game["game_date"]
    row.game_time_utc = game.get("game_time_utc")
    row.home_team = home_team
    row.away_team = away_team
    row.venue = game.get("venue")
    row.home_sp_id = home_sp_id
    row.home_sp_name = home_sp_name
    row.home_sp_hand = home_sp_hand
    row.away_sp_id = away_sp_id
    row.away_sp_name = away_sp_name
    row.away_sp_hand = away_sp_hand
    row.park_hr_factor = park_hr_f
    row.weather_hr_factor = weather_hr_f
    row.home_team_hr_lambda = totals["home_team_hr_lambda"]
    row.away_team_hr_lambda = totals["away_team_hr_lambda"]
    row.game_total_hr_lambda = totals["game_total_hr_lambda"]
    row.home_team_hr_prob = totals["home_team_hr_prob"]
    row.away_team_hr_prob = totals["away_team_hr_prob"]
    row.model_version = MODEL_VERSION

    # ── Persist player rows ──────────────────────────────────────────────────
    # Delete existing player rows for this game, then re-insert
    db.query(HRFairValuePlayer).filter(
        HRFairValuePlayer.game_pk == game_pk
    ).delete()

    for p in player_results:
        player_row = HRFairValuePlayer(
            game_pk=game_pk,
            team=p["team"],
            is_home=p["is_home"],
            batting_order=p["batting_order"],
            player_id=p["player_id"],
            player_name=p["player_name"],
            batter_hand=p["batter_hand"],
            vs_pitcher_hand=p["vs_pitcher_hand"],
            hr_rate_full=p.get("hr_rate_full"),
            hr_rate_recent=p.get("hr_rate_recent"),
            hr_rate_blended=p["hr_rate_blended"],
            pa_full=p.get("pa_full"),
            pa_recent=p.get("pa_recent"),
            pitcher_hr_factor=p["pitcher_hr_factor"],
            park_hr_factor=p["park_hr_factor"],
            weather_hr_factor=p["weather_hr_factor"],
            expected_pa=p["expected_pa"],
            hr_lambda=p["hr_lambda"],
            model_hr_prob=p["model_hr_prob"],
            fair_hr_odds=p["fair_hr_odds"],
            market_hr_prob=p.get("market_hr_prob"),
            market_hr_odds=p.get("market_hr_odds"),
            market_source=p.get("market_source"),
            edge_pp=p.get("edge_pp"),
        )
        db.add(player_row)

    db.flush()

    # Build response dict
    return _game_to_dict(row, player_results)


def _game_to_dict(game_row: HRFairValueGame, players: list[dict]) -> dict:
    """Serialize a game + its players for the API response."""
    return {
        "game_pk": game_row.game_pk,
        "game_date": str(game_row.game_date),
        "game_time_utc": game_row.game_time_utc,
        "home_team": game_row.home_team,
        "away_team": game_row.away_team,
        "venue": game_row.venue,
        "home_sp_name": game_row.home_sp_name,
        "home_sp_hand": game_row.home_sp_hand,
        "away_sp_name": game_row.away_sp_name,
        "away_sp_hand": game_row.away_sp_hand,
        "park_hr_factor": game_row.park_hr_factor,
        "weather_hr_factor": game_row.weather_hr_factor,
        "home_team_hr_lambda": game_row.home_team_hr_lambda,
        "away_team_hr_lambda": game_row.away_team_hr_lambda,
        "game_total_hr_lambda": game_row.game_total_hr_lambda,
        "home_team_hr_prob": game_row.home_team_hr_prob,
        "away_team_hr_prob": game_row.away_team_hr_prob,
        "model_version": game_row.model_version,
        "players": players,
    }
