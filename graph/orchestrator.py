"""Agent 11 - Master Orchestrator: a LangGraph StateGraph that runs all agents once
per replay window (default 1 hour of real tweets).

listening -> sentiment_emotion -> classification -> influence -> trend_discovery
          -> brand_risk --(High/Critical or forecast)--> escalation
          -> response_generation -> approval_queue -> campaign_intel -> executive_report
"""
import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import (approval, campaign, classifier, influence, listening, reporter, responder,
                    risk, sentiment, trends)
from core import db
from core.config import mode, our_brand, selected_brand, set_active_brand, set_active_mode, settings
from sources.dataset_replay import shift, time_bounds


class BrandState(TypedDict, total=False):
    brand: str
    mode: str
    start: str
    now: str
    use_llm: bool
    posts: list[dict]
    clusters: list[dict]
    risk: dict
    alert: str | None
    drafts: list[dict]
    response_ids: list[int]
    campaigns: list[dict]
    report: dict
    log: Annotated[list[dict], operator.add]


def _step(name: str, state_key: str | None, fn):
    """Wraps an agent: times it and appends its message to the shared activity log."""
    def node(state: BrandState):
        set_active_brand(state["brand"])   # nodes may run on worker threads
        set_active_mode(state.get("mode", "replay"))
        t0 = time.perf_counter()
        result, msg = fn(state)
        out = {"log": [{"agent": name, "message": msg, "ms": round((time.perf_counter() - t0) * 1000)}]}
        if state_key:
            out[state_key] = result
        return out
    return node


def _risk(state):
    r = risk.assess(state["now"], state["posts"], state["clusters"])
    return r, f"Risk {r['score']:.0f}/100 ({r['level']}), forecast {r['predicted_level']} in 2h. " \
              f"Negative {r['negative']} vs baseline {r['baseline_negative']} ({r['growth_pct']:+.0f}%)"


def _escalate(state):
    title = risk.escalate(state["now"], state["risk"])
    return title, f"ALERT raised: {title}" if title else "Alert already active (deduplicated)"


def _report(state):
    m, msg = reporter.run(state["now"])
    mine = [p for p in state["posts"] if p["brand"] == our_brand()]
    counts = {"mentions": len(mine), **{s: sum(p["sentiment"] == s for p in mine)
                                       for s in ("positive", "neutral", "negative")}}
    payload = {"risk": state["risk"], "report": m, "campaigns": state.get("campaigns", []), "log": state.get("log", [])}
    risk.save(state["now"], state["risk"], m["health"], payload, counts)
    return m, msg


def _needs_escalation(state) -> str:
    r = state["risk"]
    if r["level"] in ("High", "Critical") or r["predicted_level"] in ("High", "Critical"):
        return "escalation"
    return "response_generation"


def build():
    g = StateGraph(BrandState)
    g.add_node("listening", _step("Social Listening", "posts", lambda s: listening.run(s["start"], s["now"])))
    g.add_node("sentiment_emotion", _step("Sentiment & Emotion", "posts", lambda s: sentiment.run(s["posts"])))
    g.add_node("classification", _step("Mention Classification", "posts",
                                       lambda s: classifier.run(s["posts"], s.get("use_llm", True))))
    g.add_node("influence", _step("Influence Scoring", "posts", lambda s: influence.run(s["posts"])))
    g.add_node("trend_discovery", _step("Trend Discovery", "clusters", lambda s: trends.run(s["now"])))
    g.add_node("brand_risk", _step("Brand Risk", "risk", _risk))
    g.add_node("escalation", _step("Escalation Alert", "alert", _escalate))
    g.add_node("response_generation", _step("Response Generation", "drafts",
                                            lambda s: responder.run(s["posts"], s["clusters"], s["now"])))
    g.add_node("approval_queue", _step("Approval Workflow", "response_ids",
                                       lambda s: approval.run(s["drafts"], s["now"])))
    g.add_node("campaign_intel", _step("Campaign Intelligence", "campaigns", lambda s: campaign.run(s["now"])))
    g.add_node("executive_report", _step("Executive Reporting", "report", _report))

    g.add_edge(START, "listening")
    g.add_edge("listening", "sentiment_emotion")
    g.add_edge("sentiment_emotion", "classification")
    g.add_edge("classification", "influence")
    g.add_edge("influence", "trend_discovery")
    g.add_edge("trend_discovery", "brand_risk")
    g.add_conditional_edges("brand_risk", _needs_escalation, ["escalation", "response_generation"])
    g.add_edge("escalation", "response_generation")
    g.add_edge("response_generation", "approval_queue")
    g.add_edge("approval_queue", "campaign_intel")
    g.add_edge("campaign_intel", "executive_report")
    g.add_edge("executive_report", END)
    return g.compile()


_GRAPH = None


def graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build()
    return _GRAPH


def clock() -> str:
    """Current simulated time. Starts one window before the first real tweet."""
    now = db.kv_get(db.clock_key())
    if not now:
        lo, _ = time_bounds()
        now = shift(lo[:13] + ":00:00", 0)
        db.kv_set(db.clock_key(), now)
    return now


def run_window(start: str, now: str, use_llm: bool = True) -> BrandState:
    """Run every agent on the posts in (start, now] for the active workspace and record `now` as its clock."""
    state = graph().invoke({"brand": selected_brand(), "mode": mode(), "start": start, "now": now,
                            "use_llm": use_llm, "log": []})
    db.kv_set(db.clock_key(), now)
    return state


def step(use_llm: bool = True) -> BrandState:
    """Advance the replay by one window and run every agent on it."""
    start = clock()
    return run_window(start, shift(start, settings()["replay"]["window_minutes"]), use_llm)


def finished() -> bool:
    _, hi = time_bounds()
    return clock() >= hi
