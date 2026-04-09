from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from infrastructure.analytics_store import AnalyticsStore
from infrastructure.session_store import SessionStore
from shared.models.session import FormSession

LOGGER = logging.getLogger(__name__)


class AnalyticsMiddleware(BaseMiddleware):
    def __init__(self, analytics_store: AnalyticsStore, session_store: SessionStore) -> None:
        self._analytics = analytics_store
        self._session_store = session_store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user_id: int | None = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        fsm_context: FSMContext | None = data.get("state")
        old_state: str | None = None
        if fsm_context:
            old_state = await fsm_context.get_state()

        result = await handler(event, data)

        if fsm_context is None:
            return result

        new_state: str | None = await fsm_context.get_state()
        session = self._session_store.get(user_id)

        if session is not None and session.analytics_session_id is None:
            try:
                session_id = await self._analytics.open_session(user_id)
                session.analytics_session_id = session_id
                self._session_store.set(user_id, session)
            except Exception as exc:
                LOGGER.warning("Failed to open analytics session for user %d: %s", user_id, exc)
                return result

        if session is None or session.analytics_session_id is None:
            return result

        context = _build_context(session)

        try:
            await self._analytics.log_fsm_transition(
                session_id=session.analytics_session_id,
                telegram_user_id=user_id,
                from_state=old_state,
                to_state=new_state,
                context=context,
            )
        except Exception as exc:
            LOGGER.warning("Failed to log FSM transition for user %d: %s", user_id, exc)

        return result


def _build_context(session: FormSession) -> dict:
    try:
        payload = session.payload
        missing_owner = len(payload.owner_missing_mandatory()) if payload else None
        missing_tenant = len(payload.tenant_personal_missing_mandatory()) if payload else None
        missing_tenanted = len(payload.tenanted_addr_missing_mandatory()) if payload else None
        missing_perm = len(payload.tenant_perm_addr_missing_mandatory()) if payload else None
    except Exception:
        missing_owner = missing_tenant = missing_tenanted = missing_perm = None

    return {
        "current_confirming_person": session.current_confirming_person,
        "current_editing_field": session.current_editing_field,
        "last_error": session.last_error,
        "id_upload_extraction_in_progress": session.id_upload_extraction_in_progress,
        "overview_message_id_present": session.overview_message_id is not None,
        "last_prompt_message_id_present": session.last_prompt_message_id is not None,
        "missing_owner_fields": missing_owner,
        "missing_tenant_fields": missing_tenant,
        "missing_tenanted_addr_fields": missing_tenanted,
        "missing_perm_addr_fields": missing_perm,
    }
