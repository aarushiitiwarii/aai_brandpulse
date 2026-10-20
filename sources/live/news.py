"""Google News RSS search (no key). Headlines mentioning the airline from the last day."""
import hashlib
import xml.etree.ElementTree as ET

from sources.live.common import post, session, strip_html, to_local


def fetch(identity: str, cfg: dict, since: str | None) -> list[dict]:
    q = cfg.get("news_query")
    if not q:
        return []
    r = session.get("https://news.google.com/rss/search",
                    params={"q": f"{q} when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"}, timeout=15)
    r.raise_for_status()
    out = []
    for item in ET.fromstring(r.content).iter("item"):
        title = item.findtext("title", "")
        outlet = item.findtext("source", "") or "News"
        if title.endswith(f" - {outlet}"):
            title = title[: -len(outlet) - 3]
        link = item.findtext("link", "")
        out.append(post(id="news:" + hashlib.md5(link.encode()).hexdigest()[:16], source="news", brand=identity,
                        handle=outlet, text=strip_html(title), created_at=to_local(item.findtext("pubDate", "")),
                        url=link))
    return out
