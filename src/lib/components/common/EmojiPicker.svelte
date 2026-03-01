<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext, onMount } from 'svelte';

	import { config } from '$lib/stores';
	import { flyAndScale } from '$lib/utils/transitions';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Star from '$lib/components/icons/Star.svelte';

	const i18n = getContext('i18n');

	export let onClose = () => {};
	export let onSubmit = (name) => {};
	export let side = 'top';
	export let align = 'start';
	export let showGifTab = true;

	type PickerEmoji = {
		id: string;
		type: 'unicode' | 'custom';
		shortCode: string;
		aliases: string[];
		codepoint?: string;
		dataUrl?: string;
	};

	type EmojiDatasetGroup = {
		id: string;
		labelKey: string;
		icon: PickerEmoji | null;
		items: PickerEmoji[];
	};

	type EmojiDataset = {
		groups: EmojiDatasetGroup[];
		standardEmojis: PickerEmoji[];
		standardEmojiByShortCode: Record<string, PickerEmoji>;
	};

	type EmojiSection = {
		id: string;
		labelKey: string;
		icon: PickerEmoji | null;
		showInNav: boolean;
		rows: PickerEmoji[][];
	};

	type EmojiShortCodesMap = Record<string, string | string[]>;
	type EmojiGroupsMap = Record<string, string[]>;

	type EmojiDatasetCacheState = {
		dataset: EmojiDataset | null;
		promise: Promise<EmojiDataset> | null;
	};

	const getEmojiDatasetCacheState = (): EmojiDatasetCacheState => {
		const root = globalThis as typeof globalThis & {
			__awuEmojiDatasetCacheState?: EmojiDatasetCacheState;
		};

		if (!root.__awuEmojiDatasetCacheState) {
			root.__awuEmojiDatasetCacheState = {
				dataset: null,
				promise: null
			};
		}

		return root.__awuEmojiDatasetCacheState;
	};

	const slugify = (value: string) =>
		value
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '');

	const normalizeShortCode = (value: unknown) =>
		String(value ?? '')
			.trim()
			.replace(/^:+|:+$/g, '')
			.toLowerCase();

	const uniqueByShortCode = (items: PickerEmoji[]) => {
		const seen = new Set<string>();
		const unique: PickerEmoji[] = [];

		for (const item of items) {
			if (!item || seen.has(item.shortCode)) {
				continue;
			}
			seen.add(item.shortCode);
			unique.push(item);
		}

		return unique;
	};

	const chunk = <T,>(items: T[], size: number): T[][] => {
		const chunks: T[][] = [];
		for (let i = 0; i < items.length; i += size) {
			chunks.push(items.slice(i, i + size));
		}
		return chunks;
	};

	const sortByShortCode = (a: PickerEmoji, b: PickerEmoji) =>
		a.shortCode.localeCompare(b.shortCode);

	const buildEmojiDataset = async (): Promise<EmojiDataset> => {
		const [{ default: emojiGroups }, { default: emojiShortCodes }] = await Promise.all([
			import('$lib/emoji-groups.json'),
			import('$lib/emoji-shortcodes.json')
		]);

		const groupsData = emojiGroups as EmojiGroupsMap;
		const shortCodesData = emojiShortCodes as EmojiShortCodesMap;

		const standardEmojiByCodepoint: Record<string, PickerEmoji> = {};
		const standardEmojiByShortCode: Record<string, PickerEmoji> = {};
		const standardEmojis: PickerEmoji[] = [];

		for (const [codepoint, rawAliases] of Object.entries(shortCodesData)) {
			const aliases = (Array.isArray(rawAliases) ? rawAliases : [rawAliases])
				.map((alias) => String(alias ?? '').trim().toLowerCase())
				.filter((alias) => alias.length > 0);

			if (aliases.length === 0) {
				continue;
			}

			const emoji: PickerEmoji = {
				id: `std:${codepoint}`,
				type: 'unicode',
				shortCode: aliases[0],
				aliases,
				codepoint
			};

			standardEmojiByCodepoint[codepoint] = emoji;
			standardEmojis.push(emoji);

			for (const alias of aliases) {
				if (!standardEmojiByShortCode[alias]) {
					standardEmojiByShortCode[alias] = emoji;
				}
			}
		}

		const groups: EmojiDatasetGroup[] = [];
		const groupedShortCodes = new Set<string>();
		let groupIndex = 0;

		for (const [groupLabel, groupCodepoints] of Object.entries(groupsData)) {
			const groupItems = uniqueByShortCode(
				groupCodepoints
					.map((codepoint) => standardEmojiByCodepoint[String(codepoint)])
					.filter((emoji): emoji is PickerEmoji => Boolean(emoji))
			);

			if (groupItems.length === 0) {
				continue;
			}

			for (const emoji of groupItems) {
				groupedShortCodes.add(emoji.shortCode);
			}

			groups.push({
				id: `group-${slugify(groupLabel) || 'emoji'}-${groupIndex}`,
				labelKey: groupLabel,
				icon: groupItems[0] ?? null,
				items: groupItems
			});

			groupIndex += 1;
		}

		const remainingStandard = standardEmojis.filter(
			(emoji) => !groupedShortCodes.has(emoji.shortCode)
		);
		if (remainingStandard.length > 0) {
			groups.push({
				id: 'group-default',
				labelKey: 'Default',
				icon: remainingStandard[0] ?? null,
				items: uniqueByShortCode(remainingStandard).sort(sortByShortCode)
			});
		}

		return {
			groups,
			standardEmojis,
			standardEmojiByShortCode
		};
	};

	const loadEmojiDataset = async (): Promise<EmojiDataset> => {
		const cache = getEmojiDatasetCacheState();

		if (cache.dataset) {
			return cache.dataset;
		}

		if (!cache.promise) {
			cache.promise = buildEmojiDataset()
				.then((dataset) => {
					cache.dataset = dataset;
					return dataset;
				})
				.finally(() => {
					cache.promise = null;
				});
		}

		return await cache.promise;
	};

	const normalizeCustomEmoji = (raw: unknown): PickerEmoji | null => {
		if (!raw || typeof raw !== 'object') {
			return null;
		}

		const item = raw as { id?: string; name?: string; data_url?: string };
		const id = String(item.id ?? '').trim();
		const shortCode = normalizeShortCode(item.name ?? '');
		const dataUrl = String(item.data_url ?? '').trim();

		if (!id || shortCode.length < 2 || !dataUrl.startsWith('data:image/')) {
			return null;
		}

		return {
			id: `custom:${id}`,
			type: 'custom',
			shortCode,
			aliases: [shortCode],
			dataUrl
		};
	};

	const FAVORITES_KEY = 'awu.emoji-picker.favorites.v1';
	const RECENT_KEY = 'awu.emoji-picker.recent.v1';
	const MAX_RECENT = 40;
	const ROW_SIZE = 8;

	const readLocalList = (key: string): string[] => {
		if (typeof localStorage === 'undefined') {
			return [];
		}
		try {
			const parsed = JSON.parse(localStorage.getItem(key) ?? '[]');
			if (!Array.isArray(parsed)) {
				return [];
			}
			return parsed
				.map((item) => normalizeShortCode(item))
				.filter((item) => item.length > 0);
		} catch {
			return [];
		}
	};

	const writeLocalList = (key: string, value: string[]) => {
		if (typeof localStorage === 'undefined') {
			return;
		}
		localStorage.setItem(key, JSON.stringify(value));
	};

	const emojiMatchesSearch = (emoji: PickerEmoji, query: string) => {
		if (!query) {
			return true;
		}

		return (
			emoji.shortCode.includes(query) || emoji.aliases.some((alias) => alias.includes(query))
		);
	};

	const buildSection = ({
		id,
		labelKey,
		icon,
		items,
		showInNav
	}: {
		id: string;
		labelKey: string;
		icon: PickerEmoji | null;
		items: PickerEmoji[];
		showInNav: boolean;
	}): EmojiSection | null => {
		const normalizedItems = uniqueByShortCode(items);
		if (normalizedItems.length === 0) {
			return null;
		}

		return {
			id,
			labelKey,
			icon,
			showInNav,
			rows: chunk(normalizedItems, ROW_SIZE)
		};
	};

	let show = false;
	let activeTab: 'emoji' | 'gif' = 'emoji';
	let search = '';
	let favoriteShortCodes: string[] = [];
	let recentShortCodes: string[] = [];
	let customEmojis: PickerEmoji[] = [];

	let emojiDataset: EmojiDataset | null = getEmojiDatasetCacheState().dataset;
	let emojiSections: EmojiSection[] = [];
	let navSections: EmojiSection[] = [];
	let loadingEmojiData = false;

	let activeSectionId = '';
	let sectionContainerElement: HTMLDivElement | null = null;
	const sectionElements: Record<string, HTMLDivElement> = {};

	const resolveEmojiByShortCode = (shortCode: string): PickerEmoji | null => {
		const normalized = normalizeShortCode(shortCode);
		const custom = customEmojis.find((emoji) => emoji.shortCode === normalized);
		if (custom) {
			return custom;
		}

		if (!emojiDataset) {
			return null;
		}

		return emojiDataset.standardEmojiByShortCode[normalized] ?? null;
	};

	const addRecentEmoji = (shortCode: string) => {
		const normalized = normalizeShortCode(shortCode);
		if (!normalized) {
			return;
		}

		recentShortCodes = [normalized, ...recentShortCodes.filter((item) => item !== normalized)].slice(
			0,
			MAX_RECENT
		);
		writeLocalList(RECENT_KEY, recentShortCodes);
	};

	const isFavorite = (shortCode: string) =>
		favoriteShortCodes.includes(normalizeShortCode(shortCode));

	const toggleFavorite = (shortCode: string) => {
		const normalized = normalizeShortCode(shortCode);
		if (!normalized) {
			return;
		}

		if (favoriteShortCodes.includes(normalized)) {
			favoriteShortCodes = favoriteShortCodes.filter((item) => item !== normalized);
		} else {
			favoriteShortCodes = [normalized, ...favoriteShortCodes.filter((item) => item !== normalized)];
		}

		writeLocalList(FAVORITES_KEY, favoriteShortCodes);
	};

	const selectEmoji = (emoji: PickerEmoji) => {
		onSubmit(emoji.shortCode);
		addRecentEmoji(emoji.shortCode);
		show = false;
	};

	const ensureEmojiDataset = async () => {
		if (emojiDataset) {
			return;
		}

		loadingEmojiData = true;
		try {
			emojiDataset = await loadEmojiDataset();
		} finally {
			loadingEmojiData = false;
		}
	};

	const registerSection = (node: HTMLDivElement, sectionId: string) => {
		sectionElements[sectionId] = node;

		return {
			destroy() {
				delete sectionElements[sectionId];
			}
		};
	};

	const updateActiveSection = () => {
		if (!sectionContainerElement || navSections.length === 0) {
			return;
		}

		const scrollTop = sectionContainerElement.scrollTop;
		let closestId = navSections[0]?.id ?? '';
		let closestDistance = Number.POSITIVE_INFINITY;

		for (const section of navSections) {
			const node = sectionElements[section.id];
			if (!node) {
				continue;
			}

			const distance = Math.abs(node.offsetTop - scrollTop);
			if (distance < closestDistance) {
				closestDistance = distance;
				closestId = section.id;
			}
		}

		if (closestId) {
			activeSectionId = closestId;
		}
	};

	const jumpToSection = (sectionId: string) => {
		const container = sectionContainerElement;
		const sectionNode = sectionElements[sectionId];

		if (!container || !sectionNode) {
			return;
		}

		container.scrollTo({ top: Math.max(sectionNode.offsetTop - 6, 0), behavior: 'auto' });
		activeSectionId = sectionId;
	};

	onMount(() => {
		favoriteShortCodes = readLocalList(FAVORITES_KEY);
		recentShortCodes = readLocalList(RECENT_KEY);
	});

	$: if (!showGifTab && activeTab === 'gif') {
		activeTab = 'emoji';
	}

	$: customEmojis = Array.isArray($config?.ui?.custom_emojis)
		? $config.ui.custom_emojis
				.map((item) => normalizeCustomEmoji(item))
				.filter((item): item is PickerEmoji => item !== null)
		: [];

	$: {
		const normalizedSearch = normalizeShortCode(search);
		const sections: EmojiSection[] = [];

		if (!emojiDataset || (showGifTab && activeTab === 'gif')) {
			emojiSections = [];
		} else if (normalizedSearch) {
			const customResults = customEmojis.filter((emoji) =>
				emojiMatchesSearch(emoji, normalizedSearch)
			);
			const standardResults = emojiDataset.standardEmojis.filter((emoji) =>
				emojiMatchesSearch(emoji, normalizedSearch)
			);

			const customSection = buildSection({
				id: 'search-custom',
				labelKey: 'Custom',
				icon: customResults[0] ?? null,
				items: customResults.sort(sortByShortCode),
				showInNav: false
			});
			if (customSection) {
				sections.push(customSection);
			}

			const resultsSection = buildSection({
				id: 'search-results',
				labelKey: 'Results',
				icon: standardResults[0] ?? null,
				items: standardResults.sort(sortByShortCode),
				showInNav: false
			});
			if (resultsSection) {
				sections.push(resultsSection);
			}

			emojiSections = sections;
		} else {
			const favorites = uniqueByShortCode(
				favoriteShortCodes
					.map((shortCode) => resolveEmojiByShortCode(shortCode))
					.filter((item): item is PickerEmoji => item !== null)
			);

			const recents = uniqueByShortCode(
				recentShortCodes
					.map((shortCode) => resolveEmojiByShortCode(shortCode))
					.filter((item): item is PickerEmoji => item !== null)
			).filter((item) => !favorites.some((favorite) => favorite.shortCode === item.shortCode));

			const customSection = buildSection({
				id: 'custom',
				labelKey: 'Custom',
				icon: customEmojis[0] ?? null,
				items: [...customEmojis].sort(sortByShortCode),
				showInNav: false
			});
			if (customSection) {
				sections.push(customSection);
			}

			const favoritesSection = buildSection({
				id: 'favorites',
				labelKey: 'Favorites',
				icon: favorites[0] ?? null,
				items: favorites,
				showInNav: false
			});
			if (favoritesSection) {
				sections.push(favoritesSection);
			}

			const recentsSection = buildSection({
				id: 'frequently-used',
				labelKey: 'Frequently Used',
				icon: recents[0] ?? null,
				items: recents,
				showInNav: false
			});
			if (recentsSection) {
				sections.push(recentsSection);
			}

			for (const group of emojiDataset.groups) {
				const groupSection = buildSection({
					id: group.id,
					labelKey: group.labelKey,
					icon: group.icon,
					items: group.items,
					showInNav: true
				});

				if (groupSection) {
					sections.push(groupSection);
				}
			}

			emojiSections = sections;
		}
	}

	$: navSections = emojiSections.filter((section) => section.showInNav);

	$: if (navSections.length > 0 && !navSections.some((section) => section.id === activeSectionId)) {
		activeSectionId = navSections[0].id;
	}
