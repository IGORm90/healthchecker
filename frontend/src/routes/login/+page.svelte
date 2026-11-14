<script lang="ts">
	import { resolve } from '$app/paths';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<svelte:head>
	<title>Вход · Healthchecker</title>
</svelte:head>

<div class="mx-auto max-w-sm py-12">
	<div class="space-y-6 card p-6 text-center sm:p-8">
		<div class="space-y-2">
			<h1 class="text-2xl font-semibold tracking-tight">Вход</h1>
			<p class="text-sm text-zinc-600 dark:text-zinc-400">
				Healthchecker проверяет ваши HTTP-адреса по расписанию и сообщает в Telegram, когда они
				падают.
			</p>
		</div>

		{#if data.error}
			<p
				role="alert"
				class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-400"
			>
				{data.error}
			</p>
		{/if}

		<!-- Обычная ссылка, без клиентского роутера: /auth/login — серверный редирект в Telegram. -->
		<a href={resolve('/auth/login')} data-sveltekit-reload class="btn-primary w-full">
			Войти через Telegram
		</a>
	</div>
</div>
