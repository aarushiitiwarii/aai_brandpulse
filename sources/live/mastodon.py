"""Mastodon public hashtag timelines (no key) on mastodon.social."""
from sources.live.common import post, session, strip_html, to_local

INSTANCE = "https://mastodon.social"


def fetch(identity: str, cfg: dict, since: str | None) -> list[dict]:
    out = []
    for tag in cfg.get("mastodon_tags", []):
        r = session.get(f"{INSTANCE}/api/v1/timelines/tag/{tag}", params={"limit": 40}, timeout=15)
        r.raise_for_status()
        for s in r.json():
            if s.get("language") not in (None, "en"):
                continue
            acct = s["account"]
            out.append(post(id=f"masto:{s['id']}", source="mastodon", brand=identity, handle="@" + acct["acct"],
                            text=strip_html(s.get("content", "")), created_at=to_local(s["created_at"]),
                            url=s.get("url") or s.get("uri"), followers=acct.get("followers_count"),
                            likes=s.get("favourites_count"), reposts=s.get("reblogs_count")))
    return out
