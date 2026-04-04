"""
Nightly calibration script.

Runs at ~1:00 AM after games complete.  For each game played yesterday:

  1. Fetches the final score (home win / away win) from Statcast.
  2. Reads the model's morning probability from fair_value_games.
  3. Reads the closing-line probability from fair_value_games (market_odds field).
  4. Computes: delta = model_home_prob − closing_home_prob.
  5. Upserts a row into fair_value_calibration.
  6. Computes rolling 7-day delta stats; logs a warning if |mean| > 2pp.
  7. Re-fits Platt scaling coefficients and saves to calibration_coeffs.json.

Usage
─────
    python data_pipeline/nightly_calibration.py              # yesterday
    python data_pipeline/nightly_calibration.py --date 2026-04-01  # specific date
    python data_pipeline/nightly_calibration.py --refit      # force coefficient refit

Cron example (1 AM daily):
    0 1 * * * cd /home/user/portfolio && python data_pipeline/nightly_calibration.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

# Allow imports from backend/
sys.path.insert(0, "backend")

from database import SessionLocal
from models import FairValueGame, FairValueCalibration
from sqlalchemy import text
from sqlalchemy.orm import Session

from fair_value.calibration import (
    fit_platt,
    load_coeffs,
    save_coeffs,
    rolling_delta_stats,
)
from fair_value.win_probability import american_to_prob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger(__name__)


# ── Final score lookup ────────────────────────────────────────────────────────

def _fetch_final_scores(db: Session, target_date: date) -> dict[int, int]:
    """
    Infer game outcomes from Statcast data.
    Returns {game_pk: 1 (home win) | 0 (away win)}.
    Excludes ties (post_home_score == post_away_score).
    """
    rows = db.execute(text("""
        SELECT game_pk,
               MAX(post_home_score) AS final_home,
               MAX(post_away_score) AS final_away
        FROM statcast_pitches
        WHERE game_date = :gd
          AND inning   >= 9
        GROUP BY game_pk
    """), {"gd": target_date}).fetchall()

    outcomes: dict[int, int] = {}
    for r in rows:
        if r.final_home is None or r.final_away is None:
            continue
        if r.final_home == r.final_away:
            continue   # suspended game / tie
        outcomes[int(r.game_pk)] = 1 if r.final_home > r.final_away else 0

    return outcomes


# ── Process one date ──────────────────────────────────────────────────────────

def process_date(db: Session, target_date: date) -> int:
    """
    Upsert calibration rows for *target_date*.
    Returns number of rows written.
    """
    games = db.query(FairValueGame).filter(
        FairValueGame.game_date == target_date
    ).all()

    if not games:
        log.info("No model rows found for %s — skipping.", target_date)
        return 0

    outcomes = _fetch_final_scores(db, target_date)
    if not outcomes:
        log.info("No Statcast outcome data yet for %s.", target_date)
        return 0

    written = 0
    for game in games:
        outcome = outcomes.get(game.game_pk)
        if outcome is None:
            continue   # no outcome data for this game_pk yet

        # Model probability (raw, before Platt / blend)
        model_home_prob = game.home_win_prob   # post-calibration in v2.1
        if model_home_prob is None:
            continue

        # Closing line no-vig probability
        closing_home_prob: float | None = None
        if game.home_market_odds is not None and game.away_market_odds is not None:
            h = american_to_prob(game.home_market_odds)
            a = american_to_prob(game.away_market_odds)
            total = h + a
            closing_home_prob = h / total if total > 0 else None

        delta = None
        if closing_home_prob is not None:
            delta = round(model_home_prob - closing_home_prob, 4)

        model_brier  = round((model_home_prob - outcome) ** 2, 6)
        market_brier = (
            round((closing_home_prob - outcome) ** 2, 6)
            if closing_home_prob is not None else None
        )

        # Upsert
        existing = db.query(FairValueCalibration).filter(
            FairValueCalibration.game_pk == game.game_pk
        ).first()

        if existing is None:
            row = FairValueCalibration(game_pk=game.game_pk)
            db.add(row)
        else:
            row = existing

        row.game_date           = game.game_date
        row.home_team           = game.home_team
        row.away_team           = game.away_team
        row.model_home_prob     = model_home_prob
        row.model_away_prob     = game.away_win_prob
        row.closing_home_prob   = closing_home_prob
        row.closing_away_prob   = (1.0 - closing_home_prob) if closing_home_prob else None
        row.closing_source      = game.market_source
        row.prob_delta          = delta
        row.abs_delta           = abs(delta) if delta is not None else None
        row.outcome_home_win    = outcome
        row.model_brier         = model_brier
        row.market_brier        = market_brier
        row.home_lineup_woba    = game.home_lineup_woba
        row.away_lineup_woba    = game.away_lineup_woba
        row.total_lambda        = (
            (game.home_lambda or 0) + (game.away_lambda or 0)
        )

        written += 1

    db.commit()
    log.info("Wrote %d calibration rows for %s.", written, target_date)
    return written


# ── Platt re-fit ──────────────────────────────────────────────────────────────

def refit_platt(db: Session) -> None:
    """
    Re-fit Platt coefficients from all calibration rows with known outcomes.
    Saves updated coefficients to calibration_coeffs.json.
    """
    rows = db.execute(text("""
        SELECT model_home_prob, outcome_home_win
        FROM fair_value_calibration
        WHERE outcome_home_win IN (0, 1)
          AND model_home_prob  IS NOT NULL
        ORDER BY game_date
    """)).fetchall()

    if not rows:
        log.info("No calibration data for Platt fit.")
        return

    raw_probs = [float(r.model_home_prob) for r in rows]
    outcomes  = [int(r.outcome_home_win)  for r in rows]

    A, B = fit_platt(raw_probs, outcomes)

    coeffs = load_coeffs()
    coeffs["platt_A"]    = A
    coeffs["platt_B"]    = B
    coeffs["n_games"]    = len(raw_probs)
    coeffs["last_updated"] = str(date.today())

    # Store rolling 7-day mean delta for monitoring
    stats = rolling_delta_stats(db)
    coeffs["rolling_7d_mean_delta"] = stats["mean"]

    save_coeffs(coeffs)
    log.info("Platt updated: A=%.4f  B=%.4f  (n=%d)", A, B, len(raw_probs))

    if stats["flagged"]:
        log.warning(
            "DRIFT ALERT: 7-day mean delta = %.3f (>2pp threshold). "
            "Model is systematically mis-priced vs market. "
            "Review feature weights.",
            stats["mean"],
        )


# ── Bias report ───────────────────────────────────────────────────────────────

def bias_report(db: Session) -> None:
    """Log a bias report grouping residuals by game total (high vs low)."""
    rows = db.execute(text("""
        SELECT
            ROUND(total_lambda) AS total_bucket,
            COUNT(*)            AS n,
            AVG(prob_delta)     AS mean_delta,
            AVG(model_brier)    AS model_brier,
            AVG(market_brier)   AS market_brier
        FROM fair_value_calibration
        WHERE outcome_home_win IN (0, 1)
          AND prob_delta IS NOT NULL
        GROUP BY total_bucket
        ORDER BY total_bucket
    """)).fetchall()

    if not rows:
        return

    log.info("── Bias by game total (λ_home + λ_away) ──")
    log.info("  Total  │  n   │ Mean Δ  │ Model Brier │ Mkt Brier")
    for r in rows:
        log.info(
            "  %5.1f  │ %4d │ %+.4f  │    %.4f    │   %.4f",
            r.total_bucket or 0,
            r.n,
            r.mean_delta or 0,
            r.model_brier or 0,
            r.market_brier or 0,
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly fair-value calibration")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--refit", action="store_true",
                        help="Force re-fit of Platt coefficients")
    args = parser.parse_args()

    target = (
        date.fromisoformat(args.date)
        if args.date else
        date.today() - timedelta(days=1)
    )

    db = SessionLocal()
    try:
        written = process_date(db, target)

        if written > 0 or args.refit:
            refit_platt(db)
            bias_report(db)

        stats = rolling_delta_stats(db)
        log.info(
            "Rolling 7-day delta: mean=%.4f  std=%.4f  n=%d  flagged=%s",
            stats["mean"] or 0,
            stats["std"]  or 0,
            stats["n"],
            stats["flagged"],
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
