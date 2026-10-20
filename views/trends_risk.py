import json

import plotly.graph_objects as go
import streamlit as st

from agents.influence import VIRAL_THRESHOLD
from core import db
from core.config import our_brand, workspace
from sources.dataset_replay import shift
from ui import common as ui
from ui import theme as t

ui.page_header("Topics & Risk", "Posts grouped into topics automatically, how fast each topic is growing, "
                                "and the crisis risk score that drives escalation.")
w = ui.need_windows()
now, risk = w["window_end"], w["payload"]["risk"]
ui.status_banner(risk)


def gauge(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number={"font": {"size": 38, "family": "Poppins", "color": "#f2f3ff"}},
        title={"text": title, "font": {"size": 14, "family": "Inter", "color": "#9aa0c3"}},
        gauge={"axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#3a4170", "tickfont": {"color": "#858bb0"}},
               "bar": {"color": "#eef0ff", "thickness": 0.18}, "borderwidth": 0, "bgcolor": "rgba(255,255,255,0.04)",
               "steps": [{"range": [a, b], "color": c} for a, b, c in
                         ((0, 30, "rgba(46,204,113,0.28)"), (30, 50, "rgba(250,190,40,0.28)"), (50, 70, "rgba(255,138,61,0.30)"), (70, 100, "rgba(255,77,109,0.34)"))]}))
    return ui.chart_layout(fig, 220)


g1, g2, g3 = st.columns([1, 1, 1.25])
g1.plotly_chart(gauge(risk["score"], f"Current risk · {t.LEVEL_LABEL[risk['level']]}"), use_container_width=True)
g2.plotly_chart(gauge(risk["predicted_score"], f"Forecast, 2 hours · {t.LEVEL_LABEL[risk['predicted_level']]}"),
                use_container_width=True)
with g3, st.container(border=True, height=252):
    names = {"volume_spike": ("Volume spike", 35), "negative_share": ("Negativity", 15),
             "issue_cluster": ("Growing topic", 20), "impact": ("Influential accounts", 15),
             "emotion": ("Anger & frustration", 15)}
    rows = "".join(t.bar(names[k][0], v, names[k][1], f"{v:.0f}/{names[k][1]}") for k, v in risk["components"].items())
    t.render(t.card_title("query_stats", "Score breakdown") + rows +
             f'<div class="bp-meta" style="margin-top:10px">{risk["negative"]} negative posts this hour vs. a baseline of '
             f'{risk["baseline_negative"]:.0f} ({risk["growth_pct"]:+.0f}%).</div>')

AREAS = {  # team the Trend agent routes to -> (problem area, icon)
    "Product / Engineering": ("App & website", "smartphone"),
    "Operations + Customer Support": ("Delays & cancellations", "flight"),
    "Baggage Services": ("Baggage", "luggage"),
    "Billing & Revenue": ("Refunds, fees & fares", "payments"),
    "Customer Support": ("Customer service", "support_agent"),
    "Marketing (amplify)": ("Positive experiences", "thumb_up"),
}
SEV_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Positive": 4}


def team_of(rec: str) -> str:
    for prefix in ("Escalate to ", "Monitor - ", "Share with "):
        rec = rec.removeprefix(prefix)
    return rec.replace(" + PR / Comms", "")


def trend_text(growth: float) -> tuple[str, str]:
    if growth >= 100:
        return "Surging", "critical"
    if growth > 20:
        return "Growing", "warning"
    if growth < -20:
        return "Declining", "good"
    return "Steady", "neutral"


