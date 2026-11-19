<script lang="ts">
	import { resolve } from '$app/paths';
	import BlockButton from '#lib/components/BlockButton.svelte';
	import EmptyState from '#lib/components/EmptyState.svelte';
	import MonitorStateBadge from '#lib/components/MonitorStateBadge.svelte';
	import PauseButton from '#lib/components/PauseButton.svelte';
	import UndeliveredAlertBadge from '#lib/components/UndeliveredAlertBadge.svelte';
	import { formatTime } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
	let profile = $derived(data.profile);
</script>

<svelte:head>
	<title>{profile.name} · Пользователи · Healthchecker</title>
</svelte:head>

<div class="mb-6 flex flex-wrap items-start justify-between gap-3">
	<div class="min-w-0 space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight break-words">{profile.name}</h1>
		<p class="text-sm text-zinc-600 dark:text-zinc-400">
			{#if profile.username}@{profile.username} ·
			{/if}Telegram ID
			<span class="font-mono text-xs">{profile.telegram_id}</span>
		</p>
		<p class="text-sm text-zinc-600 dark:text-zinc-400">
			{#if profile.is_superadmin}
				<span class="text-indigo-700 dark:text-indigo-300">суперадмин</span>
			{:else if profile.blocked_at}
				<span class="text-red-600 dark:text-red-400"
					>заблокирован {formatTime(profile.blocked_at)}</span
				> — мониторы не проверяются
			{:else}
				последний вход {formatTime(profile.last_login_at)}
			{/if}
		</p>
	</div>
	{#if !profile.is_superadmin}<BlockButton user={profile} />{/if}
</div>

{#if form && 'errors' in form && form.errors}
	<p
		role="alert"
		class="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-400"
	>
		{Object.values(form.errors).join('; ')}
	</p>
{/if}

<section>
	<h2 class="mb-3 font-semibold">Мониторы</h2>
	{#if data.monitors.length === 0}
		<EmptyState
			title="Мониторов нет"
			description="Пользователь ещё не создал ни одного монитора."
		/>
	{:else}
		<div class="overflow-x-auto card">
			<table class="w-full text-left text-sm">
				<thead
					class="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400"
				>
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
									href={resolve('/(app)/monitors/[id]', { id: String(monitor.id) })}
									>{monitor.name}</a
								>
							</td>
							<td
								class="max-w-xs truncate px-4 py-3 text-zinc-600 dark:text-zinc-400"
								title={monitor.url}
							>
								<span class="font-mono text-xs">{monitor.method}</span>
								{monitor.url}
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-wrap items-center gap-1.5">
									<MonitorStateBadge state={monitor.state} />
									<UndeliveredAlertBadge deliveries={monitor.pending_deliveries} />
								</div>
							</td>
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
</section>

<a
	class="mt-6 inline-block text-sm text-indigo-600 hover:underline dark:text-indigo-400"
	href={resolve('/(app)/admin/users')}>← Все пользователи</a
>
