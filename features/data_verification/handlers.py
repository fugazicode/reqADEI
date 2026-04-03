"""Review & edit FSM handlers.

Flow:
  REVIEWING_OWNER → (confirm) → ENTERING_TENANTED_ADDRESS → REVIEWING_TENANTED_ADDR
  → (confirm) → UPLOADING_TENANT_ID → REVIEWING_TENANT → (confirm) → REVIEWING_PERM_ADDR
  → (confirm) → SUBMITTING

  Any overview can trigger an "edit" sub-flow:
  1. User taps "Edit a Field"         → show field selector keyboard
  2. User taps a field name           → show appropriate picker or ask for free-text
  3. User inputs value / taps picker  → save, refresh overview in-place, return to overview state
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from features.data_verification.keyboards import (
    cancel_edit_keyboard,
    district_picker_keyboard,
    field_selector_keyboard,
    occupation_quick_keyboard,
    occupation_search_results_keyboard,
    overview_keyboard,
    small_dropdown_keyboard,
    station_picker_keyboard,
)
from features.data_verification.labels import (
    DATE,
    DROPDOWN,
    FREE_TEXT,
    OWNER_FIELDS,
    PERM_ADDR_FIELDS,
    TENANTED_ADDR_FIELDS,
    TENANT_PERSONAL_FIELDS,
    FieldMeta,
)
from features.data_verification.overview import (
    build_owner_overview_text,
    build_perm_addr_overview_text,
    build_tenanted_addr_overview_text,
    build_tenant_personal_overview_text,
    send_perm_addr_overview,
)
from features.address_collection.states import AddressStates
from features.data_verification.states import ReviewStates
from features.identity_collection.states import IdentityStates
from features.submission.states import SubmissionStates
from features.submission.submission_worker import SubmissionWorker
from infrastructure.analytics_store import AnalyticsStore
from infrastructure.session_store import SessionStore
from shared import portal_enums
from utils.payload_accessor import PayloadAccessor
from utils.station_lookup import StationLookup

LOGGER = logging.getLogger(__name__)
router = Router(name="data_verification")

_ALL_FIELDS: dict[str, FieldMeta] = {
    **OWNER_FIELDS,
    **TENANT_PERSONAL_FIELDS,
    **TENANTED_ADDR_FIELDS,
    **PERM_ADDR_FIELDS,
}

# Ordered key lists per section — used to resolve numeric field indices from
# field_selector_keyboard callback_data (avoids Telegram's 64-byte limit).
_SECTION_FIELD_KEYS: dict[str, list[str]] = {
    "owner": list(OWNER_FIELDS.keys()),
    "tenant": list(TENANT_PERSONAL_FIELDS.keys()),
    "tenanted_addr": list(TENANTED_ADDR_FIELDS.keys()),
    "perm_addr": list(PERM_ADDR_FIELDS.keys()),
}

_SECTION_STATES = {
    "owner": ReviewStates.REVIEWING_OWNER,
    "tenant": ReviewStates.REVIEWING_TENANT,
    "tenanted_addr": ReviewStates.REVIEWING_TENANTED_ADDR,
    "perm_addr": ReviewStates.REVIEWING_PERM_ADDR,
}

_OVERVIEW_BUILDERS = {
    "owner": build_owner_overview_text,
    "tenant": build_tenant_personal_overview_text,
    "tenanted_addr": build_tenanted_addr_overview_text,
    "perm_addr": build_perm_addr_overview_text,
}


# ── Helper to refresh overview message in-place ──────────────────────────────

async def _refresh_overview(bot: Bot, chat_id: int, session, section: str) -> None:
    if not session.overview_message_id:
        return
    text = _OVERVIEW_BUILDERS[section](session)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=session.overview_message_id,
            text=text,
            reply_markup=overview_keyboard(section),
            parse_mode="Markdown",
        )
    except Exception:
        pass


async def _delete_prompt(bot: Bot, chat_id: int, session) -> None:
    if session.last_prompt_message_id:
        try:
            await bot.delete_message(chat_id, session.last_prompt_message_id)
        except Exception:
            pass
        session.last_prompt_message_id = None


# ── Overview: Confirm buttons ─────────────────────────────────────────────────

@router.callback_query(ReviewStates.REVIEWING_OWNER, F.data == "overview:confirm:owner")
async def confirm_owner(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    await state.set_state(AddressStates.ENTERING_TENANTED_ADDRESS)
    session.overview_message_id = None
    session_store.set(user_id, session)
    await callback.message.answer(  # type: ignore[union-attr]
        "📍 *Tenanted Premises Address*\n\n"
        "Please type the full address of the *rented property* (in Delhi).\n"
        "e.g. Flat 12, Block A, Green Park Extension, New Delhi – 110016",
        parse_mode="Markdown",
    )


@router.callback_query(ReviewStates.REVIEWING_TENANT, F.data == "overview:confirm:tenant")
async def confirm_tenant(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    await state.set_state(ReviewStates.REVIEWING_PERM_ADDR)
    session.overview_message_id = None
    session_store.set(user_id, session)
    await send_perm_addr_overview(callback.message, session)  # type: ignore[arg-type]


@router.callback_query(ReviewStates.REVIEWING_TENANTED_ADDR, F.data == "overview:confirm:tenanted_addr")
async def confirm_tenanted_addr(
    callback: CallbackQuery, state: FSMContext, session_store: SessionStore
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    await state.set_state(IdentityStates.UPLOADING_TENANT_ID)
    session.overview_message_id = None
    session.current_confirming_person = "tenant"
    session_store.set(user_id, session)
    await callback.message.answer(  # type: ignore[union-attr]
        "👤 *Tenant ID*\n\nNow upload a clear photo of the *tenant's Aadhaar card*.\n"
        "You may send multiple photos (front and back). Press *Confirm* when done.",
        parse_mode="Markdown",
    )


@router.callback_query(ReviewStates.REVIEWING_PERM_ADDR, F.data == "overview:confirm:perm_addr")
async def confirm_perm_addr_and_submit(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    submission_worker: SubmissionWorker,
    analytics_store: AnalyticsStore | None = None,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    missing = (
        session.payload.owner_missing_mandatory()
        + session.payload.tenant_personal_missing_mandatory()
        + session.payload.tenanted_addr_missing_mandatory()
        + session.payload.tenant_perm_addr_missing_mandatory()
    )
    if missing:
        labels = [_ALL_FIELDS[p].label if p in _ALL_FIELDS else p for p in missing]
        await callback.message.answer(  # type: ignore[union-attr]
            "⚠️ The following mandatory fields are still empty:\n"
            + "\n".join(f"• {l}" for l in labels)
            + "\n\nPlease fill them before submitting.",
        )
        return

    await state.set_state(SubmissionStates.SUBMITTING)
    session_store.set(user_id, session)
    await callback.message.answer("✅ All details confirmed. Starting portal submission…")  # type: ignore[union-attr]
    from features.submission.handlers import trigger_submission
    await trigger_submission(callback.message, session, submission_worker, analytics_store)  # type: ignore[arg-type]


# ── Overview: Edit buttons ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("overview:edit:"))
async def overview_edit(callback: CallbackQuery, state: FSMContext, session_store: SessionStore) -> None:
    await callback.answer()
    section = callback.data.split(":")[2]  # type: ignore[union-attr]
    msg = await callback.message.answer(  # type: ignore[union-attr]
        "Which field would you like to edit?",
        reply_markup=field_selector_keyboard(section),
    )
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if session:
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)


@router.callback_query(F.data.startswith("overview:back:"))
async def overview_back(callback: CallbackQuery, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await callback.answer()
    section = callback.data.split(":")[2]  # type: ignore[union-attr]
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    await _delete_prompt(bot, callback.message.chat.id, session)  # type: ignore[union-attr]
    await state.set_state(_SECTION_STATES[section])
    session.current_editing_field = None
    session_store.set(user_id, session)
    await _refresh_overview(bot, callback.message.chat.id, session, section)  # type: ignore[union-attr]


# ── Field selector: route to correct picker or free-text prompt ───────────────

@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 2)  # type: ignore[union-attr]
    section = parts[1]
    raw = parts[2]

    # Resolve numeric index → dot-path (field_selector_keyboard emits indices
    # to stay within Telegram's 64-byte callback_data limit).
    if raw.isdigit():
        keys = _SECTION_FIELD_KEYS.get(section, [])
        idx = int(raw)
        if idx >= len(keys):
            return
        field_path = keys[idx]
    else:
        field_path = raw

    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    session.current_editing_field = field_path
    session.edit_return_state = section
    session_store.set(user_id, session)

    meta = _ALL_FIELDS.get(field_path)
    if not meta:
        return

    chat_id = callback.message.chat.id  # type: ignore[union-attr]

    if meta.edit_type == FREE_TEXT or meta.edit_type == DATE:
        edit_state = {
            "owner": ReviewStates.EDITING_OWNER_FIELD,
            "tenant": ReviewStates.EDITING_TENANT_FIELD,
            "tenanted_addr": ReviewStates.EDITING_TENANTED_ADDR_FIELD,
            "perm_addr": ReviewStates.EDITING_PERM_ADDR_FIELD,
        }[section]
        await state.set_state(edit_state)
        prompt = (
            f"Enter new value for *{meta.label}*:"
            + (" (format: DD/MM/YYYY)" if meta.edit_type == DATE else "")
        )
        msg = await callback.message.answer(  # type: ignore[union-attr]
            prompt,
            reply_markup=cancel_edit_keyboard(section),
            parse_mode="Markdown",
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)
        return

    # DROPDOWN routing
    enum_key = meta.enum_key or ""

    if enum_key == "OCCUPATIONS":
        pick_state = {
            "owner": ReviewStates.PICKING_OWNER_DROPDOWN,
            "tenant": ReviewStates.PICKING_TENANT_DROPDOWN,
        }.get(section, ReviewStates.PICKING_OWNER_DROPDOWN)
        await state.set_state(pick_state)
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "Select occupation:",
            reply_markup=occupation_quick_keyboard(section),
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)

    elif enum_key == "DISTRICTS":
        pick_state = {
            "tenanted_addr": ReviewStates.PICKING_TENANTED_DISTRICT,
            "perm_addr": ReviewStates.PICKING_PERM_DISTRICT,
            "owner": ReviewStates.PICKING_TENANTED_DISTRICT,
        }.get(section, ReviewStates.PICKING_TENANTED_DISTRICT)
        await state.set_state(pick_state)
        districts = station_lookup.district_names()
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "Select district:",
            reply_markup=district_picker_keyboard(section, districts),
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)

    elif enum_key == "STATIONS":
        # Editing police station requires picking district first; remap
        # current_editing_field to the district path so district_selected saves correctly.
        _station_to_district = {
            "owner.address.police_station": "owner.address.district",
            "tenant.tenanted_address.police_station": "tenant.tenanted_address.district",
            "tenant.address.police_station": "tenant.address.district",
        }
        session.current_editing_field = _station_to_district.get(field_path, field_path)
        pick_state = {
            "tenanted_addr": ReviewStates.PICKING_TENANTED_DISTRICT,
            "perm_addr": ReviewStates.PICKING_PERM_DISTRICT,
            "owner": ReviewStates.PICKING_TENANTED_DISTRICT,
        }.get(section, ReviewStates.PICKING_TENANTED_DISTRICT)
        await state.set_state(pick_state)
        districts = station_lookup.district_names()
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "Select district first to choose a police station:",
            reply_markup=district_picker_keyboard(section, districts),
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)

    elif enum_key == "STATES":
        pick_state = {
            "owner": ReviewStates.PICKING_OWNER_DROPDOWN,
            "perm_addr": ReviewStates.PICKING_PERM_DROPDOWN,
        }.get(section, ReviewStates.PICKING_OWNER_DROPDOWN)
        await state.set_state(pick_state)
        msg = await callback.message.answer(  # type: ignore[union-attr]
            "Select state:",
            reply_markup=small_dropdown_keyboard(section, field_path, portal_enums.STATES.values),
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)

    elif enum_key in ("RELATION_TYPES", "ADDRESS_DOC_TYPES", "TENANCY_PURPOSES"):
        opt_set = getattr(portal_enums, enum_key)
        pick_state = {
            "owner": ReviewStates.PICKING_OWNER_DROPDOWN,
            "tenant": ReviewStates.PICKING_TENANT_DROPDOWN,
        }.get(section, ReviewStates.PICKING_OWNER_DROPDOWN)
        await state.set_state(pick_state)
        msg = await callback.message.answer(  # type: ignore[union-attr]
            f"Select {meta.label}:",
            reply_markup=small_dropdown_keyboard(section, field_path, opt_set.values),
        )
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)


# ── Free-text edit handlers ───────────────────────────────────────────────────

async def _handle_free_text_edit(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    section: str,
) -> None:
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session or not session.current_editing_field:
        return
    field_path = session.current_editing_field
    PayloadAccessor.set(session.payload, field_path, message.text.strip())  # type: ignore[union-attr]
    await _delete_prompt(bot, message.chat.id, session)
    await message.delete()
    session.current_editing_field = None
    session_store.set(user_id, session)
    await state.set_state(_SECTION_STATES[section])
    await _refresh_overview(bot, message.chat.id, session, section)


@router.message(ReviewStates.EDITING_OWNER_FIELD)
async def free_text_owner(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_free_text_edit(message, state, session_store, bot, "owner")


@router.message(ReviewStates.EDITING_TENANT_FIELD)
async def free_text_tenant(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_free_text_edit(message, state, session_store, bot, "tenant")


@router.message(ReviewStates.EDITING_TENANTED_ADDR_FIELD)
async def free_text_tenanted(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_free_text_edit(message, state, session_store, bot, "tenanted_addr")


@router.message(ReviewStates.EDITING_PERM_ADDR_FIELD)
async def free_text_perm(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_free_text_edit(message, state, session_store, bot, "perm_addr")


# ── Occupation picker ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("picker:occ:"))
async def occupation_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 3)  # type: ignore[union-attr]
    section = parts[2]
    occupation = parts[3]
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session or not session.current_editing_field:
        return
    PayloadAccessor.set(session.payload, session.current_editing_field, occupation)
    await _delete_prompt(bot, callback.message.chat.id, session)  # type: ignore[union-attr]
    session.current_editing_field = None
    session_store.set(user_id, session)
    await state.set_state(_SECTION_STATES[section])
    await _refresh_overview(bot, callback.message.chat.id, session, section)  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("picker:occ_search:"))
async def occupation_search_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    await callback.answer()
    section = callback.data.split(":")[2]  # type: ignore[union-attr]
    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if session:
        pick_state = {
            "owner": ReviewStates.PICKING_OWNER_DROPDOWN,
            "tenant": ReviewStates.PICKING_TENANT_DROPDOWN,
        }.get(section, ReviewStates.PICKING_OWNER_DROPDOWN)
        await state.set_state(pick_state)
        msg = await callback.message.answer("Type part of the occupation name:")  # type: ignore[union-attr]
        session.last_prompt_message_id = msg.message_id
        session_store.set(user_id, session)


@router.callback_query(F.data.startswith("picker:occ_quick:"))
async def occupation_back_to_quick(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
) -> None:
    await callback.answer()
    section = callback.data.split(":")[2]  # type: ignore[union-attr]
    await callback.message.edit_reply_markup(reply_markup=occupation_quick_keyboard(section))  # type: ignore[union-attr]


async def _handle_occupation_search(
    message: Message,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
    section: str,
) -> None:
    from shared.portal_enums import OCCUPATIONS
    query = message.text.strip().upper()  # type: ignore[union-attr]
    matches = [v for v in OCCUPATIONS.values if query in v.upper()]
    user_id = message.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    await _delete_prompt(bot, message.chat.id, session)
    await message.delete()
    msg = await message.answer(
        f"Results for '{message.text}':",
        reply_markup=occupation_search_results_keyboard(section, matches),
    )
    session.last_prompt_message_id = msg.message_id
    session_store.set(user_id, session)


@router.message(ReviewStates.PICKING_OWNER_DROPDOWN)
async def occ_search_owner(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_occupation_search(message, state, session_store, bot, "owner")


@router.message(ReviewStates.PICKING_TENANT_DROPDOWN)
async def occ_search_tenant(message: Message, state: FSMContext, session_store: SessionStore, bot: Bot) -> None:
    await _handle_occupation_search(message, state, session_store, bot, "tenant")


# ── District / station pickers ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("picker:dist_page:"))
async def district_page(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
) -> None:
    await callback.answer()
    parts = callback.data.split(":")  # type: ignore[union-attr]
    section = parts[2]
    page = int(parts[3])
    districts = station_lookup.district_names()
    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=district_picker_keyboard(section, districts, page)
    )


@router.callback_query(F.data.startswith("picker:district:"))
async def district_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    station_lookup: StationLookup,
    bot: Bot,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 3)  # type: ignore[union-attr]
    section = parts[2]
    district_name = parts[3]

    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    # Persist district (may be owner, tenanted, or perm address district)
    district_path = session.current_editing_field or {
        "owner": "owner.address.district",
        "tenanted_addr": "tenant.tenanted_address.district",
        "perm_addr": "tenant.address.district",
    }.get(section, "tenant.address.district")
    PayloadAccessor.set(session.payload, district_path, district_name)

    # Now ask for station
    station_state = {
        "tenanted_addr": ReviewStates.PICKING_TENANTED_STATION,
        "perm_addr": ReviewStates.PICKING_PERM_STATION,
        "owner": ReviewStates.PICKING_TENANTED_STATION,
    }.get(section, ReviewStates.PICKING_TENANTED_STATION)
    await state.set_state(station_state)

    stations = station_lookup.stations_for_district(district_name)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"District: *{district_name.title()}*\n\nNow select the police station:",
        reply_markup=station_picker_keyboard(section, district_name, stations),
        parse_mode="Markdown",
    )
    session_store.set(user_id, session)


@router.callback_query(F.data.startswith("picker:district_reselect:"))
async def district_reselect(
    callback: CallbackQuery,
    state: FSMContext,
    station_lookup: StationLookup,
) -> None:
    await callback.answer()
    section = callback.data.split(":")[2]  # type: ignore[union-attr]
    pick_state = {
        "tenanted_addr": ReviewStates.PICKING_TENANTED_DISTRICT,
        "perm_addr": ReviewStates.PICKING_PERM_DISTRICT,
    }.get(section, ReviewStates.PICKING_TENANTED_DISTRICT)
    await state.set_state(pick_state)
    districts = station_lookup.district_names()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "Select district:",
        reply_markup=district_picker_keyboard(section, districts),
    )


@router.callback_query(F.data.startswith("picker:stn_page:"))
async def station_page(
    callback: CallbackQuery,
    station_lookup: StationLookup,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 4)  # type: ignore[union-attr]
    section = parts[2]
    district = parts[3]
    page = int(parts[4])
    stations = station_lookup.stations_for_district(district)
    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=station_picker_keyboard(section, district, stations, page)
    )


@router.callback_query(F.data.startswith("picker:station:"))
async def station_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 4)  # type: ignore[union-attr]
    section = parts[2]
    district = parts[3]
    station_name = parts[4]

    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return

    station_path = {
        "tenanted_addr": "tenant.tenanted_address.police_station",
        "perm_addr": "tenant.address.police_station",
        "owner": "owner.address.police_station",
    }.get(section, "tenant.address.police_station")
    PayloadAccessor.set(session.payload, station_path, station_name)
    session.current_editing_field = None
    session_store.set(user_id, session)
    await state.set_state(_SECTION_STATES[section])
    await _delete_prompt(bot, callback.message.chat.id, session)  # type: ignore[union-attr]
    await _refresh_overview(bot, callback.message.chat.id, session, section)  # type: ignore[union-attr]


# ── Small dropdown (relation type, doc type, tenancy purpose) ─────────────────

@router.callback_query(F.data.startswith("picker:small:"))
async def small_dropdown_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_store: SessionStore,
    bot: Bot,
) -> None:
    await callback.answer()
    parts = callback.data.split(":", 4)  # type: ignore[union-attr]
    section = parts[2]
    field_path = parts[3]
    value = parts[4]

    user_id = callback.from_user.id
    session = session_store.get(user_id)
    if not session:
        return
    PayloadAccessor.set(session.payload, field_path, value)
    session.current_editing_field = None
    session_store.set(user_id, session)
    await state.set_state(_SECTION_STATES[section])
    await _delete_prompt(bot, callback.message.chat.id, session)  # type: ignore[union-attr]
    await _refresh_overview(bot, callback.message.chat.id, session, section)  # type: ignore[union-attr]
