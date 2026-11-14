import { API_URL } from '$app/env/private';
import { error } from '@sveltejs/kit';

const TIMEOUT_MS = 10_000;

type Fetch = typeof fetch;

/** Ошибки полей формы: имя поля → сообщение; `''` — ошибка формы целиком. */
export type FieldErrors = Record<string, string>;

/** Ответ backend, который форма должна показать пользователю (422, 409). */
export class ApiFormError extends Error {
	constructor(
		readonly status: number,
		readonly errors: FieldErrors,
		readonly detail: unknown
	) {
		super(Object.values(errors).join('; '));
	}
}

type ValidationDetail = { loc: (string | number)[]; msg: string; type: string }[];

// Сообщения pydantic — на английском; собственные ошибки backend уже на русском.
const MESSAGES: Record<string, string> = {
	missing: 'Обязательное поле',
	string_too_short: 'Обязательное поле',
	string_too_long: 'Слишком длинное значение',
	string_pattern_mismatch: 'Недопустимые символы',
	url_parsing: 'Некорректный URL',
	url_scheme: 'Допустимы только http и https',
	url_too_long: 'Слишком длинный URL',
	int_parsing: 'Нужно целое число',
	greater_than_equal: 'Код ответа — от 100 до 599',
	less_than_equal: 'Код ответа — от 100 до 599',
	enum: 'Выберите значение из списка'
};

function fieldErrors(detail: unknown): FieldErrors {
	if (Array.isArray(detail)) {
		const errors: FieldErrors = {};
		for (const { loc, msg, type } of detail as ValidationDetail) {
			// loc вида ["body", "headers", 0, "name"]: форма знает только поле верхнего уровня.
			const field = String(loc[1] ?? '');
			errors[field] ??= MESSAGES[type] ?? msg;
		}
		return errors;
	}
	if (detail && typeof detail === 'object' && 'message' in detail) {
		return { '': String(detail.message) };
	}
	return { '': String(detail) };
}

/**
 * Запрос к FastAPI из серверного кода SvelteKit. Возвращает JSON ответа.
 * Ошибки, которые форма показывает пользователю, бросаются как ApiFormError,
 * остальные сбои — страницей ошибки.
 */
export async function api<T>(fetch: Fetch, path: string, init: RequestInit = {}): Promise<T> {
	if (!API_URL) {
		console.error('API_URL is not set');
		error(503, 'Backend недоступен');
	}

	let res: Response;
	try {
		res = await fetch(`${API_URL}${path}`, {
			...init,
			headers: init.body ? { 'content-type': 'application/json', ...init.headers } : init.headers,
			signal: AbortSignal.timeout(TIMEOUT_MS)
		});
	} catch {
		error(503, 'Backend недоступен');
	}

	if (res.status === 204) return undefined as T;
	const body = await res.json().catch(() => null);
	if (res.ok) return body as T;
	// 422 и 409 — ошибки ввода; ответ с code — ожидаемый сбой (например, Telegram), не баг.
	if (res.status === 422 || res.status === 409 || body?.detail?.code) {
		throw new ApiFormError(res.status, fieldErrors(body?.detail), body?.detail);
	}
	// 404 — страница о несуществующем Мониторе или Канале, а не сбой backend.
	if (res.status === 404) error(404, body?.detail ?? 'Не найдено');
	console.error(`API ${init.method ?? 'GET'} ${path} → ${res.status}`, body);
	error(502, body?.detail?.message ?? `Ошибка backend (${res.status})`);
}
