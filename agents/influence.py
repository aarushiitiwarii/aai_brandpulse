"""Agent 4 - Influence Detection: impact score (0-100) per mention and a viral score.

impact = 50% reach (followers, log scale) + 20% engagement + 10% verified + 20% intensity
viral  = retweet volume + engagement relative to audience size (flags posts about to spread)
"""
import math

from core import db

VIRAL_THRESHOLD = 50


def impact_score(followers, retweets, likes, verified, sentiment_score, emotion) -> float:
    reach = min(1.0, math.log10((followers or 0) + 1) / 6)          # 1M followers = 1.0
    engagement = min(1.0, math.log10((retweets or 0) + (likes or 0) / 3 + 1) / 3)
    intensity = min(1.0, abs(sentiment_score or 0) * (1.2 if emotion in ("Angry", "Frustrated") else 1))
    return round(100 * (0.5 * reach + 0.2 * engagement + 0.1 * (verified or 0) + 0.2 * intensity), 1)


def viral_score(followers, retweets, likes) -> float:
    ratio = ((retweets or 0) * 3 + (likes or 0)) / ((followers or 0) + 50)
    v = 0.6 * math.log10(1 + (retweets or 0)) / 2.5 + 0.4 * math.log10(1 + ratio * 100) / 2
    return round(100 * min(1.0, v), 1)


def score(posts: list[dict]) -> int:
    todo = [p for p in posts if p.get("impact_score") is None]
    for p in todo:
        p["impact_score"] = impact_score(p["followers"], p["retweet_count"], p["likes"], p["verified"],
                                         p.get("sentiment_score"), p.get("emotion"))
        p["viral_score"] = viral_score(p["followers"], p["retweet_count"], p["likes"])
    db.executemany(
        "INSERT INTO enrichment(post_id, impact_score, viral_score) VALUES (?1, ?2, ?3) "
        "ON CONFLICT(post_id) DO UPDATE SET impact_score=?2, viral_score=?3",
        [(p["id"], p["impact_score"], p["viral_score"]) for p in todo],
    )
    return len(todo)


def run(posts: list[dict]) -> tuple[list[dict], str]:
    score(posts)
    top = max(posts, key=lambda p: p["impact_score"], default=None)
    viral = [p for p in posts if p["viral_score"] >= VIRAL_THRESHOLD]
    msg = f"Scored impact for {len(posts)} posts. {len(viral)} potentially viral."
    if top:
        msg += f" Top: {top['handle']} ({top['followers']:,} followers, impact {top['impact_score']:.0f})"
    return posts, msg
