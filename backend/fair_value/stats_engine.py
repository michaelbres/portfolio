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
import math
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
    MIN_IP_PITCHER_FULL,
    MIN_IP_PITCHER_RECENT,
    MIN_PA_BATTER_FULL,
    MIN_PA_BATTER_RECENT,
    FATIGUE_PER_PITCH_24H,
    FATIGUE_PER_PITCH_48H,
    FATIGUE_PER_PITCH_72H,
    CFIP,
    LG_HR_PER_FB,
    LEAGUE_AVG_XFIP,
    HOME_LAMBDA_FACTOR,
    DEFENSE_FACTOR_FLOOR,
    DEFENSE_FACTOR_CAP,
    MIN_BIP_DEFENSE,
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


def _regress_xfip(xfip: Optional[float], ip: float, min_ip: float) -> float:
    """Regress xFIP toward league average when innings sample is small."""
    if xfip is None or ip <= 0:
        return LEAGUE_AVG_XFIP
    weight = min(ip, min_ip) / min_ip
    return xfip * weight + LEAGUE_AVG_XFIP * (1.0 - weight)


def _blend_xfip(full_xfip: Optional[float], full_ip: float,
                recent_xfip: Optional[float], recent_ip: float) -> float:
    """50/50 blend of full and recent xFIP, each regressed by IP."""
    f = _regress_xfip(full_xfip,   full_ip,   MIN_IP_PITCHER_FULL)
    r = _regress_xfip(recent_xfip, recent_ip, MIN_IP_PITCHER_RECENT)
    return 0.5 * f + 0.5 * r


# ── xFIP computation ──────────────────────────────────────────────────────────

def _xfip_from_api_stats(stats: dict) -> Optional[float]:
    """Compute xFIP from MLB Stats API season counting stats."""
    ip = stats.get("ip", 0)
    if ip < 1.0:
        return None
    k, bb, hbp, fb = stats["k"], stats["bb"], stats["hbp"], stats["fb"]
    raw = ((13.0 * fb * LG_HR_PER_FB) + (3.0 * (bb + hbp)) - (2.0 * k)) / ip + CFIP
    return max(1.50, min(8.00, round(raw, 3)))


