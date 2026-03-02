<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';
	import { getContext, onDestroy, onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import { getAdminConfig, updateAdminConfig } from '$lib/apis/auths';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');
	const t = (key: string, params?: Record<string, unknown>) => {
		const translator = get(i18n) as
			| { t?: (k: string, p?: Record<string, unknown>) => string }
			| undefined;
		return translator?.t ? translator.t(key, params) : key;
	};

	type NoticesConfig = Record<string, unknown> & {
		ENABLE_SYSTEM_NOTICE: boolean;
		SYSTEM_NOTICE_TITLE: string;
		SYSTEM_NOTICE_CONTENT: string;
		ENABLE_MOTD: boolean;
		MOTD_TITLE: string;
		MOTD_CONTENT: string;
	};

	let adminConfig: NoticesConfig | null = null;
	let autoSaveTimer: ReturnType<typeof setTimeout> | null = null;
	let autoSaveInFlight = false;
	let autoSaveQueued = false;
	let autoSaveReady = false;

	const normalizeAdminConfig = (configData: Record<string, unknown>): NoticesConfig => ({
		...configData,
		ENABLE_SYSTEM_NOTICE: Boolean(configData?.ENABLE_SYSTEM_NOTICE ?? false),
		SYSTEM_NOTICE_TITLE: String(configData?.SYSTEM_NOTICE_TITLE ?? 'System Notice'),
		SYSTEM_NOTICE_CONTENT: String(configData?.SYSTEM_NOTICE_CONTENT ?? ''),
		ENABLE_MOTD: Boolean(configData?.ENABLE_MOTD ?? false),
		MOTD_TITLE: String(configData?.MOTD_TITLE ?? 'Message of the day!'),
		MOTD_CONTENT: String(configData?.MOTD_CONTENT ?? '')
	});

	const renderGuestPreviewDescription = (content: string) => {
		try {
			return DOMPurify.sanitize(String(marked.parse(String(content ?? ''))));
		} catch {
			return DOMPurify.sanitize(String(content ?? ''));
		}
	};

	$: guestPreviewTitle =
		String(adminConfig?.SYSTEM_NOTICE_TITLE ?? '').trim() || t('Notice');
	$: guestPreviewDescription = String(adminConfig?.SYSTEM_NOTICE_CONTENT ?? '');
	$: guestPreviewDescriptionHtml = renderGuestPreviewDescription(guestPreviewDescription);

	type SaveOptions = {
		silent?: boolean;
	};

	const saveHandler = async (options: SaveOptions = {}) => {
		if (!adminConfig) {
			return;
		}
		const { silent = false } = options;

		const payload = {
			...adminConfig,
			SYSTEM_NOTICE_TITLE: String(adminConfig.SYSTEM_NOTICE_TITLE ?? ''),
			SYSTEM_NOTICE_CONTENT: String(adminConfig.SYSTEM_NOTICE_CONTENT ?? ''),
			MOTD_TITLE: String(adminConfig.MOTD_TITLE ?? 'Message of the day!'),
			MOTD_CONTENT: String(adminConfig.MOTD_CONTENT ?? '')
		};

		const response = await updateAdminConfig(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response && !silent) {
			adminConfig = normalizeAdminConfig(response);
			toast.success(t('Notice settings updated'));
		}
	};

	const runAutoSave = async () => {
		if (autoSaveInFlight) {
			autoSaveQueued = true;
			return;
		}

		autoSaveInFlight = true;
		await saveHandler({ silent: true });
		autoSaveInFlight = false;

		if (autoSaveQueued) {
			autoSaveQueued = false;
			await runAutoSave();
		}
	};

	const queueNoticesAutoSave = () => {
		if (!autoSaveReady || !adminConfig) {
			return;
		}

		if (autoSaveTimer) {
			clearTimeout(autoSaveTimer);
		}

		autoSaveTimer = setTimeout(() => {
			autoSaveTimer = null;
			void runAutoSave();
		}, 350);
	};

	onMount(async () => {
		const configResponse = await getAdminConfig(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (configResponse) {
			adminConfig = normalizeAdminConfig(configResponse);
		}

		autoSaveReady = true;
	});

	onDestroy(() => {
		if (autoSaveTimer) {
			clearTimeout(autoSaveTimer);
			autoSaveTimer = null;
		}
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={() => saveHandler()}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if adminConfig}
			<div class="space-y-4">
				<div
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-4"
				>
					<div>
						<div class="text-base font-medium">{$i18n.t('Guest Notification')}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$i18n.t(
								'Shown to unregistered users on the auth page.'
							)}
						</div>
					</div>

					<div
						class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
					>
						<div>
							<div class="text-sm font-medium">{$i18n.t('Enable Guest Notification')}</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{$i18n.t('Show a custom notification on the sign-in/sign-up page.')}
							</div>
						</div>
						<Switch
							bind:state={adminConfig.ENABLE_SYSTEM_NOTICE}
							on:change={queueNoticesAutoSave}
						/>
					</div>

					<div class="grid gap-3 sm:grid-cols-2">
						<div class="sm:col-span-2">
							<div class="text-xs font-medium mb-1">{$i18n.t('Notification Title')}</div>
							<input
								type="text"
								bind:value={adminConfig.SYSTEM_NOTICE_TITLE}
								on:input={queueNoticesAutoSave}
								class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
								placeholder={$i18n.t('Welcome')}
							/>
						</div>
						<div class="sm:col-span-2">
							<div class="text-xs font-medium mb-1">{$i18n.t('Notification Description')}</div>
							<textarea
								bind:value={adminConfig.SYSTEM_NOTICE_CONTENT}
								on:input={queueNoticesAutoSave}
								class="w-full min-h-28 bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5 resize-y"
								placeholder={$i18n.t('Write custom description here...')}
							></textarea>
							<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
								{$i18n.t('Markdown is supported.')}
							</div>
						</div>

						<div class="sm:col-span-2">
							<div class="text-xs font-medium mb-1">{$i18n.t('Live Guest Preview')}</div>
							<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 bg-white/50 dark:bg-gray-950/30">
								<div
									class="mb-1 w-full rounded-2xl border border-gray-200/80 dark:border-gray-800/90 bg-gray-50/80 dark:bg-gray-900/70 p-4 sm:p-5 text-left shadow-sm {adminConfig.ENABLE_SYSTEM_NOTICE
										? ''
										: 'opacity-60'}"
								>
									<div
										class="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100"
									>
										{guestPreviewTitle}
									</div>
									{#if guestPreviewDescription.trim().length > 0}
										<div
											class="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300 marked"
										>
											{@html guestPreviewDescriptionHtml}
										</div>
									{:else}
										<div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
											{$i18n.t('Notification description is empty.')}
										</div>
									{/if}
								</div>

								<div class="text-[11px] text-gray-500 dark:text-gray-400">
									{#if adminConfig.ENABLE_SYSTEM_NOTICE}
										{$i18n.t('Preview reflects how this card appears to guests on the auth page.')}
									{:else}
										{$i18n.t('Guest notification is currently disabled.')}
									{/if}
								</div>
							</div>
						</div>
					</div>
				</div>

				<div
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-4"
				>
					<div>
						<div class="text-base font-medium">{$i18n.t('Message of the day')}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$i18n.t(
								'Shown in the bottom-right corner for signed-in users only.'
							)}
						</div>
					</div>

					<div
						class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
					>
						<div>
							<div class="text-sm font-medium">{$i18n.t('Enable MOTD')}</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{$i18n.t('Show MOTD for registered users.')}
							</div>
						</div>
						<Switch bind:state={adminConfig.ENABLE_MOTD} on:change={queueNoticesAutoSave} />
					</div>

					<div class="grid gap-3 sm:grid-cols-2">
						<div class="sm:col-span-2">
							<div class="text-xs font-medium mb-1">{$i18n.t('MOTD Text')}</div>
							<textarea
								bind:value={adminConfig.MOTD_CONTENT}
								on:input={queueNoticesAutoSave}
								class="w-full min-h-24 bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5 resize-y"
								placeholder={$i18n.t('Write MOTD text here...')}
							></textarea>
						</div>
					</div>
				</div>
			</div>
		{:else}
			<div class="flex h-full justify-center">
				<div class="my-auto">
					<Spinner className="size-6" />
				</div>
			</div>
		{/if}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
