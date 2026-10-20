"""Shared Streamlit pieces: page header, the sidebar (replay time machine or live panel), helpers, chart colors."""
import json
import time

import pandas as pd
import streamlit as st

from core import db, llm
from core.config import (active_brands, display_name, is_live, mode, our_brand, selected_brand, settings,
                         workspace)
from ui import theme

# Sentiment is polarity -> diverging pair with a gray midpoint
SENTIMENT_COLORS = {"positive": theme.CHART["positive"], "neutral": theme.CHART["neutral"], "negative": theme.CHART["negative"]}
# Status palette (always shown with a text label, never color alone)
LEVEL_COLORS = {"Low": "#2ecc71", "Medium": "#fabe28", "High": "#ff8a3d", "Critical": "#ff4d6d",
                "Warning": "#fabe28", "Positive": "#7c6cff"}
LEVEL_WORDS = theme.LEVEL_LABEL
# Categorical, fixed order: our brand always gets slot 1
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]  # dark-mode steps

# Plain-English explanations reused as tooltips and on the "How it works" page
GLOSSARY = {
    "Brand Health": "One number (0-100) for how people feel about the brand in the last 24 hours. "
                    "Combines how positive posts are, how many are complaints, and what big accounts say. "
                    "Above 60 is good, below 40 is poor.",
    "Crisis risk": "How likely a PR problem is right now (0-100). It rises when complaints suddenly spike "
                   "above normal, a complaint topic grows fast, angry posts increase, or big accounts join in.",
    "Forecast": "Where the crisis risk is heading in the next 2 hours, based on its recent trend and "
                "fast-growing complaint topics. Lets the team act before a problem explodes.",
    "Topic": "A group of posts about the same thing (e.g. 'Lost Baggage'), found automatically by the AI "
             "without anyone defining the topics in advance.",
    "Growth": "Posts about a topic in the last 2 hours compared with the 2 hours before. +300% means 4x more.",
    "Impact score": "How much a single post matters (0-100): big audience, lots of retweets, a verified "
                    "account and strong emotion all push it up.",
    "Viral": "A post whose retweets and engagement are unusually high for its audience, so it may spread fast.",
    "Mention type": "What the post is: Complaint, Question, Praise, Feature Request, Bug Report or Comparison.",
    "Emotion": "The feeling behind the post: Angry, Frustrated, Confused, Disappointed, Excited, Grateful…",
    "Synthetic": "Made-up but realistic data we added because the real dataset doesn't have it "
                 "(follower counts, likes, campaign numbers and the crisis demo). Everything else is real.",
}


def brand_colors() -> dict:
    brands = [our_brand()] + [b for b in active_brands() if b != our_brand()]
    return {b: CATEGORICAL[i] for i, b in enumerate(brands)}


