from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from features.data_verification.confirmation_flow import ConfirmationFlow
from features.data_verification.labels import field_label
from features.data_verification.states import DataVerificationStates
from features.extras_collection.keyboards import (
    district_keyboard,
    owner_occupation_keyboard,
    station_keyboard,
    tenant_purpose_keyboard,
)
from features.extras_collection.states import ExtrasCollectionStates
from features.submission.states import SubmissionStates
from features.submission.submission_worker import SubmissionWorker
from shared.models.submission_input import SubmissionInput
from infrastructure.session_store import SessionStore
from utils.aadhaar import validate_aadhaar
from utils.payload_accessor import PayloadAccessor
from utils.station_lookup import StationLookup

router = Router(name=__name__)
LOGGER = logging.getLogger(__name__)

_DISTRICT_FIELDS = {
    "owner.address.district",
    "tenant.tenanted_address.district",
}
_STATION_FIELDS = {
    "owner.address.police_station",
    "tenant.tenanted_address.police_station",
}


async def _delete_message_safe(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def _delete_prompt_message(message: Message, prompt_message_id: int | None) -> None:
    if not prompt_message_id:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
    except Exception:
        pass


async def _cleanup_for_incoming_user_message(message: Message, session) -> None:
    await _delete_prompt_message(message, session.last_prompt_message_id)
    session.last_prompt_message_id = None
    await _delete_message_safe(message)


async def _send_prompt(message: Message, session, text: str, *, reply_markup=None) -> None:
    await _delete_prompt_message(message, session.last_prompt_message_id)
    sent = await message.answer(text, reply_markup=reply_markup)
    session.last_prompt_message_id = sent.message_id


async def _start_district_picker(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    user_id: int,
    *,
    page: int = 0,
) -> None:
    session = await session_store.get(user_id)
    if session is None:
        await message.answer("Session expired. Send /start.")
        return
    if not session.current_editing_field or session.current_editing_field not in _DISTRICT_FIELDS:
        await _send_prompt(message, session, "No district field is currently set for editing.")
        await session_store.save(session)
        return
    await state.set_state(DataVerificationStates.PICKING_DISTRICT)
    await _send_prompt(message, session, "Select district.", reply_markup=district_keyboard(page=page))
    await session_store.save(session)


async def _start_station_picker(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
    user_id: int,
    *,
    page: int = 0,
) -> None:
    session = await session_store.get(user_id)
    if session is None:
        await message.answer("Session expired. Send /start.")
        return
    if not session.current_editing_field or session.current_editing_field not in _STATION_FIELDS:
        await _send_prompt(message, session, "No police station field is currently set for editing.")
        await session_store.save(session)
        return

    target = session.current_editing_field
    if target.startswith("owner."):
        district_path = "owner.address.district"
    else:
        district_path = "tenant.tenanted_address.district"
    district = PayloadAccessor.get(session.payload, district_path)
    if not district:
        await _send_prompt(
            message,
            session,
            "District is required before selecting police station. Please pick district first."
        )
        session.current_editing_field = district_path
        await session_store.save(session)
        await _start_district_picker(message, state, session_store, user_id, page=0)
        return

    stations = station_lookup.stations_for_district(district)
    if not stations:
        await _send_prompt(
            message,
            session,
            f"No police stations found for district '{district}'. Please pick a different district."
        )
        session.current_editing_field = district_path
        await session_store.save(session)
        await _start_district_picker(message, state, session_store, user_id, page=0)
        return

    await state.set_state(DataVerificationStates.PICKING_STATION)
    await _send_prompt(
        message,
        session,
        f"Select police station for district: {district}",
        reply_markup=station_keyboard(stations, page=page, include_skip=True),
    )
    await session_store.save(session)


@router.callback_query(F.data.startswith("edit:"))
async def edit_field(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
) -> None:
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
    if field_path in _DISTRICT_FIELDS:
        await state.set_state(DataVerificationStates.PICKING_DISTRICT)
        await _send_prompt(callback.message, session, "Select district.", reply_markup=district_keyboard(page=0))
    elif field_path in _STATION_FIELDS:
        await _start_station_picker(
            callback.message,
            state,
            session_store,
            station_lookup,
            callback.from_user.id,
            page=0,
        )
    else:
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
        await _send_prompt(
            callback.message,
            session,
            f"Please enter new value for {field_label(field_path)}.",
        )
    await session_store.save(session)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm:"))
async def confirm_field(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    submission_worker: SubmissionWorker,
) -> None:
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

    if session.confirmation_queue and session.confirmation_queue[0] == field_path:
        session.confirmation_queue.pop(0)

    await _delete_prompt_message(callback.message, session.last_prompt_message_id)
    session.last_prompt_message_id = None
    await session_store.save(session)
    await callback.answer("Confirmed")
    await _next_step(callback.message, state, session_store, callback.from_user.id, submission_worker)


async def _next_step(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    user_id: int,
    submission_worker: "SubmissionWorker | None" = None,
    station_lookup: StationLookup | None = None,
) -> None:
    session = await session_store.get(user_id)
    if session is None:
        await message.answer("Session expired. Send /start to begin again.")
        return

    if not session.confirmation_queue:
        if session.next_stage == "submission":
            if session.payload.is_submittable():
                if submission_worker is not None:
                    job = SubmissionInput(
                        telegram_user_id=user_id,
                        payload=session.payload,
                        image_bytes=session.tenant_image_bytes or b"",
                    )
                    position = await submission_worker.enqueue(job)
                    await state.set_state(SubmissionStates.COMPLETE)
                    await message.answer(
                        f"✅ All data confirmed.\n"
                        f"Your form is queued at position {position}.\n"
                        f"You will be notified when submission completes."
                    )
                else:
                    await state.set_state(SubmissionStates.COMPLETE)
                    await message.answer("Submission complete. Playwright phase is queued.")
            else:
                await message.answer("Some required fields are still missing.")
            await session_store.save(session)
            return

        if session.next_stage == "owner_extras":
            session.next_stage = None
            await state.set_state(ExtrasCollectionStates.OWNER_OCCUPATION)
            await _send_prompt(
                message,
                session,
                "Select owner occupation.",
                reply_markup=owner_occupation_keyboard(),
            )
            await session_store.save(session)
            return

        if session.next_stage == "tenant_extras":
            session.next_stage = None
            await state.set_state(ExtrasCollectionStates.TENANT_EXTRAS)
            await _send_prompt(
                message,
                session,
                "Select tenancy purpose.",
                reply_markup=tenant_purpose_keyboard(),
            )
            await session_store.save(session)
            return

        await session_store.save(session)
        return

    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(message, state)
    if result == "confirm":
        pass  # Confirm/edit keyboard already shown by show_next_field
    elif result == "missing":
        session.edit_return_state = await state.get_state()
        session.edit_return_person = session.current_confirming_person
        await session_store.save(session)
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
    elif result == "missing_picker":
        session.edit_return_state = await state.get_state()
        session.edit_return_person = session.current_confirming_person
        await session_store.save(session)
        # Route to the appropriate picker.
        field_path = session.current_editing_field
        if field_path in _DISTRICT_FIELDS:
            await _start_district_picker(message, state, session_store, user_id, page=0)
        elif field_path in _STATION_FIELDS:
            if station_lookup is not None:
                await _start_station_picker(message, state, session_store, station_lookup, user_id, page=0)
            else:
                # Fallback: prompt district first if no station_lookup available.
                if field_path.startswith("owner."):
                    district_field_path = "owner.address.district"
                else:
                    district_field_path = "tenant.tenanted_address.district"
                session.current_editing_field = district_field_path
                await _send_prompt(
                    message,
                    session,
                    "District selection required. Please use the buttons below.",
                    reply_markup=district_keyboard(page=0),
                )
                await state.set_state(DataVerificationStates.PICKING_DISTRICT)
    await session_store.save(session)


@router.message(DataVerificationStates.CONFIRMING_FIELD)
async def confirm_field_hint(message: Message) -> None:
    await message.answer("Please use the buttons to confirm or edit the field.")


@router.message(DataVerificationStates.AWAITING_EDIT_INPUT)
async def receive_edit_input(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    submission_worker: SubmissionWorker,
) -> None:
    if not message.from_user or not message.text:
        return

    session = await session_store.get(message.from_user.id)
    if session is None:
        await message.answer("Session expired. Send /start.")
        return

    if not session.current_editing_field:
        await _send_prompt(message, session, "No field is currently set for editing.")
        await session_store.save(session)
        return

    value = message.text.strip()
    if session.current_editing_field.endswith("address_verification_doc_no"):
        is_valid, cleaned = validate_aadhaar(value)
        if not is_valid:
            await _send_prompt(
                message,
                session,
                "The Aadhaar number you entered appears to be invalid. Please check it and type it again."
            )
            await session_store.save(session)
            return
        value = cleaned

    await _cleanup_for_incoming_user_message(message, session)
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
    await _next_step(message, state, session_store, message.from_user.id, submission_worker)


@router.callback_query(DataVerificationStates.PICKING_DISTRICT, F.data.startswith("pickdistrictpage:"))
async def district_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message or not callback.data:
        return
    try:
        page = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return
    await callback.message.edit_reply_markup(reply_markup=district_keyboard(page=page))
    await callback.answer()


@router.callback_query(DataVerificationStates.PICKING_DISTRICT, F.data.startswith("pickdistrict:"))
async def pick_district(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return
    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return
    district = callback.data.split(":", 1)[1].strip()
    target = session.current_editing_field
    if target not in _DISTRICT_FIELDS:
        await callback.answer("This selection is no longer active.", show_alert=True)
        return

    PayloadAccessor.set(session.payload, target, district)
    await _delete_prompt_message(callback.message, session.last_prompt_message_id)
    session.last_prompt_message_id = None
    await session_store.save(session)
    await callback.answer("District set")

    # If user was fixing district, strongly guide them to station selection next if station is empty.
    if target.startswith("owner."):
        station_path = "owner.address.police_station"
    else:
        station_path = "tenant.tenanted_address.police_station"
    if not PayloadAccessor.get(session.payload, station_path):
        session.current_editing_field = station_path
        await session_store.save(session)
        await _start_station_picker(
            callback.message,
            state,
            session_store,
            station_lookup,
            callback.from_user.id,
            page=0,
        )
        return

    # Return to confirmation flow.
    session.current_editing_field = None
    return_state = session.edit_return_state or DataVerificationStates.CONFIRMING_FIELD.state
    session.edit_return_state = None
    session.edit_return_person = None
    await session_store.save(session)
    await state.set_state(return_state)
    await _next_step(callback.message, state, session_store, callback.from_user.id)


@router.callback_query(DataVerificationStates.PICKING_STATION, F.data.startswith("pickstationpage:"))
async def station_page(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return
    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return
    try:
        page = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return
    # Recompute stations from currently selected district.
    if session.current_editing_field.startswith("owner."):
        district_path = "owner.address.district"
    else:
        district_path = "tenant.tenanted_address.district"
    district = PayloadAccessor.get(session.payload, district_path)
    stations = station_lookup.stations_for_district(district or "")
    await callback.message.edit_reply_markup(
        reply_markup=station_keyboard(stations, page=page, include_skip=True)
    )
    await callback.answer()


@router.callback_query(DataVerificationStates.PICKING_STATION, F.data.startswith("pickstation:"))
async def pick_station(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return
    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    station = callback.data.split(":", 1)[1].strip()
    target = session.current_editing_field
    if target not in _STATION_FIELDS:
        await callback.answer("This selection is no longer active.", show_alert=True)
        return
    PayloadAccessor.set(session.payload, target, station)
    await _delete_prompt_message(callback.message, session.last_prompt_message_id)
    session.last_prompt_message_id = None
    session.current_editing_field = None

    return_state = session.edit_return_state or DataVerificationStates.CONFIRMING_FIELD.state
    session.edit_return_state = None
    session.edit_return_person = None
    await session_store.save(session)

    await callback.answer("Police station set")
    await state.set_state(return_state)
    await _next_step(callback.message, state, session_store, callback.from_user.id)


@router.callback_query(DataVerificationStates.PICKING_STATION, F.data.startswith("pickstationskip:"))
async def skip_station(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    if not callback.from_user or not callback.message:
        return
    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return
    # Keep existing value (possibly empty) and return.
    await _delete_prompt_message(callback.message, session.last_prompt_message_id)
    session.last_prompt_message_id = None
    session.current_editing_field = None
    return_state = session.edit_return_state or DataVerificationStates.CONFIRMING_FIELD.state
    session.edit_return_state = None
    session.edit_return_person = None
    await session_store.save(session)
    await callback.answer("Skipped")
    await state.set_state(return_state)
    await _next_step(callback.message, state, session_store, callback.from_user.id)


@router.callback_query(F.data.startswith("picknoop:"))
async def pick_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(DataVerificationStates.PICKING_DISTRICT)
async def district_picker_hint(message: Message) -> None:
    await _delete_message_safe(message)


@router.message(DataVerificationStates.PICKING_STATION)
async def station_picker_hint(message: Message) -> None:
    await _delete_message_safe(message)


@router.message(SubmissionStates.COMPLETE)
async def already_complete(message: Message) -> None:
    await message.answer(
        "Your form was already submitted."
    )
