from sqlalchemy import (
    Column, Integer, String, Float, Date, BigInteger, UniqueConstraint, DateTime
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


class DataFetchLog(Base):
    __tablename__ = "data_fetch_log"

    id = Column(Integer, primary_key=True)
    game_date = Column(Date, unique=True, index=True)
    rows_fetched = Column(Integer)
    status = Column(String(20))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
