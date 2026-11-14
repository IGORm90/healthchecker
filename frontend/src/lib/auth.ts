/** Вошедший Пользователь: ответ `GET /api/auth/me`. */
export type User = {
	id: number;
	telegram_id: number;
	name: string;
	username: string | null;
	photo_url: string | null;
	is_superadmin: boolean;
};

/** Причины возврата на `/login`: ключ — параметр `?error=`. */
export const LOGIN_ERRORS: Record<string, string> = {
	denied: 'Вход отменён в Telegram.',
	state: 'Ссылка входа устарела или подменена. Попробуйте ещё раз.',
	blocked: 'Доступ заблокирован администратором.',
	failed: 'Telegram не подтвердил вход. Попробуйте ещё раз.',
	not_configured: 'Вход через Telegram не настроен на сервере.'
};
