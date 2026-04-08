<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getSessionUser, updateUserPassword } from '$lib/apis/auths';
	import { user } from '$lib/stores';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';

	const i18n = getContext('i18n');

	export let showByDefault = false;
	export let forceSetup = false;
	export let title: string | null = null;
	export let description: string | null = null;
	export let submitLabel: string | null = null;
	export let hideToggle = false;
	export let onSuccess: (() => void | Promise<void>) | null = null;

	let show = showByDefault;
	let currentPassword = '';
	let newPassword = '';
	let newPasswordConfirm = '';

	$: if (showByDefault) {
		show = true;
	}

	$: requiresCurrentPassword =
		!forceSetup && !($user?.password_change_required || $user?.has_password === false);

	$: resolvedTitle =
		title ?? (requiresCurrentPassword ? $i18n.t('Change Password') : $i18n.t('Set Password'));

	$: resolvedDescription =
		description ??
		(requiresCurrentPassword
			? ''
			: $i18n.t('Choose a password for your account before continuing.'));

	$: resolvedSubmitLabel =
		submitLabel ?? (requiresCurrentPassword ? $i18n.t('Update password') : $i18n.t('Set password'));

	const updatePasswordHandler = async () => {
		if (requiresCurrentPassword && !currentPassword.trim()) {
			toast.error($i18n.t('Enter your current password.'));
			return;
		}

		if (newPassword === newPasswordConfirm) {
			const res = await updateUserPassword(
				localStorage.token,
				requiresCurrentPassword ? currentPassword : null,
				newPassword
			).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (res) {
				const sessionUser = await getSessionUser(localStorage.token).catch((error) => {
					toast.error(`${error}`);
					return null;
				});

				if (sessionUser) {
					await user.set(sessionUser);
				}

				toast.success($i18n.t('Successfully updated.'));

				if (onSuccess) {
					await onSuccess();
				}
			}

			currentPassword = '';
			newPassword = '';
			newPasswordConfirm = '';
		} else {
			toast.error(
				$i18n.t("The passwords you entered don't quite match. Please double-check and try again.")
			);
			newPassword = '';
			newPasswordConfirm = '';
		}
	};
</script>

<form
	class="flex flex-col text-sm"
	on:submit|preventDefault={() => {
		updatePasswordHandler();
	}}
>
	<div class="flex justify-between items-center text-sm">
		<div class="font-medium">{resolvedTitle}</div>
		{#if !hideToggle}
			<button
				class=" text-xs font-medium text-gray-500"
				type="button"
				on:click={() => {
					show = !show;
				}}>{show ? $i18n.t('Hide') : $i18n.t('Show')}</button
			>
		{/if}
	</div>

	{#if show}
		<div class=" py-2.5 space-y-1.5">
			{#if resolvedDescription}
				<div class="text-xs text-gray-500">{resolvedDescription}</div>
			{/if}

			{#if requiresCurrentPassword}
				<div class="flex flex-col w-full">
					<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Current Password')}</div>

					<div class="flex-1">
						<SensitiveInput
							class="w-full bg-transparent text-sm dark:text-gray-300 outline-hidden placeholder:opacity-30"
							type="password"
							bind:value={currentPassword}
							placeholder={$i18n.t('Enter your current password')}
							autocomplete="current-password"
							required
						/>
					</div>
				</div>
			{/if}

			<div class="flex flex-col w-full">
				<div class=" mb-1 text-xs text-gray-500">{$i18n.t('New Password')}</div>

				<div class="flex-1">
					<SensitiveInput
						class="w-full bg-transparent text-sm dark:text-gray-300 outline-hidden placeholder:opacity-30"
						type="password"
						bind:value={newPassword}
						placeholder={$i18n.t('Enter your new password')}
						autocomplete="new-password"
						required
					/>
				</div>
			</div>

			<div class="flex flex-col w-full">
				<div class=" mb-1 text-xs text-gray-500">{$i18n.t('Confirm Password')}</div>

				<div class="flex-1">
					<SensitiveInput
						class="w-full bg-transparent text-sm dark:text-gray-300 outline-hidden placeholder:opacity-30"
						type="password"
						bind:value={newPasswordConfirm}
						placeholder={$i18n.t('Confirm your new password')}
						autocomplete="off"
						required
					/>
				</div>
			</div>
		</div>

		<div class="mt-3 flex justify-end">
			<button
				class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			>
				{resolvedSubmitLabel}
			</button>
		</div>
	{/if}
</form>
