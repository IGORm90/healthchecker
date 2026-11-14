import { fail } from '@sveltejs/kit';
import type { DiscoveredChat, NotificationChannel, TelegramConnection } from '#lib/monitors.ts';
import { api, ApiFormError } from '#lib/server/api.ts';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [telegram, channels] = await Promise.all([
		api<TelegramConnection>(fetch, '/api/telegram'),
		api<NotificationChannel[]>(fetch, '/api/channels')
	]);
	return { telegram, channels };
};

export const actions: Actions = {
	connect: async ({ request, fetch }) => {
		const token = String((await request.formData()).get('token') ?? '').trim();
		try {
			await api<TelegramConnection>(fetch, '/api/telegram', {
				method: 'PUT',
				body: JSON.stringify({ token })
			});
		} catch (e) {
			if (e instanceof ApiFormError) return fail(e.status, { action: 'connect', errors: e.errors });
			throw e;
		}
	},

	discover: async ({ fetch }) => {
		try {
			const discovered = await api<DiscoveredChat[]>(fetch, '/api/telegram/discover', {
				method: 'POST'
			});
			return { discovered };
		} catch (e) {
			if (e instanceof ApiFormError)
				return fail(e.status, { action: 'discover', errors: e.errors });
			throw e;
		}
	},

	create: async ({ request, fetch }) => {
		const form = await request.formData();
		const chatId = Number(form.get('telegram_chat_id'));
		try {
			await api<NotificationChannel>(fetch, '/api/channels', {
				method: 'POST',
				body: JSON.stringify({
					name: String(form.get('name') ?? '').trim(),
					telegram_chat_id: chatId
				})
			});
		} catch (e) {
			if (e instanceof ApiFormError) {
				return fail(e.status, { action: 'create', chatId, errors: e.errors });
			}
			throw e;
		}
		return { created: chatId };
	}
};
