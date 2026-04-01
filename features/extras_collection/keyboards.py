from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shared.portal_enums import OWNER_OCCUPATIONS, TENANCY_PURPOSES

DELHI_DISTRICTS: tuple[str, ...] = (
    "CENTRAL",
    "DWARKA",
    "EAST",
    "IGI AIRPORT",
    "NEW DELHI",
    "NORTH",
    "NORTH EAST",
    "NORTH WEST",
    "OUTER DISTRICT",
    "OUTER NORTH",
    "ROHINI",
    "SHAHDARA",
    "SOUTH",
    "SOUTH WEST",
    "SOUTH-EAST",
    "WEST",
)


def _paginate(items: list[str], page: int, page_size: int) -> tuple[list[str], int]:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    safe_page = max(0, min(page, total_pages - 1))
    start = safe_page * page_size
    end = start + page_size
    return items[start:end], total_pages


def district_keyboard(*, page: int = 0, page_size: int = 12) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = list(DELHI_DISTRICTS)
    page_items, total_pages = _paginate(items, page, page_size)
    for district in page_items:
        kb.button(text=district, callback_data=f"pickdistrict:{district}")
    if total_pages > 1:
        if page > 0:
            kb.button(text="⬅ Prev", callback_data=f"pickdistrictpage:{page-1}")
        kb.button(text=f"{page+1}/{total_pages}", callback_data="picknoop:1")
        if page + 1 < total_pages:
            kb.button(text="Next ➡", callback_data=f"pickdistrictpage:{page+1}")
    kb.adjust(2)
    return kb.as_markup()


def station_keyboard(
    stations: list[str],
    *,
    page: int = 0,
    page_size: int = 12,
    include_skip: bool = True,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    items = sorted({s.strip() for s in stations if s and s.strip()})
    page_items, total_pages = _paginate(items, page, page_size)
    for station in page_items:
        kb.button(text=station, callback_data=f"pickstation:{station}")
    if include_skip:
        kb.button(text="Skip", callback_data="pickstationskip:1")
    if total_pages > 1:
        if page > 0:
            kb.button(text="⬅ Prev", callback_data=f"pickstationpage:{page-1}")
        kb.button(text=f"{page+1}/{total_pages}", callback_data="picknoop:1")
        if page + 1 < total_pages:
            kb.button(text="Next ➡", callback_data=f"pickstationpage:{page+1}")
    kb.adjust(1)
    return kb.as_markup()


def owner_occupation_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for occupation in OWNER_OCCUPATIONS.values:
        kb.button(text=occupation, callback_data=f"occupation:{occupation}")
    kb.adjust(2)
    return kb.as_markup()



def tenant_purpose_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for purpose in TENANCY_PURPOSES.values:
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
