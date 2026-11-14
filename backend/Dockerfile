FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# Идентификатор сборки: слой пересобирается только при изменении кода выше, поэтому
# новая сборка сбрасывает Сессии, а перезапуск контейнера — нет.
RUN cat /proc/sys/kernel/random/uuid > .build-id
# Пустой именованный том при первом монтировании наследует владельца /data из образа.
RUN useradd --system --no-create-home app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000
# Строго один процесс uvicorn, без --workers: фоновый исполнитель должен быть единственным.
CMD ["sh", "-c", "export BUILD_ID=$(cat .build-id) && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
