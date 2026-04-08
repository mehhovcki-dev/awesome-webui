<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import { getAdminConfig, updateAdminConfig } from '$lib/apis/auths';

	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');
	const t = (key: string, params?: Record<string, unknown>) => {
		const translator = get(i18n) as
			| { t?: (k: string, p?: Record<string, unknown>) => string }
			| undefined;
		return translator?.t ? translator.t(key, params) : key;
	};

	type SoundType = 'channel' | 'chat_completion';

	type NotificationSoundItem = {
		id: string;
		name: string;
		type: SoundType;
		data_url: string;
	};

	type NotificationSoundConfig = Record<string, unknown> & {
		NOTIFICATION_SOUND_LIBRARY: NotificationSoundItem[];
	};

	let adminConfig: NotificationSoundConfig | null = null;
	let pendingType: SoundType = 'channel';
	let fileInputEl: HTMLInputElement;

	let autoSaveTimer: ReturnType<typeof setTimeout> | null = null;
	let autoSaveInFlight = false;
	let autoSaveQueued = false;
	let autoSaveReady = false;

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

		return `sound-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
	};

	const normalizeSound = (raw: unknown): NotificationSoundItem | null => {
		if (!raw || typeof raw !== 'object') {
			return null;
		}

		const sound = raw as Partial<NotificationSoundItem>;
		const id = String(sound.id ?? '').trim();
		const name = String(sound.name ?? '').trim();
		const type = String(sound.type ?? '')
			.trim()
			.toLowerCase();
		const dataUrl = String(sound.data_url ?? '').trim();

		if (!id || !name || !dataUrl.startsWith('data:audio/')) {
			return null;
		}
		if (!['channel', 'chat_completion'].includes(type)) {
			return null;
		}

		return {
			id,
			name,
			type: type as SoundType,
			data_url: dataUrl
		};
	};

	const normalizeAdminConfig = (configData: Record<string, unknown>): NotificationSoundConfig => ({
		...configData,
		NOTIFICATION_SOUND_LIBRARY: Array.isArray(configData?.NOTIFICATION_SOUND_LIBRARY)
			? configData.NOTIFICATION_SOUND_LIBRARY.map((item) => normalizeSound(item)).filter(
					(item): item is NotificationSoundItem => item !== null
				)
			: []
	});

	const saveHandler = async (silent = false) => {
		if (!adminConfig) {
			return;
		}

		const payload = {
			...adminConfig,
			NOTIFICATION_SOUND_LIBRARY: adminConfig.NOTIFICATION_SOUND_LIBRARY
		};

		const response = await updateAdminConfig(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response) {
			adminConfig = normalizeAdminConfig(response);
			if (!silent) {
				toast.success(t('Notification sounds updated'));
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

	const readFileAsDataUrl = (file: File): Promise<string> => {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = (event) => {
				resolve(String(event.target?.result ?? ''));
			};
			reader.onerror = (error) => {
				reject(error);
			};
			reader.readAsDataURL(file);
		});
	};

	const uploadSoundHandler = async (fileList: FileList | null) => {
		if (!adminConfig || !fileList?.length) {
			return;
		}

		const files = Array.from(fileList);
		const nextSounds: NotificationSoundItem[] = [];
		let addedCount = 0;
		let failedCount = 0;

		for (const file of files) {
			if (!file.type.startsWith('audio/')) {
				failedCount += 1;
				continue;
			}

			// Keep config payload practical for DB persistence and realtime sync.
			if (file.size > 2 * 1024 * 1024) {
				failedCount += 1;
				continue;
			}

			const dataUrl = await readFileAsDataUrl(file).catch(() => '');
			if (!dataUrl.startsWith('data:audio/')) {
				failedCount += 1;
				continue;
			}

			nextSounds.push({
				id: createSafeId(),
				name: file.name.replace(/\.[^.]+$/, ''),
				type: pendingType,
				data_url: dataUrl
			});
			addedCount += 1;
		}

		if (addedCount > 0) {
			adminConfig.NOTIFICATION_SOUND_LIBRARY = [
				...adminConfig.NOTIFICATION_SOUND_LIBRARY,
				...nextSounds
			];
			queueAutoSave();
			toast.success(
				t('{{COUNT}} sound(s) uploaded', {
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

	const removeSound = (soundId: string) => {
		if (!adminConfig) {
			return;
		}

		adminConfig.NOTIFICATION_SOUND_LIBRARY = adminConfig.NOTIFICATION_SOUND_LIBRARY.filter(
			(sound) => sound.id !== soundId
		);
		queueAutoSave();
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
					<div class="text-base font-medium">{$i18n.t('Notification Sounds')}</div>
					<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						{$i18n.t(
							'Upload custom sounds for channels and chat completions. Users can choose defaults and per-channel overrides.'
						)}
					</div>
				</div>

				<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-2">
					<div class="text-xs font-medium">{$i18n.t('Upload Sound')}</div>
					<div class="flex flex-col sm:flex-row gap-2 sm:items-center">
						<select
							class="bg-transparent border border-gray-200/80 dark:border-gray-800 rounded-md px-2 py-1.5 text-xs"
							bind:value={pendingType}
						>
							<option value="channel">{$i18n.t('Channel notifications')}</option>
							<option value="chat_completion">{$i18n.t('Chat completion')}</option>
						</select>

						<button
							type="button"
							class="w-fit rounded-full bg-black px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100"
							on:click={() => fileInputEl?.click()}
						>
							{$i18n.t('Upload audio')}
						</button>
					</div>
					<div class="text-[11px] text-gray-500 dark:text-gray-400">
						{$i18n.t('Supported: audio/*, max size 2 MB per file')}
					</div>

					<input
						bind:this={fileInputEl}
						type="file"
						accept="audio/*"
						multiple
						class="hidden"
						on:change={(event) => {
							const target = event.currentTarget as HTMLInputElement;
							uploadSoundHandler(target.files);
							target.value = '';
						}}
					/>
				</div>

				<div class="space-y-2">
					<div class="text-xs font-medium">{$i18n.t('Library')}</div>

					{#if adminConfig.NOTIFICATION_SOUND_LIBRARY.length === 0}
						<div class="text-xs text-gray-500 dark:text-gray-400">
							{$i18n.t('No custom sounds uploaded yet.')}
						</div>
					{:else}
						<div class="space-y-2">
							{#each adminConfig.NOTIFICATION_SOUND_LIBRARY as sound (sound.id)}
								<div
									class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-2 bg-white/70 dark:bg-gray-900/60"
								>
									<div class="flex flex-col sm:flex-row sm:items-center gap-2">
										<input
											type="text"
											bind:value={sound.name}
											on:input={queueAutoSave}
											class="flex-1 bg-transparent border border-gray-200/80 dark:border-gray-800 rounded-md px-2 py-1.5 text-xs"
										/>
										<select
											class="bg-transparent border border-gray-200/80 dark:border-gray-800 rounded-md px-2 py-1.5 text-xs"
											bind:value={sound.type}
											on:change={queueAutoSave}
										>
											<option value="channel">{$i18n.t('Channel notifications')}</option>
											<option value="chat_completion">{$i18n.t('Chat completion')}</option>
										</select>
										<button
											type="button"
											class="rounded-md border border-red-300/80 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/50"
											on:click={() => removeSound(sound.id)}
										>
											{$i18n.t('Remove')}
										</button>
									</div>

									<audio controls preload="none" src={sound.data_url} class="w-full h-9" />
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
