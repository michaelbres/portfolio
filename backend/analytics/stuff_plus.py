"""
Stuff+ Model
============
Trains per-pitch-type-family gradient-boosted classifiers on pitch physical
characteristics (velocity, movement, release point, spin, tunneling) to predict
the probability of a whiff on any given pitch. Scales the result to a 100-average
"plus" scale within each pitch type.

Features
--------
- release_speed       : velocity (mph)
- pfx_x_handed_in     : horizontal break in inches, sign-corrected (arm-side +)
- pfx_z_in            : induced vertical break in inches
- rp_x_handed         : release-side (ft, arm-side +)
- rp_z                : release height (ft)
- extension           : release extension (ft)
- spin_rate           : spin rate (rpm)
- spin_axis_sin/cos   : cyclic encoding of spin axis
- velo_diff_from_fb   : pitcher's avg FB velocity – this pitch's velocity
- tunnel_sep          : Euclidean separation from pitcher's avg FB at tunnel point (23 ft)

Algorithm
---------
Three models (FB / BB / OS pitch families) trained on swing pitches only.
Target: 1 = whiff, 0 = contact / non-whiff swing.

Stuff+ formula (per pitch type): (predicted_prob / league_avg_prob) × 100
  → 100 = league average, 120 = 20% above league avg, etc.

Tunneling
---------
Uses the Statcast kinematic parameters (vx0/vy0/vz0/ax/ay/az) to solve for
the 3-D position of a pitch at the tunnel point (23 ft from home plate) and
compute how similarly it looks to the pitcher's average fastball at that point.
"""

from __future__ import annotations
import logging
from collections import defaultdict
from typing import Optional

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sqlalchemy.orm import Session

from models import StatcastPitch, StuffPlusScore

logger = logging.getLogger(__name__)

# ── Pitch type families ───────────────────────────────────────────────────────
FAMILIES: dict[str, set[str]] = {
    "FB": {"FF", "SI", "FC", "FT", "FA"},
    "BB": {"SL", "CU", "KC", "SV", "ST", "CS", "GY"},
    "OS": {"CH", "FS", "FO", "SC", "EP", "KN"},
}
PITCH_TO_FAMILY: dict[str, str] = {
    pt: fam for fam, pts in FAMILIES.items() for pt in pts
}
FB_TYPES: set[str] = FAMILIES["FB"]

SWING_DESCS = {
    "swinging_strike", "swinging_strike_blocked", "foul_tip",
    "hit_into_play", "foul", "foul_bunt",
}
WHIFF_DESCS = {"swinging_strike", "swinging_strike_blocked"}

# Tunnel point: 23 ft from the back of home plate
TUNNEL_Y = 23.0
MIN_PITCHES_TO_SCORE = 25  # minimum pitches per pitch-type to report a Stuff+


# ── Kinematic helpers ─────────────────────────────────────────────────────────

def _tunnel_pos(
    ry: Optional[float], vx0, vy0, vz0, ax, ay, az, rx, rz
) -> tuple[Optional[float], Optional[float]]:
    """
    Return (x, z) position of the pitch at the tunnel point (23 ft from plate).

    Uses Statcast kinematic model: pos(t) = pos0 + v0*t + 0.5*a*t²
    Solves for t when y(t) = TUNNEL_Y.
    """
    if any(v is None for v in [ry, vx0, vy0, vz0, ax, ay, az, rx, rz]):
        return None, None
    a_c = 0.5 * ay
    b_c = vy0
    c_c = float(ry) - TUNNEL_Y
    disc = b_c * b_c - 4.0 * a_c * c_c
    if disc < 0:
        return None, None
    if abs(a_c) < 1e-9:
        if abs(b_c) < 1e-9:
            return None, None
        t = -c_c / b_c
    else:
        t1 = (-b_c - disc ** 0.5) / (2.0 * a_c)
        t2 = (-b_c + disc ** 0.5) / (2.0 * a_c)
        candidates = [t for t in (t1, t2) if t > 0]
        if not candidates:
            return None, None
        t = min(candidates)
    x = rx + vx0 * t + 0.5 * ax * t * t
    z = rz + vz0 * t + 0.5 * az * t * t
    return float(x), float(z)


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_pitches(db: Session, season: int):
    """Return all pitches for the season with the columns needed for Stuff+."""
    from sqlalchemy import Integer, cast
    return db.query(
        StatcastPitch.id,
        StatcastPitch.pitcher,
        StatcastPitch.player_name,
        StatcastPitch.pitch_type,
        StatcastPitch.p_throws,
        StatcastPitch.description,
        StatcastPitch.release_speed,
        StatcastPitch.pfx_x,
        StatcastPitch.pfx_z,
        StatcastPitch.release_pos_x,
        StatcastPitch.release_pos_y,
        StatcastPitch.release_pos_z,
        StatcastPitch.release_extension,
        StatcastPitch.release_spin_rate,
        StatcastPitch.spin_axis,
        StatcastPitch.vx0,
        StatcastPitch.vy0,
        StatcastPitch.vz0,
        StatcastPitch.ax,
        StatcastPitch.ay,
        StatcastPitch.az,
    ).filter(
        StatcastPitch.game_year == season,
        StatcastPitch.pitch_type.isnot(None),
        StatcastPitch.release_speed.isnot(None),
    ).all()


