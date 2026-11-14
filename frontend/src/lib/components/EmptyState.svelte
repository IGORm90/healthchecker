<script lang="ts">
	let { title, description }: { title: string; description: string } = $props();
</script>

<div
	class="rounded-lg border border-dashed border-zinc-300 px-6 py-12 text-center dark:border-zinc-700"
>
	<p class="font-medium text-zinc-900 dark:text-zinc-100">{title}</p>
	<p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{description}</p>
</div>
