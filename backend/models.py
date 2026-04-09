from sqlalchemy import (
    Column, Integer, String, Float, Date, BigInteger, UniqueConstraint,
    DateTime, Boolean, Text
)
from sqlalchemy.sql import func
from database import Base


class StatcastPitch(Base):
    __tablename__ = "statcast_pitches"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    game_pk = Column(BigInteger, index=True)
    at_bat_number = Column(Integer)
    pitch_number = Column(Integer)
    game_date = Column(Date, index=True)
    game_year = Column(Integer, index=True)
    game_type = Column(String(5))

    # Pitcher / Batter
    pitcher = Column(Integer, index=True)
    player_name = Column(String(100), index=True)   # pitcher name
    batter = Column(Integer, index=True)
    batter_name = Column(String(100), index=True)
    stand = Column(String(2))       # batter hand L/R
    p_throws = Column(String(2))    # pitcher hand L/R

    # Teams / Score
    home_team = Column(String(10), index=True)
    away_team = Column(String(10), index=True)
    home_score = Column(Integer)
    away_score = Column(Integer)
    bat_score = Column(Integer)
    fld_score = Column(Integer)
    post_away_score = Column(Integer)
    post_home_score = Column(Integer)
    post_bat_score = Column(Integer)
    post_fld_score = Column(Integer)

    # Count / Situation
    balls = Column(Integer)
    strikes = Column(Integer)
    outs_when_up = Column(Integer)
    inning = Column(Integer)
    inning_topbot = Column(String(5))
    on_1b = Column(Integer)
    on_2b = Column(Integer)
    on_3b = Column(Integer)

    # Pitch classification
    pitch_type = Column(String(10), index=True)
    pitch_name = Column(String(50))
    type = Column(String(2))        # B, S, X
    description = Column(String(100))
    events = Column(String(50))
    des = Column(String(500))
    zone = Column(Integer)
    bb_type = Column(String(30))
    hit_location = Column(Integer)

    # Pitch metrics
    release_speed = Column(Float)
    effective_speed = Column(Float)
    release_spin_rate = Column(Float)
    spin_axis = Column(Float)
    release_extension = Column(Float)
    release_pos_x = Column(Float)
    release_pos_y = Column(Float)
    release_pos_z = Column(Float)

    # Movement (in feet)
    pfx_x = Column(Float)
    pfx_z = Column(Float)

    # Location at plate
    plate_x = Column(Float)
    plate_z = Column(Float)
    sz_top = Column(Float)
    sz_bot = Column(Float)

    # Physics
    vx0 = Column(Float)
    vy0 = Column(Float)
    vz0 = Column(Float)
    ax = Column(Float)
    ay = Column(Float)
    az = Column(Float)

    # Batted ball
    hc_x = Column(Float)
    hc_y = Column(Float)
    hit_distance_sc = Column(Float)
    launch_speed = Column(Float)
    launch_angle = Column(Float)
    launch_speed_angle = Column(Integer)

    # Expected stats
    estimated_ba_using_speedangle = Column(Float)
    estimated_woba_using_speedangle = Column(Float)
    woba_value = Column(Float)
    woba_denom = Column(Integer)
    babip_value = Column(Float)
    iso_value = Column(Float)

    # Win probability
    delta_home_win_exp = Column(Float)
    delta_run_exp = Column(Float)

    # Fielding alignment
    if_fielding_alignment = Column(String(30))
    of_fielding_alignment = Column(String(30))

    # Hawkeye (2023+)
    bat_speed = Column(Float)
    swing_length = Column(Float)

    # Umpire / misc
    umpire = Column(String(50))
    sv_id = Column(String(50))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("game_pk", "at_bat_number", "pitch_number", name="uq_pitch"),
    )


class StuffPlusScore(Base):
    """Per-pitcher per-pitch-type Stuff+ scores, computed by the analytics module."""
    __tablename__ = "stuff_plus_scores"

    id          = Column(Integer, primary_key=True)
    pitcher_id  = Column(Integer, index=True, nullable=False)
    pitcher_name = Column(String(100))
    pitch_type  = Column(String(10), nullable=False)
    season      = Column(Integer, nullable=False, index=True)
    n_pitches   = Column(Integer)
    avg_stuff_plus = Column(Float)   # 100 = league avg for that pitch type
    model_family = Column(String(5)) # FB, BB, OS
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("pitcher_id", "pitch_type", "season", name="uq_stuff_plus"),
    )


class DataFetchLog(Base):
    __tablename__ = "data_fetch_log"

    id = Column(Integer, primary_key=True)
    game_date = Column(Date, unique=True, index=True)
    rows_fetched = Column(Integer)
    status = Column(String(20))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Fair Value Model Tables ────────────────────────────────────────────────────

