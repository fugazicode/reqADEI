from __future__ import annotations

import asyncio

from aiogram import F, Router
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
from shared.models.session import FormSession

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


@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user:
        return
    session = FormSession(telegram_user_id=message.from_user.id)
    await session_store.save(session)
    await state.set_state(IdentityCollectionStates.OWNER_UPLOAD)
    await message.answer(
        "Upload owner ID images, then tap Done.",
        reply_markup=done_upload_keyboard(),
    )


@router.message(IdentityCollectionStates.OWNER_UPLOAD, F.photo)
@router.message(IdentityCollectionStates.OWNER_UPLOAD, F.document)
async def collect_owner_photo(message: Message, session_store: SessionStore) -> None:
    if not message.from_user:
        return

    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Please send an image as Photo, or as Document with an image file type.")
        return

    session = await _get_or_create_session(message.from_user.id, session_store)
    session.owner_image_file_ids.append(file_id)
    await session_store.save(session)
    await message.answer("Owner image saved.")


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
    if not session.owner_image_file_ids:
        await callback.message.answer("Please upload at least one image first.")
        return

    session.current_confirming_person = "owner"
    await callback.message.answer("Processing owner ID images. Please wait...")
    try:
        session = await asyncio.wait_for(owner_engine.run(session), timeout=120)
    except TimeoutError:
        session.last_error = "Timed out while processing owner documents. Please try again with clearer images."
    await session_store.save(session)

    if session.last_error:
        await callback.message.answer(f"Owner extraction failed: {session.last_error}")
        return

    if not session.confirmation_queue:
        ConfirmationFlow.build_queue(session)

    await state.set_state(DataVerificationStates.CONFIRMING_FIELD)
    flow = ConfirmationFlow(session)
    await flow.show_next_field(callback.message, state)
    await session_store.save(session)


@router.message(IdentityCollectionStates.TENANT_UPLOAD, F.photo)
@router.message(IdentityCollectionStates.TENANT_UPLOAD, F.document)
async def collect_tenant_photo(message: Message, session_store: SessionStore) -> None:
    if not message.from_user:
        return

    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Please send an image as Photo, or as Document with an image file type.")
        return

    session = await _get_or_create_session(message.from_user.id, session_store)
    session.tenant_image_file_ids.append(file_id)
    await session_store.save(session)
    await message.answer("Tenant image saved.")


@router.callback_query(StateFilter(IdentityCollectionStates.TENANT_UPLOAD), F.data == "upload_done")
async def tenant_upload_done(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    tenant_engine: PipelineEngine,
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
    await callback.message.answer("Processing tenant ID images. Please wait...")
    try:
        session = await asyncio.wait_for(tenant_engine.run(session), timeout=120)
    except TimeoutError:
        session.last_error = "Timed out while processing tenant documents. Please try again with clearer images."
    await session_store.save(session)

    if session.last_error:
        await callback.message.answer(f"Tenant extraction failed: {session.last_error}")
        return

    if not session.confirmation_queue:
        ConfirmationFlow.build_queue(session)

    await state.set_state(DataVerificationStates.CONFIRMING_FIELD)
    flow = ConfirmationFlow(session)
    await flow.show_next_field(callback.message, state)
    await session_store.save(session)


@router.message(ExtrasCollectionStates.OWNER_OCCUPATION)
async def owner_occupation_hint(message: Message) -> None:
    await message.answer("Choose owner occupation.", reply_markup=owner_occupation_keyboard())
