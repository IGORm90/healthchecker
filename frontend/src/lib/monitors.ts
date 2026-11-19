// Ответы API Мониторов и Каналов оповещения и их подписи в интерфейсе.

export type MonitorState = 'unknown' | 'up' | 'down' | 'paused';

export type Header = { name: string; value: string };

export type Monitor = {
	id: number;
	// Владелец: Суперадмин видит и чужие мониторы.
	user_id: number;
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
	// Недоставленные Оповещения: повторяются при следующих проверках.
	pending_deliveries: AlertDelivery[];
};

export type AlertKind = 'down' | 'recovered';

export type DeliveryStatus = 'pending' | 'delivered' | 'cancelled';

/** Доставка оповещения: судьба одного Оповещения в одном Канале оповещения. */
export type AlertDelivery = {
	alert_kind: AlertKind;
	alert_created_at: string;
	channel_id: number;
	channel_name: string;
	status: DeliveryStatus;
	attempts: number;
	first_attempt_at: string | null;
	last_attempt_at: string | null;
	error: string | null;
	telegram_error_code: number | null;
};

export type Check = {
	id: number;
	started_at: string;
	duration_ms: number;
	status_code: number | null;
	success: boolean;
	failure_reason: string | null;
	// Оповещение о смене Состояния, которую вызвала эта проверка.
	alert: { kind: AlertKind; deliveries: AlertDelivery[] } | null;
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

/** Значения формы правки из сохранённого Монитора. */
export function toInput(monitor: Monitor): MonitorInput {
	const { name, url, method, headers, body, expected_status, expected_body } = monitor;
	const { interval_seconds, channel_ids } = monitor;
	return {
		name,
		url,
		method,
		headers,
		body,
		expected_status,
		expected_body,
		interval_seconds,
		channel_ids
	};
}

export type NotificationChannel = {
	id: number;
	name: string;
	kind: 'telegram';
	telegram_chat_id: number;
	monitors_count: number;
	// Последняя попытка доставить Оповещение в этот канал.
	last_delivery: AlertDelivery | null;
};

/** Ответ на создание Канала: результат тестового сообщения не хранится. */
export type NotificationChannelCreated = NotificationChannel & {
	test_message_error: string | null;
};

export type TelegramConnection = { connected: boolean; bot_username: string | null };

export type DiscoveredChat = { chat_id: number; title: string; type: string; connected: boolean };

export const STATE_LABELS: Record<MonitorState, string> = {
	unknown: 'неизвестно',
	up: 'работает',
	down: 'упал',
	paused: 'на паузе'
};

export const ALERT_KIND_LABELS: Record<AlertKind, string> = {
	down: '«упал»',
	recovered: '«восстановился»'
};

export const DELIVERY_STATUS_LABELS: Record<DeliveryStatus, string> = {
	pending: 'не доставлено',
	delivered: 'доставлено',
	cancelled: 'отменено'
};

// Полные имена классов: Tailwind находит их в исходниках только целиком.
export const DELIVERY_STATUS_COLORS: Record<DeliveryStatus, string> = {
	pending: 'text-red-600 dark:text-red-400',
	delivered: 'text-emerald-700 dark:text-emerald-400',
	cancelled: 'text-zinc-500 dark:text-zinc-400'
};

/** Статус Доставки; «не доставлено» без попыток — ещё ждёт первой. */
export function deliveryStatusLabel(delivery: AlertDelivery): string {
	if (delivery.status === 'pending' && delivery.attempts === 0) return 'ожидает первой попытки';
	return DELIVERY_STATUS_LABELS[delivery.status];
}

/** Причина недоставки с кодом Telegram, если он есть; null — причины нет. */
export function deliveryError(delivery: AlertDelivery): string | null {
	if (delivery.status === 'delivered' || !delivery.error) return null;
	const code = delivery.telegram_error_code;
	return code ? `${delivery.error} (код ${code})` : delivery.error;
}

/** Доставки, которые уже не удались: ещё не опробованные — не сбой. */
export function failedDeliveries(deliveries: AlertDelivery[]): AlertDelivery[] {
	return deliveries.filter((delivery) => delivery.attempts > 0);
}

export function attemptsLabel(attempts: number): string {
	return plural(attempts, ['попытка', 'попытки', 'попыток']);
}

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

export function intervalLabel(seconds: number): string {
	return INTERVALS.find((interval) => interval.seconds === seconds)?.label ?? `${seconds} с`;
}

/** «1 монитор», «3 монитора», «5 мониторов»: формы для 1, 2–4 и 5+. */
export function plural(n: number, [one, few, many]: [string, string, string]): string {
	const mod10 = n % 10;
	const mod100 = n % 100;
	if (mod10 === 1 && mod100 !== 11) return `${n} ${one}`;
	if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} ${few}`;
	return `${n} ${many}`;
}

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
