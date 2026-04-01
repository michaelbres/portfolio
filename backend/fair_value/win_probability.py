"""
Win probability and odds conversion utilities.

Model
─────
Each team's run scoring in a 9-inning game is modelled as Poisson(λ).
λ is built from:
    • Offense quality  (lineup wOBA vs opposing pitcher handedness)
    • SP suppression   (wOBA allowed × projected innings from pitch count)
    • Bullpen suppression (wOBA allowed × remaining innings)
    • Park run factor
    • Home-field advantage (λ multiplier)

P(home wins) is computed by enumerating the joint Poisson PMFs up to MAX_RUNS
and adding the tie probability × EXTRAS_HOME_WIN_RATE.

All math uses only the standard library (math module) — no scipy required.
"""

from __future__ import annotations

import math
from typing import Optional

from .constants import (
    LEAGUE_AVG_WOBA,
    RUNS_PER_INNING,
    HOME_LAMBDA_FACTOR,
    EXTRAS_HOME_WIN_RATE,
    MAX_RUNS,
    DEFAULT_PITCH_LIMIT,
)


# ── Poisson helpers ───────────────────────────────────────────────────────────

def _poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lam).  Uses log-space for numerical stability."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    log_p = -lam + k * math.log(lam) - sum(math.log(i) for i in range(1, k + 1))
    return math.exp(log_p)


def _build_pmf(lam: float, max_k: int = MAX_RUNS) -> list[float]:
    return [_poisson_pmf(k, lam) for k in range(max_k + 1)]


# ── Lambda (expected runs) computation ───────────────────────────────────────

def projected_innings(pitch_limit: int, pitches_per_inning: float,
                      max_innings: float = 7.0) -> float:
    """
    Convert a pitch limit to projected innings.
    Capped at max_innings (starters rarely go deeper even without a limit).
    """
    if pitches_per_inning <= 0:
        pitches_per_inning = 15.5
    innings = pitch_limit / pitches_per_inning
    return min(innings, max_innings)


def compute_lambda(
    lineup_woba:       float,
    sp_woba_allowed:   float,
    sp_innings:        float,
    bp_woba_allowed:   float,
    park_factor:       float,
    is_home:           bool,
) -> float:
    """
    Compute the Poisson λ (expected runs scored) for one team's offense.

    Parameters
    ----------
    lineup_woba       Weighted wOBA of the batting lineup vs opposing SP hand.
    sp_woba_allowed   Blended wOBA allowed by the opposing starting pitcher.
    sp_innings        Projected innings for the opposing SP.
    bp_woba_allowed   Fatigue-adjusted wOBA allowed by opposing bullpen.
    park_factor       Run environment multiplier for the home park.
    is_home           Whether this team is the home team.
    """
    sp_innings = max(0.0, min(sp_innings, 9.0))
    bp_innings = max(0.0, 9.0 - sp_innings)

    # Offensive quality relative to league average
    offense_factor = lineup_woba / LEAGUE_AVG_WOBA

    # Pitcher suppression: how much of league-average run rate they allow
    sp_suppression = max(sp_woba_allowed, 0.200) / LEAGUE_AVG_WOBA
    bp_suppression = max(bp_woba_allowed, 0.200) / LEAGUE_AVG_WOBA

    # Expected runs in each segment of the game
    sp_runs = RUNS_PER_INNING * offense_factor * sp_suppression * sp_innings
    bp_runs = RUNS_PER_INNING * offense_factor * bp_suppression * bp_innings

    lam = (sp_runs + bp_runs) * park_factor

    # Home-field advantage
    if is_home:
        lam *= HOME_LAMBDA_FACTOR
    else:
        lam /= HOME_LAMBDA_FACTOR

    return max(lam, 0.5)   # floor to avoid degenerate PMF


# ── Win probability ───────────────────────────────────────────────────────────

def win_probability(lambda_home: float, lambda_away: float) -> float:
    """
    Return P(home team wins) using the Poisson model.
    Ties go to extra innings; home team wins extras at EXTRAS_HOME_WIN_RATE.
    """
    home_pmf = _build_pmf(lambda_home)
    away_pmf = _build_pmf(lambda_away)

    p_home_wins = 0.0
    p_tie       = 0.0

    for h in range(MAX_RUNS + 1):
        for a in range(MAX_RUNS + 1):
            p = home_pmf[h] * away_pmf[a]
            if h > a:
                p_home_wins += p
            elif h == a:
                p_tie += p

    p_home_wins += p_tie * EXTRAS_HOME_WIN_RATE
    return p_home_wins


# ── Odds conversion ───────────────────────────────────────────────────────────

def prob_to_american(p: float) -> int:
    """Convert win probability to American moneyline odds (no vig)."""
    p = max(0.001, min(0.999, p))
    if p >= 0.5:
        return round(-p / (1 - p) * 100)
    else:
        return round((1 - p) / p * 100)


def american_to_prob(odds: int) -> float:
    """Convert American moneyline odds to implied probability."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def strip_vig(home_odds: int, away_odds: int) -> tuple[float, float]:
    """
    Given two American moneyline odds (with vig), return (home_prob, away_prob)
    with the vig removed so they sum to 1.0.
    """
    home_impl = american_to_prob(home_odds)
    away_impl = american_to_prob(away_odds)
    total = home_impl + away_impl
    return home_impl / total, away_impl / total


# ── Full game computation ─────────────────────────────────────────────────────

def compute_game_fair_value(
    home_lineup_woba:    float,
    away_lineup_woba:    float,
    home_sp_woba:        float,
    away_sp_woba:        float,
    home_bp_woba:        float,
    away_bp_woba:        float,
    home_pitch_limit:    int,
    away_pitch_limit:    int,
    home_pitches_per_inn: float,
    away_pitches_per_inn: float,
    park_factor_val:     float,
) -> dict:
    """
    Top-level function: compute all model outputs for one game.

    Returns a dict with lambda values, win probabilities, and fair odds.
    """
    home_sp_inn = projected_innings(home_pitch_limit, home_pitches_per_inn)
    away_sp_inn = projected_innings(away_pitch_limit, away_pitches_per_inn)

    # Home team offense (faces away SP + away BP)
    lambda_home = compute_lambda(
        lineup_woba=     home_lineup_woba,
        sp_woba_allowed= away_sp_woba,
        sp_innings=      away_sp_inn,
        bp_woba_allowed= away_bp_woba,
        park_factor=     park_factor_val,
        is_home=         True,
    )

    # Away team offense (faces home SP + home BP)
    lambda_away = compute_lambda(
        lineup_woba=     away_lineup_woba,
        sp_woba_allowed= home_sp_woba,
        sp_innings=      home_sp_inn,
        bp_woba_allowed= home_bp_woba,
        park_factor=     park_factor_val,
        is_home=         False,
    )

    home_wp = win_probability(lambda_home, lambda_away)
    away_wp = 1.0 - home_wp

    return {
        "home_sp_proj_innings":  round(home_sp_inn, 2),
        "away_sp_proj_innings":  round(away_sp_inn, 2),
        "home_lambda":           round(lambda_home, 3),
        "away_lambda":           round(lambda_away, 3),
        "home_win_prob":         round(home_wp, 4),
        "away_win_prob":         round(away_wp, 4),
        "home_fair_odds":        prob_to_american(home_wp),
        "away_fair_odds":        prob_to_american(away_wp),
    }
