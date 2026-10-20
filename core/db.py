"""SQLite storage: posts, per-post agent outputs, LLM cache, window metrics, alerts, replies.

Posts and per-post analysis are shared. Everything a replay produces (windows, clusters, alerts,
replies, the clock) is stored per brand workspace, so each airline keeps its own progress.
"""
import json
import sqlite3
from contextlib import contextmanager

import numpy as np
import pandas as pd

from core.config import CHECKPOINT_DB, DB_PATH, is_live, workspace

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    source TEXT, brand TEXT, handle TEXT, text TEXT, created_at TEXT,
    retweet_count INTEGER, likes INTEGER, followers INTEGER, verified INTEGER,
    location TEXT, hashtags TEXT, entities TEXT,
    is_synthetic INTEGER DEFAULT 0,
    label_sentiment TEXT, label_reason TEXT        -- ground truth, evaluation only
);
CREATE INDEX IF NOT EXISTS idx_posts_time ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_brand ON posts(brand, created_at);

CREATE TABLE IF NOT EXISTS enrichment (
    post_id TEXT PRIMARY KEY,
    sentiment TEXT, sentiment_score REAL,
    emotion TEXT, emotion_score REAL,
    mention_type TEXT, type_source TEXT,
    impact_score REAL, viral_score REAL
);

CREATE TABLE IF NOT EXISTS embeddings (post_id TEXT PRIMARY KEY, vec BLOB);

CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS windows (
    brand TEXT, window_end TEXT,
    mentions INTEGER, positive INTEGER, neutral INTEGER, negative INTEGER,
    risk_score REAL, risk_level TEXT, predicted_level TEXT, health REAL,
    payload TEXT,
    PRIMARY KEY (brand, window_end)
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT, window_end TEXT, name TEXT, size INTEGER, recent INTEGER, previous INTEGER,
    growth REAL, severity TEXT, polarity TEXT, recommendation TEXT,
    samples TEXT, post_ids TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT, window_end TEXT, level TEXT, title TEXT, message TEXT, recommendation TEXT
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT, post_id TEXT, thread_id TEXT, draft TEXT, final_text TEXT, tone TEXT,
    status TEXT DEFAULT 'pending', created_at TEXT, decided_at TEXT, note TEXT
);

CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


RUNTIME_TABLES = ("windows", "clusters", "alerts", "responses")


def init_db():
    with connect() as c:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(windows)")]
        if cols and "brand" not in cols:   # pre-workspace schema: rebuild replay tables only
            for t in RUNTIME_TABLES:
                c.execute(f"DROP TABLE IF EXISTS {t}")
            c.execute("DELETE FROM kv WHERE key IN ('clock', 'crisis')")
            c.execute("DELETE FROM enrichment WHERE post_id IN (SELECT id FROM posts WHERE source LIKE 'crisis%')")
            c.execute("DELETE FROM posts WHERE source LIKE 'crisis%'")
            for f in CHECKPOINT_DB.parent.glob(CHECKPOINT_DB.name + "*"):
                try:
                    f.unlink(missing_ok=True)   # old approval threads point at dropped reply ids
                except OSError:
                    pass
        c.executescript(SCHEMA)
        post_cols = [r["name"] for r in c.execute("PRAGMA table_info(posts)")]
        if "is_live" not in post_cols:   # live mode: posts from today's APIs, kept apart from the 2015 dataset
            c.execute("ALTER TABLE posts ADD COLUMN is_live INTEGER DEFAULT 0")
            c.execute("ALTER TABLE posts ADD COLUMN url TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_posts_live ON posts(is_live, brand, created_at)")


def query_df(sql: str, params=()) -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql_query(sql, c, params=params)


def execute(sql: str, params=()):
    with connect() as c:
        return c.execute(sql, params).lastrowid


def executemany(sql: str, rows):
    with connect() as c:
        c.executemany(sql, rows)


def insert_posts(df: pd.DataFrame):
    cols = ["id", "source", "brand", "handle", "text", "created_at", "retweet_count", "likes",
            "followers", "verified", "location", "hashtags", "entities", "is_synthetic",
            "label_sentiment", "label_reason", "is_live", "url"]
    df = df.assign(**{c: df[c] if c in df else (0 if c == "is_live" else None) for c in ("is_live", "url")})
    rows = [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in r)
            for r in df[cols].itertuples(index=False)]
    executemany(f"INSERT OR REPLACE INTO posts({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", rows)



def kv_get(key: str, default=None):
    with connect() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(key: str, value):
    execute("INSERT OR REPLACE INTO kv(key, value) VALUES (?, ?)", (key, json.dumps(value)))


def kv_incr(key: str, by: int = 1):
    kv_set(key, kv_get(key, 0) + by)


def save_embeddings(ids, vectors: np.ndarray):
    executemany(
        "INSERT OR REPLACE INTO embeddings(post_id, vec) VALUES (?, ?)",
        [(i, v.astype(np.float32).tobytes()) for i, v in zip(ids, vectors)],
    )


def load_embeddings(ids) -> dict:
    ids = list(ids)
    out = {}
    with connect() as c:
        for start in range(0, len(ids), 900):  # SQLite variable limit
            chunk = ids[start:start + 900]
            q = f"SELECT post_id, vec FROM embeddings WHERE post_id IN ({','.join('?' * len(chunk))})"
            for row in c.execute(q, chunk):
                out[row["post_id"]] = np.frombuffer(row["vec"], dtype=np.float32)
    return out


def live_filter(alias: str = "p") -> str:
    """SQL condition keeping only the current mode's posts (2015 dataset vs. live APIs)."""
    return f"{alias}.is_live = {1 if is_live() else 0}"


def clock_key(ws: str | None = None) -> str:
    return f"clock:{ws or workspace()}"


def crisis_key(ws: str | None = None) -> str:
    return f"crisis:{ws or workspace()}"


def reset_runtime(ws: str | None = None):
    """Restart one workspace (keeps posts, analysis and caches)."""
    ws = ws or workspace()
    brand, live = ws.removesuffix(":live"), int(ws.endswith(":live"))
    with connect() as c:
        for t in RUNTIME_TABLES:
            c.execute(f"DELETE FROM {t} WHERE brand=?", (ws,))
        crisis = "SELECT id FROM posts WHERE source LIKE 'crisis%' AND brand=? AND is_live=?"
        c.execute(f"DELETE FROM enrichment WHERE post_id IN ({crisis})", (brand, live))
        c.execute(f"DELETE FROM posts WHERE id IN ({crisis})", (brand, live))
        c.execute("DELETE FROM kv WHERE key IN (?, ?)", (clock_key(ws), crisis_key(ws)))
