"""Agent 10 - Executive Insights: Brand Health score, competitor benchmark and a
plain-English brand summary.

Brand Health (0-100) = 40% net sentiment + 25% (1 - complaint rate)
                     + 20% reach-weighted sentiment + 15% influencer sentiment
"""
import json

import pandas as pd

from core import db, llm
from core.config import active_brands, our_brand, settings, workspace
from sources.dataset_replay import shift

INFLUENCER_FOLLOWERS = 10_000


def brand_health(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    n = len(df)
    net = ((df["sentiment"] == "positive").sum() - (df["sentiment"] == "negative").sum()) / n
    complaint_rate = df["mention_type"].isin(["Complaint", "Bug Report"]).mean()
    w = df["followers"].clip(lower=1)
    reach_sent = float((df["sentiment_score"] * w).sum() / w.sum())
    infl = df[df["followers"] >= INFLUENCER_FOLLOWERS]
    infl_sent = float(infl["sentiment_score"].mean()) if len(infl) else float(df["sentiment_score"].mean())
    score = 100 * (0.40 * (net + 1) / 2 + 0.25 * (1 - complaint_rate)
                   + 0.20 * (reach_sent + 1) / 2 + 0.15 * (infl_sent + 1) / 2)
    return round(score, 1)


def _window_df(start: str, end: str) -> pd.DataFrame:
    return db.query_df(
        "SELECT p.id, p.brand, p.handle, p.text, p.followers, p.created_at, e.sentiment, e.sentiment_score, "
        "e.emotion, e.mention_type, e.impact_score, e.viral_score FROM posts p JOIN enrichment e ON e.post_id=p.id "
        f"WHERE p.created_at > ? AND p.created_at <= ? AND e.sentiment IS NOT NULL AND {db.live_filter()}", (start, end))


def metrics(now: str, hours: int = 24) -> dict:
    df = _window_df(shift(now, -60 * hours), now)
    brand = our_brand()
    mine = df[df["brand"] == brand]
    comp = []
    for b in active_brands():
        sub = df[df["brand"] == b]
        if len(sub):
            comp.append({"brand": b, "mentions": len(sub),
                         "positive_pct": round(100 * (sub["sentiment"] == "positive").mean(), 1),
                         "neutral_pct": round(100 * (sub["sentiment"] == "neutral").mean(), 1),
                         "negative_pct": round(100 * (sub["sentiment"] == "negative").mean(), 1),
                         "health": brand_health(sub), "is_us": b == brand})
    issue = db.query_df("SELECT name, recent, growth, severity FROM clusters WHERE brand=? AND window_end=? "
                        "AND severity NOT IN ('Positive') ORDER BY id LIMIT 1", (workspace(), now))
    praise = db.query_df("SELECT name FROM clusters WHERE brand=? AND window_end=? AND severity='Positive' "
                         "ORDER BY size DESC LIMIT 1", (workspace(), now))
    top_inf = mine.sort_values("impact_score", ascending=False).head(1)
    n = len(mine) or 1
    return {
        "as_of": now, "hours": hours, "brand": brand, "mentions": len(mine),
        "positive_pct": round(100 * (mine["sentiment"] == "positive").sum() / n, 1),
        "neutral_pct": round(100 * (mine["sentiment"] == "neutral").sum() / n, 1),
        "negative_pct": round(100 * (mine["sentiment"] == "negative").sum() / n, 1),
        "health": brand_health(mine),
        "major_concern": issue.loc[0, "name"] if len(issue) else None,
        "concern_severity": issue.loc[0, "severity"] if len(issue) else None,
        "positive_trend": praise.loc[0, "name"] if len(praise) else None,
        "top_influencer": top_inf.iloc[0]["handle"] if len(top_inf) else None,
        "top_influencer_followers": int(top_inf.iloc[0]["followers"]) if len(top_inf) else None,
        "emotions": mine["emotion"].value_counts().to_dict(),
        "types": mine["mention_type"].value_counts().to_dict(),
        "competitors": comp,
    }


def summary(m: dict, risk: dict | None = None) -> str:
    """LLM narrative for executives; template fallback."""
    if llm.available():
        prompt = ("Write a brand health briefing for executives (max 120 words, 3 short paragraphs: "
                  "overall health, main risk and recommended action, competitor position). "
                  "Use only these numbers:\n" + json.dumps({"metrics": m, "risk": risk}, default=str))
        try:
            return llm.chat(prompt, smart=True, temperature=0.3, max_tokens=300)
        except llm.LLMUnavailable:
            pass
    comp = sorted(m["competitors"], key=lambda c: -c["positive_pct"])
    best = comp[0]["brand"] if comp else "-"
    return (f"Today's {m['brand']} brand health is {m['health']:.0f}/100 across {m['mentions']} mentions "
            f"({m['positive_pct']}% positive, {m['neutral_pct']}% neutral, {m['negative_pct']}% negative).\n\n"
            f"Major concern: {m['major_concern'] or 'none'}. Risk level: {(risk or {}).get('level', 'n/a')}. "
            f"Recommendation: {(risk or {}).get('recommendation', 'monitor')}.\n\n"
            f"Most positive brand in the last {m['hours']}h: {best}.")


def run(now: str) -> tuple[dict, str]:
    m = metrics(now)
    return m, f"Brand Health {m['health']:.0f}/100 ({m['positive_pct']}% pos / {m['negative_pct']}% neg, 24h)"