def _compute_xfip(db: Session, pitcher_id: int,
                  game_pks: list[int]) -> dict:
    """
    Compute xFIP for *pitcher_id* over the given *game_pks*.

    xFIP = ((13 × FB × lgHR/FB) + (3 × (BB + HBP)) - (2 × K)) / IP + cFIP

    IP is estimated as the sum of MAX(inning) pitched per game (a reasonable
    proxy that matches the existing pitches-per-inning calculation).

    Returns dict with keys: xfip, ip, k, bb, hbp, fb.
    """
    if not game_pks:
        return {"xfip": None, "ip": 0.0, "k": 0, "bb": 0, "hbp": 0, "fb": 0}

    pk_list = ", ".join(str(pk) for pk in game_pks)

    # K, BB, HBP, FB from last-pitch-of-PA rows (events IS NOT NULL)
    row = db.execute(text(f"""
        SELECT
            SUM(CASE WHEN events IN ('strikeout', 'strikeout_double_play')
                     THEN 1 ELSE 0 END)                    AS k,
            SUM(CASE WHEN events = 'walk'                  THEN 1 ELSE 0 END) AS bb,
            SUM(CASE WHEN events = 'hit_by_pitch'          THEN 1 ELSE 0 END) AS hbp,
            SUM(CASE WHEN bb_type IN ('fly_ball', 'popup') THEN 1 ELSE 0 END) AS fb
        FROM statcast_pitches
        WHERE pitcher  = :pid
          AND game_pk IN ({pk_list})
          AND events  IS NOT NULL
    """), {"pid": pitcher_id}).fetchone()

    # IP proxy: sum of max inning pitched per start
    ip_row = db.execute(text(f"""
        SELECT SUM(max_inn) AS ip_proxy
        FROM (
            SELECT game_pk, MAX(inning) AS max_inn
            FROM statcast_pitches
            WHERE pitcher  = :pid
              AND game_pk IN ({pk_list})
            GROUP BY game_pk
        ) sub
    """), {"pid": pitcher_id}).fetchone()

    k   = int(row.k   or 0)
    bb  = int(row.bb  or 0)
    hbp = int(row.hbp or 0)
    fb  = int(row.fb  or 0)
    ip  = float(ip_row.ip_proxy or 0.0)

    if ip < 1.0:
        return {"xfip": None, "ip": ip, "k": k, "bb": bb, "hbp": hbp, "fb": fb}

    xfip_raw = ((13.0 * fb * LG_HR_PER_FB) + (3.0 * (bb + hbp)) - (2.0 * k)) / ip + CFIP
    xfip = max(1.50, min(8.00, xfip_raw))

    return {"xfip": round(xfip, 3), "ip": round(ip, 1),
            "k": k, "bb": bb, "hbp": hbp, "fb": fb}


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
            "xfip_full":          None, "xfip_recent": None,
            "xfip_blended":       LEAGUE_AVG_XFIP,
            "ip_full":            0.0,  "ip_recent":   0.0,
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

    # ── xFIP (full sample and recent sample) ─────────────────────────────────
    xfip_full_d   = _compute_xfip(db, pitcher_id, full_pks)
    xfip_recent_d = _compute_xfip(db, pitcher_id, recent_pks)

    xfip_full   = xfip_full_d["xfip"]
    xfip_recent = xfip_recent_d["xfip"]
    ip_full     = xfip_full_d["ip"]
    ip_recent   = xfip_recent_d["ip"]

    # ── MLB API supplement when Statcast IP is thin ───────────────────────────
    # Covers pitchers returning from injury (e.g. Glasnow) and rookies who
    # have real current-season K/BB/FB data but not enough Statcast history
    # to avoid heavy regression toward league average.
    if ip_full < MIN_IP_PITCHER_FULL:
        try:
            from .mlb_api import get_pitcher_season_stats
            api_s = get_pitcher_season_stats(pitcher_id,
                                              __import__("datetime").date.today().year)
            if api_s and api_s["ip"] >= 5.0:
                xfip_api = _xfip_from_api_stats(api_s)
                if xfip_api is not None:
                    sc_ip  = ip_full or 0.0
                    api_ip = api_s["ip"]
                    if sc_ip > 0 and xfip_full is not None:
                        # Pool Statcast + API weighted by innings
                        xfip_full  = (sc_ip * xfip_full + api_ip * xfip_api) / (sc_ip + api_ip)
                    else:
                        xfip_full  = xfip_api
                    ip_full = sc_ip + api_ip   # combined evidence
                    log.debug("pitcher %s: Statcast %.0fIP + API %.0fIP → xFIP %.2f",
                              pitcher_id, sc_ip, api_ip, xfip_full)
        except Exception as exc:
            log.debug("API supplement failed for pitcher %s: %s", pitcher_id, exc)

    return {
        "woba_full":          full_woba,
        "pa_full":            full_pa,
        "woba_recent":        recent_woba,
        "pa_recent":          recent_pa,
        "woba_blended":       _blend(full_woba, full_pa,
                                     recent_woba, recent_pa,
                                     MIN_PA_PITCHER_FULL,
                                     MIN_PA_PITCHER_RECENT),
        "xfip_full":          xfip_full,
        "xfip_recent":        xfip_recent,
        "xfip_blended":       _blend_xfip(xfip_full,   ip_full,
                                           xfip_recent, ip_recent),
        "ip_full":            ip_full,
        "ip_recent":          ip_recent,
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

    three_ago = game_date - timedelta(days=3)

    # Per-reliever: blended wOBA quality + 72-hour pitch count for fatigue
    reliever_stats = []
    total_72h_pitches = 0

    for bp in bp_rows:
        s = pitcher_stats(db, bp.pitcher)

        # Actual pitch counts in each of the prior 3 days
        pc_row = db.execute(text("""
            SELECT
                SUM(CASE WHEN game_date = :y  THEN pitch_count ELSE 0 END) AS pc_24h,
                SUM(CASE WHEN game_date = :t  THEN pitch_count ELSE 0 END) AS pc_48h,
                SUM(CASE WHEN game_date = :th THEN pitch_count ELSE 0 END) AS pc_72h
            FROM (
                SELECT game_date, COUNT(*) AS pitch_count
                FROM statcast_pitches
                WHERE pitcher   = :pid
                  AND game_date IN (:y, :t, :th)
                GROUP BY game_date
            ) sub
        """), {
            "pid": bp.pitcher,
            "y":   yesterday,
            "t":   two_ago,
            "th":  three_ago,
        }).fetchone()

        pc_24h = int(pc_row.pc_24h or 0)
        pc_48h = int(pc_row.pc_48h or 0)
        pc_72h = int(pc_row.pc_72h or 0)

        # Continuous fatigue wOBA penalty:
        #   24h: 0.0012 per pitch  (e.g. 30 pitches → +0.036)
        #   48h: 0.0006 per pitch
        #   72h: 0.0003 per pitch
        fatigue_pen = (
            pc_24h * FATIGUE_PER_PITCH_24H
            + pc_48h * FATIGUE_PER_PITCH_48H
            + pc_72h * FATIGUE_PER_PITCH_72H
        )
        total_72h_pitches += pc_24h + pc_48h + pc_72h

        reliever_stats.append({
            "pitcher_id":    bp.pitcher,
            "usage_weight":  float(bp.total_pitches or 1),
            "woba_blended":  s["woba_blended"],
            "fatigue_pen":   fatigue_pen,
            "pc_24h":        pc_24h,
            "pc_48h":        pc_48h,
            "pc_72h":        pc_72h,
        })

    total_weight = sum(r["usage_weight"] for r in reliever_stats) or 1.0
    woba_raw     = sum(r["woba_blended"] * r["usage_weight"]
                       for r in reliever_stats) / total_weight

    # Fatigued wOBA: usage-weighted sum of (blended + penalty)
    woba_fatigued = sum(
        (r["woba_blended"] + r["fatigue_pen"]) * r["usage_weight"]
        for r in reliever_stats
    ) / total_weight

    return {
        "woba_raw":              round(woba_raw, 4),
        "woba_fatigued":         round(min(woba_fatigued, 0.420), 4),
        "total_72h_pitches":     total_72h_pitches,
        "n_relievers":           len(reliever_stats),
    }


# ── Team defense factor ───────────────────────────────────────────────────────

def team_defense_factor(db: Session, team: str, game_date: date) -> float:
    """
    Compute a team's defensive quality entering *game_date*.

    Factor = (actual wOBA on contact while fielding) /
             (estimated wOBA on contact while fielding using Statcast xwOBA).

    > 1.0  →  poor defense (allows more hits than exit-velocity expects)
    < 1.0  →  good defense

    This factor is applied to the OPPOSING team's lambda:
      - Away defense factor multiplies lambda_home
      - Home defense factor multiplies lambda_away

    Falls back to 1.0 (neutral) if data is insufficient or xwOBA column is absent.
    """
    try:
        team_games = db.execute(text("""
            SELECT DISTINCT game_pk
            FROM statcast_pitches
            WHERE (home_team = :team OR away_team = :team)
              AND game_date  < :gd
            ORDER BY game_pk DESC
            LIMIT :n
        """), {"team": team, "gd": game_date, "n": BULLPEN_SAMPLE_GAMES}).fetchall()

        if not team_games:
            return 1.0

        pk_list = ", ".join(str(r.game_pk) for r in team_games)

        # Balls in play WHILE this team is fielding.
        # Home team fields in Top half; away team fields in Bot half.
        row = db.execute(text(f"""
            SELECT
                SUM(woba_value)                       AS actual_woba_num,
                SUM(woba_denom)                       AS bip_count,
                SUM(estimated_woba_using_speedangle)  AS xwoba_num
            FROM statcast_pitches
            WHERE game_pk IN ({pk_list})
              AND (
                  (home_team = :team AND inning_topbot = 'Top')
                  OR
                  (away_team = :team AND inning_topbot = 'Bot')
              )
              AND bb_type   IS NOT NULL
              AND events    != 'home_run'
              AND woba_denom > 0
              AND estimated_woba_using_speedangle IS NOT NULL
        """), {"team": team}).fetchone()

        bip = int(row.bip_count or 0)
        if bip < 50 or not row.xwoba_num:
            return 1.0

        actual = float(row.actual_woba_num) / bip
        xwoba  = float(row.xwoba_num)       / bip

        if xwoba < 0.01:
            return 1.0

        raw_factor = actual / xwoba

        # Regress toward 1.0 based on sample size
        weight = min(bip, MIN_BIP_DEFENSE) / MIN_BIP_DEFENSE
        factor = raw_factor * weight + 1.0 * (1.0 - weight)

        return max(DEFENSE_FACTOR_FLOOR, min(DEFENSE_FACTOR_CAP, round(factor, 4)))

    except Exception:
        return 1.0


# ── Team home-field advantage factor ─────────────────────────────────────────

def team_hfa_factor(db: Session, team: str) -> float:
    """
    Compute team-specific home-field advantage λ-multiplier from historical
    home win rate.

    Formula:  hfa = 1 + 2.507 × (hw_rate − 0.5) / sqrt(9)
    (Linear normal approximation; validated: hw_rate=0.54 → hfa≈1.033)

    Regressed toward the global HOME_LAMBDA_FACTOR (1.033) when sample < 300 games.
    Falls back to HOME_LAMBDA_FACTOR on error.
    """
    try:
        # Use MAX(post_home_score) / MAX(post_away_score) per game_pk.
        # post_*_score is monotonically increasing so MAX gives final score.
        row = db.execute(text("""
            SELECT
                COUNT(DISTINCT game_pk)                              AS home_games,
                SUM(CASE WHEN final_home > final_away THEN 1 ELSE 0 END) AS home_wins
            FROM (
                SELECT game_pk,
                       MAX(post_home_score) AS final_home,
                       MAX(post_away_score) AS final_away
                FROM statcast_pitches
                WHERE home_team = :team
                  AND inning    >= 9
                GROUP BY game_pk
            ) t
        """), {"team": team}).fetchone()

        home_games = int(row.home_games or 0)
        home_wins  = int(row.home_wins  or 0)

        if home_games < 50:
            return HOME_LAMBDA_FACTOR

        hw_rate = home_wins / home_games
        raw_hfa = 1.0 + 2.507 * (hw_rate - 0.5) / math.sqrt(9.0)

        # Regress toward global default
        weight  = min(home_games, 300) / 300
        hfa     = raw_hfa * weight + HOME_LAMBDA_FACTOR * (1.0 - weight)

        return max(0.98, min(1.08, round(hfa, 4)))

    except Exception:
        return HOME_LAMBDA_FACTOR


# ── Umpire run factor ─────────────────────────────────────────────────────────

def umpire_run_factor(db: Session, umpire_name: Optional[str]) -> float:
    """
    Run environment multiplier for the home-plate umpire.

    Placeholder — returns 1.0 until umpire assignment data is integrated.
    A tight-zone umpire → factor < 1.0; loose zone → factor > 1.0.
    """
    return 1.0
