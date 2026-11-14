<script lang="ts">
	import type { Liveness } from '#lib/liveness.ts';

	let { liveness }: { liveness: Liveness } = $props();

	const view: Record<Liveness, { label: string; dot: string }> = {
		ok: { label: 'работает', dot: 'bg-emerald-500' },
		error: { label: 'ошибка БД', dot: 'bg-amber-500' },
		unavailable: { label: 'недоступен', dot: 'bg-red-500' }
	};
</script>

<span class="inline-flex items-center gap-2">
	<span class={['size-2 rounded-full', view[liveness].dot]} aria-hidden="true"></span>
	Backend: {view[liveness].label}
</span>
