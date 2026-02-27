<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import {
		getAdminConfig,
		updateAdminConfig,
		getInviteCodes,
		createInviteCode,
		deleteInviteCode
	} from '$lib/apis/auths';
	import { getGroups } from '$lib/apis/groups';
	import { config } from '$lib/stores';

	import Switch from '$lib/components/common/Switch.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');
	const t = (key: string, params?: Record<string, unknown>) => {
		const translator = get(i18n) as
			| { t?: (k: string, p?: Record<string, unknown>) => string }
			| undefined;
		return translator?.t ? translator.t(key, params) : key;
	};

	type GroupInfo = {
		id: string;
		name: string;
	};

	type InviteCodeInfo = {
		id: string;
		code: string;
		created_by?: string;
		created_at?: number;
		expires_at?: number | null;
		uses_count?: number;
		max_uses?: number | null;
	};

	type DurationPreset = {
		id: string;
		label: string;
		seconds: number | null;
	};

	type AuthorizationConfig = Record<string, unknown> & {
		ENABLE_SIGNUP: boolean;
		ENABLE_PASSWORD_SIGNUP: boolean;
		ENABLE_OAUTH_LOGIN: boolean;
		ENABLE_OAUTH_SIGNUP: boolean;
		OAUTH_ALLOWED_LOGIN_PROVIDERS: string[] | null;
		OAUTH_ALLOWED_SIGNUP_PROVIDERS: string[] | null;
		ENABLE_INVITE_ONLY_AUTH: boolean;
		INVITE_CREATOR_SCOPE: 'admin' | 'groups' | 'all';
		INVITE_CREATOR_GROUP_IDS: string[];
		INVITE_CREATOR_COOLDOWN_SECONDS: number;
		INVITE_CODE_LENGTH: number;
		INVITE_CODE_TTL_SECONDS: number;
		INVITE_CODE_PREFIX: string;
		INVITE_CODE_REUSABLE: boolean;
		INVITE_CODE_MAX_USES: number;
	};

	let adminConfig: AuthorizationConfig | null = null;
	let groups: GroupInfo[] = [];
	let inviteCodes: InviteCodeInfo[] = [];
	let availableOAuthProviders: { id: string; label: string }[] = [];
	let creatingInvite = false;
	let copyingInviteId: string | null = null;
	let inviteTtlPreset = '7d';
	let inviteTtlDateTime = '';
	let creatorCooldownPreset = '1h';
	let creatorCooldownDateTime = '';

	const creatorScopeOptions = [
		{
			id: 'admin',
			title: 'Admin Only',
			description: 'Only admins can create invite codes.'
		},
		{
			id: 'groups',
			title: 'Selected Groups',
			description: 'Only members of selected groups can create invite codes.'
		},
		{
			id: 'all',
			title: 'All Users',
			description: 'Any user can create invite codes (with cooldown).'
		}
	];

	const inviteTtlPresets: DurationPreset[] = [
		{ id: '1h', label: '1 hour', seconds: 3600 },
		{ id: '1d', label: '1 day', seconds: 86400 },
		{ id: '7d', label: '7 days', seconds: 604800 },
		{ id: '30d', label: '30 days', seconds: 2592000 },
		{ id: 'never', label: 'Never', seconds: 0 },
		{ id: 'custom', label: 'Pick date and time', seconds: null }
	];

	const creatorCooldownPresets: DurationPreset[] = [
		{ id: 'none', label: 'No cooldown', seconds: 0 },
		{ id: '15m', label: '15 minutes', seconds: 900 },
		{ id: '1h', label: '1 hour', seconds: 3600 },
		{ id: '6h', label: '6 hours', seconds: 21600 },
		{ id: '1d', label: '1 day', seconds: 86400 },
		{ id: 'custom', label: 'Pick date and time', seconds: null }
	];

	const normalizeProviderList = (providers: unknown): string[] | null => {
		if (providers === null || providers === undefined) {
			return null;
		}

		if (!Array.isArray(providers)) {
			return [];
		}

		return Array.from(
			new Set(
				providers
					.map((provider) => String(provider).trim().toLowerCase())
					.filter((provider) => provider.length > 0)
			)
		);
	};

	const normalizeAdminConfig = (configData: Record<string, unknown>): AuthorizationConfig => ({
		...configData,
		ENABLE_SIGNUP: Boolean(configData?.ENABLE_SIGNUP ?? true),
		ENABLE_PASSWORD_SIGNUP: Boolean(configData?.ENABLE_PASSWORD_SIGNUP ?? true),
		ENABLE_OAUTH_LOGIN: Boolean(configData?.ENABLE_OAUTH_LOGIN ?? true),
		ENABLE_OAUTH_SIGNUP: Boolean(configData?.ENABLE_OAUTH_SIGNUP ?? false),
		OAUTH_ALLOWED_LOGIN_PROVIDERS: normalizeProviderList(configData?.OAUTH_ALLOWED_LOGIN_PROVIDERS),
		OAUTH_ALLOWED_SIGNUP_PROVIDERS: normalizeProviderList(
			configData?.OAUTH_ALLOWED_SIGNUP_PROVIDERS
		),
		ENABLE_INVITE_ONLY_AUTH: Boolean(configData?.ENABLE_INVITE_ONLY_AUTH ?? false),
		INVITE_CREATOR_SCOPE: ['admin', 'groups', 'all'].includes(
			String(configData?.INVITE_CREATOR_SCOPE)
		)
			? (configData.INVITE_CREATOR_SCOPE as 'admin' | 'groups' | 'all')
			: 'admin',
		INVITE_CREATOR_GROUP_IDS: Array.isArray(configData?.INVITE_CREATOR_GROUP_IDS)
			? configData.INVITE_CREATOR_GROUP_IDS.map((groupId) => String(groupId))
			: [],
		INVITE_CREATOR_COOLDOWN_SECONDS: Number(configData?.INVITE_CREATOR_COOLDOWN_SECONDS ?? 3600),
		INVITE_CODE_LENGTH: Number(configData?.INVITE_CODE_LENGTH ?? 8),
		INVITE_CODE_TTL_SECONDS: Number(configData?.INVITE_CODE_TTL_SECONDS ?? 604800),
		INVITE_CODE_PREFIX: String(configData?.INVITE_CODE_PREFIX ?? ''),
		INVITE_CODE_REUSABLE: Boolean(configData?.INVITE_CODE_REUSABLE ?? false),
		INVITE_CODE_MAX_USES: Math.max(0, Number(configData?.INVITE_CODE_MAX_USES ?? 1))
	});

	const toDateTimeLocalValue = (date: Date) => {
		const year = date.getFullYear();
		const month = String(date.getMonth() + 1).padStart(2, '0');
		const day = String(date.getDate()).padStart(2, '0');
		const hours = String(date.getHours()).padStart(2, '0');
		const minutes = String(date.getMinutes()).padStart(2, '0');
		return `${year}-${month}-${day}T${hours}:${minutes}`;
	};

	const formatDuration = (seconds: number, allowNever: boolean = false) => {
		if (seconds <= 0) {
			return allowNever ? t('Never') : t('No cooldown');
		}
		if (seconds % 86400 === 0) {
			return `${seconds / 86400}d`;
		}
		if (seconds % 3600 === 0) {
			return `${seconds / 3600}h`;
		}
		if (seconds % 60 === 0) {
			return `${seconds / 60}m`;
		}
		return `${seconds}s`;
	};

	const getSecondsFromPreset = (presetId: string, presets: DurationPreset[]) => {
		const preset = presets.find((item) => item.id === presetId);
		return preset?.seconds ?? null;
	};

	const syncDurationControlsFromConfig = () => {
		if (!adminConfig) {
			return;
		}

		const inviteTtlSeconds = Math.max(0, Number(adminConfig.INVITE_CODE_TTL_SECONDS) || 0);
		const inviteTtlPresetMatch = inviteTtlPresets.find(
			(preset) => preset.seconds === inviteTtlSeconds
		);
		if (inviteTtlPresetMatch) {
			inviteTtlPreset = inviteTtlPresetMatch.id;
		} else {
			inviteTtlPreset = 'custom';
			inviteTtlDateTime = toDateTimeLocalValue(new Date(Date.now() + inviteTtlSeconds * 1000));
		}

		const creatorCooldownSeconds = Math.max(
			0,
			Number(adminConfig.INVITE_CREATOR_COOLDOWN_SECONDS) || 0
		);
		const creatorCooldownPresetMatch = creatorCooldownPresets.find(
			(preset) => preset.seconds === creatorCooldownSeconds
		);
		if (creatorCooldownPresetMatch) {
			creatorCooldownPreset = creatorCooldownPresetMatch.id;
		} else {
			creatorCooldownPreset = 'custom';
			creatorCooldownDateTime = toDateTimeLocalValue(
				new Date(Date.now() + creatorCooldownSeconds * 1000)
			);
		}
	};

	const resolveDurationSeconds = (
		presetId: string,
		dateTimeValue: string,
		presets: DurationPreset[],
		label: string
	): number | null => {
		const presetSeconds = getSecondsFromPreset(presetId, presets);
		if (presetSeconds !== null) {
			return presetSeconds;
		}

		if (!dateTimeValue) {
			toast.error(t('Select a date/time for {{label}}', { label }));
			return null;
		}

		const selectedDateTime = new Date(dateTimeValue);
		if (Number.isNaN(selectedDateTime.getTime())) {
			toast.error(t('Invalid date/time for {{label}}', { label }));
			return null;
		}

		const diffSeconds = Math.floor((selectedDateTime.getTime() - Date.now()) / 1000);
		if (diffSeconds <= 0) {
			toast.error(t('{{label}} must be in the future', { label }));
			return null;
		}

		return diffSeconds;
	};

	const getConfiguredProviderIds = () => availableOAuthProviders.map((provider) => provider.id);

	const getEffectiveProviderSelection = (selection: string[] | null) => {
		const configuredProviderIds = getConfiguredProviderIds();
		if (!Array.isArray(selection)) {
			return configuredProviderIds;
		}
		const configuredProviderSet = new Set(configuredProviderIds);
		return selection.filter((provider) => configuredProviderSet.has(provider));
	};

	const isProviderAllowedForLogin = (providerId: string) =>
		getEffectiveProviderSelection(adminConfig?.OAUTH_ALLOWED_LOGIN_PROVIDERS ?? null).includes(
			providerId
		);

	const isProviderAllowedForSignup = (providerId: string) =>
		getEffectiveProviderSelection(adminConfig?.OAUTH_ALLOWED_SIGNUP_PROVIDERS ?? null).includes(
			providerId
		);

	const toggleLoginProvider = (providerId: string) => {
		if (!adminConfig) {
			return;
		}

		const selection = new Set(
			getEffectiveProviderSelection(adminConfig.OAUTH_ALLOWED_LOGIN_PROVIDERS)
		);
		if (selection.has(providerId)) {
			selection.delete(providerId);
		} else {
			selection.add(providerId);
		}
		adminConfig.OAUTH_ALLOWED_LOGIN_PROVIDERS = Array.from(selection);
	};

	const toggleSignupProvider = (providerId: string) => {
		if (!adminConfig) {
			return;
		}

		const selection = new Set(
			getEffectiveProviderSelection(adminConfig.OAUTH_ALLOWED_SIGNUP_PROVIDERS)
		);
		if (selection.has(providerId)) {
			selection.delete(providerId);
		} else {
			selection.add(providerId);
		}
		adminConfig.OAUTH_ALLOWED_SIGNUP_PROVIDERS = Array.from(selection);
	};

	const setAllLoginProviders = (enabled: boolean) => {
		if (!adminConfig) {
			return;
		}
		adminConfig.OAUTH_ALLOWED_LOGIN_PROVIDERS = enabled ? getConfiguredProviderIds() : [];
	};

	const setAllSignupProviders = (enabled: boolean) => {
		if (!adminConfig) {
			return;
		}
		adminConfig.OAUTH_ALLOWED_SIGNUP_PROVIDERS = enabled ? getConfiguredProviderIds() : [];
	};

	$: {
		const providerMap = $config?.oauth?.providers ?? {};
		availableOAuthProviders = Object.entries(providerMap).map(([id, label]) => ({
			id: String(id).trim().toLowerCase(),
			label: String(label || id)
		}));
	}

	const refreshInviteCodes = async () => {
		const response = await getInviteCodes(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		inviteCodes = Array.isArray(response?.items) ? response.items : [];
	};

	const toggleCreatorGroup = (groupId: string) => {
		if (!adminConfig) {
			return;
		}

		const selected = new Set(adminConfig.INVITE_CREATOR_GROUP_IDS ?? []);
		if (selected.has(groupId)) {
			selected.delete(groupId);
		} else {
			selected.add(groupId);
		}
		adminConfig.INVITE_CREATOR_GROUP_IDS = Array.from(selected);
	};

	const formatTimestamp = (timestamp?: number | null) => {
		if (!timestamp) {
			return t('Never');
		}

		const date = new Date(timestamp * 1000);
		if (Number.isNaN(date.getTime())) {
			return t('Invalid date');
		}
		return date.toLocaleString();
	};

	const copyInviteCode = async (inviteId: string, inviteCode: string) => {
		try {
			copyingInviteId = inviteId;
			await navigator.clipboard.writeText(inviteCode);
			toast.success(t('Invite code copied'));
		} catch {
			toast.error(t('Failed to copy invite code'));
		} finally {
			copyingInviteId = null;
		}
	};

	const saveHandler = async () => {
		if (!adminConfig) {
			return;
		}

		const inviteTtlSeconds = resolveDurationSeconds(
			inviteTtlPreset,
			inviteTtlDateTime,
			inviteTtlPresets,
			t('invite expiry')
		);
		if (inviteTtlSeconds === null) {
			return;
		}

		let creatorCooldownSeconds = Math.max(
			0,
			Number(adminConfig.INVITE_CREATOR_COOLDOWN_SECONDS) || 0
		);
		if (adminConfig.INVITE_CREATOR_SCOPE === 'all') {
			const resolvedCreatorCooldownSeconds = resolveDurationSeconds(
				creatorCooldownPreset,
				creatorCooldownDateTime,
				creatorCooldownPresets,
				t('creator cooldown')
			);
			if (resolvedCreatorCooldownSeconds === null) {
				return;
			}
			creatorCooldownSeconds = resolvedCreatorCooldownSeconds;
		}

		const payload = {
			...adminConfig,
			OAUTH_ALLOWED_LOGIN_PROVIDERS: normalizeProviderList(
				adminConfig.OAUTH_ALLOWED_LOGIN_PROVIDERS
			),
			OAUTH_ALLOWED_SIGNUP_PROVIDERS: normalizeProviderList(
				adminConfig.OAUTH_ALLOWED_SIGNUP_PROVIDERS
			),
			INVITE_CREATOR_COOLDOWN_SECONDS: Math.max(0, creatorCooldownSeconds),
			INVITE_CODE_LENGTH: Math.max(4, Math.min(32, Number(adminConfig.INVITE_CODE_LENGTH) || 8)),
			INVITE_CODE_TTL_SECONDS: Math.max(0, inviteTtlSeconds),
			INVITE_CODE_PREFIX: (adminConfig.INVITE_CODE_PREFIX ?? '').trim(),
			INVITE_CODE_MAX_USES: adminConfig.INVITE_CODE_REUSABLE
				? Math.max(0, Number(adminConfig.INVITE_CODE_MAX_USES) || 0)
				: 1
		};

		const response = await updateAdminConfig(localStorage.token, payload).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response) {
			adminConfig = normalizeAdminConfig(response);
			syncDurationControlsFromConfig();
			toast.success(t('Authorization settings updated'));
		}
	};

	const generateInviteHandler = async () => {
		if (!adminConfig) {
			return;
		}

		creatingInvite = true;
		const invite = await createInviteCode(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		creatingInvite = false;

		if (invite?.code) {
			toast.success(t('Invite code created'));
			inviteCodes = [invite, ...inviteCodes];
		}
	};

	const deleteInviteHandler = async (inviteId: string) => {
		const response = await deleteInviteCode(localStorage.token, inviteId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response?.status) {
			inviteCodes = inviteCodes.filter((invite) => invite.id !== inviteId);
			toast.success(t('Invite code deleted'));
		}
	};

	onMount(async () => {
		await Promise.all([
			(async () => {
				const configResponse = await getAdminConfig(localStorage.token);
				adminConfig = normalizeAdminConfig(configResponse);
				syncDurationControlsFromConfig();
			})(),
			(async () => {
				const groupResponse = await getGroups(localStorage.token);
				groups = Array.isArray(groupResponse)
					? groupResponse
					: Array.isArray(groupResponse?.items)
						? groupResponse.items
						: [];
			})(),
			refreshInviteCodes()
		]);
	});
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={saveHandler}
>
	<div class="space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		{#if adminConfig}
			<div class="space-y-4">
				<div
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-4"
				>
					<div>
						<div class="text-base font-medium">{$i18n.t('Authorization')}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							{$i18n.t('Control account creation and sign-in methods for your workspace.')}
						</div>
					</div>

					<div class="space-y-3">
						<div
							class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
						>
							<div>
								<div class="text-sm font-medium">{$i18n.t('Registration')}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Allow new accounts to register on this instance.')}
								</div>
							</div>
							<Switch bind:state={adminConfig.ENABLE_SIGNUP} />
						</div>

						<div
							class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
						>
							<div>
								<div class="text-sm font-medium">
									{$i18n.t('Email + Password Account Creation')}
								</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Allow users to create accounts via email and password.')}
								</div>
							</div>
							<Switch bind:state={adminConfig.ENABLE_PASSWORD_SIGNUP} />
						</div>

						<div
							class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
						>
							<div>
								<div class="text-sm font-medium">{$i18n.t('SSO Logins')}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Allow users to sign in with configured OAuth/SSO providers.')}
								</div>
							</div>
							<Switch bind:state={adminConfig.ENABLE_OAUTH_LOGIN} />
						</div>

						<div
							class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 flex justify-between gap-4"
						>
							<div>
								<div class="text-sm font-medium">{$i18n.t('SSO Account Creation')}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Allow new accounts to be created from SSO providers.')}
								</div>
							</div>
							<Switch bind:state={adminConfig.ENABLE_OAUTH_SIGNUP} />
						</div>
					</div>

					{#if availableOAuthProviders.length > 0}
						<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-3">
							<div>
								<div class="text-sm font-medium">{$i18n.t('SSO Provider Access')}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
									{$i18n.t('Choose which providers are allowed for login and account creation.')}
								</div>
							</div>

							<div class="grid gap-3 sm:grid-cols-2">
								<div
									class="rounded-lg border border-gray-200/70 dark:border-gray-850/70 p-2.5 space-y-2"
								>
									<div class="flex items-center justify-between">
										<div class="text-xs font-medium">{$i18n.t('Login Providers')}</div>
										<div class="flex gap-1">
											<button
												type="button"
												class="text-[11px] px-2 py-1 rounded-md border border-gray-200/70 dark:border-gray-850/70"
												on:click={() => setAllLoginProviders(true)}
											>
												{$i18n.t('All')}
											</button>
											<button
												type="button"
												class="text-[11px] px-2 py-1 rounded-md border border-gray-200/70 dark:border-gray-850/70"
												on:click={() => setAllLoginProviders(false)}
											>
												{$i18n.t('None')}
											</button>
										</div>
									</div>
									<div class="space-y-1">
										{#each availableOAuthProviders as provider}
											<label
												class="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-gray-100/70 dark:hover:bg-gray-850/70"
											>
												<input
													type="checkbox"
													checked={isProviderAllowedForLogin(provider.id)}
													on:change={() => toggleLoginProvider(provider.id)}
												/>
												<span class="text-xs">{provider.label}</span>
											</label>
										{/each}
									</div>
								</div>

								<div
									class="rounded-lg border border-gray-200/70 dark:border-gray-850/70 p-2.5 space-y-2"
								>
									<div class="flex items-center justify-between">
										<div class="text-xs font-medium">{$i18n.t('Signup Providers')}</div>
										<div class="flex gap-1">
											<button
												type="button"
												class="text-[11px] px-2 py-1 rounded-md border border-gray-200/70 dark:border-gray-850/70"
												on:click={() => setAllSignupProviders(true)}
											>
												{$i18n.t('All')}
											</button>
											<button
												type="button"
												class="text-[11px] px-2 py-1 rounded-md border border-gray-200/70 dark:border-gray-850/70"
												on:click={() => setAllSignupProviders(false)}
											>
												{$i18n.t('None')}
											</button>
										</div>
									</div>
									<div class="space-y-1">
										{#each availableOAuthProviders as provider}
											<label
												class="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-gray-100/70 dark:hover:bg-gray-850/70"
											>
												<input
													type="checkbox"
													checked={isProviderAllowedForSignup(provider.id)}
													on:change={() => toggleSignupProvider(provider.id)}
												/>
												<span class="text-xs">{provider.label}</span>
											</label>
										{/each}
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>

				<div
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-4"
				>
					<div class="flex items-start justify-between gap-4">
						<div>
							<div class="text-base font-medium">{$i18n.t('Invite-Only Access')}</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								{$i18n.t('Require invite codes for new account creation.')}
							</div>
						</div>
						<Switch bind:state={adminConfig.ENABLE_INVITE_ONLY_AUTH} />
					</div>

					{#if adminConfig.ENABLE_INVITE_ONLY_AUTH}
						<div class="space-y-3">
							<div
								class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide"
							>
								{$i18n.t('Who can create invite codes?')}
							</div>

							<div class="grid gap-2 sm:grid-cols-3">
								{#each creatorScopeOptions as option}
									<button
										type="button"
										class="rounded-xl border p-3 text-left transition {adminConfig.INVITE_CREATOR_SCOPE ===
										option.id
											? 'border-gray-400 dark:border-gray-500 bg-gray-100 dark:bg-gray-850'
											: 'border-gray-200/80 dark:border-gray-800 hover:bg-gray-100/70 dark:hover:bg-gray-850/70'}"
										on:click={() => {
											adminConfig.INVITE_CREATOR_SCOPE = option.id;
										}}
									>
										<div class="font-medium text-sm">{$i18n.t(option.title)}</div>
										<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
											{$i18n.t(option.description)}
										</div>
									</button>
								{/each}
							</div>

							{#if adminConfig.INVITE_CREATOR_SCOPE === 'groups'}
								<div
									class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-2"
								>
									<div class="text-xs font-medium">{$i18n.t('Selected Groups')}</div>
									{#if groups.length > 0}
										<div class="grid gap-2 sm:grid-cols-2">
											{#each groups as group}
												<label
													class="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-gray-100/70 dark:hover:bg-gray-850/70"
												>
													<input
														type="checkbox"
														checked={(adminConfig.INVITE_CREATOR_GROUP_IDS ?? []).includes(
															group.id
														)}
														on:change={() => toggleCreatorGroup(group.id)}
													/>
													<span class="text-xs">{group.name}</span>
												</label>
											{/each}
										</div>
									{:else}
										<div class="text-xs text-gray-500 dark:text-gray-400">
											{$i18n.t('No groups available')}
										</div>
									{/if}
								</div>
							{/if}

							{#if adminConfig.INVITE_CREATOR_SCOPE === 'all'}
								<div
									class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-2"
								>
									<div class="text-xs font-medium">{$i18n.t('Creator Cooldown')}</div>
									<select
										bind:value={creatorCooldownPreset}
										class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
									>
										{#each creatorCooldownPresets as preset}
											<option value={preset.id}>{$i18n.t(preset.label)}</option>
										{/each}
									</select>
									{#if creatorCooldownPreset === 'custom'}
										<input
											type="datetime-local"
											bind:value={creatorCooldownDateTime}
											class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
										/>
									{/if}
									<div class="text-[11px] text-gray-500 dark:text-gray-400">
										{`${$i18n.t('Current')}: ${formatDuration(adminConfig.INVITE_CREATOR_COOLDOWN_SECONDS)}`}
									</div>
								</div>
							{/if}
						</div>

						<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-3">
							<div
								class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide"
							>
								{$i18n.t('Invite Code Defaults')}
							</div>

							<div class="grid gap-3 sm:grid-cols-2">
								<div>
									<div class="text-xs font-medium mb-1">{$i18n.t('Code Length')}</div>
									<input
										type="number"
										min="4"
										max="32"
										bind:value={adminConfig.INVITE_CODE_LENGTH}
										class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
									/>
								</div>

								<div>
									<div class="text-xs font-medium mb-1">{$i18n.t('Expires')}</div>
									<select
										bind:value={inviteTtlPreset}
										class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
									>
										{#each inviteTtlPresets as preset}
											<option value={preset.id}>{$i18n.t(preset.label)}</option>
										{/each}
									</select>
									{#if inviteTtlPreset === 'custom'}
										<input
											type="datetime-local"
											bind:value={inviteTtlDateTime}
											class="mt-2 w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
										/>
									{/if}
									<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
										{`${$i18n.t('Current')}: ${formatDuration(adminConfig.INVITE_CODE_TTL_SECONDS, true)}`}
									</div>
								</div>

								<div>
									<div class="text-xs font-medium mb-1">{$i18n.t('Code Prefix')}</div>
									<input
										type="text"
										bind:value={adminConfig.INVITE_CODE_PREFIX}
										placeholder={$i18n.t('Optional prefix, e.g. AWUI')}
										class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
									/>
								</div>

								<div
									class="flex items-center justify-between rounded-lg border border-gray-200/80 dark:border-gray-800 p-2.5"
								>
									<div>
										<div class="text-xs font-medium">{$i18n.t('Reusable Codes')}</div>
										<div class="text-[11px] text-gray-500 dark:text-gray-400">
											{$i18n.t('If disabled, each code can only be used once.')}
										</div>
									</div>
									<Switch bind:state={adminConfig.INVITE_CODE_REUSABLE} />
								</div>

								{#if adminConfig.INVITE_CODE_REUSABLE}
									<div>
										<div class="text-xs font-medium mb-1">{$i18n.t('Max Uses')}</div>
										<input
											type="number"
											min="0"
											bind:value={adminConfig.INVITE_CODE_MAX_USES}
											class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
										/>
										<div class="text-[11px] text-gray-500 dark:text-gray-400 mt-1">
											{$i18n.t('Set 0 for unlimited uses.')}
										</div>
									</div>
								{/if}
							</div>
						</div>

						<div class="rounded-xl border border-gray-200/80 dark:border-gray-800 p-3 space-y-3">
							<div class="flex items-center justify-between">
								<div
									class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide"
								>
									{$i18n.t('Invite Codes')}
								</div>
								<button
									type="button"
									disabled={creatingInvite}
									class="rounded-lg px-2.5 py-1.5 text-xs font-medium border border-gray-200/80 dark:border-gray-800 hover:bg-gray-100/70 dark:hover:bg-gray-850/70 disabled:opacity-50"
									on:click={generateInviteHandler}
								>
									{creatingInvite ? $i18n.t('Creating...') : $i18n.t('Generate Invite')}
								</button>
							</div>

							{#if inviteCodes.length > 0}
								<div class="space-y-2">
									{#each inviteCodes as invite (invite.id)}
										<div
											class="rounded-lg border border-gray-200/70 dark:border-gray-850/70 px-3 py-2"
										>
											<div class="flex items-center justify-between gap-2">
												<div class="font-mono text-xs break-all">{invite.code}</div>
												<div class="flex items-center gap-1">
													<button
														type="button"
														class="text-xs px-2 py-1 rounded-md border border-gray-200/70 dark:border-gray-850/70 hover:bg-gray-100/70 dark:hover:bg-gray-850/70"
														on:click={() => copyInviteCode(invite.id, invite.code)}
													>
														{copyingInviteId === invite.id ? $i18n.t('Copied') : $i18n.t('Copy')}
													</button>
													<button
														type="button"
														class="text-xs px-2 py-1 rounded-md border border-red-200/70 text-red-600 dark:border-red-900/60 dark:text-red-300 hover:bg-red-50/60 dark:hover:bg-red-950/40"
														on:click={() => deleteInviteHandler(invite.id)}
													>
														{$i18n.t('Delete')}
													</button>
												</div>
											</div>
											<div
												class="mt-1 text-[11px] text-gray-500 dark:text-gray-400 flex flex-wrap gap-2"
											>
												<span
													>{`Uses: ${invite.uses_count ?? 0}${invite.max_uses ? `/${invite.max_uses}` : ''}`}</span
												>
												<span>{`${$i18n.t('Expires')}: ${formatTimestamp(invite.expires_at)}`}</span
												>
											</div>
										</div>
									{/each}
								</div>
							{:else}
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('No invite codes yet')}
								</div>
							{/if}
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
