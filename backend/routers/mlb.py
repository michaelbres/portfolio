from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc, or_, Integer, cast
from typing import Optional
from database import get_db
from models import StatcastPitch, DataFetchLog

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