# ── Feature engineering ───────────────────────────────────────────────────────

FEATURE_NAMES = [
    "release_speed",
    "pfx_x_handed_in",
    "pfx_z_in",
    "rp_x_handed",
    "rp_z",
    "extension",
    "spin_rate",
    "spin_axis_sin",
    "spin_axis_cos",
    "velo_diff_from_fb",
    "tunnel_sep",
]


def _build_features(
    rows,
    tunnel_sep: np.ndarray,
    pitcher_fb_velo: dict[int, float],
) -> np.ndarray:
    """Build (N, 11) feature matrix. Missing values → NaN (imputed later)."""
    N = len(rows)
    X = np.full((N, len(FEATURE_NAMES)), np.nan)
    for i, r in enumerate(rows):
        hand = -1.0 if r.p_throws == "L" else 1.0
        pfx_x_h = (r.pfx_x or 0.0) * hand * 12.0    # ft → in, arm-side +
        pfx_z_in = (r.pfx_z or 0.0) * 12.0           # ft → in
        rp_x_h = (r.release_pos_x or 0.0) * hand
        rp_z = r.release_pos_z or 0.0
        ext = r.release_extension or 0.0
        spin = r.release_spin_rate or 0.0
        axis_rad = np.radians(r.spin_axis or 0.0)
        fb_velo = pitcher_fb_velo.get(r.pitcher, r.release_speed or 0.0)
        velo_diff = float(fb_velo) - float(r.release_speed or 0.0)
        tsep = tunnel_sep[i] if not np.isnan(tunnel_sep[i]) else np.nan

        X[i] = [
            r.release_speed or 0.0,
            pfx_x_h,
            pfx_z_in,
            rp_x_h,
            rp_z,
            ext,
            spin,
            np.sin(axis_rad),
            np.cos(axis_rad),
            velo_diff,
            tsep,
        ]
    return X


