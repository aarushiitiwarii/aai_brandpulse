"""Live engine: one background thread per app process that keeps live workspaces up to date.

For every airline whose live workspace has been opened:
  - polls the live sources every `live.poll_seconds`
  - first time: backfills `live.backfill_hours` and runs hourly windows over it (rules only, fast)
  - then runs all agents every `live.stride_minutes` on the trailing `live.window_minutes`
"""
import threading
import time
import traceback
from datetime import datetime, timedelta

from core import db
from core.config import set_active_brand, set_active_mode, settings
from agents import classifier, influence, listening, sentiment
from graph import orchestrator
from sources import live
from sources.dataset_replay import shift

FMT = "%Y-%m-%d %H:%M:%S"


def _floor(dt: datetime, minutes: int) -> datetime:
    return dt.replace(second=0, microsecond=0) - timedelta(minutes=dt.minute % minutes)


class LiveEngine:
    def __init__(self):
        self.watched: set[str] = set()
        self.lock = threading.Lock()          # one agent run at a time (shared models, SQLite)
        self.wake = threading.Event()
        self.last_poll: dict[str, float] = {}
        self.thread = threading.Thread(target=self._loop, name="live-engine", daemon=True)
        self.thread.start()

    # -- called from the UI -------------------------------------------------------------
    def watch(self, identity: str):
        if identity not in self.watched:
            self.watched.add(identity)
            self.wake.set()

    def fetch_now(self, identity: str):
        self.last_poll.pop(identity, None)
        self.watch(identity)
        self.wake.set()

    @staticmethod
    def status(identity: str) -> dict:
        return db.kv_get(f"live_engine:{identity}", {})

    # -- background loop ----------------------------------------------------------------
    def _loop(self):
        while True:
            for identity in list(self.watched):
                try:
                    self._tick(identity)
                except Exception as e:
                    db.kv_set(f"live_engine:{identity}", {**self.status(identity), "state": "error",
                                                          "error": f"{e}"[:200], "trace": traceback.format_exc()[-600:]})
            self.wake.wait(timeout=15)
            self.wake.clear()

    @staticmethod
    def _score_new(identity: str):
        """Score fresh posts immediately (local models + rules) so the feed never shows blanks.
        The LLM classification pass happens in the next analysis window."""
        now = datetime.now()
        posts = listening.fetch((now - timedelta(days=2)).strftime(FMT), now.strftime(FMT))
        todo = [p for p in posts if not p.get("sentiment")]
        if todo:
            sentiment.analyze(todo)
            classifier.run(todo, use_llm=False)
            influence.score(todo)

    def _set(self, identity: str, **fields):
        db.kv_set(f"live_engine:{identity}", {**self.status(identity), **fields, "updated": datetime.now().strftime(FMT)})

    def _tick(self, identity: str):
        cfg = settings()["live"]
        set_active_mode("live")
        set_active_brand(identity)
        if time.time() - self.last_poll.get(identity, 0) >= cfg["poll_seconds"]:
            with self.lock:
                new = live.poll(identity)
                self._score_new(identity)
            self.last_poll[identity] = time.time()
            self._set(identity, last_poll=datetime.now().strftime(FMT), last_new=new)

        boundary = _floor(datetime.now(), cfg["stride_minutes"]).strftime(FMT)
        clock = db.kv_get(db.clock_key())
        if clock is None:                                   # first run: build 24h of history quickly
            start = _floor(datetime.now() - timedelta(hours=cfg["backfill_hours"]), 60)
            hours = [(start + timedelta(hours=h + 1)).strftime(FMT) for h in range(cfg["backfill_hours"])]
            for i, t in enumerate(hours, 1):
                self._set(identity, state="backfilling", progress=f"{i}/{len(hours)}")
                with self.lock:
                    orchestrator.run_window(shift(t, -60), t, use_llm=False)
            clock = hours[-1]
        if clock < boundary:
            self._set(identity, state="analysing")
            with self.lock:
                orchestrator.run_window(shift(boundary, -cfg["window_minutes"]), boundary, use_llm=True)
        self._set(identity, state="live", error=None, last_window=db.kv_get(db.clock_key()))
