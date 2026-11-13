# План MVP: FastAPI + SQLite + SvelteKit в Docker

Цель этапа — пустой каркас проекта, который поднимается одной командой: SvelteKit рендерит страницу на сервере и получает ответ от FastAPI, а SQLite лежит в Docker-томе. Бизнес-логики пока нет.

## Архитектура

```
Браузер → SvelteKit (Node, порт 3000, SSR)
              ↓ внутренняя сеть Docker
          FastAPI (порт 8000, наружу не открыт) → SQLite (Docker volume)
```

Браузер общается только с SvelteKit, а тот на сервере ходит в FastAPI по внутренней сети. Благодаря этому не нужен CORS и не нужно открывать API наружу.

## Шаг 0. Что установить локально

- Docker с Docker Compose
- Git
- Python 3.12+ и **uv** (менеджер зависимостей)
- Node.js 22 LTS

Python и Node нужны для генерации проекта и разработки без Docker.

## Шаг 1. Структура репозитория

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py            # создание FastAPI, lifespan
│   │   ├── core/config.py     # настройки через pydantic-settings
│   │   ├── db/session.py      # движок SQLAlchemy, сессия
│   │   ├── db/base.py         # базовый класс моделей
│   │   └── api/health.py      # эндпоинт /api/health
│   ├── migrations/            # Alembic
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── src/routes/+page.svelte
│   ├── src/routes/+page.server.ts
│   ├── svelte.config.js
│   ├── package.json
│   ├── Dockerfile
│   └── .dockerignore
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Шаг 2. Backend

1. В папке `backend` выполнить `uv init`, затем добавить зависимости: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy`, `aiosqlite`, `alembic`, `httpx`. Для разработки: `ruff`, `pytest`, `pytest-asyncio`.
2. В `core/config.py` описать настройки. Главная — `DATABASE_URL`, по умолчанию `sqlite+aiosqlite:////data/app.db` (путь внутри контейнера, куда смонтирован том).
3. В `db/session.py` создать async-движок и при подключении включать `PRAGMA journal_mode=WAL` и `PRAGMA foreign_keys=ON`.
4. В `main.py` создать приложение с `lifespan` (пока пустым: позже туда добавится фоновый исполнитель) и подключить роутер.
5. Сделать единственный эндпоинт `GET /api/health`, который делает `SELECT 1` в базу и возвращает `{"status": "ok"}`. Это проверка, что API и БД живы.
6. Выполнить `alembic init -t async migrations` и в `env.py` взять URL базы из настроек, а метаданные из `db/base.py`. Миграций пока нет.

## Шаг 3. Frontend

1. Создать проект командой `npx sv create frontend`: шаблон minimal, TypeScript, по желанию Prettier и ESLint.
2. Установить `@sveltejs/adapter-node` и прописать его в `svelte.config.js`. Именно он позволяет запускать SvelteKit как Node-сервер в Docker; адаптер по умолчанию для этого не подходит.
3. Адрес API передавать через приватную переменную окружения `API_URL` (читать через `$env/dynamic/private`, чтобы значение задавалось при запуске контейнера, а не при сборке). В Docker это `http://backend:8000`.
4. В `+page.server.ts` сделать загрузку данных из `/api/health`, а в `+page.svelte` вывести результат. Так сразу видно, что SSR и связь с backend работают.

## Шаг 4. Docker

### `backend/Dockerfile`

- Образ `python:3.12-slim`.
- Установка зависимостей через uv: сначала копируется только `pyproject.toml` и lock-файл, чтобы кешировался слой с зависимостями, затем копируется код.
- Команда запуска: `alembic upgrade head`, потом `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Строго **один процесс** без `--workers`, чтобы фоновые задачи не выполнялись дважды.

### `frontend/Dockerfile`

- Двухэтапная сборка.
- Этап сборки на `node:22-alpine`: `npm ci` и `npm run build`.
- Финальный этап на том же образе получает только папку `build`, `package.json` и production-зависимости. Запуск командой `node build`.

### `docker-compose.yml`

- Сервис `backend`:
  - том `sqlite_data:/data`;
  - переменные из `.env`;
  - без проброса портов наружу, только `expose: 8000`;
  - healthcheck на `/api/health` (в slim-образе нет curl, поэтому через `python -c` с `urllib`).
- Сервис `frontend`:
  - `depends_on` на backend с условием `service_healthy`;
  - переменные `API_URL=http://backend:8000` и `ORIGIN=http://localhost:3000` (adapter-node требует `ORIGIN` для защиты форм от CSRF);
  - проброс порта `3000:3000`.
- Обоим сервисам `restart: unless-stopped` и лимиты памяти через `mem_limit`, например 256M для backend и 256M для frontend.
- Именованный том `sqlite_data`.

### Служебные файлы

- `backend/.dockerignore`: `.venv`, `__pycache__`, `*.db`.
- `frontend/.dockerignore`: `node_modules`, `.svelte-kit`, `build`.
- `.gitignore`: то же самое плюс `.env`. В репозитории хранится только `.env.example`.

## Шаг 5. Режим разработки

В Docker удобно запускать «как в проде», а разрабатывать быстрее локально:

- backend: `uv run uvicorn app.main:app --reload`;
- frontend: `npm run dev` с `API_URL=http://localhost:8000`.

Позже можно добавить `docker-compose.override.yml` с монтированием исходников и hot reload, но для старта это необязательно.

## Шаг 6. Проверка готовности каркаса

- [ ] `docker compose up --build` поднимает оба контейнера без ошибок, backend получает статус healthy.
- [ ] На `http://localhost:3000` открывается страница со статусом backend «ok», и в исходном коде страницы (Ctrl+U) этот текст уже есть, то есть он отрендерен на сервере.
- [ ] Файл `app.db` появляется в томе и переживает `docker compose down` и повторный `up`.
- [ ] `docker stats` показывает потребление в пределах ожидаемого: примерно 60–120 МБ backend и 50–100 МБ frontend.

## Следующий этап (после каркаса)

1. Модели и первая миграция: запросы и история выполнений.
2. CRUD-эндпоинты.
3. Фоновый исполнитель в `lifespan`.
4. Защита от SSRF.
5. Страницы во фронтенде.
6. Caddy перед frontend для HTTPS.
