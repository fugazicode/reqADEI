from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ I Agree", callback_data="consent:agree"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="consent:cancel"),
    ]])
