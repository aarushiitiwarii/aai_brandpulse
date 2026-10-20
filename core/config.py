"""Loads config/brand.yaml and .env once, shared by every agent.

The brand being monitored ("our brand") is chosen per session in the UI and held in a
context variable, so every agent, query and LLM prompt works for whichever airline is active.
"""
import os
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw" / "Tweets.csv"
DB_PATH = DATA_DIR / "brand.db"
CHECKPOINT_DB = DATA_DIR / "approvals.db"

# .env.local (personal, git-ignored: your GROQ_API_KEY) wins over the shared, committed .env
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")


@lru_cache
def settings() -> dict:
    with open(ROOT / "config" / "brand.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["groq_api_key"] = os.getenv("GROQ_API_KEY", "").strip()
    cfg["fast_model"] = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
    cfg["smart_model"] = os.getenv("GROQ_SMART_MODEL", "openai/gpt-oss-120b")
    return cfg


_active_brand: ContextVar[str | None] = ContextVar("active_brand", default=None)
_active_mode: ContextVar[str] = ContextVar("active_mode", default="replay")


def brands() -> list[str]:
    """Workspaces on the sign-in screen: the six airlines in the dataset."""
    return list(settings()["brands"])


def live_identities() -> list[str]:
    """Airlines flying today (Live mode)."""
    return list(settings()["live_identities"])


def live_identity(brand: str) -> str:
    """Airline a dataset brand flies as today, e.g. US Airways -> American."""
    return settings()["brands"].get(brand, {}).get("now_flies_as", brand)


def set_active_brand(brand: str):
    if brand not in settings()["brands"] and brand not in settings()["live_identities"]:
        raise ValueError(f"Unknown brand {brand!r}")
    _active_brand.set(brand)


def set_active_mode(mode: str):
    if mode not in ("replay", "live"):
        raise ValueError(f"Unknown mode {mode!r}")
    _active_mode.set(mode)


def mode() -> str:
    return _active_mode.get()


def is_live() -> bool:
    return _active_mode.get() == "live"


def selected_brand() -> str:
    """The workspace the user picked (may be a retired brand)."""
    return _active_brand.get() or settings()["our_brand"]


def our_brand() -> str:
    """The airline whose posts are analysed: the picked brand in replay, its current airline in live."""
    b = selected_brand()
    return live_identity(b) if is_live() else b


def workspace() -> str:
    """Key for per-workspace runtime state. Live views of one airline share it (US Airways live = American live)."""
    return f"{our_brand()}:live" if is_live() else our_brand()


def active_brands() -> dict:
    """Brand catalogue for the current mode: dataset airlines in replay, airlines flying today in live."""
    return settings()["live_identities"] if is_live() else settings()["brands"]


def display_name(brand: str | None = None) -> str:
    """'US Airways (now American Airlines)' in live mode for retired brands, else the plain name."""
    b = brand or selected_brand()
    note = settings()["brands"].get(b, {}).get("display_now")
    return f"{b} ({note})" if note and is_live() else b


def competitors() -> list[str]:
    return [b for b in active_brands() if b != our_brand()]
