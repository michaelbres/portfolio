from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, and_, Integer, cast
from typing import Optional
from database import get_db
from models import StatcastPitch, DataFetchLog, StuffPlusScore

router = APIRouter(prefix="/api/mlb", tags=["mlb"])

SORTABLE_COLS = {
    "game_date", "release_speed", "effective_speed", "release_spin_rate",
    "pfx_x", "pfx_z", "plate_x", "plate_z", "launch_speed", "launch_angle",
    "hit_distance_sc", "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle", "delta_run_exp", "bat_speed",
    "swing_length", "release_extension", "spin_axis",
}


def _apply_pitch_filters(query, **filters):
    if filters.get("pitcher_id"):
        query = query.filter(StatcastPitch.pitcher == filters["pitcher_id"])
    if filters.get("batter_id"):
        query = query.filter(StatcastPitch.batter == filters["batter_id"])
    if filters.get("team"):
        t = filters["team"]
        query = query.filter(
            or_(StatcastPitch.home_team == t, StatcastPitch.away_team == t)
        )
    if filters.get("pitch_type"):
        query = query.filter(StatcastPitch.pitch_type == filters["pitch_type"])
    if filters.get("start_date"):
        query = query.filter(StatcastPitch.game_date >= filters["start_date"])
    if filters.get("end_date"):
        query = query.filter(StatcastPitch.game_date <= filters["end_date"])
    if filters.get("season"):
        query = query.filter(StatcastPitch.game_year == filters["season"])
    if filters.get("balls") is not None:
        query = query.filter(StatcastPitch.balls == filters["balls"])
    if filters.get("strikes") is not None:
        query = query.filter(StatcastPitch.strikes == filters["strikes"])
    if filters.get("inning"):
        query = query.filter(StatcastPitch.inning == filters["inning"])
    if filters.get("stand"):
        query = query.filter(StatcastPitch.stand == filters["stand"])
    if filters.get("p_throws"):
        query = query.filter(StatcastPitch.p_throws == filters["p_throws"])
    if filters.get("events"):
        query = query.filter(StatcastPitch.events == filters["events"])
    return query


# ── Pitch search ────────────────────────────────────────────────────────────

@router.get("/pitches")
def search_pitches(
    db: Session = Depends(get_db),
    pitcher_id: Optional[int] = None,
    batter_id: Optional[int] = None,
    team: Optional[str] = None,
    pitch_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    season: Optional[int] = None,
    balls: Optional[int] = None,
    strikes: Optional[int] = None,
    inning: Optional[int] = None,
    stand: Optional[str] = None,
    p_throws: Optional[str] = None,
    events: Optional[str] = None,
    sort_by: str = "game_date",
    sort_dir: str = "desc",
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    query = db.query(StatcastPitch)
    query = _apply_pitch_filters(
        query, pitcher_id=pitcher_id, batter_id=batter_id, team=team,
        pitch_type=pitch_type, start_date=start_date, end_date=end_date,
        season=season, balls=balls, strikes=strikes, inning=inning,
        stand=stand, p_throws=p_throws, events=events,
    )
    total = query.count()

    if sort_by in SORTABLE_COLS:
        col = getattr(StatcastPitch, sort_by)
        query = query.order_by(desc(col) if sort_dir == "desc" else asc(col))
    else:
        query = query.order_by(desc(StatcastPitch.game_date))

    rows = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [_pitch_to_dict(r) for r in rows],
    }


# ── Pitching leaderboard ─────────────────────────────────────────────────────

