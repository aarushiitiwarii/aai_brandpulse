"""One-time setup: load the real dataset, fill gaps, and pre-compute per-post agent outputs.

    python -m scripts.prepare            # load + local models (sentiment, emotion, embeddings)
    python -m scripts.prepare --llm      # also classify our brand's posts with Groq (uses free quota)
    python -m scripts.prepare --reset    # clear every workspace's replay (keeps posts and caches)
"""
import argparse
import time

from agents import classifier, influence, listening, sentiment
from core import db
from core.config import brands, our_brand
from sources.dataset_replay import load_tweets
from sources.enrich import enrich, synthetic_campaign_posts


def all_posts():
    return listening.fetch("0000", "9999")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="classify our brand's posts with Groq")
    ap.add_argument("--reset", action="store_true", help="clear replay results and restart the clock")
    args = ap.parse_args()

    db.init_db()
    if args.reset:
        for b in brands():
            db.reset_runtime(b)
        print("Replay results cleared for all workspaces.")
        return

    df = load_tweets()
    camp = synthetic_campaign_posts()
    print(f"Loaded {len(df)} real tweets ({df['created_at'].min()} -> {df['created_at'].max()}) "
          f"+ {len(camp)} synthetic campaign posts")
    db.insert_posts(enrich(df))
    if len(camp):
        db.insert_posts(enrich(camp))

    posts = all_posts()
    todo = [p for p in posts if not p.get("sentiment")]
    print(f"Running sentiment/emotion/embedding models on {len(todo)} posts (CPU, a few minutes)...")
    t0 = time.time()
    for i in range(0, len(todo), 512):
        sentiment.analyze(todo[i:i + 512])
        print(f"  {min(i + 512, len(todo))}/{len(todo)}  ({time.time() - t0:.0f}s)")

    posts = all_posts()
    classifier.run(posts, use_llm=False)   # rules for everyone first
    influence.score(posts)
    print("Rule-based classification and impact scores done.")

    if args.llm:
        mine = [p for p in all_posts() if p["brand"] == our_brand() and p.get("type_source") != "llm"]
        print(f"Classifying {len(mine)} {our_brand()} posts with Groq...")
        for i in range(0, len(mine), 100):
            _, msg = classifier.run(mine[i:i + 100], use_llm=True)
            print(f"  {min(i + 100, len(mine))}/{len(mine)}  {msg}")
    print("Done. Start the dashboard with:  streamlit run app.py")


if __name__ == "__main__":
    main()
