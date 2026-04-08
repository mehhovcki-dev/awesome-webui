<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import { getAdminConfig, updateAdminConfig } from '$lib/apis/auths';
	import { user } from '$lib/stores';
	import emojiShortCodes from '$lib/emoji-shortcodes.json';

	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');
	const t = (key: string, params?: Record<string, unknown>) => {
		const translator = get(i18n) as
			| { t?: (k: string, p?: Record<string, unknown>) => string }
			| undefined;
		return translator?.t ? translator.t(key, params) : key;
	};

	type CustomEmojiItem = {
		id: string;
		name: string;
		data_url: string;
		created_by?: string | null;
		created_by_name?: string | null;
		created_at?: number;
	};

	type CustomEmojiConfig = Record<string, unknown> & {
		CUSTOM_EMOJI_LIBRARY: CustomEmojiItem[];
	};

	let adminConfig: CustomEmojiConfig | null = null;
	let fileInputEl: HTMLInputElement;
	let autoSaveTimer: ReturnType<typeof setTimeout> | null = null;
	let autoSaveInFlight = false;
	let autoSaveQueued = false;
	let autoSaveReady = false;

	const standardShortCodes = new Set<string>(
		Object.values(emojiShortCodes)
			.flatMap((value) => (Array.isArray(value) ? value : [value]))
			.map((value) =>
				String(value ?? '')
					.trim()
					.toLowerCase()
			)
			.filter((value) => value.length > 0)
	);

	const sanitizeEmojiName = (value: string) =>
		String(value ?? '')
			.trim()
			.toLowerCase()
			.replace(/[^a-z0-9_]/g, '')
			.slice(0, 32);

	const createSafeId = () => {
		const cryptoObj = globalThis.crypto as Crypto | undefined;

		if (typeof cryptoObj?.randomUUID === 'function') {
			return cryptoObj.randomUUID();
		}

		if (cryptoObj?.getRandomValues) {
			const bytes = new Uint8Array(16);
			cryptoObj.getRandomValues(bytes);

			bytes[6] = (bytes[6] & 0x0f) | 0x40;
			bytes[8] = (bytes[8] & 0x3f) | 0x80;

			const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
			return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
		}

		return `emoji-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
	};

	const normalizeEmoji = (raw: unknown): CustomEmojiItem | null => {
		if (!raw || typeof raw !== 'object') {
			return null;
		}

		const emoji = raw as Partial<CustomEmojiItem>;
		const id = String(emoji.id ?? '').trim();
		const name = sanitizeEmojiName(String(emoji.name ?? ''));
		const dataUrl = String(emoji.data_url ?? '').trim();
		const createdBy = String(emoji.created_by ?? '').trim();
		const createdByName = String(emoji.created_by_name ?? '').trim();
		const createdAt = Number(emoji.created_at ?? Math.floor(Date.now() / 1000));

		if (!id || name.length < 2 || !dataUrl.startsWith('data:image/')) {
			return null;
		}

		return {
			id,
			name,
			data_url: dataUrl,
			created_by: createdBy || null,
			created_by_name: createdByName || null,
			created_at: Number.isFinite(createdAt) ? Math.floor(createdAt) : Math.floor(Date.now() / 1000)
		};
	};

	const normalizeAdminConfig = (configData: Record<string, unknown>): CustomEmojiConfig => ({
		...configData,
		CUSTOM_EMOJI_LIBRARY: Array.isArray(configData?.CUSTOM_EMOJI_LIBRARY)
			? configData.CUSTOM_EMOJI_LIBRARY.map((emoji) => normalizeEmoji(emoji)).filter(
					(item): item is CustomEmojiItem => item !== null
				)
			: []
	});

	const validateEmojiName = (name: string, ignoreId: string | null = null) => {
		if (name.length < 2) {
			toast.error(t('Emoji name must be at least 2 characters'));
			return false;
		}

		if (standardShortCodes.has(name)) {
			toast.error(t('This emoji name conflicts with a built-in emoji shortcode'));
			return false;
		}

		const duplicate = (adminConfig?.CUSTOM_EMOJI_LIBRARY ?? []).find(
			(emoji) => emoji.id !== ignoreId && emoji.name === name
		);
		if (duplicate) {
			toast.error(t('Emoji name must be unique'));
			return false;
		}

		return true;
	};

	const saveHandler = async (silent = false) => {
		if (!adminConfig) {
			return;
		}

		const sanitizedLibrary = adminConfig.CUSTOM_EMOJI_LIBRARY.map((emoji) =>
			normalizeEmoji(emoji)
		).filter((item): item is CustomEmojiItem => item !== null);

		const payload = {
			...adminConfig,
			CUSTOM_EMOJI_LIBRARY: sanitizedLibrary
		};

		const response = await updateAdminConfig(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response) {
			adminConfig = normalizeAdminConfig(response);
			if (!silent) {
				toast.success(t('Custom emojis updated'));
			}
		}
	};

	const runAutoSave = async () => {
		if (autoSaveInFlight) {
			autoSaveQueued = true;
			return;
		}

		autoSaveInFlight = true;
		await saveHandler(true);
		autoSaveInFlight = false;

		if (autoSaveQueued) {
			autoSaveQueued = false;
			await runAutoSave();
		}
	};

	const queueAutoSave = () => {
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

	const readFileAsDataUrl = (file: File): Promise<string> =>
		new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = (event) => resolve(String(event.target?.result ?? ''));
			reader.onerror = (error) => reject(error);
			reader.readAsDataURL(file);
		});

	const getAvailableEmojiName = (baseName: string, usedNames: Set<string>) => {
		let seed = sanitizeEmojiName(baseName);
		if (seed.length < 2) {
			seed = 'emoji';
		}

		let candidate = seed;
		let suffix = 2;

		while (standardShortCodes.has(candidate) || usedNames.has(candidate)) {
			const suffixText = `_${suffix}`;
			const trimmedSeed = seed.slice(0, Math.max(2, 32 - suffixText.length));
			candidate = `${trimmedSeed}${suffixText}`;
			suffix += 1;
		}

		return candidate;
	};

	const uploadEmojiHandler = async (fileList: FileList | null) => {
		if (!adminConfig || !fileList?.length) {
			return;
		}

		const files = Array.from(fileList);
		const usedNames = new Set(
			(adminConfig.CUSTOM_EMOJI_LIBRARY ?? []).map((emoji) => sanitizeEmojiName(emoji.name))
		);

		const nextEmojis: CustomEmojiItem[] = [];
		let addedCount = 0;
		let failedCount = 0;

		for (const file of files) {
			if (!file.type.startsWith('image/')) {
				failedCount += 1;
				continue;
			}

			// Keep payload size practical for persistent config storage.
			if (file.size > 1024 * 1024) {
				failedCount += 1;
				continue;
			}

			const dataUrl = await readFileAsDataUrl(file).catch(() => '');
			if (!dataUrl.startsWith('data:image/')) {
				failedCount += 1;
				continue;
			}

			const baseName = file.name.replace(/\.[^.]+$/, '');
			const name = getAvailableEmojiName(baseName, usedNames);
			usedNames.add(name);

			nextEmojis.push({
				id: createSafeId(),
				name,
				data_url: dataUrl,
				created_by: $user?.id ?? null,
				created_by_name: $user?.name ?? null,
				created_at: Math.floor(Date.now() / 1000)
			});
			addedCount += 1;
		}

		if (addedCount > 0) {
			adminConfig.CUSTOM_EMOJI_LIBRARY = [...adminConfig.CUSTOM_EMOJI_LIBRARY, ...nextEmojis];
			queueAutoSave();
			toast.success(
				t('{{COUNT}} emoji uploaded', {
					COUNT: addedCount
				})
			);
		}

		if (failedCount > 0) {
			toast.error(
				t('{{COUNT}} file(s) failed to upload', {
					COUNT: failedCount
				})
			);
		}
	};

	const renameEmoji = (emojiId: string, rawName: string) => {
		if (!adminConfig) {
			return false;
		}

		const nextName = sanitizeEmojiName(rawName);
		if (!validateEmojiName(nextName, emojiId)) {
			return false;
		}

		adminConfig.CUSTOM_EMOJI_LIBRARY = adminConfig.CUSTOM_EMOJI_LIBRARY.map((emoji) =>
			emoji.id === emojiId ? { ...emoji, name: nextName } : emoji
		);
		queueAutoSave();
		return true;
	};

	const removeEmoji = (emojiId: string) => {
		if (!adminConfig) {
			return;
		}

		adminConfig.CUSTOM_EMOJI_LIBRARY = adminConfig.CUSTOM_EMOJI_LIBRARY.filter(
			(emoji) => emoji.id !== emojiId
		);
		queueAutoSave();
	};

	const formatTimestamp = (value?: number) => {
		if (!value) {
			return t('Unknown');
		}

		const date = new Date(value * 1000);
		if (Number.isNaN(date.getTime())) {
			return t('Unknown');
		}
		return date.toLocaleString();
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
	on:submit|preventDefault={() => {
		saveHandler();
	}}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if adminConfig}
			<div
				class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-4"
			>
				<div>
					<div class="text-base font-medium">{$i18n.t('Custom Emojis')}</div>
					<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						{$i18n.t(
							'Upload server-wide custom emoji that users can use in statuses, reactions, and other emoji pickers.'
						)}
					</div>
				</div>

				<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-2">
					<div class="text-xs font-medium">{$i18n.t('Upload Emoji')}</div>
					<div class="flex flex-wrap items-center gap-2">
						<button
							type="button"
							class="w-fit rounded-full bg-black px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100"
							on:click={() => fileInputEl?.click()}
						>
							{$i18n.t('Upload image')}
						</button>
						<div class="text-[11px] text-gray-500 dark:text-gray-400">
							{$i18n.t(
								'Supported: image/* (PNG, JPG, WEBP, GIF), max 1 MB. Name is generated from file name.'
							)}
						</div>
					</div>

					<input
						bind:this={fileInputEl}
						type="file"
						accept="image/*"
						multiple
						class="hidden"
						on:change={(event) => {
							const target = event.currentTarget as HTMLInputElement;
							uploadEmojiHandler(target.files);
							target.value = '';
						}}
					/>
				</div>

				<div class="space-y-2">
					<div class="text-xs font-medium">{$i18n.t('Library')}</div>

					{#if adminConfig.CUSTOM_EMOJI_LIBRARY.length === 0}
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{$i18n.t('No custom emojis uploaded yet.')}
						</div>
					{:else}
						<div class="space-y-2">
							{#each adminConfig.CUSTOM_EMOJI_LIBRARY as emoji (emoji.id)}
								<div
									class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 bg-white/70 dark:bg-gray-900/60"
								>
									<div
										class="grid gap-3 md:grid-cols-[64px_minmax(0,1fr)_minmax(0,220px)_auto] items-center"
									>
										<div class="flex items-center justify-center">
											<img
												src={emoji.data_url}
												alt={emoji.name}
												class="size-10 rounded-md object-contain bg-white/80 dark:bg-gray-950/80"
												loading="lazy"
											/>
										</div>

										<div class="space-y-1">
											<input
												type="text"
												value={emoji.name}
												on:change={(event) => {
													const target = event.currentTarget as HTMLInputElement;
													if (!renameEmoji(emoji.id, target.value)) {
														target.value = emoji.name;
													}
												}}
												class="w-full bg-transparent border border-gray-200/80 dark:border-gray-800 rounded-md px-2 py-1.5 text-xs"
											/>
											<div class="text-[11px] text-gray-500 dark:text-gray-400">
												:{emoji.name}:
											</div>
										</div>

										<div class="text-[11px] text-gray-500 dark:text-gray-400">
											<div>
												{$i18n.t('Uploaded by')}: {emoji.created_by_name ||
													emoji.created_by ||
													'Unknown'}
											</div>
											<div>
												{$i18n.t('Created')}: {formatTimestamp(emoji.created_at)}
											</div>
										</div>

										<div class="flex justify-end">
											<button
												type="button"
												class="rounded-md border border-red-300/80 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/50"
												on:click={() => removeEmoji(emoji.id)}
											>
												{$i18n.t('Remove')}
											</button>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
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
