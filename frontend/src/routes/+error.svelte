<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';

	let title = $derived(page.status === 404 ? 'Страница не найдена' : 'Что-то пошло не так');
</script>

<svelte:head>
	<title>{title} · Healthchecker</title>
</svelte:head>

<div class="py-12 text-center">
	<p class="text-sm font-semibold text-indigo-600 dark:text-indigo-400">{page.status}</p>
	<h1 class="mt-2 text-2xl font-semibold tracking-tight">{title}</h1>
	{#if page.status !== 404 && page.error?.message}
		<p class="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{page.error.message}</p>
	{/if}
	<a
		href={resolve('/(app)')}
		class="mt-6 inline-block text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
	>
		К мониторам
	</a>
</div>
