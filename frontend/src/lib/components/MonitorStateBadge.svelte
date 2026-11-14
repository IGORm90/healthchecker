<script lang="ts">
	import { STATE_LABELS, type MonitorState } from '#lib/monitors.ts';

	let { state }: { state: MonitorState } = $props();

	// Полные имена классов: Tailwind находит их в исходниках только целиком.
	const dot: Record<MonitorState, string> = {
		unknown: 'bg-state-unknown',
		up: 'bg-state-up',
		down: 'bg-state-down',
		paused: 'bg-state-paused'
	};
</script>

<span
	class="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 px-2 py-0.5 text-xs font-medium whitespace-nowrap dark:border-zinc-700"
>
	<span class={['size-2 rounded-full', dot[state]]} aria-hidden="true"></span>
	{STATE_LABELS[state]}
</span>
