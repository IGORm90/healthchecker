<script lang="ts">
	import { enhance } from '$app/forms';
	import type { Monitor } from '#lib/monitors.ts';

	// Отправляет в действие `pause` или `resume` текущей страницы.
	let { monitor }: { monitor: Pick<Monitor, 'id' | 'name' | 'state'> } = $props();

	let paused = $derived(monitor.state === 'paused');
	let busy = $state(false);
</script>

<form
	method="POST"
	action={paused ? '?/resume' : '?/pause'}
	use:enhance={() => {
		busy = true;
		return async ({ update }) => {
			await update();
			busy = false;
		};
	}}
>
	<input type="hidden" name="id" value={monitor.id} />
	<button
		class="btn-secondary"
		disabled={busy}
		aria-label="{paused ? 'Возобновить' : 'Поставить на паузу'} монитор «{monitor.name}»"
		>{paused ? 'Возобновить' : 'Пауза'}</button
	>
</form>
