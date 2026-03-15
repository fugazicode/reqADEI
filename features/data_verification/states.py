from aiogram.fsm.state import State, StatesGroup


class DataVerificationStates(StatesGroup):
    CONFIRMING_FIELD = State()
    AWAITING_EDIT_INPUT = State()
