import pandas as pd
import streamlit as st

from agents import approval, listening, responder
from agents.classifier import TYPES
from agents.influence import VIRAL_THRESHOLD
from core.config import active_brands, is_live, our_brand, settings
from sources.dataset_replay import shift
from sources.live.common import now_local
from ui import common as ui
from ui import theme as t

PLATFORM = {"twitter": "X (Twitter)", "twitter (synthetic)": "X (synthetic)", "crisis (synthetic)": "Synthetic",
            "bluesky": "Bluesky", "news": "News", "mastodon": "Mastodon", "reddit": "Reddit"}

ui.page_header("Live Feed", "Every collected mention with the agents' analysis: type, sentiment, emotion and impact. "
                            + ("Newest first, refreshed automatically." if is_live() else
                               "Sorted by impact, so the posts that matter most come first."))
w = ui.need_windows()
now = now_local() if is_live() else w["window_end"]   # live feed runs up to this second

c = st.columns([1.1, 1.6, 1.6, 1.4, 1])
hours = c[0].selectbox("Time range", [1, 3, 6, 12, 24], index=1, format_func=lambda h: f"Last {h}h")
brands = c[1].multiselect("Brand", list(active_brands()), default=[our_brand()])
types = c[2].multiselect("Mention type", TYPES, help=ui.GLOSSARY["Mention type"])
sents = c[3].multiselect("Sentiment", ["negative", "neutral", "positive"], format_func=str.title)
with c[4]:
    st.write("")
    viral_only = st.toggle("Viral only", help=ui.GLOSSARY["Viral"])

posts = listening.fetch(shift(now, -60 * hours), now)
posts = [p for p in posts if (not brands or p["brand"] in brands) and (not types or p["mention_type"] in types)
         and (not sents or p["sentiment"] in sents) and (not viral_only or (p["viral_score"] or 0) >= VIRAL_THRESHOLD)]
if is_live():   # live: newest first, like a real feed
    posts.sort(key=lambda p: p["created_at"], reverse=True)
else:
    posts.sort(key=lambda p: -(p["impact_score"] or 0))

if not posts:
    st.info("No mentions match these filters.")
    st.stop()

df = pd.DataFrame(posts)
neg = (df["sentiment"] == "negative").mean()
t.kpi_row([
    t.kpi("Mentions", f"{len(df):,}", "forum", f"last {hours}h, filtered"),
    t.kpi("Negative share", f"{neg:.0%}", "sentiment_dissatisfied", "of filtered mentions"),
    t.kpi("Top emotion", str(df["emotion"].dropna().mode().iloc[0]) if df["emotion"].notna().any() else "–",
          "psychology", "most common feeling"),
    t.kpi("Potentially viral", f"{int((df['viral_score'] >= VIRAL_THRESHOLD).sum())}", "rocket_launch", "high engagement velocity"),
])

view = pd.DataFrame({
    "Time": df["created_at"].str[11:16], "Platform": df["source"].map(PLATFORM).fillna(df["source"]),
    "Brand": df["brand"], "Account": df["handle"], "Post": df["text"],
    "Type": df["mention_type"], "Sentiment": df["sentiment"].str.title(), "Emotion": df["emotion"],
    "Impact": df["impact_score"], "Viral": df["viral_score"] >= VIRAL_THRESHOLD,
    "Followers" if is_live() else "Followers*": df["followers"], "Link": df["url"],
})
if not is_live():
    view = view.drop(columns=["Link"])
st.dataframe(view, use_container_width=True, hide_index=True, height=460, column_config={
    "Post": st.column_config.TextColumn(width="large"),
    "Impact": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f", help=ui.GLOSSARY["Impact score"]),
    "Emotion": st.column_config.TextColumn(help=ui.GLOSSARY["Emotion"]),
    "Followers*": st.column_config.NumberColumn(format="%d", help="Synthetic: the dataset has no follower counts"),
    "Followers": st.column_config.NumberColumn(format="%d", help="Real follower count from the platform"),
    "Link": st.column_config.LinkColumn(display_text="Open", help="Original post or article"),
})
st.caption("Live posts from Bluesky, Google News and Mastodon (plus Reddit when keys are set). Follower counts are real "
           "for Bluesky and Mastodon; news articles have none." if is_live() else
           "* Followers and likes are synthetic. Post text, timestamps and retweets are real.")

ours = [p for p in posts if p["brand"] == our_brand()][:50]
if ours:
    with st.expander("Draft a reply with AI", icon=":material/edit_note:"):
        pick = st.selectbox("Post", ours, format_func=lambda p: f"{p['handle']}: {p['text'][:100]}")
        tones = ["friendly", "professional", "luxury", "startup"]
        tone = st.segmented_control("Brand voice", tones, default=settings()["tone"], format_func=str.title)
        if st.button("Generate draft", type="primary", icon=":material/auto_awesome:"):
            text, tone = responder.draft(pick, tone=tone or settings()["tone"])
            approval.submit(pick, text, tone, now)
            st.success(f"{text}\n\nSent to Reply Approvals for review.")
