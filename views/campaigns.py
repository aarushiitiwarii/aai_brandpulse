import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agents import campaign
from ui import common as ui
from ui import theme as t

ui.page_header("Campaigns", "Performance of each tracked hashtag: reach, engagement, sentiment, conversions, "
                            "and a combined success score.")
w = ui.need_windows()

camps = campaign.analyze(w["window_end"])
if not camps:
    st.info("No campaign hashtags yet.")
    st.stop()
df = pd.DataFrame(camps)
top = df.sort_values("success_score", ascending=False).iloc[0]

t.kpi_row([
    t.kpi("Top campaign", t.esc(top["hashtag"]), "campaign", f"{top['mentions']} mentions"),
    t.kpi("Success score", f"{top['success_score']:.0f}", "insights", "sentiment, engagement, reach, conversions", unit="/ 100"),
    t.kpi("Reach*", f"{top['reach']:,}", "visibility", "sum of followers of posting accounts"),
    t.kpi("Conversions*", f"{top['conversions']:,}", "shopping_cart", f"{top['conversion_rate']}% conversion rate"),
])

t.section("Success score by hashtag", "35% sentiment · 25% engagement rate · 20% reach · 20% conversions")
d = df.sort_values("success_score")
fig = go.Figure(go.Bar(x=d["success_score"], y=d["hashtag"], orientation="h", marker_color="#7c6cff",
                       text=d["success_score"].map(lambda v: f"{v:.0f}"), textposition="outside",
                       customdata=d[["mentions", "positive_pct", "engagement_rate"]],
                       hovertemplate="%{y}<br>Score %{x:.0f}<br>%{customdata[0]} mentions<br>"
                                     "%{customdata[1]}% positive<br>%{customdata[2]}% engagement<extra></extra>"))
fig.update_xaxes(range=[0, 100])
st.plotly_chart(ui.chart_layout(fig, 90 + 36 * len(d)), use_container_width=True)

table = pd.DataFrame({
    "Hashtag": df["hashtag"], "Source": df.apply(lambda r: "Synthetic demo" if r["synthetic"] else
                                                 r["source"].replace("-", " ").capitalize(), axis=1),
    "Mentions": df["mentions"], "Reach*": df["reach"], "Engagement rate %": df["engagement_rate"],
    "Positive %": df["positive_pct"], "Negative %": df["negative_pct"], "Conversions*": df["conversions"],
    "Success": df["success_score"],
})
st.dataframe(table, hide_index=True, use_container_width=True, column_config={
    "Success": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
    "Reach*": st.column_config.NumberColumn(format="%d")})
st.caption("* Reach and engagement use synthetic follower and like counts; clicks and conversions are simulated "
           "(25% click-through, 1–3% conversion). #FlyUnited2015 is a synthetic demo campaign; other hashtags are real.")
