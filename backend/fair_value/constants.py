"""
Static constants for the MLB fair value model.

Park factors: 2023-2024 average run factor (1.0 = league average).
Positive parks inflate scoring; negative parks suppress it.
Source: FanGraphs park factors, 3-year weighted average.
"""

# ── League averages (2024 MLB season) ────────────────────────────────────────
LEAGUE_AVG_WOBA = 0.317
LEAGUE_AVG_RUNS_PER_GAME = 4.51
RUNS_PER_INNING = LEAGUE_AVG_RUNS_PER_GAME / 9.0   # ~0.501

# wOBA scale (converts wOBA to wRAA per PA)
WOBA_SCALE = 1.15

# Default pitch limit when we have no data on a pitcher
DEFAULT_PITCH_LIMIT = 95

# ── Cross-season rolling sample sizes ────────────────────────────────────────
# Stats are pulled from the last N games/starts regardless of season year.
# This ensures meaningful samples even at the start of a new season.

PITCHER_SAMPLE_STARTS   = 40   # full sample: last 40 starts (~1 full season)
RECENT_N_STARTS         = 5    # recent sample for the 50/50 blend

BATTER_SAMPLE_GAMES     = 200  # full sample: last 200 game appearances
RECENT_N_BATTER_GAMES   = 15   # recent sample for the 50/50 blend

BULLPEN_SAMPLE_GAMES    = 40   # team games used to identify/evaluate relievers

# Minimum PA before a sample is trusted; below this we regress toward league avg
MIN_PA_PITCHER_FULL     = 250  # ~3 starts
MIN_PA_PITCHER_RECENT   = 60   # ~1 start
MIN_PA_BATTER_FULL      = 150  # ~37 games
MIN_PA_BATTER_RECENT    = 25   # ~6 games

# Minimum IP thresholds for xFIP regression
MIN_IP_PITCHER_FULL     = 80   # ~13 starts
MIN_IP_PITCHER_RECENT   = 20   # ~3-4 starts

# ── xFIP constants ────────────────────────────────────────────────────────────
# xFIP = ((13 × FB × lgHR/FB) + (3 × (BB + HBP)) - (2 × K)) / IP + cFIP
CFIP              = 3.20    # constant to center xFIP around league ERA
LG_HR_PER_FB      = 0.130   # league average HR per fly ball
LEAGUE_AVG_XFIP   = 4.26    # league average xFIP (ERA scale, for normalisation)

# ── Negative binomial dispersion ───────────────────────────────────────────────
# NegBin variance = μ + μ²/r.  Lower r = more overdispersion.
# r=3.0 reflects observed overdispersion in MLB run scoring (~2.5× Poisson var).
NEGBIN_DISPERSION = 3.0

# ── Calibration ────────────────────────────────────────────────────────────────
# Power calibration: p_cal = 1/(1 + ((1-p)/p)^alpha).
# alpha=1.0 is identity; tune after accumulating historical game results.
CALIBRATION_ALPHA = 1.0

# ── Team defense factor bounds ─────────────────────────────────────────────────
# Factor = (actual wOBA on contact) / (xwOBA on contact) when fielding.
# Capped to prevent outliers from dominating.
DEFENSE_FACTOR_FLOOR  = 0.93
DEFENSE_FACTOR_CAP    = 1.07
MIN_BIP_DEFENSE       = 600   # min balls-in-play before defence factor is trusted

# Home field advantage: multiplier applied to home lambda (≈ +3.3% run scoring)
# Calibrated so equal teams produce ~54% home win rate.
HOME_LAMBDA_FACTOR = 1.033

# Extra-innings home win rate (batting last is a slight edge)
EXTRAS_HOME_WIN_RATE = 0.505

# Maximum runs to enumerate in the Poisson convolution
MAX_RUNS = 28

# Batting order PA weights (positions 1-9).
# Reflects that leadoff hitters get more plate appearances over 9 innings.
# Values normalised so sum = 1.0.
PA_WEIGHTS = [0.1195, 0.1148, 0.1122, 0.1088, 0.1055, 0.1021, 0.0988, 0.0954, 0.0922]
# position index:  1       2       3       4       5       6       7       8       9

# Bullpen fatigue wOBA penalties (added to raw BP wOBA allowed)
# Applied per pitcher who appeared recently; averaged across BP.
FATIGUE_YESTERDAY = 0.018       # ~1 ERA equivalent degradation
FATIGUE_TWO_DAYS_AGO = 0.008

# Park run factors  (multiply expected runs by this value when game is at that park)
PARK_FACTORS: dict[str, float] = {
    "COL": 1.19,   # Coors Field
    "CIN": 1.08,   # Great American Ball Park
    "PHI": 1.06,   # Citizens Bank Park
    "BAL": 1.05,   # Camden Yards
    "BOS": 1.04,   # Fenway Park
    "TOR": 1.03,   # Rogers Centre
    "TEX": 1.03,   # Globe Life Field
    "MIL": 1.02,   # American Family Field
    "WSH": 1.01,   # Nationals Park
    "CHC": 1.01,   # Wrigley Field
    "ATL": 1.00,   # Truist Park
    "HOU": 1.00,   # Minute Maid Park
    "NYY": 1.00,   # Yankee Stadium
    "NYM": 0.99,   # Citi Field
    "LAD": 0.99,   # Dodger Stadium
    "MIN": 0.99,   # Target Field
    "ARI": 0.99,   # Chase Field
    "DET": 0.98,   # Comerica Park
    "SEA": 0.97,   # T-Mobile Park
    "SF":  0.97,   # Oracle Park
    "SFG": 0.97,
    "CLE": 0.97,   # Progressive Field
    "STL": 0.97,   # Busch Stadium
    "KC":  0.97,   # Kauffman Stadium
    "KCR": 0.97,
    "PIT": 0.96,   # PNC Park
    "TB":  0.96,   # Tropicana Field
    "TBR": 0.96,
    "MIA": 0.96,   # loanDepot park
    "CWS": 0.96,   # Guaranteed Rate Field
    "CHW": 0.96,
    "OAK": 0.96,   # Oakland / Sacramento
    "ATH": 0.96,
    "LAA": 0.97,   # Angel Stadium
    "SD":  0.95,   # Petco Park
    "SDP": 0.95,
}

# Normalise common alternative abbreviations to a single key
TEAM_ALIASES: dict[str, str] = {
    "SFG": "SF",
    "SDP": "SD",
    "KCR": "KC",
    "TBR": "TB",
    "CHW": "CWS",
    "ATH": "OAK",
    "WSN": "WSH",
}

def park_factor(home_team: str) -> float:
    team = TEAM_ALIASES.get(home_team, home_team)
    return PARK_FACTORS.get(team, 1.00)
