from aiogram.fsm.state import State, StatesGroup


class AddressStates(StatesGroup):
    ENTERING_TENANTED_ADDRESS = State()
