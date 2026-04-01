"""
Fair value pipeline CLI.

Modes
─────
  --daily           Compute today's games (default)
  --date YYYY-MM-DD Compute a specific date
  --force           Recompute even if rows already exist for that date

Usage
─────
  python data_pipeline/fetch_fair_value.py
  python data_pipeline/fetch_fair_value.py --date 2025-04-15
  python data_pipeline/fetch_fair_value.py --date 2025-04-15 --force

Intended to run via cron or Render scheduled job:
  10:00 AM and 5:30 PM ET daily during the MLB season.
"""

import argparse
import logging
import os
import sys
from datetime import date

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import SessionLocal
from models import Base
from fair_value.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch_fair_value")

# Season is inferred from the target date automatically


def main():
    parser = argparse.ArgumentParser(description="Run MLB fair value pipeline")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--daily", action="store_true",
                       help="Compute today's games (default)")
    group.add_argument("--date", type=str, metavar="YYYY-MM-DD",
                       help="Compute a specific date")
    parser.add_argument("--force", action="store_true",
                        help="Recompute even if rows already exist")
    args = parser.parse_args()

    if args.date:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            log.error("Invalid date: %s. Use YYYY-MM-DD.", args.date)
            sys.exit(1)
    else:
        target = date.today()

    log.info("Starting fair value pipeline for %s (force=%s)", target, args.force)

    db = SessionLocal()
    try:
        outcome = run_pipeline(game_date=target, db=db, force=args.force)
        log.info("Done. %d game(s) computed.", outcome["games_computed"])
        if outcome.get("error"):
            log.warning("Pipeline message: %s", outcome["error"])
        for r in outcome["games"]:
            log.info(
                "  %-3s @ %-3s  home %+d / away %+d  λ %.2f / %.2f",
                r["away_team"], r["home_team"],
                r["home_fair_odds"], r["away_fair_odds"],
                r["home_lambda"], r["away_lambda"],
            )
    except Exception:
        log.exception("Pipeline failed")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
