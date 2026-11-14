import type { Monitor } from '#lib/monitors.ts';
import { api } from '#lib/server/api.ts';
import { pauseActions } from '#lib/server/pause.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => ({
	monitors: await api<Monitor[]>(fetch, '/api/monitors')
});

export const actions: Actions = pauseActions;
