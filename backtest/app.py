"""
MLB Fair Value — Backtest Dashboard
====================================
Streamlit app for dual-track analysis: model vs closing line vs outcomes.

Run locally:
    cd backtest && pip install -r requirements.txt
    DATABASE_URL=postgresql://... streamlit run app.py

The app reads from the fair_value_calibration table populated nightly by
data_pipeline/nightly_calibration.py.  Seed historical data first with:
    python data_pipeline/nightly_calibration.py --backfill 60
"""

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MLB Fair Value — Backtest",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal custom CSS — tighten metric cards
st.markdown("""
<style>
[data-testid="metric-container"] { background:#f8f9fa; border:1px solid #dee2e6;
    border-radius:4px; padding:12px 16px; }
[data-testid="stMetricValue"] { font-size:1.6rem; font-weight:700; }
</style>
""", unsafe_allow_html=True)


# ── Database ──────────────────────────────────────────────────────────────────

@st.cache_resource
def get_engine():
    url = os.getenv("DATABASE_URL")
    if not url:
        st.error("DATABASE_URL environment variable not set.")
        st.stop()
    return create_engine(url)


@st.cache_data(ttl=300)   # refresh every 5 minutes
def load_calibration(_engine) -> pd.DataFrame:
    query = text("""
        SELECT
            game_date,
            home_team,
            away_team,
            model_home_prob,
            closing_home_prob,
            prob_delta,
            abs_delta,
            outcome_home_win,
            model_brier,
            market_brier,
            total_lambda,
            home_lineup_woba,
            away_lineup_woba
        FROM fair_value_calibration
        WHERE outcome_home_win IN (0, 1)
          AND model_home_prob   IS NOT NULL
        ORDER BY game_date
    """)
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


# ── Metric helpers ─────────────────────────────────────────────────────────────

def calibration_slope(x: np.ndarray, y: np.ndarray) -> float:
    """OLS slope of y ~ x (no intercept forcing), cov(x,y)/var(x)."""
    if len(x) < 5:
        return float("nan")
    return float(np.cov(x, y)[0, 1] / np.var(x))


def brier_skill_score(model_brier: float, market_brier: float) -> float:
    """Fraction of market Brier score beaten. >0 = model adds value."""
    if market_brier == 0:
        return float("nan")
    return float(1 - model_brier / market_brier)


def calibration_bins(df: pd.DataFrame, n_bins: int = 12) -> pd.DataFrame:
    """
    Bin model_home_prob into equal-width buckets.
    Returns: bin_center, mean_model, mean_closing, actual_win_rate, n.
    """
    edges = np.linspace(df["model_home_prob"].min() - 0.001,
                        df["model_home_prob"].max() + 0.001, n_bins + 1)
    df2 = df.copy()
    df2["bin"] = pd.cut(df2["model_home_prob"], bins=edges, labels=False)
    g = df2.groupby("bin").agg(
        n=("model_home_prob", "count"),
        mean_model=("model_home_prob", "mean"),
        mean_closing=("closing_home_prob", "mean"),
        actual_win_rate=("outcome_home_win", "mean"),
    ).dropna(subset=["mean_model"])
    g["bin_center"] = (edges[:-1] + edges[1:])[g.index.astype(int)] / 2
    return g.reset_index(drop=True)


