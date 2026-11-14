import { error } from '@sveltejs/kit';
import type { MonitorInput } from '#lib/monitors.ts';

/** id Монитора из параметра маршрута; иначе — 404. */
export function monitorIdParam(raw: string): number {
	const id = Number(raw);
	if (!Number.isInteger(id) || id <= 0) error(404, 'Монитор не найден');
	return id;
}

function text(form: FormData, name: string): string {
	return String(form.get(name) ?? '').trim();
}

/** Значения формы Монитора; пустые строки заголовков отбрасываются. */
export function readMonitorForm(form: FormData): MonitorInput {
	const names = form.getAll('header_name').map(String);
	const values = form.getAll('header_value').map(String);
	return {
		name: text(form, 'name'),
		url: text(form, 'url'),
		method: text(form, 'method'),
		headers: names
			.map((name, i) => ({ name: name.trim(), value: values[i] ?? '' }))
			.filter((header) => header.name || header.value),
		body: String(form.get('body') ?? '') || null,
		expected_status: Number(text(form, 'expected_status')),
		expected_body: String(form.get('expected_body') ?? '') || null,
		interval_seconds: Number(text(form, 'interval_seconds')),
		channel_ids: form.getAll('channel_ids').map(Number)
	};
}
