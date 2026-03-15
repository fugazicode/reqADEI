from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from features.data_verification.confirmation_flow import ConfirmationFlow
from features.data_verification.friction import HIGH_FRICTION_FIELDS
from features.data_verification.keyboards import double_confirm_keyboard
from features.data_verification.states import DataVerificationStates
from features.extras_collection.keyboards import owner_occupation_keyboard, tenant_purpose_keyboard
from features.submission.states import SubmissionStates
from infrastructure.session_store import SessionStore
from utils.aadhaar import validate_aadhaar
from utils.payload_accessor import PayloadAccessor

router = Router(name=__name__)
LOGGER = logging.getLogger(__name__)


async def _next_step(message: Message, state: FSMContext, session_store: SessionStore, user_id: int) -> None:
    session = await session_store.get(user_id)
    if session is None:
        await message.answer("Session expired. Send /start to begin again.")
        return

    if not session.confirmation_queue:
        if session.next_stage == "submission":
            if session.payload.is_submittable():
                await state.set_state("SubmissionStates:COMPLETE")
                await message.answer("Submission complete. Playwright phase is queued.")
            else:
                await message.answer("Some required fields are still missing.")
            await session_store.save(session)
            return

        if session.next_stage == "owner_extras":
            session.next_stage = None
            await state.set_state("ExtrasCollectionStates:OWNER_OCCUPATION")
            await message.answer("Select owner occupation.", reply_markup=owner_occupation_keyboard())
            await session_store.save(session)
            return

        if session.next_stage == "tenant_extras":
            session.next_stage = None
            await state.set_state("ExtrasCollectionStates:TENANT_EXTRAS")
            await message.answer("Select tenancy purpose.", reply_markup=tenant_purpose_keyboard())
            await session_store.save(session)
            return

        await session_store.save(session)
        return

    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(message, state)
    if result == "missing":
        session.edit_return_state = await state.get_state()
        session.edit_return_person = session.current_confirming_person
        await session_store.save(session)
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
    await session_store.save(session)


@router.callback_query(F.data.startswith("edit:"))
async def edit_field(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    field_path = callback.data.split(":", 1)[1]
    session.current_editing_field = field_path
    session.edit_return_state = await state.get_state()
    session.edit_return_person = session.current_confirming_person
    await session_store.save(session)
    await state.update_data(pending_double_confirm=None)
    await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
    await callback.message.answer(f"Please type new value for {field_path}.")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_field(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    field_path = callback.data.split(":", 1)[1]
    expected_field = session.confirmation_queue[0] if session.confirmation_queue else None
    if expected_field is None or expected_field != field_path:
        await callback.answer("This confirmation is no longer active.", show_alert=True)
        return

    fsm_data = await state.get_data()
    pending_double = fsm_data.get("pending_double_confirm")

    if pending_double and pending_double != field_path:
        await callback.answer("This confirmation is no longer active.", show_alert=True)
        return

    if field_path in HIGH_FRICTION_FIELDS and pending_double != field_path:
        # High-friction fields defer queue popping to confirm2 for double-acknowledgement.
        await state.update_data(pending_double_confirm=field_path)
        await callback.message.answer(
            f"Please reconfirm {field_path}.",
            reply_markup=double_confirm_keyboard(field_path),
        )
        await callback.answer()
        return

    if session.confirmation_queue and session.confirmation_queue[0] == field_path:
        session.confirmation_queue.pop(0)

    await state.update_data(pending_double_confirm=None)
    await session_store.save(session)
    await callback.answer("Confirmed")
    await _next_step(callback.message, state, session_store, callback.from_user.id)


@router.callback_query(F.data.startswith("confirm2:"))
async def confirm_field_second(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    field_path = callback.data.split(":", 1)[1]
    expected_field = session.confirmation_queue[0] if session.confirmation_queue else None
    if expected_field is None or expected_field != field_path:
        await callback.answer("This confirmation is no longer active.", show_alert=True)
        return

    fsm_data = await state.get_data()
    pending_double = fsm_data.get("pending_double_confirm")
    if pending_double != field_path:
        await callback.answer("This confirmation is no longer active.", show_alert=True)
        return
    assert (
        session.confirmation_queue and session.confirmation_queue[0] == field_path
    ), f"Double confirm out of sync for {field_path}."
    if session.confirmation_queue and session.confirmation_queue[0] == field_path:
        session.confirmation_queue.pop(0)

    await state.update_data(pending_double_confirm=None)
    await session_store.save(session)
    await callback.answer("Confirmed")
    await _next_step(callback.message, state, session_store, callback.from_user.id)


@router.message(DataVerificationStates.CONFIRMING_FIELD)
async def confirm_field_hint(message: Message) -> None:
    await message.answer("Please use the buttons to confirm or edit the field.")


@router.message(DataVerificationStates.AWAITING_EDIT_INPUT)
async def receive_edit_input(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user or not message.text:
        return

    session = await session_store.get(message.from_user.id)
    if session is None:
        await message.answer("Session expired. Send /start.")
        return

    if not session.current_editing_field:
        await message.answer("No field is currently set for editing.")
        return

    value = message.text.strip()
    if session.current_editing_field.endswith("address_verification_doc_no"):
        is_valid, cleaned = validate_aadhaar(value)
        if not is_valid:
            await message.answer(
                "The Aadhaar number you entered appears to be invalid. Please check it and type it again."
            )
            return
        value = cleaned

    PayloadAccessor.set(session.payload, session.current_editing_field, value)
    session.current_editing_field = None

    if session.edit_return_state is None:
        LOGGER.warning(
            "Missing edit_return_state for user %s; falling back to confirmation state.",
            message.from_user.id,
        )
        return_state = DataVerificationStates.CONFIRMING_FIELD.state
    else:
        return_state = session.edit_return_state

    session.edit_return_state = None
    session.edit_return_person = None
    await session_store.save(session)
    await state.set_state(return_state)
    await _next_step(message, state, session_store, message.from_user.id)


@router.message(SubmissionStates.COMPLETE)
async def already_complete(message: Message) -> None:
    await message.answer("Your submission is queued. Playwright integration is coming soon.")
