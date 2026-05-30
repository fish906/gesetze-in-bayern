import atexit
import logging
import os
import time

from .extensions import db
from models import Law, Norm

logger = logging.getLogger("hits")

_hits: dict = {}
_last_flush: float = time.time()
_INTERVAL: int = int(os.environ.get("HITS_FLUSH_INTERVAL", 60))
_app = None


def init_app(app) -> None:
    global _app
    _app = app
    atexit.register(flush)


def record(hit_type: str, identifier: str) -> None:
    key = f"{hit_type}:{identifier}"
    _hits[key] = _hits.get(key, 0) + 1
    logger.debug(f"Hit recorded: {key}")
    _maybe_flush()


def flush() -> None:
    global _hits, _last_flush
    if not _hits or not _app:
        return
    snapshot = _hits.copy()
    _hits = {}
    _last_flush = time.time()
    try:
        with _app.app_context():
            for key, count in snapshot.items():
                hit_type, identifier = key.split(":", 1)
                if hit_type == "law":
                    law = db.session.query(Law).filter(Law.name == identifier).first()
                    if law:
                        law.views += count
                elif hit_type == "norm":
                    law_name, number = identifier.split("/", 1)
                    norm = db.session.query(Norm).join(Law).filter(
                        Law.name == law_name,
                        Norm.number == number,
                    ).first()
                    if norm:
                        norm.views += count
            db.session.commit()
        logger.debug(f"Flushed {len(snapshot)} hit counters")
    except Exception as e:
        logger.info(f"Failed to flush hits: {e}")
        for key, count in snapshot.items():
            _hits[key] = _hits.get(key, 0) + count


def _maybe_flush() -> None:
    if (time.time() - _last_flush) >= _INTERVAL:
        flush()
