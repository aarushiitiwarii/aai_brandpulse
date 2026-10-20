import plotly.graph_objects as go
import streamlit as st

from core import db
from core.config import display_name, is_live, our_brand, workspace
from ui import common as ui
from ui import theme as t

t.inject()
if not ui.data_ready():
    st.error("No data loaded. Put `Tweets.csv` in `data/raw/` and run `python -m scripts.prepare`.")
    st.stop()
now = db.kv_get(db.clock_key())
w = ui.need_windows()
risk, report = w["payload"]["risk"], w["payload"]["report"]
pending = int(db.query_df("SELECT COUNT(*) AS n FROM responses WHERE brand=? AND status='pending'",
                          (workspace(),)).loc[0, "n"])

# ---- hero ------------------------------------------------------------------------------------
pills = "".join([
    t.pill_stat("Positive", f"{report['positive_pct']:.0f}%", t.CHART["positive"], "#ffffff"),
    t.pill_stat("Neutral", f"{report['neutral_pct']:.0f}%", "#e7e8f5"),
    t.pill_stat("Negative", f"{report['negative_pct']:.0f}%", t.CHART["negative"], "#ffffff"),
    t.pill_stat("Brand health", f"{report['health']:.0f} / 100",
                "repeating-linear-gradient(135deg,#2a3056 0 6px,#232847 6px 12px)", "#eef0ff"),
])
nums = "".join([
    t.bignum(f"{risk['score']:.0f}", f"Crisis risk · {t.LEVEL_LABEL[risk['level']]}", "shield", t.LEVEL_TONE[risk["level"]]),
    t.bignum(f"{report['mentions']:,}", "Mentions, 24h", "forum", "info"),
    t.bignum(f"{pending}", "Replies to review", "fact_check", "warning"),
])
when = (f"right now ({ui.fmt_time(now)}), from live Bluesky, news and Mastodon posts" if is_live()
        else f"at {ui.fmt_time(now)} 2015 (dataset replay)")
t.render(f'<div class="bp-hero"><div><h1>Welcome back, <span>{t.esc(display_name())} team</span></h1>'
         f'<div class="sub">Here is how the conversation looks {when}.</div>'
         f'<div class="bp-pills">{pills}</div></div><div class="bp-bignums">{nums}</div></div>')
ui.status_banner(risk)

# ---- summary · volume chart · active incident ----------------------------------------------------
df = ui.windows_df().tail(72)
c1, c2, c3 = st.columns([1, 1.9, 1.05])
with c1, st.container(border=True, height=380):
    alerts = int(db.query_df("SELECT COUNT(*) AS n FROM alerts WHERE brand=? AND window_end > datetime(?, '-24 hours')",
                             (workspace(), w["window_end"])).loc[0, "n"])
    types = report["types"]
    rows = [("fact_check", "Replies pending", pending), ("notifications", "Alerts, 24h", alerts),
            ("report", "Complaints", types.get("Complaint", 0)), ("bug_report", "Bug reports", types.get("Bug Report", 0)),
            ("help", "Questions", types.get("Question", 0)), ("thumb_up", "Praise", types.get("Praise", 0))]
    t.render(t.card_title("list_alt", "Summary") + '<div class="bp-list">' + "".join(
        f'<div class="bp-row" style="padding:9px 2px"><div class="ic">{t.icon(i, 18)}</div><div class="d" style="margin:0">{a}</div>'
        f'<div class="time" style="font-size:13px;color:var(--bp-text);font-weight:600">{v:,}</div></div>' for i, a, v in rows) + "</div>")
    st.page_link("views/approvals.py", label="Review replies", icon=":material/arrow_forward:")
with c2:
    fig = go.Figure()
    for s, label in (("negative", "Negative"), ("neutral", "Neutral"), ("positive", "Positive")):
        fig.add_bar(x=df["window_end"], y=df[s], name=label, marker_color=ui.SENTIMENT_COLORS[s], marker_line_width=0)
    fig.update_layout(barmode="stack", bargap=0.25, title=dict(text="Mention volume by sentiment", x=0.01, y=0.97,
                                                                font=dict(family="Poppins", size=15, color="#f2f3ff")))
    fig = ui.chart_layout(fig, 368)
    fig.update_layout(legend=dict(x=0, xanchor="left", y=-0.12, yanchor="top"), margin=dict(t=40, b=40))
    st.plotly_chart(fig, use_container_width=True)
with c3:
    issue = db.query_df("SELECT name, recent, growth, recommendation, samples FROM clusters WHERE brand=? AND window_end=? "
                        "AND severity IN ('Critical','High') ORDER BY id LIMIT 3", (workspace(), w["window_end"]))
    if len(issue):
        top = issue.iloc[0]
        items = "".join(f'<div class="item"><span>{t.esc(n)}</span><b>{r}</b></div>' for n, r in zip(issue["name"], issue["recent"]))
        t.render(f'<div class="bp-feature" style="min-height:368px"><div class="k">{t.icon("bolt", 16, "#fff", True)}Active incident</div>'
                 f'<div class="t">{t.esc(top["name"])}</div>'
                 f'<div class="d">{top["recent"]} posts in 2h · {top["growth"]:+.0f}% growth</div>'
                 f'<div class="row">{items}</div>'
                 f'<div class="d" style="margin-top:14px">{t.icon("subdirectory_arrow_right", 16, "#fff")} {t.esc(top["recommendation"])}</div></div>')
    else:
        t.render(f'<div class="bp-feature" style="min-height:368px;background:linear-gradient(160deg,#2f3a7a,#1d2456)">'
                 f'<div class="k">{t.icon("verified_user", 16, "#fff", True)}No active incident</div>'
                 f'<div class="t">All systems normal</div><div class="d">No complaint topic is growing fast enough to escalate. '
                 f'The Brand Risk agent re-checks every hour.</div></div>')

# ---- risk trend · agent pipeline -------------------------------------------------------------
c1, c2 = st.columns([1.9, 1.05])
with c1:
    fig = go.Figure()
    for lo, hi, name in ((50, 70, "High"), (70, 100, "Critical")):
        fig.add_hrect(y0=lo, y1=hi, fillcolor=ui.LEVEL_COLORS[name], opacity=0.07, line_width=0)
    fig.add_scatter(x=df["window_end"], y=df["risk_score"], mode="lines", name="Risk score", showlegend=False,
                    line=dict(width=2.5, color=t.CHART["line"], shape="spline", smoothing=0.6),
                    fill="tozeroy", fillcolor="rgba(124,108,255,0.12)")
    fig.update_yaxes(range=[0, 100])
    fig.update_layout(title=dict(text="Crisis risk score", x=0.01, y=0.96, font=dict(family="Poppins", size=15, color="#f2f3ff")))
    st.plotly_chart(ui.chart_layout(fig, 300), use_container_width=True)
with c2, st.container(border=True, height=314):
    t.render(t.card_title("account_tree", "Agent pipeline · last hour") + '<div>' + "".join(
        f'<div class="bp-step"><div class="n">{i}</div><div><div class="t">{t.esc(e["agent"])}</div>'
        f'<div class="d">{t.esc(e["message"])}</div></div><div class="ms_r">{e["ms"]} ms</div></div>'
        for i, e in enumerate(w["payload"]["log"], 1)) + "</div>")
