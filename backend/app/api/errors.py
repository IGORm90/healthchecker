from fastapi import HTTPException, status


def validation_error(field: str, message: str, error_type: str) -> HTTPException:
    # Тот же формат, что у ошибок валидации FastAPI, чтобы фронт разбирал их одинаково.
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[{"loc": ["body", field], "msg": message, "type": error_type}],
    )
