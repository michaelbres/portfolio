"""
Daily fair value pipeline.

Orchestrates:
  1. Fetch schedule + probable pitchers from MLB Stats API
  2. Fetch (or project) lineups
  3. Compute pitcher / bullpen / lineup stats from Statcast DB
  4. Calculate win probabilities and fair odds
  5. Persist results to fair_value_games + fair_value_lineup_slots tables
  6. Optionally fetch Kalshi market lines for comparison

Usage (called by data_pipeline/fetch_fair_value.py):
    from fair_value.pipeline import run_pipeline
    run_pipeline(game_date, db, season=2025, force=False)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional, Any

from sqlalchemy.orm import Session

from models import FairValueGame, FairValueLineupSlot

from .constants import (
    DEFAULT_PITCH_LIMIT,
    LEAGUE_AVG_WOBA,
    park_factor,
)
from .mlb_api import (
    get_schedule,
    get_boxscore_lineups,
    get_pitcher_hand,
    get_kalshi_mlb_lines,
)
from .stats_engine import (
    pitcher_stats,
    team_bullpen_stats,
    projected_lineup,
    lineup_weighted_woba,
    batter_stats,
)
from .win_probability import (
    compute_game_fair_value,
    projected_innings,
)

log = logging.getLogger(__name__)

MODEL_VERSION = "1.0"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_pitch_limit(sp_stats: dict) -> int:
    """
    Estimate a reasonable default pitch limit for a SP based on recent usage.
    Uses average pitches per start derived from pitches_per_inning × avg innings.
    Falls back to DEFAULT_PITCH_LIMIT.
    """
    ppi  = sp_stats.get("pitches_per_inning", 15.5)
    # Target 6 innings as default depth; cap at 110, floor at 75
    limit = round(ppi * 6)
    return max(75, min(110, limit))


def _enrich_sp_hand(sp_id: Optional[int], sp_hand: Optional[str]) -> Optional[str]:
    """Fill in missing SP hand by hitting the MLB people endpoint."""
    if sp_hand:
        return sp_hand
    if sp_id:
        return get_pitcher_hand(sp_id)
    return None


# ── Lineup builder ────────────────────────────────────────────────────────────

def _build_lineup(db: Session, game_pk: int, team: str, season: int,
                  sp_hand: Optional[str], team_abbr: str) -> tuple[list[dict], str]:
    """
    Try confirmed boxscore lineup first; fall back to projected.
    Returns (slots, source_label).
    """
    source = "projected"

    # Attempt confirmed lineup via boxscore
    box = get_boxscore_lineups(game_pk)
    confirmed_side = "home" if team == team_abbr else None
    # We need to figure out which side (home/away) this team is.
    # The caller passes team_abbr = the game's home_team or away_team.
    # Here team IS team_abbr (we call this function once per team).
    confirmed_slots = box.get("home", []) if team == team_abbr else box.get("away", [])

    if len(confirmed_slots) >= 8:
        source = "confirmed"
        slots = []
        for s in confirmed_slots[:9]:
            stats = batter_stats(db, s["player_id"], season, vs_hand=sp_hand)
            order = s["batting_order"]
            from .constants import PA_WEIGHTS
            slots.append({
                "player_id":     s["player_id"],
                "player_name":   s["player_name"],
                "batter_hand":   s["batter_hand"] or "R",
                "batting_order": order,
                "woba_vs_sp_hand": stats["woba_blended"],
                "woba_season":   stats["woba_season"],
                "woba_recent":   stats["woba_recent"],
                "woba_blended":  stats["woba_blended"],
                "pa_weight":     PA_WEIGHTS[order - 1],
            })
        return slots, source

    # Fall back to projected lineup from recent Statcast data
    slots = projected_lineup(db, team, season, sp_hand=sp_hand)
    return slots, source


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(game_date: date, db: Session, season: int | None = None,
                 force: bool = False) -> dict[str, Any]:
    """
    Run the fair value pipeline for all regular-season games on *game_date*.

    Parameters
    ----------
    game_date  Target date.
    db         SQLAlchemy session (caller manages lifecycle).
    season     MLB season year for Statcast queries. Defaults to game_date.year.
    force      If True, recompute even if rows already exist for today.

    Returns dict with keys: games (list), games_computed (int), error (str|None).
    """
    if season is None:
        season = game_date.year

    log.info("Fair value pipeline: %s  season=%d", game_date, season)

    # Check for existing rows (skip unless forced)
    if not force:
        existing = db.query(FairValueGame).filter(
            FairValueGame.game_date == game_date
        ).count()
        if existing > 0:
            log.info("Already have %d games for %s; skipping (use force=True to override)",
                     existing, game_date)
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
        msg = f"No regular-season games found on {game_date} via MLB Stats API."
        log.info(msg)
        return {"games": [], "games_computed": 0, "error": msg}

    log.info("Processing %d games", len(games))

    # 2. Optional: Kalshi market lines
    kalshi_lines = []
    try:
        kalshi_lines = get_kalshi_mlb_lines(game_date)
    except Exception:
        pass   # market lines are optional

    results = []

    for g in games:
        game_pk   = g["game_pk"]
        home_team = g["home_team"]
        away_team = g["away_team"]

        log.info("  %s @ %s  (pk=%s)", away_team, home_team, game_pk)

        try:
            result = _process_game(
                db=db, game=g, season=season,
                kalshi_lines=kalshi_lines,
            )
            if result:
                results.append(result)
        except Exception as exc:
            log.error("    Failed game %s: %s", game_pk, exc, exc_info=True)

    db.commit()
    log.info("Pipeline complete: %d games processed", len(results))
    return {"games": results, "games_computed": len(results), "error": None}


def _process_game(db: Session, game: dict, season: int,
                  kalshi_lines: list[dict]) -> Optional[dict]:
    game_pk   = game["game_pk"]
    home_team = game["home_team"]
    away_team = game["away_team"]

    # ── Starting pitcher stats ────────────────────────────────────────────────
    home_sp_id   = game.get("home_sp_id")
    home_sp_name = game.get("home_sp_name") or "TBD"
    home_sp_hand = _enrich_sp_hand(home_sp_id, game.get("home_sp_hand"))

    away_sp_id   = game.get("away_sp_id")
    away_sp_name = game.get("away_sp_name") or "TBD"
    away_sp_hand = _enrich_sp_hand(away_sp_id, game.get("away_sp_hand"))

    if home_sp_id:
        home_sp_s = pitcher_stats(db, home_sp_id, season)
    else:
        home_sp_s = {
            "woba_season": None, "pa_season": 0,
            "woba_recent": None, "pa_recent": 0,
            "woba_blended": LEAGUE_AVG_WOBA,
            "pitches_per_inning": 15.5,
        }

    if away_sp_id:
        away_sp_s = pitcher_stats(db, away_sp_id, season)
    else:
        away_sp_s = {
            "woba_season": None, "pa_season": 0,
            "woba_recent": None, "pa_recent": 0,
            "woba_blended": LEAGUE_AVG_WOBA,
            "pitches_per_inning": 15.5,
        }

    # Check if a manual pitch limit override exists in the DB
    existing = db.query(FairValueGame).filter(
        FairValueGame.game_pk == game_pk
    ).first()

    if existing and existing.home_pitch_limit_manual:
        home_pitch_limit = existing.home_pitch_limit
    else:
        home_pitch_limit = _default_pitch_limit(home_sp_s)

    if existing and existing.away_pitch_limit_manual:
        away_pitch_limit = existing.away_pitch_limit
    else:
        away_pitch_limit = _default_pitch_limit(away_sp_s)

    # ── Bullpen stats ─────────────────────────────────────────────────────────
    home_bp = team_bullpen_stats(db, home_team, game["game_date"], season)
    away_bp = team_bullpen_stats(db, away_team, game["game_date"], season)

    # ── Lineups ───────────────────────────────────────────────────────────────
    home_slots, home_src = _build_lineup(
        db, game_pk, home_team, season, away_sp_hand, home_team
    )
    away_slots, away_src = _build_lineup(
        db, game_pk, away_team, season, home_sp_hand, home_team
    )

    home_lineup_woba = lineup_weighted_woba(home_slots)
    away_lineup_woba = lineup_weighted_woba(away_slots)

    # ── Win probability ───────────────────────────────────────────────────────
    pf = park_factor(home_team)

    fv = compute_game_fair_value(
        home_lineup_woba=    home_lineup_woba,
        away_lineup_woba=    away_lineup_woba,
        home_sp_woba=        home_sp_s["woba_blended"],
        away_sp_woba=        away_sp_s["woba_blended"],
        home_bp_woba=        home_bp["woba_fatigued"],
        away_bp_woba=        away_bp["woba_fatigued"],
        home_pitch_limit=    home_pitch_limit,
        away_pitch_limit=    away_pitch_limit,
        home_pitches_per_inn=home_sp_s["pitches_per_inning"],
        away_pitches_per_inn=away_sp_s["pitches_per_inning"],
        park_factor_val=     pf,
    )

    # ── Market lines (Kalshi) ─────────────────────────────────────────────────
    home_market_odds = None
    away_market_odds = None
    market_source    = None

    for line in kalshi_lines:
        ht = line.get("home_team", "").upper()
        at = line.get("away_team", "").upper()
        if home_team in ht or ht in home_team:
            if line.get("home_yes_price"):
                from .win_probability import prob_to_american
                home_market_odds = prob_to_american(line["home_yes_price"])
                away_market_odds = prob_to_american(line["away_yes_price"])
                market_source    = "kalshi"
            break

    # ── Persist ───────────────────────────────────────────────────────────────
    if existing:
        row = existing
    else:
        row = FairValueGame(game_pk=game_pk)
        db.add(row)

    # Preserve manual overrides
    row.game_date         = game["game_date"]
    row.game_time_utc     = game.get("game_time_utc")
    row.home_team         = home_team
    row.away_team         = away_team
    row.venue             = game.get("venue")
    row.home_sp_id        = home_sp_id
    row.home_sp_name      = home_sp_name
    row.home_sp_hand      = home_sp_hand
    row.away_sp_id        = away_sp_id
    row.away_sp_name      = away_sp_name
    row.away_sp_hand      = away_sp_hand

    if not (existing and existing.home_pitch_limit_manual):
        row.home_pitch_limit = home_pitch_limit
    if not (existing and existing.away_pitch_limit_manual):
        row.away_pitch_limit = away_pitch_limit

    row.home_sp_pitches_per_inning = round(home_sp_s["pitches_per_inning"], 2)
    row.home_sp_proj_innings       = fv["home_sp_proj_innings"]
    row.home_sp_woba_season        = home_sp_s["woba_season"]
    row.home_sp_woba_recent        = home_sp_s["woba_recent"]
    row.home_sp_woba_blended       = home_sp_s["woba_blended"]
    row.home_sp_pa_season          = home_sp_s["pa_season"]
    row.home_sp_pa_recent          = home_sp_s["pa_recent"]

    row.away_sp_pitches_per_inning = round(away_sp_s["pitches_per_inning"], 2)
    row.away_sp_proj_innings       = fv["away_sp_proj_innings"]
    row.away_sp_woba_season        = away_sp_s["woba_season"]
    row.away_sp_woba_recent        = away_sp_s["woba_recent"]
    row.away_sp_woba_blended       = away_sp_s["woba_blended"]
    row.away_sp_pa_season          = away_sp_s["pa_season"]
    row.away_sp_pa_recent          = away_sp_s["pa_recent"]

    row.home_bp_woba_raw      = round(home_bp["woba_raw"], 4)
    row.home_bp_woba_fatigued = round(home_bp["woba_fatigued"], 4)
    row.away_bp_woba_raw      = round(away_bp["woba_raw"], 4)
    row.away_bp_woba_fatigued = round(away_bp["woba_fatigued"], 4)

    row.home_lineup_woba   = round(home_lineup_woba, 4)
    row.away_lineup_woba   = round(away_lineup_woba, 4)
    row.home_lineup_source = home_src
    row.away_lineup_source = away_src

    row.park_factor    = pf
    row.home_lambda    = fv["home_lambda"]
    row.away_lambda    = fv["away_lambda"]
    row.home_win_prob  = fv["home_win_prob"]
    row.away_win_prob  = fv["away_win_prob"]
    row.home_fair_odds = fv["home_fair_odds"]
    row.away_fair_odds = fv["away_fair_odds"]

    row.home_market_odds = home_market_odds
    row.away_market_odds = away_market_odds
    row.market_source    = market_source
    row.model_version    = MODEL_VERSION

    # Persist lineup slots (delete old, insert new)
    db.query(FairValueLineupSlot).filter(
        FairValueLineupSlot.game_pk == game_pk
    ).delete()

    for slot in home_slots + away_slots:
        db.add(FairValueLineupSlot(
            game_pk=       game_pk,
            team=          home_team if slot in home_slots else away_team,
            batting_order= slot["batting_order"],
            player_id=     slot.get("player_id"),
            player_name=   slot.get("player_name"),
            batter_hand=   slot.get("batter_hand"),
            woba_season=   slot.get("woba_season"),
            woba_recent=   slot.get("woba_recent"),
            woba_blended=  slot.get("woba_blended"),
            woba_vs_sp_hand= slot.get("woba_vs_sp_hand"),
            pa_weight=     slot.get("pa_weight"),
        ))

    # Build return dict
    result = {
        "game_pk":        game_pk,
        "home_team":      home_team,
        "away_team":      away_team,
        "home_sp_name":   home_sp_name,
        "away_sp_name":   away_sp_name,
        "home_win_prob":  fv["home_win_prob"],
        "home_fair_odds": fv["home_fair_odds"],
        "away_fair_odds": fv["away_fair_odds"],
        "home_lambda":    fv["home_lambda"],
        "away_lambda":    fv["away_lambda"],
    }
    log.info("    → home %.1f%% (%+d)  away %.1f%% (%+d)  λ=%.2f/%.2f",
             fv["home_win_prob"] * 100, fv["home_fair_odds"],
             fv["away_win_prob"] * 100, fv["away_fair_odds"],
             fv["home_lambda"], fv["away_lambda"])
    return result


# ── Recalculate a single game (after pitch limit override) ────────────────────

def recalculate_game(db: Session, game_pk: int, season: int = 2025) -> Optional[dict]:
    """
    Recompute fair value for a single game_pk, honouring any manual overrides
    already stored on the FairValueGame row.  Returns the updated row data.
    """
    row = db.query(FairValueGame).filter(FairValueGame.game_pk == game_pk).first()
    if not row:
        return None

    # Re-fetch the game from our DB (no external call needed for recalc)
    home_sp_s = pitcher_stats(db, row.home_sp_id, season) if row.home_sp_id else {
        "woba_blended": LEAGUE_AVG_WOBA, "pitches_per_inning": 15.5,
    }
    away_sp_s = pitcher_stats(db, row.away_sp_id, season) if row.away_sp_id else {
        "woba_blended": LEAGUE_AVG_WOBA, "pitches_per_inning": 15.5,
    }

    pf = park_factor(row.home_team)

    fv = compute_game_fair_value(
        home_lineup_woba=    row.home_lineup_woba or LEAGUE_AVG_WOBA,
        away_lineup_woba=    row.away_lineup_woba or LEAGUE_AVG_WOBA,
        home_sp_woba=        home_sp_s["woba_blended"],
        away_sp_woba=        away_sp_s["woba_blended"],
        home_bp_woba=        row.home_bp_woba_fatigued or LEAGUE_AVG_WOBA,
        away_bp_woba=        row.away_bp_woba_fatigued or LEAGUE_AVG_WOBA,
        home_pitch_limit=    row.home_pitch_limit or DEFAULT_PITCH_LIMIT,
        away_pitch_limit=    row.away_pitch_limit or DEFAULT_PITCH_LIMIT,
        home_pitches_per_inn=row.home_sp_pitches_per_inning or 15.5,
        away_pitches_per_inn=row.away_sp_pitches_per_inning or 15.5,
        park_factor_val=     pf,
    )

    row.home_sp_proj_innings = fv["home_sp_proj_innings"]
    row.away_sp_proj_innings = fv["away_sp_proj_innings"]
    row.home_lambda    = fv["home_lambda"]
    row.away_lambda    = fv["away_lambda"]
    row.home_win_prob  = fv["home_win_prob"]
    row.away_win_prob  = fv["away_win_prob"]
    row.home_fair_odds = fv["home_fair_odds"]
    row.away_fair_odds = fv["away_fair_odds"]
    db.commit()
    db.refresh(row)

    return _row_to_dict(row)


def _row_to_dict(row: FairValueGame) -> dict:
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
    }
