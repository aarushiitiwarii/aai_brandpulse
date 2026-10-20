"""Entry point and navigation. Run with:  streamlit run app.py

No brand chosen -> workspace picker. Brand + mode chosen (kept in the session and the URL as
?brand=...&mode=replay|live) -> that workspace: the 2015 dataset replay, or live posts from today.
"""
import streamlit as st

from core import db
from core.config import brands, our_brand, set_active_brand, set_active_mode, workspace
from ui import common as ui
from ui import theme

st.set_page_config(page_title=theme.PRODUCT, page_icon="assets/icon.svg", layout="wide")
st.logo("assets/logo.svg", size="large", icon_image="assets/icon.svg")
db.init_db()
theme.inject()

# Page links drop query params, so the session is the source of truth; the URL copy
# just survives browser refreshes and makes links shareable.
brand = st.query_params.get("brand") or st.session_state.get("brand")
mode = st.query_params.get("mode") or st.session_state.get("mode") or "replay"
if brand in brands():
    mode = mode if mode in ("replay", "live") else "replay"
    st.session_state.brand, st.session_state.mode = brand, mode
    if st.query_params.get("brand") != brand or st.query_params.get("mode") != mode:
        st.query_params.update(brand=brand, mode=mode)
else:
    st.navigation([st.Page("views/login.py", title="Choose workspace", icon=":material/login:")],
                  position="hidden").run()
    st.stop()

set_active_brand(brand)
set_active_mode(mode)
if mode == "live":
    ui.engine().watch(our_brand())   # start polling + analysing this airline's live data
pending = db.query_df("SELECT COUNT(*) AS n FROM responses WHERE brand=? AND status='pending'",
                      (workspace(),)).loc[0, "n"]
nav = st.navigation({
    "Overview": [st.Page("views/home.py", title="Command Center", icon=":material/space_dashboard:", default=True)],
    "Monitor": [st.Page("views/live_feed.py", title="Live Feed", icon=":material/dynamic_feed:"),
                st.Page("views/trends_risk.py", title="Topics & Risk", icon=":material/crisis_alert:")],
    "Respond": [st.Page("views/approvals.py", title=f"Reply Approvals · {pending}", icon=":material/fact_check:")],
    "Insights": [st.Page("views/executive.py", title="Executive Summary", icon=":material/summarize:"),
                 st.Page("views/competitors.py", title="Competitors", icon=":material/leaderboard:"),
                 st.Page("views/campaigns.py", title="Campaigns", icon=":material/campaign:")],
    "Help": [st.Page("views/guide.py", title="How it works", icon=":material/help:")],
})
ui.sidebar()
nav.run()
ui.finish()