def area_cards(df, empty_msg):
    """One card per problem area; the AI-discovered topics are listed inside it."""
    if df.empty:
        st.info(empty_msg)
        return
    df = df.assign(team=df["recommendation"].map(team_of), rank=df["severity"].map(SEV_RANK))
    groups = sorted(df.groupby("team"), key=lambda g: (g[1]["rank"].min(), -g[1]["recent"].sum()))
    cols = st.columns(3)
    for i, (team, g) in enumerate(groups):
        g = g.sort_values(["rank", "recent"], ascending=[True, False])
        top = g.iloc[0]
        recent, previous = int(g["recent"].sum()), int(g["previous"].sum())
        growth = (recent - previous) / max(previous, 1) * 100
        label, tone = trend_text(growth)
        area, ic = AREAS.get(team, (team, "label"))
        right = t.level_badge(top["severity"]) if top["severity"] != "Positive" else ""
        tags = "".join(f'<span class="bp-tag">{t.esc(n)} <b>{r}</b></span>' for n, r in zip(g["name"], g["recent"]))
        trend_badge = t.badge(f"{label} {growth:+.0f}%", tone)
        with cols[i % 3].container(border=True):
            t.render(t.card_title(ic, area, right) +
                     f'<div class="bp-meta"><b>{recent}</b> posts in the last 2h &nbsp;{trend_badge}</div>'
                     f'<div class="bp-tags">{tags}</div>'
                     f'<div class="bp-action">{t.icon("subdirectory_arrow_right", 18)}<span>{t.esc(top["recommendation"])}</span></div>')
            with st.expander("Example posts"):
                for _, c in g.head(3).iterrows():
                    for smp in json.loads(c["samples"])[:2]:
                        t.render(t.post(smp["text"]))


clusters = db.query_df("SELECT * FROM clusters WHERE brand=? AND window_end=? ORDER BY id", (workspace(), now))
problems = clusters[clusters["severity"] != "Positive"]
praise = clusters[clusters["severity"] == "Positive"]

t.section("Topics in the last 12 hours", "Topics are discovered by the AI, then grouped by the team responsible. "
                                          "Growth compares the last 2 hours with the 2 hours before.")
tab1, tab2, tab3, tab4 = st.tabs([f"Issues ({len(problems)})", f"Positive ({len(praise)})", "Viral posts", "Alert log"])
with tab1:
    area_cards(problems, "No complaint topics right now.")
with tab2:
    area_cards(praise, "No positive topics standing out right now.")
with tab3:
    viral = db.query_df(
        "SELECT substr(p.created_at, 6, 11) AS time, p.handle AS account, p.followers, p.retweet_count AS retweets, "
        "p.text AS post, e.viral_score FROM posts p JOIN enrichment e ON e.post_id=p.id WHERE p.brand=? "
        f"AND p.created_at > ? AND p.created_at <= ? AND e.viral_score >= ? AND {db.live_filter()} ORDER BY e.viral_score DESC LIMIT 15",
        (our_brand(), shift(now, -1440), now, VIRAL_THRESHOLD))
    if viral.empty:
        st.info("No posts are spreading unusually fast right now.")
    else:
        st.dataframe(viral, hide_index=True, use_container_width=True, column_config={
            "post": st.column_config.TextColumn("Post", width="large"),
            "followers": st.column_config.NumberColumn("Followers*", format="%d"),
            "viral_score": st.column_config.ProgressColumn("Viral score", min_value=0, max_value=100, format="%.0f")})
with tab4:
    alerts = db.query_df("SELECT window_end, level, title, message, recommendation FROM alerts WHERE brand=? "
                         "ORDER BY id DESC LIMIT 30", (workspace(),))
    if alerts.empty:
        st.info("No alerts yet.")
    else:
        with st.container(border=True):
            t.render('<div class="bp-list">' + "".join(
                f'<div class="bp-row"><div>{t.level_badge(a["level"])}</div><div style="flex:1"><div class="t">{t.esc(a["title"])}</div>'
                f'<div class="d">{t.esc(a["message"])}</div><div class="d"><b>Action:</b> {t.esc(a["recommendation"])}</div></div>'
                f'<div class="time">{ui.fmt_time(a["window_end"])}</div></div>' for _, a in alerts.iterrows()) + "</div>")
