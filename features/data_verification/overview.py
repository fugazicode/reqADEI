"""Build overview messages and send/update them in-place."""
from __future__ import annotations

from aiogram.types import Message

from features.data_verification.keyboards import (
    overview_keyboard,
)
from features.data_verification.labels import (
    OWNER_FIELDS,
    OWNER_MANDATORY,
    PERM_ADDR_FIELDS,
    PERM_ADDR_MANDATORY,
    TENANTED_ADDR_FIELDS,
    TENANTED_ADDR_MANDATORY,
    TENANT_PERSONAL_FIELDS,
    TENANT_PERSONAL_MANDATORY,
)
from shared.models.session import FormSession
from utils.payload_accessor import PayloadAccessor

_MISSING = "—"


def _value(session: FormSession, field_path: str) -> str:
    v = PayloadAccessor.get(session.payload, field_path)
    return str(v) if v is not None else _MISSING


def _field_line(session: FormSession, path: str, label: str, mandatory_set: set[str]) -> str:
    v = _value(session, path)
    star = "⚠️" if (path in mandatory_set and v == _MISSING) else "  "
    return f"{star} *{label}:* {v}"


def build_owner_overview_text(session: FormSession) -> str:
    lines = ["*👤 Owner Details*\n"]
    for path, meta in OWNER_FIELDS.items():
        lines.append(_field_line(session, path, meta.label, OWNER_MANDATORY))
    lines.append("\n⚠️ = mandatory field not yet filled")
    return "\n".join(lines)


def build_tenant_personal_overview_text(session: FormSession) -> str:
    lines = ["*👥 Tenant Personal Details*\n"]
    for path, meta in TENANT_PERSONAL_FIELDS.items():
        lines.append(_field_line(session, path, meta.label, TENANT_PERSONAL_MANDATORY))
    lines.append("\n⚠️ = mandatory field not yet filled")
    return "\n".join(lines)


def build_tenanted_addr_overview_text(session: FormSession) -> str:
    lines = ["*🏠 Tenant Tenanted Premises Address (Delhi)*\n"]
    for path, meta in TENANTED_ADDR_FIELDS.items():
        lines.append(_field_line(session, path, meta.label, TENANTED_ADDR_MANDATORY))
    lines.append("\n⚠️ = mandatory field not yet filled")
    return "\n".join(lines)


def build_perm_addr_overview_text(session: FormSession) -> str:
    lines = ["*🏡 Tenant Permanent Address*\n"]
    for path, meta in PERM_ADDR_FIELDS.items():
        lines.append(_field_line(session, path, meta.label, PERM_ADDR_MANDATORY))
    lines.append("\n⚠️ = mandatory field not yet filled")
    return "\n".join(lines)


async def send_owner_overview(message: Message, session: FormSession) -> None:
    text = build_owner_overview_text(session)
    keyboard = overview_keyboard("owner")
    sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    session.overview_message_id = sent.message_id


async def send_tenant_personal_overview(message: Message, session: FormSession) -> None:
    text = build_tenant_personal_overview_text(session)
    keyboard = overview_keyboard("tenant")
    sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    session.overview_message_id = sent.message_id


async def send_tenanted_addr_overview(message: Message, session: FormSession) -> None:
    text = build_tenanted_addr_overview_text(session)
    keyboard = overview_keyboard("tenanted_addr")
    sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    session.overview_message_id = sent.message_id


async def send_perm_addr_overview(message: Message, session: FormSession) -> None:
    text = build_perm_addr_overview_text(session)
    keyboard = overview_keyboard("perm_addr")
    sent = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
    session.overview_message_id = sent.message_id
