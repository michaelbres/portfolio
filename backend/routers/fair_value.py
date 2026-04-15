"""
Fair Value API router.

Endpoints
─────────
GET  /api/fair-value/games               ?date=YYYY-MM-DD
GET  /api/fair-value/games/{game_pk}
PATCH /api/fair-value/games/{game_pk}/pitch-limit   body: PitchLimitOverride
DELETE /api/fair-value/games/{game_pk}/pitch-limit/{side}
POST /api/fair-value/run                 ?date=YYYY-MM-DD  (trigger pipeline)
"""

import logging
import sys
import os
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import FairValueGame, FairValueLineupSlot
from fair_value.pipeline import run_pipeline, recalculate_game, _row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fair-value", tags=["fair-value"])

def _current_season(for_date: date) -> int:
    """Use the year of the target date as the season for Statcast lookups."""
    return for_date.year


# ── Schemas ───────────────────────────────────────────────────────────────────

class PitchLimitOverride(BaseModel):
    side: Literal["home", "away"]
    pitch_limit: int = Field(..., ge=50, le=150,
                              description="Pitch count limit for the starter (50–150)")


# ── Serialisers ───────────────────────────────────────────────────────────────

def _game_to_dict(row: FairValueGame) -> dict:
    d = _row_to_dict(row)
    # Convert non-serialisable types
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
    return d


def _slot_to_dict(slot: FairValueLineupSlot) -> dict:
    return {c.name: getattr(slot, c.name) for c in slot.__table__.columns}


# ── GET /games ────────────────────────────────────────────────────────────────

