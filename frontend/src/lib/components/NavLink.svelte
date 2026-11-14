<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { PageRouteId } from '$app/types';
	import type { Snippet } from 'svelte';

	// Только маршруты без параметров: пункт навигации ведёт на раздел, а не на конкретную запись.
	type SectionRoute = Exclude<PageRouteId, `${string}[${string}`>;
	let { route, children }: { route: SectionRoute; children: Snippet } = $props();

	// Сравниваются id маршрутов, а не пути: resolve() при SSR отдаёт относительную ссылку.
	// Корень активен только сам по себе, остальные пункты — и на вложенных страницах.
	let active = $derived(
		route === '/'
			? page.route.id === '/'
			: page.route.id === route || !!page.route.id?.startsWith(`${route}/`)
	);
</script>

<a
	href={resolve(route)}
	aria-current={active ? 'page' : undefined}
	class={[
		'rounded-md px-3 py-2 text-sm font-medium transition-colors',
		active
			? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300'
			: 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100'
	]}
>
	{@render children()}
</a>
