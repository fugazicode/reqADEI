from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
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
from shared.models.session import FormSession

LOGGER = logging.getLogger(__name__)
router = Router(name="identity_collection")

UPLOAD_PROMPT_DEBOUNCE_SEC = 0.5

_CONSENT_TEXT = (
    "🔒 *Tenant Verification Bot*\n\n"
    "This bot collects owner and tenant Aadhaar information "
    "to automate the Delhi Police Tenant Verification portal.\n\n"
    "By proceeding you confirm that you have consent from all parties "
    "to share their identity documents."
)


def _id_upload_prompt_text(person_label: str, count: int) -> str:
    return (
        f"📎 *{count} image{'s' if count != 1 else ''} queued* for {person_label}.\n\n"
        "Tap *Extract* when you are ready to read the ID. "
        "*Clear all* removes every photo from this batch only (your messages stay in the chat)."
    )


async def _flush_id_upload_prompt(
    bot: Bot,
    session_store: SessionStore,
    user_id: int,
    chat_id: int,
    person: str,
) -> None:
    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if session is None or session.id_upload_extraction_in_progress:
            return
        if person == "owner":
            count = len(session.owner_image_file_ids)
            label = "the owner's ID"
        else:
            count = len(session.tenant_image_file_ids)
            label = "the tenant's ID"

        text = _id_upload_prompt_text(label, count)
        kb = upload_confirm_keyboard(person, count)
        mid = session.upload_status_message_id

        if mid is not None:
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=chat_id,
                    message_id=mid,
                    reply_markup=kb,
                    parse_mode="Markdown",
                )
                session_store.set(user_id, session)
                return
            except TelegramBadRequest as e:
                err = str(e).lower()
                if "message is not modified" in err:
                    return
                # Message deleted or not editable — send a new prompt.

        msg = await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
        session.upload_status_message_id = msg.message_id
        session_store.set(user_id, session)


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

    session_store.cancel_all_upload_debounces_for_user(user_id)
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
        "You may send multiple photos (front and back). Tap *Extract* on the bot prompt when ready.",
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
    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await message.answer("Session expired. Please send /start.")
            return

        if session.id_upload_extraction_in_progress:
            await message.answer("Please wait — extraction is running. Try again in a moment.")
            return

        file_id = message.photo[-1].file_id
        session.owner_image_file_ids = [file_id]
        session_store.set(user_id, session)

        chat_id = message.chat.id

        async def _debounced_flush() -> None:
            try:
                await asyncio.sleep(UPLOAD_PROMPT_DEBOUNCE_SEC)
            except asyncio.CancelledError:
                return
            await _flush_id_upload_prompt(bot, session_store, user_id, chat_id, "owner")

        task = asyncio.create_task(_debounced_flush())
        session_store.replace_upload_debounce_task(user_id, "owner", task)


@router.callback_query(IdentityStates.UPLOADING_OWNER_ID, F.data == "upload:confirm:owner")
async def owner_upload_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    user_id = callback.from_user.id
    mid = callback.message.message_id if callback.message else None

    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await callback.answer("Session expired.", show_alert=True)
            return
        if mid is None or session.upload_status_message_id is None or mid != session.upload_status_message_id:
            await callback.answer("That button is outdated. Use the latest prompt.", show_alert=True)
            return
        if session.id_upload_extraction_in_progress:
            await callback.answer("Extraction already running.", show_alert=True)
            return
        if len(session.owner_image_file_ids) < 1:
            await callback.answer("Send at least one photo first.", show_alert=True)
            return

        session_store.cancel_upload_debounce(user_id, "owner")
        await callback.answer()

        try:
            await callback.message.delete()  # type: ignore[union-attr]
        except Exception:
            pass
        session.upload_status_message_id = None
        session.id_upload_extraction_in_progress = True
        session.current_confirming_person = "owner"
        session_store.set(user_id, session)

    status_msg = await callback.message.answer(  # type: ignore[union-attr]
        "⏳ Extracting owner details from ID image…"
    )
    try:
        session = session_store.get(user_id)
        if session is None:
            await status_msg.edit_text("Session expired. Send /start.")
            return
        session = await pipeline.run(session)
        session_store.set(user_id, session)
    finally:
        session = session_store.get(user_id)
        if session is not None:
            session.id_upload_extraction_in_progress = False
            session_store.set(user_id, session)

    session = session_store.get(user_id)
    if session is None:
        return

    if session.last_error:
        err = session.last_error
        session.image_records = [r for r in session.image_records if r.person != "owner"]
        session.last_error = None
        count = len(session.owner_image_file_ids)
        prompt = _id_upload_prompt_text("the owner's ID", count)
        try:
            await status_msg.edit_text(
                f"❌ {err}\n\n{prompt}",
                reply_markup=upload_confirm_keyboard("owner", count),
                parse_mode="Markdown",
            )
            session.upload_status_message_id = status_msg.message_id
        except TelegramBadRequest:
            session.upload_status_message_id = None
            msg = await callback.message.answer(  # type: ignore[union-attr]
                f"❌ {err}\n\n{prompt}",
                reply_markup=upload_confirm_keyboard("owner", count),
                parse_mode="Markdown",
            )
            session.upload_status_message_id = msg.message_id
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
) -> None:
    user_id = callback.from_user.id
    mid = callback.message.message_id if callback.message else None

    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await callback.answer("Session expired.", show_alert=True)
            return
        if mid is None or session.upload_status_message_id is None or mid != session.upload_status_message_id:
            await callback.answer("That button is outdated. Use the latest prompt.", show_alert=True)
            return

        session_store.cancel_upload_debounce(user_id, "owner")
        await callback.answer()

        session.image_records = [r for r in session.image_records if r.person != "owner"]
        count = len(session.owner_image_file_ids)
        text = _id_upload_prompt_text("the owner's ID", count)
        kb = upload_confirm_keyboard("owner", count)

        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                text, reply_markup=kb, parse_mode="Markdown"
            )
            session.upload_status_message_id = callback.message.message_id  # type: ignore[union-attr]
        except TelegramBadRequest:
            try:
                await callback.message.delete()  # type: ignore[union-attr]
            except Exception:
                pass
            session.upload_status_message_id = None
            msg = await callback.message.answer(  # type: ignore[union-attr]
                text, reply_markup=kb, parse_mode="Markdown"
            )
            session.upload_status_message_id = msg.message_id

        session_store.set(user_id, session)


