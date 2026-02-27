<script lang="ts">
	import { getContext, onMount } from 'svelte';
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

	type SSOConfig = Record<string, unknown> & {
		ENABLE_OAUTH_LOGIN: boolean;
		ENABLE_OAUTH_SIGNUP: boolean;
		OAUTH_MERGE_ACCOUNTS_BY_EMAIL: boolean;
		OAUTH_TIMEOUT: string;
		OAUTH_AUDIENCE: string;
		GOOGLE_OAUTH_ENABLED: boolean;
		GOOGLE_CLIENT_ID: string;
		GOOGLE_CLIENT_SECRET: string;
		GOOGLE_OAUTH_SCOPE: string;
		GOOGLE_SERVER_METADATA_URL: string;
		GOOGLE_REDIRECT_URI: string;
		MICROSOFT_OAUTH_ENABLED: boolean;
		MICROSOFT_CLIENT_ID: string;
		MICROSOFT_CLIENT_SECRET: string;
		MICROSOFT_CLIENT_TENANT_ID: string;
		MICROSOFT_CLIENT_LOGIN_BASE_URL: string;
		MICROSOFT_CLIENT_PICTURE_URL: string;
		MICROSOFT_OAUTH_SCOPE: string;
		MICROSOFT_REDIRECT_URI: string;
		GITHUB_OAUTH_ENABLED: boolean;
		GITHUB_CLIENT_ID: string;
		GITHUB_CLIENT_SECRET: string;
		GITHUB_CLIENT_SCOPE: string;
		GITHUB_CLIENT_REDIRECT_URI: string;
		GITHUB_ACCESS_TOKEN_URL: string;
		GITHUB_AUTHORIZE_URL: string;
		GITHUB_API_BASE_URL: string;
		GITHUB_USERINFO_ENDPOINT: string;
		DISCORD_OAUTH_ENABLED: boolean;
		DISCORD_CLIENT_ID: string;
		DISCORD_CLIENT_SECRET: string;
		DISCORD_OAUTH_SCOPE: string;
		DISCORD_REDIRECT_URI: string;
		DISCORD_ACCESS_TOKEN_URL: string;
		DISCORD_AUTHORIZE_URL: string;
		DISCORD_API_BASE_URL: string;
		DISCORD_USERINFO_ENDPOINT: string;
		OIDC_OAUTH_ENABLED: boolean;
		OAUTH_PROVIDER_NAME: string;
		OAUTH_CLIENT_ID: string;
		OAUTH_CLIENT_SECRET: string;
		OPENID_PROVIDER_URL: string;
		OPENID_REDIRECT_URI: string;
		OAUTH_SCOPES: string;
		OAUTH_TOKEN_ENDPOINT_AUTH_METHOD: string;
		OAUTH_CODE_CHALLENGE_METHOD: string;
		OAUTH_SUB_CLAIM: string;
		OAUTH_USERNAME_CLAIM: string;
		OAUTH_EMAIL_CLAIM: string;
		OAUTH_PICTURE_CLAIM: string;
		OAUTH_GROUPS_CLAIM: string;
		FEISHU_OAUTH_ENABLED: boolean;
		FEISHU_CLIENT_ID: string;
		FEISHU_CLIENT_SECRET: string;
		FEISHU_OAUTH_SCOPE: string;
		FEISHU_REDIRECT_URI: string;
		FEISHU_ACCESS_TOKEN_URL: string;
		FEISHU_AUTHORIZE_URL: string;
		FEISHU_API_BASE_URL: string;
		FEISHU_USERINFO_ENDPOINT: string;
	};

	let adminConfig: SSOConfig | null = null;

	const normalizeConfig = (configData: Record<string, unknown>): SSOConfig => ({
		...configData,
		ENABLE_OAUTH_LOGIN: Boolean(configData?.ENABLE_OAUTH_LOGIN ?? true),
		ENABLE_OAUTH_SIGNUP: Boolean(configData?.ENABLE_OAUTH_SIGNUP ?? false),
		OAUTH_MERGE_ACCOUNTS_BY_EMAIL: Boolean(configData?.OAUTH_MERGE_ACCOUNTS_BY_EMAIL ?? false),
		OAUTH_TIMEOUT: String(configData?.OAUTH_TIMEOUT ?? ''),
		OAUTH_AUDIENCE: String(configData?.OAUTH_AUDIENCE ?? ''),
		GOOGLE_OAUTH_ENABLED: Boolean(configData?.GOOGLE_OAUTH_ENABLED ?? true),
		GOOGLE_CLIENT_ID: String(configData?.GOOGLE_CLIENT_ID ?? ''),
		GOOGLE_CLIENT_SECRET: String(configData?.GOOGLE_CLIENT_SECRET ?? ''),
		GOOGLE_OAUTH_SCOPE: String(configData?.GOOGLE_OAUTH_SCOPE ?? 'openid email profile'),
		GOOGLE_SERVER_METADATA_URL: String(
			configData?.GOOGLE_SERVER_METADATA_URL ??
				'https://accounts.google.com/.well-known/openid-configuration'
		),
		GOOGLE_REDIRECT_URI: String(configData?.GOOGLE_REDIRECT_URI ?? ''),
		MICROSOFT_OAUTH_ENABLED: Boolean(configData?.MICROSOFT_OAUTH_ENABLED ?? true),
		MICROSOFT_CLIENT_ID: String(configData?.MICROSOFT_CLIENT_ID ?? ''),
		MICROSOFT_CLIENT_SECRET: String(configData?.MICROSOFT_CLIENT_SECRET ?? ''),
		MICROSOFT_CLIENT_TENANT_ID: String(configData?.MICROSOFT_CLIENT_TENANT_ID ?? ''),
		MICROSOFT_CLIENT_LOGIN_BASE_URL: String(
			configData?.MICROSOFT_CLIENT_LOGIN_BASE_URL ?? 'https://login.microsoftonline.com'
		),
		MICROSOFT_CLIENT_PICTURE_URL: String(
			configData?.MICROSOFT_CLIENT_PICTURE_URL ?? 'https://graph.microsoft.com/v1.0/me/photo/$value'
		),
		MICROSOFT_OAUTH_SCOPE: String(configData?.MICROSOFT_OAUTH_SCOPE ?? 'openid email profile'),
		MICROSOFT_REDIRECT_URI: String(configData?.MICROSOFT_REDIRECT_URI ?? ''),
		GITHUB_OAUTH_ENABLED: Boolean(configData?.GITHUB_OAUTH_ENABLED ?? true),
		GITHUB_CLIENT_ID: String(configData?.GITHUB_CLIENT_ID ?? ''),
		GITHUB_CLIENT_SECRET: String(configData?.GITHUB_CLIENT_SECRET ?? ''),
		GITHUB_CLIENT_SCOPE: String(configData?.GITHUB_CLIENT_SCOPE ?? 'user:email'),
		GITHUB_CLIENT_REDIRECT_URI: String(configData?.GITHUB_CLIENT_REDIRECT_URI ?? ''),
		GITHUB_ACCESS_TOKEN_URL: String(
			configData?.GITHUB_ACCESS_TOKEN_URL ?? 'https://github.com/login/oauth/access_token'
		),
		GITHUB_AUTHORIZE_URL: String(
			configData?.GITHUB_AUTHORIZE_URL ?? 'https://github.com/login/oauth/authorize'
		),
		GITHUB_API_BASE_URL: String(configData?.GITHUB_API_BASE_URL ?? 'https://api.github.com'),
		GITHUB_USERINFO_ENDPOINT: String(
			configData?.GITHUB_USERINFO_ENDPOINT ?? 'https://api.github.com/user'
		),
		DISCORD_OAUTH_ENABLED: Boolean(configData?.DISCORD_OAUTH_ENABLED ?? true),
		DISCORD_CLIENT_ID: String(configData?.DISCORD_CLIENT_ID ?? ''),
		DISCORD_CLIENT_SECRET: String(configData?.DISCORD_CLIENT_SECRET ?? ''),
		DISCORD_OAUTH_SCOPE: String(configData?.DISCORD_OAUTH_SCOPE ?? 'identify email'),
		DISCORD_REDIRECT_URI: String(configData?.DISCORD_REDIRECT_URI ?? ''),
		DISCORD_ACCESS_TOKEN_URL: String(
			configData?.DISCORD_ACCESS_TOKEN_URL ?? 'https://discord.com/api/oauth2/token'
		),
		DISCORD_AUTHORIZE_URL: String(
			configData?.DISCORD_AUTHORIZE_URL ?? 'https://discord.com/oauth2/authorize'
		),
		DISCORD_API_BASE_URL: String(configData?.DISCORD_API_BASE_URL ?? 'https://discord.com/api'),
		DISCORD_USERINFO_ENDPOINT: String(
			configData?.DISCORD_USERINFO_ENDPOINT ?? 'https://discord.com/api/users/@me'
		),
		OIDC_OAUTH_ENABLED: Boolean(configData?.OIDC_OAUTH_ENABLED ?? true),
		OAUTH_PROVIDER_NAME: String(configData?.OAUTH_PROVIDER_NAME ?? 'SSO'),
		OAUTH_CLIENT_ID: String(configData?.OAUTH_CLIENT_ID ?? ''),
		OAUTH_CLIENT_SECRET: String(configData?.OAUTH_CLIENT_SECRET ?? ''),
		OPENID_PROVIDER_URL: String(configData?.OPENID_PROVIDER_URL ?? ''),
		OPENID_REDIRECT_URI: String(configData?.OPENID_REDIRECT_URI ?? ''),
		OAUTH_SCOPES: String(configData?.OAUTH_SCOPES ?? 'openid email profile'),
		OAUTH_TOKEN_ENDPOINT_AUTH_METHOD: String(configData?.OAUTH_TOKEN_ENDPOINT_AUTH_METHOD ?? ''),
		OAUTH_CODE_CHALLENGE_METHOD: String(configData?.OAUTH_CODE_CHALLENGE_METHOD ?? ''),
		OAUTH_SUB_CLAIM: String(configData?.OAUTH_SUB_CLAIM ?? ''),
		OAUTH_USERNAME_CLAIM: String(configData?.OAUTH_USERNAME_CLAIM ?? 'name'),
		OAUTH_EMAIL_CLAIM: String(configData?.OAUTH_EMAIL_CLAIM ?? 'email'),
		OAUTH_PICTURE_CLAIM: String(configData?.OAUTH_PICTURE_CLAIM ?? 'picture'),
		OAUTH_GROUPS_CLAIM: String(configData?.OAUTH_GROUPS_CLAIM ?? 'groups'),
		FEISHU_OAUTH_ENABLED: Boolean(configData?.FEISHU_OAUTH_ENABLED ?? true),
		FEISHU_CLIENT_ID: String(configData?.FEISHU_CLIENT_ID ?? ''),
		FEISHU_CLIENT_SECRET: String(configData?.FEISHU_CLIENT_SECRET ?? ''),
		FEISHU_OAUTH_SCOPE: String(configData?.FEISHU_OAUTH_SCOPE ?? 'contact:user.base:readonly'),
		FEISHU_REDIRECT_URI: String(configData?.FEISHU_REDIRECT_URI ?? ''),
		FEISHU_ACCESS_TOKEN_URL: String(
			configData?.FEISHU_ACCESS_TOKEN_URL ??
				'https://open.feishu.cn/open-apis/authen/v2/oauth/token'
		),
		FEISHU_AUTHORIZE_URL: String(
			configData?.FEISHU_AUTHORIZE_URL ?? 'https://accounts.feishu.cn/open-apis/authen/v1/authorize'
		),
		FEISHU_API_BASE_URL: String(
			configData?.FEISHU_API_BASE_URL ?? 'https://open.feishu.cn/open-apis'
		),
		FEISHU_USERINFO_ENDPOINT: String(
			configData?.FEISHU_USERINFO_ENDPOINT ?? 'https://open.feishu.cn/open-apis/authen/v1/user_info'
		)
	});

	const saveHandler = async () => {
		if (!adminConfig) {
			return;
		}

		const response = await updateAdminConfig(localStorage.token, adminConfig).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (response) {
			adminConfig = normalizeConfig(response);
			toast.success(t('SSO management settings updated'));
		}
	};

	onMount(async () => {
		const configResponse = await getAdminConfig(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (configResponse) {
			adminConfig = normalizeConfig(configResponse);
		}
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
					<div class="text-base font-medium">{$i18n.t('SSO Management')}</div>
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t(
							'Configure OAuth providers and advanced runtime behavior. Changes apply immediately.'
						)}
					</div>

					<div class="grid gap-3 sm:grid-cols-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between"
						>
							<div>
								<div class="text-sm font-medium">{$i18n.t('Merge Accounts By Email')}</div>
								<div class="text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Link OAuth users to existing accounts with matching emails.')}
								</div>
							</div>
							<Switch bind:state={adminConfig.OAUTH_MERGE_ACCOUNTS_BY_EMAIL} />
						</div>

						<div class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 space-y-2">
							<div class="text-sm font-medium">{$i18n.t('OAuth Timeout (seconds)')}</div>
							<input
								type="text"
								bind:value={adminConfig.OAUTH_TIMEOUT}
								class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
								placeholder="30"
							/>
						</div>

						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 space-y-2 sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('OAuth Audience')}</div>
							<input
								type="text"
								bind:value={adminConfig.OAUTH_AUDIENCE}
								class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							/>
						</div>
					</div>
				</div>

				<details
					open
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">Google</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable Google')}</div>
							<Switch bind:state={adminConfig.GOOGLE_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.GOOGLE_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.GOOGLE_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.GOOGLE_OAUTH_SCOPE}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.GOOGLE_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.GOOGLE_SERVER_METADATA_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5 sm:col-span-2"
							placeholder="Server metadata URL"
						/>
					</div>
				</details>

				<details
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">Microsoft</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable Microsoft')}</div>
							<Switch bind:state={adminConfig.MICROSOFT_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.MICROSOFT_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_CLIENT_TENANT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Tenant ID"
						/>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_OAUTH_SCOPE}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_CLIENT_LOGIN_BASE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Login base URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.MICROSOFT_CLIENT_PICTURE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5 sm:col-span-2"
							placeholder="Picture URL"
						/>
					</div>
				</details>

				<details
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">GitHub</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable GitHub')}</div>
							<Switch bind:state={adminConfig.GITHUB_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.GITHUB_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_CLIENT_SCOPE}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_CLIENT_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_AUTHORIZE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Authorize URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_ACCESS_TOKEN_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Access token URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_API_BASE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="API base URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.GITHUB_USERINFO_ENDPOINT}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Userinfo endpoint"
						/>
					</div>
				</details>

				<details
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">Discord</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable Discord')}</div>
							<Switch bind:state={adminConfig.DISCORD_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.DISCORD_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_OAUTH_SCOPE}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_AUTHORIZE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Authorize URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_ACCESS_TOKEN_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Access token URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_API_BASE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="API base URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.DISCORD_USERINFO_ENDPOINT}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Userinfo endpoint"
						/>
					</div>
				</details>

				<details
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">OIDC</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable OIDC')}</div>
							<Switch bind:state={adminConfig.OIDC_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_PROVIDER_NAME}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Provider name"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.OAUTH_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.OPENID_PROVIDER_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Provider URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.OPENID_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_SCOPES}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_TOKEN_ENDPOINT_AUTH_METHOD}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Token endpoint auth method"
						/>
						<select
							bind:value={adminConfig.OAUTH_CODE_CHALLENGE_METHOD}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
						>
							<option value="">{$i18n.t('None')}</option>
							<option value="S256">S256</option>
						</select>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_SUB_CLAIM}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Sub claim"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_USERNAME_CLAIM}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Username claim"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_EMAIL_CLAIM}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Email claim"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_PICTURE_CLAIM}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Picture claim"
						/>
						<input
							type="text"
							bind:value={adminConfig.OAUTH_GROUPS_CLAIM}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Groups claim"
						/>
					</div>
				</details>

				<details
					class="rounded-2xl border border-gray-100/80 dark:border-gray-850/80 bg-gray-50/40 dark:bg-gray-900/40 p-4 space-y-3"
				>
					<summary class="cursor-pointer text-base font-medium">Feishu</summary>
					<div class="grid gap-3 sm:grid-cols-2 pt-2">
						<div
							class="rounded-lg border border-gray-200/80 dark:border-gray-800 p-3 flex items-center justify-between sm:col-span-2"
						>
							<div class="text-sm font-medium">{$i18n.t('Enable Feishu')}</div>
							<Switch bind:state={adminConfig.FEISHU_OAUTH_ENABLED} />
						</div>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_CLIENT_ID}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client ID"
						/>
						<input
							type="password"
							bind:value={adminConfig.FEISHU_CLIENT_SECRET}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Client Secret"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_OAUTH_SCOPE}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Scopes"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_REDIRECT_URI}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Redirect URI"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_AUTHORIZE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Authorize URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_ACCESS_TOKEN_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Access token URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_API_BASE_URL}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="API base URL"
						/>
						<input
							type="text"
							bind:value={adminConfig.FEISHU_USERINFO_ENDPOINT}
							class="w-full bg-transparent text-sm outline-hidden border border-gray-200/70 dark:border-gray-850/70 rounded-md px-2 py-1.5"
							placeholder="Userinfo endpoint"
						/>
					</div>
				</details>
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
