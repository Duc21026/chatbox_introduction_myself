"""In-memory session state for tiered suggestions.

The server owns ``shown_ids``/``level`` so the browser only has to send the
``session_id`` back.  State is intentionally process-local: this chatbot is a
single-user portfolio deployment.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

MAX_SHOWN_IDS = 200


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"Giá trị biến môi trường {name} không hợp lệ: {raw!r}"
        ) from exc


@dataclass
class SessionState:
    session_id: str
    shown_ids: list[str] = field(default_factory=list)
    last_query: Optional[str] = None
    level: int = 1
    last_topics: list[str] = field(default_factory=list)
    last_candidates: list[str] = field(default_factory=list)
    touched_at: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.touched_at = time.monotonic()

    def add_shown(self, ids) -> None:
        for item_id in ids:
            if not item_id or item_id in self.shown_ids:
                continue
            self.shown_ids.append(str(item_id))
        if len(self.shown_ids) > MAX_SHOWN_IDS:
            del self.shown_ids[: len(self.shown_ids) - MAX_SHOWN_IDS]


class SessionStore:
    def __init__(self, ttl=None, max_sessions=None):
        self.ttl = int(
            ttl if ttl is not None else _env_int("CHATBOT_SESSION_TTL", 1800)
        )
        self.max_sessions = int(
            max_sessions
            if max_sessions is not None
            else _env_int("CHATBOT_SESSION_MAX", 1000)
        )
        if self.ttl <= 0:
            raise RuntimeError("CHATBOT_SESSION_TTL phải lớn hơn 0")
        if self.max_sessions <= 0:
            raise RuntimeError("CHATBOT_SESSION_MAX phải lớn hơn 0")
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def _expire_locked(self, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        stale = [
            session_id
            for session_id, state in self._sessions.items()
            if now - state.touched_at >= self.ttl
        ]
        for session_id in stale:
            self._sessions.pop(session_id, None)

    def _evict_locked(self) -> None:
        while len(self._sessions) > self.max_sessions:
            oldest = min(
                self._sessions.items(), key=lambda item: item[1].touched_at
            )[0]
            self._sessions.pop(oldest, None)

    def expire(self) -> int:
        with self._lock:
            before = len(self._sessions)
            self._expire_locked()
            return before - len(self._sessions)

    def get_or_create(self, session_id: Optional[str] = None):
        with self._lock:
            self._expire_locked()
            if isinstance(session_id, str):
                session_id = session_id.strip()
            if not session_id or len(session_id) > 100:
                session_id = f"s-{uuid.uuid4().hex}"
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id)
                self._sessions[session_id] = state
            state.touch()
            self._evict_locked()
            return session_id, state

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            self._expire_locked()
            return self._sessions.get(session_id)

    def reset(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def count(self) -> int:
        with self._lock:
            self._expire_locked()
            return len(self._sessions)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
