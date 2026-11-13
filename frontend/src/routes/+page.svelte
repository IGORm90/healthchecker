<script lang="ts">
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<h1>Healthchecker</h1>
<p>Backend: {data.liveness}</p>
