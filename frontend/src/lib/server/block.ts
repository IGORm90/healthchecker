import { error, fail, type RequestEvent } from '@sveltejs/kit';
import type { UserSummary } from '#lib/auth.ts';
import { api, ApiFormError } from '#lib/server/api.ts';

/** Действия «Заблокировать» и «Разблокировать» для форм с полем `user_id`. */
function action(kind: 'block' | 'unblock') {
	return async ({ request, fetch }: RequestEvent) => {
		const id = Number((await request.formData()).get('user_id'));
		if (!Number.isInteger(id) || id <= 0) error(400, 'Некорректный пользователь');
		try {
			await api<UserSummary>(fetch, `/api/admin/users/${id}/${kind}`, { method: 'POST' });
		} catch (e) {
			// 409 — попытка заблокировать Суперадмина.
			if (e instanceof ApiFormError) return fail(e.status, { userId: id, errors: e.errors });
			throw e;
		}
	};
}

export const blockActions = { block: action('block'), unblock: action('unblock') };
