from aiogram.fsm.state import State, StatesGroup


class ExtrasCollectionStates(StatesGroup):
    OWNER_OCCUPATION = State()
    TENANT_EXTRAS = State()
    TENANTED_ADDRESS_INPUT = State()
    TENANTED_ADDRESS_CONFIRM = State()
