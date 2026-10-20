"""Agent 3 - Sentiment & Emotion: positive/neutral/negative plus an emotion
(Angry, Frustrated, Confused, Excited, Disappointed, ...) and a sentence embedding
used later by the Trend agent. Runs local HuggingFace models; results are stored once.
"""
from core import db, models


def analyze(posts: list[dict]) -> int:
    todo = [p for p in posts if not p.get("sentiment")]
    if not todo:
        return 0
    texts = [p["text"] for p in todo]
    sents = models.sentiment(texts)
    emos = models.emotion(texts)
    for p, (s, ss), (e, es) in zip(todo, sents, emos):
        p.update(sentiment=s, sentiment_score=ss, emotion=e, emotion_score=es)
    db.executemany(
        "INSERT INTO enrichment(post_id, sentiment, sentiment_score, emotion, emotion_score) "
        "VALUES (?1, ?2, ?3, ?4, ?5) ON CONFLICT(post_id) DO UPDATE SET "
        "sentiment=?2, sentiment_score=?3, emotion=?4, emotion_score=?5",
        [(p["id"], p["sentiment"], p["sentiment_score"], p["emotion"], p["emotion_score"]) for p in todo],
    )
    have = db.load_embeddings(p["id"] for p in todo)
    missing = [p for p in todo if p["id"] not in have]
    if missing:
        db.save_embeddings([p["id"] for p in missing], models.embed([p["text"] for p in missing]))
    return len(todo)


def run(posts: list[dict]) -> tuple[list[dict], str]:
    n = analyze(posts)
    total = len(posts) or 1
    neg = sum(p["sentiment"] == "negative" for p in posts)
    emos = {}
    for p in posts:
        emos[p["emotion"]] = emos.get(p["emotion"], 0) + 1
    top = ", ".join(f"{k} {v}" for k, v in sorted(emos.items(), key=lambda x: -x[1])[:3])
    return posts, f"Scored {n} new posts. Negative {neg / total:.0%}. Top emotions: {top or '-'}"
