from aiogram.fsm.state import State, StatesGroup


class SubmissionStates(StatesGroup):
    COMPLETE = State()
    AWAITING_PAYMENT = State()
