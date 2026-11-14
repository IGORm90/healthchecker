import { API_URL } from '$app/env/private';
import type { Liveness } from '#lib/liveness.ts';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, locals }) => {
	const user = locals.user;
	if (!API_URL) {
		console.error('API_URL is not set');
		return { liveness: 'unavailable' as Liveness, user };
	}

	let liveness: Liveness;
	try {
		const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(3000) });
		const body = await res.json();
		liveness = res.ok && body.status === 'ok' ? 'ok' : 'error';
	} catch {
		liveness = 'unavailable';
	}
	return { liveness, user };
};
