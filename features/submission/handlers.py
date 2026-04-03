"""Trigger and handle Playwright submission."""
from __future__ import annotations

import logging

from aiogram.types import Message

from infrastructure.session_store import SessionStore
from shared.models.form_payload import FormPayload
from shared.models.session import FormSession
from shared.models.submission_input import SubmissionInput

LOGGER = logging.getLogger(__name__)


async def trigger_submission(message: Message, session: FormSession) -> None:
    """
    Build a SubmissionInput from the session and enqueue it to the SubmissionWorker.
    The worker is injected via the dispatcher context and retrieved from message's bot data.
    """
    from aiogram import Bot

    bot: Bot = message.bot  # type: ignore[assignment]
    submission_worker = bot["submission_worker"]  # type: ignore[index]
    analytics_store = bot.get("analytics_store")  # type: ignore[union-attr]

    if session.payload.tenant and session.payload.tenant.tenanted_address is None:
        LOGGER.warning("Submitting without tenanted_address — possible data gap")

    tenant_image_bytes = b""
    job = SubmissionInput(
        telegram_user_id=session.telegram_user_id,
        payload=session.payload,
        image_bytes=tenant_image_bytes,
    )

    queue_size = await submission_worker.enqueue(job)
    LOGGER.info(
        "Enqueued submission for user %d (queue size: %d)",
        session.telegram_user_id,
        queue_size,
    )

    if analytics_store and session.analytics_session_id:
        await analytics_store.update_session(
            session.analytics_session_id,
            submitted_at=__import__("time").time(),
        )

    await message.answer(
        f"⏳ Your form has been queued for portal submission (position {queue_size}).\n"
        "You will receive a PDF confirmation once it completes."
    )
