"""Bluesky: public search (no key) + real follower counts from getProfiles."""
import re

from sources.live.common import post, session, to_local

API = "https://api.bsky.app/xrpc"          # public.api.bsky.app rejects search requests
# flight-tracker and spotter bots post thousands of "UAL123 at 32000 ft" messages
BOT_TEXT = re.compile(r"\bft\b.*heading|SkyBot|#?\b(UAL|DAL|AAL|SWA|ASA)\d{2,4}\b|squawk|ADS-B|flightaware", re.I)
_followers: dict[str, tuple[int, int]] = {}


def _profiles(dids: list[str]):
    todo = [d for d in dict.fromkeys(dids) if d not in _followers]
    for i in range(0, len(todo), 25):
        r = session.get(f"{API}/app.bsky.actor.getProfiles", params=[("actors", d) for d in todo[i:i + 25]], timeout=15)
        r.raise_for_status()
        for p in r.json().get("profiles", []):
            verified = (p.get("verification") or {}).get("verifiedStatus") == "valid"
            _followers[p["did"]] = (p.get("followersCount", 0), int(verified))


def fetch(identity: str, cfg: dict, since: str | None) -> list[dict]:
    items = []
    for q in cfg.get("bluesky_queries", []):
        params = {"q": q, "sort": "latest", "limit": 100}
        if since:
            params["since"] = since
        r = session.get(f"{API}/app.bsky.feed.searchPosts", params=params, timeout=15)
        r.raise_for_status()
        items += r.json().get("posts", [])
    items = [p for p in items
             if "bot" not in p["author"]["handle"].lower() and not BOT_TEXT.search(p["record"].get("text", ""))
             and (not p["record"].get("langs") or "en" in p["record"]["langs"])]
    _profiles([p["author"]["did"] for p in items])
    out = []
    for p in items:
        handle, rkey = p["author"]["handle"], p["uri"].rsplit("/", 1)[-1]
        followers, verified = _followers.get(p["author"]["did"], (0, 0))
        out.append(post(id=f"bsky:{p['author']['did'][-12:]}:{rkey}", source="bluesky", brand=identity,
                        handle="@" + handle, text=p["record"].get("text", ""), created_at=to_local(p["indexedAt"]),
                        url=f"https://bsky.app/profile/{handle}/post/{rkey}", followers=followers,
                        likes=p.get("likeCount"), reposts=p.get("repostCount"), verified=verified))
    return out
