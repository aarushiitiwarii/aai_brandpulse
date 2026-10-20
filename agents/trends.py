"""Agent 5 - Trend Discovery: clusters the brand's recent mentions into topics and
measures how fast each topic is growing.

1000 individual posts -> "Cluster: App Login Failures, 140 mentions, +300% in 2h, Critical".
Embeddings (MiniLM) + Ward agglomerative clustering find the clusters
(HDBSCAN labelled almost every short tweet as noise; see eval/results.md); c-TF-IDF finds key terms; Groq names them.
"""
import json
import re

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import CountVectorizer

from agents import listening
from core import db, llm
from core.config import our_brand, settings, workspace
from sources.dataset_replay import shift

_NOISE = re.compile(r"@\w+|https?://\S+|#")

ROUTES = {  # team -> whole-word keywords; the team with the most matches wins
    "Product / Engineering": r"apps?|website|site|online|login|log in|logging|crash\w*|error|wifi|wi-fi|"
                             r"boarding pass|mobile|iphone|android|glitch|bug",
    "Baggage Services": r"bags?|luggage|suitcases?|baggage|lost",
    "Billing & Revenue": r"refunds?|fees?|charged?|price|fares?|money|credit|vouchers?",
    "Operations + Customer Support": r"delay\w*|cancel\w*|late|weather|gates?|connections?|missed|stuck|"
                                     r"stranded|diverted|tarmac|crew|pilot|maintenance",
    "Customer Support": r"hold|phone|calls?|agents?|rude|service|staff|response|help|answer",
}