def _impute(X: np.ndarray, medians: Optional[np.ndarray] = None) -> tuple[np.ndarray, np.ndarray]:
    """Fill NaN with column medians. Returns (imputed_X, medians)."""
    if medians is None:
        medians = np.nanmedian(X, axis=0)
    for col in range(X.shape[1]):
        mask = np.isnan(X[:, col])
        if mask.any():
            X[mask, col] = medians[col]
    return X, medians


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_and_store(db: Session, season: int) -> dict:
    """
    Train Stuff+ models for the given season and write scores to stuff_plus_scores.
    Returns a summary dict.
    """
    logger.info("Stuff+ — loading pitches for season %s", season)
    rows = _load_pitches(db, season)
    if not rows:
        return {"error": f"No pitch data for season {season}"}

    N = len(rows)
    logger.info("Stuff+ — %d pitches loaded", N)

    pitch_types = [r.pitch_type or "" for r in rows]
    pitcher_ids = [r.pitcher for r in rows]
    p_throws = [r.p_throws for r in rows]

    # ── 1. Compute tunnel positions ─────────────────────────────────────────
    tunnel_x = np.full(N, np.nan)
    tunnel_z = np.full(N, np.nan)
    for i, r in enumerate(rows):
        tx, tz = _tunnel_pos(
            r.release_pos_y, r.vx0, r.vy0, r.vz0,
            r.ax, r.ay, r.az, r.release_pos_x, r.release_pos_z,
        )
        if tx is not None:
            tunnel_x[i] = tx
            tunnel_z[i] = tz

    # ── 2. Per-pitcher fastball tunnel centroid ──────────────────────────────
    is_fb = np.array([pt in FB_TYPES for pt in pitch_types])
    pid_arr = np.array(pitcher_ids)

    pitcher_fb_cx: dict[int, float] = {}
    pitcher_fb_cz: dict[int, float] = {}
    for pid in set(pitcher_ids):
        mask = (pid_arr == pid) & is_fb & ~np.isnan(tunnel_x)
        if mask.sum() >= 5:
            pitcher_fb_cx[pid] = float(np.nanmean(tunnel_x[mask]))
            pitcher_fb_cz[pid] = float(np.nanmean(tunnel_z[mask]))

    tunnel_sep = np.full(N, np.nan)
    for i, r in enumerate(rows):
        pid = r.pitcher
        if pid in pitcher_fb_cx and not np.isnan(tunnel_x[i]):
            dx = tunnel_x[i] - pitcher_fb_cx[pid]
            dz = tunnel_z[i] - pitcher_fb_cz[pid]
            tunnel_sep[i] = float(np.sqrt(dx * dx + dz * dz))

    # ── 3. Per-pitcher average FB velocity (for velocity differential) ───────
    pitcher_fb_velos: dict[int, list] = defaultdict(list)
    for i, r in enumerate(rows):
        if pitch_types[i] in FB_TYPES and r.release_speed is not None:
            pitcher_fb_velos[r.pitcher].append(r.release_speed)
    pitcher_fb_velo = {pid: float(np.mean(v)) for pid, v in pitcher_fb_velos.items()}

    # ── 4. Build global feature matrix ──────────────────────────────────────
    X_all = _build_features(rows, tunnel_sep, pitcher_fb_velo)

    # ── 5. Train per-family models and score ─────────────────────────────────
    is_swing = np.array([r.description in SWING_DESCS for r in rows])
    is_whiff = np.array([r.description in WHIFF_DESCS for r in rows])

    # pitcher × pitch_type → avg Stuff+
    all_scores: dict[int, dict[str, dict]] = defaultdict(dict)
    pitcher_names: dict[int, str] = {}
    for r in rows:
        pitcher_names[r.pitcher] = r.player_name or ""

    for fam, fam_types in FAMILIES.items():
        fam_mask = np.array([pt in fam_types for pt in pitch_types])
        if fam_mask.sum() < 500:
            logger.warning("Stuff+ — family %s: only %d pitches, skipping", fam, fam_mask.sum())
            continue

        X_fam = X_all[fam_mask].copy()
        fam_swing = is_swing[fam_mask]
        fam_whiff = is_whiff[fam_mask]
        fam_types_arr = np.array(pitch_types)[fam_mask]
        fam_pids = np.array(pitcher_ids)[fam_mask]

        swing_idx = np.where(fam_swing)[0]
        if len(swing_idx) < 200:
            logger.warning("Stuff+ — family %s: only %d swings, skipping", fam, len(swing_idx))
            continue

        X_train = X_fam[swing_idx].copy()
        y_train = fam_whiff[swing_idx].astype(float)
        X_train, medians = _impute(X_train)

        logger.info(
            "Stuff+ — training %s model on %d swings (%.1f%% whiff rate)",
            fam, len(swing_idx), y_train.mean() * 100
        )

        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=50,
                random_state=42,
            )),
        ])
        model.fit(X_train, y_train)

        # Score all pitches in this family
        X_score = X_fam.copy()
        _impute(X_score, medians)
        probs = model.predict_proba(X_score)[:, 1]

        # League-avg probability per pitch type (for plus scaling)
        pt_league_avg: dict[str, float] = {}
        for pt in fam_types:
            pt_mask = fam_types_arr == pt
            if pt_mask.sum() > 0:
                pt_league_avg[pt] = float(np.mean(probs[pt_mask]))

        # Aggregate per pitcher × pitch type
        pid_pt_probs: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for j, (pid, pt, prob) in enumerate(zip(fam_pids, fam_types_arr, probs)):
            pid_pt_probs[pid][pt].append(float(prob))

        for pid, pt_data in pid_pt_probs.items():
            for pt, probs_list in pt_data.items():
                n = len(probs_list)
                avg_prob = float(np.mean(probs_list))
                league_avg = pt_league_avg.get(pt, avg_prob)
                stuff_plus = round((avg_prob / league_avg) * 100) if league_avg > 0 else 100
                all_scores[pid][pt] = {
                    "stuff_plus": stuff_plus,
                    "n_pitches": n,
                    "family": fam,
                }

        logger.info("Stuff+ — %s model done, scored %d pitcher×pitch-type pairs", fam, len(pid_pt_probs))

    # ── 6. Write to DB ────────────────────────────────────────────────────────
    n_written = 0
    for pid, pt_scores in all_scores.items():
        for pt, data in pt_scores.items():
            if data["n_pitches"] < MIN_PITCHES_TO_SCORE:
                continue
            existing = db.query(StuffPlusScore).filter(
                StuffPlusScore.pitcher_id == pid,
                StuffPlusScore.pitch_type == pt,
                StuffPlusScore.season == season,
            ).first()
            if existing:
                existing.avg_stuff_plus = data["stuff_plus"]
                existing.n_pitches = data["n_pitches"]
                existing.model_family = data["family"]
                existing.pitcher_name = pitcher_names.get(pid)
            else:
                db.add(StuffPlusScore(
                    pitcher_id=pid,
                    pitcher_name=pitcher_names.get(pid),
                    pitch_type=pt,
                    season=season,
                    avg_stuff_plus=data["stuff_plus"],
                    n_pitches=data["n_pitches"],
                    model_family=data["family"],
                ))
            n_written += 1

    db.commit()
    logger.info("Stuff+ — wrote %d score rows for season %s", n_written, season)
    return {
        "season": season,
        "n_pitches_loaded": N,
        "n_score_rows_written": n_written,
        "families_trained": [f for f in FAMILIES if any(
            data.get("family") == f
            for pt_scores in all_scores.values()
            for data in pt_scores.values()
        )],
    }
