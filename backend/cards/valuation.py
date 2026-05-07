"""
Fair value estimation for sports cards.

Two methods, applied in priority order:

1. Direct — enough recent sales of the exact same card spec (>= 3).
   Returns a recency-weighted average with high confidence.

2. Print-run ratio — uses a power-law scarcity model:
       ratio = (anchor_print_run / target_print_run) ^ EXPONENT
   where EXPONENT ≈ 0.65 captures the empirical observation that
   scarcity multipliers are sublinear (demand + condition variance
   compress the extremes).

   Example:  /5 vs /100  →  (100/5)^0.65  ≈ 7.4×
             /10 vs /100  →  (100/10)^0.65 ≈ 4.5×
             /25 vs /100  →  (100/25)^0.65 ≈ 2.7×

   RC multiplier and set-tier adjustments from the hierarchy are
   applied on top of the ratio estimate.
"""

from datetime import datetime, timezone
from typing import Optional

SCARCITY_EXPONENT = 0.65   # power-law exponent; tune via hierarchy later
MIN_DIRECT_SALES  = 3      # minimum sales to use direct method
RECENCY_HALF_LIFE = 30     # days — sales older than this get half weight


def _recency_weight(sold_at: Optional[datetime]) -> float:
    if sold_at is None:
        return 0.5
    age_days = (datetime.now(timezone.utc) - sold_at).total_seconds() / 86400
    return max(0.1, 2 ** (-age_days / RECENCY_HALF_LIFE))


def _weighted_avg(sales: list[dict]) -> float:
    total_w = sum(_recency_weight(s.get("sold_at")) for s in sales)
    if total_w == 0:
        return sum(s["price"] for s in sales) / len(sales)
    return sum(s["price"] * _recency_weight(s.get("sold_at")) for s in sales) / total_w


def scarcity_ratio(from_run: int, to_run: int) -> float:
    """
    How much more valuable is a card numbered to `to_run`
    compared to one numbered to `from_run`?
    """
    if not from_run or not to_run or from_run == to_run:
        return 1.0
    return (from_run / to_run) ** SCARCITY_EXPONENT


def compute_group_stats(sales: list[dict]) -> dict:
    """Aggregate raw stats for a group of sales."""
    if not sales:
        return {"sale_count": 0, "avg_price": None, "min_price": None,
                "max_price": None, "last_price": None, "last_sale_date": None}

    prices = [s["price"] for s in sales]
    sorted_by_date = sorted(
        [s for s in sales if s.get("sold_at")],
        key=lambda s: s["sold_at"],
        reverse=True,
    )
    return {
        "sale_count":     len(sales),
        "avg_price":      round(_weighted_avg(sales), 2),
        "min_price":      round(min(prices), 2),
        "max_price":      round(max(prices), 2),
        "last_price":     round(sorted_by_date[0]["price"], 2) if sorted_by_date else round(prices[-1], 2),
        "last_sale_date": sorted_by_date[0]["sold_at"].date().isoformat() if sorted_by_date else None,
    }


def fair_value(
    target: dict,           # group dict with print_run, insert_type, stats
    all_groups: list[dict], # all groups for this player search
    rc_multiplier: float = 1.0,
) -> dict:
    """
    Estimate fair value for `target` group.

    Returns:
        value          — estimated price (None if cannot estimate)
        method         — 'direct' | 'print_run_ratio' | 'insufficient_data'
        confidence     — 'high' | 'medium' | 'low' | 'none'
        anchor_label   — description of what was used as anchor (for tooltip)
        ratio_used     — numeric ratio applied
    """
    stats = target.get("stats", {})
    target_pr = target.get("print_run")
    target_it = target.get("insert_type", "")

    # ── Method 1: Direct ──────────────────────────────────────────────────────
    if stats.get("sale_count", 0) >= MIN_DIRECT_SALES:
        v = stats["avg_price"] * rc_multiplier
        return {
            "value":       round(v, 2),
            "method":      "direct",
            "confidence":  "high",
            "anchor_label": f"{stats['sale_count']} recent sales",
            "ratio_used":  1.0,
        }

    # If only 1-2 direct sales, use them as the anchor but mark medium
    if stats.get("sale_count", 0) >= 1:
        v = stats["avg_price"] * rc_multiplier
        return {
            "value":       round(v, 2),
            "method":      "direct",
            "confidence":  "medium",
            "anchor_label": f"{stats['sale_count']} recent sale(s)",
            "ratio_used":  1.0,
        }

    # ── Method 2: Print-run ratio ─────────────────────────────────────────────
    if target_pr is not None:
        # Find comparable groups: same insert type, has sales, different print run
        comparables = [
            g for g in all_groups
            if g.get("insert_type") == target_it
            and g.get("print_run") is not None
            and g.get("print_run") != target_pr
            and g.get("stats", {}).get("sale_count", 0) >= 1
        ]
        if not comparables:
            # Fall back: same auto/patch flag regardless of exact insert type label
            target_is_auto = "Auto" in target_it
            comparables = [
                g for g in all_groups
                if ("Auto" in g.get("insert_type", "")) == target_is_auto
                and g.get("print_run") is not None
                and g.get("print_run") != target_pr
                and g.get("stats", {}).get("sale_count", 0) >= 1
            ]

        if comparables:
            # Prefer anchor with most sales; break ties by closer print run
            anchor = max(
                comparables,
                key=lambda g: (g["stats"]["sale_count"],
                               -abs(g["print_run"] - target_pr)),
            )
            anchor_pr    = anchor["print_run"]
            anchor_price = anchor["stats"]["avg_price"]
            ratio        = scarcity_ratio(anchor_pr, target_pr)
            v            = anchor_price * ratio * rc_multiplier
            conf         = "medium" if anchor["stats"]["sale_count"] >= 3 else "low"
            return {
                "value":       round(v, 2),
                "method":      "print_run_ratio",
                "confidence":  conf,
                "anchor_label": f"/{anchor_pr} avg ${anchor_price:.0f} × {ratio:.2f}× ratio",
                "ratio_used":  round(ratio, 3),
            }

    return {
        "value":       None,
        "method":      "insufficient_data",
        "confidence":  "none",
        "anchor_label": "Not enough sales data",
        "ratio_used":  None,
    }