# ── Tenant photo accumulation ─────────────────────────────────────────────────


@router.message(IdentityStates.UPLOADING_TENANT_ID, F.photo)
async def tenant_photo_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    user_id = message.from_user.id
    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await message.answer("Session expired. Please send /start.")
            return

        if session.id_upload_extraction_in_progress:
            await message.answer("Please wait — extraction is running. Try again in a moment.")
            return

        file_id = message.photo[-1].file_id
        session.tenant_image_file_ids = [file_id]
        session_store.set(user_id, session)

        chat_id = message.chat.id

        async def _debounced_flush() -> None:
            try:
                await asyncio.sleep(UPLOAD_PROMPT_DEBOUNCE_SEC)
            except asyncio.CancelledError:
                return
            await _flush_id_upload_prompt(bot, session_store, user_id, chat_id, "tenant")

        task = asyncio.create_task(_debounced_flush())
        session_store.replace_upload_debounce_task(user_id, "tenant", task)


@router.callback_query(IdentityStates.UPLOADING_TENANT_ID, F.data == "upload:confirm:tenant")
async def tenant_upload_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    pipeline: PipelineEngine,
) -> None:
    user_id = callback.from_user.id
    mid = callback.message.message_id if callback.message else None

    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await callback.answer("Session expired.", show_alert=True)
            return
        if mid is None or session.upload_status_message_id is None or mid != session.upload_status_message_id:
            await callback.answer("That button is outdated. Use the latest prompt.", show_alert=True)
            return
        if session.id_upload_extraction_in_progress:
            await callback.answer("Extraction already running.", show_alert=True)
            return
        if len(session.tenant_image_file_ids) < 1:
            await callback.answer("Send at least one photo first.", show_alert=True)
            return

        session_store.cancel_upload_debounce(user_id, "tenant")
        await callback.answer()

        try:
            await callback.message.delete()  # type: ignore[union-attr]
        except Exception:
            pass
        session.upload_status_message_id = None
        session.id_upload_extraction_in_progress = True
        session.current_confirming_person = "tenant"
        session_store.set(user_id, session)

    status_msg = await callback.message.answer(  # type: ignore[union-attr]
        "⏳ Extracting tenant details from ID image…"
    )
    try:
        session = session_store.get(user_id)
        if session is None:
            await status_msg.edit_text("Session expired. Send /start.")
            return
        session = await pipeline.run(session)
    finally:
        session = session_store.get(user_id)
        if session is not None:
            session.id_upload_extraction_in_progress = False
            session_store.set(user_id, session)

    session = session_store.get(user_id)
    if session is None:
        return

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
) -> None:
    user_id = callback.from_user.id
    mid = callback.message.message_id if callback.message else None

    async with session_store.user_lock(user_id):
        session = session_store.get(user_id)
        if not session:
            await callback.answer("Session expired.", show_alert=True)
            return
        if mid is None or session.upload_status_message_id is None or mid != session.upload_status_message_id:
            await callback.answer("That button is outdated. Use the latest prompt.", show_alert=True)
            return

        session_store.cancel_upload_debounce(user_id, "tenant")
        await callback.answer()

        session.image_records = [r for r in session.image_records if r.person != "tenant"]
        count = len(session.tenant_image_file_ids)
        text = _id_upload_prompt_text("the tenant's ID", count)
        kb = upload_confirm_keyboard("tenant", count)

        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                text, reply_markup=kb, parse_mode="Markdown"
            )
            session.upload_status_message_id = callback.message.message_id  # type: ignore[union-attr]
        except TelegramBadRequest:
            try:
                await callback.message.delete()  # type: ignore[union-attr]
            except Exception:
                pass
            session.upload_status_message_id = None
            msg = await callback.message.answer(  # type: ignore[union-attr]
                text, reply_markup=kb, parse_mode="Markdown"
            )
            session.upload_status_message_id = msg.message_id

        session_store.set(user_id, session)