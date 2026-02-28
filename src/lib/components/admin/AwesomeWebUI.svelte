<script>
	import { getContext, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { user } from '$lib/stores';

	import Authorization from './AwesomeWebUI/Authorization.svelte';
	import Notices from './AwesomeWebUI/Notices.svelte';
	import SSO from './AwesomeWebUI/SSO.svelte';

	const i18n = getContext('i18n');

	let selectedTab = 'authorization';

	$: {
		const pathParts = $page.url.pathname.split('/');
		const tabFromPath = pathParts[pathParts.length - 1];
		selectedTab = ['authorization', 'notices', 'sso'].includes(tabFromPath)
			? tabFromPath
			: 'authorization';
	}

	$: if (selectedTab) {
		scrollToTab(selectedTab);
	}

	const scrollToTab = (tabId) => {
		const tabElement = document.getElementById(tabId);
		if (tabElement) {
			tabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
		}
	};

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
			return;
		}

		const containerElement = document.getElementById('awesome-webui-tabs-container');
		if (containerElement) {
			containerElement.addEventListener('wheel', (event) => {
				if (event.deltaY !== 0) {
					containerElement.scrollLeft += event.deltaY;
				}
			});
		}

		scrollToTab(selectedTab);
	});
</script>

<div class="flex flex-col lg:flex-row w-full h-full pb-2 lg:space-x-4">
	<div
		id="awesome-webui-tabs-container"
		class="mx-[16px] lg:mx-0 lg:px-[16px] flex flex-row overflow-x-auto gap-2.5 max-w-full lg:gap-1 lg:flex-col lg:flex-none lg:w-56 dark:text-gray-200 text-sm font-medium text-left scrollbar-none"
	>
		<a
			id="authorization"
			href="/admin/awesome-webui/authorization"
			draggable="false"
			class="px-0.5 py-1 min-w-fit rounded-lg lg:flex-none flex text-right transition select-none {selectedTab ===
			'authorization'
				? ''
				: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
		>
			<div class="self-center mr-2">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="currentColor"
					class="size-4"
				>
					<path
						fill-rule="evenodd"
						d="M12.516 2.17a.75.75 0 0 0-1.032 0 11.258 11.258 0 0 1-4.765 2.265 11.266 11.266 0 0 1-2.28.307.75.75 0 0 0-.689.75v5.12a11.25 11.25 0 0 0 6.322 10.165l1.59.795a.75.75 0 0 0 .676 0l1.59-.795a11.25 11.25 0 0 0 6.322-10.165v-5.12a.75.75 0 0 0-.688-.75 11.252 11.252 0 0 1-7.046-2.572Z"
						clip-rule="evenodd"
					/>
				</svg>
			</div>
			<div class="self-center">{$i18n.t('Authorization')}</div>
		</a>

		<a
			id="notices"
			href="/admin/awesome-webui/notices"
			draggable="false"
			class="px-0.5 py-1 min-w-fit rounded-lg lg:flex-none flex text-right transition select-none {selectedTab ===
			'notices'
				? ''
				: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
		>
			<div class="self-center mr-2">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="currentColor"
					class="size-4"
				>
					<path
						fill-rule="evenodd"
						d="M2.25 6.75A3.75 3.75 0 0 1 6 3h12a3.75 3.75 0 0 1 3.75 3.75v5.46a3.75 3.75 0 0 1-1.098 2.652l-4.29 4.29a3.75 3.75 0 0 1-2.652 1.098H6a3.75 3.75 0 0 1-3.75-3.75V6.75Zm9.75 3a.75.75 0 0 0-.75.75v3a.75.75 0 1 0 1.5 0v-3a.75.75 0 0 0-.75-.75Zm0-3a.75.75 0 1 0 0 1.5h.008a.75.75 0 1 0 0-1.5H12Z"
						clip-rule="evenodd"
					/>
				</svg>
			</div>
			<div class="self-center">{$i18n.t('Notices')}</div>
		</a>

		<a
			id="sso"
			href="/admin/awesome-webui/sso"
			draggable="false"
			class="px-0.5 py-1 min-w-fit rounded-lg lg:flex-none flex text-right transition select-none {selectedTab ===
			'sso'
				? ''
				: 'text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
		>
			<div class="self-center mr-2">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="currentColor"
					class="size-4"
				>
					<path
						d="M11.25 4.5a.75.75 0 0 1 .75-.75h6a.75.75 0 0 1 .53 1.28l-2.47 2.47a7.5 7.5 0 1 1-2.122-2.122l1.69-1.69H12a.75.75 0 0 1-.75-.75Zm-6 7.5a6 6 0 1 0 10.633-3.816l-1.53 1.53a.75.75 0 0 1-1.06 0l-1.53-1.53A3.75 3.75 0 1 1 8.25 12a.75.75 0 0 1-1.5 0 2.25 2.25 0 1 0 3.843-1.59l-.84.84a.75.75 0 0 1-1.06-1.06l1.53-1.53a.75.75 0 0 1 1.06 0l1.53 1.53a.75.75 0 0 1 0 1.06l-.84.84A3.75 3.75 0 1 1 8.25 12a.75.75 0 0 1-1.5 0Z"
					/>
				</svg>
			</div>
			<div class="self-center">{$i18n.t('SSO Management')}</div>
		</a>
	</div>

	<div
		class="flex-1 mt-1 lg:mt-0 px-[16px] lg:pr-[16px] lg:pl-0 overflow-y-scroll scrollbar-hidden"
	>
		{#if selectedTab === 'authorization'}
			<Authorization />
		{:else if selectedTab === 'notices'}
			<Notices />
		{:else if selectedTab === 'sso'}
			<SSO />
		{/if}
	</div>
</div>
