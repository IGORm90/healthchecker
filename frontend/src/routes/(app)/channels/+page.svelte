<script lang="ts">
	import { enhance, type SubmitFunction } from '$app/forms';
	import { resolve } from '$app/paths';
	import EmptyState from '#lib/components/EmptyState.svelte';
	import {
		formatTime,
		plural,
		type DiscoveredChat,
		type NotificationChannel
	} from '#lib/monitors.ts';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();

	// Telegram отдаёт обновление один раз: найденные чаты живут на странице,
	// пока их не подключат, а не в ответе последнего действия.
	let discovered: DiscoveredChat[] | null = $state(null);
	$effect(() => {
		if (form && 'discovered' in form && form.discovered) discovered = form.discovered;
	});

	let busy = $state(false);
	const submit: SubmitFunction = () => {
		busy = true;
		return async ({ update }) => {
			await update();
			busy = false;
		};
	};

	function errorsFor(action: string) {
		return form && 'action' in form && form.action === action ? form.errors : {};
	}

	/** Ошибка действия над конкретным Каналом оповещения. */
	function channelError(action: string, id: number): string | null {
		if (!form || !('channelId' in form) || form.action !== action || form.channelId !== id) {
			return null;
		}
		return Object.values(form.errors).join('; ');
	}

	// confirm() — в enhance: preventDefault() в onsubmit enhance не останавливает.
	function deleteChannel(channel: NotificationChannel): SubmitFunction {
		return (input) => {
			const usage =
				channel.monitors_count > 0
					? ` Мониторов с этим каналом: ${channel.monitors_count} — канал будет от них отвязан.`
					: '';
			if (!confirm(`Удалить канал оповещения «${channel.name}»?${usage}`)) return input.cancel();
			return submit(input);
		};
	}

	const rename: SubmitFunction = ({ formElement }) => {
		busy = true;
		return async ({ result, update }) => {
			if (result.type === 'success') formElement.closest('details')?.removeAttribute('open');
			await update();
			busy = false;
		};
	};

	// Ответ 409 на токен другого бота: ждём подтверждения удаления Каналов.
	let replace = $derived(form && 'replace' in form ? form.replace : null);

	const disconnect: SubmitFunction = (input) => {
		const channels =
			data.channels.length > 0
				? ` Будут удалены ${plural(data.channels.length, ['канал', 'канала', 'каналов'])} оповещения.`
				: '';
		if (!confirm(`Отключить Telegram?${channels}`)) return input.cancel();
		return submit(input);
	};

	let createErrors = $derived(form && 'action' in form && form.action === 'create' ? form : null);
</script>

