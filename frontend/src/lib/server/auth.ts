import type { Cookies } from '@sveltejs/kit';

export const SESSION_COOKIE = 'session';
// state и code_verifier живут от старта входа до возврата из Telegram.
export const STATE_COOKIE = 'oidc_state';
export const VERIFIER_COOKIE = 'oidc_verifier';
const OIDC_COOKIE_PATH = '/auth';
const OIDC_COOKIE_MAX_AGE = 10 * 60;

// Lax, а не Strict: иначе браузер не пришлёт cookie при возврате из Telegram.
// Secure — только по https: при разработке на http://localhost cookie иначе не сохранится.
function options(url: URL) {
	return { httpOnly: true, sameSite: 'lax', secure: url.protocol === 'https:' } as const;
}

export function setOidcCookies(cookies: Cookies, url: URL, state: string, verifier: string) {
	const opts = { ...options(url), path: OIDC_COOKIE_PATH, maxAge: OIDC_COOKIE_MAX_AGE };
	cookies.set(STATE_COOKIE, state, opts);
	cookies.set(VERIFIER_COOKIE, verifier, opts);
}

/** Читает и сразу удаляет state и code_verifier: они одноразовые. */
export function takeOidcCookies(cookies: Cookies, url: URL) {
	const state = cookies.get(STATE_COOKIE);
	const verifier = cookies.get(VERIFIER_COOKIE);
	cookies.delete(STATE_COOKIE, { ...options(url), path: OIDC_COOKIE_PATH });
	cookies.delete(VERIFIER_COOKIE, { ...options(url), path: OIDC_COOKIE_PATH });
	return { state, verifier };
}

export function setSessionCookie(cookies: Cookies, url: URL, token: string, expiresAt: string) {
	cookies.set(SESSION_COOKIE, token, { ...options(url), path: '/', expires: new Date(expiresAt) });
}

export function deleteSessionCookie(cookies: Cookies, url: URL) {
	cookies.delete(SESSION_COOKIE, { ...options(url), path: '/' });
}
