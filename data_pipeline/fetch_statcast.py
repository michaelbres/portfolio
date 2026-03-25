"""
Fetches Statcast pitch-by-pitch data and upserts it into the database.

Modes:
  --init   : Load the full 2025 regular season (skips dates already logged)
  --daily  : Fetch yesterday's data (default, used by GitHub Actions)
  --date   : Fetch a specific date  e.g. --date 2025-04-15
  --range  : Fetch a date range     e.g. --range 2025-04-01 2025-04-30

Usage:
  python data_pipeline/fetch_statcast.py --init
  python data_pipeline/fetch_statcast.py --daily
  python data_pipeline/fetch_statcast.py --date 2025-06-01
  python data_pipeline/fetch_statcast.py --range 2025-04-01 2025-04-30
"""

import os
import sys
import argparse
import time
import traceback
from datetime import date, timedelta, datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Allow imports from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import engine, SessionLocal
from models import StatcastPitch, DataFetchLog, Base

# pybaseball — suppress the "caching" message
import warnings
warnings.filterwarnings("ignore")
import pybaseball
pybaseball.cache.enable()

# ── 2025 regular season opener ────────────────────────────────────────────────
SEASON_START = {
    2025: date(2025, 3, 27),
    2026: date(2026, 3, 27),   # update if Opening Day changes
}
DEFAULT_SEASON = 2025


def get_already_fetched(db) -> set:
    rows = db.query(DataFetchLog.game_date).filter(DataFetchLog.status == "success").all()
    return {r.game_date for r in rows}


def log_fetch(db, game_date, rows_fetched, status):
    existing = db.query(DataFetchLog).filter(DataFetchLog.game_date == game_date).first()
    if existing:
        existing.rows_fetched = rows_fetched
        existing.status = status
        existing.fetched_at = datetime.utcnow()
    else:
        db.add(DataFetchLog(
            game_date=game_date,
            rows_fetched=rows_fetched,
            status=status,
        ))
    db.commit()


