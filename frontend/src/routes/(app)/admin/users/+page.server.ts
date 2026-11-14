import type { UserSummary } from '#lib/auth.ts';
import { api } from '#lib/server/api.ts';
import { blockActions } from '#lib/server/block.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => ({
	users: await api<UserSummary[]>(fetch, '/api/admin/users')
});

export const actions: Actions = blockActions;
