.DEFAULT_GOAL := help
.PHONY: help install dev backend-dev frontend-dev check backend-check frontend-check \
	test backend-test lint backend-lint frontend-lint format migrate migration up down logs

# Локальная база, если нет backend/.env: переменная окружения перекрыла бы значение из него.
# Явный `make DATABASE_URL=...` действует всегда.
ifeq ($(wildcard backend/.env),)
DATABASE_URL ?= sqlite+aiosqlite:///./app.db
endif
BACKEND_DB := $(if $(DATABASE_URL),DATABASE_URL='$(DATABASE_URL)')

help: ## Показать список целей
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Установить зависимости backend и frontend
	cd backend && uv sync
	cd frontend && npm install

dev: ## Запустить backend и frontend локально (Ctrl+C останавливает оба)
	$(MAKE) -j2 backend-dev frontend-dev

backend-dev: migrate ## Запустить backend с автоперезагрузкой
	cd backend && $(BACKEND_DB) uv run uvicorn app.main:app --reload

frontend-dev: ## Запустить frontend в режиме разработки
	cd frontend && API_URL=http://localhost:8000 npm run dev

check: backend-check frontend-check ## Все проверки: линтеры, типы, тесты, дрейф миграций

backend-check: backend-lint backend-test migrate ## Проверки backend (накатывает миграции на локальную базу)
	cd backend && $(BACKEND_DB) uv run alembic check

frontend-check: frontend-lint ## Проверки frontend
	cd frontend && npm run check

test: backend-test ## Тесты

backend-test: ## Тесты backend
	cd backend && uv run pytest

lint: backend-lint frontend-lint ## Линтеры

backend-lint: ## Линтер и проверка форматирования backend
	cd backend && uv run ruff check . && uv run ruff format --check .

frontend-lint: ## Линтер и проверка форматирования frontend
	cd frontend && npm run lint

format: ## Отформатировать код backend и frontend
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && npm run format

migrate: ## Применить миграции к локальной базе
	cd backend && $(BACKEND_DB) uv run alembic upgrade head

migration: ## Создать миграцию: make migration m="описание"
	@test -n "$(m)" || { echo 'Укажите описание: make migration m="описание"'; exit 1; }
	cd backend && $(BACKEND_DB) uv run alembic revision --autogenerate -m "$(m)"

up: ## Собрать и запустить в Docker
	docker compose up --build

down: ## Остановить контейнеры (том с базой сохраняется)
	docker compose down

logs: ## Логи контейнеров
	docker compose logs -f
