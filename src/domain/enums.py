from enum import StrEnum


class Level(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"


class Goal(StrEnum):
    TRAVEL = "travel"
    WORK = "work"
    CONVERSATION = "conversation"
    GENERAL = "general"
    STUDY = "study"


class WordType(StrEnum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    PHRASE = "phrase"


class Language(StrEnum):
    DE = "de"
    EN = "en"
    ES = "es"
    FR = "fr"
    IT = "it"
    PT = "pt"
    RU = "ru"
    UK = "uk"
