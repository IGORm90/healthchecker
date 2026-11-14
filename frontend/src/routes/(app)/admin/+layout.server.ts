import { error } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

// Раздел Суперадмина: остальным — 404, как и в API.
export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.user?.is_superadmin) error(404, 'Не найдено');
};
