from aiogram.fsm.state import State, StatesGroup


class IdentityCollectionStates(StatesGroup):
    OWNER_UPLOAD = State()
    TENANT_UPLOAD = State()
