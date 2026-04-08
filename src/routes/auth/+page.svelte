<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';

	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import {
		ldapUserSignIn,
		getSessionUser,
		userSignIn,
		userSignUp,
		updateUserTimezone
	} from '$lib/apis/auths';

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';

	import { generateInitialsImage, getUserTimezone } from '$lib/utils';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import UpdatePassword from '$lib/components/chat/Settings/Account/UpdatePassword.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	let mode = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let form = null;

	let name = '';
	let email = '';
	let password = '';
	let confirmPassword = '';
	let inviteCode = '';
	let visibleOAuthProviders: string[] = [];
	let requiresPasswordSetup = false;
	let passwordSetupRedirectPath: string | null = null;

	let ldapUsername = '';

	$: if (mode === 'signup' && !($config?.features?.enable_password_signup ?? true)) {
		mode = $config?.features.enable_ldap ? 'ldap' : 'signin';
	}

	let showGuestNotification = false;
	let guestNotificationTitle = '';
	let guestNotificationDescription = '';

	const evaluateGuestNotification = () => {
		const enabled = Boolean($config?.ui?.system_notice?.enabled ?? false);
		const title = String($config?.ui?.system_notice?.title ?? '').trim();
		const description = String($config?.ui?.system_notice?.content ?? '').trim();

		showGuestNotification = enabled && (title.length > 0 || description.length > 0);
		guestNotificationTitle = title || 'Notice';
		guestNotificationDescription = description;
	};

	const sessionNeedsPasswordSetup = (sessionUser) =>
		Boolean(
			sessionUser && (sessionUser.password_change_required || sessionUser.has_password === false)
		);

	const setSessionUser = async (sessionUser, redirectPath: string | null = null) => {
		if (sessionUser) {
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			// Update user timezone
			const timezone = getUserTimezone();
			if (sessionUser.token && timezone) {
				updateUserTimezone(sessionUser.token, timezone);
			}

			if (!redirectPath) {
				redirectPath = $page.url.searchParams.get('redirect') || '/';
			}

			if (sessionNeedsPasswordSetup(sessionUser)) {
				requiresPasswordSetup = true;
				passwordSetupRedirectPath = redirectPath;
				toast.info($i18n.t('Set a password to finish signing in.'));
				return;
			}

			requiresPasswordSetup = false;
			passwordSetupRedirectPath = null;
			toast.success($i18n.t(`You're now logged in.`));
			goto(redirectPath);
			localStorage.removeItem('redirectPath');
		}
	};

	const completePasswordSetup = async () => {
		const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!sessionUser) {
			return;
		}

		await setSessionUser(
			sessionUser,
			passwordSetupRedirectPath || localStorage.getItem('redirectPath') || null
		);
	};

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		if ($config?.features?.enable_signup_password_confirmation) {
			if (password !== confirmPassword) {
				toast.error($i18n.t('Passwords do not match.'));
				return;
			}
		}

		const sessionUser = await userSignUp(
			name,
			email,
			password,
			generateInitialsImage(name),
			inviteCode
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else {
			if (!($config?.features?.enable_password_signup ?? true)) {
				toast.error($i18n.t('Email and password signups are disabled.'));
				return;
			}
			await signUpHandler();
		}
	};

	const getOAuthLoginUrl = (provider: string) => {
		const inviteCodeParam = inviteCode.trim()
			? `?invite_code=${encodeURIComponent(inviteCode.trim())}`
			: '';
		return `${WEBUI_BASE_URL}/oauth/${provider}/login${inviteCodeParam}`;
	};

	const getAllowedOAuthProviders = (target: 'login' | 'signup') => {
		const configuredProviders = Object.keys($config?.oauth?.providers ?? {});
		const rawAllowedProviders =
			target === 'login'
				? $config?.oauth?.allowed_login_providers
				: $config?.oauth?.allowed_signup_providers;

		if (!Array.isArray(rawAllowedProviders)) {
			return configuredProviders;
		}

		const configuredProviderSet = new Set(configuredProviders);
		return rawAllowedProviders
			.map((provider) => String(provider).trim().toLowerCase())
			.filter((provider) => configuredProviderSet.has(provider));
	};

	const getVisibleOAuthProviders = () => {
		const loginProviders = getAllowedOAuthProviders('login');
		if (mode !== 'signup') {
			return loginProviders;
		}

		if (!($config?.features?.enable_oauth_signup ?? false)) {
			return [];
		}

		const signupProviders = new Set(getAllowedOAuthProviders('signup'));
		return loginProviders.filter((provider) => signupProviders.has(provider));
	};

	$: visibleOAuthProviders = getVisibleOAuthProviders();
	$: evaluateGuestNotification();

	const oauthCallbackHandler = async () => {
		// Get the value of the 'token' cookie
		function getCookie(name) {
			const match = document.cookie.match(
				new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
			);
			return match ? decodeURIComponent(match[1]) : null;
		}

		const token = getCookie('token');
		if (!token) {
			return;
		}

		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!sessionUser) {
			return;
		}

		localStorage.token = token;
		await setSessionUser(sessionUser, localStorage.getItem('redirectPath') || null);
	};

	let onboarding = false;

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = `${WEBUI_BASE_URL}/static/favicon-dark.png`;

				darkImage.onload = () => {
					logo.src = `${WEBUI_BASE_URL}/static/favicon-dark.png`;
					logo.style.filter = ''; // Ensure no inversion is applied if favicon-dark.png exists
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)'; // Invert image if favicon-dark.png is missing
				};
			}
		}
	}

	onMount(async () => {
		const redirectPath = $page.url.searchParams.get('redirect');
		if ($user !== undefined) {
			if (sessionNeedsPasswordSetup($user)) {
				requiresPasswordSetup = true;
				passwordSetupRedirectPath = redirectPath || localStorage.getItem('redirectPath') || '/';
			} else {
				goto(redirectPath || '/');
			}
		} else {
			if (redirectPath) {
				localStorage.setItem('redirectPath', redirectPath);
			}
		}

		const error = $page.url.searchParams.get('error');
		if (error) {
			toast.error(error);
		}

		await oauthCallbackHandler();
		form = $page.url.searchParams.get('form');

		loaded = true;
		setLogoImage();

		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		} else {
			onboarding = $config?.onboarding ?? false;
		}
	});
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div class="w-full h-screen max-h-[100dvh] text-white relative" id="auth-page">
	<div class="w-full h-full absolute top-0 left-0 bg-white dark:bg-black"></div>

	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region"></div>

	{#if loaded}
		<div
			class="fixed bg-transparent min-h-screen w-full flex justify-center font-primary z-50 text-black dark:text-white"
			id="auth-container"
		>
			<div class="w-full px-10 min-h-screen flex flex-col text-center">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<div class=" my-auto pb-10 w-full sm:max-w-md">
						<div
							class="flex items-center justify-center gap-3 text-xl sm:text-2xl text-center font-medium dark:text-gray-200"
						>
							<div>
								{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}
							</div>

							<div>
								<Spinner className="size-5" />
							</div>
						</div>
					</div>
				{:else}
					<div class="my-auto flex flex-col justify-center items-center">
						<div class=" sm:max-w-md my-auto pb-10 w-full dark:text-gray-100">
							{#if $config?.metadata?.auth_logo_position === 'center'}
								<div class="flex justify-center mb-6">
									<img
										id="logo"
										crossorigin="anonymous"
										src="{WEBUI_BASE_URL}/static/favicon.png"
										class="size-24 rounded-full"
										alt="{$WEBUI_NAME} logo"
									/>
								</div>
							{/if}
							{#if requiresPasswordSetup}
								<div
									class="flex flex-col justify-center text-left rounded-2xl border border-gray-200/80 dark:border-gray-800/90 bg-gray-50/80 dark:bg-gray-900/70 p-5 shadow-sm"
								>
									<div class="text-2xl font-medium text-center">
										{$i18n.t('Set Your Password')}
									</div>
									<div class="mt-2 text-sm text-center text-gray-600 dark:text-gray-400">
										{$i18n.t('Finish signing in by choosing a password for {{email}}.', {
											email: $user?.email ?? email
										})}
									</div>
									<div class="mt-5">
										<UpdatePassword
											showByDefault={true}
											forceSetup={true}
											hideToggle={true}
											description={$i18n.t(
												'You will be taken back to the app as soon as your new password is saved.'
											)}
											onSuccess={completePasswordSetup}
										/>
									</div>
								</div>
							{:else}
								<form
									class=" flex flex-col justify-center"
									on:submit={(e) => {
										e.preventDefault();
										submitHandler();
									}}
								>
									{#if showGuestNotification}
										<div
											class="mb-4 w-full rounded-2xl border border-gray-200/80 dark:border-gray-800/90 bg-gray-50/80 dark:bg-gray-900/70 p-4 sm:p-5 text-left shadow-sm"
										>
											<div
												class="text-base sm:text-lg font-semibold text-gray-900 dark:text-gray-100"
											>
												{guestNotificationTitle}
											</div>
											{#if guestNotificationDescription}
												<div
													class="mt-2 text-sm leading-relaxed text-gray-700 dark:text-gray-300 marked"
												>
													{@html DOMPurify.sanitize(marked(guestNotificationDescription))}
												</div>
											{/if}
										</div>
									{/if}

									<div class="mb-1">
										<div class=" text-2xl font-medium">
											{#if $config?.onboarding ?? false}
												{$i18n.t(`Get started with {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
											{:else if mode === 'ldap'}
												{$i18n.t(`Sign in to {{WEBUI_NAME}} with LDAP`, {
													WEBUI_NAME: $WEBUI_NAME
												})}
											{:else if mode === 'signin'}
												{$i18n.t(`Sign in to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
											{:else}
												{$i18n.t(`Sign up to {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
											{/if}
										</div>

										{#if $config?.onboarding ?? false}
											<div class="mt-1 text-xs font-medium text-gray-600 dark:text-gray-500">
												i {$WEBUI_NAME}
												{$i18n.t(
													'does not make any external connections, and your data stays securely on your locally hosted server.'
												)}
											</div>
										{/if}
									</div>

									{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
										<div class="flex flex-col mt-4">
											{#if mode === 'signup'}
												<div class="mb-2">
													<label for="name" class="text-sm font-medium text-left mb-1 block"
														>{$i18n.t('Name')}</label
													>
													<input
														bind:value={name}
														type="text"
														id="name"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
														autocomplete="name"
														placeholder={$i18n.t('Enter Your Full Name')}
														required
													/>
												</div>
											{/if}

											{#if mode === 'ldap'}
												<div class="mb-2">
													<label for="username" class="text-sm font-medium text-left mb-1 block"
														>{$i18n.t('Username')}</label
													>
													<input
														bind:value={ldapUsername}
														type="text"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
														autocomplete="username"
														name="username"
														id="username"
														placeholder={$i18n.t('Enter Your Username')}
														required
													/>
												</div>
											{:else}
												<div class="mb-2">
													<label for="email" class="text-sm font-medium text-left mb-1 block"
														>{$i18n.t('Email')}</label
													>
													<input
														bind:value={email}
														type="email"
														id="email"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
														autocomplete="email"
														name="email"
														placeholder={$i18n.t('Enter Your Email')}
														required
													/>
												</div>
											{/if}

											<div>
												<label for="password" class="text-sm font-medium text-left mb-1 block"
													>{$i18n.t('Password')}</label
												>
												<SensitiveInput
													bind:value={password}
													type="password"
													id="password"
													class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
													placeholder={$i18n.t('Enter Your Password')}
													autocomplete={mode === 'signup' ? 'new-password' : 'current-password'}
													name="password"
													screenReader={true}
													required
													aria-required="true"
												/>
											</div>

											{#if mode === 'signup' && $config?.features?.enable_signup_password_confirmation}
												<div class="mt-2">
													<label
														for="confirm-password"
														class="text-sm font-medium text-left mb-1 block"
														>{$i18n.t('Confirm Password')}</label
													>
													<SensitiveInput
														bind:value={confirmPassword}
														type="password"
														id="confirm-password"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent"
														placeholder={$i18n.t('Confirm Your Password')}
														autocomplete="new-password"
														name="confirm-password"
														required
													/>
												</div>
											{/if}

											{#if mode === 'signup' && $config?.features?.enable_invite_only_auth}
												<div class="mt-2">
													<label for="invite-code" class="text-sm font-medium text-left mb-1 block"
														>{$i18n.t('Invite Code')}</label
													>
													<input
														bind:value={inviteCode}
														type="text"
														id="invite-code"
														class="my-0.5 w-full text-sm outline-hidden bg-transparent placeholder:text-gray-300 dark:placeholder:text-gray-600"
														placeholder={$i18n.t('Enter your invite code')}
														required
													/>
												</div>
											{/if}
										</div>
									{/if}
									<div class="mt-5">
										{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
											{#if mode === 'ldap'}
												<button
													class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
													type="submit"
												>
													{$i18n.t('Authenticate')}
												</button>
											{:else}
												<button
													class="bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
													type="submit"
												>
													{mode === 'signin'
														? $i18n.t('Sign in')
														: ($config?.onboarding ?? false)
															? $i18n.t('Create Admin Account')
															: $i18n.t('Create Account')}
												</button>

												{#if $config?.features.enable_signup && ($config?.features.enable_password_signup ?? true) && !($config?.onboarding ?? false)}
													<div class=" mt-4 text-sm text-center">
														{mode === 'signin'
															? $i18n.t("Don't have an account?")
															: $i18n.t('Already have an account?')}

														<button
															class=" font-medium underline"
															type="button"
															on:click={() => {
																if (mode === 'signin') {
																	mode = 'signup';
																} else {
																	mode = 'signin';
																}
															}}
														>
															{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
														</button>
													</div>
												{/if}
											{/if}
										{/if}
									</div>
								</form>

								{#if ($config?.features?.enable_oauth_login ?? true) && visibleOAuthProviders.length > 0}
									<div class="inline-flex items-center justify-center w-full">
										<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
										{#if $config?.features.enable_login_form || $config?.features.enable_ldap || form}
											<span
												class="px-3 text-sm font-medium text-gray-900 dark:text-white bg-transparent"
												>{$i18n.t('or')}</span
											>
										{/if}

										<hr class="w-32 h-px my-4 border-0 dark:bg-gray-100/10 bg-gray-700/10" />
									</div>
									<div class="flex flex-col space-y-2">
										{#if visibleOAuthProviders.includes('google')}
											<button
												class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('google');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 48 48"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														fill="#EA4335"
														d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
													/><path
														fill="#4285F4"
														d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
													/><path
														fill="#FBBC05"
														d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
													/><path
														fill="#34A853"
														d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
													/><path fill="none" d="M0 0h48v48H0z" />
												</svg>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('microsoft')}
											<button
												class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('microsoft');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 21 21"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
														x="1"
														y="11"
														width="9"
														height="9"
														fill="#00a4ef"
													/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
														x="11"
														y="11"
														width="9"
														height="9"
														fill="#ffb900"
													/>
												</svg>
												<span
													>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span
												>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('github')}
											<button
												class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('github');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 24 24"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														fill="currentColor"
														d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z"
													/>
												</svg>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitHub' })}</span>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('gitlab')}
											<button
												class="flex justify-center items-center bg-orange-500/10 hover:bg-orange-500/20 text-orange-700 dark:text-orange-300 transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('gitlab');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 24 24"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														fill="currentColor"
														d="m22.5 9.5-2.1-6.5a.8.8 0 0 0-.76-.54H4.36a.8.8 0 0 0-.76.54L1.5 9.5a1.43 1.43 0 0 0 .52 1.6l9.47 7.02 9.47-7.02a1.43 1.43 0 0 0 .52-1.6Z"
													/>
													<path fill="#FC6D26" d="M12 18.2 15.5 7.4h-7L12 18.2Z" />
													<path fill="#FCA326" d="M8.5 7.4 6.9 2.5H4.3l4.2 4.9Z" />
												</svg>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'GitLab' })}</span>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('slack')}
											<button
												class="flex justify-center items-center bg-purple-500/10 hover:bg-purple-500/20 text-purple-700 dark:text-purple-300 transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('slack');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 24 24"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														fill="currentColor"
														d="M6.3 15.2a2 2 0 1 1-2 2h2v-2Zm1 0h3v2a2 2 0 1 1-2-2h-1v-0Zm1-8a2 2 0 1 1 2 2h-2v-2Zm0 1h2.9v3H8.3a2 2 0 1 1 0-3Zm8 1a2 2 0 1 1 2-2v2h-2Zm-1 0V6.3h2v2.9a2 2 0 1 1-2 0Zm1 8a2 2 0 1 1-2-2h2v2Zm-1-1h-2.9v-3h2.9a2 2 0 1 1 0 3Z"
													/>
												</svg>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'Slack' })}</span>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('oidc')}
											<button
												class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('oidc');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="1.5"
													stroke="currentColor"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
													/>
												</svg>

												<span
													>{$i18n.t('Continue with {{provider}}', {
														provider: $config?.oauth?.providers?.oidc ?? 'SSO'
													})}</span
												>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('feishu')}
											<button
												class="flex justify-center items-center bg-gray-700/5 hover:bg-gray-700/10 dark:bg-gray-100/5 dark:hover:bg-gray-100/10 dark:text-gray-300 dark:hover:text-white transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('feishu');
												}}
											>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'Feishu' })}</span>
											</button>
										{/if}
										{#if visibleOAuthProviders.includes('discord')}
											<button
												class="flex justify-center items-center bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 transition w-full rounded-full font-medium text-sm py-2.5"
												on:click={() => {
													window.location.href = getOAuthLoginUrl('discord');
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 256 199"
													class="size-6 mr-3"
													aria-hidden="true"
												>
													<path
														fill="currentColor"
														d="M216.9 16.6A208.5 208.5 0 0 0 163.3 0a150.5 150.5 0 0 0-6.8 13.9a193.2 193.2 0 0 0-57 0A150.5 150.5 0 0 0 92.7 0A208.5 208.5 0 0 0 39.1 16.6C5.2 67.5-3.9 117.1.6 165.8a209.9 209.9 0 0 0 64.7 33.2a161.8 161.8 0 0 0 13.9-22.6a133.7 133.7 0 0 1-21.9-10.5c1.9-1.4 3.7-2.8 5.4-4.3c42.3 19.8 88.2 19.8 130 0c1.8 1.5 3.6 2.9 5.4 4.3a133.7 133.7 0 0 1-21.9 10.5a161.8 161.8 0 0 0 13.9 22.6a209.9 209.9 0 0 0 64.7-33.2c5.3-56.4-9.1-105.5-37.9-149.2ZM85.5 135.6c-12.6 0-22.9-11.6-22.9-25.8s10.1-25.8 22.9-25.8s23.1 11.6 22.9 25.8s-10.2 25.8-22.9 25.8Zm84.9 0c-12.6 0-22.9-11.6-22.9-25.8s10.1-25.8 22.9-25.8s23.1 11.6 22.9 25.8s-10.2 25.8-22.9 25.8Z"
													/>
												</svg>
												<span>{$i18n.t('Continue with {{provider}}', { provider: 'Discord' })}</span
												>
											</button>
										{/if}
									</div>
								{/if}

								{#if $config?.features.enable_ldap && $config?.features.enable_login_form}
									<div class="mt-2">
										<button
											class="flex justify-center items-center text-xs w-full text-center underline"
											type="button"
											on:click={() => {
												if (mode === 'ldap')
													mode = ($config?.onboarding ?? false) ? 'signup' : 'signin';
												else mode = 'ldap';
											}}
										>
											<span
												>{mode === 'ldap'
													? $i18n.t('Continue with Email')
													: $i18n.t('Continue with LDAP')}</span
											>
										</button>
									</div>
								{/if}
							{/if}
						</div>
						{#if $config?.metadata?.login_footer}
							<div class="max-w-3xl mx-auto">
								<div class="mt-2 text-[0.7rem] text-gray-500 dark:text-gray-400 marked">
									{@html DOMPurify.sanitize(marked($config?.metadata?.login_footer))}
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		{#if !$config?.metadata?.auth_logo_position}
			<div class="fixed m-10 z-50">
				<div class="flex space-x-2">
					<div class=" self-center">
						<img
							id="logo"
							crossorigin="anonymous"
							src="{WEBUI_BASE_URL}/static/favicon.png"
							class=" w-6 rounded-full"
							alt=""
						/>
					</div>
				</div>
			</div>
		{/if}
	{/if}
</div>
