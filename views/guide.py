import streamlit as st

from core.config import our_brand
from ui import common as ui
from ui import theme as t

ui.page_header("How it works", "What the system does, how to run the demo, and what each metric means.")

with st.container(border=True):
    t.render(t.card_title("hub", "Overview") +
             f'<div class="bp-meta">Eleven AI agents read every social post about <b>{our_brand()}</b> and five competitors, '
             'work out what people are saying and how they feel, detect problems before they become a PR crisis, and '
             'draft replies that a person approves. The data is ~14,500 real tweets about US airlines from 16–24 Feb 2015 '
             '(Kaggle, Twitter US Airline Sentiment), replayed hour by hour as if they were arriving live.</div>')

t.section("Replay vs Live", "Every workspace can run on the 2015 dataset or on today's public posts")
lc, rc = st.columns(2)
with lc, st.container(border=True):
    t.render(t.card_title("history", "Replay 2015") +
             '<div class="bp-meta">Real tweets from 16–24 Feb 2015, streamed hour by hour with the time machine. '
             'Human labels in the dataset let us measure accuracy. Follower counts and campaign numbers are synthetic.</div>')
with rc, st.container(border=True):
    t.render(t.card_title("sensors", "Live now") +
             '<div class="bp-meta">Public posts fetched every 90 seconds: <b>Bluesky</b> (real follower counts), '
             '<b>Google News</b> headlines, <b>Mastodon</b> hashtags, and <b>Reddit</b> once free API keys are added. '
             'The agents re-run every 10 minutes over the last hour, and pages refresh on their own. '
             'Retired airlines go live as their successor: US Airways (now American Airlines), '
             'Virgin America (now Alaska Airlines).</div>')

t.section("Agent pipeline", "The Master Orchestrator (agent 11, built with LangGraph) runs this chain once per hour of posts")
STEPS = [
    ("travel_explore", "Listening", "Collects every mention of the brand, competitors, products and executives"),
    ("mood", "Sentiment & emotion", "Positive / neutral / negative, plus the feeling behind it"),
    ("category", "Classification", "Complaint, question, praise, bug report, feature request, comparison"),
    ("group", "Influence", "Impact score from audience size, engagement and intensity"),
    ("bubble_chart", "Trend discovery", "Groups posts into topics and measures their growth"),
    ("shield", "Brand risk", "Crisis score vs. normal levels, with a 2-hour forecast and alerts"),
    ("edit_note", "Response drafting", "Writes replies in the brand's voice for the top posts"),
    ("fact_check", "Human approval", "A person approves, edits or rejects every reply"),
    ("campaign", "Campaigns", "Reach, engagement, sentiment and conversions per hashtag"),
    ("summarize", "Executive report", "Brand health, competitor benchmark, AI briefing"),
]
cells = "".join(
    f'<div class="bp-kpi" style="padding:14px"><div class="label">{t.icon(ic)}<span>Agent {i}</span></div>'
    f'<div style="font-weight:600;font-size:14.5px;color:var(--bp-text);margin:6px 0 4px">{name}</div>'
    f'<div style="font-size:12.5px;color:var(--bp-muted);line-height:1.4">{desc}</div></div>'
    for i, (ic, name, desc) in enumerate(STEPS, 1))
t.render(f'<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px">{cells}</div>'
         '<div class="bp-meta" style="margin-top:10px">Agent 11, the <b>Master Orchestrator</b>, runs agents 1–10 in order '
         'every hour and branches to an escalation alert when risk is high.</div>')

left, right = st.columns(2)
with left, st.container(border=True):
    t.render(t.card_title("play_circle", "Run the demo") + '<div class="bp-steps">' + "".join(
        f'<div class="bp-step"><div class="n">{i}</div><div><div class="t">{a}</div><div class="d">{b}</div></div></div>'
        for i, (a, b) in enumerate([
            ("Replay real data", "In the sidebar, advance by 1 day a few times. The Command Center fills with real conversations."),
            ("Simulate an outage", "Click <b>Simulate app outage</b>, then advance 1 hour three times. The system warns early, "
                                   "then raises a Crisis alert and routes it to the right team."),
            ("Review replies", "Open <b>Reply Approvals</b> to edit, approve or reject the AI's drafts."),
            ("Brief leadership", "Open <b>Executive Summary</b> and generate the AI briefing."),
        ], 1)) + "</div>")
with right, st.container(border=True):
    t.render(t.card_title("verified", "Accuracy") +
             '<div class="bp-meta">The dataset includes human labels, which the agents never see, so the AI can be tested honestly.</div>'
             '<div class="bp-list">'
             '<div class="bp-row"><div class="ic">' + t.icon("sentiment_satisfied", 20) + '</div><div><div class="t">Sentiment: 76.9% accuracy</div>'
             '<div class="d">Macro F1 0.735 on 14,485 tweets, with no training on this dataset.</div></div></div>'
             '<div class="bp-row"><div class="ic">' + t.icon("bubble_chart", 20) + '</div><div><div class="t">Topic discovery: purity 0.52</div>'
             '<div class="d">Clusters line up with human complaint reasons, versus a 0.31 majority-class baseline.</div></div></div>'
             '</div><div class="bp-meta">Full report: <code>python -m eval.evaluate</code></div>')

t.section("Glossary")
with st.container(border=True):
    t.render('<div class="bp-list">' + "".join(
        f'<div class="bp-row"><div style="width:150px;flex:none" class="t">{t.esc(k)}</div><div class="d">{t.esc(v)}</div></div>'
        for k, v in ui.GLOSSARY.items()) + "</div>")