@router.get("/leaderboards/pitching")
def pitching_leaderboard(
    db: Session = Depends(get_db),
    season: Optional[int] = None,
    team: Optional[str] = None,
    p_throws: Optional[str] = None,
    min_pitches: int = 100,
    sort_by: str = "avg_velo",
    sort_dir: str = "desc",
):
    swinging_miss = func.sum(
        cast(
            StatcastPitch.description.in_(
                ["swinging_strike", "swinging_strike_blocked", "foul_tip"]
            ),
            Integer,
        )
    )
    total_swings = func.sum(
        cast(
            StatcastPitch.description.in_([
                "swinging_strike", "swinging_strike_blocked", "foul_tip",
                "hit_into_play", "foul", "foul_bunt",
            ]),
            Integer,
        )
    )

    query = db.query(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
        func.count(StatcastPitch.id).label("total_pitches"),
        func.avg(StatcastPitch.release_speed).label("avg_velo"),
        func.max(StatcastPitch.release_speed).label("max_velo"),
        func.avg(StatcastPitch.release_spin_rate).label("avg_spin"),
        func.avg(StatcastPitch.pfx_x).label("avg_pfx_x"),
        func.avg(StatcastPitch.pfx_z).label("avg_pfx_z"),
        func.avg(StatcastPitch.release_extension).label("avg_extension"),
        func.avg(StatcastPitch.estimated_woba_using_speedangle).label("avg_xwoba_against"),
        swinging_miss.label("whiffs"),
        total_swings.label("swings"),
    ).group_by(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
    ).having(func.count(StatcastPitch.id) >= min_pitches)

    if season:
        query = query.filter(StatcastPitch.game_year == season)
    if team:
        query = query.filter(
            or_(StatcastPitch.home_team == team, StatcastPitch.away_team == team)
        )
    if p_throws:
        query = query.filter(StatcastPitch.p_throws == p_throws)

    rows = query.all()

    leaderboard = []
    for r in rows:
        whiff_rate = round(r.whiffs / r.swings * 100, 1) if r.swings else None
        leaderboard.append({
            "pitcher_id": r.pitcher,
            "pitcher_name": r.player_name,
            "p_throws": r.p_throws,
            "total_pitches": r.total_pitches,
            "avg_velo": _round(r.avg_velo, 1),
            "max_velo": _round(r.max_velo, 1),
            "avg_spin": _round(r.avg_spin, 0),
            "avg_pfx_x": _round(r.avg_pfx_x, 2),
            "avg_pfx_z": _round(r.avg_pfx_z, 2),
            "avg_extension": _round(r.avg_extension, 1),
            "avg_xwoba_against": _round(r.avg_xwoba_against, 3),
            "whiff_rate": whiff_rate,
        })

    _sort_leaderboard(leaderboard, sort_by, sort_dir)
    return leaderboard


# ── Hitting leaderboard ───────────────────────────────────────────────────────

@router.get("/leaderboards/hitting")
def hitting_leaderboard(
    db: Session = Depends(get_db),
    season: Optional[int] = None,
    team: Optional[str] = None,
    stand: Optional[str] = None,
    min_batted_balls: int = 25,
    sort_by: str = "avg_exit_velo",
    sort_dir: str = "desc",
):
    query = db.query(
        StatcastPitch.batter,
        StatcastPitch.batter_name,
        StatcastPitch.stand,
        func.count(StatcastPitch.id).label("batted_balls"),
        func.avg(StatcastPitch.launch_speed).label("avg_exit_velo"),
        func.max(StatcastPitch.launch_speed).label("max_exit_velo"),
        func.avg(StatcastPitch.launch_angle).label("avg_launch_angle"),
        func.avg(StatcastPitch.hit_distance_sc).label("avg_distance"),
        func.avg(StatcastPitch.estimated_ba_using_speedangle).label("avg_xba"),
        func.avg(StatcastPitch.estimated_woba_using_speedangle).label("avg_xwoba"),
    ).filter(
        StatcastPitch.launch_speed.isnot(None),
        StatcastPitch.bb_type.isnot(None),
    ).group_by(
        StatcastPitch.batter,
        StatcastPitch.batter_name,
        StatcastPitch.stand,
    ).having(func.count(StatcastPitch.id) >= min_batted_balls)

    if season:
        query = query.filter(StatcastPitch.game_year == season)
    if team:
        query = query.filter(
            or_(StatcastPitch.home_team == team, StatcastPitch.away_team == team)
        )
    if stand:
        query = query.filter(StatcastPitch.stand == stand)

    rows = query.all()

    leaderboard = [{
        "batter_id": r.batter,
        "batter_name": r.batter_name,
        "stand": r.stand,
        "batted_balls": r.batted_balls,
        "avg_exit_velo": _round(r.avg_exit_velo, 1),
        "max_exit_velo": _round(r.max_exit_velo, 1),
        "avg_launch_angle": _round(r.avg_launch_angle, 1),
        "avg_distance": _round(r.avg_distance, 0),
        "avg_xba": _round(r.avg_xba, 3),
        "avg_xwoba": _round(r.avg_xwoba, 3),
    } for r in rows]

    _sort_leaderboard(leaderboard, sort_by, sort_dir)
    return leaderboard


