from __future__ import annotations

import logging
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.pipeline_engine import PipelineEngine
from features.data_verification.states import ReviewStates
from features.identity_collection.keyboards import consent_keyboard
from features.identity_collection.states import IdentityStates
from infrastructure.session_store import SessionStore
from shared.models.form_payload import FormPayload
from shared.models.session import FormSession, ImageRecord

LOGGER = logging.getLogger(__name__)
router = Router(name="identity_collection")

_CONSENT_TEXT = (
    "🔒 *Tenant Verification Bot*\n\n"
    "This bot collects owner and tenant Aadhaar information "
    "to automate the Delhi Police Tenant Verification portal.\n\n"
    "By proceeding you confirm that you have consent from all parties "
    "to share their identity documents."
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    user_id = message.from_user.id
    session = FormSession(telegram_user_id=user_id, payload=FormPayload())
    session_store.set(user_id, session)
    await state.set_state(IdentityStates.AWAITING_CONSENT)
    await message.answer(_CONSENT_TEXT, reply_markup=consent_keyboard(), parse_mode="Markdown")


@router.callback_query(IdentityStates.AWAITING_CONSENT, F.data == "consent:agree")
async def consent_agreed(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        session = FormSession(telegram_user_id=user_id, payload=FormPayload())
        session_store.set(user_id, session)
    session.consent_given_at = time.time()
    session.current_confirming_person = "owner"
    await state.set_state(IdentityStates.UPLOADING_OWNER_ID)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "👤 *Owner ID*\n\nPlease upload a clear photo of the *owner's Aadhaar card*.",
        parse_mode="Markdown",
    )


@router.callback_query(IdentityStates.AWAITING_CONSENT, F.data == "consent:cancel")
async def consent_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Operation cancelled.")
    await state.clear()
    await callback.message.edit_text("Operation cancelled. Send /start to begin again.")  # type: ignore[union-attr]


@router.message(IdentityStates.UPLOADING_OWNER_ID, F.photo)
async def owner_photo_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        await message.answer("Session expired. Please send /start.")
        return

    file_id = message.photo[-1].file_id
    session.owner_image_file_ids = [file_id]

    status_msg = await message.answer("⏳ Extracting owner details from ID image…")
    session.upload_status_message_id = status_msg.message_id
    session.current_confirming_person = "owner"
    session_store.set(user_id, session)

    session = await pipeline.run(session)
    session_store.set(user_id, session)

    if session.last_error:
        await status_msg.edit_text(f"❌ {session.last_error}\n\nPlease re-upload the owner ID.")
        session.last_error = None
        return

    await status_msg.delete()
    await state.set_state(IdentityStates.UPLOADING_TENANT_ID)
    session.current_confirming_person = "tenant"
    session_store.set(user_id, session)
    await message.answer(
        "✅ Owner details extracted.\n\n"
        "👤 *Tenant ID*\n\nNow upload a clear photo of the *tenant's Aadhaar card*.",
        parse_mode="Markdown",
    )


@router.message(IdentityStates.UPLOADING_TENANT_ID, F.photo)
async def tenant_photo_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        await message.answer("Session expired. Please send /start.")
        return

    file_id = message.photo[-1].file_id
    session.tenant_image_file_ids = [file_id]

    status_msg = await message.answer("⏳ Extracting tenant details from ID image…")
    session.upload_status_message_id = status_msg.message_id
    session.current_confirming_person = "tenant"
    session_store.set(user_id, session)

    session = await pipeline.run(session)
    session_store.set(user_id, session)

    if session.last_error:
        await status_msg.edit_text(f"❌ {session.last_error}\n\nPlease re-upload the tenant ID.")
        session.last_error = None
        return

    await status_msg.delete()
    await state.set_state(ReviewStates.REVIEWING_OWNER)
    session_store.set(user_id, session)
    from features.data_verification.overview import send_owner_overview
    await send_owner_overview(message, session)
