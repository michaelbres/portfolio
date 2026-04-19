"""
Static constants for the MLB home run fair value model.

HR park factors differ significantly from run-scoring park factors.
Source: FanGraphs HR-specific park factors, 3-year weighted average (2022-2024).
"""

# ── League averages (2024 MLB season) ────────────────��───────────────────────
LEAGUE_AVG_HR_PER_PA = 0.035       # ~1 HR per 28.6 PA league-wide
LEAGUE_AVG_HR_PER_FB = 0.130       # league HR/FB rate (matches fair_value constants)
AVG_PA_PER_GAME_TEAM = 38.5        # typical team PA per 9-inning game

# ── Cross-season rolling sample sizes ────────────────────────────────────────
# Mirror the fair_value model's cross-season approach.
BATTER_SAMPLE_GAMES     = 200      # full sample: last 200 game appearances
RECENT_N_BATTER_GAMES   = 15       # recent sample for 50/50 blend

PITCHER_SAMPLE_STARTS   = 40       # full sample: last 40 starts
RECENT_N_STARTS         = 5        # recent sample for 50/50 blend

# ── Regression minimums ────────────────────���─────────────���───────────────────
# HR rates are noisier than wOBA — heavier regression needed.
MIN_PA_BATTER_HR_FULL   = 300      # ~75 games of PA before trusting HR rate
MIN_PA_BATTER_HR_RECENT = 50       # ~12 games
MIN_PA_PITCHER_HR_FULL  = 300      # pitcher HR-allowed rate
MIN_PA_PITCHER_HR_RECENT = 60

# ── Weather HR coefficients ──────────────────���───────────────────────────────
# HRs are more sensitive to temperature and wind than overall run scoring.
# ~1.5% HR probability increase per °F above baseline (vs 0.25% for runs).
HR_TEMP_BASELINE_F     = 72.0
HR_TEMP_COEFF_PER_F    = 0.015     # +1.5% HR carry per degree above baseline
HR_WIND_COEFF_PER_MPH  = 0.010     # +1.0% HR carry per mph wind toward CF

# ── Batting order PA exposure ─────────────���──────────────────────────────────
# Expected PA per game by batting order position (derived from PA_WEIGHTS).
# PA_WEIGHTS sum to 1.0; multiply by AVG_PA_PER_GAME_TEAM to get per-batter PA.
PA_WEIGHTS = [0.1195, 0.1148, 0.1122, 0.1088, 0.1055, 0.1021, 0.0988, 0.0954, 0.0922]

def expected_pa(batting_order: int) -> float:
    """Expected PA for a batter in a given lineup slot (1-indexed)."""
    idx = max(0, min(8, batting_order - 1))
    return PA_WEIGHTS[idx] * AVG_PA_PER_GAME_TEAM

# ── HR-specific park factors ─────────────────────────────────────────────────
# These differ from run-scoring park factors. E.g., Yankee Stadium is a
# strong HR park (short porch in right) but neutral for overall runs.
HR_PARK_FACTORS: dict[str, float] = {
    "NYY": 1.22,   # Yankee Stadium — short porch in right
    "CIN": 1.18,   # Great American Ball Park
    "COL": 1.15,   # Coors Field (extreme for runs, less so for HR relative to total offense)
    "PHI": 1.12,   # Citizens Bank Park
    "BAL": 1.10,   # Camden Yards
    "BOS": 1.08,   # Fenway Park — Green Monster creates doubles, but HR-friendly dimensions
    "CHC": 1.07,   # Wrigley Field — wind-dependent but historically HR-friendly
    "MIL": 1.05,   # American Family Field
    "TOR": 1.04,   # Rogers Centre
    "TEX": 1.03,   # Globe Life Field
    "MIN": 1.03,   # Target Field
    "ATL": 1.02,   # Truist Park
    "WSH": 1.01,   # Nationals Park
    "ARI": 1.01,   # Chase Field
    "HOU": 1.00,   # Minute Maid Park
    "LAD": 1.00,   # Dodger Stadium
    "NYM": 0.98,   # Citi Field
    "STL": 0.97,   # Busch Stadium
    "CLE": 0.96,   # Progressive Field
    "DET": 0.96,   # Comerica Park — deep center
    "PIT": 0.95,   # PNC Park
    "KC":  0.95,   # Kauffman Stadium
    "KCR": 0.95,
    "LAA": 0.95,   # Angel Stadium
    "SEA": 0.93,   # T-Mobile Park
    "TB":  0.92,   # Tropicana Field
    "TBR": 0.92,
    "CWS": 0.92,   # Guaranteed Rate Field
    "CHW": 0.92,
    "OAK": 0.90,   # Oakland / Sacramento
    "ATH": 0.90,
    "MIA": 0.88,   # loanDepot park — deep, humid
    "SD":  0.85,   # Petco Park
    "SDP": 0.85,
    "SF":  0.82,   # Oracle Park — heaviest HR suppression in MLB
    "SFG": 0.82,
}

TEAM_ALIASES: dict[str, str] = {
    "SFG": "SF",
    "SDP": "SD",
    "KCR": "KC",
    "TBR": "TB",
    "CHW": "CWS",
    "ATH": "OAK",
    "WSN": "WSH",
}

def hr_park_factor(home_team: str) -> float:
    """Look up HR-specific park factor, defaulting to 1.0."""
    team = TEAM_ALIASES.get(home_team, home_team)
    return HR_PARK_FACTORS.get(team, 1.00)

# Model version
MODEL_VERSION = "1.0"
