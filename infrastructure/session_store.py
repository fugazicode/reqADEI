from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from shared.models.session import FormSession


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, FormSession] = {}
        self._last_activity: dict[int, float] = {}
        self._user_locks: dict[int, asyncio.Lock] = {}
        # (telegram_user_id, person) person is "owner" | "tenant"
        self._upload_debounce_tasks: dict[tuple[int, str], asyncio.Task[None]] = {}

    @asynccontextmanager
    async def user_lock(self, user_id: int) -> AsyncIterator[None]:
        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            yield

    def cancel_upload_debounce(self, user_id: int, person: str) -> None:
        key = (user_id, person)
        task = self._upload_debounce_tasks.pop(key, None)
        if task is not None and not task.done():
            task.cancel()

    def cancel_all_upload_debounces_for_user(self, user_id: int) -> None:
        for key in list(self._upload_debounce_tasks.keys()):
            if key[0] != user_id:
                continue
            task = self._upload_debounce_tasks.pop(key, None)
            if task is not None and not task.done():
                task.cancel()

    def replace_upload_debounce_task(
        self, user_id: int, person: str, task: asyncio.Task[None]
    ) -> None:
        self.cancel_upload_debounce(user_id, person)
        self._upload_debounce_tasks[(user_id, person)] = task

    # ── Sync interface (used by FSM handlers) ────────────────────────────────

    def get(self, telegram_user_id: int) -> Optional[FormSession]:
        return self._sessions.get(telegram_user_id)

    def set(self, telegram_user_id: int, session: FormSession) -> None:
        self._sessions[telegram_user_id] = session
        self._last_activity[telegram_user_id] = time.time()

    def delete(self, telegram_user_id: int) -> None:
        self.cancel_all_upload_debounces_for_user(telegram_user_id)
        self._user_locks.pop(telegram_user_id, None)
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
                self.cancel_all_upload_debounces_for_user(user_id)
                self._user_locks.pop(user_id, None)
                self._sessions.pop(user_id, None)
                self._last_activity.pop(user_id, None)
