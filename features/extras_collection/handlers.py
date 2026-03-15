from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from features.data_verification.confirmation_flow import ConfirmationFlow
from features.data_verification.states import DataVerificationStates
from features.extras_collection.keyboards import district_station_keyboard, tenant_purpose_keyboard
from features.extras_collection.states import ExtrasCollectionStates
from features.identity_collection.keyboards import done_upload_keyboard
from features.identity_collection.states import IdentityCollectionStates
from infrastructure.groq_parser import GroqParser, GroqParsingError
from infrastructure.session_store import SessionStore
from utils.payload_accessor import PayloadAccessor
from utils.station_lookup import StationLookup

router = Router(name=__name__)


@router.callback_query(ExtrasCollectionStates.OWNER_OCCUPATION, F.data.startswith("occupation:"))
async def set_owner_occupation(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    occupation = callback.data.split(":", 1)[1]
    PayloadAccessor.set(session.payload, "owner.occupation", occupation)

    await session_store.save(session)
    await state.set_state(IdentityCollectionStates.TENANT_UPLOAD)
    await callback.message.answer(
        "Upload tenant ID images, then tap Done.",
        reply_markup=done_upload_keyboard(),
    )
    await callback.answer()


@router.callback_query(ExtrasCollectionStates.TENANT_EXTRAS, F.data.startswith("purpose:"))
async def set_tenant_purpose(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    purpose = callback.data.split(":", 1)[1]
    PayloadAccessor.set(session.payload, "tenant.purpose_of_tenancy", purpose)
    await session_store.save(session)

    await state.set_state(ExtrasCollectionStates.TENANTED_ADDRESS_INPUT)
    await callback.message.answer("Please type full tenanted address.")
    await callback.answer()


@router.message(ExtrasCollectionStates.TENANT_EXTRAS)
async def tenant_extras_hint(message: Message) -> None:
    await message.answer("Select tenancy purpose.", reply_markup=tenant_purpose_keyboard())


@router.message(ExtrasCollectionStates.TENANTED_ADDRESS_INPUT)
async def receive_tenanted_address(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    groq_parser: GroqParser,
    station_lookup: StationLookup,
) -> None:
    if not message.from_user or not message.text:
        return

    session = await session_store.get(message.from_user.id)
    if session is None:
        await message.answer("Session expired. Send /start.")
        return

    try:
        parsed = await groq_parser.parse(message.text, "address_parsing")
    except GroqParsingError:
        await message.answer("Address parsing failed. Please re-enter the tenanted address.")
        return

    for key, value in parsed.items():
        PayloadAccessor.set(session.payload, f"tenant.tenanted_address.{key}", value)

    if not PayloadAccessor.get(session.payload, "tenant.tenanted_address.country"):
        PayloadAccessor.set(session.payload, "tenant.tenanted_address.country", "India")
    if not PayloadAccessor.get(session.payload, "tenant.tenanted_address.state"):
        PayloadAccessor.set(session.payload, "tenant.tenanted_address.state", "Delhi")

    colony = PayloadAccessor.get(session.payload, "tenant.tenanted_address.colony_locality_area")
    district = PayloadAccessor.get(session.payload, "tenant.tenanted_address.district")
    suggested_district, suggested_station = station_lookup.suggest(colony, district)

    if suggested_district and not district:
        PayloadAccessor.set(session.payload, "tenant.tenanted_address.district", suggested_district)

    stations_in_district: list[str] = []
    if suggested_station:
        PayloadAccessor.set(session.payload, "tenant.tenanted_address.police_station", suggested_station)
    elif suggested_district:
        stations_in_district = station_lookup.stations_for_district(suggested_district)

    session.confirmation_queue = [
        "tenant.tenanted_address.house_no",
        "tenant.tenanted_address.street_name",
        "tenant.tenanted_address.colony_locality_area",
        "tenant.tenanted_address.village_town_city",
        "tenant.tenanted_address.tehsil_block_mandal",
        "tenant.tenanted_address.district",
        "tenant.tenanted_address.police_station",
        "tenant.tenanted_address.pincode",
    ]

    session.next_stage = "submission"
    await session_store.save(session)
    await state.set_state(ExtrasCollectionStates.TENANTED_ADDRESS_CONFIRM)

    if stations_in_district:
        await message.answer(
            "Select police station from suggested district, or tap Skip to continue editing fields.",
            reply_markup=district_station_keyboard(stations_in_district),
        )
        return

    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(message, state)
    if result == "missing":
        await state.update_data(return_state=(await state.get_state()))
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
    await session_store.save(session)


@router.callback_query(ExtrasCollectionStates.TENANTED_ADDRESS_CONFIRM, F.data.startswith("station:"))
async def pick_station(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    if not callback.from_user or not callback.message or not callback.data:
        return

    session = await session_store.get(callback.from_user.id)
    if session is None:
        await callback.answer("Session expired. Send /start.", show_alert=True)
        return

    station = callback.data.split(":", 1)[1]
    if station != "__skip__":
        PayloadAccessor.set(session.payload, "tenant.tenanted_address.police_station", station)

        station_field = "tenant.tenanted_address.police_station"
        if station_field in session.confirmation_queue:
            session.confirmation_queue.remove(station_field)

    await session_store.save(session)
    if station != "__skip__":
        await callback.message.answer(f"Police station set to: {station}")
    else:
        await callback.message.answer("Continuing without pre-selecting police station.")

    flow = ConfirmationFlow(session)
    result = await flow.show_next_field(callback.message, state)
    if result == "missing":
        await state.update_data(return_state=(await state.get_state()))
        await state.set_state(DataVerificationStates.AWAITING_EDIT_INPUT)
    await session_store.save(session)
    await callback.answer()


@router.message(ExtrasCollectionStates.TENANTED_ADDRESS_CONFIRM)
async def tenanted_address_confirm_hint(message: Message) -> None:
    await message.answer("Please use the buttons to confirm or edit the address fields.")