# ── Pitchers list ─────────────────────────────────────────────────────────────

@router.get("/pitchers")
def list_pitchers(
    db: Session = Depends(get_db),
    season: Optional[int] = None,
    team: Optional[str] = None,
    search: Optional[str] = None,
):
    query = db.query(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
        func.count(StatcastPitch.id).label("total_pitches"),
        func.min(StatcastPitch.game_date).label("first_game"),
        func.max(StatcastPitch.game_date).label("last_game"),
    ).group_by(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
    )

    if season:
        query = query.filter(StatcastPitch.game_year == season)
    if team:
        query = query.filter(
            or_(StatcastPitch.home_team == team, StatcastPitch.away_team == team)
        )
    if search:
        query = query.filter(
            StatcastPitch.player_name.ilike(f"%{search}%")
        )

    rows = query.order_by(StatcastPitch.player_name).all()
    return [{
        "pitcher_id": r.pitcher,
        "pitcher_name": r.player_name,
        "p_throws": r.p_throws,
        "total_pitches": r.total_pitches,
        "first_game": str(r.first_game),
        "last_game": str(r.last_game),
    } for r in rows]


# ── Pitcher detail ────────────────────────────────────────────────────────────

@router.get("/pitchers/{pitcher_id}/summary")
def pitcher_summary(
    pitcher_id: int,
    db: Session = Depends(get_db),
    season: Optional[int] = None,
):
    query = db.query(StatcastPitch).filter(StatcastPitch.pitcher == pitcher_id)
    if season:
        query = query.filter(StatcastPitch.game_year == season)

    total = query.count()
    if total == 0:
        raise HTTPException(status_code=404, detail="Pitcher not found")

    # Arsenal breakdown
    arsenal = db.query(
        StatcastPitch.pitch_type,
        StatcastPitch.pitch_name,
        func.count(StatcastPitch.id).label("count"),
        func.avg(StatcastPitch.release_speed).label("avg_velo"),
        func.avg(StatcastPitch.release_spin_rate).label("avg_spin"),
        func.avg(StatcastPitch.pfx_x).label("avg_pfx_x"),
        func.avg(StatcastPitch.pfx_z).label("avg_pfx_z"),
        func.avg(StatcastPitch.release_extension).label("avg_extension"),
    ).filter(StatcastPitch.pitcher == pitcher_id)

    if season:
        arsenal = arsenal.filter(StatcastPitch.game_year == season)

    arsenal = arsenal.group_by(
        StatcastPitch.pitch_type, StatcastPitch.pitch_name
    ).all()

    pitcher_name = (
        db.query(StatcastPitch.player_name, StatcastPitch.p_throws)
        .filter(StatcastPitch.pitcher == pitcher_id)
        .first()
    )

    return {
        "pitcher_id": pitcher_id,
        "pitcher_name": pitcher_name.player_name if pitcher_name else None,
        "p_throws": pitcher_name.p_throws if pitcher_name else None,
        "total_pitches": total,
        "arsenal": [{
            "pitch_type": a.pitch_type,
            "pitch_name": a.pitch_name,
            "count": a.count,
            "usage_pct": round(a.count / total * 100, 1),
            "avg_velo": _round(a.avg_velo, 1),
            "avg_spin": _round(a.avg_spin, 0),
            "avg_pfx_x": _round(a.avg_pfx_x, 2),
            "avg_pfx_z": _round(a.avg_pfx_z, 2),
            "avg_extension": _round(a.avg_extension, 1),
        } for a in arsenal],
    }


