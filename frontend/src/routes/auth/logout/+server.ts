import { redirect } from '@sveltejs/kit';
import { api } from '#lib/server/api.ts';
import { deleteSessionCookie } from '#lib/server/auth.ts';
import type { RequestHandler } from './$types';

/** Выход только POST-формой: чужая ссылка не разлогинит Пользователя (CSRF проверяет SvelteKit). */
export const POST: RequestHandler = async ({ fetch, cookies, url, locals }) => {
	deleteSessionCookie(cookies, url);
	if (locals.sessionToken) {
		try {
			await api<void>(fetch, '/api/auth/logout', { method: 'POST' });
		} catch {
			// Сессия уже недействительна или backend недоступен: cookie всё равно удалена.
		}
	}
	redirect(303, '/login');
};
