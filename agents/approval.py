"""Agent 8 - Human Approval: every draft becomes its own LangGraph thread that pauses
at interrupt() until a marketer approves, edits or rejects it in the dashboard.

Generated Response -> (interrupt) Marketing Approval -> Publish (simulated, never posted)

Checkpoints live in data/approvals.db, so pending approvals survive app restarts.
"""
import sqlite3
from functools import lru_cache
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from core import db
from core.config import CHECKPOINT_DB, mode, selected_brand, set_active_brand, set_active_mode, workspace


class ApprovalState(TypedDict, total=False):
    brand: str
    mode: str
    response_id: int
    post_text: str
    draft: str
    decision: dict
    status: str
    final_text: str


def review(state: ApprovalState):
    decision = interrupt({"response_id": state["response_id"], "post": state["post_text"],
                          "draft": state["draft"]})
    return {"decision": decision}


def finalize(state: ApprovalState):
    set_active_brand(state["brand"])
    set_active_mode(state.get("mode", "replay"))
    d = state["decision"]
    action = d.get("action")
    if action in ("approve", "edit"):
        status, final = "published", (d.get("text") or state["draft"]).strip()
    else:
        status, final = "rejected", None
    db.execute("UPDATE responses SET status=?, final_text=?, decided_at=?, note=? WHERE id=?",
               (status, final, db.kv_get(db.clock_key()), d.get("note"), state["response_id"]))
    return {"status": status, "final_text": final}


@lru_cache
def graph():
    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    saver = SqliteSaver(sqlite3.connect(CHECKPOINT_DB, check_same_thread=False))
    g = StateGraph(ApprovalState)
    g.add_node("review", review)
    g.add_node("finalize", finalize)
    g.add_edge(START, "review")
    g.add_edge("review", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=saver)


def _config(thread_id: str):
    return {"configurable": {"thread_id": thread_id}}


def submit(post: dict, draft: str, tone: str, now: str) -> int:
    rid = db.execute("INSERT INTO responses(brand, post_id, draft, tone, status, created_at) VALUES (?,?,?,?,?,?)",
                     (workspace(), post["id"], draft, tone, "pending", now))
    thread = f"reply-{rid}"
    db.execute("UPDATE responses SET thread_id=? WHERE id=?", (thread, rid))
    graph().invoke({"brand": selected_brand(), "mode": mode(), "response_id": rid, "post_text": post["text"], "draft": draft}, _config(thread))
    return rid


def decide(response_id: int, action: str, text: str | None = None, note: str | None = None) -> str:
    """action: approve | edit | reject. Resumes the paused thread."""
    thread = f"reply-{response_id}"
    result = graph().invoke(Command(resume={"action": action, "text": text, "note": note}), _config(thread))
    return result.get("status", "unknown")


def run(drafts: list[dict], now: str) -> tuple[list[int], str]:
    ids = [submit(d["post"], d["draft"], d["tone"], now) for d in drafts]
    pending = db.query_df("SELECT COUNT(*) AS n FROM responses WHERE brand=? AND status='pending'",
                          (workspace(),)).loc[0, "n"]
    return ids, f"Queued {len(ids)} drafts for human approval ({pending} pending in total). Nothing auto-posted."
