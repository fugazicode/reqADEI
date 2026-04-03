from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ I Agree", callback_data="consent:agree"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="consent:cancel"),
    ]])


def upload_confirm_keyboard(person: str, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"✅ Confirm ({count} image{'s' if count != 1 else ''})",
            callback_data=f"upload:confirm:{person}",
        ),
        InlineKeyboardButton(
            text="🗑 Remove",
            callback_data=f"upload:remove:{person}",
        ),
    ]])
