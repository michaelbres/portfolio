"""
Win probability and odds conversion utilities.

Model
─────
Each team's run scoring in a 9-inning game is modelled as
NegativeBinomial(μ, r) — a more accurate choice than Poisson because MLB
run-scoring is overdispersed (real variance ≈ 2.5× Poisson for λ≈4.5 runs).

λ (mean runs scored, μ) is built from:
    • Offense quality  (lineup wOBA vs opposing pitcher handedness)
    • SP suppression   (xFIP-based: sp_xfip / LEAGUE_AVG_XFIP)
    • Bullpen suppression (wOBA allowed × remaining innings)
    • Team defense factor (actual vs expected wOBA on contact while fielding)
    • Park run factor
    • Team-specific home-field advantage (λ multiplier)
    • Umpire run factor (default 1.0)

P(home wins) is computed by enumerating the joint NegBin PMFs up to MAX_RUNS
and adding the tie probability × EXTRAS_HOME_WIN_RATE.

Power calibration (alpha parameter) is available but defaults to 1.0 (identity).

All math uses only the standard library (math module) — no scipy required.
"""

from __future__ import annotations

import math
from typing import Optional

from .constants import (
    LEAGUE_AVG_WOBA,
    LEAGUE_AVG_XFIP,
    RUNS_PER_INNING,
    HOME_LAMBDA_FACTOR,
    EXTRAS_HOME_WIN_RATE,
    MAX_RUNS,
    DEFAULT_PITCH_LIMIT,
    NEGBIN_DISPERSION,
    CALIBRATION_ALPHA,
    TEAM_RUN_FACTOR_BLEND,
)


# ── Negative Binomial PMF ─────────────────────────────────────────────────────

def _negbin_pmf(k: int, mu: float, r: float = NEGBIN_DISPERSION) -> float:
    """
    P(X = k) for X ~ NegBin(mean=mu, dispersion=r).

    log P = lgamma(k+r) - lgamma(r) - lgamma(k+1)
          + r·log(r/(r+μ)) + k·log(μ/(r+μ))

    Variance = μ + μ²/r  (Poisson is recovered as r → ∞).
    """
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    p_r   = r / (r + mu)         # success probability in NegBin parameterisation
    p_mu  = mu / (r + mu)
    log_p = (
        math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
        + r * math.log(p_r)
        + k * math.log(p_mu)
    )
    return math.exp(log_p)


def _build_pmf(mu: float, max_k: int = MAX_RUNS,
               r: float = NEGBIN_DISPERSION) -> list[float]:
    return [_negbin_pmf(k, mu, r) for k in range(max_k + 1)]


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
    sp_xfip:           float,
    sp_innings:        float,
    bp_woba_allowed:   float,
    park_factor:       float,
    is_home:           bool,
    defense_factor:    float = 1.0,
    hfa_factor:        Optional[float] = None,
    umpire_factor:     float = 1.0,
    team_run_factor:   float = 1.0,
) -> float:
    """
    Compute the NegBin μ (expected runs scored) for one team's offense.

    Parameters
    ----------
    lineup_woba       Weighted wOBA of the batting lineup vs opposing SP hand.
    sp_xfip           Blended xFIP of the opposing starting pitcher (ERA scale).
    sp_innings        Projected innings for the opposing SP.
    bp_woba_allowed   Fatigue-adjusted wOBA allowed by opposing bullpen.
    park_factor       Run environment multiplier for the home park.
    is_home           Whether this team is the home team.
    defense_factor    Fielding-team defensive quality (actual/xwOBA on contact).
                      Pass the OPPOSING team's factor.  >1 = worse defense.
    hfa_factor        Home-team-specific λ multiplier.  None → global default.
    umpire_factor     Umpire zone tightness multiplier (default 1.0).
    team_run_factor   Season RS/G relative to league avg (1.0 = neutral).
                      Blended at TEAM_RUN_FACTOR_BLEND (30%) as a top-down anchor.
    """
    sp_innings = max(0.0, min(sp_innings, 9.0))
    bp_innings = max(0.0, 9.0 - sp_innings)

    # Offensive quality relative to league average
    offense_factor = lineup_woba / LEAGUE_AVG_WOBA

    # SP suppression via xFIP (normalised to league average xFIP)
    sp_suppression = max(sp_xfip, 1.50) / LEAGUE_AVG_XFIP

    # Bullpen suppression via wOBA (same as before — xFIP less reliable for relief)
    bp_suppression = max(bp_woba_allowed, 0.200) / LEAGUE_AVG_WOBA

    # Expected runs per segment
    sp_runs = RUNS_PER_INNING * offense_factor * sp_suppression * sp_innings
    bp_runs = RUNS_PER_INNING * offense_factor * bp_suppression * bp_innings

    lam = (sp_runs + bp_runs) * defense_factor * park_factor * umpire_factor

    # Home-field advantage
    if hfa_factor is None:
        hfa_factor = HOME_LAMBDA_FACTOR
    if is_home:
        lam *= hfa_factor
    else:
        lam /= hfa_factor

    # Top-down anchor: blend 30% of team's actual RS/G factor
    # lambda = lambda * (1 - blend + blend * factor)
    # Bad team (factor=0.80): lambda * 0.94;  Good team (factor=1.20): lambda * 1.06
    lam *= (1.0 - TEAM_RUN_FACTOR_BLEND + TEAM_RUN_FACTOR_BLEND * team_run_factor)

    return max(lam, 0.5)   # floor to avoid degenerate PMF


