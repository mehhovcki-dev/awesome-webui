<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { createEventDispatcher, getContext, tick } from 'svelte';

	import { flyAndScale } from '$lib/utils/transitions';
	import { goto } from '$app/navigation';
	import { fade } from 'svelte/transition';

	import { getUsage } from '$lib/apis';
	import { getSessionUser, userSignOut } from '$lib/apis/auths';

	import { showSettings, mobile, showSidebar, showShortcuts, user, config } from '$lib/stores';

	import { WEBUI_API_BASE_URL, WEBUI_RELEASES_URL } from '$lib/constants';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Map from '$lib/components/icons/Map.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import Keyboard from '$lib/components/icons/Keyboard.svelte';
	import ShortcutsModal from '$lib/components/chat/ShortcutsModal.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import Code from '$lib/components/icons/Code.svelte';
	import UserGroup from '$lib/components/icons/UserGroup.svelte';
	import SignOut from '$lib/components/icons/SignOut.svelte';
	import FaceSmile from '$lib/components/icons/FaceSmile.svelte';
	import UserStatusModal from './UserStatusModal.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import { updateUserStatus } from '$lib/apis/users';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	export let show = false;
	export let role = '';

	export let profile = false;
	export let help = false;

	export let className = 'max-w-[240px]';
	export let align = 'end';

	export let showActiveUsers = true;

	let showUserStatusModal = false;

	const dispatch = createEventDispatcher();

	let usage = null;
	const getUsageInfo = async () => {
		const res = await getUsage(localStorage.token).catch((error) => {
			console.error('Error fetching usage info:', error);
		});

		if (res) {
			usage = res;
		} else {
			usage = null;
		}
	};

	const handleDropdownChange = (state: boolean) => {
		dispatch('change', state);

		// Fetch usage info when dropdown opens, if user has permission
		if (state && ($config?.features?.enable_public_active_users_count || role === 'admin')) {
			getUsageInfo();
		}
	};

	type PresenceOption = {
		id: 'online' | 'idle' | 'dnd' | 'offline';
		label: string;
		description?: string;
		colorClass: string;
	};

	const presenceOptions: PresenceOption[] = [
		{
			id: 'online',
			label: 'Online',
			description: 'All notifications',
			colorClass: 'bg-green-500'
		},
		{
			id: 'idle',
			label: 'Idle',
			description: 'Only channel and chat completion notifications',
			colorClass: 'bg-yellow-500'
		},
		{
			id: 'dnd',
			label: 'Do Not Disturb',
			description: 'You will not receive channel notifications',
			colorClass: 'bg-red-500'
		},
		{
			id: 'offline',
			label: 'Invisible',
			description: 'You will appear offline',
			colorClass: 'bg-gray-500'
		}
	];

	const getPresenceState = () => {
		const value = String($user?.presence_state ?? 'online').toLowerCase();
		return presenceOptions.some((option) => option.id === value) ? value : 'online';
	};

	const getPresenceOption = () => {
		const state = getPresenceState();
		return presenceOptions.find((option) => option.id === state) ?? presenceOptions[0];
	};

	const updatePresenceState = async (presenceState: PresenceOption['id']) => {
		const res = await updateUserStatus(localStorage.token, {
			presence_state: presenceState
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (!res) {
			toast.error($i18n.t('Failed to update status'));
			return;
		}

		user.set(await getSessionUser(localStorage.token));
	};
</script>

<ShortcutsModal bind:show={$showShortcuts} />
<UserStatusModal
	bind:show={showUserStatusModal}
	onSave={async () => {
		user.set(await getSessionUser(localStorage.token));
	}}
/>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<DropdownMenu.Root bind:open={show} onOpenChange={handleDropdownChange}>
	<DropdownMenu.Trigger>
		<slot />
	</DropdownMenu.Trigger>

	<slot name="content">
		<DropdownMenu.Content
			class="w-full {className}  rounded-2xl px-1 py-1  border border-gray-100  dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg text-sm"
			sideOffset={4}
			side="top"
			{align}
			transition={(e) => fade(e, { duration: 100 })}
		>
			{#if profile}
				<div class=" flex gap-3.5 w-full p-2.5 items-center">
					<div class=" items-center flex shrink-0">
						<img
							src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
							class=" size-10 object-cover rounded-full"
							alt="profile"
						/>
					</div>

					<div class=" flex flex-col w-full flex-1">
						<div class="font-medium line-clamp-1 pr-2">
							{$user.name}
						</div>

						<div class=" flex items-center gap-2">
							{#if getPresenceState() === 'dnd'}
								<span
									class="inline-flex size-2.5 rounded-full bg-red-500 items-center justify-center"
								>
									<span class="h-[1.5px] w-1.5 rounded-full bg-white"></span>
								</span>
							{:else if getPresenceState() === 'offline'}
								<span class="inline-flex size-2.5 rounded-full border-2 border-gray-500"></span>
							{:else}
								<span
									class="relative inline-flex rounded-full size-2.5 {getPresenceOption()
										.colorClass}"
								></span>
							{/if}

							<span class="text-xs"> {$i18n.t(getPresenceOption().label)} </span>
						</div>
					</div>
				</div>

				<div class="mx-1 mb-1">
					<DropdownMenu.Sub>
						<DropdownMenu.SubTrigger
							class="mb-1 w-full px-2.5 py-1.5 rounded-xl bg-gray-50 dark:text-white dark:bg-gray-900/50 text-black transition text-xs flex items-center gap-2"
						>
							{#if getPresenceState() === 'dnd'}
								<span
									class="inline-flex size-3 rounded-full bg-red-500 items-center justify-center shrink-0"
								>
									<span class="h-[1.5px] w-1.5 rounded-full bg-white"></span>
								</span>
							{:else if getPresenceState() === 'offline'}
								<span class="inline-flex size-3 rounded-full border-2 border-gray-500 shrink-0"
								></span>
							{:else}
								<span
									class="inline-flex size-3 rounded-full {getPresenceOption().colorClass} shrink-0"
								></span>
							{/if}

							<div class="self-center flex-1 text-left">{getPresenceOption().label}</div>
							<ChevronRight className="size-3.5 opacity-60 shrink-0" strokeWidth="2" />
						</DropdownMenu.SubTrigger>

						<DropdownMenu.SubContent
							class="select-none w-72 rounded-2xl p-1 z-50 bg-white dark:bg-gray-850 dark:text-white border border-gray-100 dark:border-gray-800 shadow-lg"
							transition={flyAndScale}
							sideOffset={8}
						>
							{#each presenceOptions as option}
								<DropdownMenu.Item
									class="w-full rounded-xl px-2.5 py-2 text-left cursor-pointer select-none hover:bg-gray-50 dark:hover:bg-gray-800 transition"
									on:click={() => {
										updatePresenceState(option.id);
									}}
								>
									<div class="flex items-start gap-2.5">
										<div class="pt-0.5 shrink-0">
											{#if option.id === 'dnd'}
												<span
													class="inline-flex size-3 rounded-full bg-red-500 items-center justify-center"
												>
													<span class="h-[1.5px] w-1.5 rounded-full bg-white"></span>
												</span>
											{:else if option.id === 'offline'}
												<span class="inline-flex size-3 rounded-full border-2 border-gray-500"
												></span>
											{:else}
												<span class="inline-flex size-3 rounded-full {option.colorClass}"></span>
											{/if}
										</div>

										<div class="flex-1 min-w-0">
											<div class="text-sm leading-tight text-gray-900 dark:text-gray-100">
												{option.label}
											</div>
											{#if option.description}
												<div class="mt-0.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
													{option.description}
												</div>
											{/if}
										</div>
									</div>
								</DropdownMenu.Item>
							{/each}
						</DropdownMenu.SubContent>
					</DropdownMenu.Sub>
				</div>

				{#if $user?.status_emoji || $user?.status_message}
					<div class="mx-1">
						<button
							class="mb-1 w-full gap-2 px-2.5 py-1.5 rounded-xl bg-gray-50 dark:text-white dark:bg-gray-900/50 text-black transition text-xs flex items-center"
							type="button"
							on:click={() => {
								show = false;
								showUserStatusModal = true;
							}}
						>
							{#if $user?.status_emoji}
								<div class=" self-center shrink-0">
									<Emoji className="size-4" shortCode={$user?.status_emoji} />
								</div>
							{/if}

							<Tooltip
								content={$user?.status_message}
								className=" self-center line-clamp-2 flex-1 text-left"
							>
								{$user?.status_message}
							</Tooltip>

							<div class="self-start">
								<Tooltip content={$i18n.t('Clear status')}>
									<button
										type="button"
										on:click={async (e) => {
											e.preventDefault();
											e.stopPropagation();
											e.stopImmediatePropagation();

											const res = await updateUserStatus(localStorage.token, {
												status_emoji: '',
												status_message: ''
											});

											if (res) {
												toast.success($i18n.t('Status cleared successfully'));
												user.set(await getSessionUser(localStorage.token));
											} else {
												toast.error($i18n.t('Failed to clear status'));
											}
										}}
									>
										<XMark className="size-4 opacity-50" strokeWidth="2" />
									</button>
								</Tooltip>
							</div>
						</button>
					</div>
				{:else}
					<div class="mx-1">
						<button
							class="mb-1 w-full px-3 py-1.5 gap-1 rounded-xl bg-gray-50 dark:text-white dark:bg-gray-900/50 text-black transition text-xs flex items-center justify-center"
							type="button"
							on:click={() => {
								show = false;
								showUserStatusModal = true;
							}}
						>
							<div class=" self-center">
								<FaceSmile className="size-4" strokeWidth="1.5" />
							</div>
							<div class=" self-center truncate">{$i18n.t('Update your status')}</div>
						</button>
					</div>
				{/if}

				<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1.5 p-0" />
			{/if}

			<button
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
				type="button"
				on:click={async () => {
					show = false;

					await showSettings.set(true);

					if ($mobile) {
						await tick();
						showSidebar.set(false);
					}
				}}
			>
				<div class=" self-center mr-3">
					<Settings className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Settings')}</div>
			</button>

			<button
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
				type="button"
				on:click={async () => {
					show = false;

					dispatch('show', 'archived-chat');

					if ($mobile) {
						await tick();

						showSidebar.set(false);
					}
				}}
			>
				<div class=" self-center mr-3">
					<ArchiveBox className="size-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Archived Chats')}</div>
			</button>

			{#if role === 'admin'}
				<a
					href="/playground"
					draggable="false"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					on:click={async (e) => {
						if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
							return;
						}

						e.preventDefault();
						show = false;
						await goto('/playground');

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<Code className="size-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Playground')}</div>
				</a>
				<a
					href="/admin"
					draggable="false"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					on:click={async (e) => {
						if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) {
							return;
						}

						e.preventDefault();
						show = false;
						await goto('/admin');

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<UserGroup className="w-5 h-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Admin Panel')}</div>
				</a>
			{/if}

			{#if help}
				<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1 p-0" />

				<!-- {$i18n.t('Help')} -->

				<a
					href="/model-health"
					draggable="false"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					on:click={() => {
						show = false;
					}}
				>
					<div class=" self-center mr-3">
						<ChartBar className="size-5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Model Health')}</div>
				</a>

				{#if $user?.role === 'admin'}
					<a
						href="https://docs.openwebui.com"
						target="_blank"
						draggable="false"
						class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
						id="chat-share-button"
						on:click={() => {
							show = false;
						}}
					>
						<div class=" self-center mr-3">
							<QuestionMarkCircle className="size-5" />
						</div>
						<div class=" self-center truncate">{$i18n.t('Documentation')}</div>
					</a>

					<!-- Releases -->
					<a
						href={WEBUI_RELEASES_URL}
						target="_blank"
						draggable="false"
						class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
						id="chat-share-button"
						on:click={() => {
							show = false;
						}}
					>
						<div class=" self-center mr-3">
							<Map className="size-5" />
						</div>
						<div class=" self-center truncate">{$i18n.t('Releases')}</div>
					</a>
				{/if}

				<button
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
					type="button"
					id="chat-share-button"
					on:click={async () => {
						show = false;
						showShortcuts.set(!$showShortcuts);

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<Keyboard className="size-5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Keyboard shortcuts')}</div>
				</button>
			{/if}

			<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1 p-0" />

			<button
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer select-none"
				type="button"
				on:click={async () => {
					const res = await userSignOut();
					user.set(null);
					localStorage.removeItem('token');

					location.href = res?.redirect_url ?? '/auth';
					show = false;
				}}
			>
				<div class=" self-center mr-3">
					<SignOut className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Sign Out')}</div>
			</button>

			{#if showActiveUsers && ($config?.features?.enable_public_active_users_count || role === 'admin') && usage}
				{#if usage?.user_count}
					<hr class=" border-gray-50/30 dark:border-gray-800/30 my-1 p-0" />

					<Tooltip
						content={usage?.model_ids && usage?.model_ids.length > 0
							? `${$i18n.t('Running')}: ${usage.model_ids.join(', ')} ✨`
							: ''}
					>
						<div
							class="flex rounded-xl py-1 px-3 text-xs gap-2.5 items-center"
							on:mouseenter={() => {
								if ($config?.features?.enable_public_active_users_count || role === 'admin') {
									getUsageInfo();
								}
							}}
						>
							<div class=" flex items-center">
								<span class="relative flex size-2">
									<span class="relative inline-flex rounded-full size-2 bg-green-500"></span>
								</span>
							</div>

							<div class=" ">
								<span class="">
									{$i18n.t('Active Users')}:
								</span>
								<span class=" font-semibold">
									{usage?.user_count}
								</span>
							</div>
						</div>
					</Tooltip>
				{/if}
			{/if}

			<!-- <DropdownMenu.Item class="flex items-center py-1.5 px-3 text-sm ">
				<div class="flex items-center">Profile</div>
			</DropdownMenu.Item> -->
		</DropdownMenu.Content>
	</slot>
</DropdownMenu.Root>
