from aiogram.fsm.state import State, StatesGroup


class ReviewStates(StatesGroup):
    # Phase 1 — Owner overview: show all owner fields at once
    REVIEWING_OWNER = State()
    # Sub-state: user typed free-text value for an owner field
    EDITING_OWNER_FIELD = State()
    # Sub-state: user is in a picker for owner dropdown field
    PICKING_OWNER_DROPDOWN = State()

    # Phase 2 — Tenant personal overview
    REVIEWING_TENANT = State()
    EDITING_TENANT_FIELD = State()
    PICKING_TENANT_DROPDOWN = State()

    # Phase 3 — Tenant tenanted premises address (always Delhi)
    REVIEWING_TENANTED_ADDR = State()
    EDITING_TENANTED_ADDR_FIELD = State()
    PICKING_TENANTED_DISTRICT = State()
    PICKING_TENANTED_STATION = State()

    # Phase 4 — Tenant permanent address (extracted from Aadhaar)
    REVIEWING_PERM_ADDR = State()
    EDITING_PERM_ADDR_FIELD = State()
    PICKING_PERM_DISTRICT = State()
    PICKING_PERM_STATION = State()
