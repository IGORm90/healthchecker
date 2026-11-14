import { redirect } from '@sveltejs/kit';
import { api, ApiFormError } from '#lib/server/api.ts';
import { setOidcCookies } from '#lib/server/auth.ts';
import type { RequestHandler } from './$types';

type Authorization = { url: string; state: string; code_verifier: string };

/** Старт входа: state и code_verifier — в cookie браузера, сам браузер — в Telegram. */
export const GET: RequestHandler = async ({ fetch, cookies, url }) => {
	let authorization: Authorization;
	try {
		authorization = await api<Authorization>(fetch, '/api/auth/telegram/start', {
			method: 'POST'
		});
	} catch (e) {
		if (e instanceof ApiFormError) redirect(303, '/login?error=not_configured');
		throw e;
	}
	setOidcCookies(cookies, url, authorization.state, authorization.code_verifier);
	redirect(303, authorization.url);
};
