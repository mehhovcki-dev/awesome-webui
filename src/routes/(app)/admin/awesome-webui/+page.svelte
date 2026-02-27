<script>
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import AwesomeWebUI from '$lib/components/admin/AwesomeWebUI.svelte';

	onMount(() => {
		goto('/admin/awesome-webui/authorization');
	});
</script>

<AwesomeWebUI />
