<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import {
		INTERVALS,
		METHODS,
		METHODS_WITHOUT_BODY,
		type Header,
		type MonitorInput,
		type NotificationChannel
	} from '#lib/monitors.ts';

	let {
		values,
		errors = {},
		channels,
		submitLabel
	}: {
		values: MonitorInput;
		errors?: Record<string, string>;
		channels: NotificationChannel[];
		submitLabel: string;
	} = $props();

	// Поля, которые меняют форму на лету; остальные — обычные поля с начальным значением.
	// При ошибке без JS страница рендерится заново с введёнными значениями.
	// svelte-ignore state_referenced_locally
	let method = $state(values.method);
	// svelte-ignore state_referenced_locally
	let headers: Header[] = $state(values.headers.map((h) => ({ ...h })));
	let submitting = $state(false);
</script>

<form
	method="POST"
	class="space-y-6"
	use:enhance={() => {
		submitting = true;
		return async ({ update }) => {
			await update({ reset: false });
			submitting = false;
		};
	}}
>
	{#if errors['']}
		<p
			class="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300"
		>
			{errors['']}
		</p>
	{/if}

	<section class="space-y-4 card p-4 sm:p-6">
		<h2 class="font-semibold">Что проверять</h2>

		<div>
			<label class="label" for="name">Название</label>
			<input class="input" id="name" name="name" required maxlength="200" value={values.name} />
			{#if errors.name}<p class="field-error">{errors.name}</p>{/if}
		</div>

		<div class="grid gap-4 sm:grid-cols-[8rem_1fr]">
			<div>
				<label class="label" for="method">Метод</label>
				<select class="input" id="method" name="method" bind:value={method}>
					{#each METHODS as m (m)}<option value={m}>{m}</option>{/each}
				</select>
			</div>
			<div>
				<label class="label" for="url">URL</label>
				<input
					class="input"
					id="url"
					name="url"
					type="url"
					required
					placeholder="https://example.com/health"
					value={values.url}
				/>
				{#if errors.url}<p class="field-error">{errors.url}</p>{/if}
			</div>
		</div>

		<fieldset>
			<legend class="label">Заголовки</legend>
			<div class="space-y-2">
				{#each headers as header, i (i)}
					<div class="flex gap-2">
						<input
							class="input"
							name="header_name"
							placeholder="Имя"
							aria-label="Имя заголовка"
							bind:value={header.name}
						/>
						<input
							class="input"
							name="header_value"
							placeholder="Значение"
							aria-label="Значение заголовка"
							bind:value={header.value}
						/>
						<button
							type="button"
							class="btn-secondary"
							aria-label="Удалить заголовок"
							onclick={() => headers.splice(i, 1)}>✕</button
						>
					</div>
				{/each}
			</div>
			<button
				type="button"
				class="mt-2 btn-secondary"
				onclick={() => headers.push({ name: '', value: '' })}>Добавить заголовок</button
			>
			{#if errors.headers}<p class="field-error">{errors.headers}</p>{/if}
		</fieldset>

		{#if !METHODS_WITHOUT_BODY.has(method)}
			<div>
				<label class="label" for="body">Тело запроса</label>
				<textarea class="input font-mono" id="body" name="body" rows="4"
					>{values.body ?? ''}</textarea
				>
				<p class="hint">Отправляется как есть; Content-Type задайте заголовком.</p>
				{#if errors.body}<p class="field-error">{errors.body}</p>{/if}
			</div>
		{/if}
	</section>

	<section class="space-y-4 card p-4 sm:p-6">
		<h2 class="font-semibold">Ожидание</h2>
		<div class="grid gap-4 sm:grid-cols-[10rem_1fr]">
			<div>
				<label class="label" for="expected_status">Код ответа</label>
				<input
					class="input"
					id="expected_status"
					name="expected_status"
					type="number"
					min="100"
					max="599"
					required
					value={values.expected_status}
				/>
				{#if errors.expected_status}<p class="field-error">{errors.expected_status}</p>{/if}
			</div>
			<div>
				<label class="label" for="expected_body">Тело содержит</label>
				<input
					class="input"
					id="expected_body"
					name="expected_body"
					placeholder="необязательно"
					value={values.expected_body ?? ''}
				/>
				<p class="hint">Подстрока с учётом регистра, ищется в первом мегабайте ответа.</p>
				{#if errors.expected_body}<p class="field-error">{errors.expected_body}</p>{/if}
			</div>
		</div>
	</section>

	<section class="space-y-4 card p-4 sm:p-6">
		<h2 class="font-semibold">Расписание и оповещения</h2>
		<div class="max-w-xs">
			<label class="label" for="interval_seconds">Проверять каждые</label>
			<select class="input" id="interval_seconds" name="interval_seconds">
				{#each INTERVALS as interval (interval.seconds)}
					<option value={interval.seconds} selected={interval.seconds === values.interval_seconds}
						>{interval.label}</option
					>
				{/each}
			</select>
		</div>

		<fieldset>
			<legend class="label">Каналы оповещения</legend>
			{#if channels.length === 0}
				<p class="text-sm text-zinc-500 dark:text-zinc-400">
					Каналов оповещения пока нет —
					<a
						class="text-indigo-600 hover:underline dark:text-indigo-400"
						href={resolve('/channels')}>подключите Telegram</a
					>.
				</p>
			{:else}
				<div class="space-y-2">
					{#each channels as channel (channel.id)}
						<label class="flex items-center gap-2 text-sm">
							<input
								type="checkbox"
								class="rounded border-zinc-300 text-indigo-600 dark:border-zinc-600 dark:bg-zinc-800"
								name="channel_ids"
								value={channel.id}
								checked={values.channel_ids.includes(channel.id)}
							/>
							{channel.name}
						</label>
					{/each}
				</div>
			{/if}
			{#if errors.channel_ids}<p class="field-error">{errors.channel_ids}</p>{/if}
		</fieldset>
	</section>

	<div class="flex gap-3">
		<button class="btn-primary" disabled={submitting}>{submitLabel}</button>
		<a class="btn-secondary" href={resolve('/')}>Отмена</a>
	</div>
</form>
