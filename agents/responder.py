"""Agent 7 - Response Generation: drafts a reply that fits the brand tone, the
customer's emotion and history, and any known issue cluster. Drafts never get posted
directly; they go to the Approval agent.
"""
from core import db, llm
from core.config import is_live, our_brand, settings, workspace
from sources.dataset_replay import shift

TONES = {
    "friendly": ("Warm, casual, empathetic, first names, light emoji allowed (max 1).",
                 "Oh no, that's not the start to your trip we want! 😟 DM us your confirmation number and we'll sort it out."),
    "professional": ("Polite, concise, empathetic, no emoji, clear next step.",
                     "We're sorry for the trouble with your flight. Please DM us your confirmation number so we can look into this right away."),
    "luxury": ("Refined, gracious, personal, unhurried, never casual, no emoji.",
               "Please accept our sincere apologies. A member of our premier care team would be delighted to assist you personally; kindly share your details via DM."),
    "startup": ("Upbeat, human, transparent, owns mistakes, a bit playful, may use 1 emoji.",
                "Ugh, that's on us 🙈 Our team is on it right now. DM us and we'll make it right."),
}
TYPE_WEIGHT = {"Bug Report": 1.3, "Complaint": 1.2, "Question": 1.1, "Comparison": 1.0,
               "Feature Request": 0.9, "Praise": 0.7}


def history_for(handle: str, before: str, limit: int = 3) -> list[str]:
    df = db.query_df("SELECT text FROM posts WHERE handle=? AND created_at < ? ORDER BY created_at DESC LIMIT ?",
                     (handle, before, limit))
    return df["text"].tolist()


def pick_candidates(posts: list[dict], n: int) -> list[dict]:
    cfg = settings()["responses"]
    done = set(db.query_df("SELECT post_id FROM responses WHERE brand=?", (workspace(),))["post_id"])
    cands = [p for p in posts if p["brand"] == our_brand() and p["id"] not in done
             and p.get("mention_type") in TYPE_WEIGHT and (p.get("impact_score") or 0) >= cfg["min_impact"]]
    for p in cands:
        p["priority"] = p["impact_score"] * TYPE_WEIGHT[p["mention_type"]] * \
            (1 + max(0, -(p.get("sentiment_score") or 0))) * (1.3 if (p.get("viral_score") or 0) >= 50 else 1)
    return sorted(cands, key=lambda p: -p["priority"])[:n]


def _template(post: dict, issue: str | None) -> str:
    t = post.get("mention_type")
    if issue and t in ("Complaint", "Bug Report"):
        return (f"Hi {post['handle']}, we're sorry about this. We're aware of the {issue.lower()} issue "
                "and our team is actively working on a fix. We'll update you shortly.")
    return {
        "Praise": f"Thank you {post['handle']}! We're so glad you enjoyed it and hope to see you on board again soon.",
        "Question": f"Hi {post['handle']}, happy to help! Please DM us your confirmation number and we'll get you an answer.",
        "Feature Request": f"Thanks for the suggestion {post['handle']}! We've shared it with our product team.",
        "Comparison": f"Hi {post['handle']}, we appreciate the feedback and would love the chance to earn your trust. DM us anytime.",
    }.get(t, f"Hi {post['handle']}, we're sorry to hear this. Please DM us your confirmation number so we can help right away.")


def draft(post: dict, issue: str | None = None, tone: str | None = None) -> tuple[str, str]:
    """-> (reply text, tone)"""
    tone = tone or settings()["tone"]
    style, example = TONES.get(tone, TONES["professional"])
    if not llm.available():
        return _template(post, issue), tone
    history = history_for(post["handle"], post["created_at"])
    prompt = (
        f"You are the social media team for {our_brand()} replying on X (Twitter).\n"
        f"Tone: {tone} - {style}\nExample in this tone: \"{example}\"\n\n"
        f"Customer: {post['handle']} ({post.get('followers', 0):,} followers)\n"
        f"Their post: \"{post['text']}\"\n"
        f"Mention type: {post.get('mention_type')} | Sentiment: {post.get('sentiment')} | Emotion: {post.get('emotion')}\n"
        f"Their earlier posts: {history if history else 'none'}\n"
        f"Known ongoing issue this relates to: {issue or 'none'}\n\n"
        "Write ONE reply under 260 characters. Acknowledge their emotion, be specific to what they said, "
        "give a clear next step (e.g. DM), never promise compensation or blame the customer, "
        "and if there is a known issue say the team is investigating. Output only the reply text."
    )
    try:
        text = llm.chat(prompt, smart=True, temperature=0.5, max_tokens=150)
        return text.strip().strip('"'), tone
    except llm.LLMUnavailable:
        return _template(post, issue), tone


def run(posts: list[dict], clusters: list[dict], now: str) -> tuple[list[dict], str]:
    n = settings()["responses"]["drafts_per_window"]
    if is_live():  # live windows overlap (every 10 min over the last hour): cap drafts per hour instead
        recent = db.query_df("SELECT COUNT(*) AS n FROM responses WHERE brand=? AND created_at > ?",
                             (workspace(), shift(now, -60))).loc[0, "n"]
        n = max(0, n - int(recent))
    issue_of = {}
    for c in clusters:
        if c["severity"] != "Positive":
            for pid in c["post_ids"]:
                issue_of.setdefault(pid, c["name"])
    drafts = []
    for p in pick_candidates(posts, n):
        text, tone = draft(p, issue_of.get(p["id"]))
        drafts.append({"post": p, "draft": text, "tone": tone})
    return drafts, f"Drafted {len(drafts)} replies for high-priority mentions"
