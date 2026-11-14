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

## Команды

Повседневные команды собраны в `Makefile`; полный список — `make help`.

```sh
make install   # зависимости backend и frontend
make dev       # backend на :8000 и frontend на :5173, Ctrl+C останавливает оба
make check     # линтеры, типы, тесты и проверка, что модели не разошлись с миграциями
make format    # автоформатирование
make up        # docker compose up --build -d; логи — make logs, остановка — make down
```

Backend и frontend можно запускать по отдельности: `make backend-dev`, `make frontend-dev`. Локальная база — `backend/app.db`; другой путь задаётся через `make DATABASE_URL=... <цель>` или `backend/.env`. Frontend в режиме разработки обращается к API по `API_URL=http://localhost:8000`.

## Миграции

```sh
make migration m="описание"   # alembic revision --autogenerate
make migrate                  # alembic upgrade head
```

В контейнере миграции применяются автоматически при старте.
