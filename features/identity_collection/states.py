from aiogram.fsm.state import State, StatesGroup


class IdentityStates(StatesGroup):
    AWAITING_CONSENT = State()
    UPLOADING_OWNER_ID = State()
    UPLOADING_TENANT_ID = State()
