<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import AddConnectionModal from '$lib/components/AddConnectionModal.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	export let onDelete: () => void = () => {};
	export let onSubmit: (connection?: any) => void = () => {};

	export let pipeline = false;

	export let url = '';
	export let key = '';
	export let config: any = {};

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

<ConfirmDialog
	bind:show={showDeleteConfirmDialog}
	on:confirm={() => {
		onDelete();
	}}
/>

<AddConnectionModal
	edit
	bind:show={showConfigModal}
	connection={{
		url,
		key,
		config
	}}
	onDelete={() => {
		showDeleteConfirmDialog = true;
	}}
	onSubmit={(connection) => {
		url = connection.url;
		key = connection.key;
		config = connection.config;
		onSubmit(connection);
	}}
/>

<div class="flex w-full flex-col gap-1">
	<div class="flex w-full items-center gap-2">
		<div class="flex gap-1 items-center shrink-0">
			<Tooltip content={(config?.enable ?? true) ? $i18n.t('Enabled') : $i18n.t('Disabled')}>
				<Switch
					bind:state={config.enable}
					on:change={() => {
						config.enable = config.enable ?? false;
						onSubmit({ url, key, config });
					}}
				/>
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
			content={$i18n.t(`WebUI will make requests to "{{url}}/chat/completions"`, {
				url
			})}
			placement="top-start"
		>
			{#if !(config?.enable ?? true)}
				<div
					class="absolute top-0 bottom-0 left-0 right-0 opacity-60 bg-white dark:bg-gray-900 z-10"
				></div>
			{/if}
			<div class="flex w-full items-center gap-2 min-w-0">
				{#if url}
					<a
						class="flex-1 min-w-0 truncate text-sm hover:underline underline-offset-2"
						href={url}
						target="_blank"
						rel="noreferrer"
					>
						{url}
					</a>
				{:else}
					<span class="flex-1 min-w-0 truncate text-sm">{$i18n.t('API Base URL')}</span>
				{/if}

				{#if pipeline}
					<div class="shrink-0">
						<Tooltip content="Pipelines">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="currentColor"
								class="size-4"
							>
								<path
									d="M11.644 1.59a.75.75 0 0 1 .712 0l9.75 5.25a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.712 0l-9.75-5.25a.75.75 0 0 1 0-1.32l9.75-5.25Z"
								/>
								<path
									d="m3.265 10.602 7.668 4.129a2.25 2.25 0 0 0 2.134 0l7.668-4.13 1.37.739a.75.75 0 0 1 0 1.32l-9.75 5.25a.75.75 0 0 1-.71 0l-9.75-5.25a.75.75 0 0 1 0-1.32l1.37-.738Z"
								/>
								<path
									d="m10.933 19.231-7.668-4.13-1.37.739a.75.75 0 0 0 0 1.32l9.75 5.25c.221.12.489.12.71 0l9.75-5.25a.75.75 0 0 0 0-1.32l-1.37-.738-7.668 4.13a2.25 2.25 0 0 1-2.134-.001Z"
								/>
							</svg>
						</Tooltip>
					</div>
				{/if}
			</div>
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
