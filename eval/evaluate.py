"""Evaluates the agents against the dataset's human labels (never shown to the agents).

    python -m eval.evaluate

- Sentiment agent vs `airline_sentiment`: accuracy, macro-F1, confusion matrix
- Topic clustering vs `negativereason`: purity, NMI, coverage
Writes eval/results.md.
"""
from pathlib import Path

import numpy as np
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             normalized_mutual_info_score)

from agents.trends import cluster_embeddings
from core import db
from core.config import our_brand

OUT = Path(__file__).with_name("results.md")


def sentiment_eval(lines: list[str]):
    df = db.query_df("SELECT p.brand, p.label_sentiment AS y, e.sentiment AS p FROM posts p "
                     "JOIN enrichment e ON e.post_id=p.id WHERE p.is_synthetic=0 AND e.sentiment IS NOT NULL")
    labels = ["negative", "neutral", "positive"]
    acc, f1 = accuracy_score(df["y"], df["p"]), f1_score(df["y"], df["p"], average="macro")
    cm = confusion_matrix(df["y"], df["p"], labels=labels)
    lines += ["## Sentiment agent vs human labels", f"Posts: {len(df)}",
              f"- **Accuracy: {acc:.3f}**", f"- **Macro F1: {f1:.3f}**", "",
              "Confusion matrix (rows = human label, cols = predicted):", "",
              "| | " + " | ".join(labels) + " |", "|---" * 4 + "|"]
    lines += [f"| {l} | " + " | ".join(str(v) for v in row) + " |" for l, row in zip(labels, cm)]
    lines += ["", "```", classification_report(df["y"], df["p"], digits=3), "```", "",
              "Per brand accuracy:", ""]
    for b, g in df.groupby("brand"):
        lines.append(f"- {b}: {accuracy_score(g['y'], g['p']):.3f} (n={len(g)})")
    lines.append("")


def cluster_eval(lines: list[str]):
    df = db.query_df("SELECT p.id, p.label_reason AS reason FROM posts p JOIN enrichment e ON e.post_id=p.id "
                     "WHERE p.is_synthetic=0 AND p.brand=? AND e.sentiment='negative' "
                     "AND p.label_reason NOT IN ('', 'Can''t Tell')", (our_brand(),))
    vecs = db.load_embeddings(df["id"])
    df = df[df["id"].isin(vecs)]
    X = np.stack([vecs[i] for i in df["id"]])
    labels = cluster_embeddings(X)
    mask = labels >= 0
    sub, lab = df[mask].assign(c=labels[mask]), labels[mask]
    purity = sum(int(g.value_counts().iloc[0]) for _, g in sub.groupby("c")["reason"]) / max(len(sub), 1)
    nmi = normalized_mutual_info_score(sub["reason"], lab) if len(sub) else 0
    lines += [f"## Topic clustering vs `negativereason` ({our_brand()} negative posts)",
              f"Posts: {len(df)}, clusters found: {len(set(lab))}, coverage (not noise): {mask.mean():.1%}",
              f"- **Purity: {purity:.3f}** (share of each cluster's posts with its majority reason)",
              f"- **NMI: {nmi:.3f}**", f"- Majority-class baseline purity: {df['reason'].value_counts().iloc[0] / len(df):.3f}", "", "Largest clusters and their majority human reason:", ""]
    for c, g in sorted(sub.groupby("c"), key=lambda x: -len(x[1]))[:10]:
        top = g["reason"].value_counts()
        lines.append(f"- cluster {c}: {len(g)} posts, majority '{top.index[0]}' ({top.iloc[0] / len(g):.0%})")
    lines.append("")


def distribution(lines: list[str]):
    df = db.query_df("SELECT e.mention_type, e.type_source, e.emotion FROM posts p JOIN enrichment e "
                     "ON e.post_id=p.id WHERE p.brand=? AND p.is_synthetic=0", (our_brand(),))
    lines += [f"## Mention types and emotions ({our_brand()}, no ground truth)", "",
              "Mention type by source:", "", "```", df.groupby(["type_source", "mention_type"]).size().to_string(),
              "```", "", "Emotions:", "", "```", df["emotion"].value_counts().to_string(), "```", ""]


def main():
    lines = ["# Evaluation results", ""]
    sentiment_eval(lines)
    cluster_eval(lines)
    distribution(lines)
    text = "\n".join(lines)
    OUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
