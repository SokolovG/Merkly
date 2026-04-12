from aiogram.fsm.state import State, StatesGroup


class OnboardingSG(StatesGroup):
    target_lang = State()
    level = State()
    goal = State()
    native_lang = State()
    reminder = State()
    reminder_time = State()
    utc_offset = State()
    vocab_count = State()
    strategy = State()
    confirm = State()


class SessionSG(StatesGroup):
    reading = State()  # user reads the article + questions
    answering_1 = State()
    answering_2 = State()
    answering_3 = State()
    reviewing = State()  # agent is reviewing
    done = State()


class BugSG(StatesGroup):
    reporting = State()
