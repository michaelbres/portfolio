import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base
from routers import mlb
from routers import fair_value

log = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

# ── Column migrations (ADD IF NOT EXISTS for existing deployments) ─────────────
# create_all only creates missing tables; use ALTER TABLE for new columns.
_COLUMN_MIGRATIONS = [
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS home_sp_xfip_blended FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS away_sp_xfip_blended FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS weather_carry_factor FLOAT",
    "ALTER TABLE statcast_pitches ADD COLUMN IF NOT EXISTS batter_name VARCHAR(100)",
    # Opening price tracking (set once on first pipeline run, never overwritten)
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS opening_home_odds INTEGER",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS opening_away_odds INTEGER",
    # Raw model probability (pre-market-anchor) — needed for EV display
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS home_model_prob FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS away_model_prob FLOAT",
    # Totals model
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS model_total FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS kalshi_total_line FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS kalshi_over_price FLOAT",
    "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS model_over_prob FLOAT",
]

try:
    with engine.connect() as conn:
        for stmt in _COLUMN_MIGRATIONS:
            conn.execute(text(stmt))
        conn.commit()
except Exception as exc:
    log.warning("Column migration skipped: %s", exc)

app = FastAPI(title="Portfolio API", version="1.0.0")

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mlb.router)
app.include_router(fair_value.router)


@app.get("/health")
def health():
    return {"status": "ok"}
