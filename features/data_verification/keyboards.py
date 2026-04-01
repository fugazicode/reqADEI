from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder



def confirm_edit_keyboard(field_path: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Confirm", callback_data=f"confirm:{field_path}")
    kb.button(text="Edit", callback_data=f"edit:{field_path}")
    kb.adjust(2)
    return kb.as_markup()
