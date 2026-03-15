from aiogram.fsm.state import State, StatesGroup


class IdentityCollectionStates(StatesGroup):
    AWAITING_CONSENT = State()
    OWNER_UPLOAD = State()
    TENANT_UPLOAD = State()
