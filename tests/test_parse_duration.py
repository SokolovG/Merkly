from src.infrastructure.fetchers.podcast.utils import parse_duration


def test_hh_mm_ss():
    assert parse_duration("1:02:03") == 3723


def test_mm_ss():
    assert parse_duration("5:30") == 330


def test_seconds_only():
    assert parse_duration("120") == 120


def test_zero():
    assert parse_duration("0") == 0


def test_invalid_returns_zero():
    assert parse_duration("not-a-duration") == 0


def test_empty_returns_zero():
    assert parse_duration("") == 0


def test_whitespace_stripped():
    assert parse_duration("  3:30  ") == 210
