import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agents.reporter import metrics
from core import db
from core.config import is_live, our_brand
from sources.dataset_replay import shift
from ui import common as ui
from ui import theme as t

ui.page_header("Competitors", "How we compare with the other airlines in the same conversation: "
                              "sentiment, brand health and share of voice.")
w = ui.need_windows()
now = w["window_end"]
hours = st.segmented_control("Period", [24, 72, 24 * 9], default=24, label_visibility="collapsed",
                             format_func=lambda h: ("Last 9 days" if is_live() else "Entire replay") if h > 100 else f"Last {h} hours") or 24

m = metrics(now, hours=hours)
comp = pd.DataFrame(m["competitors"]).sort_values("positive_pct", ascending=False)
colors = ui.brand_colors()

us = comp[comp["is_us"]]
if len(us):
    us, best = us.iloc[0], comp.iloc[0]
    rank = int((comp["health"] > us["health"]).sum()) + 1
    t.kpi_row([
        t.kpi(f"{our_brand()} positive", f"{us['positive_pct']:.0f}%", "sentiment_satisfied",
              f"vs. {best['brand']} at {best['positive_pct']:.0f}% (highest)"),
        t.kpi(f"{our_brand()} brand health", f"{us['health']:.0f}", "favorite", f"rank {rank} of {len(comp)}", unit="/ 100"),
        t.kpi("Share of voice", f"{100 * us['mentions'] / comp['mentions'].sum():.0f}%", "campaign",
              f"{int(us['mentions']):,} of {int(comp['mentions'].sum()):,} mentions"),
    ])

left, right = st.columns(2)
with left:
    t.section("Sentiment by brand", "Share of each brand's mentions")
    fig = go.Figure()
    for s in ("negative", "neutral", "positive"):
        fig.add_bar(y=comp["brand"], x=comp[f"{s}_pct"], name=s.title(), orientation="h",
                    marker_color=ui.SENTIMENT_COLORS[s], marker_line_color="#0b0e22", marker_line_width=2)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[0, 100], ticksuffix="%")
    st.plotly_chart(ui.chart_layout(fig, 320), use_container_width=True)
with right:
    t.section("Brand health", "0–100 composite score")
    d = comp.sort_values("health")
    fig = go.Figure(go.Bar(x=d["health"], y=d["brand"], orientation="h",
                           marker_color=[colors.get(b, "#5d6488") for b in d["brand"]],
                           text=d["health"].map(lambda v: f"{v:.0f}"), textposition="outside"))
    fig.update_xaxes(range=[0, 100])
    st.plotly_chart(ui.chart_layout(fig, 320), use_container_width=True)

t.section("Share of voice over time", "Mentions per hour by brand")
df = db.query_df("SELECT substr(created_at, 1, 13) AS hour, brand, COUNT(*) AS n FROM posts "
                 f"WHERE is_synthetic=0 AND created_at > ? AND created_at <= ? AND {db.live_filter('posts')} GROUP BY hour, brand",
                 (shift(now, -60 * hours), now))
df["hour"] = pd.to_datetime(df["hour"] + ":00")
fig = go.Figure()
for b, color in colors.items():
    sub = df[df["brand"] == b]
    fig.add_scatter(x=sub["hour"], y=sub["n"], name=b, mode="lines", line=dict(width=2, color=color))
st.plotly_chart(ui.chart_layout(fig, 300), use_container_width=True)

table = comp.drop(columns=["is_us"]).rename(columns={
    "brand": "Brand", "mentions": "Mentions", "positive_pct": "Positive %", "neutral_pct": "Neutral %",
    "negative_pct": "Negative %", "health": "Brand health"})
st.dataframe(table, hide_index=True, use_container_width=True, column_config={
    "Brand health": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})
