<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import LivenessIndicator from '#lib/components/LivenessIndicator.svelte';
	import NavLink from '#lib/components/NavLink.svelte';
	import { resolve } from '$app/paths';
	import type { LayoutProps } from './$types';

	let { data, children }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="flex min-h-dvh flex-col">
	<header class="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
		<div class="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
			<a href={resolve('/')} class="font-semibold tracking-tight">Healthchecker</a>
			<nav class="flex gap-1">
				<NavLink route="/">Мониторы</NavLink>
				<NavLink route="/channels">Каналы оповещения</NavLink>
			</nav>
		</div>
	</header>

	<main class="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
		{@render children()}
	</main>

	<footer class="border-t border-zinc-200 dark:border-zinc-800">
		<div class="mx-auto max-w-5xl px-4 py-3 text-sm text-zinc-500 dark:text-zinc-400">
			<LivenessIndicator liveness={data.liveness} />
		</div>
	</footer>
</div>
