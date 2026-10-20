"""Demo tool: injects a growing burst of SYNTHETIC complaints into the replay.

Volume grows window by window (e.g. 12 -> 45 -> 140 posts/hour) so the Trend, Risk
and Early-Warning agents have a crisis to detect live.
"""
import numpy as np
import pandas as pd

from core import db
from core.config import active_brands, is_live, our_brand
from sources.enrich import enrich

TEMPLATES = [
    "The latest {app} update broke check-in, it just spins forever",
    "Can't log in to the {app} since the update this morning. Flight in 2 hours!!",
    "{app} crashes every time I open my boarding pass after updating",
    "Is anyone else's {app} broken? Update wiped my boarding pass",
    "Why is the {app} login broken? Tried 10 times. Fix it",
    "New {app} version won't load my reservation. Stuck at the airport",
    "{app} update = can't check in, can't see seat, can't do anything. Great.",
    "Seriously, the {app} keeps logging me out after the update. Frustrated",
    "Mobile check-in down? {app} says error 503 after updating",
    "Third time today the {app} crashed. Who tested this update?",
]
def app_names(brand: str) -> list[str]:
    handle = active_brands()[brand]["handle"]
    return [f"{handle} app", f"{brand} app", f"{brand} iPhone app", f"{brand} Android app"]
INFLUENCERS = [("@TechReviewer", 212_000), ("@TravelDealsDaily", 98_000)]


def inject(start_ts: str, waves=(12, 45, 140), wave_minutes: int = 60, seed: int = 7) -> int:
    brand = our_brand()
    rng = np.random.default_rng(seed + len(start_ts))
    start = pd.Timestamp(start_ts)
    apps = app_names(brand)
    slug = brand.lower().replace(" ", "") + ("-live" if is_live() else "")
    rows, n = [], 0
    for w, count in enumerate(waves):
        offsets = np.sort(rng.uniform(0, wave_minutes * 60, count))
        for off in offsets:
            text = rng.choice(TEMPLATES).format(app=rng.choice(apps))
            rows.append({
                "id": f"crisis-{slug}-{start.strftime('%m%d%H%M')}-{n}",
                "source": "crisis (synthetic)",
                "brand": brand,
                "handle": f"@user{rng.integers(10_000, 999_999)}",
                "text": text,
                "created_at": (start + pd.Timedelta(minutes=w * wave_minutes, seconds=float(off)))
                .strftime("%Y-%m-%d %H:%M:%S"),
                "retweet_count": int(rng.poisson(2 + w * 2)),
                "location": "",
                "is_synthetic": 1,
                "label_sentiment": None,
                "label_reason": None,
            })
            n += 1
    df = enrich(pd.DataFrame(rows)).assign(is_live=int(is_live()))
    # two influencer posts in the second wave, so impact scoring has something to find
    for i, (handle, followers) in enumerate(INFLUENCERS):
        idx = waves[0] + 5 + i * 10
        if idx < len(df):
            df.loc[idx, ["handle", "followers", "verified"]] = [handle, followers, 1]
            df.loc[idx, "text"] = f"Heads up travelers: the new {brand} app update is breaking check-in for a lot of people. Use the website for now."
            df.loc[idx, "retweet_count"] = 380 + i * 150
    db.insert_posts(df)
    db.kv_set(db.crisis_key(), {"start": start_ts, "posts": n})
    return n

