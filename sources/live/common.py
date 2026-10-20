"""Shared helpers for live sources: HTTP session, time conversion, post shape."""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

TIME_FMT = "%Y-%m-%d %H:%M:%S"
_TAGS = re.compile(r"<[^>]+>")

session = requests.Session()
session.headers["User-Agent"] = "BrandPulse/0.1 (student brand-monitoring project)"


def now_local() -> str:
    return datetime.now().strftime(TIME_FMT)


def to_local(value) -> str:
    """ISO-8601 string, RFC-822 string or UTC epoch seconds -> local wall-clock 'YYYY-MM-DD HH:MM:SS'."""
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif "," in value[:5]:                      # RFC-822 (RSS pubDate)
        dt = parsedate_to_datetime(value)
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime(TIME_FMT)


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub(" ", text or "")).strip()


def post(*, id, source, brand, handle, text, created_at, url, followers=0, likes=0, reposts=0, verified=0) -> dict:
    return {"id": id, "source": source, "brand": brand, "handle": handle, "text": text[:1000],
            "created_at": created_at, "retweet_count": int(reposts or 0), "likes": int(likes or 0),
            "followers": int(followers or 0), "verified": int(bool(verified)), "location": "",
            "is_synthetic": 0, "is_live": 1, "url": url, "label_sentiment": None, "label_reason": None}
