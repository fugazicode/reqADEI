"""Tenant tenanted premises address collection.

User types free-text address → Groq parses it into structured fields
→ session.payload.tenant.tenanted_address is populated
→ state moves to REVIEWING_TENANTED_ADDR overview.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from features.address_collection.states import AddressStates
from features.data_verification.overview import send_tenanted_addr_overview
from features.data_verification.states import ReviewStates
from infrastructure.groq_parser import GroqParser, GroqParsingError
from infrastructure.session_store import SessionStore
from shared.models.form_payload import AddressData
from utils.payload_accessor import PayloadAccessor
from utils.station_autopick import auto_pick_station
from utils.station_lookup import StationLookup

LOGGER = logging.getLogger(__name__)
router = Router(name="address_collection")

_EXAMPLE = (
    "e.g. Flat 12, Block A, Green Park Extension, New Delhi - 110016"
)


@router.message(AddressStates.ENTERING_TENANTED_ADDRESS)
async def tenanted_address_received(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    groq_parser: GroqParser,
    station_lookup: StationLookup,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        await message.answer("Session expired. Please send /start.")
        return

    raw_text = (message.text or "").strip()
    if not raw_text:
        await message.answer(f"Please type the tenanted premises address.\n{_EXAMPLE}")
        return

    status_msg = await message.answer("⏳ Parsing address…")

    try:
        parsed = await groq_parser.parse(raw_text, "address_parsing")
    except GroqParsingError as exc:
        LOGGER.warning("Address parsing failed: %s", exc)
        parsed = {}

    await status_msg.delete()

    addr = session.payload.tenant.tenanted_address if session.payload.tenant else None  # type: ignore[union-attr]
    if addr is None:
        if session.payload.tenant is None:
            from shared.models.form_payload import TenantData
            session.payload.tenant = TenantData()
        session.payload.tenant.tenanted_address = AddressData()
        addr = session.payload.tenant.tenanted_address

    field_map = {
        "house_no": "house_no",
        "street_name": "street_name",
        "colony_locality_area": "colony_locality_area",
        "village_town_city": "village_town_city",
        "district": "district",
        "police_station": "police_station",
        "pincode": "pincode",
        "state": "state",
    }
    for json_key, attr in field_map.items():
        val = parsed.get(json_key)
        if val:
            setattr(addr, attr, str(val))

    # Tenanted premises are always in Delhi
    addr.state = "DELHI"
    addr.country = "INDIA"

    if addr.district and not addr.police_station:
        stations = station_lookup.stations_for_district(str(addr.district))
        picked = auto_pick_station(stations)
        if picked:
            addr.police_station = picked

    session_store.set(user_id, session)
    await state.set_state(ReviewStates.REVIEWING_TENANTED_ADDR)
    await send_tenanted_addr_overview(message, session)
