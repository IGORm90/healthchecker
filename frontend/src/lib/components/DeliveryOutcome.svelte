<script lang="ts">
	import {
		attemptsLabel,
		DELIVERY_STATUS_COLORS,
		deliveryError,
		deliveryStatusLabel,
		type AlertDelivery
	} from '#lib/monitors.ts';

	let { delivery }: { delivery: AlertDelivery } = $props();

	let error = $derived(deliveryError(delivery));
</script>

<span class={DELIVERY_STATUS_COLORS[delivery.status]}>{deliveryStatusLabel(delivery)}</span
>{#if delivery.attempts > 1}, {attemptsLabel(delivery.attempts)}{/if}{#if error}
	— {error}{/if}
