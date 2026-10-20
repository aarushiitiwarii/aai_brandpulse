import streamlit as st

from agents import approval
from core import db
from core.config import workspace
from sources.dataset_replay import shift
from ui import common as ui
from ui import theme as t

ui.page_header("Reply Approvals", "Replies drafted by the Response agent. Every reply needs human approval; "
                                  "nothing is posted automatically (publishing is simulated in this demo).")

pending = db.query_df(
    "SELECT r.id, r.draft, r.tone, r.created_at, p.handle, p.text, p.followers, e.mention_type, e.sentiment, "
    "e.emotion, e.impact_score FROM responses r JOIN posts p ON p.id=r.post_id "
    "LEFT JOIN enrichment e ON e.post_id=p.id WHERE r.brand=? AND r.status='pending'", (workspace(),))
decided = db.query_df("SELECT status, COUNT(*) AS n FROM responses WHERE brand=? AND status!='pending' GROUP BY status",
                      (workspace(),))
counts = dict(zip(decided["status"], decided["n"]))
clock = db.kv_get(db.clock_key())
fresh = pending["created_at"] >= shift(clock, -6 * 60) if clock else True
pending = pending.assign(fresh=fresh).sort_values(["fresh", "impact_score"], ascending=[False, False])
stale = pending[~pending["fresh"]] if clock else pending.iloc[0:0]

t.kpi_row([
    t.kpi("Awaiting review", f"{len(pending)}", "pending_actions", f"{len(stale)} older than 6 hours"),
    t.kpi("Published", f"{counts.get('published', 0)}", "check_circle", "approved by a reviewer"),
    t.kpi("Rejected", f"{counts.get('rejected', 0)}", "cancel", "including dismissed stale drafts"),
])

c1, c2, c3 = st.columns([2, 1, 1])
show = c1.segmented_control("Show", [5, 10, 20, 30], default=10, format_func=lambda n: f"Top {n}",
                            label_visibility="collapsed") or 10
c3.button(f"Dismiss {len(stale)} stale", use_container_width=True, icon=":material/delete_sweep:",
          disabled=stale.empty, key="dismiss", help="Reject drafts for posts older than 6 hours")
if st.session_state.get("dismiss"):
    for rid in stale["id"]:
        approval.decide(int(rid), "reject", note="stale (older than 6h)")
    st.rerun()

if pending.empty:
    st.info("Nothing to review. New drafts appear as the replay advances.")
for _, r in pending.head(show).iterrows():
    with st.container(border=True):
        a, b = st.columns([1, 1.25], gap="large")
        with a:
            tone = {"negative": "critical", "neutral": "neutral", "positive": "good"}.get(r["sentiment"], "neutral")
            t.render(t.author(r["handle"], f"{int(r['followers']):,} followers* · {ui.fmt_time(r['created_at'])}") +
                     t.post(r["text"]) +
                     f'<div class="bp-tags">{t.badge(str(r["sentiment"]).title(), tone)}'
                     f'{t.badge(r["mention_type"], "info")}{t.badge(str(r["emotion"]), "neutral")}'
                     f'{t.badge("Impact %.0f" % r["impact_score"], "neutral", "bolt")}</div>')
        with b:
            text = st.text_area(f"Draft reply · {r['tone']} tone", r["draft"], key=f"t{r['id']}", height=118)
            over = len(text) > 280
            x, y, z = st.columns([1.3, 1, 1])
            x.caption(f"{len(text)} / 280 characters" + (" · too long" if over else ""))
            if y.button("Reject", key=f"r{r['id']}", use_container_width=True, icon=":material/close:"):
                approval.decide(int(r["id"]), "reject", note="rejected by reviewer")
                st.toast("Reply rejected", icon=":material/close:")
                st.rerun()
            if z.button("Approve", key=f"a{r['id']}", use_container_width=True, type="primary",
                        icon=":material/check:", disabled=over):
                approval.decide(int(r["id"]), "edit" if text != r["draft"] else "approve", text)
                st.toast("Reply approved and published", icon=":material/check:")
                st.rerun()

with st.expander("Decision history", icon=":material/history:"):
    done = db.query_df("SELECT r.decided_at AS decided, r.status, p.handle AS account, p.text AS post, "
                       "r.final_text AS reply, r.note FROM responses r JOIN posts p ON p.id=r.post_id "
                       "WHERE r.brand=? AND r.status!='pending' ORDER BY r.id DESC LIMIT 200", (workspace(),))
    st.dataframe(done, hide_index=True, use_container_width=True)
