"""
Derives pitcher and batter projections from the Statcast data already in
the local database.  No external requests are made here.

Key functions
─────────────
pitcher_stats(db, pitcher_id, season)
    → season-long and last-N-start wOBA allowed, PA counts,
      pitches per inning

batter_stats(db, player_id, season, vs_hand)
    → season-long and last-N-game wOBA, PA counts

team_bullpen_stats(db, team, game_date, season)
    → weighted average wOBA allowed for relievers + fatigue-adjusted version

recent_lineup_for_team(db, team_id_or_abbr, season, sp_hand)
    → list of (player_id, player_name, batter_hand, batting_order,
               woba_vs_sp_hand, pa_weight)
      derived from recent Statcast game logs when confirmed lineup is missing
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .constants import (
    LEAGUE_AVG_WOBA,
    MIN_PA_SEASON,
    MIN_PA_RECENT,
    RECENT_N_STARTS,
    PA_WEIGHTS,
    FATIGUE_YESTERDAY,
    FATIGUE_TWO_DAYS_AGO,
)

log = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _regress(woba: Optional[float], pa: int, min_pa: int) -> float:
    """Regress woba toward league average proportionally when sample is small."""
    if woba is None or pa == 0:
        return LEAGUE_AVG_WOBA
    weight = min(pa, min_pa) / min_pa   # 0 → 1
    return woba * weight + LEAGUE_AVG_WOBA * (1 - weight)


def blend(season_woba: Optional[float], season_pa: int,
          recent_woba: Optional[float], recent_pa: int) -> float:
    """50/50 blend of season and recent wOBA, each regressed to mean."""
    s = _regress(season_woba, season_pa, MIN_PA_SEASON)
    r = _regress(recent_woba, recent_pa, MIN_PA_RECENT)
    return 0.5 * s + 0.5 * r


# ── Pitcher stats ─────────────────────────────────────────────────────────────

def pitcher_stats(db: Session, pitcher_id: int, season: int) -> dict:
    """
    Returns:
        woba_season, pa_season,
        woba_recent,  pa_recent,
        woba_blended,
        pitches_per_inning   (season average)
    """
    # --- season-long wOBA allowed -------------------------------------------
    row = db.execute(text("""
        SELECT
            SUM(woba_value)                         AS woba_num,
            SUM(woba_denom)                         AS pa,
            COUNT(*)                                AS pitches,
            COUNT(DISTINCT game_pk)                 AS starts
        FROM statcast_pitches
        WHERE pitcher      = :pid
          AND game_year    = :season
          AND woba_denom   > 0
    """), {"pid": pitcher_id, "season": season}).fetchone()

    season_pa     = int(row.pa or 0)
    season_woba   = float(row.woba_num / row.pa) if (row.pa and row.pa > 0) else None
    total_pitches = int(row.pitches or 0)
    total_starts  = int(row.starts or 0)

    # --- last N starts -------------------------------------------------------
    # Find the game_pks of the last RECENT_N_STARTS starts by this pitcher
    starts_row = db.execute(text("""
        SELECT game_pk
        FROM statcast_pitches
        WHERE pitcher   = :pid
          AND game_year = :season
        GROUP BY game_pk
        ORDER BY MAX(game_date) DESC
        LIMIT :n
    """), {"pid": pitcher_id, "season": season, "n": RECENT_N_STARTS}).fetchall()

    recent_game_pks = [r.game_pk for r in starts_row]

    recent_woba: Optional[float] = None
    recent_pa = 0

    if recent_game_pks:
        placeholders = ", ".join(str(pk) for pk in recent_game_pks)
        r2 = db.execute(text(f"""
            SELECT SUM(woba_value) AS woba_num, SUM(woba_denom) AS pa
            FROM statcast_pitches
            WHERE pitcher    = :pid
              AND game_pk IN ({placeholders})
              AND woba_denom > 0
        """), {"pid": pitcher_id}).fetchone()

        recent_pa   = int(r2.pa or 0)
        recent_woba = float(r2.woba_num / r2.pa) if (r2.pa and r2.pa > 0) else None

    # --- pitches per inning --------------------------------------------------
    # Estimate innings as max inning reached per start, averaged over starts
    ppi_row = db.execute(text("""
        SELECT
            COUNT(*) AS total_pitches,
            SUM(max_inn) AS total_innings
        FROM (
            SELECT game_pk, MAX(inning) AS max_inn
            FROM statcast_pitches
            WHERE pitcher   = :pid
              AND game_year = :season
            GROUP BY game_pk
        ) sub
    """), {"pid": pitcher_id, "season": season}).fetchone()

    if ppi_row.total_innings and ppi_row.total_innings > 0:
        pitches_per_inning = ppi_row.total_pitches / ppi_row.total_innings
    else:
        pitches_per_inning = 15.5   # league average fallback

    # Cap to a reasonable range
    pitches_per_inning = max(12.0, min(20.0, pitches_per_inning))

    return {
        "woba_season":        season_woba,
        "pa_season":          season_pa,
        "woba_recent":        recent_woba,
        "pa_recent":          recent_pa,
        "woba_blended":       blend(season_woba, season_pa, recent_woba, recent_pa),
        "pitches_per_inning": pitches_per_inning,
        "total_starts":       total_starts,
    }


# ── Batter stats ──────────────────────────────────────────────────────────────

def batter_stats(db: Session, player_id: int, season: int,
                 vs_hand: Optional[str] = None) -> dict:
    """
    Returns woba_season, pa_season, woba_recent, pa_recent, woba_blended
    all relative to *vs_hand* ('R' or 'L').  If vs_hand is None, uses
    overall splits.
    """
    hand_filter = "AND p_throws = :hand" if vs_hand else ""
    params_season = {"pid": player_id, "season": season}
    if vs_hand:
        params_season["hand"] = vs_hand

    row = db.execute(text(f"""
        SELECT SUM(woba_value) AS woba_num, SUM(woba_denom) AS pa
        FROM statcast_pitches
        WHERE batter       = :pid
          AND game_year    = :season
          AND woba_denom   > 0
          {hand_filter}
    """), params_season).fetchone()

    season_pa   = int(row.pa or 0)
    season_woba = float(row.woba_num / row.pa) if (row.pa and row.pa > 0) else None

    # --- last N games this batter appeared in --------------------------------
    games_row = db.execute(text("""
        SELECT game_pk
        FROM statcast_pitches
        WHERE batter     = :pid
          AND game_year  = :season
        GROUP BY game_pk
        ORDER BY MAX(game_date) DESC
        LIMIT :n
    """), {"pid": player_id, "season": season, "n": RECENT_N_STARTS}).fetchall()

    recent_woba: Optional[float] = None
    recent_pa = 0

    if games_row:
        pks = ", ".join(str(r.game_pk) for r in games_row)
        hand_f2 = "AND p_throws = :hand" if vs_hand else ""
        params_r = {"pid": player_id}
        if vs_hand:
            params_r["hand"] = vs_hand
        r2 = db.execute(text(f"""
            SELECT SUM(woba_value) AS woba_num, SUM(woba_denom) AS pa
            FROM statcast_pitches
            WHERE batter      = :pid
              AND game_pk IN ({pks})
              AND woba_denom  > 0
              {hand_f2}
        """), params_r).fetchone()

        recent_pa   = int(r2.pa or 0)
        recent_woba = float(r2.woba_num / r2.pa) if (r2.pa and r2.pa > 0) else None

    return {
        "woba_season":  season_woba,
        "pa_season":    season_pa,
        "woba_recent":  recent_woba,
        "pa_recent":    recent_pa,
        "woba_blended": blend(season_woba, season_pa, recent_woba, recent_pa),
    }


# ── Team lineup (projected from recent appearances) ───────────────────────────

def projected_lineup(db: Session, team: str, season: int,
                     sp_hand: Optional[str] = None) -> list[dict]:
    """
    Builds a projected 9-man lineup for *team* by finding the 9 batters who
    appeared most frequently in recent games (last 14 days of the season or
    last 15 game days), ordered by their median batting-order position.

    Returns list of 9 dicts (batting_order 1-9):
        player_id, player_name, batter_hand,
        batting_order, woba_vs_sp_hand, pa_weight
    """
    # Find the 9 most-used batters in recent games for this team
    rows = db.execute(text("""
        WITH recent_games AS (
            SELECT DISTINCT game_pk
            FROM statcast_pitches
            WHERE (home_team = :team OR away_team = :team)
              AND game_year  = :season
            ORDER BY game_pk DESC
            LIMIT 15
        ),
        batter_order AS (
            SELECT
                sp.batter                          AS player_id,
                MAX(sp.batter_name)                AS player_name,
                MAX(sp.stand)                      AS batter_hand,
                COUNT(DISTINCT sp.game_pk)         AS games_appeared,
                -- Approximate batting order: use the most common inning-1 at-bat order
                -- (not perfect, but reasonable for projected lineup)
                AVG(sp.at_bat_number)              AS avg_ab_num
            FROM statcast_pitches sp
            JOIN recent_games rg ON sp.game_pk = rg.game_pk
            WHERE (sp.home_team = :team OR sp.away_team = :team)
              AND sp.batter IS NOT NULL
              -- Only include at-bats where this player was batting FOR the team
              AND (
                  (sp.inning_topbot = 'Top'  AND sp.away_team = :team)
                  OR
                  (sp.inning_topbot = 'Bot'  AND sp.home_team = :team)
              )
            GROUP BY sp.batter
            ORDER BY games_appeared DESC, avg_ab_num ASC
            LIMIT 9
        )
        SELECT * FROM batter_order ORDER BY avg_ab_num
    """), {"team": team, "season": season}).fetchall()

    lineup = []
    for order, row in enumerate(rows[:9], start=1):
        stats = batter_stats(db, row.player_id, season, vs_hand=sp_hand)
        lineup.append({
            "player_id":     row.player_id,
            "player_name":   row.player_name or "",
            "batter_hand":   row.batter_hand or "R",
            "batting_order": order,
            "woba_vs_sp_hand": stats["woba_blended"],
            "woba_season":   stats["woba_season"],
            "woba_recent":   stats["woba_recent"],
            "woba_blended":  stats["woba_blended"],
            "pa_weight":     PA_WEIGHTS[order - 1],
        })

    # Pad to 9 with league-average placeholders if fewer batters found
    while len(lineup) < 9:
        order = len(lineup) + 1
        lineup.append({
            "player_id":      None,
            "player_name":    "Unknown",
            "batter_hand":    "R",
            "batting_order":  order,
            "woba_vs_sp_hand": LEAGUE_AVG_WOBA,
            "woba_season":    LEAGUE_AVG_WOBA,
            "woba_recent":    LEAGUE_AVG_WOBA,
            "woba_blended":   LEAGUE_AVG_WOBA,
            "pa_weight":      PA_WEIGHTS[order - 1],
        })

    return lineup


def lineup_weighted_woba(slots: list[dict]) -> float:
    """Weighted average wOBA across 9 lineup slots, weighted by PA weight."""
    total_w = sum(s["pa_weight"] for s in slots)
    if total_w == 0:
        return LEAGUE_AVG_WOBA
    return sum(s["woba_vs_sp_hand"] * s["pa_weight"] for s in slots) / total_w


# ── Bullpen stats ─────────────────────────────────────────────────────────────

def team_bullpen_stats(db: Session, team: str, game_date: date,
                       season: int) -> dict:
    """
    Computes:
        woba_raw       – season+recent blended wOBA allowed by bullpen
        woba_fatigued  – woba_raw adjusted for recent appearances

    Strategy:
    1. Find all pitchers who have relieved for *team* this season (appeared
       in multiple games, not always as the first pitcher).
    2. Blend their wOBA allowed (season vs recent, 50/50).
    3. Identify who pitched in the last 1 or 2 days and apply fatigue penalty.
    4. Weighted average by usage share (IP-based).
    """
    # Identify bullpen pitchers: pitchers who started at inning > 1 in at
    # least one appearance (or appeared in 3+ games as non-openers).
    bp_rows = db.execute(text("""
        WITH appearances AS (
            SELECT
                pitcher,
                MAX(player_name)   AS pitcher_name,
                game_pk,
                MIN(inning)        AS first_inning,
                COUNT(*)           AS pitches
            FROM statcast_pitches
            WHERE (home_team = :team OR away_team = :team)
              AND game_year  = :season
              AND (
                  (inning_topbot = 'Top'  AND away_team = :team)
                  OR
                  (inning_topbot = 'Bot'  AND home_team = :team)
              )
            GROUP BY pitcher, game_pk
        )
        SELECT
            pitcher,
            MAX(pitcher_name)            AS pitcher_name,
            COUNT(DISTINCT game_pk)      AS appearances,
            SUM(pitches)                 AS total_pitches,
            AVG(first_inning)            AS avg_entry_inning
        FROM appearances
        GROUP BY pitcher
        HAVING AVG(first_inning) > 1.5   -- reliever heuristic
           AND COUNT(DISTINCT game_pk) >= 3
        ORDER BY total_pitches DESC
        LIMIT 12
    """), {"team": team, "season": season}).fetchall()

    if not bp_rows:
        return {
            "woba_raw":      LEAGUE_AVG_WOBA,
            "woba_fatigued": LEAGUE_AVG_WOBA,
        }

    # Compute recent appearances for fatigue
    yesterday = game_date - timedelta(days=1)
    two_ago   = game_date - timedelta(days=2)

    fatigued_ids_yesterday: set[int] = set()
    fatigued_ids_two_ago:   set[int] = set()

    for bp in bp_rows:
        # Check if this pitcher appeared in the last 1 or 2 days
        recent = db.execute(text("""
            SELECT DISTINCT game_date
            FROM statcast_pitches
            WHERE pitcher  = :pid
              AND game_date IN (:y, :t)
        """), {"pid": bp.pitcher, "y": yesterday, "t": two_ago}).fetchall()

        dates_appeared = {r.game_date for r in recent}
        if yesterday in dates_appeared:
            fatigued_ids_yesterday.add(bp.pitcher)
        elif two_ago in dates_appeared:
            fatigued_ids_two_ago.add(bp.pitcher)

    # Compute blended wOBA for each reliever
    reliever_stats = []
    for bp in bp_rows:
        s = pitcher_stats(db, bp.pitcher, season)
        reliever_stats.append({
            "pitcher_id":    bp.pitcher,
            "pitcher_name":  bp.pitcher_name,
            "usage_weight":  bp.total_pitches,   # IP proxy
            "woba_blended":  s["woba_blended"],
        })

    total_weight = sum(r["usage_weight"] for r in reliever_stats) or 1

    woba_raw = sum(
        r["woba_blended"] * r["usage_weight"]
        for r in reliever_stats
    ) / total_weight

    # Apply fatigue: penalise the TEAM's average by the fraction of bullpen
    # that is fatigued × the penalty constant
    n_relievers = len(reliever_stats)
    fatigue_delta = (
        len(fatigued_ids_yesterday) / n_relievers * FATIGUE_YESTERDAY
        + len(fatigued_ids_two_ago)  / n_relievers * FATIGUE_TWO_DAYS_AGO
    )

    return {
        "woba_raw":              woba_raw,
        "woba_fatigued":         min(woba_raw + fatigue_delta, 0.420),
        "fatigued_yesterday":    len(fatigued_ids_yesterday),
        "fatigued_two_days_ago": len(fatigued_ids_two_ago),
        "n_relievers":           n_relievers,
    }