def fetch_and_upsert(date_str: str, db):
    """Fetch one day of Statcast data and upsert into DB. Returns row count."""
    print(f"  Fetching {date_str} ...", flush=True)
    try:
        df = pybaseball.statcast(start_dt=date_str, end_dt=date_str, verbose=False)
    except Exception as e:
        print(f"  ERROR fetching {date_str}: {e}")
        raise

    if df is None or df.empty:
        print(f"  No data for {date_str}")
        return 0

    df = _clean_df(df)
    rows = df.to_dict(orient="records")
    if not rows:
        return 0

    # Upsert — skip duplicates (game_pk / at_bat_number / pitch_number)
    stmt = pg_insert(StatcastPitch.__table__).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_pitch")

    with engine.begin() as conn:
        result = conn.execute(stmt)

    inserted = result.rowcount
    print(f"  {date_str}: {len(rows)} pitches fetched, {inserted} new rows inserted")
    return len(rows)


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Rename and coerce columns to match the SQLAlchemy model."""
    col_map = {
        "player_name": "player_name",   # pitcher name in pybaseball
    }
    df = df.rename(columns=col_map)

    # Add batter_name column if not present (not always returned by pybaseball)
    if "batter_name" not in df.columns:
        df["batter_name"] = None

    # Keep only columns that exist in the model
    model_cols = {c.name for c in StatcastPitch.__table__.columns} - {"id", "created_at"}
    keep = [c for c in df.columns if c in model_cols]
    df = df[keep].copy()

    # Coerce numeric columns (some come as object dtype)
    float_cols = [
        "release_speed", "release_pos_x", "release_pos_z", "release_pos_y",
        "pfx_x", "pfx_z", "plate_x", "plate_z", "sz_top", "sz_bot",
        "vx0", "vy0", "vz0", "ax", "ay", "az",
        "hc_x", "hc_y", "hit_distance_sc", "launch_speed", "launch_angle",
        "effective_speed", "release_spin_rate", "release_extension",
        "estimated_ba_using_speedangle", "estimated_woba_using_speedangle",
        "woba_value", "babip_value", "iso_value",
        "delta_home_win_exp", "delta_run_exp",
        "bat_speed", "swing_length", "spin_axis",
    ]
    for c in float_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    int_cols = [
        "balls", "strikes", "outs_when_up", "inning", "zone", "hit_location",
        "on_1b", "on_2b", "on_3b", "woba_denom", "launch_speed_angle",
        "at_bat_number", "pitch_number", "home_score", "away_score",
        "bat_score", "fld_score", "post_away_score", "post_home_score",
        "post_bat_score", "post_fld_score",
    ]
    for c in int_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
            df[c] = df[c].where(df[c].notna(), other=None)

    # game_date → python date
    if "game_date" in df.columns:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce").dt.date

    # game_year
    if "game_year" not in df.columns and "game_date" in df.columns:
        df["game_year"] = df["game_date"].apply(
            lambda d: d.year if isinstance(d, date) else None
        )

    # Drop rows missing the unique key
    df = df.dropna(subset=["game_pk", "at_bat_number", "pitch_number"])

    # Convert pandas NA → None so psycopg2 doesn't choke
    df = df.where(pd.notna(df), other=None)

    return df


def dates_in_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def run(mode: str, specific_date: str = None, range_start: str = None, range_end: str = None):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if mode == "daily":
            yesterday = date.today() - timedelta(days=1)
            date_str = yesterday.strftime("%Y-%m-%d")
            rows = fetch_and_upsert(date_str, db)
            log_fetch(db, yesterday, rows, "success")

        elif mode == "date":
            d = date.fromisoformat(specific_date)
            rows = fetch_and_upsert(specific_date, db)
            log_fetch(db, d, rows, "success")

        elif mode == "range":
            start = date.fromisoformat(range_start)
            end = date.fromisoformat(range_end)
            already_fetched = get_already_fetched(db)
            for d in dates_in_range(start, end):
                if d in already_fetched:
                    print(f"  Skipping {d} (already fetched)")
                    continue
                date_str = d.strftime("%Y-%m-%d")
                try:
                    rows = fetch_and_upsert(date_str, db)
                    log_fetch(db, d, rows, "success")
                except Exception:
                    traceback.print_exc()
                    log_fetch(db, d, 0, "error")
                time.sleep(2)  # be polite to Baseball Savant

        elif mode == "init":
            already_fetched = get_already_fetched(db)
            today = date.today()
            season_start = SEASON_START.get(DEFAULT_SEASON, date(DEFAULT_SEASON, 3, 27))
            # Don't fetch today or future dates
            end = min(today - timedelta(days=1), date(DEFAULT_SEASON, 11, 5))

            if end < season_start:
                print("Season hasn't started yet or no completed games to load.")
                return

            print(f"Initial load: {season_start} → {end}")
            print(f"Already fetched {len(already_fetched)} days, will skip those.\n")

            for d in dates_in_range(season_start, end):
                if d in already_fetched:
                    print(f"  Skipping {d} (already fetched)")
                    continue
                date_str = d.strftime("%Y-%m-%d")
                try:
                    rows = fetch_and_upsert(date_str, db)
                    log_fetch(db, d, rows, "success")
                except Exception:
                    traceback.print_exc()
                    log_fetch(db, d, 0, "error")
                time.sleep(3)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Statcast data")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init", action="store_true", help="Load full season history")
    group.add_argument("--daily", action="store_true", help="Fetch yesterday (default)")
    group.add_argument("--date", type=str, help="Fetch a specific date (YYYY-MM-DD)")
    group.add_argument("--range", nargs=2, metavar=("START", "END"), help="Fetch date range")

    args = parser.parse_args()

    if args.init:
        run("init")
    elif args.date:
        run("date", specific_date=args.date)
    elif args.range:
        run("range", range_start=args.range[0], range_end=args.range[1])
    else:
        run("daily")
