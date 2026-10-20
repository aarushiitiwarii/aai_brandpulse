"""Agent 1 - Social Listening: pulls every mention in the current replay window.

Tracks brand, competitors, products, executives and campaign hashtags (tags were
extracted at ingest by sources/enrich.py; injected posts are tagged the same way).
"""
from core import db

POST_COLUMNS = """
p.id, p.source, p.brand, p.handle, p.text, p.created_at, p.retweet_count, p.likes,
p.followers, p.verified, p.hashtags, p.entities, p.is_synthetic, p.url,
e.sentiment, e.sentiment_score, e.emotion, e.emotion_score, e.mention_type, e.type_source,
e.impact_score, e.viral_score
"""


def fetch(start: str, end: str, brand: str | None = None) -> list[dict]:
    """Posts with start < created_at <= end, joined with any agent outputs already stored."""
    sql = f"SELECT {POST_COLUMNS} FROM posts p LEFT JOIN enrichment e ON e.post_id = p.id " \
          f"WHERE p.created_at > ? AND p.created_at <= ? AND {db.live_filter()}"
    params = [start, end]
    if brand:
        sql += " AND p.brand = ?"
        params.append(brand)
    df = db.query_df(sql + " ORDER BY p.created_at", params)
    df = df.astype(object).where(df.notna(), None)   # NaN -> None so "not yet scored" checks work
    return df.to_dict("records")


def run(start: str, end: str) -> tuple[list[dict], str]:
    posts = fetch(start, end)
    by_brand = {}
    for p in posts:
        by_brand[p["brand"]] = by_brand.get(p["brand"], 0) + 1
    summary = ", ".join(f"{b}: {n}" for b, n in sorted(by_brand.items(), key=lambda x: -x[1]))
    return posts, f"Collected {len(posts)} mentions ({summary or 'none'})"
