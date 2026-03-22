from __future__ import annotations

import asyncio
import time

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from core.engine import PipelineEngine
from features.data_verification.confirmation_flow import ConfirmationFlow
from features.data_verification.states import DataVerificationStates
from features.extras_collection.keyboards import owner_occupation_keyboard
from features.extras_collection.states import ExtrasCollectionStates
from features.identity_collection.keyboards import done_upload_keyboard
from features.identity_collection.states import IdentityCollectionStates
from infrastructure.session_store import SessionStore
from shared.models.session import FormSession, ImageRecord

_pending_edit_tasks: dict[int, asyncio.Task] = {}

router = Router(name=__name__)


async def _get_or_create_session(user_id: int, session_store: SessionStore) -> FormSession:
    session = await session_store.get(user_id)
    if session is not None:
        return session
    session = FormSession(telegram_user_id=user_id)
    await session_store.save(session)
    return session


def _extract_image_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id

    if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        return message.document.file_id

    return None


@router.callback_query(StateFilter(IdentityCollectionStates.AWAITING_CONSENT), F.data == "consent:agree")
async def consent_agree(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    if not callback.from_user or not callback.message:
        return

    session = await _get_or_create_session(callback.from_user.id, session_store)
    session.consent_given_at = time.time()
    await session_store.save(session)

    await state.set_state(IdentityCollectionStates.OWNER_UPLOAD)
    response = await callback.message.answer(
        "Upload owner ID images, then tap Done.",
        reply_markup=done_upload_keyboard(),
    )
    session.upload_status_message_id = response.message_id
    await session_store.save(session)
    await callback.answer()


@router.message(IdentityCollectionStates.OWNER_UPLOAD, F.photo)
@router.message(IdentityCollectionStates.OWNER_UPLOAD, F.document)
async def collect_owner_photo(message: Message, session_store: SessionStore, bot: Bot) -> None:
    if not message.from_user:
        return

    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Please send an image as Photo, or as Document with an image file type.")
        return

    session = await _get_or_create_session(message.from_user.id, session_store)
    session.image_records.append(
        ImageRecord(
            image_id=file_id,
            person="owner",
            upload_timestamp=time.time(),
            media_group_id=message.media_group_id,
        )
    )
    await session_store.save(session)
    count = len([record for record in session.image_records if record.person == "owner"])

    existing_task = _pending_edit_tasks.get(message.from_user.id)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        try:
            await existing_task
        except asyncio.CancelledError:
            pass

    upload_status_message_id = session.upload_status_message_id
    chat_id = message.chat.id
    reply_markup = done_upload_keyboard()
    text = f"{count} image(s) received. Tap Done when finished."

    async def _do_edit() -> None:
        await asyncio.sleep(0.2)
        if upload_status_message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=upload_status_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return

        response = await message.answer(text, reply_markup=reply_markup)
        session.upload_status_message_id = response.message_id
        await session_store.save(session)

    _pending_edit_tasks[message.from_user.id] = asyncio.create_task(_do_edit())


@router.callback_query(StateFilter(IdentityCollectionStates.OWNER_UPLOAD), F.data == "upload_done")
async def owner_upload_done(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    owner_engine: PipelineEngine,
) -> None:
    if not callback.from_user or not callback.message:
        return

    # Acknowledge immediately so Telegram client does not keep spinning.
    await callback.answer()

    session = await _get_or_create_session(callback.from_user.id, session_store)
    if session.consent_given_at is None:
        await callback.answer(
            "Please agree to the data collection terms first. Send /start to begin.",
            show_alert=True,
        )
        return
    if not session.owner_image_file_ids:
        await callback.message.answer("Please upload at least one image first.")
        return

    session.current_confirming_person = "owner"
    session.upload_status_message_id = None
    await callback.message.answer("Processing owner ID images. Please wait...")
    try:
        session = await asyncio.wait_for(owner_engine.run(session), timeout=120)
    except TimeoutError:
        session.last_error = "Timed out while processing owner documents. Please try again with clearer images."
    await session_store.save(session)

    if session.last_error:
        await callback.message.answer(f"Owner extraction failed: {session.last_error}")
        return

    session.next_stage = "owner_extras"

    if not session.confirmation_queue:
        ConfirmationFlow.build_queue(session)

    await state.set_state(DataVerificationStates.CONFIRMING_FIELD)
    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(callback.message, state)
    if result == "missing":
        session.edit_return_state = DataVerificationStates.CONFIRMING_FIELD.state
        session.edit_return_person = session.current_confirming_person
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)

    for record in session.image_records:
        if record.person == "owner":
            record.image_id = "redacted"
    await session_store.save(session)


