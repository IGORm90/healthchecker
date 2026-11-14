import { redirect } from '@sveltejs/kit';
import { api, ApiFormError } from '#lib/server/api.ts';
import { setSessionCookie, takeOidcCookies } from '#lib/server/auth.ts';
import type { RequestHandler } from './$types';

type NewSession = { token: string; expires_at: string };

/** Возврат из Telegram: проверка state, обмен кода в backend, cookie Сессии. */
export const GET: RequestHandler = async ({ fetch, cookies, url }) => {
	const { state, verifier } = takeOidcCookies(cookies, url);
	const params = url.searchParams;
	// Пользователь отказался от входа в окне Telegram.
	if (params.has('error')) redirect(303, '/login?error=denied');

	const code = params.get('code');
	if (!code || !state || !verifier || params.get('state') !== state) {
		redirect(303, '/login?error=state');
	}

	let session: NewSession;
	try {
		session = await api<NewSession>(fetch, '/api/auth/telegram/callback', {
			method: 'POST',
			body: JSON.stringify({ code, code_verifier: verifier })
		});
	} catch (e) {
		if (e instanceof ApiFormError) {
			const blocked = (e.detail as { code?: string } | undefined)?.code === 'user_blocked';
			redirect(303, `/login?error=${blocked ? 'blocked' : 'failed'}`);
		}
		throw e;
	}
	setSessionCookie(cookies, url, session.token, session.expires_at);
	redirect(303, '/');
};