class FairValueGame(Base):
    """One row per game per model run. Stores computed fair value odds."""
    __tablename__ = "fair_value_games"

    id = Column(Integer, primary_key=True)
    game_pk = Column(BigInteger, unique=True, index=True, nullable=False)
    game_date = Column(Date, index=True, nullable=False)
    game_time_utc = Column(String(30))        # ISO string, nullable before schedule posts
    home_team = Column(String(10), nullable=False)
    away_team = Column(String(10), nullable=False)
    venue = Column(String(100))

    # Starting pitchers
    home_sp_id = Column(Integer)
    home_sp_name = Column(String(100))
    home_sp_hand = Column(String(2))
    away_sp_id = Column(Integer)
    away_sp_name = Column(String(100))
    away_sp_hand = Column(String(2))

    # Pitch limits — manual_flag means the user set this, not the default
    home_pitch_limit = Column(Integer)
    home_pitch_limit_manual = Column(Boolean, default=False)
    away_pitch_limit = Column(Integer)
    away_pitch_limit_manual = Column(Boolean, default=False)

    # Pitcher projections (blended season + last-N)
    home_sp_pitches_per_inning = Column(Float)
    home_sp_proj_innings = Column(Float)
    home_sp_woba_season = Column(Float)
    home_sp_woba_recent = Column(Float)
    home_sp_woba_blended = Column(Float)
    home_sp_xfip_blended = Column(Float)
    home_sp_pa_season = Column(Integer)
    home_sp_pa_recent = Column(Integer)

    away_sp_pitches_per_inning = Column(Float)
    away_sp_proj_innings = Column(Float)
    away_sp_woba_season = Column(Float)
    away_sp_woba_recent = Column(Float)
    away_sp_woba_blended = Column(Float)
    away_sp_xfip_blended = Column(Float)
    away_sp_pa_season = Column(Integer)
    away_sp_pa_recent = Column(Integer)

    # Bullpen (pre-fatigue wOBA, post-fatigue wOBA)
    home_bp_woba_raw = Column(Float)
    home_bp_woba_fatigued = Column(Float)
    away_bp_woba_raw = Column(Float)
    away_bp_woba_fatigued = Column(Float)

    # Lineup
    home_lineup_woba = Column(Float)       # weighted by batting order + vs SP hand
    away_lineup_woba = Column(Float)
    home_lineup_source = Column(String(20))  # 'confirmed', 'projected', 'recent_avg'
    away_lineup_source = Column(String(20))

    # Park + weather
    park_factor = Column(Float)
    weather_carry_factor = Column(Float)

    # Model outputs
    home_lambda = Column(Float)            # expected runs, home team offense
    away_lambda = Column(Float)
    home_win_prob = Column(Float)
    away_win_prob = Column(Float)
    home_fair_odds = Column(Integer)       # American odds (no vig)
    away_fair_odds = Column(Integer)

    # Market lines for comparison (optional, free sources only)
    home_market_odds = Column(Integer)
    away_market_odds = Column(Integer)
    market_source = Column(String(50))

    model_version = Column(String(20), default="1.0")
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FairValueLineupSlot(Base):
    """Each batter slot in a game's projected/confirmed lineup."""
    __tablename__ = "fair_value_lineup_slots"

    id = Column(Integer, primary_key=True)
    game_pk = Column(BigInteger, index=True, nullable=False)
    team = Column(String(10), nullable=False)
    batting_order = Column(Integer, nullable=False)   # 1–9
    player_id = Column(Integer)
    player_name = Column(String(100))
    batter_hand = Column(String(2))
    woba_season = Column(Float)
    woba_recent = Column(Float)
    woba_blended = Column(Float)
    woba_vs_sp_hand = Column(Float)   # split vs opposing SP handedness
    pa_weight = Column(Float)         # fraction of team PAs this slot gets

    __table_args__ = (
        UniqueConstraint("game_pk", "team", "batting_order",
                         name="uq_lineup_slot"),
    )


class FairValueCalibration(Base):
    """
    Post-game calibration record linking model output to closing line and outcome.
    One row per game; populated by the nightly_calibration.py script.

    Used for:
      - Calibration audit (systematic bias detection)
      - Platt scaling coefficient fitting
      - Rolling delta monitoring / auto-reweight triggers
    """
    __tablename__ = "fair_value_calibration"

    id = Column(Integer, primary_key=True)
    game_pk = Column(BigInteger, unique=True, index=True, nullable=False)
    game_date = Column(Date, index=True)
    home_team = Column(String(10))
    away_team = Column(String(10))

    # Morning model output (raw, pre-Platt / pre-blend)
    model_home_prob = Column(Float)
    model_away_prob = Column(Float)

    # Closing line (no-vig, from Kalshi or other sharp source)
    closing_home_prob = Column(Float)
    closing_away_prob = Column(Float)
    closing_source = Column(String(50))

    # Delta: positive = model overrates home team vs market
    prob_delta = Column(Float)          # model_home_prob - closing_home_prob
    abs_delta = Column(Float)           # |prob_delta|

    # Game outcome (-1 = unknown, 0 = away win, 1 = home win)
    outcome_home_win = Column(Integer, default=-1)

    # Brier score contributions for model vs market
    model_brier = Column(Float)         # (model_home_prob - outcome)²
    market_brier = Column(Float)        # (closing_home_prob - outcome)²

    # Additional feature context for bias grouping
    home_sp_xfip = Column(Float)
    away_sp_xfip = Column(Float)
    home_lineup_woba = Column(Float)
    away_lineup_woba = Column(Float)
    weather_carry_factor = Column(Float)
    total_lambda = Column(Float)        # home_lambda + away_lambda (game total proxy)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