@router.message(IdentityCollectionStates.TENANT_UPLOAD, F.photo)
@router.message(IdentityCollectionStates.TENANT_UPLOAD, F.document)
async def collect_tenant_photo(message: Message, session_store: SessionStore, bot: Bot) -> None:
    if not message.from_user:
        return

    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Please send an image as Photo, or as Document with an image file type.")
        return

    session = await _get_or_create_session(message.from_user.id, session_store)
    session.image_records.append(
        ImageRecord(
            image_id=file_id,
            person="tenant",
            upload_timestamp=time.time(),
            media_group_id=message.media_group_id,
        )
    )
    await session_store.save(session)
    count = len([record for record in session.image_records if record.person == "tenant"])

    existing_task = _pending_edit_tasks.get(message.from_user.id)
    if existing_task and not existing_task.done():
        existing_task.cancel()
        try:
            await existing_task
        except asyncio.CancelledError:
            pass

    upload_status_message_id = session.upload_status_message_id
    chat_id = message.chat.id
    reply_markup = done_upload_keyboard()
    text = f"{count} image(s) received. Tap Done when finished."

    async def _do_edit() -> None:
        await asyncio.sleep(0.2)
        if upload_status_message_id:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=upload_status_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return

        response = await message.answer(text, reply_markup=reply_markup)
        session.upload_status_message_id = response.message_id
        await session_store.save(session)

    _pending_edit_tasks[message.from_user.id] = asyncio.create_task(_do_edit())


@router.callback_query(StateFilter(IdentityCollectionStates.TENANT_UPLOAD), F.data == "upload_done")
async def tenant_upload_done(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    tenant_engine: PipelineEngine,
    bot: Bot,
) -> None:
    if not callback.from_user or not callback.message:
        return

    # Acknowledge immediately so Telegram client does not keep spinning.
    await callback.answer()

    session = await _get_or_create_session(callback.from_user.id, session_store)
    if not session.tenant_image_file_ids:
        await callback.message.answer("Please upload at least one image first.")
        return

    session.current_confirming_person = "tenant"
    session.upload_status_message_id = None
    await callback.message.answer("Processing tenant ID images. Please wait...")
    try:
        session = await asyncio.wait_for(tenant_engine.run(session), timeout=120)
    except TimeoutError:
        session.last_error = "Timed out while processing tenant documents. Please try again with clearer images."
    await session_store.save(session)

    if session.last_error:
        await callback.message.answer(f"Tenant extraction failed: {session.last_error}")
        return

    session.next_stage = "tenant_extras"

    if not session.confirmation_queue:
        ConfirmationFlow.build_queue(session)

    await state.set_state(DataVerificationStates.CONFIRMING_FIELD)
    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(callback.message, state)
    if result == "missing":
        session.edit_return_state = DataVerificationStates.CONFIRMING_FIELD.state
        session.edit_return_person = session.current_confirming_person
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)

    front_record = next(
        (r for r in session.image_records if r.person == "tenant" and r.side == "front"),
        None,
    ) or next(
        (r for r in session.image_records if r.person == "tenant"),
        None,
    )
    if front_record:
        import io

        buffer = io.BytesIO()
        await bot.download(front_record.image_id, destination=buffer)
        session.tenant_image_bytes = buffer.getvalue()

    for record in session.image_records:
        if record.person == "tenant":
            record.image_id = "redacted"
    await session_store.save(session)


@router.message(ExtrasCollectionStates.OWNER_OCCUPATION)
async def owner_occupation_hint(message: Message) -> None:
    await message.answer("Choose owner occupation.", reply_markup=owner_occupation_keyboard())
