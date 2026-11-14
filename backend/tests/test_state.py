import pytest

from app.models import MonitorState
from app.monitoring.state import AlertKind, transition


@pytest.mark.parametrize(
    ("current", "success", "expected"),
    [
        # Первая проверка: о падении сообщаем, о «работает» — нет.
        (MonitorState.UNKNOWN, True, (MonitorState.UP, None)),
        (MonitorState.UNKNOWN, False, (MonitorState.DOWN, AlertKind.DOWN)),
        # Смена между «работает» и «упал» — после одной проверки и с Оповещением.
        (MonitorState.UP, False, (MonitorState.DOWN, AlertKind.DOWN)),
        (MonitorState.DOWN, True, (MonitorState.UP, AlertKind.RECOVERED)),
        # Без смены состояния — без Оповещения.
        (MonitorState.UP, True, (MonitorState.UP, None)),
        (MonitorState.DOWN, False, (MonitorState.DOWN, None)),
    ],
)
def test_transition(
    current: MonitorState, success: bool, expected: tuple[MonitorState, AlertKind | None]
) -> None:
    assert transition(current, success) == expected


def test_paused_monitor_has_no_transition() -> None:
    with pytest.raises(ValueError):
        transition(MonitorState.PAUSED, True)
