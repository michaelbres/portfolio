"""
Home run probability model.

For each batter-game combination:
    adjusted_hr_rate = batter_hr_rate × pitcher_hr_factor × park_hr_factor × weather_hr_factor
    lambda_hr = adjusted_hr_rate × expected_PA
    P(at least 1 HR) = 1 - exp(-lambda_hr)

Uses Poisson approximation — appropriate because individual HR events are rare
(~3.5% per PA) and approximately independent within a game.
"""

from __future__ import annotations

import math

from fair_value.win_probability import prob_to_american, american_to_prob


def compute_batter_hr_prob(
    hr_rate_blended: float,
    pitcher_hr_factor: float,
    park_hr_factor: float,
    weather_hr_factor: float,
    expected_pa: float,
) -> dict:
    """
    Compute the probability that a single batter hits at least 1 HR in this game.

    Parameters
    ----------
    hr_rate_blended    Batter's blended HR/PA rate (already regressed + split-adjusted)
    pitcher_hr_factor  Pitcher HR allowed rate / league avg (>1 = HR-prone pitcher)
    park_hr_factor     HR-specific park factor
    weather_hr_factor  Temperature + wind HR adjustment (1.0 = neutral)
    expected_pa        Expected plate appearances for this lineup slot

    Returns dict with hr_lambda, model_hr_prob, fair_hr_odds.
    """
    adjusted_rate = hr_rate_blended * pitcher_hr_factor * park_hr_factor * weather_hr_factor

    # Sanity clamp: no batter has a >15% HR rate per PA
    adjusted_rate = max(0.001, min(0.15, adjusted_rate))

    hr_lambda = adjusted_rate * expected_pa

    # P(HR >= 1) = 1 - P(HR = 0) = 1 - e^(-lambda)
    model_prob = 1.0 - math.exp(-hr_lambda)

    # Clamp for odds conversion sanity
    model_prob = max(0.005, min(0.95, model_prob))

    return {
        "adjusted_hr_rate": round(adjusted_rate, 5),
        "hr_lambda":        round(hr_lambda, 4),
        "model_hr_prob":    round(model_prob, 4),
        "fair_hr_odds":     prob_to_american(model_prob),
    }


def compute_game_hr_totals(player_results: list[dict]) -> dict:
    """
    Aggregate individual batter HR lambdas into team and game totals.

    Parameters
    ----------
    player_results  List of dicts, each with 'team', 'hr_lambda'.

    Returns dict with home/away team HR lambda and game total.
    """
    home_lambda = 0.0
    away_lambda = 0.0

    for p in player_results:
        lam = p.get("hr_lambda", 0.0)
        if p.get("is_home"):
            home_lambda += lam
        else:
            away_lambda += lam

    game_total = home_lambda + away_lambda

    # P(team hits at least 1 HR)
    home_hr_prob = 1.0 - math.exp(-home_lambda) if home_lambda > 0 else 0.0
    away_hr_prob = 1.0 - math.exp(-away_lambda) if away_lambda > 0 else 0.0

    return {
        "home_team_hr_lambda": round(home_lambda, 3),
        "away_team_hr_lambda": round(away_lambda, 3),
        "game_total_hr_lambda": round(game_total, 3),
        "home_team_hr_prob": round(home_hr_prob, 4),
        "away_team_hr_prob": round(away_hr_prob, 4),
    }


def weather_hr_factor(temp_f: float | None, wind_mph_to_cf: float | None) -> float:
    """
    Compute HR-specific weather adjustment.

    Temperature: +1.5% HR carry per °F above 72°F baseline.
    Wind: +1.0% HR carry per mph of wind component toward center field.
    """
    from .constants import HR_TEMP_BASELINE_F, HR_TEMP_COEFF_PER_F, HR_WIND_COEFF_PER_MPH

    factor = 1.0

    if temp_f is not None:
        delta = temp_f - HR_TEMP_BASELINE_F
        factor *= (1.0 + HR_TEMP_COEFF_PER_F * delta)

    if wind_mph_to_cf is not None:
        factor *= (1.0 + HR_WIND_COEFF_PER_MPH * wind_mph_to_cf)

    # Clamp to reasonable range
    return max(0.70, min(1.40, round(factor, 4)))
