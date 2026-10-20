import pandas as pd
import streamlit as st

from core import db
from core.config import brands, live_identity, settings
from sources.dataset_replay import time_bounds
from ui import common as ui
from ui import theme as t

t.inject()
t.render('<div style="text-align:center;margin:28px 0 8px">'
         '<div class="bp-badge" style="color:#c9c2ff;background:rgba(124,108,255,0.14);border-color:rgba(124,108,255,0.4)">'
         f'{t.icon("monitoring", 14)}{t.PRODUCT} · Brand intelligence</div>'
         '<h1 class="bp-display" style="font-size:46px;font-weight:400;margin:18px 0 6px;line-height:1.15">'
         'Choose your <span style="background:linear-gradient(90deg,#b3a8ff,#7cb0ff);-webkit-background-clip:text;'
         'color:transparent">workspace</span></h1>'
         '<div style="color:var(--bp-muted);font-size:15px;max-width:660px;margin:0 auto">'
         'Each airline has two modes. <b style="color:var(--bp-text)">Replay 2015</b> streams the real Feb 2015 tweets '
         'from the dataset. <b style="color:var(--bp-text)">Live now</b> monitors today\'s posts from Bluesky, Google News '
         'and Mastodon (and Reddit with free keys). Retired airlines go live as the airline they fly as today.</div></div>')

if not ui.data_ready():
    st.error("No data loaded. Put `Tweets.csv` in `data/raw/` and run `python -m scripts.prepare`.")
    st.stop()

stats = db.query_df(
    "SELECT p.brand, COUNT(*) AS n, AVG(e.sentiment='negative') AS neg, AVG(e.sentiment='positive') AS pos "
    "FROM posts p JOIN enrichment e ON e.post_id=p.id WHERE p.is_synthetic=0 AND p.is_live=0 GROUP BY p.brand"
).set_index("brand")
live_counts = db.query_df("SELECT brand, COUNT(*) AS n FROM posts WHERE is_live=1 GROUP BY brand").set_index("brand")["n"]
lo, hi = time_bounds()
total = (pd.Timestamp(hi) - pd.Timestamp(lo)).total_seconds()
colors = dict(zip(brands(), ui.CATEGORICAL))
live_names = {k: v.get("display_now", "").removeprefix("now ") for k, v in settings()["brands"].items()}


def open_workspace(brand: str, mode: str):
    st.query_params.update(brand=brand, mode=mode)
    st.session_state.update(brand=brand, mode=mode)
    st.rerun()


st.write("")
_, mid, _ = st.columns([0.06, 1, 0.06])
with mid:
    cols = st.columns(3, gap="medium")
    for i, b in enumerate(sorted(brands(), key=lambda x: -stats.loc[x, "n"] if x in stats.index else 0)):
        info, s = settings()["brands"][b], stats.loc[b] if b in stats.index else None
        retired = bool(info.get("now_flies_as"))
        clock = db.kv_get(db.clock_key(b))
        progress = max(0.0, min(1.0, (pd.Timestamp(clock) - pd.Timestamp(lo)).total_seconds() / total)) if clock else 0
        replay_badge = t.badge(f"Replay {progress:.0%}", "info", "history") if clock else ""
        live_badge = t.badge("Live available", "good", "sensors")
        name = t.esc(b) + (f'<span style="font-size:13px;color:var(--bp-muted);font-family:Inter"> '
                           f'({t.esc(info["display_now"])})</span>' if retired else "")
        live_from = live_names[b] if retired else b
        sub = (f'Brand retired · live data from {t.esc(live_from)} '
               f'({int(live_counts.get(live_identity(b), 0)):,} live posts)' if retired else
               f'{t.esc(info["handle"])} · {int(live_counts.get(b, 0)):,} live posts')
        initials = "".join(w[0] for w in b.split())[:2].upper()
        with cols[i % 3].container(border=True):
            t.render(
                f'<div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:10px">'
                f'<div style="width:46px;height:46px;border-radius:14px;background:{colors[b]};display:flex;align-items:center;'
                f'justify-content:center;font-family:Poppins;font-weight:600;color:#fff;font-size:17px;flex:none">{initials}</div>'
                f'<div style="flex:1;min-width:0"><div style="font-family:Poppins;font-size:18px;color:var(--bp-text);line-height:1.25">'
                f'{name}</div><div style="font-size:12.5px;color:var(--bp-muted);margin-top:2px">{sub}</div></div></div>'
                f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">{live_badge}{replay_badge}</div>'
                f'<div style="font-size:11.5px;color:var(--bp-muted);text-transform:uppercase;letter-spacing:.06em">Feb 2015 dataset</div>'
                f'<div style="display:flex;gap:18px;margin:4px 0 12px">'
                f'<div><div style="font-size:12px;color:var(--bp-muted)">Mentions</div>'
                f'<div style="font-family:Poppins;font-size:20px;color:var(--bp-text)">{int(s["n"]) if s is not None else 0:,}</div></div>'
                f'<div><div style="font-size:12px;color:var(--bp-muted)">Positive</div>'
                f'<div style="font-family:Poppins;font-size:20px;color:{t.CHART["positive"]}">{(s["pos"] if s is not None else 0):.0%}</div></div>'
                f'<div><div style="font-size:12px;color:var(--bp-muted)">Negative</div>'
                f'<div style="font-family:Poppins;font-size:20px;color:{t.CHART["negative"]}">{(s["neg"] if s is not None else 0):.0%}</div></div></div>')
            a, c = st.columns(2)
            if a.button("Live now", key=f"live-{b}", use_container_width=True, type="primary", icon=":material/sensors:",
                        help=f"Today's posts about {live_from}" if retired else "Today's posts from live sources"):
                open_workspace(b, "live")
            if c.button("Replay 2015", key=f"replay-{b}", use_container_width=True, icon=":material/history:",
                        help="Stream the real Feb 2015 tweets"):
                open_workspace(b, "replay")

t.render('<div style="text-align:center;color:var(--bp-muted);font-size:12.5px;margin-top:18px">'
         'Replay: real tweets from 16–24 Feb 2015 (Kaggle, Twitter US Airline Sentiment). '
         'Live: public posts fetched in real time. Workspace selection only, no login required.</div>')
