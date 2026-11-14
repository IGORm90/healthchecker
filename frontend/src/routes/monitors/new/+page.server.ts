import { fail, redirect } from '@sveltejs/kit';
import type { Monitor, NotificationChannel } from '#lib/monitors.ts';
import { api, ApiFormError } from '#lib/server/api.ts';
import { readMonitorForm } from '#lib/server/monitor-form.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => ({
	channels: await api<NotificationChannel[]>(fetch, '/api/channels')
});

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const values = readMonitorForm(await request.formData());
		try {
			await api<Monitor>(fetch, '/api/monitors', {
				method: 'POST',
				body: JSON.stringify(values)
			});
		} catch (e) {
			if (e instanceof ApiFormError) return fail(e.status, { values, errors: e.errors });
			throw e;
		}
		redirect(303, '/');
	}
};
