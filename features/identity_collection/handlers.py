from __future__ import annotations

import logging
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.engine import PipelineEngine
from features.data_verification.states import ReviewStates
from features.identity_collection.keyboards import consent_keyboard, upload_confirm_keyboard
from features.identity_collection.states import IdentityStates
from features.submission.states import SubmissionStates
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
    existing = session_store.get(user_id)
    cur = await state.get_state()

    if existing and existing.consent_given_at is not None:
        idle_states = (
            IdentityStates.AWAITING_CONSENT.state,
            SubmissionStates.DONE.state,
        )
        if cur is not None and cur not in idle_states:
            now = time.time()
            if existing.pending_discard_start_at is None:
                existing.pending_discard_start_at = now
                session_store.set(user_id, existing)
                await message.answer(
                    "You have a form in progress. Send /start again within 60 seconds "
                    "to discard it and begin again."
                )
                return
            if now - existing.pending_discard_start_at <= 60.0:
                pass
            else:
                existing.pending_discard_start_at = now
                session_store.set(user_id, existing)
                await message.answer(
                    "You have a form in progress. Send /start again within 60 seconds "
                    "to discard it and begin again."
                )
                return

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
        "👤 *Owner ID*\n\nPlease upload a clear photo of the *owner's Aadhaar card*.\n"
        "You may send multiple photos (front and back). Press *Confirm* when done.",
        parse_mode="Markdown",
    )


@router.callback_query(IdentityStates.AWAITING_CONSENT, F.data == "consent:cancel")
async def consent_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Operation cancelled.")
    await state.clear()
    await callback.message.edit_text("Operation cancelled. Send /start to begin again.")  # type: ignore[union-attr]


# ── Owner photo accumulation ──────────────────────────────────────────────────

@router.message(IdentityStates.UPLOADING_OWNER_ID, F.photo)
async def owner_photo_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        await message.answer("Session expired. Please send /start.")
        return

    file_id = message.photo[-1].file_id
    session.owner_image_file_ids = [file_id]

    if session.upload_status_message_id:
        try:
            await bot.delete_message(message.chat.id, session.upload_status_message_id)
        except Exception:
            pass

    count = len(session.owner_image_file_ids)
    confirm_msg = await message.answer(
        f"📎 *{count} image{'s' if count != 1 else ''} received.*\n"
        "Confirm to proceed with extraction, or Remove to start over.",
        reply_markup=upload_confirm_keyboard("owner", count),
        parse_mode="Markdown",
    )
    session.upload_status_message_id = confirm_msg.message_id
    session_store.set(user_id, session)


@router.callback_query(IdentityStates.UPLOADING_OWNER_ID, F.data == "upload:confirm:owner")
async def owner_upload_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    await callback.message.delete()  # type: ignore[union-attr]
    session.upload_status_message_id = None

    status_msg = await callback.message.answer(  # type: ignore[union-attr]
        "⏳ Extracting owner details from ID image…"
    )
    session.current_confirming_person = "owner"
    session_store.set(user_id, session)

    session = await pipeline.run(session)
    session_store.set(user_id, session)

    if session.last_error:
        session.image_records = [r for r in session.image_records if r.person != "owner"]
        await status_msg.edit_text(
            f"❌ {session.last_error}\n\nPlease re-upload the owner ID."
            "\n\nSend a new photo to try again."
        )
        session.last_error = None
        session_store.set(user_id, session)
        return

    if session.payload.owner and session.payload.owner.occupation is None:
        session.payload.owner.occupation = "SERVICE"

    await status_msg.delete()
    await state.set_state(ReviewStates.REVIEWING_OWNER)
    session_store.set(user_id, session)

    from features.data_verification.overview import send_owner_overview
    await send_owner_overview(callback.message, session)  # type: ignore[arg-type]


@router.callback_query(IdentityStates.UPLOADING_OWNER_ID, F.data == "upload:remove:owner")
async def owner_upload_removed(
    callback: CallbackQuery,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    session.image_records = [r for r in session.image_records if r.person != "owner"]
    await callback.message.delete()  # type: ignore[union-attr]
    session.upload_status_message_id = None
    session_store.set(user_id, session)

    await callback.message.answer(  # type: ignore[union-attr]
        "🔄 Images cleared. Please re-upload the owner's Aadhaar photo(s)."
    )


# ── Tenant photo accumulation ─────────────────────────────────────────────────

@router.message(IdentityStates.UPLOADING_TENANT_ID, F.photo)
async def tenant_photo_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        await message.answer("Session expired. Please send /start.")
        return

    file_id = message.photo[-1].file_id
    session.tenant_image_file_ids = [file_id]

    if session.upload_status_message_id:
        try:
            await bot.delete_message(message.chat.id, session.upload_status_message_id)
        except Exception:
            pass

    count = len(session.tenant_image_file_ids)
    confirm_msg = await message.answer(
        f"📎 *{count} image{'s' if count != 1 else ''} received.*\n"
        "Confirm to proceed with extraction, or Remove to start over.",
        reply_markup=upload_confirm_keyboard("tenant", count),
        parse_mode="Markdown",
    )
    session.upload_status_message_id = confirm_msg.message_id
    session_store.set(user_id, session)


@router.callback_query(IdentityStates.UPLOADING_TENANT_ID, F.data == "upload:confirm:tenant")
async def tenant_upload_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    await callback.message.delete()  # type: ignore[union-attr]
    session.upload_status_message_id = None

    status_msg = await callback.message.answer(  # type: ignore[union-attr]
        "⏳ Extracting tenant details from ID image…"
    )
    session.current_confirming_person = "tenant"
    session_store.set(user_id, session)

    session = await pipeline.run(session)
    session_store.set(user_id, session)

    if session.last_error:
        session.image_records = [r for r in session.image_records if r.person != "tenant"]
        await status_msg.edit_text(
            f"❌ {session.last_error}\n\nPlease re-upload the tenant ID."
            "\n\nSend a new photo to try again."
        )
        session.last_error = None
        session_store.set(user_id, session)
        return

    await status_msg.delete()
    await state.set_state(ReviewStates.REVIEWING_TENANT)
    session_store.set(user_id, session)

    from features.data_verification.overview import send_tenant_personal_overview
    await send_tenant_personal_overview(callback.message, session)  # type: ignore[arg-type]


@router.callback_query(IdentityStates.UPLOADING_TENANT_ID, F.data == "upload:remove:tenant")
async def tenant_upload_removed(
    callback: CallbackQuery,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    session.image_records = [r for r in session.image_records if r.person != "tenant"]
    await callback.message.delete()  # type: ignore[union-attr]
    session.upload_status_message_id = None
    session_store.set(user_id, session)

    await callback.message.answer(  # type: ignore[union-attr]
        "🔄 Images cleared. Please re-upload the tenant's Aadhaar photo(s)."
    )
