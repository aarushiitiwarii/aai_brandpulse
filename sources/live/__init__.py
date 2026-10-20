"""Live sources for Live mode: Bluesky, Google News, Mastodon (no keys) and Reddit (free app keys).

poll(identity) fetches new posts for one airline flying today, tags them, stores them with
is_live=1, and records each source's health in kv `live_status:<identity>`.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd

from core import db
from core.config import settings
from sources.enrich import tag
from sources.live import bluesky, mastodon, news, reddit
from sources.live.common import now_local

SOURCES = {"bluesky": bluesky, "news": news, "mastodon": mastodon, "reddit": reddit}
LABELS = {"bluesky": "Bluesky", "news": "Google News", "mastodon": "Mastodon", "reddit": "Reddit"}


def status_key(identity: str) -> str:
    return f"live_status:{identity}"


def poll(identity: str) -> int:
    """Fetch and store new posts for one live identity. Returns how many posts were new."""
    cfg = settings()["live_identities"][identity]
    status = db.kv_get(status_key(identity), {})
    last = db.kv_get(f"live_last_poll:{identity}")
    since_dt = (datetime.fromisoformat(last) - timedelta(minutes=15)) if last else \
        datetime.now(timezone.utc) - timedelta(hours=settings()["live"]["backfill_hours"])
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for name, module in SOURCES.items():
        if name == "reddit" and not reddit.enabled():
            status[name] = {"state": "disabled", "count": 0, "at": None, "error": "Add REDDIT_CLIENT_ID / SECRET to .env"}
            continue
        try:
            got = module.fetch(identity, cfg, since)
            rows += got
            status[name] = {"state": "ok", "count": len(got), "at": now_local(), "error": None}
        except Exception as e:  # one broken source must not stop the others
            status[name] = {"state": "error", "count": 0, "at": now_local(), "error": str(e)[:160]}
    db.kv_set(status_key(identity), status)
    db.kv_set(f"live_last_poll:{identity}", datetime.now(timezone.utc).isoformat())
    if not rows:
        return 0
    df = pd.DataFrame(rows).drop_duplicates("id")
    since_local = since_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    # hashtag timelines aren't time-filtered, and link-only posts carry nothing to analyse
    df = df[(df["created_at"] >= since_local) & (df["text"].str.strip().str.len() >= 15)]
    if df.empty:
        return 0
    known = set(db.query_df(f"SELECT id FROM posts WHERE id IN ({','.join('?' * len(df))})", tuple(df["id"]))["id"]) \
        if len(df) < 900 else set()
    db.insert_posts(tag(df))            # replaces existing rows too, so engagement counts stay fresh
    return int((~df["id"].isin(known)).sum())
