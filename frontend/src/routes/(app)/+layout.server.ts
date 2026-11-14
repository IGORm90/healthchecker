import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

// Закрытые страницы: без входа — на /login.
export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.user) redirect(303, '/login');
	return { user: locals.user };
};
