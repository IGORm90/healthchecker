import { error, fail } from '@sveltejs/kit';
import type {
	DiscoveredChat,
	NotificationChannel,
	NotificationChannelCreated,
	TelegramConnection
} from '#lib/monitors.ts';
import { api, ApiFormError, type FieldErrors } from '#lib/server/api.ts';
import type { Actions, PageServerLoad } from './$types';

function channelId(form: FormData): number {
	const id = Number(form.get('id'));
	if (!Number.isInteger(id) || id <= 0) error(400, 'Некорректный канал оповещения');
	return id;
}

export const load: PageServerLoad = async ({ fetch }) => {
	const [telegram, channels] = await Promise.all([
		api<TelegramConnection>(fetch, '/api/telegram'),
		api<NotificationChannel[]>(fetch, '/api/channels')
	]);
	return { telegram, channels };
};

export const actions: Actions = {
	connect: async ({ request, fetch }) => {
		const form = await request.formData();
		const token = String(form.get('token') ?? '').trim();
		const confirmReplace = form.get('confirm_replace') === 'true';
		try {
			await api<TelegramConnection>(fetch, '/api/telegram', {
				method: 'PUT',
				body: JSON.stringify({ token, confirm_replace: confirmReplace })
			});
		} catch (e) {
			if (e instanceof ApiFormError) {
				// Другой бот: токен возвращается в форму подтверждения, чтобы не вводить его заново.
				const detail = e.detail as { code?: string; channels_count?: number } | undefined;
				const replace =
					detail?.code === 'bot_change'
						? { token, channelsCount: detail.channels_count ?? 0 }
						: null;
				return fail(e.status, { action: 'connect', errors: e.errors, replace });
			}
			throw e;
		}
	},

	disconnect: async ({ fetch }) => {
		await api<void>(fetch, '/api/telegram', { method: 'DELETE' });
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
		let created: NotificationChannelCreated;
		try {
			created = await api<NotificationChannelCreated>(fetch, '/api/channels', {
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
		// Канал создан и тогда, когда приветственное сообщение не дошло: ошибку показываем у него.
		const welcome = created.test_message_error
			? { channelId: created.id, error: created.test_message_error }
			: null;
		return { created: chatId, welcome };
	},

	test: async ({ request, fetch }) => {
		const id = channelId(await request.formData());
		try {
			await api<NotificationChannel>(fetch, `/api/channels/${id}/test`, { method: 'POST' });
		} catch (e) {
			if (e instanceof ApiFormError) {
				return fail(e.status, { action: 'test', channelId: id, errors: e.errors });
			}
			throw e;
		}
		return { action: 'test', channelId: id, errors: {} as FieldErrors, sent: true };
	},

	rename: async ({ request, fetch }) => {
		const form = await request.formData();
		const id = channelId(form);
		const name = String(form.get('name') ?? '').trim();
		try {
			await api<NotificationChannel>(fetch, `/api/channels/${id}`, {
				method: 'PATCH',
				body: JSON.stringify({ name })
			});
		} catch (e) {
			if (e instanceof ApiFormError) {
				return fail(e.status, { action: 'rename', channelId: id, name, errors: e.errors });
			}
			throw e;
		}
	},

	delete: async ({ request, fetch }) => {
		const id = channelId(await request.formData());
		await api<void>(fetch, `/api/channels/${id}`, { method: 'DELETE' });
	}
};
