# 0003. Каркас интерфейса на Tailwind

Предыдущий этап: [`0001-scaffold.md`](0001-scaffold.md). Термины: [`GLOSSARY.md`](../../GLOSSARY.md).

**Цель:** вместо единственной строки «Backend: ok» — каркас веб-приложения на Tailwind: общий layout с навигацией между страницами «Мониторы» и «Каналы оповещения», страница ошибки, **Liveness** в подвале.

**Вне объёма:** данные и формы Мониторов и Каналов оповещения — это шаг 5 плана `0002`, он наполнит страницы каркаса.

## Принятые решения

| # | Решение |
|---|---------|
| 1 | Отдельный этап, не зависящий от backend: на backend по-прежнему только `/api/health` |
| 2 | Tailwind v4 через `sv add tailwindcss` (плагин `@tailwindcss/vite`, без `tailwind.config.js`) + `@tailwindcss/forms` + `prettier-plugin-tailwindcss` |
| 3 | Без библиотеки компонентов — чистый Tailwind |
| 4 | Верхняя шапка: «Healthchecker», «Мониторы» (`/`), «Каналы оповещения» (`/channels`); активный пункт подсвечен; без бургер-меню |
| 5 | Тёмная тема — только по системной настройке (`prefers-color-scheme`), без переключателя |
| 6 | Интерфейс только на русском, без i18n; подписи — по глоссарию |
| 7 | Маршруты: `/`, `/channels`, общий `+error.svelte`; у каждой страницы `<title>` вида «… · Healthchecker» |
| 8 | Страницы — честное пустое состояние: без кнопок и фейковых данных |
| 9 | Liveness загружается в `+layout.server.ts` (не зависит от URL, поэтому при клиентской навигации не перезапрашивается) и выводится в подвале: «Backend: работает / ошибка БД / недоступен» с цветной точкой |
| 10 | Палитра `zinc` + акцент `indigo`, системный шрифт. Цвета Состояний монитора — токены `@theme` в `src/routes/layout.css` для шага 5 плана `0002` |
| 11 | Компоненты в `src/lib/components/`: только `NavLink`, `LivenessIndicator`, `EmptyState` |
| 12 | Тестов фронтенда нет: `make check`, `npm run build` и ручной чек-лист. E2E — когда появятся формы |

---

## Шаг 1. Tailwind

`npx sv add tailwindcss="plugins:forms"` — ставит `@tailwindcss/vite`, `@tailwindcss/forms` и `prettier-plugin-tailwindcss`, создаёт `src/routes/layout.css` и подключает его в корневом `+layout.svelte`.

## Шаг 2. Layout и навигация

- `src/app.html`: `lang="ru"`.
- `src/routes/layout.css`: `@import 'tailwindcss'`, `@plugin '@tailwindcss/forms'`, токены `--color-state-unknown|up|down|paused` в `@theme`.
- `+layout.server.ts`: прежняя загрузка Liveness из `+page.server.ts` (тот удаляется); тип `Liveness` — в `src/lib/liveness.ts`.
- `+layout.svelte`: шапка с `NavLink`, `<main>` со страницей, подвал с `LivenessIndicator`.
- `NavLink`: принимает id маршрута без параметров (`PageRouteId`), ссылку строит через `resolve()` (правило eslint `svelte/no-navigation-without-resolve`). Активен, если `page.route.id` совпадает с маршрутом (для `/` — точное совпадение, иначе — и вложенные); `aria-current="page"`. Пути не сравниваются: при SSR `resolve()` отдаёт относительную ссылку (`./channels`).

## Шаг 3. Страницы

- `/` — «Мониторы», `EmptyState`: «Мониторов пока нет» / «Создание мониторов появится в следующем этапе».
- `/channels` — «Каналы оповещения», `EmptyState`: «Каналов оповещения пока нет» / «Подключение Telegram появится в следующем этапе».
- `+error.svelte` — код и сообщение (`page.status`, `page.error`), для 404 — «Страница не найдена», ссылка на `/`.

## Шаг 4. Проверка готовности

| Проверка | Как |
|---|---|
| Статика и типы | `make frontend-check`, `npm run build` |
| Навигация | `/` ↔ `/channels` переключаются, активный пункт подсвечен |
| Ошибка | `/nope` — «Страница не найдена» в общем layout, код 404 |
| SSR | `curl -s localhost:3000 \| grep 'Backend: работает'` |
| Деградация | `docker compose stop backend` → в подвале «Backend: недоступен» |
| Тёмная тема | смена системной темы меняет оформление |
| Мобильная ширина | 375px — без горизонтального скролла |