# ── Calibration ───────────────────────────────────────────────────────────────

def calibrate_prob(p: float, alpha: float = CALIBRATION_ALPHA) -> float:
    """
    Power calibration: p_cal = 1 / (1 + ((1−p)/p)^alpha).

    alpha = 1.0 → identity (no effect, default).
    alpha < 1.0 → shrink toward 0.5 (useful if model is overconfident).
    alpha > 1.0 → push away from 0.5 (sharpen predictions).
    """
    p = max(0.001, min(0.999, p))
    if alpha == 1.0:
        return p
    odds = (1.0 - p) / p
    return 1.0 / (1.0 + odds ** alpha)


# ── Win probability ───────────────────────────────────────────────────────────

def win_probability(lambda_home: float, lambda_away: float,
                    r: float = NEGBIN_DISPERSION) -> float:
    """
    Return P(home team wins) using the Negative Binomial model.
    Ties go to extra innings; home team wins extras at EXTRAS_HOME_WIN_RATE.
    """
    home_pmf = _build_pmf(lambda_home, r=r)
    away_pmf = _build_pmf(lambda_away, r=r)

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
    home_lineup_woba:     float,
    away_lineup_woba:     float,
    home_sp_xfip:         float,
    away_sp_xfip:         float,
    home_bp_woba:         float,
    away_bp_woba:         float,
    home_pitch_limit:     int,
    away_pitch_limit:     int,
    home_pitches_per_inn: float,
    away_pitches_per_inn: float,
    park_factor_val:      float,
    home_defense_factor:  float = 1.0,
    away_defense_factor:  float = 1.0,
    home_hfa_factor:      Optional[float] = None,
    umpire_factor:        float = 1.0,
    calibration_alpha:    float = CALIBRATION_ALPHA,
    home_run_factor:      float = 1.0,
    away_run_factor:      float = 1.0,
) -> dict:
    """
    Top-level function: compute all model outputs for one game.

    Defense factors:
      home_defense_factor  = HOME team fielding quality (applied to lambda_away)
      away_defense_factor  = AWAY team fielding quality (applied to lambda_home)

    Run factors (top-down anchor):
      home_run_factor  = home team RS/G / league avg this season
      away_run_factor  = away team RS/G / league avg this season

    Returns a dict with lambda values, win probabilities, and fair odds.
    """
    home_sp_inn = projected_innings(home_pitch_limit, home_pitches_per_inn)
    away_sp_inn = projected_innings(away_pitch_limit, away_pitches_per_inn)

    # Home offense faces away SP + away BP + away defense
    lambda_home = compute_lambda(
        lineup_woba=     home_lineup_woba,
        sp_xfip=         away_sp_xfip,
        sp_innings=      away_sp_inn,
        bp_woba_allowed= away_bp_woba,
        park_factor=     park_factor_val,
        is_home=         True,
        defense_factor=  away_defense_factor,
        hfa_factor=      home_hfa_factor,
        umpire_factor=   umpire_factor,
        team_run_factor= home_run_factor,
    )

    # Away offense faces home SP + home BP + home defense
    lambda_away = compute_lambda(
        lineup_woba=     away_lineup_woba,
        sp_xfip=         home_sp_xfip,
        sp_innings=      home_sp_inn,
        bp_woba_allowed= home_bp_woba,
        park_factor=     park_factor_val,
        is_home=         False,
        defense_factor=  home_defense_factor,
        hfa_factor=      home_hfa_factor,
        umpire_factor=   umpire_factor,
        team_run_factor= away_run_factor,
    )

    home_wp_raw = win_probability(lambda_home, lambda_away)
    home_wp     = calibrate_prob(home_wp_raw, calibration_alpha)
    away_wp     = 1.0 - home_wp

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
