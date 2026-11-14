# Healthchecker

Сервис, который по расписанию проверяет доступность HTTP-целей и хранит историю результатов. Термины — в [`GLOSSARY.md`](GLOSSARY.md), планы — в [`docs/plans/`](docs/plans/).

**Пользователь** входит через Telegram, создаёт **Мониторы** (URL, метод, заголовки, тело, Ожидание, периодичность), сервис выполняет **Проверки** по расписанию и шлёт **Оповещения** о падении и восстановлении в Telegram-чаты — **Каналы оповещения** — через бота, которого Пользователь подключил сам. Чужие мониторы и каналы не видны. **Суперадмин** видит всех Пользователей, может их заблокировать, ставить их мониторы на паузу и смотреть историю их проверок.

**Срок хранения истории** — 3 дня: Проверки старше удаляются при старте backend и каждый день в 03:00 UTC, у Мониторов на паузе тоже.

> **Внимание.** Регистрация открытая: войти может любой пользователь Telegram. Токены ботов и заголовки Мониторов хранятся в базе открытым текстом.

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
cp .env.example .env   # заполните переменные входа через Telegram (см. ниже)
docker compose up --build
```

Страница — значение `ORIGIN` (по умолчанию http://localhost:3000). База лежит в томе `sqlite_data` и переживает `docker compose down` (но не `down -v`).

Сессия живёт 7 дней с момента входа. Новая сборка образа backend с изменённым кодом сбрасывает все Сессии, простой перезапуск контейнера — нет.

## Вход через Telegram

Вход — Telegram OpenID Connect. Нужен бот для входа и публичный HTTPS-адрес.

1. Создайте бота у [@BotFather](https://t.me/BotFather): его имя и аватар пользователь увидит в окне подтверждения входа.
2. В мини-приложении @BotFather откройте бота → **Login Widget** и добавьте разрешённые URL: origin сайта (`https://example.com`) и redirect URI (`https://example.com/auth/callback`). Там же скопируйте **Client ID** и **Client Secret**.
3. Заполните в `.env`: `TELEGRAM_CLIENT_ID`, `TELEGRAM_CLIENT_SECRET`, `TELEGRAM_REDIRECT_URI` (побайтово как в @BotFather), `ORIGIN` (тот же HTTPS-адрес) и `SUPERADMIN_TELEGRAM_ID`.
4. Для разработки поднимите HTTPS-туннель на `localhost:3000` (cloudflared или ngrok), лучше с постоянным адресом, и зарегистрируйте его в @BotFather. По `http://localhost` войти нельзя: Telegram требует HTTPS.

Суперадмин — Пользователь с Telegram ID из `SUPERADMIN_TELEGRAM_ID`. Права выдаются при входе: после смены переменной нужно войти заново. Суперадмина нельзя заблокировать.

## Подключение Telegram

У каждого Пользователя свой бот для оповещений ([ADR 0001](docs/adr/0001-telegram-bot-per-user.md)); один бот нельзя подключить двум Пользователям. Это может быть и бот для входа.

1. Создайте бота у [@BotFather](https://t.me/BotFather) командой `/newbot` и скопируйте токен.
2. На странице «Каналы оповещения» вставьте токен и нажмите «Подключить».
3. Добавьте бота в группу (или напишите ему в личные сообщения).
4. Нажмите «Найти чаты» **в течение суток**: Telegram хранит такие события 24 часа. Найденный чат сразу подключите — повторный поиск его уже не покажет. В чат придёт тестовое сообщение.
5. В форме Монитора отметьте нужные Каналы оповещения.

## Настройки

Переменные окружения задаются в `.env` (см. `.env.example`). `ORIGIN` — публичный адрес frontend для docker-compose (по умолчанию `http://localhost:3000`): по нему SvelteKit проверяет формы, а cookie получают `Secure`, если адрес — https. Остальные — для backend:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:////data/app.db` | путь к базе |
| `TELEGRAM_CLIENT_ID` | — | Client ID бота для входа (Login Widget в @BotFather) |
| `TELEGRAM_CLIENT_SECRET` | — | Client Secret бота для входа; есть только в контейнере backend |
| `TELEGRAM_REDIRECT_URI` | — | `https://<ORIGIN>/auth/callback`, побайтово как в @BotFather |
| `SUPERADMIN_TELEGRAM_ID` | — | Telegram ID Суперадмина |
| `ALLOW_PRIVATE_TARGETS` | `false` | разрешить Мониторам приватные сети (10/8, 172.16/12, 192.168/16, fc00::/7). Loopback, link-local и имена без точки (`localhost`, `backend`) запрещены всегда — защита от SSRF |

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
