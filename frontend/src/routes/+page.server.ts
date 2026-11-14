import type { Monitor } from '#lib/monitors.ts';
import { api } from '#lib/server/api.ts';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => ({
	monitors: await api<Monitor[]>(fetch, '/api/monitors')
});
