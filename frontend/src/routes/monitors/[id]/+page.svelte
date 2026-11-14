<script lang="ts">
	import { resolve } from '$app/paths';
	import EmptyState from '#lib/components/EmptyState.svelte';
	import MonitorStateBadge from '#lib/components/MonitorStateBadge.svelte';
	import PauseButton from '#lib/components/PauseButton.svelte';
	import { formatTime, intervalLabel } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let monitor = $derived(data.monitor);
</script>

<svelte:head>
	<title>{monitor.name} · Healthchecker</title>
</svelte:head>

<div class="mb-6 flex flex-wrap items-start justify-between gap-3">
	<div class="min-w-0 space-y-2">
		<h1 class="text-2xl font-semibold tracking-tight break-words">{monitor.name}</h1>
		<p class="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
			<MonitorStateBadge state={monitor.state} />
			с {formatTime(monitor.state_changed_at)}
		</p>
	</div>
	<div class="flex flex-wrap gap-2">
		<a class="btn-secondary" href={resolve('/monitors/[id]/edit', { id: String(monitor.id) })}
			>Изменить</a
		>
		<PauseButton {monitor} />
		<form
			method="POST"
			action="?/delete"
			onsubmit={(event) => {
				if (!confirm(`Удалить монитор «${monitor.name}» вместе с историей проверок?`)) {
					event.preventDefault();
				}
			}}
		>
			<button class="btn-danger">Удалить</button>
		</form>
	</div>
</div>

<div class="space-y-6">
	<section class="card p-4 sm:p-6">
		<dl class="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[12rem_1fr]">
			<dt class="text-zinc-500 dark:text-zinc-400">Запрос</dt>
			<dd class="min-w-0 break-all">
				<span class="font-mono text-xs">{monitor.method}</span>
				{monitor.url}
			</dd>

			<dt class="text-zinc-500 dark:text-zinc-400">Ожидание</dt>
			<dd class="min-w-0 break-words">
				код {monitor.expected_status}{#if monitor.expected_body}, тело содержит «{monitor.expected_body}»{/if}
			</dd>

			<dt class="text-zinc-500 dark:text-zinc-400">Проверять каждые</dt>
			<dd>{intervalLabel(monitor.interval_seconds)}</dd>

			<dt class="text-zinc-500 dark:text-zinc-400">Каналы оповещения</dt>
			<dd>
				{#if data.channels.length > 0}
					{data.channels.map((channel) => channel.name).join(', ')}
				{:else}
					<span class="text-zinc-500 dark:text-zinc-400">нет</span>
				{/if}
			</dd>
		</dl>
	</section>

	<section>
		<h2 class="mb-3 font-semibold">Последние проверки</h2>
		{#if data.checks.length === 0}
			<EmptyState
				title="Проверок пока нет"
				description={monitor.state === 'paused'
					? 'Монитор на паузе.'
					: 'Первая проверка появится в ближайшие секунды.'}
			/>
		{:else}
			<div class="overflow-x-auto card">
				<table class="w-full text-left text-sm">
					<thead
						class="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400"
					>
						<tr>
							<th class="px-4 py-3 font-medium">Время</th>
							<th class="px-4 py-3 font-medium">Длительность</th>
							<th class="px-4 py-3 font-medium">Код</th>
							<th class="px-4 py-3 font-medium">Результат</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-zinc-200 dark:divide-zinc-800">
						{#each data.checks as check (check.id)}
							<tr>
								<td class="px-4 py-3 whitespace-nowrap">{formatTime(check.started_at)}</td>
								<td class="px-4 py-3 whitespace-nowrap">{check.duration_ms} мс</td>
								<td class="px-4 py-3">{check.status_code ?? '—'}</td>
								<td class="px-4 py-3">
									{#if check.success}
										<span class="text-emerald-700 dark:text-emerald-400">успех</span>
									{:else}
										<span class="text-red-600 dark:text-red-400">{check.failure_reason}</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<a class="text-sm text-indigo-600 hover:underline dark:text-indigo-400" href={resolve('/')}
		>← Все мониторы</a
	>
</div>
