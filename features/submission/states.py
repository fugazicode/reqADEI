from aiogram.fsm.state import State, StatesGroup


class SubmissionStates(StatesGroup):
    SUBMITTING = State()
    DONE = State()
