import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
	API_URL: {
		description: 'Адрес FastAPI, доступный серверу SvelteKit (в Docker — http://backend:8000)',
		// Валидатор запускается и при `vite build`, где переменной намеренно нет: она задаётся
		// при старте контейнера. Поэтому пустое значение допустимо, его обрабатывает вызывающий код.
		schema: (value) => (value ? new URL(value).origin : undefined)
	}
});
