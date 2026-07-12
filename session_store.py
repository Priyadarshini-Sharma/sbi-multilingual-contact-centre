"""
To run standalone to sanity check:
    python session_store.py
"""

from __future__ import annotations
import json
import time

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
SESSION_TTL_SECONDS = 3600  # auto-expire abandoned sessions after 1hr

_redis_client = None
_CONNECTION_ATTEMPTED = False
_in_memory_store: dict[str, str] = {}
_backend_in_use = "unknown"  # "redis" or "in_memory"


def _get_client():
    """Lazily connect to Redis once. Falls back to in-memory dict on any failure."""
    global _redis_client, _CONNECTION_ATTEMPTED, _backend_in_use
    if _CONNECTION_ATTEMPTED:
        return _redis_client
    _CONNECTION_ATTEMPTED = True

    if redis_lib is None:
        _backend_in_use = "in_memory"
        return None

    try:
        client = redis_lib.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True, socket_connect_timeout=1,
        )
        client.ping()  # actually verifies the server is reachable
        _redis_client = client
        _backend_in_use = "redis"
    except Exception:
        _redis_client = None
        _backend_in_use = "in_memory"
    return _redis_client


def backend() -> str:
    """Returns which backend is currently active: 'redis' or 'in_memory'."""
    _get_client()
    return _backend_in_use


def set_session(call_id: str, data: dict, ttl: int = SESSION_TTL_SECONDS) -> None:
    """Store/overwrite the full session state for a call."""
    payload = json.dumps(data)
    client = _get_client()
    if client is not None:
        client.set(f"session:{call_id}", payload, ex=ttl)
    else:
        _in_memory_store[f"session:{call_id}"] = payload


def get_session(call_id: str) -> dict | None:
    """Retrieve the current session state for a call, or None if not found/expired."""
    client = _get_client()
    if client is not None:
        raw = client.get(f"session:{call_id}")
    else:
        raw = _in_memory_store.get(f"session:{call_id}")
    return json.loads(raw) if raw else None


def append_sentiment(call_id: str, emotional_index: float) -> list[float]:
    """Appends to the rolling sentiment history for a live call and
    returns the updated history list. This is what lets the system
    detect a *trend* (e.g. customer getting progressively angrier)
    rather than judging only the latest utterance.
    """
    session = get_session(call_id) or {"sentiment_history": []}
    session.setdefault("sentiment_history", []).append(emotional_index)
    set_session(call_id, session)
    return session["sentiment_history"]


def end_session(call_id: str) -> None:
    """Deletes a session once the call ends (data has already been
    persisted to CallLogs in SQLite by this point)."""
    client = _get_client()
    if client is not None:
        client.delete(f"session:{call_id}")
    else:
        _in_memory_store.pop(f"session:{call_id}", None)


if __name__ == "__main__":
    print(f"Backend in use: {backend()}")

    test_call_id = "demo-call-001"
    set_session(test_call_id, {
        "customer_id": 7,
        "language": "Marathi",
        "intent": "Fraud",
        "sentiment_history": [],
    })

    for score in [-0.8, -0.6, -0.3]:
        history = append_sentiment(test_call_id, score)
        print(f"  sentiment history now: {history}")
        time.sleep(0.1)

    session = get_session(test_call_id)
    print(f"Full session state: {session}")

    end_session(test_call_id)
    print(f"After end_session, lookup returns: {get_session(test_call_id)}")