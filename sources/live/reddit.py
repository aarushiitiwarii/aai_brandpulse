"""Reddit via the official API (PRAW, read-only app auth). Needs a free 'script' app:
https://www.reddit.com/prefs/apps -> REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env.
"""
import os
from functools import lru_cache

from sources.live.common import post, to_local


def enabled() -> bool:
    return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))


@lru_cache
def _client():
    import praw
    return praw.Reddit(client_id=os.getenv("REDDIT_CLIENT_ID"), client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
                       user_agent=os.getenv("REDDIT_USER_AGENT", "brand-monitor/0.1"), check_for_async=False)


def fetch(identity: str, cfg: dict, since: str | None) -> list[dict]:
    reddit = _client()
    subs = list(reddit.subreddit("+".join(cfg.get("subreddits", []))).new(limit=50)) if cfg.get("subreddits") else []
    query = cfg.get("news_query") or identity
    subs += list(reddit.subreddit("all").search(query, sort="new", time_filter="day", limit=50))
    out = []
    for s in subs:
        text = s.title + (f" — {s.selftext[:400]}" if s.selftext else "")
        out.append(post(id=f"reddit:{s.id}", source="reddit", brand=identity,
                        handle=f"u/{s.author.name}" if s.author else "u/[deleted]", text=text,
                        created_at=to_local(s.created_utc), url=f"https://www.reddit.com{s.permalink}",
                        likes=s.score, reposts=s.num_comments))
    return out
