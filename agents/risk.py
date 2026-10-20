"""Agent 6 - Brand Risk: compares the current hour with a rolling baseline and
detects potential PR crises, plus an early-warning forecast 2 hours ahead.

score (0-100) = 35 volume spike (z-score of negative mentions vs baseline)
              + 15 negative share above normal
              + 20 worst issue cluster (severity x growth)
              + 15 average impact of negative posts
              + 15 share of Angry/Frustrated posts
"""
import json

import numpy as np

from core import db
from core.config import is_live, our_brand, settings, workspace
from sources.dataset_replay import shift

LEVELS = [(30, "Low"), (50, "Medium"), (70, "High"), (101, "Critical")]
SEV_WEIGHT = {"Critical": 1.0, "High": 0.75, "Medium": 0.4, "Low": 0.2, "Positive": 0.0}


def level_for(score: float) -> str:
    return next(name for cut, name in LEVELS if score < cut)


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def assess(now: str, posts: list[dict], clusters: list[dict]) -> dict:
    n_base = settings()["live" if is_live() else "replay"]["baseline_windows"]
    hist = db.query_df("SELECT * FROM windows WHERE brand=? AND window_end < ? ORDER BY window_end DESC LIMIT ?",
                       (workspace(), now, n_base))
    mine = [p for p in posts if p["brand"] == our_brand()]
    total = len(mine)
    negs = [p for p in mine if p["sentiment"] == "negative"]
    neg = len(negs)

    if len(hist) >= 3:
        mean = max(float(hist["negative"].mean()), 3.0)       # floor: quiet nights aren't a baseline
        std = max(float(hist["negative"].std(ddof=0)), mean ** 0.5, 2.0)
        base_share = float(hist["negative"].sum() / max(hist["mentions"].sum(), 1))
    else:  # warm-up: not enough history yet
        mean, std, base_share = float(neg), max(neg ** 0.5, 2.0), 0.6
    z = (neg - mean) / std
    growth = (neg - mean) / max(mean, 1) * 100
    share = neg / total if total else 0.0

    issue = next((c for c in clusters if c["severity"] != "Positive"), None)
    if issue:
        w = SEV_WEIGHT[issue["severity"]]
        cluster_comp = max(0.6 * w, _clamp(issue["growth"] / 300) * w)
    else:
        cluster_comp = 0.0
    avg_impact = float(np.mean([p["impact_score"] for p in negs])) if negs else 0.0
    hot = sum(p["emotion"] in ("Angry", "Frustrated") for p in negs) / neg if neg else 0.0

    warmup = min(1.0, len(hist) / 12)                        # trust the spike signal once history exists
    parts = {
        "volume_spike": 35 * _clamp(z / 4) * warmup,
        "negative_share": 15 * _clamp((share - base_share) / 0.3 + 0.5) if total else 0.0,
        "issue_cluster": 20 * cluster_comp,
        "impact": 15 * avg_impact / 100,
        "emotion": 15 * hot,
    }
    score = round(sum(parts.values()), 1)

    # early warning: smooth recent scores (EWMA), fit a line to the last 4, project 2 windows ahead
    past = list(hist["risk_score"][:5][::-1]) + [score]
    if len(past) >= 3:
        smooth = [past[0]]
        for v in past[1:]:
            smooth.append(0.5 * v + 0.5 * smooth[-1])
        tail = smooth[-4:]
        slope = np.polyfit(np.arange(len(tail)), tail, 1)[0]
        predicted = round(float(np.clip(max(score, smooth[-1]) + 2 * slope, 0, 100)), 1)
    else:
        predicted = score
    # a fast-growing issue cluster is a leading indicator even before the hourly totals move
    if issue and issue["growth"] >= 300 and issue["severity"] in ("High", "Critical"):
        predicted = max(predicted, 80.0 if issue["severity"] == "Critical" else 60.0)

    return {
        "score": score, "level": level_for(score),
        "predicted_score": predicted, "predicted_level": level_for(predicted),
        "negative": neg, "mentions": total, "baseline_negative": round(mean, 1),
        "z": round(z, 2), "growth_pct": round(growth, 1), "negative_share": round(share, 3),
        "components": {k: round(v, 1) for k, v in parts.items()},
        "top_issue": issue["name"] if issue else None,
        "top_issue_growth": issue["growth"] if issue else None,
        "top_issue_mentions": issue["recent"] if issue else None,
        "recommendation": issue["recommendation"] if issue else "No action needed",
    }


def escalate(now: str, risk: dict) -> str | None:
    """Writes an alert for High/Critical risk, or when the forecast says Critical. Deduplicated."""
    if risk["level"] in ("High", "Critical"):
        title = f"Potential PR crisis: {risk['top_issue'] or 'negative spike'}" if risk["level"] == "Critical" \
            else f"Risk elevated: {risk['top_issue'] or 'negative spike'}"
        level = risk["level"]
    elif risk["predicted_level"] in ("High", "Critical") and risk["level"] in ("Low", "Medium"):
        title = f"Early warning: risk predicted {risk['predicted_level']} within 2h"
        level = "Warning"
    else:
        return None
    recent = db.query_df("SELECT title FROM alerts WHERE brand=? AND window_end > ?", (workspace(), shift(now, -180)))
    if title in set(recent["title"]):
        return None
    msg = (f"Negative mentions {risk['negative']} this hour vs baseline {risk['baseline_negative']} "
           f"({risk['growth_pct']:+.0f}%). Risk {risk['score']:.0f}/100 ({risk['level']}), "
           f"forecast {risk['predicted_level']} in 2h.")
    if risk["top_issue"]:
        msg += f" Top issue: {risk['top_issue']} - {risk['top_issue_mentions']} mentions in 2h " \
               f"({risk['top_issue_growth']:+.0f}%)."
    db.execute("INSERT INTO alerts(brand, window_end, level, title, message, recommendation) VALUES (?,?,?,?,?,?)",
               (workspace(), now, level, title, msg, risk["recommendation"]))
    return title


def save(now: str, risk: dict, health: float, payload: dict, counts: dict):
    db.execute(
        "INSERT OR REPLACE INTO windows(brand, window_end, mentions, positive, neutral, negative, risk_score, "
        "risk_level, predicted_level, health, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (workspace(), now, counts["mentions"], counts["positive"], counts["neutral"], counts["negative"],
         risk["score"], risk["level"], risk["predicted_level"], health, json.dumps(payload, default=str)),
    )