@router.get("/pitch-type-norms")
def pitch_type_norms(db: Session = Depends(get_db), season: Optional[int] = None):
    """
    P10/P90 ranges for each metric per pitch type, computed across all pitchers
    with >= 50 pitches of that type. Used for league-relative heat map coloring.
    """
    swing_descs = ["swinging_strike", "swinging_strike_blocked", "foul_tip",
                   "hit_into_play", "foul", "foul_bunt"]
    miss_descs  = ["swinging_strike", "swinging_strike_blocked"]

    swings      = func.sum(cast(StatcastPitch.description.in_(swing_descs), Integer))
    misses      = func.sum(cast(StatcastPitch.description.in_(miss_descs),  Integer))
    in_zone     = func.sum(cast(and_(StatcastPitch.zone >= 1, StatcastPitch.zone <= 9), Integer))
    out_zone    = func.sum(cast(StatcastPitch.zone > 9, Integer))
    chase       = func.sum(cast(and_(StatcastPitch.zone > 9,
                                     StatcastPitch.description.in_(swing_descs)), Integer))

    query = db.query(
        StatcastPitch.pitch_type,
        func.count(StatcastPitch.id).label("cnt"),
        func.avg(StatcastPitch.release_speed).label("velo"),
        func.avg(StatcastPitch.release_spin_rate).label("spin"),
        func.avg(StatcastPitch.pfx_z).label("ivb"),
        func.avg(StatcastPitch.estimated_woba_using_speedangle).label("xwoba"),
        swings.label("swings"),
        misses.label("misses"),
        in_zone.label("in_zone"),
        out_zone.label("out_zone"),
        chase.label("chase"),
    ).filter(
        StatcastPitch.pitch_type.isnot(None)
    ).group_by(
        StatcastPitch.pitcher, StatcastPitch.pitch_type
    ).having(func.count(StatcastPitch.id) >= 50)

    if season:
        query = query.filter(StatcastPitch.game_year == season)

    rows = query.all()

    # Group values by pitch type, then compute percentiles in Python
    from collections import defaultdict
    buckets = defaultdict(lambda: defaultdict(list))
    for r in rows:
        pt = r.pitch_type
        if r.velo:   buckets[pt]["velo"].append(float(r.velo))
        if r.spin:   buckets[pt]["spin"].append(float(r.spin))
        if r.ivb:    buckets[pt]["ivb"].append(float(r.ivb) * 12)   # feet → inches
        if r.xwoba:  buckets[pt]["xwoba"].append(float(r.xwoba))
        if r.swings: buckets[pt]["whiff_pct"].append(float(r.misses or 0) / float(r.swings) * 100)
        if r.cnt:    buckets[pt]["zone_pct"].append(float(r.in_zone or 0) / float(r.cnt) * 100)
        if r.out_zone: buckets[pt]["chase_pct"].append(float(r.chase or 0) / float(r.out_zone) * 100)

    def pct(data, p):
        s = sorted(data)
        if not s:
            return None
        idx = (len(s) - 1) * p / 100
        lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 4)

    norms = {}
    for pt, metrics in buckets.items():
        norms[pt] = {m: {"p10": pct(vals, 10), "p90": pct(vals, 90)}
                     for m, vals in metrics.items()}
    return norms


@router.get("/game-dates")
def game_dates(db: Session = Depends(get_db), season: Optional[int] = None):
    """Return all distinct dates that have pitch data, most recent first."""
    query = db.query(StatcastPitch.game_date).distinct()
    if season:
        query = query.filter(StatcastPitch.game_year == season)
    rows = query.order_by(desc(StatcastPitch.game_date)).all()
    return [str(r.game_date) for r in rows]