def summary_by_cl_range(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics grouped by closing-line probability bucket."""
    has_cl = df.dropna(subset=["closing_home_prob"])

    def cl_bucket(p):
        if p < 0.50:  return "< 50%  (home dog)"
        if p < 0.55:  return "50–55% (pick)"
        if p < 0.60:  return "55–60% (slight fav)"
        if p < 0.65:  return "60–65% (mod fav)"
        return             "65%+   (heavy fav)"

    has_cl = has_cl.copy()
    has_cl["cl_range"] = has_cl["closing_home_prob"].apply(cl_bucket)

    order = ["< 50%  (home dog)", "50–55% (pick)", "55–60% (slight fav)",
             "60–65% (mod fav)", "65%+   (heavy fav)"]

    agg = has_cl.groupby("cl_range").agg(
        n=("model_home_prob", "count"),
        avg_model=("model_home_prob", "mean"),
        avg_cl=("closing_home_prob", "mean"),
        mean_delta=("prob_delta", "mean"),
        mae=("abs_delta", "mean"),
        actual_win_rate=("outcome_home_win", "mean"),
        model_brier=("model_brier", "mean"),
        market_brier=("market_brier", "mean"),
    ).reindex([o for o in order if o in has_cl["cl_range"].values])

    agg.columns = ["N", "Avg Model", "Avg CL", "Mean Δ",
                   "MAE", "Actual Win%", "Model Brier", "Mkt Brier"]
    return agg.reset_index().rename(columns={"cl_range": "CL Range"})


def monthly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Month-by-month metric table for walk-forward view."""
    df2 = df.copy()
    df2["month"] = df2["game_date"].dt.to_period("M").astype(str)
    has_cl = df2.dropna(subset=["closing_home_prob"])

    rows = []
    for month, grp in has_cl.groupby("month"):
        x = grp["model_home_prob"].values
        y = grp["closing_home_prob"].values
        rows.append({
            "Month":        month,
            "N":            len(grp),
            "MAE":          grp["abs_delta"].mean(),
            "Bias":         grp["prob_delta"].mean(),
            "Cal Slope":    calibration_slope(x, y),
            "Model Brier":  grp["model_brier"].mean(),
            "Mkt Brier":    grp["market_brier"].mean(),
            "Skill Score":  brier_skill_score(grp["model_brier"].mean(),
                                              grp["market_brier"].mean()),
        })
    return pd.DataFrame(rows)


# ── Sidebar filters ────────────────────────────────────────────────────────────

engine = get_engine()
df_all = load_calibration(engine)

with st.sidebar:
    st.markdown("## ⚾ Filters")

    if df_all.empty:
        st.warning("No data yet.\n\nRun:\n```\npython data_pipeline/nightly_calibration.py --backfill 60\n```")
        st.stop()

    min_d = df_all["game_date"].min().date()
    max_d = df_all["game_date"].max().date()

    date_range = st.date_input(
        "Date range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )

    require_market = st.checkbox("Only games with closing line", value=True)

    total_bucket = st.slider(
        "Filter by game total (λ home + λ away)",
        min_value=4.0, max_value=14.0,
        value=(4.0, 14.0), step=0.5,
    )

    st.markdown("---")
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

# Apply filters
start, end = (date_range[0], date_range[1]) if len(date_range) == 2 \
             else (min_d, max_d)
df = df_all[
    (df_all["game_date"].dt.date >= start) &
    (df_all["game_date"].dt.date <= end)
].copy()

if require_market:
    df = df.dropna(subset=["closing_home_prob"])

if "total_lambda" in df.columns:
    df = df[
        df["total_lambda"].between(total_bucket[0], total_bucket[1],
                                    inclusive="both")
    ]

# ── Page header ───────────────────────────────────────────────────────────────

st.markdown("# MLB Fair Value — Backtest Dashboard")
st.caption(f"**{len(df):,}** games · {start} → {end}")

if df.empty:
    st.warning("No games match the current filters.")
    st.stop()

# ── Top-line metrics ──────────────────────────────────────────────────────────

has_cl = df.dropna(subset=["closing_home_prob"])
has_outcome = df.dropna(subset=["outcome_home_win"])

n_total       = len(df)
n_with_cl     = len(has_cl)
mae           = has_cl["abs_delta"].mean()
bias          = has_cl["prob_delta"].mean()
model_brier   = has_outcome["model_brier"].mean()
market_brier  = has_outcome.dropna(subset=["market_brier"])["market_brier"].mean()
skill         = brier_skill_score(model_brier, market_brier)
slope         = calibration_slope(
    has_cl["model_home_prob"].values,
    has_cl["closing_home_prob"].values,
)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Games (w/ CL)",  f"{n_with_cl:,}")
c2.metric("Mean AE",        f"{mae:.3f}",
          help="|model − closing| — lower is better")
c3.metric("Bias",           f"{bias:+.3f}",
          help="mean(model − closing) — 0 = unbiased")
c4.metric("Model Brier",    f"{model_brier:.4f}",
          help="(model − outcome)² — lower is better")
c5.metric("Mkt Brier",      f"{market_brier:.4f}" if not np.isnan(market_brier) else "–")
c6.metric("Skill Score",    f"{skill:+.3f}" if not np.isnan(skill) else "–",
          delta=f"{'▲ better' if skill > 0 else '▼ worse'} than market" if not np.isnan(skill) else None,
          help="1 − (model_brier / market_brier). >0 = model beats market.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Calibration Curve",
    "📊 Residual Distribution",
    "📋 Summary Table",
    "🗓 Walk-Forward",
])


# ── Tab 1: Calibration curve ──────────────────────────────────────────────────

with tab1:
    st.markdown("### Reliability Diagram")
    st.caption(
        "Each point = a 5% bin of model probabilities. "
        "Dashed line = perfect calibration (model == reality). "
        "**Blue** = model vs closing line.  **Red** = model vs actual win rate."
    )

    if has_cl.empty:
        st.info("No games with closing lines in this range.")
    else:
        bins_df = calibration_bins(has_cl)

        fig = go.Figure()

        # Perfect calibration reference
        diag = np.linspace(0.40, 0.75, 50)
        fig.add_trace(go.Scatter(
            x=diag, y=diag,
            mode="lines", line=dict(dash="dash", color="gray", width=1),
            name="Perfect (slope=1)", hoverinfo="skip",
        ))

        # Model vs closing line
        fig.add_trace(go.Scatter(
            x=bins_df["mean_model"],
            y=bins_df["mean_closing"],
            mode="markers+lines",
            marker=dict(size=bins_df["n"].clip(5, 40).tolist(),
                        color="#1f77b4", opacity=0.85,
                        line=dict(width=1, color="white")),
            line=dict(color="#1f77b4"),
            name="vs Closing Line",
            text=[f"n={r.n}<br>Model {r.mean_model:.3f}<br>CL {r.mean_closing:.3f}"
                  for _, r in bins_df.iterrows()],
            hovertemplate="%{text}<extra></extra>",
        ))

        # Model vs actual win rate
        if has_outcome is not None and len(has_outcome) > 20:
            bins_out = calibration_bins(has_outcome.dropna(subset=["outcome_home_win"]))
            fig.add_trace(go.Scatter(
                x=bins_out["mean_model"],
                y=bins_out["actual_win_rate"],
                mode="markers+lines",
                marker=dict(size=8, color="#d62728",
                            symbol="diamond",
                            line=dict(width=1, color="white")),
                line=dict(color="#d62728", dash="dot"),
                name="vs Actual Win Rate",
                text=[f"n={r.n}<br>Model {r.mean_model:.3f}<br>Actual {r.actual_win_rate:.3f}"
                      for _, r in bins_out.iterrows()],
                hovertemplate="%{text}<extra></extra>",
            ))

        # Calibration slope annotation
        fig.add_annotation(
            x=0.68, y=0.42,
            text=f"Calibration slope: <b>{slope:.3f}</b><br>"
                 f"(1.00 = perfect market alignment)",
            showarrow=False,
            font=dict(size=12),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#aaa",
        )

        fig.update_layout(
            xaxis_title="Model Probability",
            yaxis_title="Closing Line / Actual Win Rate",
            xaxis=dict(tickformat=".0%", range=[0.38, 0.77]),
            yaxis=dict(tickformat=".0%", range=[0.38, 0.77]),
            legend=dict(x=0.02, y=0.98),
            height=480,
            margin=dict(l=40, r=40, t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Slope interpretation
        if not np.isnan(slope):
            if abs(slope - 1.0) < 0.05:
                st.success(f"Slope {slope:.3f} — model is well-calibrated to the market.")
            elif slope < 1.0:
                st.warning(f"Slope {slope:.3f} — model is **compressed** (under-confident on big favorites). "
                           "Consider reducing the Platt scaling A coefficient.")
            else:
                st.warning(f"Slope {slope:.3f} — model is **stretched** (over-confident). "
                           "Consider increasing Platt scaling A.")


# ── Tab 2: Residual distribution ──────────────────────────────────────────────

with tab2:
    st.markdown("### Residual Distribution  (model − closing line)")
    st.caption(
        "A tight bell curve centered at 0 = well-aligned model. "
        "Fat tails = specific game types where the model breaks down."
    )

    col_hist, col_stats = st.columns([3, 1])

    with col_hist:
        if has_cl.empty:
            st.info("No data.")
        else:
            deltas = has_cl["prob_delta"].dropna()

            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=deltas,
                nbinsx=40,
                marker_color="#1f77b4",
                opacity=0.8,
                name="Residuals",
            ))
            fig.add_vline(x=0, line_dash="dash", line_color="red",
                          annotation_text="0", annotation_position="top right")
            fig.add_vline(x=deltas.mean(), line_dash="dot", line_color="orange",
                          annotation_text=f"Mean {deltas.mean():+.3f}",
                          annotation_position="top left")

            # Shade fat-tail region (|delta| > 0.10)
            fig.add_vrect(x0=-1, x1=-0.10, fillcolor="red", opacity=0.05,
                          line_width=0, annotation_text="|Δ|>10pp")
            fig.add_vrect(x0=0.10, x1=1, fillcolor="red", opacity=0.05,
                          line_width=0, annotation_text="|Δ|>10pp")

            fig.update_layout(
                xaxis_title="model prob − closing prob",
                yaxis_title="# games",
                xaxis=dict(tickformat="+.0%"),
                height=380,
                margin=dict(l=40, r=20, t=20, b=40),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_stats:
        st.markdown("**Distribution stats**")
        d = has_cl["prob_delta"].dropna()
        st.metric("Mean",   f"{d.mean():+.4f}")
        st.metric("Std",    f"{d.std():.4f}")
        st.metric("Median", f"{d.median():+.4f}")
        skew = float(pd.Series(d).skew())
        st.metric("Skew",   f"{skew:+.3f}",
                  help=">0 = right tail (overrates home teams on avg)")

        pct_fat = (d.abs() > 0.10).mean() * 100
        st.metric("|Δ| > 10pp", f"{pct_fat:.1f}%",
                  help="Games where model was >10pp off market — investigate these")

    # Worst misses table
    st.markdown("#### Biggest misses  (|model − closing| > 8pp)")
    fat = has_cl[has_cl["abs_delta"] > 0.08].sort_values("abs_delta", ascending=False)
    if fat.empty:
        st.success("No games with |Δ| > 8pp in this filter range.")
    else:
        display = fat[["game_date", "away_team", "home_team",
                        "model_home_prob", "closing_home_prob",
                        "prob_delta", "outcome_home_win"]].copy()
        display.columns = ["Date", "Away", "Home",
                            "Model", "Closing", "Δ", "Outcome"]
        display["Date"]    = display["Date"].dt.strftime("%Y-%m-%d")
        display["Model"]   = display["Model"].map("{:.3f}".format)
        display["Closing"] = display["Closing"].map("{:.3f}".format)
        display["Δ"]       = display["Δ"].map("{:+.3f}".format)
        display["Outcome"] = display["Outcome"].map({1: "Home Win", 0: "Away Win"})
        st.dataframe(display, use_container_width=True, hide_index=True)


# ── Tab 3: Summary table ──────────────────────────────────────────────────────

with tab3:
    st.markdown("### Summary by Closing Line Range")
    st.caption(
        "Grouped by the market's implied home-win probability. "
        "Mean Δ > 0 = model overrates the home team in that range."
    )

    summ = summary_by_cl_range(has_cl)

    if summ.empty:
        st.info("Not enough data with closing lines.")
    else:
        def color_delta(val):
            try:
                v = float(val)
                if v > 0.02:  return "background-color:#fdd"
                if v < -0.02: return "background-color:#dfd"
                return ""
            except Exception:
                return ""

        styled = (
            summ.style
            .format({
                "Avg Model":    "{:.3f}",
                "Avg CL":       "{:.3f}",
                "Mean Δ":       "{:+.4f}",
                "MAE":          "{:.4f}",
                "Actual Win%":  "{:.3f}",
                "Model Brier":  "{:.4f}",
                "Mkt Brier":    "{:.4f}",
            })
            .map(color_delta, subset=["Mean Δ"])
            .bar(subset=["MAE"], color="#b0c4de")
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Bar chart of MAE by CL range
        fig = px.bar(
            summ, x="CL Range", y="MAE",
            color="Mean Δ",
            color_continuous_scale=["#4CAF50", "white", "#F44336"],
            color_continuous_midpoint=0,
            text="N",
            title="Mean Absolute Error by Closing Line Range",
        )
        fig.update_traces(texttemplate="n=%{text}", textposition="outside")
        fig.update_layout(height=340, margin=dict(t=40, b=40),
                          coloraxis_colorbar_title="Bias (Δ)")
        st.plotly_chart(fig, use_container_width=True)


# ── Tab 4: Walk-forward ───────────────────────────────────────────────────────

with tab4:
    st.markdown("### Walk-Forward Analysis — Month by Month")
    st.caption(
        "Time-series split: metrics computed chronologically. "
        "Skill Score > 0 means the model out-predicted the closing line on outcomes."
    )

    monthly = monthly_metrics(has_cl)

    if monthly.empty or len(monthly) < 2:
        st.info("Need at least 2 months of data for walk-forward analysis. "
                "Run nightly_calibration.py --backfill 60 to seed more history.")
    else:
        # MAE + Bias trend line
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=monthly["Month"], y=monthly["MAE"],
            name="MAE", marker_color="#1f77b4", opacity=0.7,
        ))
        fig1.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["Bias"],
            name="Bias", yaxis="y2",
            line=dict(color="orange", width=2),
            mode="lines+markers",
        ))
        fig1.add_hline(y=0, line_dash="dash", line_color="gray",
                        yref="y2", opacity=0.5)
        fig1.update_layout(
            title="Monthly MAE and Bias",
            yaxis=dict(title="MAE"),
            yaxis2=dict(title="Bias", overlaying="y", side="right",
                        zeroline=True),
            height=320,
            margin=dict(t=40, b=40),
            legend=dict(x=0.01, y=0.99),
        )
        st.plotly_chart(fig1, use_container_width=True)

        # Brier model vs market
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=monthly["Month"], y=monthly["Model Brier"],
            name="Model Brier", marker_color="#d62728", opacity=0.8,
        ))
        fig2.add_trace(go.Bar(
            x=monthly["Month"], y=monthly["Mkt Brier"],
            name="Market Brier", marker_color="#2ca02c", opacity=0.8,
        ))
        fig2.update_layout(
            title="Model vs Market Brier Score (lower = better)",
            barmode="group", height=300,
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Monthly stats table
        fmt = {
            "MAE":          "{:.4f}",
            "Bias":         "{:+.4f}",
            "Cal Slope":    "{:.3f}",
            "Model Brier":  "{:.4f}",
            "Mkt Brier":    "{:.4f}",
            "Skill Score":  "{:+.3f}",
        }

        def color_skill(val):
            try:
                v = float(val)
                return "color:green;font-weight:bold" if v > 0 else "color:red"
            except Exception:
                return ""

        styled_m = (
            monthly.style
            .format(fmt)
            .map(color_skill, subset=["Skill Score"])
        )
        st.dataframe(styled_m, use_container_width=True, hide_index=True)

        # Cumulative skill score
        monthly["cum_skill"] = monthly["Skill Score"].cumsum()
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["cum_skill"],
            fill="tozeroy",
            line=dict(color="#1f77b4"),
            name="Cumulative Skill Score",
        ))
        fig3.add_hline(y=0, line_dash="dash", line_color="red")
        fig3.update_layout(
            title="Cumulative Skill Score vs Market (staying above 0 = model improving over time)",
            height=280, margin=dict(t=40, b=40),
        )
        st.plotly_chart(fig3, use_container_width=True)
