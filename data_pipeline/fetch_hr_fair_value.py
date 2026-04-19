"""
CLI entry point for the HR fair value pipeline.

Usage:
    python data_pipeline/fetch_hr_fair_value.py               # today's games
    python data_pipeline/fetch_hr_fair_value.py --date 2026-04-19
    python data_pipeline/fetch_hr_fair_value.py --force        # recompute
"""

import argparse
import logging
import sys
import os
from datetime import date

# Ensure backend modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import SessionLocal
from hr_fair_value.pipeline import run_hr_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run HR fair value pipeline")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--force", action="store_true", help="Force recompute even if data exists")
    args = parser.parse_args()

    game_date = date.fromisoformat(args.date) if args.date else date.today()

    db = SessionLocal()
    try:
        result = run_hr_pipeline(game_date, db, force=args.force)
        log.info("Result: %d games computed", result.get("games_computed", 0))
        if result.get("error"):
            log.warning("Error: %s", result["error"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
