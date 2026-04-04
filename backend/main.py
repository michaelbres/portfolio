import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import mlb
from routers import fair_value


def _run_migrations():
    """
    Additive schema migrations — safe to run on every startup.
    Only adds columns/tables that don't exist yet; never drops or alters.
    """
    from sqlalchemy import text
    stmts = [
        # v2.0 — xFIP and weather carry factor
        "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS home_sp_xfip_blended FLOAT",
        "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS away_sp_xfip_blended FLOAT",
        "ALTER TABLE fair_value_games ADD COLUMN IF NOT EXISTS weather_carry_factor  FLOAT",
    ]
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))


Base.metadata.create_all(bind=engine)   # creates new tables (fair_value_calibration etc.)
_run_migrations()                        # adds new columns to existing tables

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
