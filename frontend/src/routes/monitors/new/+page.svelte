<script lang="ts">
	import MonitorForm from '#lib/components/MonitorForm.svelte';
	import { NEW_MONITOR } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<svelte:head>
	<title>Новый монитор · Healthchecker</title>
</svelte:head>

<h1 class="mb-6 text-2xl font-semibold tracking-tight">Новый монитор</h1>

<MonitorForm
	values={form?.values ?? NEW_MONITOR}
	errors={form?.errors}
	channels={data.channels}
	submitLabel="Создать монитор"
/>
