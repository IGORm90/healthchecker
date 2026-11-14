import { redirect } from '@sveltejs/kit';
import type { UserSummary } from '#lib/auth.ts';
import type { Check, Monitor, NotificationChannel } from '#lib/monitors.ts';
import { api } from '#lib/server/api.ts';
import { monitorIdParam } from '#lib/server/monitor-form.ts';
import { pauseActions } from '#lib/server/pause.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch, locals }) => {
	const id = monitorIdParam(params.id);
	const [monitor, checks] = await Promise.all([
		api<Monitor>(fetch, `/api/monitors/${id}`),
		api<Check[]>(fetch, `/api/monitors/${id}/checks?limit=50`)
	]);
	// Чужой монитор открывает только Суперадмин: правка и Каналы оповещения ему недоступны.
	const isOwner = monitor.user_id === locals.user?.id;
	const [channels, owner] = isOwner
		? [await api<NotificationChannel[]>(fetch, '/api/channels'), null]
		: [[], await api<UserSummary>(fetch, `/api/admin/users/${monitor.user_id}`)];
	return {
		monitor,
		checks,
		isOwner,
		owner,
		channels: channels.filter((channel) => monitor.channel_ids.includes(channel.id))
	};
};

export const actions: Actions = {
	...pauseActions,
	delete: async ({ params, fetch }) => {
		await api<void>(fetch, `/api/monitors/${monitorIdParam(params.id)}`, { method: 'DELETE' });
		redirect(303, '/');
	}
};