@router.get("/pitchers-by-date")
def pitchers_by_date(
    game_date: str,
    db: Session = Depends(get_db),
):
    """Return every pitcher who threw at least one pitch on the given date."""
    rows = db.query(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
        StatcastPitch.game_pk,
        StatcastPitch.home_team,
        StatcastPitch.away_team,
        func.count(StatcastPitch.id).label("total_pitches"),
    ).filter(StatcastPitch.game_date == game_date).group_by(
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.p_throws,
        StatcastPitch.game_pk,
        StatcastPitch.home_team,
        StatcastPitch.away_team,
    ).order_by(StatcastPitch.away_team, StatcastPitch.home_team, desc("total_pitches")).all()

    return [{
        "pitcher_id": r.pitcher,
        "pitcher_name": r.player_name,
        "p_throws": r.p_throws,
        "game_pk": r.game_pk,
        "home_team": r.home_team,
        "away_team": r.away_team,
        "total_pitches": r.total_pitches,
    } for r in rows]


@router.get("/pitchers/{pitcher_id}/games")
def pitcher_games(
    pitcher_id: int,
    db: Session = Depends(get_db),
    season: Optional[int] = None,
):
    query = db.query(
        StatcastPitch.game_pk,
        StatcastPitch.game_date,
        StatcastPitch.home_team,
        StatcastPitch.away_team,
        func.count(StatcastPitch.id).label("total_pitches"),
    ).filter(StatcastPitch.pitcher == pitcher_id).group_by(
        StatcastPitch.game_pk, StatcastPitch.game_date,
        StatcastPitch.home_team, StatcastPitch.away_team,
    )
    if season:
        query = query.filter(StatcastPitch.game_year == season)
    rows = query.order_by(desc(StatcastPitch.game_date)).all()
    return [{
        "game_pk": r.game_pk,
        "game_date": str(r.game_date),
        "home_team": r.home_team,
        "away_team": r.away_team,
        "total_pitches": r.total_pitches,
    } for r in rows]


