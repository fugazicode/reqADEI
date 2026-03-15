from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder



def owner_occupation_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for occupation in ["ACADEMICIAN", "BANK EMPLOYEE", "BUSINESS", "GOVERNMENT SERVICE", "PRIVATE SERVICE", "SELF EMPLOYED"]:
        kb.button(text=occupation, callback_data=f"occupation:{occupation}")
    kb.adjust(2)
    return kb.as_markup()



def tenant_purpose_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for purpose in ["Commercial", "Residential"]:
        kb.button(text=purpose, callback_data=f"purpose:{purpose}")
    kb.adjust(2)
    return kb.as_markup()



def district_station_keyboard(stations: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for station in stations:
        kb.button(text=station, callback_data=f"station:{station}")
    kb.button(text="Skip", callback_data="station:__skip__")
    kb.adjust(1)
    return kb.as_markup()
