import plotly.graph_objects as go
import streamlit as st

from agents import reporter
from ui import common as ui
from ui import theme as t

ui.page_header("Executive Summary", "A one-page brief for leadership: brand health, the biggest concern, "
                                    "the best news, and an AI-written briefing.")
w = ui.need_windows()
m, risk = w["payload"]["report"], w["payload"]["risk"]

t.kpi_row([
    t.kpi("Brand health", f"{m['health']:.0f}", "favorite", "last 24 hours", unit="/ 100"),
    t.kpi("Positive", f"{m['positive_pct']:.0f}%", "sentiment_satisfied", f"of {m['mentions']:,} mentions"),
    t.kpi("Neutral", f"{m['neutral_pct']:.0f}%", "sentiment_neutral", "informational or unclear"),
    t.kpi("Negative", f"{m['negative_pct']:.0f}%", "sentiment_dissatisfied", "complaints and frustration"),
])

c = st.columns(3)
facts = [
    ("report", "Major concern", m["major_concern"] or "None",
     t.level_badge(m["concern_severity"]) if m["concern_severity"] else ""),
    ("thumb_up", "Positive trend", m["positive_trend"] or "None", ""),
    ("person_celebrate", "Top influencer mention", m["top_influencer"] or "None",
     f'<span class="bp-meta">{m["top_influencer_followers"]:,} followers*</span>' if m["top_influencer_followers"] else ""),
]
for col, (ic, label, value, extra) in zip(c, facts):
    with col.container(border=True):
        t.render(t.card_title(ic, label) + f'<div style="font-size:16px;font-weight:600;color:var(--bp-text)">{t.esc(value)}</div>'
                 f'<div style="margin-top:6px">{extra}</div>')

t.section("AI briefing", "Generated from the numbers on this page by the Executive Reporting agent")
with st.container(border=True):
    key = f"brief-{m['as_of']}"
    if st.button("Generate briefing", type="primary", icon=":material/auto_awesome:"):
        with st.spinner("Writing briefing..."):
            st.session_state[key] = reporter.summary(m, risk)
    st.markdown(st.session_state.get(key, "Generate a written summary of the last 24 hours for leadership."))

left, mid, right = st.columns(3)
with left:
    t.section("Brand health trend")
    df = ui.windows_df()
    fig = go.Figure(go.Scatter(x=df["window_end"], y=df["health"], mode="lines", line=dict(width=2.5, color="#8b7bff"), fill="tozeroy", fillcolor="rgba(124,108,255,0.12)"))
    fig.update_yaxes(range=[0, 100])
    st.plotly_chart(ui.chart_layout(fig, 260), use_container_width=True)
with mid:
    t.section("Emotions")
    e = dict(sorted(m["emotions"].items(), key=lambda x: x[1]))
    fig = go.Figure(go.Bar(x=list(e.values()), y=list(e.keys()), orientation="h", marker_color="#7c6cff"))
    st.plotly_chart(ui.chart_layout(fig, 260), use_container_width=True)
with right:
    t.section("Mention types")
    ty = dict(sorted(m["types"].items(), key=lambda x: x[1]))
    fig = go.Figure(go.Bar(x=list(ty.values()), y=list(ty.keys()), orientation="h", marker_color="#4f8cff"))
    st.plotly_chart(ui.chart_layout(fig, 260), use_container_width=True)
st.caption("Brand health = 40% net sentiment + 25% (1 − complaint rate) + 20% reach-weighted sentiment + "
           "15% influencer sentiment. * Synthetic follower counts.")
