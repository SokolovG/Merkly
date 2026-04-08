from src.application.listening_service import ListeningAgent

parse = ListeningAgent._parse_questions


def test_happy_path_numbered_dot():
    text = "1. What is the main topic?\n2. Who is the speaker?\n3. What conclusion was drawn?"
    assert parse(text, 3) == [
        "What is the main topic?",
        "Who is the speaker?",
        "What conclusion was drawn?",
    ]


def test_happy_path_numbered_paren():
    text = "1) First question\n2) Second question"
    assert parse(text, 2) == ["First question", "Second question"]


def test_truncates_to_count():
    text = "1. Q1\n2. Q2\n3. Q3\n4. Q4"
    result = parse(text, 2)
    assert len(result) == 2
    assert result == ["Q1", "Q2"]


def test_fewer_matches_than_count():
    text = "1. Only one question"
    result = parse(text, 3)
    assert result == ["Only one question"]


def test_empty_text_returns_fallback():
    result = parse("", 3)
    assert result == ["What did you understand from the podcast?"]


def test_no_matches_returns_fallback():
    result = parse("Some random text without numbered questions", 3)
    assert result == ["What did you understand from the podcast?"]


def test_strips_whitespace():
    text = "1.   Padded question   \n2.  Another one  "
    assert parse(text, 2) == ["Padded question", "Another one"]


def test_ignores_blank_lines():
    text = "\n1. First\n\n2. Second\n"
    assert parse(text, 2) == ["First", "Second"]
