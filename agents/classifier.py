"""Agent 2 - Mention Classification: Complaint / Question / Praise / Feature Request /
Bug Report / Comparison / Other.

Our brand's posts go to Groq (batched, cached). Competitor posts and any LLM failure
use the keyword rules below, so the pipeline never blocks on the API.
"""
import json
import re

from core import db, llm
from core.config import active_brands, our_brand, settings

TYPES = ["Complaint", "Question", "Praise", "Feature Request", "Bug Report", "Comparison", "Other"]

_BUG = re.compile(r"\b(app|website|site|online|login|log in|error|crash\w*|bug|glitch|broken|"
                  r"won'?t load|not loading|check-?in (page|isn'?t|won'?t)|server|503|500)\b", re.I)
_PRAISE = re.compile(r"\b(love|great|thanks?|thank you|awesome|amazing|best|excellent|kudos|"
                     r"appreciate|fantastic|wonderful|impressed)\b", re.I)
_FEATURE = re.compile(r"\b(should (add|have|offer)|wish (you|there)|please add|would be (nice|great)|"
                      r"why don'?t you|bring back|feature|option to)\b", re.I)
_COMPARE = re.compile(r"\b(better than|worse than|unlike|switch(ing|ed)? to|never again.*fly|vs\.?)\b", re.I)


def _other_brand_handles(brand: str) -> list[str]:
    return [i["handle"].lower() for b, i in active_brands().items() if b != brand]


def rules_classify(text: str, brand: str, sentiment: str | None = None) -> str:
    low = text.lower()
    if _COMPARE.search(text) or any(h in low for h in _other_brand_handles(brand)):
        return "Comparison"
    if _FEATURE.search(text):
        return "Feature Request"
    if _BUG.search(text) and sentiment != "positive":
        return "Bug Report"
    if sentiment == "positive" or (_PRAISE.search(text) and sentiment != "negative"):
        return "Praise"
    if "?" in text:
        return "Question"
    if sentiment == "negative":
        return "Complaint"
    return "Other"


SYSTEM = (
    "You classify social media mentions of a brand. For each post return one type from: "
    + ", ".join(TYPES) + ". Definitions: Complaint = unhappy about service/experience; "
    "Question = asks for information or help; Praise = positive feedback; Feature Request = asks "
    "for something new or changed; Bug Report = app/website/technical failure; Comparison = compares "
    "with a competitor; Other = none of these. Respond with JSON only: "
    '{"results": [{"id": "<id>", "type": "<type>"}]}'
)


def llm_classify(posts: list[dict]) -> dict:
    """{post_id: type}. Raises llm.LLMUnavailable on failure."""
    lines = "\n".join(json.dumps({"id": p["id"], "text": p["text"]}) for p in posts)
    result = llm.chat(f"Brand: {our_brand()}\nPosts:\n{lines}", system=SYSTEM, json_mode=True,
                      max_tokens=60 * len(posts) + 100)
    items = result.get("results", result) if isinstance(result, dict) else result
    out = {}
    for item in items:
        t = str(item.get("type", "")).strip().title().replace("Feature request", "Feature Request")
        out[str(item.get("id"))] = t if t in TYPES else "Other"
    return out


def run(posts: list[dict], use_llm: bool = True) -> tuple[list[dict], str]:
    brand = our_brand()
    todo_llm = [p for p in posts if p["brand"] == brand and p.get("type_source") != "llm"
                and not str(p["id"]).startswith("campaign-")] if use_llm and llm.available() else []
    labels, n_llm = {}, 0
    batch = settings()["llm"]["batch_size"]
    for i in range(0, len(todo_llm), batch):
        chunk = todo_llm[i:i + batch]
        try:
            got = llm_classify(chunk)
            labels.update({k: (v, "llm") for k, v in got.items()})
            n_llm += len(got)
        except llm.LLMUnavailable:
            break
    rows = []
    for p in posts:
        if p["id"] in labels:
            p["mention_type"], p["type_source"] = labels[p["id"]]
        elif not p.get("mention_type"):
            p["mention_type"] = rules_classify(p["text"], p["brand"], p.get("sentiment"))
            p["type_source"] = "rules"
        else:
            continue
        rows.append((p["mention_type"], p["type_source"], p["id"]))
    save(rows)
    counts = {}
    for p in posts:
        if p["brand"] == brand:
            counts[p["mention_type"]] = counts.get(p["mention_type"], 0) + 1
    top = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])[:4])
    return posts, f"Classified {len(rows)} posts ({n_llm} via LLM). {brand}: {top or '-'}"


def save(rows):
    db.executemany(
        "INSERT INTO enrichment(post_id, mention_type, type_source) VALUES (?3, ?1, ?2) "
        "ON CONFLICT(post_id) DO UPDATE SET mention_type=?1, type_source=?2", rows)
