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
    OFFENSE_RATIO_SIGMA,
    XFIP_RATIO_SIGMA,
    NONLINEAR_THRESHOLD,
    NONLINEAR_AMP,
    CAUCHY_BLEND_WEIGHT,
)


# ── Non-linear Z-score weighting (Step 1) ────────────────────────────────────

def _nonlinear_ratio(ratio: float, sigma: float) -> float:
    """
    Non-linear stretch for metric ratios beyond NONLINEAR_THRESHOLD standard
    deviations from 1.0 (league average).

    For |z| > threshold: excess SDs are amplified by (1 + NONLINEAR_AMP),
    so extreme teams have a disproportionately larger impact on lambda.

    Examples (sigma=0.065, threshold=2.0, amp=0.50):
      ratio=0.789 (z=-3.25) → 0.748  (bad lineup penalised more)
      ratio=1.199 (z=+3.06) → 1.232  (great lineup rewarded more)
      ratio=1.0   (z=0)     → 1.0    (unchanged)
    """
    z = (ratio - 1.0) / sigma
    if abs(z) <= NONLINEAR_THRESHOLD:
        return ratio
    excess   = abs(z) - NONLINEAR_THRESHOLD
    new_z    = abs(z) + excess * NONLINEAR_AMP
    delta    = new_z * sigma
    return 1.0 + delta if ratio >= 1.0 else 1.0 - delta


# ── Cauchy fat-tail win probability (Step 2) ──────────────────────────────────

def _cauchy_win_prob(lambda_home: float, lambda_away: float,
                     r: float = NEGBIN_DISPERSION) -> float:
    """
    P(home wins) via Cauchy CDF: P = 0.5 + arctan(diff / scale) / π.

    Heavier tails than NegBin → explicitly models real-world run-scoring
    uncertainty; slightly reduces over-confidence in large-lambda-gap games.

    Scale is the square root of the combined NegBin variance, scaled by 0.45
    to keep the Cauchy win probabilities in a sensible range.
    """
    diff  = lambda_home - lambda_away
    var_h = lambda_home + lambda_home * lambda_home / r
    var_a = lambda_away + lambda_away * lambda_away / r
    scale = max(0.1, (var_h + var_a) ** 0.5 * 0.45)
    return 0.5 + math.atan(diff / scale) / math.pi


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

    # Offensive quality — non-linear Z-score stretch for extreme lineups (Step 1)
    offense_factor = _nonlinear_ratio(
        lineup_woba / LEAGUE_AVG_WOBA,
        sigma=OFFENSE_RATIO_SIGMA,
    )

    # SP suppression — non-linear stretch for elite / terrible starters (Step 1)
    sp_suppression = _nonlinear_ratio(
        max(sp_xfip, 1.50) / LEAGUE_AVG_XFIP,
        sigma=XFIP_RATIO_SIGMA,
    )

    # Bullpen suppression via wOBA (xFIP less reliable for relief)
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
    Return P(home team wins) as a blend of NegBin convolution (75%) and
    Cauchy CDF (25%).

    The Cauchy component introduces fat-tail behaviour — it explicitly models
    the real-world uncertainty that the NegBin under-represents, preventing
    over-confidence on large lambda differentials (Step 2).
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

    p_negbin = p_home_wins + p_tie * EXTRAS_HOME_WIN_RATE

    if CAUCHY_BLEND_WEIGHT > 0:
        p_cauchy = _cauchy_win_prob(lambda_home, lambda_away, r=r)
        return (1.0 - CAUCHY_BLEND_WEIGHT) * p_negbin + CAUCHY_BLEND_WEIGHT * p_cauchy

    return p_negbin


# ── Three-segment lambda (Opener / Bulk / Residual BP) ───────────────────────