def chart_layout(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", size=12, color=theme.CHART["text"]),
                      hoverlabel=dict(bgcolor="#151a38", bordercolor="#2b3260", font=dict(color="#eef0ff", family="Inter")),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
                      hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest")
    fig.update_xaxes(showgrid=False, linecolor=theme.CHART["grid"])
    fig.update_yaxes(gridcolor=theme.CHART["grid"], zeroline=False)
    return fig


def fmt_time(ts: str) -> str:
    """'2015-02-20 15:00:00' -> 'Fri 20 Feb, 15:00'"""
    return pd.Timestamp(ts).strftime("%a %d %b, %H:%M")


def page_header(title: str, what: str):
    theme.inject()
    now = db.kv_get(db.clock_key())
    if is_live():
        chip = f"Live · updated {pd.Timestamp(now).strftime('%H:%M')}" if now else "Live · warming up"
    else:
        chip = f"Replay · {fmt_time(now)} 2015" if now else None
    theme.page_header(title, what, chip)


@st.cache_resource
def engine():
    """The process-wide live engine (background thread)."""
    from graph.live_engine import LiveEngine
    return LiveEngine()


def data_ready() -> bool:
    return db.query_df("SELECT COUNT(*) AS n FROM posts").loc[0, "n"] > 0


def run_steps(n: int, where=None):
    from graph import orchestrator
    use_llm = st.session_state.get("use_llm", True)
    bar = (where or st.sidebar).progress(0.0, text="AI agents are analysing...")
    for i in range(n):
        if orchestrator.finished():
            st.session_state.stop_autoplay = True
            break
        state = orchestrator.step(use_llm=use_llm)
        bar.progress((i + 1) / n, text=f"Analysed hour {i + 1} of {n} ({fmt_time(state['now'])})")
    bar.empty()


def _workspace_card(sb):
    brand = our_brand()
    initials = "".join(w[0] for w in selected_brand().split())[:2].upper()
    with sb:
        theme.render(f'<div class="bp-side-label">Workspace</div>'
                     f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0 8px">'
                     f'<div style="width:34px;height:34px;border-radius:10px;background:{brand_colors()[brand]};display:flex;'
                     f'align-items:center;justify-content:center;font-family:Poppins;font-weight:600;color:#fff;font-size:13px">'
                     f'{initials}</div><div><div style="font-weight:600;color:var(--bp-text);font-size:14px;line-height:1.3">'
                     f'{theme.esc(display_name())}</div><div style="font-size:12px;color:var(--bp-muted)">'
                     f'{theme.esc(active_brands()[brand]["handle"])} · {len(active_brands()) - 1} competitors</div></div></div>')
    choice = sb.segmented_control("Mode", ["replay", "live"], default=mode(), key="mode_switch",
                                  format_func=lambda m: "Replay 2015" if m == "replay" else "Live now",
                                  label_visibility="collapsed")
    if choice and choice != mode():
        st.session_state.mode = choice
        st.query_params["mode"] = choice
        st.session_state.stop_autoplay = True
        st.rerun()
    if sb.button("Switch workspace", use_container_width=True, icon=":material/swap_horiz:"):
        st.session_state.stop_autoplay = True
        for k in ("brand", "mode"):
            st.session_state.pop(k, None)
            st.query_params.pop(k, None)
        st.rerun()
    sb.divider()


def _replay_panel(sb):
    from graph import orchestrator
    from sources.dataset_replay import time_bounds

    now = orchestrator.clock()
    lo, hi = time_bounds()
    total = (pd.Timestamp(hi) - pd.Timestamp(lo)).total_seconds()
    done = max(0.0, min(1.0, (pd.Timestamp(now) - pd.Timestamp(lo)).total_seconds() / total))
    with sb:
        theme.render(f'<div class="bp-side-label">Replay</div><div class="bp-clock">{fmt_time(now)} 2015</div>')
    sb.progress(done, text=f"{done:.0%} of the Feb 16–24 dataset")
    c1, c2, c3 = sb.columns(3)
    for col, hours, label in ((c1, 1, "1h"), (c2, 6, "6h"), (c3, 24, "1d")):
        if col.button(label, use_container_width=True, icon=":material/fast_forward:",
                      help=f"Analyse the next {hours} hour(s) of posts"):
            run_steps(hours)
            st.rerun()
    st.session_state.setdefault("autoplay", False)
    if st.session_state.pop("stop_autoplay", False):
        st.session_state.autoplay = False  # widget not created yet in this run, so this is allowed
    sb.toggle("Auto-play", key="autoplay", help="Keeps analysing one hour every few seconds")
    sb.caption("Replays real tweets hour by hour, as if they were arriving live.")
    return now


SOURCE_TONE = {"ok": "good", "error": "critical", "disabled": "neutral"}


def _live_panel(sb):
    from sources.live import LABELS, status_key
    from sources.live.common import now_local

    st.session_state.pop("stop_autoplay", None)
    ident = our_brand()
    eng = engine()
    status = eng.status(ident)
    state = status.get("state", "starting")
    label = {"backfilling": f"Loading last 24h · {status.get('progress', '')}", "analysing": "Analysing new posts",
             "live": "Monitoring", "error": "Error", "starting": "Starting"}.get(state, state)
    recent = db.query_df("SELECT COUNT(*) AS n FROM posts WHERE is_live=1 AND brand=? "
                         "AND created_at > datetime('now', 'localtime', '-1 hour')", (ident,)).loc[0, "n"]
    sources = db.kv_get(status_key(ident), {})
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin:6px 0;font-size:13px">'
        f'<span style="color:var(--bp-text-2)">{LABELS[k]}</span>'
        f'{theme.badge(("%d posts" % v["count"]) if v["state"] == "ok" else v["state"].title(), SOURCE_TONE[v["state"]])}</div>'
        for k, v in sources.items())
    last = (status.get("last_poll") or "–")[11:16]
    with sb:
        theme.render(f'<div class="bp-side-label">Live</div>'
                     f'<div style="display:flex;align-items:center;gap:8px"><span class="bp-chip" style="padding:4px 10px">'
                     f'<span class="dot"></span>LIVE</span>'
                     f'<span style="font-size:13px;color:var(--bp-text-2)">{theme.esc(label)}</span></div>'
                     f'<div style="font-size:12.5px;color:var(--bp-muted);margin:8px 0 4px">{recent} posts in the last hour · '
                     f'last fetch {last}</div>{rows}')
        if sources.get("reddit", {}).get("state") == "disabled":
            st.caption("Reddit: add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env to enable.")
        if state == "error":
            st.caption(f"Engine error: {status.get('error')}")
    if sb.button("Fetch now", use_container_width=True, icon=":material/refresh:"):
        eng.fetch_now(ident)
        st.toast("Fetching new posts…")
    return now_local()


