from app.models import AlertKind, MonitorState


def transition(current: MonitorState, success: bool) -> tuple[MonitorState, AlertKind | None]:
    """Новое Состояние монитора после проверки и Оповещение, которое надо отправить.

    Упал — после одной неудачи, восстановился — после одного успеха (план 0002, решения 9, 15).
    """
    if current is MonitorState.PAUSED:
        raise ValueError("монитор на паузе не проверяется")
    if success:
        return MonitorState.UP, AlertKind.RECOVERED if current is MonitorState.DOWN else None
    return MonitorState.DOWN, None if current is MonitorState.DOWN else AlertKind.DOWN
