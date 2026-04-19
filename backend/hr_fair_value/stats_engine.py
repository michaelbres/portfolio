"""
HR-specific stats derived from the Statcast database.

All queries are CROSS-SEASON (no game_year filter) to ensure meaningful
samples even at the start of a new season. Mirrors the pattern from
fair_value.stats_engine but focuses on HR/PA rates.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .constants import (
    LEAGUE_AVG_HR_PER_PA,
    BATTER_SAMPLE_GAMES,
    RECENT_N_BATTER_GAMES,
    PITCHER_SAMPLE_STARTS,
    RECENT_N_STARTS,
    MIN_PA_BATTER_HR_FULL,
    MIN_PA_BATTER_HR_RECENT,
    MIN_PA_PITCHER_HR_FULL,
    MIN_PA_PITCHER_HR_RECENT,
)

log = logging.getLogger(__name__)


# ── Regression helpers ────────────────────────────────────────────────────────

def _regress_hr(hr_rate: Optional[float], pa: int, min_pa: int) -> float:
    """Regress HR/PA rate toward league average when sample is small."""
    if hr_rate is None or pa == 0:
        return LEAGUE_AVG_HR_PER_PA
    weight = min(pa, min_pa) / min_pa
    return hr_rate * weight + LEAGUE_AVG_HR_PER_PA * (1.0 - weight)


def _blend_hr(full_rate: Optional[float], full_pa: int,
              recent_rate: Optional[float], recent_pa: int,
              min_full: int, min_recent: int) -> float:
    """50/50 blend of full-sample and recent-sample HR/PA rate, each regressed."""
    f = _regress_hr(full_rate, full_pa, min_full)
    r = _regress_hr(recent_rate, recent_pa, min_recent)
    return 0.5 * f + 0.5 * r


# ── Batter HR stats ──────────────────────────────────────────────────────────

def batter_hr_stats(db: Session, player_id: int,
                    vs_hand: Optional[str] = None) -> dict:
    """
    Cross-season batter HR rate using:
      - Full sample  : last BATTER_SAMPLE_GAMES (200) game appearances
      - Recent sample: last RECENT_N_BATTER_GAMES (15) game appearances
      - Optionally split by opposing pitcher hand (vs_hand = 'R' or 'L')

    Returns:
        hr_rate_full, pa_full, hr_full,
        hr_rate_recent, pa_recent, hr_recent,
        hr_rate_blended
    """
    hand_clause = "AND p_throws = :hand" if vs_hand else ""

    # Find last N game_pks for this batter
    full_pks_rows = db.execute(text("""
        SELECT game_pk
        FROM statcast_pitches
        WHERE batter = :pid
        GROUP BY game_pk
        ORDER BY MAX(game_date) DESC
        LIMIT :n
    """), {"pid": player_id, "n": BATTER_SAMPLE_GAMES}).fetchall()

    full_pks = [r.game_pk for r in full_pks_rows]

    if not full_pks:
        return {
            "hr_rate_full": None, "pa_full": 0, "hr_full": 0,
            "hr_rate_recent": None, "pa_recent": 0, "hr_recent": 0,
            "hr_rate_blended": LEAGUE_AVG_HR_PER_PA,
        }

    pk_list = ", ".join(str(pk) for pk in full_pks)

    base_params: dict = {"pid": player_id}
    if vs_hand:
        base_params["hand"] = vs_hand

    # Full-sample HR rate
    full_row = db.execute(text(f"""
        SELECT COUNT(CASE WHEN events = 'home_run' THEN 1 END) AS hr_count,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE batter = :pid
          AND game_pk IN ({pk_list})
          AND woba_denom > 0
          {hand_clause}
    """), base_params).fetchone()

    full_pa = int(full_row.pa or 0)
    full_hr = int(full_row.hr_count or 0)
    full_rate = full_hr / full_pa if full_pa > 0 else None

    # Recent-sample HR rate
    recent_pks = full_pks[:RECENT_N_BATTER_GAMES]
    recent_pk_list = ", ".join(str(pk) for pk in recent_pks)

    recent_row = db.execute(text(f"""
        SELECT COUNT(CASE WHEN events = 'home_run' THEN 1 END) AS hr_count,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE batter = :pid
          AND game_pk IN ({recent_pk_list})
          AND woba_denom > 0
          {hand_clause}
    """), base_params).fetchone()

    recent_pa = int(recent_row.pa or 0)
    recent_hr = int(recent_row.hr_count or 0)
    recent_rate = recent_hr / recent_pa if recent_pa > 0 else None

    return {
        "hr_rate_full":    full_rate,
        "pa_full":         full_pa,
        "hr_full":         full_hr,
        "hr_rate_recent":  recent_rate,
        "pa_recent":       recent_pa,
        "hr_recent":       recent_hr,
        "hr_rate_blended": round(_blend_hr(
            full_rate, full_pa,
            recent_rate, recent_pa,
            MIN_PA_BATTER_HR_FULL,
            MIN_PA_BATTER_HR_RECENT,
        ), 5),
    }


# ── Pitcher HR-allowed stats ─────────────────────────────────────────────────

def pitcher_hr_allowed_stats(db: Session, pitcher_id: int) -> dict:
    """
    Cross-season pitcher HR-allowed rate:
      - Full sample  : last PITCHER_SAMPLE_STARTS (40) starts
      - Recent sample: last RECENT_N_STARTS (5) starts
      - 50/50 blend, each regressed toward league avg

    Returns:
        hr_rate_full, pa_full, hr_full,
        hr_rate_recent, pa_recent, hr_recent,
        hr_rate_blended,
        hr_factor (pitcher rate / league avg — multiplier for batter HR rates)
    """
    full_pks_rows = db.execute(text("""
        SELECT game_pk
        FROM statcast_pitches
        WHERE pitcher = :pid
        GROUP BY game_pk
        ORDER BY MAX(game_date) DESC
        LIMIT :n
    """), {"pid": pitcher_id, "n": PITCHER_SAMPLE_STARTS}).fetchall()

    full_pks = [r.game_pk for r in full_pks_rows]

    if not full_pks:
        return {
            "hr_rate_full": None, "pa_full": 0, "hr_full": 0,
            "hr_rate_recent": None, "pa_recent": 0, "hr_recent": 0,
            "hr_rate_blended": LEAGUE_AVG_HR_PER_PA,
            "hr_factor": 1.0,
        }

    pk_list = ", ".join(str(pk) for pk in full_pks)

    # Full-sample HR-allowed rate
    full_row = db.execute(text(f"""
        SELECT COUNT(CASE WHEN events = 'home_run' THEN 1 END) AS hr_count,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE pitcher = :pid
          AND game_pk IN ({pk_list})
          AND woba_denom > 0
    """), {"pid": pitcher_id}).fetchone()

    full_pa = int(full_row.pa or 0)
    full_hr = int(full_row.hr_count or 0)
    full_rate = full_hr / full_pa if full_pa > 0 else None

    # Recent-sample
    recent_pks = full_pks[:RECENT_N_STARTS]
    recent_pk_list = ", ".join(str(pk) for pk in recent_pks)

    recent_row = db.execute(text(f"""
        SELECT COUNT(CASE WHEN events = 'home_run' THEN 1 END) AS hr_count,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE pitcher = :pid
          AND game_pk IN ({recent_pk_list})
          AND woba_denom > 0
    """), {"pid": pitcher_id}).fetchone()

    recent_pa = int(recent_row.pa or 0)
    recent_hr = int(recent_row.hr_count or 0)
    recent_rate = recent_hr / recent_pa if recent_pa > 0 else None

    blended = _blend_hr(
        full_rate, full_pa,
        recent_rate, recent_pa,
        MIN_PA_PITCHER_HR_FULL,
        MIN_PA_PITCHER_HR_RECENT,
    )

    return {
        "hr_rate_full":    full_rate,
        "pa_full":         full_pa,
        "hr_full":         full_hr,
        "hr_rate_recent":  recent_rate,
        "pa_recent":       recent_pa,
        "hr_recent":       recent_hr,
        "hr_rate_blended": round(blended, 5),
        "hr_factor":       round(blended / LEAGUE_AVG_HR_PER_PA, 3),
    }
