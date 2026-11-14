import { error, type RequestEvent } from '@sveltejs/kit';
import type { Monitor } from '#lib/monitors.ts';
import { api } from '#lib/server/api.ts';

/** Действия «Пауза» и «Возобновить» для форм с полем `id` Монитора. */
function action(kind: 'pause' | 'resume') {
	return async ({ request, fetch }: RequestEvent) => {
		const id = Number((await request.formData()).get('id'));
		if (!Number.isInteger(id) || id <= 0) error(400, 'Некорректный монитор');
		await api<Monitor>(fetch, `/api/monitors/${id}/${kind}`, { method: 'POST' });
	};
}

export const pauseActions = { pause: action('pause'), resume: action('resume') };
