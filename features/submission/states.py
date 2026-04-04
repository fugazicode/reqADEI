from aiogram.fsm.state import State, StatesGroup


class SubmissionStates(StatesGroup):
    DONE = State()
