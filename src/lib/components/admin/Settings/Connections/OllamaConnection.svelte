<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import ManageOllamaModal from './ManageOllamaModal.svelte';
	import Download from '$lib/components/icons/Download.svelte';

	export let onDelete: () => void = () => {};
	export let onSubmit: (connection?: any) => void = () => {};

	export let url = '';
	export let idx = 0;
	export let config: any = {};

	let showManageModal = false;
	let showConfigModal = false;
	let showDeleteConfirmDialog = false;

	const getTagName = (tag: any) => {
		if (typeof tag === 'string') {
			return tag;
		}

		if (tag && typeof tag === 'object' && typeof tag.name === 'string') {
			return tag.name;
		}

		return '';
	};

	$: prefixId = typeof config?.prefix_id === 'string' ? config.prefix_id.trim() : '';
	$: tagNames = Array.isArray(config?.tags)
		? config.tags.map((tag: any) => getTagName(tag)).filter(Boolean)
		: [];
</script>

<AddConnectionModal
	ollama
	edit
	bind:show={showConfigModal}
	connection={{
		url,
		key: config?.key ?? '',
		config: config
	}}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(connection) => {
		url = connection.url;
		config = { ...connection.config, key: connection.key };
		onSubmit(connection);
	}}
/>

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	on:confirm={() => {
		onDelete();
		showConfigModal = false;
	}}
/>

<ManageOllamaModal bind:show={showManageModal} urlIdx={idx} />

<div class="flex w-full flex-col gap-1">
	<div class="flex w-full items-center gap-2">
		<div class="flex gap-1 items-center shrink-0">
			<Tooltip content={(config?.enable ?? true) ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
				<Switch
					bind:state={config.enable}
					on:change={() => {
						config.enable = config.enable ?? false;
						onSubmit({ url, key: config?.key ?? '', config });
					}}
				/>
			</Tooltip>

			<Tooltip content={$i18n.t('Manage')} className="self-start">
				<button
					class="self-center p-1 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-850 rounded-lg transition"
					on:click={() => {
						showManageModal = true;
					}}
					type="button"
				>
					<Download />
				</button>
			</Tooltip>

			<Tooltip content={$i18n.t('Configure')} className="self-start">
				<button
					class="self-center p-1 bg-transparent hover:bg-gray-100 dark:hover:bg-gray-850 rounded-lg transition"
					on:click={() => {
						showConfigModal = true;
					}}
					type="button"
				>
					<Cog6 />
				</button>
			</Tooltip>
		</div>

		<Tooltip
			className="w-full relative"
			content={$i18n.t(`WebUI will make requests to "{{url}}/api/chat"`, {
				url
			})}
			placement="top-start"
		>
			{#if !(config?.enable ?? true)}
				<div
					class="absolute top-0 bottom-0 left-0 right-0 opacity-60 bg-white dark:bg-gray-900 z-10"
				></div>
			{/if}

			{#if url}
				<a
					class="block w-full min-w-0 truncate text-sm hover:underline underline-offset-2"
					href={url}
					target="_blank"
					rel="noreferrer"
				>
					{url}
				</a>
			{:else}
				<span class="block w-full min-w-0 truncate text-sm"
					>{$i18n.t('Enter URL (e.g. http://localhost:11434)')}</span
				>
			{/if}
		</Tooltip>
	</div>

	{#if prefixId || tagNames.length > 0}
		<div class="flex flex-wrap items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
			{#if prefixId}
				<span class="px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-850">{prefixId}.</span>
			{/if}
			{#each tagNames as tagName}
				<span class="px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-850">{tagName}</span>
			{/each}
		</div>
	{/if}
</div>
