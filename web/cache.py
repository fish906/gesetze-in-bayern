import os
import time
from flask_login import current_user

_cache: dict = {}
_TTL = int(os.environ.get("CACHE_TTL", 3600))


def cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["time"]) < _TTL:
        return entry["value"]
    return None


def cache_set(key: str, value) -> None:
    _cache[key] = {"value": value, "time": time.time()}


def page_cache_get(key: str):
    """Returns None for authenticated users so they always get a fresh render."""
    if current_user.is_authenticated:
        return None
    return cache_get(key)


def page_cache_set(key: str, value) -> None:
    """Skips caching for authenticated users."""
    if not current_user.is_authenticated:
        cache_set(key, value)
