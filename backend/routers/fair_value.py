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
from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import FairValueGame, FairValueLineupSlot
from fair_value.pipeline import run_pipeline, recalculate_game, _row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fair-value", tags=["fair-value"])

CURRENT_SEASON = 2025


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

    updated = recalculate_game(db, game_pk, season=CURRENT_SEASON)
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

    updated = recalculate_game(db, game_pk, season=CURRENT_SEASON)
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

    results = run_pipeline(d, db, season=CURRENT_SEASON, force=force)
    return {"date": d.isoformat(), "games_computed": len(results), "results": results}
