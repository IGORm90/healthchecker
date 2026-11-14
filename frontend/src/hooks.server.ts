import { API_URL } from '$app/env/private';
import type { Handle, HandleFetch } from '@sveltejs/kit/hooks';
import type { User } from '#lib/auth.ts';
import { deleteSessionCookie, SESSION_COOKIE } from '#lib/server/auth.ts';

const TIMEOUT_MS = 5000;

/** Пользователь по токену Сессии; 'invalid' — Сессия недействительна, null — backend недоступен. */
async function currentUser(token: string): Promise<User | null | 'invalid'> {
	if (!API_URL) return null;
	try {
		const res = await fetch(`${API_URL}/api/auth/me`, {
			headers: { authorization: `Bearer ${token}` },
			signal: AbortSignal.timeout(TIMEOUT_MS)
		});
		if (res.status === 401) return 'invalid';
		return res.ok ? ((await res.json()) as User) : null;
	} catch {
		return null;
	}
}

export const handle: Handle = async ({ event, resolve }) => {
	const token = event.cookies.get(SESSION_COOKIE) ?? null;
	const user = token ? await currentUser(token) : null;
	if (user === 'invalid') {
		// Сессия истекла, удалена при выходе или сброшена новой сборкой.
		deleteSessionCookie(event.cookies, event.url);
		event.locals.user = null;
		event.locals.sessionToken = null;
	} else {
		event.locals.user = user;
		event.locals.sessionToken = user ? token : null;
	}
	return resolve(event);
};

/** Токен Сессии в каждом серверном запросе к API: load и actions его не передают сами. */
export const handleFetch: HandleFetch = ({ event, request, fetch }) => {
	const token = event.locals.sessionToken;
	if (API_URL && token && request.url.startsWith(`${API_URL}/`)) {
		request.headers.set('authorization', `Bearer ${token}`);
	}
	return fetch(request);
};
