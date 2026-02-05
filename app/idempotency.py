"""Idempotency support for webhook: deduplicate requests by key to avoid duplicate orders."""

import os
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Default: 24 hours. Set IDEMPOTENCY_TTL_SECONDS=0 to disable.
DEFAULT_TTL_SECONDS = 86400

_store = None
_store_lock = threading.Lock()


def get_idempotency_key(request):
    """Return idempotency key from request: header 'Idempotency-Key' or body 'idempotency_key'."""
    key = None
    if request.headers.get("Idempotency-Key"):
        key = request.headers.get("Idempotency-Key").strip()
    if not key and request.is_json:
        data = request.get_json(silent=True) or {}
        raw = data.get("idempotency_key")
        if raw is not None:
            key = str(raw).strip() if raw else None
    return key if key else None


def _ttl_seconds():
    try:
        val = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", DEFAULT_TTL_SECONDS))
        return max(0, val)
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS


class IdempotencyStore:
    """Thread-safe in-memory store for idempotency: key -> (response_dict, status_code, expires_at)."""

    def __init__(self, ttl_seconds=None):
        self._ttl = ttl_seconds if ttl_seconds is not None else _ttl_seconds()
        self._data = {}
        self._lock = threading.Lock()

    def get(self, key):
        """Return (response_dict, status_code) if key exists and not expired, else None."""
        with self._lock:
            self._prune_locked()
            entry = self._data.get(key)
            if not entry:
                return None
            _, status_code, expires_at = entry
            if time.time() > expires_at:
                del self._data[key]
                return None
            response_dict, status_code, _ = entry
            return (response_dict, status_code)

    def set(self, key, response_dict, status_code):
        """Store response for key. Only call for successful (200) responses if you want duplicate to get success."""
        if self._ttl <= 0:
            return
        with self._lock:
            self._prune_locked()
            expires_at = time.time() + self._ttl
            self._data[key] = (response_dict, status_code, expires_at)
            logger.debug("Idempotency stored key=%s status=%s ttl=%ss", key[:32] if len(key) > 32 else key, status_code, self._ttl)

    def _prune_locked(self):
        now = time.time()
        expired = [k for k, v in self._data.items() if v[2] < now]
        for k in expired:
            del self._data[k]


def get_store():
    """Return singleton IdempotencyStore (TTL from env)."""
    global _store
    with _store_lock:
        if _store is None:
            ttl = _ttl_seconds()
            _store = IdempotencyStore(ttl_seconds=ttl)
            logger.info("Idempotency store initialized with TTL=%ss", ttl)
        return _store
