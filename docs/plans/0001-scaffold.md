# 0001. Каркас: FastAPI + SQLite + SvelteKit в Docker

Исходный план: [`docs/mvp-plan-fastapi-sqlite-sveltekit.md`](../mvp-plan-fastapi-sqlite-sveltekit.md). Термины: [`GLOSSARY.md`](../../GLOSSARY.md).

**Цель:** `docker compose up --build` поднимает оба сервиса; страница на `localhost:3000`, отрендеренная на сервере, показывает **Liveness** backend. Бизнес-логики (мониторы, проверки) нет.

**Вне объёма:** всё из раздела «Следующий этап» исходного плана.

## Принятые решения

| # | Решение |
|---|---------|
| 1 | Корень репозитория — `healthchecker/`, без вложенной `project/` |
| 2 | `git init`, ветка `main`, коммит на каждый шаг ниже, Conventional Commits на английском |
| 3 | Python 3.14 локально и в образе (`uv python pin 3.14`; системный Python — 3.11). 3.15 отложена: свежий релиз, риск отсутствия wheels |
| 4 | `uv init --app`; в Docker `uv sync --frozen --no-dev`; `uv.lock` и `package-lock.json` в git |
| 5 | `/api/health`: `200 {"status":"ok"}` или `503 {"status":"error"}` при недоступной БД |
| 6 | Фронт при недоступном backend рендерит статус `unavailable`, а не страницу ошибки 500 |
| 7 | Контейнеры не от root: пользователь `app` в backend, `node` во frontend |
| 8 | `DATABASE_URL` по умолчанию `sqlite+aiosqlite:////data/app.db`; локально — `backend/.env` с `./app.db` |
| 9 | Тесты: pytest на `/api/health` (ok и error) + `ruff`. Фронт — `svelte-check`, `eslint` и ручной чек-лист |
| 10 | README и документация на русском |

---

## Шаг 0. Репозиторий

1. `git init -b main`.
2. Корневой `.gitignore`:
   ```
   .env
   .venv/
   __pycache__/
   *.db
   *.db-wal
   *.db-shm
   node_modules/
   .svelte-kit/
   build/
   .DS_Store
   ```
   (`*.db-wal`/`*.db-shm` — побочные файлы режима WAL.)
3. Уже лежат: `AGENTS.md`, `CLAUDE.md`, `GLOSSARY.md`, `docs/`.

**Готово, когда:** `git status` чистый после коммита `chore: initialize repository`.

---

## Шаг 1. Backend

### 1.1. Проект и зависимости

```sh
mkdir backend && cd backend
uv init --app --name healthchecker-backend --no-readme
uv python pin 3.14
rm main.py                       # заготовка uv не нужна
uv add fastapi "uvicorn[standard]" pydantic-settings "sqlalchemy[asyncio]" aiosqlite alembic httpx
uv add --dev ruff pytest pytest-asyncio
```

В `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 1.2. `app/core/config.py`

`Settings(BaseSettings)` с `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` и полем `database_url: str = "sqlite+aiosqlite:////data/app.db"`. Экземпляр модуля — `settings = Settings()`.

### 1.3. `app/db/base.py`

`class Base(DeclarativeBase)` с `MetaData(naming_convention=...)` (ix/uq/ck/fk/pk). Именованные ограничения нужны Alembic: на SQLite изменения схемы идут через batch-режим (пересоздание таблицы), и безымянные ограничения в нём не удалить.

### 1.4. `app/db/session.py`

- `engine = create_async_engine(settings.database_url)`.
- Слушатель `@event.listens_for(engine.sync_engine, "connect")`, который на каждом новом соединении выполняет `PRAGMA journal_mode=WAL` и `PRAGMA foreign_keys=ON` через `dbapi_connection.cursor()`.
- `SessionLocal = async_sessionmaker(engine, expire_on_commit=False)`.
- Зависимость `async def get_session() -> AsyncIterator[AsyncSession]`.

### 1.5. `app/api/health.py`

`router = APIRouter(prefix="/api")`, `GET /health`:
- `await session.execute(text("SELECT 1"))` → `{"status": "ok"}`;
- `SQLAlchemyError` → `JSONResponse(status_code=503, content={"status": "error"})`.

### 1.6. `app/main.py`

`lifespan`: пустой до `yield` (комментарий: здесь появится фоновый исполнитель), после `yield` — `await engine.dispose()`. `app = FastAPI(lifespan=lifespan)`, `app.include_router(health.router)`.

Во всех пакетах `app/`, `app/core/`, `app/db/`, `app/api/` — пустые `__init__.py`.

### 1.7. Alembic

```sh
uv run alembic init -t async migrations
```

- В `alembic.ini` оставить `sqlalchemy.url` пустым.
- В `migrations/env.py`: `config.set_main_option("sqlalchemy.url", settings.database_url)`, `target_metadata = Base.metadata`, в `context.configure(...)` обоих режимов — `render_as_batch=True` (см. 1.3).
- `migrations/versions/` пустая, но в git: положить `.gitkeep`.

### 1.8. Тест `tests/test_health.py`

Фикстура строит `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` и подменяет `get_session` через `app.dependency_overrides` на сессию отдельного движка:
- `test_health_ok`: движок на `tmp_path / "test.db"` → 200, `{"status": "ok"}`;
- `test_health_db_unavailable`: движок на `tmp_path / "missing" / "test.db"` (каталога нет, SQLite не откроет файл) → 503, `{"status": "error"}`.

### 1.9. Локальный запуск

`backend/.env` (в git не попадает): `DATABASE_URL=sqlite+aiosqlite:///./app.db`.

