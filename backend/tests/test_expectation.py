from app.monitoring.expectation import Expectation, evaluate


def test_expected_status_without_body_rule_succeeds() -> None:
    assert evaluate(Expectation(status=200, body=None), 200, b"") is None


def test_unexpected_status_names_both_codes() -> None:
    assert evaluate(Expectation(status=200, body=None), 503, b"") == "ожидался 200, получен 503"


def test_body_containing_substring_succeeds() -> None:
    assert evaluate(Expectation(status=200, body="ok"), 200, b'{"status": "ok"}') is None


def test_body_without_substring_fails() -> None:
    assert evaluate(Expectation(status=200, body="ok"), 200, b"down") == "тело не содержит «ok»"


def test_body_substring_is_case_sensitive() -> None:
    assert evaluate(Expectation(status=200, body="OK"), 200, b"ok") == "тело не содержит «OK»"


def test_body_with_invalid_utf8_is_still_searched() -> None:
    assert evaluate(Expectation(status=200, body="ok"), 200, b"\xff\xfe ok") is None


def test_status_is_reported_before_body() -> None:
    assert evaluate(Expectation(status=200, body="ok"), 500, b"") == "ожидался 200, получен 500"
