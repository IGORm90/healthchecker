import { error } from '@sveltejs/kit';
import type { UserSummary } from '#lib/auth.ts';
import type { Monitor } from '#lib/monitors.ts';
import { api } from '#lib/server/api.ts';
import { blockActions } from '#lib/server/block.ts';
import { pauseActions } from '#lib/server/pause.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
	const id = Number(params.id);
	if (!Number.isInteger(id) || id <= 0) error(404, 'Пользователь не найден');
	const [user, monitors] = await Promise.all([
		api<UserSummary>(fetch, `/api/admin/users/${id}`),
		api<Monitor[]>(fetch, `/api/admin/users/${id}/monitors`)
	]);
	return { profile: user, monitors };
};

export const actions: Actions = { ...pauseActions, ...blockActions };
