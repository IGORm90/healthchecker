<script lang="ts">
	import {
		ALERT_KIND_LABELS,
		deliveryError,
		failedDeliveries,
		type AlertDelivery
	} from '#lib/monitors.ts';

	let { deliveries }: { deliveries: AlertDelivery[] } = $props();

	let failed = $derived(failedDeliveries(deliveries));
	let details = $derived(
		failed
			.map((d) => `${ALERT_KIND_LABELS[d.alert_kind]} → ${d.channel_name}: ${deliveryError(d)}`)
			.join('\n')
	);
</script>

{#if failed.length > 0}
	<span
		class="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium whitespace-nowrap text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
		title={details}
	>
		⚠ оповещение не доставлено
	</span>
{/if}
