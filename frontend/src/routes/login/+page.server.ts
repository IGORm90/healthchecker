import { redirect } from '@sveltejs/kit';
import { LOGIN_ERRORS } from '#lib/auth.ts';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals, url }) => {
	if (locals.user) redirect(303, '/');
	const error = url.searchParams.get('error');
	return { error: error ? (LOGIN_ERRORS[error] ?? LOGIN_ERRORS.failed) : null };
};