@router.get("/games")
def list_games(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    db: Session = Depends(get_db),
):
    """Return all computed fair value games for a given date."""
    if game_date:
        try:
            d = date.fromisoformat(game_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        d = date.today()

    rows = (
        db.query(FairValueGame)
        .filter(FairValueGame.game_date == d)
        .order_by(FairValueGame.game_time_utc.asc().nullslast())
        .all()
    )
    return {"date": d.isoformat(), "games": [_game_to_dict(r) for r in rows]}


# ── GET /games/{game_pk} ──────────────────────────────────────────────────────

@router.get("/games/{game_pk}")
def get_game(game_pk: int, db: Session = Depends(get_db)):
    """Return a single game with lineup detail."""
    row = db.query(FairValueGame).filter(FairValueGame.game_pk == game_pk).first()
    if not row:
        raise HTTPException(404, f"Game {game_pk} not found.")

    slots = (
        db.query(FairValueLineupSlot)
        .filter(FairValueLineupSlot.game_pk == game_pk)
        .order_by(FairValueLineupSlot.team, FairValueLineupSlot.batting_order)
        .all()
    )

    home_slots = [_slot_to_dict(s) for s in slots if s.team == row.home_team]
    away_slots = [_slot_to_dict(s) for s in slots if s.team == row.away_team]

    return {
        "game": _game_to_dict(row),
        "home_lineup": home_slots,
        "away_lineup": away_slots,
    }


# ── PATCH /games/{game_pk}/pitch-limit ───────────────────────────────────────

@router.patch("/games/{game_pk}/pitch-limit")
def set_pitch_limit(
    game_pk: int,
    body: PitchLimitOverride,
    db: Session = Depends(get_db),
):
    """
    Set a manual pitch count override for a starting pitcher.
    Immediately recomputes fair value and returns the updated game row.
    """
    row = db.query(FairValueGame).filter(FairValueGame.game_pk == game_pk).first()
    if not row:
        raise HTTPException(404, f"Game {game_pk} not found.")

    if body.side == "home":
        row.home_pitch_limit        = body.pitch_limit
        row.home_pitch_limit_manual = True
    else:
        row.away_pitch_limit        = body.pitch_limit
        row.away_pitch_limit_manual = True

    db.commit()

    updated = recalculate_game(db, game_pk, season=_current_season(row.game_date))
    if not updated:
        raise HTTPException(500, "Recalculation failed.")

    return {"game": updated}


# ── DELETE /games/{game_pk}/pitch-limit/{side} ────────────────────────────────

@router.delete("/games/{game_pk}/pitch-limit/{side}")
def remove_pitch_limit_override(
    game_pk: int,
    side: Literal["home", "away"],
    db: Session = Depends(get_db),
):
    """
    Remove a manual pitch limit override, reverting to the model's default.
    Recomputes fair value.
    """
    row = db.query(FairValueGame).filter(FairValueGame.game_pk == game_pk).first()
    if not row:
        raise HTTPException(404, f"Game {game_pk} not found.")

    if side == "home":
        row.home_pitch_limit_manual = False
    else:
        row.away_pitch_limit_manual = False

    db.commit()

    updated = recalculate_game(db, game_pk, season=_current_season(row.game_date))
    return {"game": updated}


# ── POST /run ─────────────────────────────────────────────────────────────────

@router.post("/run")
def trigger_pipeline(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    force: bool = Query(False, description="Recompute even if rows already exist"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """
    Trigger the fair value pipeline for a given date.
    Runs in the foreground (suitable for cron) and returns a summary.
    """
    if game_date:
        try:
            d = date.fromisoformat(game_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        d = date.today()

    outcome = run_pipeline(d, db, season=_current_season(d), force=force)
    return {
        "date":           d.isoformat(),
        "games_computed": outcome["games_computed"],
        "error":          outcome.get("error"),
        "results":        outcome["games"],
    }


# ── GET /debug/kalshi ─────────────────────────────────────────────────────────

@router.get("/debug/kalshi")
def debug_kalshi(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
):
    """Return raw Kalshi API response for debugging market line fetch."""
    from fair_value.mlb_api import get_kalshi_mlb_lines, KALSHI_BASE
    import requests as _requests
    d = date.fromisoformat(game_date) if game_date else date.today()
    lines = get_kalshi_mlb_lines(d)

    # Also return raw response for inspection
    try:
        resp = _requests.get(
            f"{KALSHI_BASE}/events",
            params={"status": "open", "series_ticker": "MLBM", "limit": 100},
            timeout=10,
        )
        raw = {"status_code": resp.status_code, "body": resp.json()}
    except Exception as e:
        raw = {"error": str(e)}

    return {"date": d.isoformat(), "parsed_lines": lines, "raw_response": raw}


# ── GET /live-odds ─────────────────────────────────────────────────────────────

@router.get("/live-odds")
def live_odds(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    db: Session = Depends(get_db),
):
    """
    Fetch current Kalshi moneyline prices and match them to today's games.
    Returns odds keyed by game_pk so the frontend can overlay them live.
    """
    from fair_value.mlb_api import get_kalshi_mlb_lines
    from fair_value.win_probability import prob_to_american
    from fair_value.constants import TEAM_ALIASES

    d = date.fromisoformat(game_date) if game_date else date.today()

    try:
        kalshi_lines = get_kalshi_mlb_lines(d)
    except Exception:
        kalshi_lines = []

    def _norm(t: str) -> str:
        t = (t or "").upper().strip()
        return TEAM_ALIASES.get(t, t)

    games = db.query(FairValueGame).filter(FairValueGame.game_date == d).all()

    result = []
    for game in games:
        home_key = _norm(game.home_team)
        away_key = _norm(game.away_team)
        for line in kalshi_lines:
            lh = _norm(line.get("home_team", ""))
            la = _norm(line.get("away_team", ""))
            if (lh == home_key and la == away_key) or (lh == away_key and la == home_key):
                hp = line.get("home_yes_price")
                ap = line.get("away_yes_price")
                if hp and ap:
                    total = float(hp) + float(ap)
                    home_prob = float(hp) / total
                    # flip if we matched on the away side
                    if lh != home_key:
                        home_prob = 1.0 - home_prob
                    away_prob = 1.0 - home_prob
                    result.append({
                        "game_pk":    game.game_pk,
                        "home_team":  game.home_team,
                        "away_team":  game.away_team,
                        "home_prob":  round(home_prob, 4),
                        "away_prob":  round(away_prob, 4),
                        "home_odds":  prob_to_american(home_prob),
                        "away_odds":  prob_to_american(away_prob),
                        "source":     "kalshi",
                    })
                break

    return {
        "date":  d.isoformat(),
        "lines": result,
        "kalshi_available": len(kalshi_lines) > 0,
    }


# ── POST /admin/backfill ──────────────────────────────────────────────────────

@router.post("/admin/backfill")
def backfill_calibration(
    days: int = Query(60, ge=1, le=365, description="Number of past days to backfill"),
    db: Session = Depends(get_db),
):
    """
    Seed the fair_value_calibration table from existing fair_value_games rows.
    Processes the last `days` days and re-fits Platt scaling coefficients.
    Safe to call multiple times (upserts).
    """
    # Import calibration helpers — they live in data_pipeline/ relative to project root,
    # but the logic is duplicated inline here to avoid path hacks in production.
    from sqlalchemy import text
    from models import FairValueCalibration
    from fair_value.calibration import fit_platt, load_coeffs, save_coeffs
    from fair_value.win_probability import american_to_prob

    today = date.today()
    total_written = 0
    dates_processed = []

    for offset in range(days, 0, -1):
        target = today - timedelta(days=offset)

        games = db.query(FairValueGame).filter(
            FairValueGame.game_date == target
        ).all()
        if not games:
            continue

        # Get outcomes from Statcast
        rows = db.execute(text("""
            SELECT game_pk,
                   MAX(post_home_score) AS final_home,
                   MAX(post_away_score) AS final_away
            FROM statcast_pitches
            WHERE game_date = :gd
              AND inning >= 9
            GROUP BY game_pk
        """), {"gd": target}).fetchall()

        outcomes = {}
        for r in rows:
            if r.final_home is None or r.final_away is None:
                continue
            if r.final_home == r.final_away:
                continue
            outcomes[int(r.game_pk)] = 1 if r.final_home > r.final_away else 0

        if not outcomes:
            continue

        written = 0
        for game in games:
            outcome = outcomes.get(game.game_pk)
            if outcome is None or game.home_win_prob is None:
                continue

            closing_home_prob = None
            if game.home_market_odds is not None and game.away_market_odds is not None:
                h = american_to_prob(game.home_market_odds)
                a = american_to_prob(game.away_market_odds)
                total = h + a
                closing_home_prob = h / total if total > 0 else None

            delta = None
            if closing_home_prob is not None:
                delta = round(game.home_win_prob - closing_home_prob, 4)

            model_brier  = round((game.home_win_prob - outcome) ** 2, 6)
            market_brier = (
                round((closing_home_prob - outcome) ** 2, 6)
                if closing_home_prob is not None else None
            )

            existing = db.query(FairValueCalibration).filter(
                FairValueCalibration.game_pk == game.game_pk
            ).first()

            if existing is None:
                cal = FairValueCalibration(game_pk=game.game_pk)
                db.add(cal)
            else:
                cal = existing

            cal.game_date         = game.game_date
            cal.home_team         = game.home_team
            cal.away_team         = game.away_team
            cal.model_home_prob   = game.home_win_prob
            cal.model_away_prob   = game.away_win_prob
            cal.closing_home_prob = closing_home_prob
            cal.closing_away_prob = (1.0 - closing_home_prob) if closing_home_prob else None
            cal.closing_source    = game.market_source
            cal.prob_delta        = delta
            cal.abs_delta         = abs(delta) if delta is not None else None
            cal.outcome_home_win  = outcome
            cal.model_brier       = model_brier
            cal.market_brier      = market_brier
            cal.home_lineup_woba  = game.home_lineup_woba
            cal.away_lineup_woba  = game.away_lineup_woba
            cal.total_lambda      = (game.home_lambda or 0) + (game.away_lambda or 0)

            written += 1

        db.commit()
        if written:
            dates_processed.append({"date": target.isoformat(), "rows": written})
            total_written += written

    # Re-fit Platt coefficients if we have enough data
    platt_updated = False
    platt_n = 0
    cal_rows = db.execute(text("""
        SELECT model_home_prob, outcome_home_win
        FROM fair_value_calibration
        WHERE outcome_home_win IN (0, 1) AND model_home_prob IS NOT NULL
        ORDER BY game_date
    """)).fetchall()

    if len(cal_rows) >= 30:
        raw_probs = [float(r.model_home_prob) for r in cal_rows]
        outcomes_list = [int(r.outcome_home_win) for r in cal_rows]
        A, B = fit_platt(raw_probs, outcomes_list)
        coeffs = load_coeffs()
        coeffs["platt_A"] = A
        coeffs["platt_B"] = B
        coeffs["n_games"] = len(raw_probs)
        coeffs["last_updated"] = str(today)
        save_coeffs(coeffs)
        platt_updated = True
        platt_n = len(raw_probs)

    return {
        "total_rows_written": total_written,
        "dates_processed": dates_processed,
        "platt_refit": platt_updated,
        "platt_n_games": platt_n,
        "message": (
            f"Backfill complete. {total_written} rows upserted across "
            f"{len(dates_processed)} dates. "
            + (f"Platt re-fit on {platt_n} games." if platt_updated
               else f"Platt NOT re-fit (need ≥30 rows, have {len(cal_rows)}).")
        ),
    }


# ── POST /admin/stuff-plus ────────────────────────────────────────────────────

@router.post("/admin/stuff-plus")
def run_stuff_plus(
    season: Optional[int] = Query(None, description="Season year; defaults to current year"),
    db: Session = Depends(get_db),
):
    """
    Train Stuff+ models for the given season and populate stuff_plus_scores.
    This is the manual trigger — it also runs nightly via the calibration cron.
    Training on a full season of Statcast data takes ~30–60 seconds.
    """
    from analytics.stuff_plus import compute_and_store
    s = season or date.today().year
    result = compute_and_store(db, s)
    return {"season": s, **result}
