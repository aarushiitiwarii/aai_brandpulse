"""Fills fields the real dataset lacks. Everything here is SYNTHETIC and seeded (reproducible).

- followers / verified : long-tail distribution per handle (dataset has no follower counts)
- likes                : derived from real retweet_count + follower tier
- hashtags / entities  : extracted from the real text (not synthetic)
- campaign posts       : a synthetic #FlyUnited2015 campaign so Campaign Intelligence has data
"""
import hashlib
import re

import numpy as np
import pandas as pd

from core.config import active_brands, settings

HASHTAG_RE = re.compile(r"#\w+")


def rng_for(key: str) -> np.random.Generator:
    seed = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def followers_for(handle: str) -> tuple[int, int]:
    """Most users < 500 followers, ~1% are 50k-500k 'influencers'. Same handle -> same value."""
    rng = rng_for(handle.lower())
    if rng.random() < 0.012:
        followers = int(10 ** rng.uniform(4.7, 5.7))
    else:
        followers = int(np.clip(rng.lognormal(mean=5.2, sigma=1.5), 3, 45_000))
    verified = int(followers > 50_000 and rng.random() < 0.6)
    return followers, verified


def likes_for(post_id: str, retweets: int, followers: int) -> int:
    rng = rng_for("likes" + post_id)
    return int(retweets * rng.uniform(2, 6) + followers * rng.uniform(0.0005, 0.004) + rng.poisson(0.6))


def extract_entities(text: str) -> list[str]:
    """Which tracked names (brands, products, executives) a post mentions."""
    low = text.lower()
    found = []
    for brand, info in active_brands().items():
        names = [info["handle"]] + info.get("aliases", [])
        if any(n.lower() in low for n in names):
            found.append(brand)
        found += [p for p in info.get("products", []) if p.lower() in low]
        found += [e for e in info.get("executives", []) if e.lower() in low]
    return sorted(set(found))


def tag(df: pd.DataFrame) -> pd.DataFrame:
    """Real-text features only (hashtags, tracked entities). Used alone for live posts, which have real counts."""
    df = df.copy()
    df["hashtags"] = df["text"].map(lambda t: " ".join(h.lower() for h in HASHTAG_RE.findall(t)))
    df["entities"] = df["text"].map(lambda t: ",".join(extract_entities(t)))
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    fv = df["handle"].map(followers_for)
    df["followers"] = [f for f, _ in fv]
    df["verified"] = [v for _, v in fv]
    df["likes"] = [likes_for(i, r, f) for i, r, f in zip(df["id"], df["retweet_count"], df["followers"])]
    return tag(df)


# --- synthetic campaign -------------------------------------------------------------

_CAMPAIGN_POSITIVE = [
    "Loving the new {tag} lie-flat seats, best sleep I've had on a plane",
    "{tag} upgrade to Economy Plus made my week, thanks @united",
    "The {tag} lounge passes are a great touch, nice job @united",
    "Wifi actually worked the whole flight {tag} impressed",
    "Crew on UA{num} was fantastic {tag}",
    "Just booked the {tag} fare sale, cheapest SFO to NYC I've seen",
]
_CAMPAIGN_NEUTRAL = [
    "Anyone tried the {tag} deal yet? Worth it?",
    "Saw the {tag} ad at the airport, what's included?",
    "Does the {tag} promo apply to MileagePlus award tickets?",
]
_CAMPAIGN_NEGATIVE = [
    "{tag} promo code doesn't work at checkout @united",
    "So much hype for {tag} and my flight is still delayed 3 hours",
    "{tag} fare disappeared after I logged in, bait and switch?",
]


def synthetic_campaign_posts() -> pd.DataFrame:
    rows = []
    for camp in settings().get("campaigns", []):
        if not camp.get("synthetic"):
            continue
        tag = camp["hashtag"]
        rng = rng_for(tag)
        start, end = pd.Timestamp(camp["start"]), pd.Timestamp(camp["end"])
        n = 160
        offsets = np.sort(rng.uniform(0, (end - start).total_seconds(), n))
        for i, off in enumerate(offsets):
            pool = rng.choice(3, p=[0.6, 0.25, 0.15])
            tmpl = rng.choice([_CAMPAIGN_POSITIVE, _CAMPAIGN_NEUTRAL, _CAMPAIGN_NEGATIVE][pool])
            text = tmpl.format(tag=tag, num=rng.integers(100, 1999))
            rows.append({
                "id": f"campaign-{tag[1:].lower()}-{i}",
                "source": "twitter (synthetic)",
                "brand": settings()["our_brand"],
                "handle": f"@traveler{rng.integers(1000, 99999)}",
                "text": text,
                "created_at": (start + pd.Timedelta(seconds=float(off))).strftime("%Y-%m-%d %H:%M:%S"),
                "retweet_count": int(rng.poisson(1.5)),
                "location": "",
                "is_synthetic": 1,
                "label_sentiment": None,
                "label_reason": None,
            })
    return pd.DataFrame(rows)
