import { fail, redirect } from '@sveltejs/kit';
import type { Monitor, NotificationChannel } from '#lib/monitors.ts';
import { api, ApiFormError } from '#lib/server/api.ts';
import { monitorIdParam, readMonitorForm } from '#lib/server/monitor-form.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch }) => {
	const id = monitorIdParam(params.id);
	const [monitor, channels] = await Promise.all([
		api<Monitor>(fetch, `/api/monitors/${id}`),
		api<NotificationChannel[]>(fetch, '/api/channels')
	]);
	return { monitor, channels };
};

export const actions: Actions = {
	default: async ({ params, request, fetch }) => {
		const id = monitorIdParam(params.id);
		const values = readMonitorForm(await request.formData());
		try {
			await api<Monitor>(fetch, `/api/monitors/${id}`, {
				method: 'PUT',
				body: JSON.stringify(values)
			});
		} catch (e) {
			if (e instanceof ApiFormError) return fail(e.status, { values, errors: e.errors });
			throw e;
		}
		redirect(303, `/monitors/${id}`);
	}
};