{#snippet tokenForm(label: string)}
	{#if replace}
		<div
			class="space-y-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-500/10 dark:text-amber-200"
		>
			<p>
				Это другой бот. Его подключение удалит {plural(replace.channelsCount, [
					'канал',
					'канала',
					'каналов'
				])} оповещения — их придётся подключить заново.
			</p>
			<form method="POST" action="?/connect" class="flex flex-wrap gap-2" use:enhance={submit}>
				<input type="hidden" name="token" value={replace.token} />
				<input type="hidden" name="confirm_replace" value="true" />
				<button class="btn-danger" disabled={busy}>Сменить бота и удалить каналы</button>
				<a class="btn-secondary" href={resolve('/(app)/channels')}>Отмена</a>
			</form>
		</div>
	{:else}
		<form method="POST" action="?/connect" class="flex flex-wrap gap-2" use:enhance={submit}>
			<input
				class="input max-w-md"
				name="token"
				type="password"
				autocomplete="off"
				required
				placeholder="123456:ABC-DEF…"
				aria-label="Токен бота"
			/>
			<button class="btn-primary" disabled={busy}>{label}</button>
		</form>
		{#if errorsFor('connect').token || errorsFor('connect')['']}
			<p class="field-error">{errorsFor('connect').token ?? errorsFor('connect')['']}</p>
		{/if}
	{/if}
{/snippet}

<svelte:head>
	<title>Каналы оповещения · Healthchecker</title>
</svelte:head>

<h1 class="mb-6 text-2xl font-semibold tracking-tight">Каналы оповещения</h1>

<div class="space-y-6">
	<section class="space-y-4 card p-4 sm:p-6">
		<h2 class="font-semibold">Подключение Telegram</h2>

		{#if !data.telegram.connected}
			<ol class="list-decimal space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
				<li>Создайте бота у @BotFather командой <code>/newbot</code>.</li>
				<li>Вставьте выданный токен ниже.</li>
			</ol>
			{@render tokenForm('Подключить')}
		{:else}
			<div class="flex flex-wrap items-center justify-between gap-2">
				<p class="text-sm">
					Бот <span class="font-medium">@{data.telegram.bot_username}</span> подключён.
				</p>
				<form method="POST" action="?/disconnect" use:enhance={disconnect}>
					<button class="btn-danger" disabled={busy}>Отключить Telegram</button>
				</form>
			</div>
			<details
				class="text-sm"
				open={replace !== null || Object.keys(errorsFor('connect')).length > 0 || undefined}
			>
				<summary class="cursor-pointer text-indigo-600 dark:text-indigo-400">Сменить бота</summary>
				<div class="mt-3 space-y-3">
					<p class="text-zinc-600 dark:text-zinc-400">
						Токен того же бота сохранит каналы. Токен другого бота удалит все Каналы оповещения —
						перед этим попросим подтверждение.
					</p>
					{@render tokenForm('Сохранить токен')}
				</div>
			</details>
			<p class="text-sm text-zinc-600 dark:text-zinc-400">
				Добавьте бота в группу или напишите ему в личные сообщения, затем нажмите «Найти чаты».
				Telegram хранит такие события 24 часа.
			</p>
			<form method="POST" action="?/discover" use:enhance={submit}>
				<button class="btn-secondary" disabled={busy}>Найти чаты</button>
			</form>
			{#if errorsFor('discover')['']}
				<p class="field-error">{errorsFor('discover')['']}</p>
			{/if}

			{#if discovered !== null}
				{#if discovered.length === 0}
					<p class="text-sm text-zinc-500 dark:text-zinc-400">
						Новых чатов не найдено. Добавьте бота в чат и повторите поиск.
					</p>
				{:else}
					<ul
						class="divide-y divide-zinc-200 rounded-md border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800"
					>
						{#each discovered as chat (chat.chat_id)}
							<li class="p-3">
								{#if chat.connected}
									<p class="text-sm">
										{chat.title}
										<span class="text-zinc-500 dark:text-zinc-400">— уже подключён</span>
									</p>
								{:else}
									<form
										method="POST"
										action="?/create"
										class="flex flex-wrap items-center gap-2"
										use:enhance={() => {
											busy = true;
											return async ({ result, update }) => {
												if (result.type === 'success') chat.connected = true;
												await update();
												busy = false;
											};
										}}
									>
										<input type="hidden" name="telegram_chat_id" value={chat.chat_id} />
										<input
											class="input max-w-xs"
											name="name"
											required
											maxlength="200"
											value={chat.title}
											aria-label="Название канала для чата {chat.title}"
										/>
										<span class="text-xs text-zinc-500 dark:text-zinc-400">{chat.type}</span>
										<button class="btn-primary" disabled={busy}>Подключить</button>
									</form>
									{#if createErrors?.chatId === chat.chat_id}
										<p class="field-error">
											{Object.values(createErrors.errors).join('; ')}
										</p>
									{/if}
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			{/if}
		{/if}
	</section>

	{#if data.channels.length === 0}
		<EmptyState
			title="Каналов оповещения пока нет"
			description="Подключите Telegram и найдите чат, куда слать оповещения."
		/>
	{:else}
		<section class="overflow-x-auto card">
			<table class="w-full text-left text-sm">
				<thead
					class="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800 dark:text-zinc-400"
				>
					<tr>
						<th class="px-4 py-3 font-medium">Название</th>
						<th class="px-4 py-3 font-medium">Мониторов</th>
						<th class="px-4 py-3 font-medium whitespace-nowrap">Последняя отправка</th>
						<th class="relative px-4 py-3"><span class="sr-only">Действия</span></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-zinc-200 dark:divide-zinc-800">
					{#each data.channels as channel (channel.id)}
						<tr>
							<td class="px-4 py-3 font-medium">
								{channel.name}
								{#if channelError('rename', channel.id) !== null}
									<p class="field-error font-normal">{channelError('rename', channel.id)}</p>
								{/if}
							</td>
							<td class="px-4 py-3">{channel.monitors_count}</td>
							<td class="px-4 py-3">
								<span class="whitespace-nowrap">{formatTime(channel.last_delivery_at)}</span>
								{#if channel.last_delivery_error}
									<p class="text-red-600 dark:text-red-400">{channel.last_delivery_error}</p>
								{/if}
								{#if channelError('test', channel.id) !== null}
									<p class="field-error">{channelError('test', channel.id)}</p>
								{/if}
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-wrap justify-end gap-2">
									<form method="POST" action="?/test" use:enhance={submit}>
										<input type="hidden" name="id" value={channel.id} />
										<button class="btn-secondary" disabled={busy}>Тест</button>
									</form>
									<details
										class="group"
										open={channelError('rename', channel.id) !== null || undefined}
									>
										<summary class="btn-secondary cursor-pointer list-none group-open:hidden"
											>Переименовать</summary
										>
										<form
											method="POST"
											action="?/rename"
											class="flex flex-wrap gap-2"
											use:enhance={rename}
										>
											<input type="hidden" name="id" value={channel.id} />
											<input
												class="input w-48"
												name="name"
												required
												maxlength="200"
												value={form && 'name' in form && channelError('rename', channel.id) !== null
													? form.name
													: channel.name}
												aria-label="Новое название канала «{channel.name}»"
											/>
											<button class="btn-primary" disabled={busy}>Сохранить</button>
											<button
												type="button"
												class="btn-secondary"
												onclick={(event) =>
													event.currentTarget.closest('details')?.removeAttribute('open')}
												>Отмена</button
											>
										</form>
									</details>
									<form method="POST" action="?/delete" use:enhance={deleteChannel(channel)}>
										<input type="hidden" name="id" value={channel.id} />
										<button class="btn-danger" disabled={busy}>Удалить</button>
									</form>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}
</div>