def compute_lambda_opener(
    lineup_woba:     float,
    opener_xfip:     float,
    opener_innings:  float,
    bulk_xfip:       float,
    bulk_innings:    float,
    bp_woba_allowed: float,
    park_factor:     float,
    is_home:         bool,
    defense_factor:  float = 1.0,
    hfa_factor:      Optional[float] = None,
    umpire_factor:   float = 1.0,
    team_run_factor: float = 1.0,
) -> float:
    """
    Three-segment λ for an Opener / Bulk pitcher / Residual bullpen strategy.

    Formula (LaTeX)
    ---------------
    λ = R_{inn} · f_{off} · \\bigl[
            f_{opr}  · IP_{opr}  +
            f_{bulk} · IP_{bulk} +
            f_{bp}   · IP_{rem}
        \\bigr] · f_{def} · f_{park} · f_{ump} · f_{hfa} · f_{top-down}

    where
      IP_{rem}   = 9 − IP_{opr} − IP_{bulk}
      f_{off}    = g(wOBA_{lineup} / wOBA_{LG})      non-linear offense ratio
      f_{opr}    = g(xFIP_{opr}   / xFIP_{LG})      non-linear opener suppression
      f_{bulk}   = g(xFIP_{bulk}  / xFIP_{LG})      non-linear bulk suppression
      f_{bp}     = wOBA_{bp} / wOBA_{LG}             linear residual BP suppression
      g(·)       = _nonlinear_ratio() (Step-1 Z-score amplification)
    """
    opener_innings = max(0.0, min(opener_innings, 9.0))
    bulk_innings   = max(0.0, min(bulk_innings, 9.0 - opener_innings))
    bp_innings     = max(0.0, 9.0 - opener_innings - bulk_innings)

    offense_factor = _nonlinear_ratio(
        lineup_woba / LEAGUE_AVG_WOBA, sigma=OFFENSE_RATIO_SIGMA)
    opener_supp    = _nonlinear_ratio(
        max(opener_xfip, 1.50) / LEAGUE_AVG_XFIP, sigma=XFIP_RATIO_SIGMA)
    bulk_supp      = _nonlinear_ratio(
        max(bulk_xfip, 1.50) / LEAGUE_AVG_XFIP, sigma=XFIP_RATIO_SIGMA)
    bp_supp        = max(bp_woba_allowed, 0.200) / LEAGUE_AVG_WOBA

    runs = RUNS_PER_INNING * offense_factor * (
        opener_supp * opener_innings
        + bulk_supp * bulk_innings
        + bp_supp   * bp_innings
    )

    lam = runs * defense_factor * park_factor * umpire_factor

    if hfa_factor is None:
        hfa_factor = HOME_LAMBDA_FACTOR
    lam *= hfa_factor if is_home else (1.0 / hfa_factor)
    lam *= (1.0 - TEAM_RUN_FACTOR_BLEND + TEAM_RUN_FACTOR_BLEND * team_run_factor)

    return max(lam, 0.5)


def composite_pitching_value(
    opener_xfip:    float,
    opener_innings: float,
    bulk_xfip:      float,
    bulk_innings:   float,
    bp_woba:        float,
) -> float:
    """
    Weighted Composite Pitching Value (CPV) — an ERA-scale reference metric.

    Formula (LaTeX)
    ---------------
    CPV = \\frac{
        IP_{opr} · xFIP_{opr} +
        IP_{bulk} · xFIP_{bulk} +
        IP_{rem}  · \\overline{xFIP}_{bp}
    }{9}

    where  \\overline{xFIP}_{bp} = wOBA_{bp} × (xFIP_{LG} / wOBA_{LG})

    Used for logging/display; not fed back into lambda computation.
    """
    bp_innings    = max(0.0, 9.0 - opener_innings - bulk_innings)
    xfip_bp_equiv = bp_woba * (LEAGUE_AVG_XFIP / LEAGUE_AVG_WOBA)
    return round(
        (opener_xfip    * opener_innings
         + bulk_xfip    * bulk_innings
         + xfip_bp_equiv * bp_innings) / 9.0,
        3,
    )


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
    # Opener scenario — set when is_opener_game() returns True.
    # home_opener_* describes the HOME team's pitching staff → affects lambda_away.
    # away_opener_* describes the AWAY team's pitching staff → affects lambda_home.
    home_opener_xfip:     Optional[float] = None,
    home_opener_inn:      Optional[float] = None,
    home_bulk_xfip:       Optional[float] = None,
    home_bulk_inn:        Optional[float] = None,
    away_opener_xfip:     Optional[float] = None,
    away_opener_inn:      Optional[float] = None,
    away_bulk_xfip:       Optional[float] = None,
    away_bulk_inn:        Optional[float] = None,
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

    # Home offense faces the AWAY team's pitching staff
    if away_opener_xfip is not None:
        lambda_home = compute_lambda_opener(
            lineup_woba=     home_lineup_woba,
            opener_xfip=     away_opener_xfip,
            opener_innings=  away_opener_inn,
            bulk_xfip=       away_bulk_xfip,
            bulk_innings=    away_bulk_inn,
            bp_woba_allowed= away_bp_woba,
            park_factor=     park_factor_val,
            is_home=         True,
            defense_factor=  away_defense_factor,
            hfa_factor=      home_hfa_factor,
            umpire_factor=   umpire_factor,
            team_run_factor= home_run_factor,
        )
    else:
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

    # Away offense faces the HOME team's pitching staff
    if home_opener_xfip is not None:
        lambda_away = compute_lambda_opener(
            lineup_woba=     away_lineup_woba,
            opener_xfip=     home_opener_xfip,
            opener_innings=  home_opener_inn,
            bulk_xfip=       home_bulk_xfip,
            bulk_innings=    home_bulk_inn,
            bp_woba_allowed= home_bp_woba,
            park_factor=     park_factor_val,
            is_home=         False,
            defense_factor=  home_defense_factor,
            hfa_factor=      home_hfa_factor,
            umpire_factor=   umpire_factor,
            team_run_factor= away_run_factor,
        )
    else:
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
