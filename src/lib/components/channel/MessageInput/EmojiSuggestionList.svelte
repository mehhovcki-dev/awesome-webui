<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { config, shortCodesToEmojis } from '$lib/stores';
	import Emoji from '$lib/components/common/Emoji.svelte';

	export let query = '';
	export let command: (item: { id: string; label?: string }) => void = () => {};
	export let insertTextHandler: (text: string) => void = () => {};
	export let selectedIndex = 0;

	type EmojiItem = {
		type: 'standard' | 'custom';
		shortCode: string;
	};

	const DEFAULT_SHORTCODES = [
		'grinning',
		'smiley',
		'smile',
		'joy',
		'laughing',
		'blush',
		'slightly_smiling_face',
		'upside_down_face',
		'wink',
		'heart_eyes',
		'kissing_heart',
		'sunglasses',
		'thinking_face',
		'neutral_face',
		'grimacing',
		'cry',
		'sob',
		'angry',
		'thumbsup',
		'thumbsdown',
		'clap',
		'pray',
		'wave',
		'ok_hand',
		'fire',
		'sparkles',
		'100',
		'heart',
		'broken_heart',
		'rocket'
	];

	const normalizeShortCode = (value: unknown) =>
		String(value ?? '')
			.trim()
			.replace(/^:+|:+$/g, '')
			.toLowerCase();

	const getCustomEmojiItems = (): EmojiItem[] => {
		const customEmojis = Array.isArray($config?.ui?.custom_emojis) ? $config.ui.custom_emojis : [];

		return customEmojis
			.map((item) => normalizeShortCode(item?.name))
			.filter((shortCode) => shortCode.length > 1)
			.map((shortCode) => ({
				type: 'custom' as const,
				shortCode
			}));
	};

	const getStandardEmojiItems = (): EmojiItem[] =>
		Object.keys($shortCodesToEmojis ?? {})
			.map((shortCode) => normalizeShortCode(shortCode))
			.filter((shortCode) => shortCode.length > 0)
			.map((shortCode) => ({
				type: 'standard' as const,
				shortCode
			}));

	const dedupeByShortCode = (items: EmojiItem[]) => {
		const seen = new Set<string>();
		const unique: EmojiItem[] = [];

		for (const item of items) {
			if (!item || seen.has(item.shortCode)) {
				continue;
			}
			seen.add(item.shortCode);
			unique.push(item);
		}

		return unique;
	};

	const sortByRelevance = (items: EmojiItem[], rawQuery: string) => {
		const normalizedQuery = normalizeShortCode(rawQuery);
		if (!normalizedQuery) {
			const preferred = DEFAULT_SHORTCODES.map((code) =>
				items.find((item) => item.shortCode === code)
			).filter((item): item is EmojiItem => Boolean(item));

			const remaining = items
				.filter((item) => !DEFAULT_SHORTCODES.includes(item.shortCode))
				.sort((a, b) => a.shortCode.localeCompare(b.shortCode));

			return [...preferred, ...remaining];
		}

		return [...items].sort((a, b) => {
			const aStarts = a.shortCode.startsWith(normalizedQuery) ? 0 : 1;
			const bStarts = b.shortCode.startsWith(normalizedQuery) ? 0 : 1;
			if (aStarts !== bStarts) {
				return aStarts - bStarts;
			}

			return a.shortCode.localeCompare(b.shortCode);
		});
	};

	let filteredItems: EmojiItem[] = [];

	$: {
		const normalizedQuery = normalizeShortCode(query);
		const allItems = dedupeByShortCode([...getCustomEmojiItems(), ...getStandardEmojiItems()]);

		filteredItems = sortByRelevance(
			allItems.filter((item) =>
				normalizedQuery ? item.shortCode.includes(normalizedQuery) : true
			),
			normalizedQuery
		).slice(0, 60);
	}

	$: if (query) {
		selectedIndex = 0;
	}

	const select = (index: number) => {
		const item = filteredItems[index];
		if (!item) {
			return;
		}

		if (command) {
			command({
				id: item.shortCode,
				label: item.shortCode
			});
		} else {
			insertTextHandler(`:${item.shortCode}: `);
		}
		document.getElementById('chat-input')?.focus();
	};

	const onKeyDown = (event: KeyboardEvent) => {
		if (!['ArrowUp', 'ArrowDown', 'Enter', 'Tab', 'Escape'].includes(event.key)) {
			return false;
		}

		if (event.key === 'ArrowUp') {
			selectedIndex = Math.max(0, selectedIndex - 1);
			const item = document.querySelector(`[data-selected="true"]`);
			item?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
			return true;
		}

		if (event.key === 'ArrowDown') {
			selectedIndex = Math.min(selectedIndex + 1, filteredItems.length - 1);
			const item = document.querySelector(`[data-selected="true"]`);
			item?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
			return true;
		}

		if (event.key === 'Enter' || event.key === 'Tab') {
			select(selectedIndex);
			if (event.key === 'Enter') {
				event.preventDefault();
			}
			return true;
		}

		if (event.key === 'Escape') {
			return true;
		}

		return false;
	};

	// Called by getSuggestionRenderer()
	// @ts-ignore
	export function _onKeyDown(event: KeyboardEvent) {
		return onKeyDown(event);
	}
</script>

<div
	class="mention-list text-black dark:text-white rounded-2xl shadow-lg border border-gray-200 dark:border-gray-800 flex flex-col bg-white dark:bg-gray-850 w-72 p-1"
	id="suggestions-container"
>
	<div class="px-2 text-xs text-gray-500 py-1">
		{$i18n.t('Emojis')}
	</div>

	<div class="overflow-y-auto scrollbar-thin max-h-60">
		{#if filteredItems.length === 0}
			<div class="px-2.5 py-2 text-xs text-gray-500 dark:text-gray-400">
				{$i18n.t('No results')}
			</div>
		{:else}
			{#each filteredItems as item, i}
				<button
					type="button"
					on:click={() => select(i)}
					on:mousemove={() => {
						selectedIndex = i;
					}}
					class="flex items-center justify-between px-2.5 py-1.5 rounded-xl w-full text-left {i ===
					selectedIndex
						? 'bg-gray-50 dark:bg-gray-800 selected-command-option-button'
						: ''}"
					data-selected={i === selectedIndex}
				>
					<div class="flex items-center gap-2 min-w-0">
						<Emoji shortCode={item.shortCode} className="size-5" />
						<div class="truncate">:{item.shortCode}:</div>
					</div>

					<div class="shrink-0 text-xs text-gray-500">
						{item.type === 'custom' ? $i18n.t('Custom') : $i18n.t('Emoji')}
					</div>
				</button>
			{/each}
		{/if}
	</div>
</div>
