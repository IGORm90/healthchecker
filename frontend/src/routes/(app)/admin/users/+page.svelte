<script lang="ts">
	import { resolve } from '$app/paths';
	import BlockButton from '#lib/components/BlockButton.svelte';
	import { formatTime } from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();
</script>

<svelte:head>
	<title>Пользователи · Healthchecker</title>
</svelte:head>

<h1 class="mb-6 text-2xl font-semibold tracking-tight">Пользователи</h1>

{#if form?.errors}
	<p
		role="alert"
		class="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-400"
	>
		{Object.values(form.errors).join('; ')}
	</p>
{/if}

<div class="overflow-x-auto card">
	<table class="w-full text-left text-sm">
		<thead class="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
			<tr>
				<th class="px-4 py-3 font-medium">Пользователь</th>
				<th class="px-4 py-3 font-medium whitespace-nowrap">Telegram ID</th>
				<th class="px-4 py-3 font-medium whitespace-nowrap">Регистрация</th>
				<th class="px-4 py-3 font-medium whitespace-nowrap">Последний вход</th>
				<th class="px-4 py-3 font-medium">Мониторы</th>
				<th class="px-4 py-3 font-medium">Статус</th>
				<th class="relative px-4 py-3"><span class="sr-only">Действия</span></th>
			</tr>
		</thead>
		<tbody class="divide-y divide-zinc-200 dark:divide-zinc-800">
			{#each data.users as user (user.id)}
				<tr>
					<td class="px-4 py-3">
						<a
							class="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
							href={resolve('/(app)/admin/users/[id]', { id: String(user.id) })}>{user.name}</a
						>
						{#if user.username}
							<span class="block text-zinc-500 dark:text-zinc-400">@{user.username}</span>
						{/if}
					</td>
					<td class="px-4 py-3 font-mono text-xs">{user.telegram_id}</td>
					<td class="px-4 py-3 whitespace-nowrap text-zinc-600 dark:text-zinc-400">
						{formatTime(user.created_at)}
					</td>
					<td class="px-4 py-3 whitespace-nowrap text-zinc-600 dark:text-zinc-400">
						{formatTime(user.last_login_at)}
					</td>
					<td class="px-4 py-3">{user.monitors_count}</td>
					<td class="px-4 py-3 whitespace-nowrap">
						{#if user.is_superadmin}
							<span class="text-indigo-700 dark:text-indigo-300">суперадмин</span>
						{:else if user.blocked_at}
							<span class="text-red-600 dark:text-red-400">заблокирован</span>
						{:else}
							<span class="text-zinc-600 dark:text-zinc-400">активен</span>
						{/if}
					</td>
					<td class="px-4 py-3 text-right">
						{#if !user.is_superadmin}<BlockButton {user} />{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
