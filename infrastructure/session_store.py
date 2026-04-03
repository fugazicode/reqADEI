from __future__ import annotations

import time
from typing import Optional

from shared.models.session import FormSession


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, FormSession] = {}
        self._last_activity: dict[int, float] = {}

    # ── Sync interface (used by FSM handlers) ────────────────────────────────

    def get(self, telegram_user_id: int) -> Optional[FormSession]:
        return self._sessions.get(telegram_user_id)

    def set(self, telegram_user_id: int, session: FormSession) -> None:
        self._sessions[telegram_user_id] = session
        self._last_activity[telegram_user_id] = time.time()

    def delete(self, telegram_user_id: int) -> None:
        self._sessions.pop(telegram_user_id, None)
        self._last_activity.pop(telegram_user_id, None)

    # ── Async wrappers (kept for backward compat with submission_worker etc.) ─

    async def async_get(self, telegram_user_id: int) -> Optional[FormSession]:
        return self.get(telegram_user_id)

    async def save(self, session: FormSession) -> None:
        self.set(session.telegram_user_id, session)

    async def async_delete(self, telegram_user_id: int) -> None:
        self.delete(telegram_user_id)

    def cleanup_expired(self, ttl_seconds: int = 86400) -> None:
        now = time.time()
        for user_id, last_seen in list(self._last_activity.items()):
            if now - last_seen > ttl_seconds:
                self._sessions.pop(user_id, None)
                self._last_activity.pop(user_id, None)
