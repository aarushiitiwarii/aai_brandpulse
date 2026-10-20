"""Local HuggingFace models (CPU). Loaded lazily, once per process."""
from functools import lru_cache

import numpy as np

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
EMOTION_MODEL = "SamLowe/roberta-base-go_emotions"   # 28 GoEmotions labels
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# GoEmotions label -> the emotion set the brief asks for
EMOTION_MAP = {
    "anger": "Angry", "annoyance": "Frustrated", "disgust": "Angry",
    "disapproval": "Frustrated", "confusion": "Confused", "curiosity": "Confused",
    "disappointment": "Disappointed", "sadness": "Disappointed", "grief": "Disappointed",
    "remorse": "Disappointed", "embarrassment": "Disappointed",
    "excitement": "Excited", "joy": "Excited", "amusement": "Excited", "optimism": "Excited",
    "admiration": "Delighted", "love": "Delighted", "approval": "Delighted", "pride": "Delighted",
    "gratitude": "Grateful", "relief": "Grateful", "caring": "Grateful",
    "fear": "Worried", "nervousness": "Worried",
    "surprise": "Surprised", "realization": "Surprised", "desire": "Hopeful",
    "neutral": "Neutral",
}


@lru_cache
def _sentiment_pipe():
    from transformers import pipeline
    return pipeline("text-classification", model=SENTIMENT_MODEL, top_k=None,
                    truncation=True, max_length=128)


@lru_cache
def _emotion_pipe():
    from transformers import pipeline
    return pipeline("text-classification", model=EMOTION_MODEL, top_k=None,
                    truncation=True, max_length=128)


@lru_cache
def _embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


def _clean(texts):
    # cardiffnlp convention: mask user handles
    return [" ".join("@user" if w.startswith("@") and len(w) > 1 else w for w in str(t).split())
            for t in texts]


def sentiment(texts, batch_size=64):
    """-> list of (label, score in [-1, 1] = p(pos) - p(neg))"""
    out = []
    for scores in _sentiment_pipe()(_clean(texts), batch_size=batch_size):
        p = {s["label"].lower(): s["score"] for s in scores}
        label = max(p, key=p.get)
        out.append((label, round(p.get("positive", 0) - p.get("negative", 0), 4)))
    return out


def emotion(texts, batch_size=64, threshold=0.2):
    """-> list of (emotion, confidence). Picks the strongest non-neutral label above threshold."""
    out = []
    for scores in _emotion_pipe()(list(map(str, texts)), batch_size=batch_size):
        ranked = sorted(scores, key=lambda s: -s["score"])
        pick = next((s for s in ranked if s["label"] != "neutral" and s["score"] >= threshold),
                    ranked[0])
        out.append((EMOTION_MAP.get(pick["label"], "Neutral"), round(pick["score"], 4)))
    return out


def embed(texts, batch_size=128) -> np.ndarray:
    return _embedder().encode(list(map(str, texts)), batch_size=batch_size,
                              normalize_embeddings=True, show_progress_bar=False)