def sidebar():
    sb = st.sidebar
    if not data_ready():
        sb.warning("No data yet. Run `python -m scripts.prepare` first.")
        return
    from sources import crisis_injector

    _workspace_card(sb)
    now = _live_panel(sb) if is_live() else _replay_panel(sb)

    sb.divider()
    with sb:
        theme.render('<div class="bp-side-label">Scenario</div>')
    crisis = db.kv_get(db.crisis_key())
    wave = 10 if is_live() else 60
    if crisis:
        follow = ("Detection follows over the next 30 minutes." if is_live()
                  else "Advance 3 hours to watch detection and escalation.")
        with sb:
            theme.render(f'{theme.badge("Crisis scenario running", "critical", "bolt")}'
                         f'<div style="font-size:12.5px;color:var(--bp-muted);margin-top:6px">'
                         f'Started {fmt_time(crisis["start"])}. {follow}</div>')
    elif sb.button("Simulate app outage", use_container_width=True, icon=":material/bolt:",
                   help=f"Injects a growing burst of synthetic complaints (12 → 45 → 140 per {wave} min) "
                        "about a broken app update. Clearly labelled as synthetic."):
        crisis_injector.inject(now, wave_minutes=wave)
        st.rerun()

    with sb.expander("Settings", icon=":material/settings:"):
        st.session_state.setdefault("use_llm", True)
        st.toggle("AI language model (Groq)", key="use_llm", disabled=not llm.available() or is_live(),
                  help="Off = keyword rules and templates instead (no API calls). Live mode always uses the model.")
        if llm.available():
            st.caption(f"{db.kv_get('llm_calls', 0)} model calls · {db.kv_get('llm_tokens', 0):,} tokens")
        else:
            st.caption("No GROQ_API_KEY in .env; using rule-based fallbacks.")
        if st.button("Rebuild live history" if is_live() else "Restart replay", use_container_width=True,
                     icon=":material/restart_alt:"):
            db.reset_runtime()
            if is_live():
                engine().fetch_now(our_brand())
            st.session_state.stop_autoplay = True
            st.rerun()


def _signature() -> tuple:
    return (db.kv_get(db.clock_key()), engine().status(our_brand()).get("state"),
            db.query_df("SELECT COUNT(*) AS n FROM posts WHERE is_live=1 AND brand=?", (our_brand(),)).loc[0, "n"])


def live_heartbeat():
    """Live mode: re-render the page when the engine has new posts or a new analysis window."""
    seen = _signature()

    @st.fragment(run_every="20s")
    def _beat():
        if _signature() != seen:
            st.rerun()
    _beat()


def finish():
    """Runs after the page renders: auto-play in replay, auto-refresh in live."""
    if is_live():
        live_heartbeat()
    elif st.session_state.get("autoplay") and not st.session_state.get("stop_autoplay") and data_ready():
        time.sleep(1.0)
        run_steps(1)
        st.rerun()


def latest_window(offset: int = 0) -> dict | None:
    df = db.query_df("SELECT * FROM windows WHERE brand=? ORDER BY window_end DESC LIMIT 1 OFFSET ?",
                     (workspace(), offset))
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    row["payload"] = json.loads(row["payload"])
    return row


def windows_df() -> pd.DataFrame:
    df = db.query_df("SELECT window_end, mentions, positive, neutral, negative, risk_score, risk_level, "
                     "predicted_level, health FROM windows WHERE brand=? ORDER BY window_end", (workspace(),))
    df["window_end"] = pd.to_datetime(df["window_end"])
    return df


def need_windows() -> dict:
    """Latest analysed hour, or an empty state with a start button if nothing has run yet."""
    w = latest_window()
    if w is None and is_live():
        status = engine().status(our_brand())
        with st.container(border=True):
            theme.render(theme.card_title("cloud_sync", "Connecting to live sources") +
                         '<div class="bp-meta">Fetching the last 24 hours of posts from Bluesky, Google News and Mastodon, '
                         f'then running the agents over them. Progress: {theme.esc(status.get("progress", "starting"))}. '
                         'This page refreshes on its own.</div>')
        live_heartbeat()
        st.stop()
    if w is None:
        with st.container(border=True):
            theme.render(theme.card_title("play_circle", "No data analysed yet") +
                         '<div class="bp-meta">Replay the first day of real tweets through the agent pipeline. '
                         'This takes a few seconds.</div>')
            if st.button("Analyse first 24 hours", type="primary", icon=":material/play_arrow:"):
                run_steps(24, where=st)
                st.rerun()
        st.stop()
    return w


def status_story(risk: dict) -> tuple[str, str, str, str | None]:
    """-> (level, headline, detail, action) in plain English for the status banner."""
    level, issue = risk["level"], risk.get("top_issue")
    n, g = risk.get("top_issue_mentions"), risk.get("top_issue_growth")
    topic = issue or "complaints"
    detail = (f"{n} posts in the last 2 hours" + (f", up {g:.0f}% on the previous 2 hours." if g and g > 0 else ".")
              if issue else "Conversation volume and sentiment are within normal ranges.")
    if level == "Critical":
        head = f"Possible PR crisis: {topic} is spreading fast"
    elif level == "High":
        head = f"Complaints are rising: {topic} needs attention"
    elif risk["predicted_level"] in ("High", "Critical"):
        head, level = f"{topic} is accelerating; risk expected to rise within 2 hours", "Warning"
    elif level == "Medium":
        head = f"Mostly normal. Keep an eye on {topic}"
    else:
        head = "All quiet: nothing unusual in the conversation"
    action = risk.get("recommendation") if level in ("Critical", "High", "Warning") else None
    return level, head, detail, action


def status_banner(risk: dict):
    level, head, detail, action = status_story(risk)
    theme.banner(level, head, detail, action)
