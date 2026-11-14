<script lang="ts">
	import { resolve } from '$app/paths';
	import EmptyState from '#lib/components/EmptyState.svelte';
	import MonitorStateBadge from '#lib/components/MonitorStateBadge.svelte';
	import PauseButton from '#lib/components/PauseButton.svelte';
	import { formatTime } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Мониторы · Healthchecker</title>
</svelte:head>

<div class="mb-6 flex flex-wrap items-center justify-between gap-3">
	<h1 class="text-2xl font-semibold tracking-tight">Мониторы</h1>
	{#if data.monitors.length > 0}
		<a href={resolve('/monitors/new')} class="btn-primary">Создать монитор</a>
	{/if}
</div>

{#if data.monitors.length === 0}
	<EmptyState title="Мониторов пока нет" description="Монитор проверяет HTTP-адрес по расписанию.">
		<a href={resolve('/monitors/new')} class="btn-primary">Создать монитор</a>
	</EmptyState>
{:else}
	<div class="overflow-x-auto card">
		<table class="w-full text-left text-sm">
			<thead class="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
				<tr>
					<th class="px-4 py-3 font-medium">Название</th>
					<th class="px-4 py-3 font-medium">URL</th>
					<th class="px-4 py-3 font-medium">Состояние</th>
					<th class="px-4 py-3 font-medium whitespace-nowrap">Последняя проверка</th>
					<th class="relative px-4 py-3"><span class="sr-only">Действия</span></th>
				</tr>
			</thead>
			<tbody class="divide-y divide-zinc-200 dark:divide-zinc-800">
				{#each data.monitors as monitor (monitor.id)}
					<tr>
						<td class="px-4 py-3 font-medium">
							<a
								class="text-indigo-600 hover:underline dark:text-indigo-400"
								href={resolve('/monitors/[id]', { id: String(monitor.id) })}>{monitor.name}</a
							>
						</td>
						<td
							class="max-w-xs truncate px-4 py-3 text-zinc-600 dark:text-zinc-400"
							title={monitor.url}
						>
							<span class="font-mono text-xs">{monitor.method}</span>
							{monitor.url}
						</td>
						<td class="px-4 py-3"><MonitorStateBadge state={monitor.state} /></td>
						<td class="px-4 py-3 whitespace-nowrap text-zinc-600 dark:text-zinc-400">
							{formatTime(monitor.last_check_at)}
						</td>
						<td class="px-4 py-3 text-right"><PauseButton {monitor} /></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
