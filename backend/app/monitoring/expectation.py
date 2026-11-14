from dataclasses import dataclass


@dataclass(frozen=True)
class Expectation:
    """Ожидание монитора: код ответа и, необязательно, подстрока тела."""

    status: int
    body: str | None


def evaluate(expectation: Expectation, status_code: int, body_prefix: bytes) -> str | None:
    """None — ответ соответствует Ожиданию, иначе причина неуспеха для пользователя."""
    if status_code != expectation.status:
        return f"ожидался {expectation.status}, получен {status_code}"
    if expectation.body is not None:
        # Кодировку ответа не угадываем: битые байты не должны мешать найти подстроку.
        if expectation.body not in body_prefix.decode("utf-8", errors="replace"):
            return f"тело не содержит «{expectation.body}»"
    return None
