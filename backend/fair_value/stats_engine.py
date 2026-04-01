"""
Derives pitcher and batter projections from the Statcast database.

All queries are CROSS-SEASON — no game_year filter.  Samples are capped to
the last N game appearances so early-season numbers reflect a full year of
prior history rather than a handful of April games.

Sample windows
──────────────
  Pitchers  : last PITCHER_SAMPLE_STARTS (40) starts for the full sample,
              last RECENT_N_STARTS (5) starts for the recent half of 50/50 blend
  Batters   : last BATTER_SAMPLE_GAMES (200) game appearances for full sample,
              last RECENT_N_BATTER_GAMES (15) for the recent half
  Bullpen   : relievers evaluated over last BULLPEN_SAMPLE_GAMES (40) team games

Lineup approach
───────────────
Every batter in the projected/confirmed lineup gets their own individual
wOBA computed from their personal Statcast history (vs. the opposing SP's
handedness), then those 9 values are aggregated into a single lineup wOBA
weighted by batting-order PA exposure.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .constants import (
    LEAGUE_AVG_WOBA,
    PA_WEIGHTS,
    PITCHER_SAMPLE_STARTS,
    RECENT_N_STARTS,
    BATTER_SAMPLE_GAMES,
    RECENT_N_BATTER_GAMES,
    BULLPEN_SAMPLE_GAMES,
    MIN_PA_PITCHER_FULL,
    MIN_PA_PITCHER_RECENT,
    MIN_PA_BATTER_FULL,
    MIN_PA_BATTER_RECENT,
    FATIGUE_YESTERDAY,
    FATIGUE_TWO_DAYS_AGO,
)

log = logging.getLogger(__name__)


# ── Regression helper ─────────────────────────────────────────────────────────

def _regress(woba: Optional[float], pa: int, min_pa: int) -> float:
    """Regress woba toward league average when the sample is small."""
    if woba is None or pa == 0:
        return LEAGUE_AVG_WOBA
    weight = min(pa, min_pa) / min_pa   # 0 → 1
    return woba * weight + LEAGUE_AVG_WOBA * (1.0 - weight)


def _blend(full_woba: Optional[float], full_pa: int,
           recent_woba: Optional[float], recent_pa: int,
           min_full: int, min_recent: int) -> float:
    """50/50 blend of full-sample and recent-sample wOBA, each regressed."""
    f = _regress(full_woba,   full_pa,   min_full)
    r = _regress(recent_woba, recent_pa, min_recent)
    return 0.5 * f + 0.5 * r


# ── Pitcher stats ─────────────────────────────────────────────────────────────

def pitcher_stats(db: Session, pitcher_id: int) -> dict:
    """
    Cross-season pitcher projection using:
      - Full sample  : last PITCHER_SAMPLE_STARTS (40) starts
      - Recent sample: last RECENT_N_STARTS (5) starts
      - 50/50 blend of both, each regressed toward league avg

    Returns:
        woba_full, pa_full,
        woba_recent, pa_recent,
        woba_blended,
        pitches_per_inning
    """
    # ── Find last N start game_pks (cross-season) ─────────────────────────────
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
            "woba_full":          None, "pa_full":    0,
            "woba_recent":        None, "pa_recent":  0,
            "woba_blended":       LEAGUE_AVG_WOBA,
            "pitches_per_inning": 15.5,
            "total_starts":       0,
        }

    pk_list = ", ".join(str(pk) for pk in full_pks)

    # ── Full-sample wOBA allowed ──────────────────────────────────────────────
    full_row = db.execute(text(f"""
        SELECT SUM(woba_value) AS woba_num,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE pitcher    = :pid
          AND game_pk IN ({pk_list})
          AND woba_denom > 0
    """), {"pid": pitcher_id}).fetchone()

    full_pa   = int(full_row.pa or 0)
    full_woba = float(full_row.woba_num / full_row.pa) \
                if (full_row.pa and full_row.pa > 0) else None

    # ── Recent-sample wOBA allowed (last RECENT_N_STARTS) ────────────────────
    recent_pks = full_pks[:RECENT_N_STARTS]
    recent_pk_list = ", ".join(str(pk) for pk in recent_pks)

    recent_row = db.execute(text(f"""
        SELECT SUM(woba_value) AS woba_num,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE pitcher    = :pid
          AND game_pk IN ({recent_pk_list})
          AND woba_denom > 0
    """), {"pid": pitcher_id}).fetchone()

    recent_pa   = int(recent_row.pa or 0)
    recent_woba = float(recent_row.woba_num / recent_row.pa) \
                  if (recent_row.pa and recent_row.pa > 0) else None

    # ── Pitches per inning (full sample) ─────────────────────────────────────
    ppi_row = db.execute(text(f"""
        SELECT COUNT(*)        AS total_pitches,
               SUM(max_inn)    AS total_innings
        FROM (
            SELECT game_pk, MAX(inning) AS max_inn
            FROM statcast_pitches
            WHERE pitcher = :pid
              AND game_pk IN ({pk_list})
            GROUP BY game_pk
        ) sub
    """), {"pid": pitcher_id}).fetchone()

    if ppi_row.total_innings and ppi_row.total_innings > 0:
        ppi = ppi_row.total_pitches / ppi_row.total_innings
    else:
        ppi = 15.5
    ppi = max(12.0, min(20.0, ppi))

    return {
        "woba_full":          full_woba,
        "pa_full":            full_pa,
        "woba_recent":        recent_woba,
        "pa_recent":          recent_pa,
        "woba_blended":       _blend(full_woba, full_pa,
                                     recent_woba, recent_pa,
                                     MIN_PA_PITCHER_FULL,
                                     MIN_PA_PITCHER_RECENT),
        "pitches_per_inning": round(ppi, 2),
        "total_starts":       len(full_pks),
    }


# ── Batter stats ──────────────────────────────────────────────────────────────

def batter_stats(db: Session, player_id: int,
                 vs_hand: Optional[str] = None) -> dict:
    """
    Cross-season batter projection using:
      - Full sample  : last BATTER_SAMPLE_GAMES (200) game appearances
      - Recent sample: last RECENT_N_BATTER_GAMES (15) game appearances
      - wOBA split vs the opposing SP's handedness (vs_hand = 'R' or 'L')

    Returns:
        woba_full, pa_full,
        woba_recent, pa_recent,
        woba_blended
    """
    hand_clause = "AND p_throws = :hand" if vs_hand else ""

    # ── Find last N game_pks for this batter ──────────────────────────────────
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
            "woba_full":    None, "pa_full":   0,
            "woba_recent":  None, "pa_recent": 0,
            "woba_blended": LEAGUE_AVG_WOBA,
        }

    pk_list = ", ".join(str(pk) for pk in full_pks)

    base_params: dict = {"pid": player_id}
    if vs_hand:
        base_params["hand"] = vs_hand

    # ── Full-sample wOBA ──────────────────────────────────────────────────────
    full_row = db.execute(text(f"""
        SELECT SUM(woba_value) AS woba_num,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE batter      = :pid
          AND game_pk  IN ({pk_list})
          AND woba_denom  > 0
          {hand_clause}
    """), base_params).fetchone()

    full_pa   = int(full_row.pa or 0)
    full_woba = float(full_row.woba_num / full_row.pa) \
                if (full_row.pa and full_row.pa > 0) else None

    # ── Recent-sample wOBA ────────────────────────────────────────────────────
    recent_pks    = full_pks[:RECENT_N_BATTER_GAMES]
    recent_pk_list = ", ".join(str(pk) for pk in recent_pks)

    recent_row = db.execute(text(f"""
        SELECT SUM(woba_value) AS woba_num,
               SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE batter      = :pid
          AND game_pk  IN ({recent_pk_list})
          AND woba_denom  > 0
          {hand_clause}
    """), base_params).fetchone()

    recent_pa   = int(recent_row.pa or 0)
    recent_woba = float(recent_row.woba_num / recent_row.pa) \
                  if (recent_row.pa and recent_row.pa > 0) else None

    return {
        "woba_full":    full_woba,
        "pa_full":      full_pa,
        "woba_recent":  recent_woba,
        "pa_recent":    recent_pa,
        "woba_blended": _blend(full_woba, full_pa,
                               recent_woba, recent_pa,
                               MIN_PA_BATTER_FULL,
                               MIN_PA_BATTER_RECENT),
    }


# ── Projected lineup ──────────────────────────────────────────────────────────

def projected_lineup(db: Session, team: str,
                     sp_hand: Optional[str] = None) -> list[dict]:
    """
    Build a projected 9-man lineup for *team*.

    Strategy:
      1. Find the last BULLPEN_SAMPLE_GAMES (40) team game_pks.
      2. Within those games identify the 9 batters who appeared most often
         batting FOR this team, ordered by their median at-bat sequence.
      3. For each batter call batter_stats() with vs_hand=sp_hand to get
         their individual cross-season wOBA split.
      4. Weight by batting-order PA exposure.

    Returns list of 9 slot dicts.
    """
    # Last 40 game_pks this team appeared in
    team_games_rows = db.execute(text("""
        SELECT DISTINCT game_pk
        FROM statcast_pitches
        WHERE home_team = :team OR away_team = :team
        ORDER BY game_pk DESC
        LIMIT :n
    """), {"team": team, "n": BULLPEN_SAMPLE_GAMES}).fetchall()

    team_game_pks = [r.game_pk for r in team_games_rows]

    if not team_game_pks:
        return _league_avg_lineup(sp_hand)

    pk_list = ", ".join(str(pk) for pk in team_game_pks)

    # Find the 9 most-used batters hitting FOR this team in those games.
    # "Batting for the team" means: top-half inning when away_team=team,
    # or bottom-half inning when home_team=team.
    rows = db.execute(text(f"""
        SELECT
            batter                          AS player_id,
            MAX(batter_name)                AS player_name,
            MAX(stand)                      AS batter_hand,
            COUNT(DISTINCT game_pk)         AS games_appeared,
            AVG(at_bat_number)              AS avg_ab_num
        FROM statcast_pitches
        WHERE game_pk IN ({pk_list})
          AND batter IS NOT NULL
          AND (
              (inning_topbot = 'Top' AND away_team = :team)
              OR
              (inning_topbot = 'Bot' AND home_team = :team)
          )
        GROUP BY batter
        ORDER BY games_appeared DESC, avg_ab_num ASC
        LIMIT 9
    """), {"team": team}).fetchall()

    if not rows:
        return _league_avg_lineup(sp_hand)

    # Sort by avg_ab_num so order 1 is the typical leadoff hitter
    sorted_rows = sorted(rows, key=lambda r: r.avg_ab_num)

    slots = []
    for order, row in enumerate(sorted_rows[:9], start=1):
        stats = batter_stats(db, row.player_id, vs_hand=sp_hand)
        slots.append({
            "player_id":       row.player_id,
            "player_name":     row.player_name or "",
            "batter_hand":     row.batter_hand or "R",
            "batting_order":   order,
            "woba_vs_sp_hand": stats["woba_blended"],
            "woba_full":       stats["woba_full"],
            "woba_recent":     stats["woba_recent"],
            "woba_blended":    stats["woba_blended"],
            "pa_weight":       PA_WEIGHTS[order - 1],
        })

    # Pad to 9 with league-average placeholders if needed
    while len(slots) < 9:
        order = len(slots) + 1
        slots.append(_avg_slot(order))

    return slots


def _avg_slot(order: int) -> dict:
    return {
        "player_id":       None,
        "player_name":     "Unknown",
        "batter_hand":     "R",
        "batting_order":   order,
        "woba_vs_sp_hand": LEAGUE_AVG_WOBA,
        "woba_full":       LEAGUE_AVG_WOBA,
        "woba_recent":     LEAGUE_AVG_WOBA,
        "woba_blended":    LEAGUE_AVG_WOBA,
        "pa_weight":       PA_WEIGHTS[order - 1],
    }


def _league_avg_lineup(sp_hand: Optional[str]) -> list[dict]:
    return [_avg_slot(i) for i in range(1, 10)]


def lineup_weighted_woba(slots: list[dict]) -> float:
    """Weighted average wOBA across lineup slots by PA weight."""
    total_w = sum(s["pa_weight"] for s in slots)
    if total_w == 0:
        return LEAGUE_AVG_WOBA
    return sum(s["woba_vs_sp_hand"] * s["pa_weight"] for s in slots) / total_w


# ── Bullpen stats ─────────────────────────────────────────────────────────────

def team_bullpen_stats(db: Session, team: str, game_date: date) -> dict:
    """
    Compute bullpen quality for *team* entering *game_date*.

    1. Find last BULLPEN_SAMPLE_GAMES (40) team game_pks before game_date.
    2. Identify relievers (avg entry inning > 1.5, 3+ appearances).
    3. Compute each reliever's individual wOBA allowed (cross-season, last 40 starts).
    4. Weight by usage (pitch count) → team bullpen wOBA.
    5. Apply fatigue penalties for pitchers who appeared yesterday / two days ago.
    """
    yesterday = game_date - timedelta(days=1)
    two_ago   = game_date - timedelta(days=2)

    # Team game_pks strictly before game_date
    team_games_rows = db.execute(text("""
        SELECT DISTINCT game_pk
        FROM statcast_pitches
        WHERE (home_team = :team OR away_team = :team)
          AND game_date  < :gd
        ORDER BY game_pk DESC
        LIMIT :n
    """), {"team": team, "gd": game_date, "n": BULLPEN_SAMPLE_GAMES}).fetchall()

    team_game_pks = [r.game_pk for r in team_games_rows]

    if not team_game_pks:
        return {"woba_raw": LEAGUE_AVG_WOBA, "woba_fatigued": LEAGUE_AVG_WOBA}

    pk_list = ", ".join(str(pk) for pk in team_game_pks)

    # Identify relievers: pitched FOR this team, avg entry inning > 1.5
    bp_rows = db.execute(text(f"""
        SELECT
            pitcher,
            MAX(player_name)            AS pitcher_name,
            COUNT(DISTINCT game_pk)     AS appearances,
            SUM(pitch_count)            AS total_pitches,
            AVG(first_inning)           AS avg_entry_inning
        FROM (
            SELECT pitcher, player_name, game_pk,
                   COUNT(*)    AS pitch_count,
                   MIN(inning) AS first_inning
            FROM statcast_pitches
            WHERE game_pk IN ({pk_list})
              AND (
                  (inning_topbot = 'Top' AND away_team = :team)
                  OR
                  (inning_topbot = 'Bot' AND home_team = :team)
              )
            GROUP BY pitcher, player_name, game_pk
        ) app
        GROUP BY pitcher
        HAVING AVG(first_inning) > 1.5
           AND COUNT(DISTINCT game_pk) >= 3
        ORDER BY total_pitches DESC
        LIMIT 12
    """), {"team": team}).fetchall()

    if not bp_rows:
        return {"woba_raw": LEAGUE_AVG_WOBA, "woba_fatigued": LEAGUE_AVG_WOBA}

    # Check fatigue for each reliever
    fatigued_yesterday: set[int] = set()
    fatigued_two_ago:   set[int] = set()

    for bp in bp_rows:
        recent = db.execute(text("""
            SELECT DISTINCT game_date
            FROM statcast_pitches
            WHERE pitcher   = :pid
              AND game_date IN (:y, :t)
        """), {"pid": bp.pitcher, "y": yesterday, "t": two_ago}).fetchall()

        appeared = {r.game_date for r in recent}
        if yesterday in appeared:
            fatigued_yesterday.add(bp.pitcher)
        elif two_ago in appeared:
            fatigued_two_ago.add(bp.pitcher)

    # Per-reliever blended wOBA (using their own cross-season last-40-start data)
    reliever_stats = []
    for bp in bp_rows:
        s = pitcher_stats(db, bp.pitcher)
        reliever_stats.append({
            "pitcher_id":   bp.pitcher,
            "usage_weight": float(bp.total_pitches or 1),
            "woba_blended": s["woba_blended"],
        })

    total_weight = sum(r["usage_weight"] for r in reliever_stats) or 1.0
    woba_raw = sum(r["woba_blended"] * r["usage_weight"]
                   for r in reliever_stats) / total_weight

    n = len(reliever_stats)
    fatigue_delta = (
        len(fatigued_yesterday) / n * FATIGUE_YESTERDAY
        + len(fatigued_two_ago)  / n * FATIGUE_TWO_DAYS_AGO
    )

    return {
        "woba_raw":              round(woba_raw, 4),
        "woba_fatigued":         round(min(woba_raw + fatigue_delta, 0.420), 4),
        "fatigued_yesterday":    len(fatigued_yesterday),
        "fatigued_two_days_ago": len(fatigued_two_ago),
        "n_relievers":           n,
    }
