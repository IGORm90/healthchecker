# Healthchecker

Сервис, который по расписанию проверяет доступность HTTP-целей и хранит историю результатов. Термины — в [`GLOSSARY.md`](GLOSSARY.md), планы — в [`docs/plans/`](docs/plans/).

Сейчас это каркас: страница показывает Liveness backend, предметной логики ещё нет.

## Архитектура

```
Браузер → SvelteKit (Node, порт 3000, SSR)
              ↓ внутренняя сеть Docker
          FastAPI (порт 8000, наружу не открыт) → SQLite (Docker volume)
```

Браузер общается только с SvelteKit; тот на сервере ходит в FastAPI по внутренней сети, поэтому CORS не нужен и API наружу закрыт.

## Требования

- Docker с Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python 3.14 он поставит сам)
- Node.js 22 LTS

## Запуск в Docker

```sh
cp .env.example .env   # необязательно: все значения имеют умолчания
docker compose up --build
```

Страница — http://localhost:3000. База лежит в томе `sqlite_data` и переживает `docker compose down` (но не `down -v`).

## Локальная разработка

Backend:

```sh
cd backend
echo 'DATABASE_URL=sqlite+aiosqlite:///./app.db' > .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Frontend (при запущенном backend):

```sh
cd frontend
npm install
API_URL=http://localhost:8000 npm run dev
```

## Тесты и линтеры

```sh
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run check && npm run lint
```

## Миграции

```sh
cd backend
uv run alembic revision --autogenerate -m "описание"
uv run alembic upgrade head
```

В контейнере миграции применяются автоматически при старте.
