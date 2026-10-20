"""Agent 9 - Campaign Intelligence: reach, engagement, sentiment and (simulated)
conversions per campaign hashtag, combined into a Campaign Success Score.

Tracks configured campaigns plus real hashtags auto-discovered in our brand's posts.
Clicks/conversions are SIMULATED: clicks = 25% of engagements, conversion rate seeded
per hashtag in the 1-3% range typical of published social ad benchmarks.
"""
import math

from core import db
from core.config import our_brand, settings
from sources.enrich import rng_for

MIN_MENTIONS = 8


def _metrics(tag: str, df) -> dict:
    reach = int(df["followers"].sum())
    engagement = int(df["retweet_count"].sum() * 3 + df["likes"].sum())
    clicks = engagement * 0.25
    cvr = float(rng_for("cvr" + tag).uniform(0.01, 0.03))
    conversions = int(round(clicks * cvr))
    sentiment = float(df["sentiment_score"].mean())
    eng_rate = engagement / max(reach, 1)
    score = 100 * (0.35 * (sentiment + 1) / 2
                   + 0.25 * min(1.0, eng_rate / 0.02)            # 2% engagement rate = excellent
                   + 0.20 * min(1.0, math.log10(reach + 1) / 6)
                   + 0.20 * min(1.0, conversions / 50))
    return {
        "hashtag": tag, "mentions": len(df), "reach": reach, "engagement": engagement,
        "engagement_rate": round(eng_rate * 100, 2), "sentiment": round(sentiment, 3),
        "positive_pct": round(100 * (df["sentiment"] == "positive").mean(), 1),
        "negative_pct": round(100 * (df["sentiment"] == "negative").mean(), 1),
        "clicks": int(clicks), "conversion_rate": round(cvr * 100, 2), "conversions": conversions,
        "success_score": round(score, 1),
    }


def analyze(now: str) -> list[dict]:
    df = db.query_df(
        "SELECT p.hashtags, p.followers, p.retweet_count, p.likes, p.is_synthetic, e.sentiment, e.sentiment_score "
        "FROM posts p JOIN enrichment e ON e.post_id=p.id WHERE p.brand=? AND p.created_at <= ? "
        f"AND p.hashtags != '' AND e.sentiment IS NOT NULL AND {db.live_filter()}", (our_brand(), now))
    if df.empty:
        return []
    tags = df["hashtags"].str.split().explode()
    configured = {c["hashtag"].lower(): c for c in settings().get("campaigns", [])}
    counts = tags.value_counts()
    tracked = [t for t in counts.index if t in configured or counts[t] >= MIN_MENTIONS]
    out = []
    for tag in tracked:
        sub = df[df["hashtags"].str.split().map(lambda hs: tag in hs)]
        m = _metrics(tag, sub)
        m["synthetic"] = bool(configured.get(tag, {}).get("synthetic", False))
        m["source"] = "configured" if tag in configured else "auto-discovered"
        out.append(m)
    return sorted(out, key=lambda m: -m["mentions"])


def run(now: str) -> tuple[list[dict], str]:
    camps = analyze(now)
    if not camps:
        return [], "No campaign hashtags active yet"
    best = max(camps, key=lambda c: c["success_score"])
    return camps, f"Tracking {len(camps)} hashtags. Best: {best['hashtag']} (score {best['success_score']:.0f})"