@router.get("/pitchers/{pitcher_id}/game-summary")
def pitcher_game_summary(
    pitcher_id: int,
    game_pk: int,
    db: Session = Depends(get_db),
):
    pitches = db.query(StatcastPitch).filter(
        StatcastPitch.pitcher == pitcher_id,
        StatcastPitch.game_pk == game_pk,
    ).all()

    if not pitches:
        raise HTTPException(status_code=404, detail="No pitches found")

    p0 = pitches[0]
    total = len(pitches)

    # Overall line stats — walk the pitch list once
    ab_events = {}       # at_bat_number → events value (last pitch of AB)
    whiffs = strikes = 0
    for p in pitches:
        if p.description in ("swinging_strike", "swinging_strike_blocked"):
            whiffs += 1
        if p.type in ("S", "X"):
            strikes += 1
        if p.events:
            ab_events[p.at_bat_number] = p.events

    k = bb = hits = hr = hbp = 0
    for ev in ab_events.values():
        if "strikeout" in ev:   k += 1
        if ev == "walk":        bb += 1
        if ev in ("single", "double", "triple", "home_run"): hits += 1
        if ev == "home_run":    hr += 1
        if ev == "hit_by_pitch": hbp += 1

    # Per-pitch-type breakdown
    from collections import defaultdict
    groups = defaultdict(list)
    for p in pitches:
        if p.pitch_type:
            groups[p.pitch_type].append(p)

    arsenal = []
    for pt, grp in groups.items():
        cnt = len(grp)
        velos  = [p.release_speed for p in grp if p.release_speed is not None]
        spins  = [p.release_spin_rate for p in grp if p.release_spin_rate is not None]
        pfx_xs = [p.pfx_x for p in grp if p.pfx_x is not None]
        pfx_zs = [p.pfx_z for p in grp if p.pfx_z is not None]
        xwobas = [p.estimated_woba_using_speedangle for p in grp if p.estimated_woba_using_speedangle is not None]

        in_zone     = [p for p in grp if p.zone and 1 <= p.zone <= 9]
        out_zone    = [p for p in grp if p.zone and p.zone > 9]
        swing_descs = {"swinging_strike", "swinging_strike_blocked", "foul_tip",
                       "hit_into_play", "foul", "foul_bunt"}
        miss_descs  = {"swinging_strike", "swinging_strike_blocked"}

        swings_total = sum(1 for p in grp if p.description in swing_descs)
        misses_total = sum(1 for p in grp if p.description in miss_descs)
        chases       = sum(1 for p in out_zone if p.description in swing_descs)

        arsenal.append({
            "pitch_type": pt,
            "pitch_name": grp[0].pitch_name or pt,
            "count": cnt,
            "usage_pct": round(cnt / total * 100, 1),
            "avg_velo":  round(sum(velos)  / len(velos),  1) if velos  else None,
            "avg_spin":  round(sum(spins)  / len(spins),  0) if spins  else None,
            "avg_hb":    round(sum(pfx_xs) / len(pfx_xs) * 12, 1) if pfx_xs else None,
            "avg_ivb":   round(sum(pfx_zs) / len(pfx_zs) * 12, 1) if pfx_zs else None,
            "zone_pct":  round(len(in_zone) / cnt * 100, 1),
            "chase_pct": round(chases / len(out_zone) * 100, 1) if out_zone else None,
            "whiff_pct": round(misses_total / swings_total * 100, 1) if swings_total else None,
            "avg_xwoba": round(sum(xwobas) / len(xwobas), 3) if xwobas else None,
        })

    arsenal.sort(key=lambda x: -x["count"])

    # Attach Stuff+ scores (season-level, from stuff_plus_scores table)
    game_season = p0.game_date.year if p0.game_date else None
    if game_season:
        sp_rows = db.query(StuffPlusScore).filter(
            StuffPlusScore.pitcher_id == pitcher_id,
            StuffPlusScore.season == game_season,
        ).all()
        sp_map = {r.pitch_type: r.avg_stuff_plus for r in sp_rows}
    else:
        sp_map = {}

    for row in arsenal:
        row["stuff_plus"] = sp_map.get(row["pitch_type"])

    # Individual pitch coordinates for scatter plots
    pitch_coords = [{
        "pitch_type":     p.pitch_type,
        "plate_x":        p.plate_x,
        "plate_z":        p.plate_z,
        "sz_top":         p.sz_top,
        "sz_bot":         p.sz_bot,
        "release_pos_x":  p.release_pos_x,
        "release_pos_z":  p.release_pos_z,
        "description":    p.description,
    } for p in pitches if p.pitch_type]

    return {
        "pitcher_id": pitcher_id,
        "pitcher_name": p0.player_name,
        "p_throws": p0.p_throws,
        "game_pk": game_pk,
        "game_date": str(p0.game_date),
        "home_team": p0.home_team,
        "away_team": p0.away_team,
        "line": {
            "total_pitches": total,
            "pa": len(ab_events),
            "k": k, "bb": bb, "hits": hits, "hr": hr, "hbp": hbp,
            "whiffs": whiffs,
            "strike_pct": round(strikes / total * 100, 1) if total else None,
        },
        "arsenal": arsenal,
        "pitches": pitch_coords,
    }


@router.get("/pitchers/{pitcher_id}/pitches")
def pitcher_pitches(
    pitcher_id: int,
    db: Session = Depends(get_db),
    season: Optional[int] = None,
    pitch_type: Optional[str] = None,
    limit: int = Query(default=200, le=2000),
    offset: int = 0,
):
    query = db.query(StatcastPitch).filter(StatcastPitch.pitcher == pitcher_id)
    if season:
        query = query.filter(StatcastPitch.game_year == season)
    if pitch_type:
        query = query.filter(StatcastPitch.pitch_type == pitch_type)

    total = query.count()
    rows = query.order_by(desc(StatcastPitch.game_date)).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [_pitch_to_dict(r) for r in rows],
    }


