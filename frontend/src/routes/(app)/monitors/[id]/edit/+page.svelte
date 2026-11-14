<script lang="ts">
	import MonitorForm from '#lib/components/MonitorForm.svelte';
	import { toInput } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<svelte:head>
	<title>Изменить «{data.monitor.name}» · Healthchecker</title>
</svelte:head>

<h1 class="mb-2 text-2xl font-semibold tracking-tight break-words">
	Изменить «{data.monitor.name}»
</h1>
<p class="mb-6 text-sm text-zinc-600 dark:text-zinc-400">
	Изменение адреса, запроса или Ожидания сбросит состояние монитора.
</p>

<MonitorForm
	values={form?.values ?? toInput(data.monitor)}
	errors={form?.errors}
	channels={data.channels}
	submitLabel="Сохранить"
	monitorId={data.monitor.id}
/>
