from datetime import UTC, datetime, timedelta

from app.models import Alert, AlertKind, HttpMethod, Monitor
from app.notifications.alerts import alert_text

DOWN_AT = datetime(2026, 11, 14, 9, 30, 5, tzinfo=UTC)


def monitor(**overrides: object) -> Monitor:
    fields = {"name": "API", "url": "https://example.com/health", "method": HttpMethod.HEAD}
    return Monitor(**(fields | overrides))


def down(reason: str = "ожидался 200, получен 503") -> Alert:
    return Alert(kind=AlertKind.DOWN, reason=reason, down_since=DOWN_AT, created_at=DOWN_AT)


def test_down_alert_names_monitor_request_reason_and_time() -> None:
    text = alert_text(monitor(), down(), first_attempt_at=None)

    assert text == (
        "🔴 <b>API</b> упал\n"
        "HEAD https://example.com/health\n"
        "Причина: ожидался 200, получен 503\n"
        "Время: 14.11.2026 09:30:05 UTC"
    )


def test_recovery_alert_shows_downtime_until_recovery() -> None:
    recovered_at = DOWN_AT + timedelta(hours=1, minutes=5, seconds=12)
    alert = Alert(kind=AlertKind.RECOVERED, down_since=DOWN_AT, created_at=recovered_at)

    text = alert_text(monitor(), alert, first_attempt_at=None)

    assert text == "🟢 <b>API</b> восстановился\nhttps://example.com/health\nПростой: 1 ч 5 мин"


def test_user_text_is_html_escaped() -> None:
    text = alert_text(
        monitor(name="<API>", url="https://example.com/?a=1&b=2"),
        down("<x>"),
        first_attempt_at=None,
    )

    assert "&lt;API&gt;" in text
    assert "a=1&amp;b=2" in text
    assert "&lt;x&gt;" in text


def test_retry_says_when_first_attempt_failed() -> None:
    first_attempt_at = DOWN_AT + timedelta(seconds=2)

    text = alert_text(monitor(), down(), first_attempt_at=first_attempt_at)

    assert text.endswith("\n⚠️ Повторная попытка: первая не удалась 14.11.2026 09:30:07 UTC")