# ── Teams / meta ──────────────────────────────────────────────────────────────

@router.get("/teams")
def list_teams(db: Session = Depends(get_db), season: Optional[int] = None):
    q = db.query(StatcastPitch.home_team).distinct()
    if season:
        q = q.filter(StatcastPitch.game_year == season)
    teams = sorted({r[0] for r in q.all() if r[0]})
    return teams


@router.get("/pitch-types")
def list_pitch_types(db: Session = Depends(get_db)):
    rows = db.query(
        StatcastPitch.pitch_type, StatcastPitch.pitch_name
    ).distinct().order_by(StatcastPitch.pitch_name).all()
    return [{"code": r.pitch_type, "name": r.pitch_name} for r in rows if r.pitch_type]


@router.get("/data-status")
def data_status(db: Session = Depends(get_db)):
    latest = (
        db.query(DataFetchLog)
        .filter(DataFetchLog.status == "success")
        .order_by(desc(DataFetchLog.game_date))
        .first()
    )
    total_pitches = db.query(func.count(StatcastPitch.id)).scalar()
    return {
        "latest_game_date": str(latest.game_date) if latest else None,
        "total_pitches": total_pitches,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _round(val, decimals):
    if val is None:
        return None
    return round(float(val), decimals)


def _sort_leaderboard(data, sort_by, sort_dir):
    reverse = sort_dir == "desc"
    data.sort(key=lambda x: (x.get(sort_by) is None, x.get(sort_by) or 0), reverse=reverse)


def _pitch_to_dict(p: StatcastPitch) -> dict:
    return {
        "id": p.id,
        "game_pk": p.game_pk,
        "game_date": str(p.game_date) if p.game_date else None,
        "game_year": p.game_year,
        "at_bat_number": p.at_bat_number,
        "pitch_number": p.pitch_number,
        "pitcher_id": p.pitcher,
        "pitcher_name": p.player_name,
        "batter_id": p.batter,
        "batter_name": p.batter_name,
        "stand": p.stand,
        "p_throws": p.p_throws,
        "home_team": p.home_team,
        "away_team": p.away_team,
        "pitch_type": p.pitch_type,
        "pitch_name": p.pitch_name,
        "type": p.type,
        "description": p.description,
        "events": p.events,
        "zone": p.zone,
        "bb_type": p.bb_type,
        "balls": p.balls,
        "strikes": p.strikes,
        "outs_when_up": p.outs_when_up,
        "inning": p.inning,
        "inning_topbot": p.inning_topbot,
        "on_1b": p.on_1b,
        "on_2b": p.on_2b,
        "on_3b": p.on_3b,
        "release_speed": p.release_speed,
        "effective_speed": p.effective_speed,
        "release_spin_rate": p.release_spin_rate,
        "spin_axis": p.spin_axis,
        "release_extension": p.release_extension,
        "release_pos_x": p.release_pos_x,
        "release_pos_y": p.release_pos_y,
        "release_pos_z": p.release_pos_z,
        "pfx_x": p.pfx_x,
        "pfx_z": p.pfx_z,
        "plate_x": p.plate_x,
        "plate_z": p.plate_z,
        "sz_top": p.sz_top,
        "sz_bot": p.sz_bot,
        "launch_speed": p.launch_speed,
        "launch_angle": p.launch_angle,
        "hit_distance_sc": p.hit_distance_sc,
        "hc_x": p.hc_x,
        "hc_y": p.hc_y,
        "estimated_ba_using_speedangle": p.estimated_ba_using_speedangle,
        "estimated_woba_using_speedangle": p.estimated_woba_using_speedangle,
        "woba_value": p.woba_value,
        "delta_run_exp": p.delta_run_exp,
        "delta_home_win_exp": p.delta_home_win_exp,
        "bat_speed": p.bat_speed,
        "swing_length": p.swing_length,
        "home_score": p.home_score,
        "away_score": p.away_score,
    }
