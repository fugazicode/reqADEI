"""All inline keyboards for the review/edit flow."""
from __future__ import annotations

import math
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from features.data_verification.labels import (
    OWNER_FIELDS,
    PERM_ADDR_FIELDS,
    TENANTED_ADDR_FIELDS,
    TENANT_PERSONAL_FIELDS,
    FieldMeta,
)

_SECTION_FIELDS: dict[str, dict[str, FieldMeta]] = {
    "owner": OWNER_FIELDS,
    "tenant": TENANT_PERSONAL_FIELDS,
    "tenanted_addr": TENANTED_ADDR_FIELDS,
    "perm_addr": PERM_ADDR_FIELDS,
}

_CONFIRM_LABELS: dict[str, str] = {
    "owner": "✅ Confirm Owner → Tenant Details",
    "tenant": "✅ Confirm Tenant → Tenanted Address",
    "tenanted_addr": "✅ Confirm Tenanted Address → Permanent Address",
    "perm_addr": "✅ Confirm & Submit",
}


def overview_keyboard(section: str) -> InlineKeyboardMarkup:
    """Overview keyboard: Edit Fields button + Confirm/Next button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit a Field", callback_data=f"overview:edit:{section}")],
        [InlineKeyboardButton(text=_CONFIRM_LABELS[section], callback_data=f"overview:confirm:{section}")],
    ])


def field_selector_keyboard(section: str) -> InlineKeyboardMarkup:
    """Show all fields in the section as buttons so user can pick which to edit."""
    fields = _SECTION_FIELDS.get(section, {})
    buttons: list[list[InlineKeyboardButton]] = []
    for path, meta in fields.items():
        buttons.append([
            InlineKeyboardButton(
                text=meta.label,
                callback_data=f"edit_field:{section}:{path}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="← Back to Overview", callback_data=f"overview:back:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Occupation picker — two-tier ────────────────────────────────────────────

_COMMON_OCCUPATIONS = [
    "SERVICE",
    "BUSINESS",
    "HOUSEWIFE",
    "STUDENT",
    "TEACHER",
    "GOVT. OFFICIAL NON-GAZETTED",
    "DOCTOR",
    "ENGINEER",
    "RETIRED EMPLOYEE",
    "LABOURER",
]

_RETURN_CB = "picker:occ:done"


def occupation_quick_keyboard(section: str) -> InlineKeyboardMarkup:
    """Quick-tap common occupations + a search option."""
    buttons: list[list[InlineKeyboardButton]] = []
    for occ in _COMMON_OCCUPATIONS:
        buttons.append([InlineKeyboardButton(
            text=occ.title(),
            callback_data=f"picker:occ:{section}:{occ}",
        )])
    buttons.append([InlineKeyboardButton(text="🔍 Search occupation…", callback_data=f"picker:occ_search:{section}")])
    buttons.append([InlineKeyboardButton(text="← Back", callback_data=f"overview:back:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def occupation_search_results_keyboard(section: str, results: list[str]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for occ in results[:10]:
        buttons.append([InlineKeyboardButton(
            text=occ.title(),
            callback_data=f"picker:occ:{section}:{occ}",
        )])
    if not results:
        buttons.append([InlineKeyboardButton(text="No matches found", callback_data="noop")])
    buttons.append([InlineKeyboardButton(text="← Back to list", callback_data=f"picker:occ_quick:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── District / station pickers ───────────────────────────────────────────────

def district_picker_keyboard(section: str, districts: list[str], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = max(1, math.ceil(len(districts) / per_page))
    start = page * per_page
    chunk = districts[start: start + per_page]

    buttons: list[list[InlineKeyboardButton]] = []
    for name in chunk:
        buttons.append([InlineKeyboardButton(
            text=name.title(),
            callback_data=f"picker:district:{section}:{name}",
        )])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"picker:dist_page:{section}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"picker:dist_page:{section}:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="← Back", callback_data=f"overview:back:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def station_picker_keyboard(section: str, district: str, stations: list[str], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = max(1, math.ceil(len(stations) / per_page))
    start = page * per_page
    chunk = stations[start: start + per_page]

    buttons: list[list[InlineKeyboardButton]] = []
    for name in chunk:
        buttons.append([InlineKeyboardButton(
            text=name.title(),
            callback_data=f"picker:station:{section}:{district}:{name}",
        )])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"picker:stn_page:{section}:{district}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"picker:stn_page:{section}:{district}:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="← Pick District Again", callback_data=f"picker:district_reselect:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Generic small-list dropdown ──────────────────────────────────────────────

def small_dropdown_keyboard(section: str, field_path: str, options: tuple[str, ...]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for opt in options:
        buttons.append([InlineKeyboardButton(
            text=opt,
            callback_data=f"picker:small:{section}:{field_path}:{opt}",
        )])
    buttons.append([InlineKeyboardButton(text="← Back", callback_data=f"overview:back:{section}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Cancel / confirm edit helpers ────────────────────────────────────────────

def cancel_edit_keyboard(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Cancel", callback_data=f"overview:back:{section}"),
    ]])
