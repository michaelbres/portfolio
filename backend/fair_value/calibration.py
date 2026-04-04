"""
Model calibration utilities.

Three complementary techniques are implemented:

1. Platt Scaling (post-hoc calibration)
   ────────────────────────────────────
   A single-feature logistic regression trained on (raw_prob → outcome) pairs.
   Transforms raw model output so the calibrated probabilities match historical
   frequencies.  Coefficients (A, B) are stored in calibration_coeffs.json and
   re-fit nightly by nightly_calibration.py.

   Formula: logit(p_cal) = A · logit(p_raw) + B
       Equivalently: p_cal = sigmoid(A · logit(p_raw) + B)

   A=1, B=0 is the identity (no correction) — the starting default.

2. Bayesian Market Blend
   ──────────────────────
   When a market closing line is available, blend the Platt-calibrated model
   probability toward the market as a Bayesian update:

       p_final = (1 − w) · p_model + w · p_market

   The market weight w starts at MARKET_BLEND_WEIGHT (default 0.25) and can
   be increased as game time approaches (time-decay option).

3. Residual Tracking
   ──────────────────
   `compute_delta` stores (model_prob, market_prob, outcome) in the
   FairValueCalibration table via the nightly script.
   `rolling_delta_stats` reads that table to report the 7-day mean / std
   of (model − market) residuals and flags if drift exceeds a threshold.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import date, timedelta
from typing import Optional

# sqlalchemy is imported lazily inside functions that need it so this module
# can be loaded in environments without a DB connection (e.g. CLI utilities).

log = logging.getLogger(__name__)

# Path to the JSON file that stores the fitted Platt coefficients
_COEFFS_PATH = os.path.join(os.path.dirname(__file__), "calibration_coeffs.json")

# Default (identity) coefficients
_DEFAULT_COEFFS = {"platt_A": 1.0, "platt_B": 0.0, "n_games": 0,
                   "last_updated": None, "rolling_7d_mean_delta": None}

# Market blend weight when a closing line is available
MARKET_BLEND_WEIGHT = 0.25   # 25% weight to market; 75% to model


# ── Coefficient I/O ───────────────────────────────────────────────────────────

def load_coeffs() -> dict:
    """Load Platt coefficients from disk (or return defaults if absent)."""
    try:
        with open(_COEFFS_PATH) as f:
            return {**_DEFAULT_COEFFS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULT_COEFFS)


def save_coeffs(coeffs: dict) -> None:
    try:
        with open(_COEFFS_PATH, "w") as f:
            json.dump(coeffs, f, indent=2, default=str)
    except Exception as exc:
        log.error("Could not save calibration coefficients: %s", exc)


# ── Platt scaling ─────────────────────────────────────────────────────────────

def _logit(p: float) -> float:
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def platt_scale(raw_prob: float,
                A: float = 1.0,
                B: float = 0.0) -> float:
    """
    Apply Platt scaling: p_cal = sigmoid(A · logit(p_raw) + B).
    Identity at A=1, B=0.
    """
    return _sigmoid(A * _logit(raw_prob) + B)


def fit_platt(raw_probs: list[float],
              outcomes: list[int],
              lr: float = 0.05,
              epochs: int = 1000) -> tuple[float, float]:
    """
    Fit Platt scaling coefficients via gradient descent on binary cross-entropy.

    Parameters
    ----------
    raw_probs : Model's raw home-win probabilities (0–1).
    outcomes  : Actual home-win outcomes (1 = home win, 0 = away win).
    lr        : Learning rate.
    epochs    : Number of gradient steps.

    Returns (A, B) — the fitted coefficients.
    """
    if len(raw_probs) < 30:
        log.info("Platt fit skipped: only %d samples (need ≥30)", len(raw_probs))
        return 1.0, 0.0

    A, B = 1.0, 0.0
    n = len(raw_probs)

    for _ in range(epochs):
        dA = dB = 0.0
        for p_raw, y in zip(raw_probs, outcomes):
            logit_p = _logit(p_raw)
            p_cal   = _sigmoid(A * logit_p + B)
            err     = p_cal - y          # gradient of cross-entropy
            dA     += err * logit_p
            dB     += err
        A -= lr * dA / n
        B -= lr * dB / n

    log.info("Platt fit: A=%.4f  B=%.4f  (n=%d)", A, B, n)
    return round(A, 4), round(B, 4)


# ── Bayesian market blend ─────────────────────────────────────────────────────

def bayesian_blend(
    model_prob:    float,
    market_prob:   Optional[float],
    weight:        float = MARKET_BLEND_WEIGHT,
) -> float:
    """
    Blend model probability toward the market closing line.

    Parameters
    ----------
    model_prob   Platt-calibrated model probability (0–1).
    market_prob  No-vig market implied probability.  None → no blend.
    weight       Market weight [0, 1].  0 = pure model; 1 = pure market.

    Returns the final blended probability.
    """
    if market_prob is None or weight <= 0:
        return model_prob
    weight = max(0.0, min(1.0, weight))
    return (1.0 - weight) * model_prob + weight * market_prob


# ── Full calibration pipeline ─────────────────────────────────────────────────

def calibrated_prob(
    raw_prob:      float,
    market_prob:   Optional[float] = None,
    market_weight: float = MARKET_BLEND_WEIGHT,
) -> float:
    """
    Apply Platt scaling (from saved coefficients) then blend with market.
    This is the single function the pipeline calls for a final probability.
    """
    coeffs     = load_coeffs()
    A, B       = coeffs["platt_A"], coeffs["platt_B"]
    p_platt    = platt_scale(raw_prob, A, B)
    return bayesian_blend(p_platt, market_prob, market_weight)


# ── Residual / delta utilities ────────────────────────────────────────────────

def rolling_delta_stats(db: "Session", days: int = 7) -> dict:
    """
    Compute rolling statistics of (model_home_prob − closing_home_prob)
    over the last *days* calendar days from the FairValueCalibration table.

    Returns dict: {mean, std, n, flagged}
      flagged=True if |mean| > 0.02 (2pp threshold for auto-reweight trigger).
    """
    from sqlalchemy import text
    cutoff = date.today() - timedelta(days=days)
    try:
        rows = db.execute(text("""
            SELECT prob_delta
            FROM fair_value_calibration
            WHERE game_date >= :cutoff
              AND prob_delta IS NOT NULL
            ORDER BY game_date DESC
        """), {"cutoff": cutoff}).fetchall()
    except Exception as exc:
        log.warning("rolling_delta_stats query failed: %s", exc)
        return {"mean": None, "std": None, "n": 0, "flagged": False}

    deltas = [float(r.prob_delta) for r in rows]
    n = len(deltas)
    if n == 0:
        return {"mean": None, "std": None, "n": 0, "flagged": False}

    mean = sum(deltas) / n
    std  = math.sqrt(sum((d - mean) ** 2 for d in deltas) / n) if n > 1 else 0.0

    return {
        "mean":    round(mean, 4),
        "std":     round(std,  4),
        "n":       n,
        "flagged": abs(mean) > 0.02,
    }
