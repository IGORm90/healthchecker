import { API_URL } from '$app/env/private';
import type { PageServerLoad } from './$types';

// Liveness backend: ok — API и БД живы, error — API жив, БД нет, unavailable — API не ответил.
type Liveness = 'ok' | 'error' | 'unavailable';

export const load: PageServerLoad = async ({ fetch }) => {
	if (!API_URL) {
		console.error('API_URL is not set');
		return { liveness: 'unavailable' as Liveness };
	}

	let liveness: Liveness;
	try {
		const res = await fetch(`${API_URL}/api/health`, { signal: AbortSignal.timeout(3000) });
		const body = await res.json();
		liveness = res.ok && body.status === 'ok' ? 'ok' : 'error';
	} catch {
		liveness = 'unavailable';
	}
	return { liveness };
};