</script>

<DropdownMenu.Root
	bind:open={show}
	closeFocus={false}
	onOpenChange={(state) => {
		if (state) {
			void ensureEmojiDataset();
			return;
		}

		search = '';
		activeTab = 'emoji';
		onClose();
	}}
	typeahead={false}
>
	<DropdownMenu.Trigger>
		<slot />
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		class="max-w-full w-[22rem] border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-850 rounded-3xl z-9999 shadow-lg dark:text-white"
		sideOffset={8}
		{side}
		{align}
		transition={flyAndScale}
	>
		<div class="px-3 pt-2.5 pb-2 border-b border-gray-100/70 dark:border-gray-800/70 space-y-2">
			{#if showGifTab}
				<div class="inline-flex rounded-xl bg-gray-100/70 dark:bg-gray-900/70 p-1 gap-1">
					<button
						type="button"
						class="px-2.5 py-1 text-xs font-medium rounded-lg transition {activeTab === 'gif'
							? 'bg-white dark:bg-gray-800 shadow-sm'
							: 'text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white'}"
						on:click={() => {
							activeTab = 'gif';
							search = '';
						}}
					>
						GIF
					</button>
					<button
						type="button"
						class="px-2.5 py-1 text-xs font-medium rounded-lg transition {activeTab === 'emoji'
							? 'bg-white dark:bg-gray-800 shadow-sm'
							: 'text-gray-500 dark:text-gray-400 hover:text-black dark:hover:text-white'}"
						on:click={() => {
							activeTab = 'emoji';
						}}
					>
						{$i18n.t('Emoji')}
					</button>
				</div>
			{/if}

			{#if !showGifTab || activeTab === 'emoji'}
				<div class="flex items-center gap-2">
					<input
						type="text"
						class="w-full text-sm bg-transparent outline-hidden border border-gray-200/80 dark:border-gray-800/80 rounded-xl px-3 py-1.5"
						placeholder={$i18n.t('Search emojis')}
						bind:value={search}
						on:focus={() => {
							void ensureEmojiDataset();
						}}
					/>
				</div>
			{:else}
				<input
					type="text"
					class="w-full text-sm bg-transparent outline-hidden border border-gray-200/80 dark:border-gray-800/80 rounded-xl px-3 py-1.5 opacity-70"
					placeholder={$i18n.t('GIF search coming soon')}
					disabled
				/>
			{/if}
		</div>

		{#if showGifTab && activeTab === 'gif'}
			<div class="h-96 px-4 py-6 text-center text-xs text-gray-500 dark:text-gray-400">
				<div class="text-sm font-medium mb-1">{$i18n.t('GIF')}</div>
				<div>{$i18n.t('GIF support is coming soon.')}</div>
			</div>
		{:else if loadingEmojiData && !emojiDataset}
			<div class="h-96 px-4 py-6 text-center text-xs text-gray-500 dark:text-gray-400">
				<div>{$i18n.t('Loading emojis...')}</div>
			</div>
		{:else}
			<div class="h-96 flex">
				{#if navSections.length > 0 && normalizeShortCode(search) === ''}
					<div
						class="w-12 shrink-0 border-r border-gray-100/70 dark:border-gray-800/70 px-1 py-2 overflow-y-auto space-y-1"
					>
						{#each navSections as section}
							<Tooltip content={$i18n.t(section.labelKey)} placement="right">
								<button
									type="button"
									class="w-full h-9 rounded-lg flex items-center justify-center transition {activeSectionId === section.id
										? 'bg-gray-200/80 dark:bg-gray-700/70'
										: 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
									on:click={() => jumpToSection(section.id)}
									aria-label={$i18n.t(section.labelKey)}
								>
									{#if section.icon}
										{#if section.icon.type === 'custom' && section.icon.dataUrl}
											<img
												src={section.icon.dataUrl}
												alt={section.icon.shortCode}
												class="size-5 object-contain"
												loading="lazy"
											/>
										{:else}
											<img
												src="{WEBUI_BASE_URL}/assets/emojis/{section.icon.codepoint?.toLowerCase()}.svg"
												alt={section.icon.shortCode}
												class="size-5"
												loading="lazy"
											/>
										{/if}
									{:else}
										<Star className="size-4 text-gray-500 dark:text-gray-400" strokeWidth="2" />
									{/if}
								</button>
							</Tooltip>
						{/each}
					</div>
				{/if}

				<div
					class="flex-1 overflow-y-auto px-2 pb-2 pt-1 text-sm"
					bind:this={sectionContainerElement}
					on:scroll={updateActiveSection}
				>
					{#if emojiSections.length === 0}
						<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-6">
							{$i18n.t('No results')}
						</div>
					{:else}
						<div class="w-full">
							{#each emojiSections as section}
								<div use:registerSection={section.id}>
									<div class="text-xs font-medium py-1.5 px-1 text-gray-500 dark:text-gray-400">
										{$i18n.t(section.labelKey)}
									</div>

									{#each section.rows as rowItems}
										<div class="flex items-center gap-1.5 w-full pb-1">
											{#each rowItems as emojiItem}
												<div class="relative group/emoji">
													<Tooltip content={`:${emojiItem.shortCode}:`} placement="top">
														<button
															type="button"
															class="p-1.5 rounded-lg cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition"
															on:click={() => selectEmoji(emojiItem)}
														>
															{#if emojiItem.type === 'custom' && emojiItem.dataUrl}
																<img
																	src={emojiItem.dataUrl}
																	alt={emojiItem.shortCode}
																	class="size-5 object-contain"
																	loading="lazy"
																/>
															{:else}
																<img
																	src="{WEBUI_BASE_URL}/assets/emojis/{emojiItem.codepoint?.toLowerCase()}.svg"
																	alt={emojiItem.shortCode}
																	class="size-5"
																	loading="lazy"
																/>
															{/if}
														</button>
													</Tooltip>

													<button
														type="button"
														class="absolute -top-0.5 -right-0.5 rounded-full bg-white dark:bg-gray-900 p-0.5 border border-gray-200/80 dark:border-gray-700/80 opacity-0 group-hover/emoji:opacity-100 transition"
														on:click|stopPropagation={() => toggleFavorite(emojiItem.shortCode)}
														aria-label={$i18n.t('Toggle favorite')}
													>
														<Star
															className={`size-2.5 ${isFavorite(emojiItem.shortCode) ? 'fill-yellow-400 text-yellow-500' : 'text-gray-400'}`}
															strokeWidth="2"
														/>
													</button>
												</div>
											{/each}
										</div>
									{/each}
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</DropdownMenu.Content>
</DropdownMenu.Root>
