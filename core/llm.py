"""Groq client with SQLite caching, retry/backoff and JSON parsing.

Every agent that uses the LLM has a non-LLM fallback, so the app still runs
without a key or when the free-tier rate limit is hit.
"""
import hashlib
import json
import re
import time

from core import db
from core.config import settings


class LLMUnavailable(Exception):
    pass


_client = None
_dead_models: set[str] = set()


def available() -> bool:
    return bool(settings()["groq_api_key"])


def _get_client():
    global _client
    if not available():
        raise LLMUnavailable("GROQ_API_KEY not set")
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=settings()["groq_api_key"])
    return _client


def _cache_key(model, system, prompt):
    return hashlib.sha256(f"{model}\n{system}\n{prompt}".encode()).hexdigest()


def _parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def chat(prompt: str, system: str = "", smart: bool = False, json_mode: bool = False,
         temperature: float = 0.2, max_tokens: int = 1024, retries: int = 3):
    """Returns the model's text (or parsed JSON). Cached on (model, system, prompt)."""
    cfg = settings()
    models = [cfg["smart_model"], cfg["fast_model"]] if smart else [cfg["fast_model"]]
    models = [m for m in models if m not in _dead_models]
    last_err = None
    for model in models:  # smart model falls back to the fast model on rate limits
        key = _cache_key(model, system, prompt)
        with db.connect() as c:
            row = c.execute("SELECT value FROM llm_cache WHERE key=?", (key,)).fetchone()
        if row:
            return _parse_json(row["value"]) if json_mode else row["value"]

        client = _get_client()
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        for attempt in range(retries):
            try:
                kwargs = dict(model=model, messages=messages,
                              temperature=temperature, max_tokens=max_tokens)
                if "gpt-oss" in model:  # reasoning models: keep thinking short, budget tokens for it
                    kwargs.update(reasoning_effort="low", max_tokens=max_tokens + 400)
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                text = resp.choices[0].message.content
                result = _parse_json(text) if json_mode else text.strip()
                db.execute("INSERT OR REPLACE INTO llm_cache(key, value) VALUES (?, ?)", (key, text))
                db.kv_incr("llm_calls")
                db.kv_incr("llm_tokens", getattr(resp.usage, "total_tokens", 0) or 0)
                return result
            except Exception as e:  # rate limits, timeouts, bad JSON
                last_err = e
                msg = str(e).lower()
                if "rate" in msg or "429" in msg:
                    if "per day" in msg or "tpd" in msg or "rpd" in msg:
                        break  # daily quota gone, try next model
                    time.sleep(min(20, 2 ** (attempt + 1)))
                elif "decommissioned" in msg or "not found" in msg or "does not exist" in msg:
                    _dead_models.add(model)  # don't retry a model this key can't use
                    break
                else:
                    time.sleep(1)
    db.kv_incr("llm_failures")
    raise LLMUnavailable(str(last_err or "no usable model"))