def route(text: str) -> str:
    scores = {team: len(re.findall(rf"\b(?:{pattern})\b", text, re.I)) for team, pattern in ROUTES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "Customer Support"


DISTANCE_THRESHOLD = 2.5   # Ward merge distance on unit-length MiniLM vectors
MIN_CLUSTER = 4


def cluster_embeddings(X: np.ndarray) -> np.ndarray:
    """Ward clustering; the number of clusters follows the data. Tiny clusters -> -1 (noise)."""
    labels = AgglomerativeClustering(n_clusters=None, distance_threshold=DISTANCE_THRESHOLD,
                                     linkage="ward").fit_predict(X)
    sizes = np.bincount(labels)
    return np.where(sizes[labels] >= MIN_CLUSTER, labels, -1)


def _key_terms(docs_by_cluster: dict, top_n=6) -> dict:
    labels = list(docs_by_cluster)
    joined = [" ".join(_NOISE.sub(" ", d) for d in docs_by_cluster[l]) for l in labels]
    vec = CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b")
    counts = vec.fit_transform(joined).toarray().astype(float)
    tf = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    idf = np.log(1 + counts.sum() / np.maximum(counts.sum(axis=0), 1))   # class-based TF-IDF
    scores = tf * idf
    vocab = np.array(vec.get_feature_names_out())
    skip = {"flight", "flights", "united", "thanks", "just", "amp", "don't", "can't", "i'm", "i've", "it's",
            "got", "does", "get", "did", "really", "need", "know", "going", "like", "today", "time", "way",
            "you're", "that's", "won't", "didn't", "doesn't", "isn't", "make", "want", "fly", "flying"}
    out = {}
    for i, l in enumerate(labels):
        terms = [t for t in vocab[np.argsort(-scores[i])] if t not in skip]
        out[l] = terms[:top_n]
    return out


def _name_clusters(clusters: list[dict]):
    """Fills c['name'] for each cluster; one batched LLM call for uncached names."""
    todo = []
    for c in clusters:
        key = "cluster-name:" + "|".join(sorted(c["terms"][:5]))
        c["_key"] = key
        with db.connect() as conn:
            row = conn.execute("SELECT value FROM llm_cache WHERE key=?", (key,)).fetchone()
        if row:
            c["name"] = row["value"]
        else:
            c["name"] = " / ".join(t.title() for t in c["terms"][:3])
            todo.append(c)
    todo = todo[:8]   # only the most important clusters go to the LLM
    if not todo or not llm.available():
        return
    payload = [{"cluster": i, "key_terms": c["terms"][:6], "examples": [s["text"] for s in c["samples"][:4]]}
               for i, c in enumerate(todo)]
    prompt = ("Name each cluster of customer posts about an airline with a short topic label "
              "(2-5 words, Title Case), e.g. 'App Check-in Failures', 'Cancelled Flights', 'Lost Baggage', "
              "'Long Hold Times', 'Friendly Crew Praise'. Return JSON: "
              '{"names": [{"cluster": 0, "name": "..."}]}\n\n' + json.dumps(payload))
    try:
        res = llm.chat(prompt, json_mode=True, max_tokens=400)
        for item in res.get("names", []):
            c = todo[int(item["cluster"])]
            c["name"] = str(item["name"]).strip()[:60]
            db.execute("INSERT OR REPLACE INTO llm_cache(key, value) VALUES (?, ?)", (c["_key"], c["name"]))
    except (llm.LLMUnavailable, KeyError, ValueError, IndexError, TypeError):
        pass


def severity(polarity: float, recent: int, growth: float) -> str:
    """Growth matters as much as size: a steady 25 posts/2h is normal, 12 -> 45 is not."""
    if polarity > 0.15:
        return "Positive"
    if recent >= 80 or (recent >= 25 and growth >= 150):
        return "Critical"
    if recent >= 50 or (recent >= 12 and growth >= 100):
        return "High"
    if recent >= 8 or (recent >= 5 and growth >= 100):
        return "Medium"
    return "Low"


def discover(now: str) -> list[dict]:
    cfg = settings()["replay"]
    hours, cmp_h = cfg["trend_lookback_hours"], cfg["growth_compare_hours"]
    posts = listening.fetch(shift(now, -60 * hours), now, brand=our_brand())
    posts = [p for p in posts if p.get("sentiment")]
    vecs = db.load_embeddings(p["id"] for p in posts)
    posts = [p for p in posts if p["id"] in vecs]
    if len(posts) < 20:
        return []
    X = np.stack([vecs[p["id"]] for p in posts])
    labels = cluster_embeddings(X)

    recent_start, prev_start = shift(now, -60 * cmp_h), shift(now, -120 * cmp_h)
    groups = {}
    for p, l in zip(posts, labels):
        if l >= 0:
            groups.setdefault(int(l), []).append(p)
    if not groups:
        return []
    terms = _key_terms({l: [p["text"] for p in g] for l, g in groups.items()})
    clusters = []
    for l, members in groups.items():
        recent = sum(p["created_at"] > recent_start for p in members)
        previous = sum(prev_start < p["created_at"] <= recent_start for p in members)
        growth = (recent - previous) / max(previous, 1) * 100
        polarity = float(np.mean([p["sentiment_score"] for p in members]))
        types = {}
        for p in members:
            types[p.get("mention_type") or "Other"] = types.get(p.get("mention_type") or "Other", 0) + 1
        samples = sorted(members, key=lambda p: -(p.get("impact_score") or 0))[:6]
        sev = severity(polarity, recent, growth)
        team = "Marketing (amplify)" if sev == "Positive" else route(" ".join(terms[l]) + " " + " ".join(p["text"] for p in samples))
        avg_impact = float(np.mean([p.get("impact_score") or 0 for p in members]))
        if sev in ("Critical", "High") and (avg_impact > 45 or any((p.get("viral_score") or 0) >= 50 for p in members)):
            team += " + PR / Comms"
        clusters.append({
            "size": len(members), "recent": recent, "previous": previous, "growth": round(growth, 1),
            "polarity": round(polarity, 3), "severity": sev, "recommendation": f"Escalate to {team}"
            if sev in ("Critical", "High") else (f"Share with {team}" if sev == "Positive" else f"Monitor - {team}"),
            "terms": terms[l], "types": types, "avg_impact": round(avg_impact, 1),
            "emerging": recent >= 5 and growth >= 100,
            "samples": [{"id": p["id"], "handle": p["handle"], "text": p["text"],
                         "impact": p.get("impact_score")} for p in samples],
            "post_ids": [p["id"] for p in members],
        })
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Positive": 3, "Low": 4}
    clusters.sort(key=lambda c: (rank[c["severity"]], -c["recent"]))
    _name_clusters(clusters)
    for c in clusters:
        c.pop("_key", None)
    return clusters


def save(now: str, clusters: list[dict]):
    db.execute("DELETE FROM clusters WHERE brand=? AND window_end=?", (workspace(), now))
    db.executemany(
        "INSERT INTO clusters(brand, window_end, name, size, recent, previous, growth, severity, polarity, "
        "recommendation, samples, post_ids) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(workspace(), now, c["name"], c["size"], c["recent"], c["previous"], c["growth"], c["severity"],
          "positive" if c["polarity"] > 0.15 else ("negative" if c["polarity"] < -0.15 else "mixed"),
          c["recommendation"], json.dumps(c["samples"]), json.dumps(c["post_ids"])) for c in clusters],
    )


def run(now: str) -> tuple[list[dict], str]:
    clusters = discover(now)
    save(now, clusters)
    emerging = [c for c in clusters if c["emerging"]]
    msg = f"Found {len(clusters)} topic clusters, {len(emerging)} emerging."
    if clusters:
        c = clusters[0]
        msg += f" Top: '{c['name']}' ({c['recent']} in last 2h, {c['growth']:+.0f}%, {c['severity']})"
    return clusters, msg
