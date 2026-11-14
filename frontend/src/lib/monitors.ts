// Ответы API Мониторов и Каналов оповещения и их подписи в интерфейсе.

export type MonitorState = 'unknown' | 'up' | 'down' | 'paused';

export type Header = { name: string; value: string };

export type Monitor = {
	id: number;
	name: string;
	url: string;
	method: string;
	headers: Header[];
	body: string | null;
	expected_status: number;
	expected_body: string | null;
	interval_seconds: number;
	channel_ids: number[];
	state: MonitorState;
	state_changed_at: string;
	next_check_at: string | null;
	last_check_at: string | null;
};

/** Поля Монитора, которые задаёт пользователь (тело запроса создания и правки). */
export type MonitorInput = {
	name: string;
	url: string;
	method: string;
	headers: Header[];
	body: string | null;
	expected_status: number;
	expected_body: string | null;
	interval_seconds: number;
	channel_ids: number[];
};

export const NEW_MONITOR: MonitorInput = {
	name: '',
	url: '',
	method: 'GET',
	headers: [],
	body: null,
	expected_status: 200,
	expected_body: null,
	interval_seconds: 300,
	channel_ids: []
};

export type NotificationChannel = {
	id: number;
	name: string;
	kind: 'telegram';
	telegram_chat_id: number;
	monitors_count: number;
	last_delivery_at: string | null;
	last_delivery_error: string | null;
};

export type TelegramConnection = { connected: boolean; bot_username: string | null };

export type DiscoveredChat = { chat_id: number; title: string; type: string; connected: boolean };

export const STATE_LABELS: Record<MonitorState, string> = {
	unknown: 'неизвестно',
	up: 'работает',
	down: 'упал',
	paused: 'на паузе'
};

export const METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'];

/** Методы без тела запроса: поле тела для них скрыто, backend его отбрасывает. */
export const METHODS_WITHOUT_BODY = new Set(['GET', 'HEAD']);

export const INTERVALS: { seconds: number; label: string }[] = [
	{ seconds: 30, label: '30 секунд' },
	{ seconds: 60, label: '1 минута' },
	{ seconds: 300, label: '5 минут' },
	{ seconds: 900, label: '15 минут' },
	{ seconds: 3600, label: '1 час' }
];

// Пояс фиксирован: страница рендерится на сервере, и время не должно зависеть от его пояса.
// UTC — как в текстах Оповещений.
const dateTime = new Intl.DateTimeFormat('ru-RU', {
	dateStyle: 'short',
	timeStyle: 'medium',
	timeZone: 'UTC'
});

export function formatTime(iso: string | null): string {
	return iso ? `${dateTime.format(new Date(iso))} UTC` : '—';
}
