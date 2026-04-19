"""
HR Fair Value API router.

Endpoints
─────────
GET  /api/hr-fair-value/games           ?date=YYYY-MM-DD
GET  /api/hr-fair-value/games/{game_pk}
POST /api/hr-fair-value/run             ?date=YYYY-MM-DD&force=true
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import HRFairValueGame, HRFairValuePlayer
from hr_fair_value.pipeline import run_hr_pipeline

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/hr-fair-value", tags=["hr-fair-value"])


# ── Serializers ──────────────────────────────────────────────────────────────

def _game_to_dict(row: HRFairValueGame) -> dict:
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    for k, v in d.items():
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
    return d


def _player_to_dict(row: HRFairValuePlayer) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


# ── GET /games ───────────────────────────────────────────────────────────────

@router.get("/games")
def list_games(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    db: Session = Depends(get_db),
):
    """Return all HR fair value games for a given date, with player-level detail."""
    if game_date:
        try:
            d = date.fromisoformat(game_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        d = date.today()

    rows = (
        db.query(HRFairValueGame)
        .filter(HRFairValueGame.game_date == d)
        .order_by(HRFairValueGame.game_time_utc.asc().nullslast())
        .all()
    )

    games = []
    for row in rows:
        game_dict = _game_to_dict(row)

        players = (
            db.query(HRFairValuePlayer)
            .filter(HRFairValuePlayer.game_pk == row.game_pk)
            .order_by(HRFairValuePlayer.is_home.desc(), HRFairValuePlayer.batting_order)
            .all()
        )
        game_dict["players"] = [_player_to_dict(p) for p in players]
        games.append(game_dict)

    return {"date": d.isoformat(), "games": games}


# ── GET /games/{game_pk} ─────────────────────────────────────────────��──────

@router.get("/games/{game_pk}")
def get_game(game_pk: int, db: Session = Depends(get_db)):
    """Return a single HR fair value game with player-level detail."""
    row = db.query(HRFairValueGame).filter(
        HRFairValueGame.game_pk == game_pk
    ).first()

    if not row:
        raise HTTPException(404, f"Game {game_pk} not found")

    game_dict = _game_to_dict(row)

    players = (
        db.query(HRFairValuePlayer)
        .filter(HRFairValuePlayer.game_pk == game_pk)
        .order_by(HRFairValuePlayer.is_home.desc(), HRFairValuePlayer.batting_order)
        .all()
    )
    game_dict["players"] = [_player_to_dict(p) for p in players]

    return game_dict


# ── POST /run ────────────────────────────────────────────────────────────────

@router.post("/run")
def trigger_pipeline(
    game_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    force: bool = Query(False, description="Force recompute"),
    db: Session = Depends(get_db),
):
    """Trigger the HR fair value pipeline for a given date."""
    if game_date:
        try:
            d = date.fromisoformat(game_date)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
    else:
        d = date.today()

    result = run_hr_pipeline(d, db, force=force)
    return result