**Готово, когда:**
- `uv run ruff check . && uv run ruff format --check .` — без замечаний;
- `uv run pytest` — 2 passed;
- `uv run alembic upgrade head` создаёт `backend/app.db` без ошибок;
- `uv run uvicorn app.main:app --reload` → `curl localhost:8000/api/health` отдаёт `{"status":"ok"}`.

Коммит: `feat(backend): scaffold FastAPI app with SQLite and health endpoint`.

---

## Шаг 2. Frontend

### 2.1. Создание

```sh
npx sv create frontend    # minimal, TypeScript, add-ons: prettier, eslint; менеджер — npm
cd frontend
npm i -D @sveltejs/adapter-node
```

Флаги `sv create` при неинтерактивном запуске сверить с `npx sv create --help`.

> **Отклонение при реализации:** `sv create` сгенерировал SvelteKit 3. В нём нет `svelte.config.js` (конфиг Kit — в `vite.config.ts`), а `$env/dynamic/private` устарел в пользу `src/env.ts` + `$app/env/private`.

### 2.2. Адаптер (`vite.config.ts`)

Импорт адаптера заменить на `@sveltejs/adapter-node`; удалить `@sveltejs/adapter-auto` из `devDependencies`.

### 2.3. `src/env.ts` и `src/routes/+page.server.ts`

`API_URL` объявлен через `defineEnvVars` (приватный, не static — читается при старте). Валидатор выполняется и во время `vite build`, где переменной нет, поэтому пропускает пустое значение; `load` в этом случае отдаёт `unavailable` и пишет ошибку в лог.

`load` ходит в `${API_URL}/api/health` с таймаутом 3 с.

`503 {"status":"error"}` → `error` (backend жив, БД нет); сетевой сбой или таймаут → `unavailable` (backend недоступен).

### 2.4. `src/routes/+page.svelte`

Заголовок `Healthchecker` и строка `Backend: {data.liveness}`. Стилизация не нужна.

### 2.5. Локальный запуск

`API_URL=http://localhost:8000 npm run dev` при запущенном backend из шага 1.9.

**Готово, когда:**
- `npm run check` и `npm run lint` — без ошибок;
- `npm run build` создаёт `build/`;
- страница показывает `Backend: ok`; при остановленном backend — `Backend: unavailable`, без страницы ошибки.

Коммит: `feat(frontend): scaffold SvelteKit app with node adapter`.

---

## Шаг 3. Docker

### 3.1. `backend/Dockerfile`

```dockerfile
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN useradd --system --no-create-home app && mkdir /data && chown app:app /data
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- Один процесс uvicorn, без `--workers` (см. `AGENTS.md`).
- `chown /data` в образе важен: пустой именованный том при первом монтировании наследует владельца каталога из образа, иначе `app` не сможет создать `app.db`. Каталог `/data` должен существовать: SQLite создаёт файл, но не каталог.
- `backend/.dockerignore`: `.venv`, `__pycache__`, `*.db*`, `.env`, `.pytest_cache`, `.ruff_cache`, `tests`.

### 3.2. `frontend/Dockerfile`

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/build ./build
USER node
EXPOSE 3000
CMD ["node", "build"]
```

- `frontend/.dockerignore`: `node_modules`, `.svelte-kit`, `build`, `.env`.

### 3.3. `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    env_file:
      - path: .env
        required: false
    volumes:
      - sqlite_data:/data
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    mem_limit: 256m

  frontend:
    build: ./frontend
    depends_on:
      backend:
        condition: service_healthy
    environment:
      API_URL: http://backend:8000
      ORIGIN: http://localhost:3000
    ports:
      - "3000:3000"
    restart: unless-stopped
    mem_limit: 256m

volumes:
  sqlite_data:
```

`urlopen` бросает исключение на 503, поэтому healthcheck падает и при недоступной БД (решение 5).

### 3.4. `.env.example`

```
# Путь к SQLite внутри контейнера backend (по умолчанию):
# DATABASE_URL=sqlite+aiosqlite:////data/app.db
```

**Готово, когда:** выполнен чек-лист из шага 5 (кроме README).

Коммит: `build: add Dockerfiles and docker-compose`.

---

## Шаг 4. README

Разделы: что это (одна строка + ссылка на `GLOSSARY.md`); требования (Docker, uv, Node 22); запуск в Docker; локальная разработка (`backend/.env`, команды из 1.9 и 2.5); тесты и линтеры; схема архитектуры из исходного плана.

Коммит: `docs: add README`.

---

## Шаг 5. Проверка готовности

| Проверка | Как |
|---|---|
| Оба контейнера поднялись, backend `healthy` | `docker compose up --build -d && docker compose ps` |
| Статус отрендерен на сервере | `curl -s localhost:3000 \| grep 'Backend: ok'` |
| API наружу закрыт | `curl localhost:8000/api/health` — connection refused |
| БД в томе | `docker compose exec backend ls -l /data` — есть `app.db`, владелец `app` |
| БД переживает перезапуск | `docker compose down && docker compose up -d`, затем снова `ls -l /data` — тот же файл (дата создания не изменилась) |
| Память в норме | `docker stats --no-stream` — backend ≈ 60–120 МБ, frontend ≈ 50–100 МБ |
| Деградация фронта | `docker compose stop backend` → страница `Backend: unavailable`, не 500 |
| Контейнеры не от root | `docker compose exec backend id`, `docker compose exec frontend id` — не `uid=0` |

Плюс зелёные `uv run pytest`, `uv run ruff check .`, `npm run check`, `npm run lint`.
