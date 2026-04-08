<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext, onDestroy, onMount, tick } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { config } from '$lib/stores';
	import { flyAndScale } from '$lib/utils/transitions';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Star from '$lib/components/icons/Star.svelte';

	const i18n = getContext('i18n');

	export let onClose = () => {};
	export let onSubmit = (name) => {};
	export let onGifSubmit: ((gif: GifItem) => void | Promise<void>) | null = null;
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

	type GifFileAsset = {
		url?: string;
		width?: number;
		height?: number;
		size?: number;
	};

	type GifFileGroup = {
		gif?: GifFileAsset;
		webp?: GifFileAsset;
		jpg?: GifFileAsset;
		mp4?: GifFileAsset;
		webm?: GifFileAsset;
	};

	type GifFileMap = {
		hd?: GifFileGroup;
		md?: GifFileGroup;
		sm?: GifFileGroup;
		xs?: GifFileGroup;
	};

	type GifItem = {
		id: string;
		slug: string;
		title: string;
		file: GifFileMap;
		blurPreview?: string;
	};

	type GifCategory = {
		label: string;
		query: string;
		previewUrl: string;
	};

	type GifSection = {
		id: string;
		label: string;
		type: 'favorites' | 'trending' | 'category';
		query?: string;
		previewUrl?: string;
	};

	type GifListResponse = {
		items: GifItem[];
		currentPage: number;
		hasNext: boolean;
	};

	type GifSectionState = {
		items: GifItem[];
		page: number;
		hasNext: boolean;
		loading: boolean;
		loaded: boolean;
		error: string;
	};

	type GifCacheState = {
		listByUrl: Record<string, GifListResponse>;
		inFlightListByUrl: Record<string, Promise<GifListResponse>>;
		categoriesByUrl: Record<string, GifCategory[]>;
		itemsBySlug: Record<string, GifItem>;
		slugByAssetUrl: Record<string, string>;
	};

	type KlipyUiConfig = {
		app_key?: string;
		customer_id?: string;
		locale?: string;
		per_page?: number;
		content_filter?: string;
		format_filter?: string;
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

	const getGifCacheState = (): GifCacheState => {
		const root = globalThis as typeof globalThis & {
			__awuGifCacheState?: GifCacheState;
		};

		if (!root.__awuGifCacheState) {
			root.__awuGifCacheState = {
				listByUrl: {},
				inFlightListByUrl: {},
				categoriesByUrl: {},
				itemsBySlug: {},
				slugByAssetUrl: {}
			};
		}

		return root.__awuGifCacheState;
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
				.map((alias) =>
					String(alias ?? '')
						.trim()
						.toLowerCase()
				)
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

	const GIF_FAVORITES_KEY = 'awu.gif-picker.favorites.v1';
	const GIF_EMBED_FAVORITES_KEY = 'awu.gif-embed.favorites.v1';
	const GIF_CUSTOMER_ID_KEY = 'awu.gif-picker.customer-id.v1';
	const GIF_FAVORITES_EVENT = 'awu:gif-favorites-updated';
	const MAX_GIF_FAVORITES = 2048;
	const KLIPY_API_BASE_URL = 'https://api.klipy.com';
	const MAX_GIF_CATEGORY_SECTIONS = 16;
	const GIF_AUTO_LOAD_THRESHOLD_PX = 220;
	const GIF_AUTO_LOAD_COOLDOWN_MS = 450;

	const FALLBACK_GIF_QUERIES = [
		'smile',
		'laugh',
		'thumbs up',
		'yes',
		'no',
		'wow',
		'party',
		'dance',
		'cat',
		'dog',
		'hello',
		'good night'
	];

	const ROW_SIZE = 8;
	const gifCacheState = getGifCacheState();

	const toTitleCase = (value: string) =>
		String(value ?? '')
			.trim()
			.split(/\s+/)
			.filter((token) => token.length > 0)
			.map((token) => token.charAt(0).toUpperCase() + token.slice(1))
			.join(' ');

	const clampInteger = (value: unknown, fallback: number, min: number, max: number) => {
		const parsed = Number(value);
		if (!Number.isFinite(parsed)) {
			return fallback;
		}

		return Math.min(max, Math.max(min, Math.floor(parsed)));
	};

	const getErrorMessage = (error: unknown, fallback: string) =>
		error instanceof Error && error.message ? error.message : fallback;

	const readLocalStringList = (
		key: string,
		normalize: (value: unknown) => string = (value) => String(value ?? '').trim()
	): string[] => {
		if (typeof localStorage === 'undefined') {
			return [];
		}

		try {
			const parsed = JSON.parse(localStorage.getItem(key) ?? '[]');
			if (!Array.isArray(parsed)) {
				return [];
			}

			const values: string[] = [];
			const seen = new Set<string>();

			for (const item of parsed) {
				const normalized = normalize(item);
				if (!normalized || seen.has(normalized)) {
					continue;
				}

				seen.add(normalized);
				values.push(normalized);
			}

			return values;
		} catch {
			return [];
		}
	};

	const writeLocalStringList = (key: string, value: string[]) => {
		if (typeof localStorage === 'undefined') {
			return;
		}

		localStorage.setItem(key, JSON.stringify(value));
	};

	const readLocalList = (key: string): string[] => readLocalStringList(key, normalizeShortCode);
	const writeLocalList = (key: string, value: string[]) => writeLocalStringList(key, value);

	const normalizeGifSlug = (value: unknown) => String(value ?? '').trim();
	const normalizeGifFavoriteUrl = (value: unknown) => {
		const rawValue = String(value ?? '').trim();
		if (!rawValue) {
			return '';
		}

		const parseWithBase = (input: string, base?: string) => {
			try {
				const parsed = base ? new URL(input, base) : new URL(input);
				if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
					return parsed.toString();
				}
			} catch {
				// Ignore invalid URLs
			}

			return '';
		};

		return (
			parseWithBase(rawValue) ||
			(typeof window !== 'undefined' ? parseWithBase(rawValue, window.location.origin) : '')
		);
	};

	const parseHttpUrl = (value: string) => {
		const normalizedValue = normalizeGifFavoriteUrl(value);
		if (!normalizedValue) {
			return null;
		}

		try {
			return new URL(normalizedValue);
		} catch {
			return null;
		}
	};

	const dispatchGifFavoritesUpdated = () => {
		if (typeof window === 'undefined') {
			return;
		}

		window.dispatchEvent(new CustomEvent(GIF_FAVORITES_EVENT));
	};

	const getGifCustomerId = () => {
		if (typeof localStorage === 'undefined') {
			return `awu-guest-${Date.now().toString(36)}`;
		}

		const existing = String(localStorage.getItem(GIF_CUSTOMER_ID_KEY) ?? '').trim();
		if (existing) {
			return existing;
		}

		const generated =
			typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
				? crypto.randomUUID()
				: `awu-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;

		localStorage.setItem(GIF_CUSTOMER_ID_KEY, generated);
		return generated;
	};

	const resolveClientLocale = () => {
		if (typeof localStorage !== 'undefined') {
			const storedLocale = String(localStorage.getItem('locale') ?? '').trim();
			if (storedLocale) {
				return storedLocale;
			}
		}

		if (typeof navigator !== 'undefined' && navigator.language) {
			return navigator.language;
		}

		return 'en-US';
	};

	const parseLocale = (rawLocale: string) => {
		const normalized = String(rawLocale ?? '')
			.trim()
			.replace('_', '-');
		const [languagePart = 'en', countryPart = 'US'] = normalized.split('-');

		return {
			language: (languagePart || 'en').toLowerCase(),
			country: (countryPart || 'US').toUpperCase()
		};
	};

	const resolveCountryCode = (rawLocale: string) => parseLocale(rawLocale).country.toLowerCase();
	const resolveLanguageCountryLocale = (rawLocale: string) => {
		const locale = parseLocale(rawLocale);
		return `${locale.language}_${locale.country}`;
	};

	const resolveKlipyUiConfig = (): KlipyUiConfig => {
		const uiConfig = ($config?.ui ?? {}) as { klipy?: KlipyUiConfig };
		return uiConfig.klipy ?? {};
	};

	const resolveGifConfig = () => {
		const klipyConfig = resolveKlipyUiConfig();
		const locale = String(klipyConfig.locale ?? resolveClientLocale()).trim() || 'en-US';

		return {
			appKey:
				String(
					klipyConfig.app_key ??
						import.meta.env.VITE_KLIPY_APP_KEY ??
						import.meta.env.VITE_KLIPY_APPKEY ??
						''
				).trim() || '',
			customerId: String(klipyConfig.customer_id ?? getGifCustomerId()).trim(),
			locale: resolveCountryCode(locale),
			categoriesLocale: resolveLanguageCountryLocale(locale),
			perPage: clampInteger(klipyConfig.per_page, 24, 8, 50),
			contentFilter: String(klipyConfig.content_filter ?? 'medium').trim() || 'medium',
			formatFilter:
				String(klipyConfig.format_filter ?? 'gif,webp,jpg,mp4,webm').trim() ||
				'gif,webp,jpg,mp4,webm'
		};
	};

	const buildKlipyUrl = (
		path: string,
		params: Record<string, string | number | undefined | null>
	) => {
		const url = new URL(path, KLIPY_API_BASE_URL);

		for (const [key, value] of Object.entries(params)) {
			if (value === undefined || value === null) {
				continue;
			}

			const normalized = String(value).trim();
			if (!normalized) {
				continue;
			}

			url.searchParams.set(key, normalized);
		}

		return url.toString();
	};

	const normalizeGifItem = (raw: unknown): GifItem | null => {
		if (!raw || typeof raw !== 'object') {
			return null;
		}

		const item = raw as {
			id?: string | number;
			slug?: string;
			title?: string;
			file?: GifFileMap;
			blur_preview?: string;
		};

		const slug = normalizeGifSlug(item.slug ?? item.id ?? '');
		if (!slug) {
			return null;
		}

		return {
			id: String(item.id ?? slug),
			slug,
			title: String(item.title ?? slug),
			file: (item.file ?? {}) as GifFileMap,
			blurPreview: typeof item.blur_preview === 'string' ? item.blur_preview : undefined
		};
	};

	const normalizeGifItems = (rawItems: unknown[]): GifItem[] => {
		const items: GifItem[] = [];
		const seen = new Set<string>();

		for (const rawItem of rawItems) {
			const normalized = normalizeGifItem(rawItem);
			if (!normalized || seen.has(normalized.slug)) {
				continue;
			}

			seen.add(normalized.slug);
			items.push(normalized);
		}

		return items;
	};

	const rememberGifItems = (items: GifItem[]) => {
		if (items.length === 0) {
			return;
		}

		let changed = false;
		for (const item of items) {
			const slug = normalizeGifSlug(item.slug || item.id);
			if (!slug) {
				continue;
			}

			const fileGroups = [item.file?.hd, item.file?.md, item.file?.sm, item.file?.xs];
			for (const group of fileGroups) {
				const candidateUrls = [
					group?.gif?.url,
					group?.webp?.url,
					group?.jpg?.url,
					group?.mp4?.url,
					group?.webm?.url
				];

				for (const candidateUrl of candidateUrls) {
					const parsed = parseHttpUrl(String(candidateUrl ?? '').trim());
					if (!parsed) {
						continue;
					}

					gifCacheState.slugByAssetUrl[parsed.toString()] = slug;
				}
			}

			const existing = gifCacheState.itemsBySlug[slug];
			if (existing !== item) {
				gifCacheState.itemsBySlug[slug] = item;
				changed = true;
			}
		}

		if (changed) {
			gifItemsBySlug = { ...gifCacheState.itemsBySlug };
		}
	};

	const mergeGifItems = (baseItems: GifItem[], incomingItems: GifItem[]) => {
		const mergedBySlug: Record<string, GifItem> = {};

		for (const item of baseItems) {
			mergedBySlug[item.slug] = item;
		}
		for (const item of incomingItems) {
			mergedBySlug[item.slug] = item;
		}

		return Object.values(mergedBySlug);
	};

	const getGifPreviewUrl = (gif: GifItem) =>
		String(
			gif.file?.sm?.webp?.url ??
				gif.file?.sm?.gif?.url ??
				gif.file?.xs?.webp?.url ??
				gif.file?.xs?.gif?.url ??
				gif.file?.md?.webp?.url ??
				gif.file?.md?.gif?.url ??
				gif.file?.sm?.jpg?.url ??
				gif.file?.xs?.jpg?.url ??
				''
		).trim();

	const buildFavoriteGifItemFromUrl = (rawUrl: string): GifItem | null => {
		const parsed = parseHttpUrl(rawUrl);
		if (!parsed) {
			return null;
		}

		const url = parsed.toString();
		const pathname = parsed.pathname.toLowerCase();
		const file: GifFileMap = {};

		if (pathname.endsWith('.gif')) {
			file.sm = { gif: { url } };
			file.md = { gif: { url } };
		} else if (pathname.endsWith('.webp')) {
			file.sm = { webp: { url } };
			file.md = { webp: { url } };
		} else if (
			pathname.endsWith('.jpg') ||
			pathname.endsWith('.jpeg') ||
			pathname.endsWith('.png') ||
			pathname.endsWith('.bmp') ||
			pathname.endsWith('.avif') ||
			pathname.endsWith('.svg')
		) {
			file.sm = { jpg: { url } };
			file.md = { jpg: { url } };
		} else if (pathname.endsWith('.mp4')) {
			file.sm = { mp4: { url } };
			file.md = { mp4: { url } };
		} else if (pathname.endsWith('.webm')) {
			file.sm = { webm: { url } };
			file.md = { webm: { url } };
		} else {
			return null;
		}

		return {
			id: `url:${url}`,
			slug: `url:${url}`,
			title: $i18n.t('Favorite GIF'),
			file
		};
	};

	const fetchGifListByUrl = async (url: string): Promise<GifListResponse> => {
		const cachedResponse = gifCacheState.listByUrl[url];
		if (cachedResponse) {
			return cachedResponse;
		}

		const inFlightRequest = gifCacheState.inFlightListByUrl[url];
		if (inFlightRequest) {
			return await inFlightRequest;
		}

		const request = (async () => {
			const response = await fetch(url);
			if (!response.ok) {
				throw new Error(`KLIPY request failed (${response.status})`);
			}

			const payload = await response.json().catch(() => ({}));
			const rawItems = Array.isArray(payload?.data?.data) ? payload.data.data : [];
			const items = normalizeGifItems(rawItems);
			const parsedResponse: GifListResponse = {
				items,
				currentPage: clampInteger(payload?.data?.current_page, 1, 1, 99999),
				hasNext: Boolean(payload?.data?.has_next)
			};

			gifCacheState.listByUrl[url] = parsedResponse;
			rememberGifItems(items);

			return parsedResponse;
		})();

		gifCacheState.inFlightListByUrl[url] = request;

		try {
			return await request;
		} finally {
			delete gifCacheState.inFlightListByUrl[url];
		}
	};

	const fetchTrendingGifPage = async (page: number) => {
		const gifConfig = resolveGifConfig();
		if (!gifConfig.appKey) {
			throw new Error('KLIPY app key is not configured.');
		}

		const url = buildKlipyUrl(`/api/v1/${encodeURIComponent(gifConfig.appKey)}/gifs/trending`, {
			page,
			per_page: gifConfig.perPage,
			customer_id: gifConfig.customerId,
			locale: gifConfig.locale,
			format_filter: gifConfig.formatFilter
		});

		return await fetchGifListByUrl(url);
	};

	const fetchGifSearchPage = async (query: string, page: number) => {
		const gifConfig = resolveGifConfig();
		if (!gifConfig.appKey) {
			throw new Error('KLIPY app key is not configured.');
		}

		const url = buildKlipyUrl(`/api/v1/${encodeURIComponent(gifConfig.appKey)}/gifs/search`, {
			page,
			per_page: gifConfig.perPage,
			q: query,
			customer_id: gifConfig.customerId,
			locale: gifConfig.locale,
			content_filter: gifConfig.contentFilter,
			format_filter: gifConfig.formatFilter
		});

		return await fetchGifListByUrl(url);
	};

	const normalizeGifCategory = (raw: unknown): GifCategory | null => {
		if (!raw || typeof raw !== 'object') {
			return null;
		}

		const category = raw as {
			category?: string;
			query?: string;
			preview_url?: string;
		};

		const query = String(category.query ?? category.category ?? '').trim();
		if (!query) {
			return null;
		}

		const label = String(category.category ?? query).trim() || query;
		const previewUrl = String(category.preview_url ?? '').trim();

		return {
			label,
			query,
			previewUrl
		};
	};

	const fetchGifCategories = async () => {
		const gifConfig = resolveGifConfig();
		if (!gifConfig.appKey) {
			return [];
		}

		const url = buildKlipyUrl(`/api/v1/${encodeURIComponent(gifConfig.appKey)}/gifs/categories`, {
			locale: gifConfig.categoriesLocale
		});

		const cachedCategories = gifCacheState.categoriesByUrl[url];
		if (cachedCategories) {
			return cachedCategories;
		}

		const response = await fetch(url);
		if (!response.ok) {
			throw new Error(`KLIPY categories request failed (${response.status})`);
		}

		const payload = await response.json().catch(() => ({}));
		const rawCategories = Array.isArray(payload?.data?.categories) ? payload.data.categories : [];
		const categories: GifCategory[] = [];
		const seenQueries = new Set<string>();

		for (const rawCategory of rawCategories) {
			const normalized = normalizeGifCategory(rawCategory);
			if (!normalized) {
				continue;
			}

			const normalizedQuery = normalized.query.toLowerCase();
			if (seenQueries.has(normalizedQuery)) {
				continue;
			}

			seenQueries.add(normalizedQuery);
			categories.push(normalized);
		}

		gifCacheState.categoriesByUrl[url] = categories;
		return categories;
	};

	const fetchGifItemsBySlugs = async (slugs: string[]) => {
		const gifConfig = resolveGifConfig();
		if (!gifConfig.appKey) {
			throw new Error('KLIPY app key is not configured.');
		}

		if (slugs.length === 0) {
			return [];
		}

		const url = buildKlipyUrl(`/api/v1/${encodeURIComponent(gifConfig.appKey)}/gifs/items`, {
			slugs: slugs.join(',')
		});

		const response = await fetch(url);
		if (!response.ok) {
			throw new Error(`KLIPY items request failed (${response.status})`);
		}

		const payload = await response.json().catch(() => ({}));
		const rawItems = Array.isArray(payload?.data?.data) ? payload.data.data : [];
		const items = normalizeGifItems(rawItems);

		rememberGifItems(items);
		return items;
	};

	const createGifSectionState = (): GifSectionState => ({
		items: [],
		page: 0,
		hasNext: true,
		loading: false,
		loaded: false,
		error: ''
	});

	const buildGifSections = (apiCategories: GifCategory[]): GifSection[] => {
		const sections: GifSection[] = [
			{
				id: 'gif-favorites',
				label: 'Favorites',
				type: 'favorites'
			},
			{
				id: 'gif-trending',
				label: 'Trending GIFs',
				type: 'trending'
			}
		];

		const seenQueries = new Set<string>();

		for (const category of apiCategories) {
			const normalizedQuery = category.query.toLowerCase();
			if (seenQueries.has(normalizedQuery)) {
				continue;
			}

			seenQueries.add(normalizedQuery);

			sections.push({
				id: `gif-category-${slugify(category.query) || sections.length}`,
				label: category.label,
				type: 'category',
				query: category.query,
				previewUrl: category.previewUrl || undefined
			});
		}

		for (const fallbackQuery of FALLBACK_GIF_QUERIES) {
			if (sections.length >= MAX_GIF_CATEGORY_SECTIONS + 2) {
				break;
			}

			const normalizedQuery = fallbackQuery.toLowerCase();
			if (seenQueries.has(normalizedQuery)) {
				continue;
			}

			seenQueries.add(normalizedQuery);

			sections.push({
				id: `gif-category-${slugify(fallbackQuery) || sections.length}`,
				label: toTitleCase(fallbackQuery),
				type: 'category',
				query: fallbackQuery
			});
		}

		return sections;
	};

	const emojiMatchesSearch = (emoji: PickerEmoji, query: string) => {
		if (!query) {
			return true;
		}

		return emoji.shortCode.includes(query) || emoji.aliases.some((alias) => alias.includes(query));
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
	let gifContainerElement: HTMLDivElement | null = null;
	let gifAutoLoadInFlight = false;
	let gifAutoLoadLastRunAt = 0;

	let gifItemsBySlug: Record<string, GifItem> = { ...gifCacheState.itemsBySlug };
	let gifSections: GifSection[] = buildGifSections([]);
	let gifSectionStateById: Record<string, GifSectionState> = {};
	let gifSearchState: GifSectionState = createGifSectionState();
	let gifSearchQuery = '';

	let gifInitError = '';
	let gifTabInitialized = false;
	let gifTabInitializing = false;
	let gifApiKeyConfigured = false;
	let lastGifAppKey = '';

	let favoriteGifSlugs: string[] = [];
	let favoriteGifExternalUrls: string[] = [];
	let favoriteGifItems: GifItem[] = [];
	let favoriteGifsLoading = false;
	let favoriteGifsError = '';

	let activeGifSectionId = '';

	let gifSearchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	let gifSearchRequestToken = 0;

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

		recentShortCodes = [
			normalized,
			...recentShortCodes.filter((item) => item !== normalized)
		].slice(0, MAX_RECENT);
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
			favoriteShortCodes = [
				normalized,
				...favoriteShortCodes.filter((item) => item !== normalized)
			];
		}

		writeLocalList(FAVORITES_KEY, favoriteShortCodes);
	};

	const selectEmoji = (emoji: PickerEmoji) => {
		onSubmit(emoji.shortCode);
		addRecentEmoji(emoji.shortCode);
		show = false;
	};

	const selectGif = async (gif: GifItem) => {
		const slug = normalizeGifSlug(gif.slug || gif.id);
		if (slug) {
			rememberGifItems([{ ...gif, slug }]);
		}

		try {
			if (onGifSubmit) {
				await Promise.resolve(onGifSubmit(gif));
			} else {
				onSubmit(slug || gif.title);
			}

			show = false;
		} catch (error) {
			toast.error(getErrorMessage(error, $i18n.t('Failed to insert GIF.')));
		}
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

	const getGifSectionById = (sectionId: string) =>
		gifSections.find((section) => section.id === sectionId) ?? null;

	const getGifSectionState = (sectionId: string): GifSectionState =>
		gifSectionStateById[sectionId] ?? createGifSectionState();

	const setGifSectionState = (sectionId: string, nextState: GifSectionState) => {
		gifSectionStateById = {
			...gifSectionStateById,
			[sectionId]: nextState
		};
	};

	const ensureGifSectionState = (sectionId: string): GifSectionState => {
		const existingState = gifSectionStateById[sectionId];
		if (existingState) {
			return existingState;
		}

		const createdState = createGifSectionState();
		setGifSectionState(sectionId, createdState);
		return createdState;
	};

	const ensureFavoriteGifItemsLoaded = async () => {
		if (favoriteGifSlugs.length === 0) {
			favoriteGifsError = '';
			return;
		}

		const missingSlugs = favoriteGifSlugs.filter((slug) => !gifItemsBySlug[slug]);
		if (missingSlugs.length === 0) {
			favoriteGifsError = '';
			return;
		}

		if (!gifApiKeyConfigured) {
			favoriteGifsError = $i18n.t('Set VITE_KLIPY_APP_KEY to load favorited GIFs.');
			return;
		}

		favoriteGifsLoading = true;
		favoriteGifsError = '';

		try {
			for (const slugChunk of chunk(missingSlugs, 24)) {
				await fetchGifItemsBySlugs(slugChunk);
			}
		} catch (error) {
			favoriteGifsError = getErrorMessage(error, $i18n.t('Failed to load favorites.'));
		} finally {
			favoriteGifsLoading = false;
		}
	};

	const isGifFavorite = (gif: GifItem) => {
		const slug = normalizeGifSlug(gif.slug || gif.id);
		return Boolean(slug && favoriteGifSlugs.includes(slug));
	};

	const toggleGifFavorite = (gif: GifItem) => {
		const slug = normalizeGifSlug(gif.slug || gif.id);
		if (!slug) {
			return;
		}

		if (favoriteGifSlugs.includes(slug)) {
			favoriteGifSlugs = favoriteGifSlugs.filter((item) => item !== slug);
		} else {
			if (favoriteGifSlugs.length >= MAX_GIF_FAVORITES) {
				toast.error(
					$i18n.t('You can favorite up to {{COUNT}} GIFs.', {
						COUNT: MAX_GIF_FAVORITES
					})
				);
				return;
			}

			favoriteGifSlugs = [slug, ...favoriteGifSlugs.filter((item) => item !== slug)].slice(
				0,
				MAX_GIF_FAVORITES
			);
			rememberGifItems([gif]);
		}

		writeLocalStringList(GIF_FAVORITES_KEY, favoriteGifSlugs);
		dispatchGifFavoritesUpdated();
	};

	const loadGifSection = async (sectionId: string, reset = false) => {
		const section = getGifSectionById(sectionId);
		if (!section || section.type === 'favorites') {
			return;
		}

		const currentState = ensureGifSectionState(sectionId);
		if (currentState.loading) {
			return;
		}

		if (!reset && currentState.loaded && !currentState.hasNext) {
			return;
		}

		const targetPage = reset ? 1 : currentState.page + 1;

		setGifSectionState(sectionId, {
			...(reset
				? createGifSectionState()
				: {
						...currentState
					}),
			loading: true
		});

		try {
			const response =
				section.type === 'trending'
					? await fetchTrendingGifPage(targetPage)
					: await fetchGifSearchPage(section.query ?? '', targetPage);

			setGifSectionState(sectionId, {
				items: mergeGifItems(reset ? [] : currentState.items, response.items),
				page: targetPage,
				hasNext: response.hasNext,
				loading: false,
				loaded: true,
				error: ''
			});

			await tick();
			await maybeAutoLoadMoreGifs();
		} catch (error) {
			const latestState = ensureGifSectionState(sectionId);
			setGifSectionState(sectionId, {
				...latestState,
				loading: false,
				loaded: true,
				error: getErrorMessage(error, $i18n.t('Failed to load GIFs.'))
			});
		}
	};

	const ensureGifSectionLoaded = async (sectionId: string) => {
		const section = getGifSectionById(sectionId);
		if (!section) {
			return;
		}

		if (section.type === 'favorites') {
			await ensureFavoriteGifItemsLoaded();
			return;
		}

		const currentState = ensureGifSectionState(sectionId);
		if (currentState.loaded || currentState.loading) {
			return;
		}

		await loadGifSection(sectionId, true);
	};

	const resetGifScrollPosition = () => {
		gifAutoLoadLastRunAt = 0;

		if (!gifContainerElement) {
			return;
		}

		gifContainerElement.scrollTop = 0;
	};

	const openGifSection = async (sectionId: string) => {
		if (sectionId === 'gif-favorites') {
			syncGifFavoritesFromStorage();
		}

		activeGifSectionId = sectionId;
		resetGifScrollPosition();
		await ensureGifSectionLoaded(sectionId);
		await tick();
		await maybeAutoLoadMoreGifs();
	};

	const closeGifSection = () => {
		activeGifSectionId = '';
		resetGifScrollPosition();
	};

	const getGifSectionPreviewUrl = (section: GifSection) => {
		if (section.type === 'favorites') {
			const favoriteItem = favoriteGifItems[0];
			return favoriteItem ? getGifPreviewUrl(favoriteItem) : '';
		}

		if (section.type === 'trending') {
			const trendingItems = getGifSectionState(section.id).items;
			return trendingItems[0] ? getGifPreviewUrl(trendingItems[0]) : '';
		}

		if (section.previewUrl) {
			return section.previewUrl;
		}

		const sectionItems = getGifSectionState(section.id).items;
		return sectionItems[0] ? getGifPreviewUrl(sectionItems[0]) : '';
	};

	const resetGifSearchState = () => {
		if (gifSearchDebounceTimer) {
			clearTimeout(gifSearchDebounceTimer);
			gifSearchDebounceTimer = null;
		}

		gifSearchRequestToken += 1;
		gifSearchQuery = '';
		gifSearchState = createGifSectionState();
	};

	const runGifSearch = async (rawQuery: string) => {
		const query = rawQuery.trim();
		if (!query) {
			resetGifSearchState();
			return;
		}

		const requestToken = ++gifSearchRequestToken;
		gifSearchQuery = query;
		gifSearchState = {
			...createGifSectionState(),
			loading: true
		};

		try {
			const response = await fetchGifSearchPage(query, 1);
			if (requestToken !== gifSearchRequestToken) {
				return;
			}

			gifSearchState = {
				items: response.items,
				page: 1,
				hasNext: response.hasNext,
				loading: false,
				loaded: true,
				error: ''
			};

			await tick();
			await maybeAutoLoadMoreGifs();
		} catch (error) {
			if (requestToken !== gifSearchRequestToken) {
				return;
			}

			gifSearchState = {
				...createGifSectionState(),
				loading: false,
				loaded: true,
				error: getErrorMessage(error, $i18n.t('Failed to load GIFs.'))
			};
		}
	};

	const handleGifSearchInput = (value: string) => {
		if (gifSearchDebounceTimer) {
			clearTimeout(gifSearchDebounceTimer);
			gifSearchDebounceTimer = null;
		}

		const query = String(value ?? '').trim();
		if (!query) {
			activeGifSectionId = '';
			resetGifScrollPosition();
			resetGifSearchState();
			return;
		}

		activeGifSectionId = '';
		resetGifScrollPosition();
		gifSearchDebounceTimer = setTimeout(() => {
			void runGifSearch(query);
		}, 220);
	};

	const loadMoreGifSearch = async () => {
		if (!gifSearchQuery || gifSearchState.loading || !gifSearchState.hasNext) {
			return;
		}

		const targetPage = gifSearchState.page + 1;
		gifSearchState = {
			...gifSearchState,
			loading: true
		};

		try {
			const response = await fetchGifSearchPage(gifSearchQuery, targetPage);
			gifSearchState = {
				items: mergeGifItems(gifSearchState.items, response.items),
				page: targetPage,
				hasNext: response.hasNext,
				loading: false,
				loaded: true,
				error: ''
			};

			await tick();
			await maybeAutoLoadMoreGifs();
		} catch (error) {
			gifSearchState = {
				...gifSearchState,
				loading: false,
				error: getErrorMessage(error, $i18n.t('Failed to load GIFs.'))
			};
		}
	};

	const isNearBottom = (element: HTMLDivElement | null, threshold = GIF_AUTO_LOAD_THRESHOLD_PX) => {
		if (!element) {
			return false;
		}

		const remaining = element.scrollHeight - element.scrollTop - element.clientHeight;
		return remaining <= threshold;
	};

	const maybeAutoLoadMoreGifs = async () => {
		const now = Date.now();
		if (
			gifAutoLoadInFlight ||
			now - gifAutoLoadLastRunAt < GIF_AUTO_LOAD_COOLDOWN_MS ||
			!isNearBottom(gifContainerElement)
		) {
			return;
		}

		gifAutoLoadInFlight = true;
		gifAutoLoadLastRunAt = now;

		try {
			if (search.trim() !== '') {
				if (!gifSearchQuery || gifSearchState.loading || !gifSearchState.hasNext) {
					return;
				}

				await loadMoreGifSearch();
				return;
			}

			if (!activeGifSectionId) {
				return;
			}

			const activeSection = getGifSectionById(activeGifSectionId);
			if (!activeSection || activeSection.type === 'favorites') {
				return;
			}

			const sectionState = getGifSectionState(activeSection.id);
			if (sectionState.loading || !sectionState.hasNext) {
				return;
			}

			await loadGifSection(activeSection.id, false);
		} finally {
			gifAutoLoadInFlight = false;
		}
	};

	const handleGifScroll = () => {
		void maybeAutoLoadMoreGifs();
	};

	const ensureGifTabInitialized = async () => {
		syncGifFavoritesFromStorage();

		if (gifTabInitializing) {
			return;
		}

		if (gifTabInitialized) {
			await ensureFavoriteGifItemsLoaded();
			return;
		}

		gifTabInitializing = true;
		gifInitError = '';

		try {
			if (!gifApiKeyConfigured) {
				gifSections = buildGifSections([]);
				activeGifSectionId = '';
				gifInitError = $i18n.t('Set VITE_KLIPY_APP_KEY to enable trending and search GIFs.');
				await ensureFavoriteGifItemsLoaded();
				gifTabInitialized = true;
				return;
			}

			const categories = await fetchGifCategories().catch((error) => {
				gifInitError = getErrorMessage(error, $i18n.t('Failed to load categories.'));
				return [];
			});

			gifSections = buildGifSections(categories);
			gifSectionStateById = {};
			activeGifSectionId = '';

			await Promise.all([ensureFavoriteGifItemsLoaded(), loadGifSection('gif-trending', true)]);

			gifTabInitialized = true;
		} finally {
			gifTabInitializing = false;
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

	const syncGifFavoritesFromStorage = () => {
		favoriteGifSlugs = readLocalStringList(GIF_FAVORITES_KEY, normalizeGifSlug).slice(
			0,
			MAX_GIF_FAVORITES
		);
		favoriteGifExternalUrls = readLocalStringList(
			GIF_EMBED_FAVORITES_KEY,
			normalizeGifFavoriteUrl
		).slice(0, MAX_GIF_FAVORITES);
	};

	onMount(() => {
		favoriteShortCodes = readLocalList(FAVORITES_KEY);
		recentShortCodes = readLocalList(RECENT_KEY);

		syncGifFavoritesFromStorage();

		if (typeof window === 'undefined') {
			return;
		}

		const handleGifFavoritesUpdated = () => {
			syncGifFavoritesFromStorage();
		};

		window.addEventListener(GIF_FAVORITES_EVENT, handleGifFavoritesUpdated);
		window.addEventListener('storage', handleGifFavoritesUpdated);

		return () => {
			window.removeEventListener(GIF_FAVORITES_EVENT, handleGifFavoritesUpdated);
			window.removeEventListener('storage', handleGifFavoritesUpdated);
		};
	});

	onDestroy(() => {
		if (gifSearchDebounceTimer) {
			clearTimeout(gifSearchDebounceTimer);
			gifSearchDebounceTimer = null;
		}
	});

	$: if (!showGifTab && activeTab === 'gif') {
		activeTab = 'emoji';
	}

	$: gifApiKeyConfigured = Boolean(resolveGifConfig().appKey);

	$: {
		const currentGifAppKey = resolveGifConfig().appKey;
		if (currentGifAppKey !== lastGifAppKey) {
			lastGifAppKey = currentGifAppKey;
			gifTabInitialized = false;
			gifSectionStateById = {};
			gifSections = buildGifSections([]);
			activeGifSectionId = '';
		}
	}

	$: {
		const fromSlugs = favoriteGifSlugs
			.map((slug) => gifItemsBySlug[slug])
			.filter((item): item is GifItem => item !== undefined);

		const fromUrls = favoriteGifExternalUrls
			.map((url) => buildFavoriteGifItemFromUrl(url))
			.filter((item): item is GifItem => item !== null);

		const merged: GifItem[] = [];
		const seen = new Set<string>();

		for (const item of [...fromSlugs, ...fromUrls]) {
			const key = getGifPreviewUrl(item) || item.slug || item.id;
			if (!key || seen.has(key)) {
				continue;
			}

			seen.add(key);
			merged.push(item);
		}

		favoriteGifItems = merged;
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

	$: if (activeGifSectionId && !gifSections.some((section) => section.id === activeGifSectionId)) {
		activeGifSectionId = '';
	}

	$: if (show && showGifTab && activeTab === 'gif') {
		void ensureGifTabInitialized();
	}
</script>

<DropdownMenu.Root
	bind:open={show}
	closeFocus={false}
	onOpenChange={(state) => {
		if (state) {
			syncGifFavoritesFromStorage();

			if (activeTab === 'gif' && showGifTab) {
				void ensureGifTabInitialized();
			} else {
				void ensureEmojiDataset();
			}
			return;
		}

		search = '';
		activeTab = 'emoji';
		activeGifSectionId = '';
		resetGifScrollPosition();
		resetGifSearchState();
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
				<div class="inline-flex items-center gap-1.5">
					<button
						type="button"
						class="px-3 py-1.5 text-sm font-semibold rounded-lg transition {activeTab === 'gif'
							? 'bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-white'
							: 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800'}"
						on:click={() => {
							activeTab = 'gif';
							search = '';
							activeGifSectionId = '';
							resetGifScrollPosition();
							resetGifSearchState();
							void ensureGifTabInitialized();
						}}
					>
						{$i18n.t('GIFs')}
					</button>
					<button
						type="button"
						class="px-3 py-1.5 text-sm font-semibold rounded-lg transition {activeTab === 'emoji'
							? 'bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-white'
							: 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800'}"
						on:click={() => {
							activeTab = 'emoji';
							search = '';
							resetGifScrollPosition();
							resetGifSearchState();
							void ensureEmojiDataset();
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
				<div class="relative">
					<div
						class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 pointer-events-none"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 20 20"
							fill="currentColor"
							class="size-4"
						>
							<path
								fill-rule="evenodd"
								d="M9 3.5a5.5 5.5 0 1 0 3.473 9.766l3.63 3.63a.75.75 0 1 0 1.06-1.06l-3.63-3.63A5.5 5.5 0 0 0 9 3.5ZM5 9a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<input
						type="text"
						class="w-full text-sm bg-transparent outline-hidden border border-gray-200/80 dark:border-gray-700 rounded-xl pl-9 pr-3 py-2"
						placeholder={$i18n.t('Search GIFs')}
						bind:value={search}
						on:focus={() => {
							void ensureGifTabInitialized();
						}}
						on:input={(event) => {
							const target = event.currentTarget as HTMLInputElement;
							handleGifSearchInput(target.value);
						}}
					/>
				</div>
			{/if}
		</div>

		{#if showGifTab && activeTab === 'gif'}
			<div class="h-96 flex">
				<div
					class="flex-1 overflow-y-auto px-2 pb-2 pt-1 text-sm"
					bind:this={gifContainerElement}
					on:scroll={handleGifScroll}
				>
					{#if !gifApiKeyConfigured}
						<div class="px-1 pb-1 text-xs text-amber-600 dark:text-amber-400">
							{$i18n.t('Set VITE_KLIPY_APP_KEY to enable trending and search GIFs.')}
						</div>
					{/if}

					{#if search.trim() !== ''}
						<div class="text-xs font-medium py-1.5 px-1 text-gray-500 dark:text-gray-400">
							{$i18n.t('Results')}
						</div>

						{#if gifSearchState.loading && gifSearchState.items.length === 0}
							<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-6">
								{$i18n.t('Loading GIFs...')}
							</div>
						{:else if gifSearchState.error && gifSearchState.items.length === 0}
							<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-6">
								<div>{gifSearchState.error}</div>
								<button
									type="button"
									class="mt-2 px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
									on:click={() => {
										void runGifSearch(search);
									}}
								>
									{$i18n.t('Retry')}
								</button>
							</div>
						{:else if gifSearchState.items.length === 0}
							<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-6">
								{$i18n.t('No results')}
							</div>
						{:else}
							<div class="grid grid-cols-3 gap-1.5 pb-2">
								{#each gifSearchState.items as gifItem (gifItem.slug || gifItem.id)}
									{@const previewUrl = getGifPreviewUrl(gifItem)}
									<div class="relative group/gif">
										<button
											type="button"
											class="w-full aspect-square rounded-xl overflow-hidden border border-transparent hover:border-gray-300/80 dark:hover:border-gray-600/80 bg-gray-100 dark:bg-gray-800 transition"
											on:click={() => {
												void selectGif(gifItem);
											}}
										>
											{#if previewUrl}
												<img
													src={previewUrl}
													alt={gifItem.title}
													class="size-full object-cover"
													loading="lazy"
												/>
											{:else}
												<div
													class="size-full flex items-center justify-center text-[11px] text-gray-500 dark:text-gray-400"
												>
													GIF
												</div>
											{/if}
										</button>

										<button
											type="button"
											class="absolute top-1 right-1 rounded-full bg-white/90 dark:bg-gray-900/90 p-1 border border-gray-200/90 dark:border-gray-700/90 opacity-0 group-hover/gif:opacity-100 transition"
											on:click|stopPropagation={() => toggleGifFavorite(gifItem)}
											aria-label={$i18n.t('Toggle favorite')}
										>
											<Star
												className={`size-3 ${isGifFavorite(gifItem) ? 'fill-yellow-400 text-yellow-500' : 'text-gray-500 dark:text-gray-300'}`}
												strokeWidth="2"
											/>
										</button>
									</div>
								{/each}
							</div>

							{#if gifSearchState.loading && gifSearchState.items.length > 0}
								<div class="w-full py-2 text-center text-xs text-gray-500 dark:text-gray-400">
									{$i18n.t('Loading...')}
								</div>
							{/if}
						{/if}
					{:else if gifTabInitializing && !gifTabInitialized}
						<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-6">
							{$i18n.t('Loading GIFs...')}
						</div>
					{:else}
						{#if gifInitError}
							<div class="px-1 pb-1 text-xs text-gray-500 dark:text-gray-400">{gifInitError}</div>
						{/if}

						{#if activeGifSectionId === ''}
							<div class="grid grid-cols-2 gap-2 pb-2">
								{#each gifSections as section}
									{@const previewUrl = getGifSectionPreviewUrl(section)}
									<button
										type="button"
										class="relative rounded-xl overflow-hidden aspect-[2.15/1] bg-gray-200 dark:bg-gray-800 ring-1 ring-black/5 dark:ring-white/10 hover:brightness-110 transition"
										aria-label={section.label}
										on:click={() => {
											void openGifSection(section.id);
										}}
									>
										{#if previewUrl}
											<img
												src={previewUrl}
												alt={section.label}
												class="absolute inset-0 size-full object-cover"
												loading="lazy"
											/>
										{:else}
											<div
												class="absolute inset-0 bg-linear-to-br from-blue-500/80 via-blue-600/60 to-purple-700/70"
											/>
										{/if}

										<div
											class="absolute inset-0 bg-linear-to-t from-black/70 via-black/35 to-black/10"
										/>

										<div
											class="absolute inset-x-0 bottom-0 text-white text-sm font-semibold px-3 py-2.5 text-left tracking-tight drop-shadow-md"
										>
											{#if section.type === 'favorites'}
												<span class="inline-flex items-center gap-1.5">
													<Star
														className={`size-3.5 ${favoriteGifItems.length > 0 ? 'fill-yellow-300 text-yellow-300' : 'text-white'}`}
														strokeWidth="2"
													/>
													{section.label}
												</span>
											{:else if section.type === 'trending'}
												<span class="inline-flex items-center gap-1.5">
													<span aria-hidden="true">🔥</span>
													{section.label}
												</span>
											{:else}
												{section.label}
											{/if}
										</div>
									</button>
								{/each}
							</div>
						{:else}
							{@const activeSection = getGifSectionById(activeGifSectionId)}
							{#if activeSection}
								{@const sectionState = getGifSectionState(activeSection.id)}
								{@const sectionItems =
									activeSection.type === 'favorites' ? favoriteGifItems : sectionState.items}

								<div class="flex items-center justify-between mb-2 px-0.5">
									<button
										type="button"
										class="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
										on:click={closeGifSection}
									>
										{$i18n.t('Back')}
									</button>
									<div class="text-xs font-semibold text-gray-600 dark:text-gray-300">
										{activeSection.label}
									</div>
								</div>

								{#if activeSection.type === 'favorites' && favoriteGifItems.length === 0}
									<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
										{$i18n.t('No favorites yet')}
									</div>
								{:else if activeSection.type === 'favorites' && favoriteGifsLoading && sectionItems.length === 0}
									<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
										{$i18n.t('Loading GIFs...')}
									</div>
								{:else if activeSection.type === 'favorites' && favoriteGifsError && sectionItems.length === 0}
									<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
										<div>{favoriteGifsError}</div>
										<button
											type="button"
											class="mt-2 px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
											on:click={() => {
												void ensureFavoriteGifItemsLoaded();
											}}
										>
											{$i18n.t('Retry')}
										</button>
									</div>
								{:else if sectionItems.length === 0}
									{#if activeSection.type !== 'favorites' && sectionState.loading}
										<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
											{$i18n.t('Loading GIFs...')}
										</div>
									{:else if activeSection.type !== 'favorites' && sectionState.error}
										<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
											<div>{sectionState.error}</div>
											<button
												type="button"
												class="mt-2 px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
												on:click={() => {
													void loadGifSection(activeSection.id, true);
												}}
											>
												{$i18n.t('Retry')}
											</button>
										</div>
									{:else if activeSection.type !== 'favorites' && !sectionState.loaded}
										<div class="w-full py-2 flex justify-center">
											<button
												type="button"
												class="text-xs px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
												on:click={() => {
													void loadGifSection(activeSection.id, true);
												}}
											>
												{$i18n.t('Load GIFs')}
											</button>
										</div>
									{:else}
										<div class="text-center text-xs text-gray-500 dark:text-gray-400 w-full py-4">
											{$i18n.t('No results')}
										</div>
									{/if}
								{:else}
									<div class="grid grid-cols-3 gap-1.5 pb-1">
										{#each sectionItems as gifItem (gifItem.slug || gifItem.id)}
											{@const previewUrl = getGifPreviewUrl(gifItem)}
											<div class="relative group/gif">
												<button
													type="button"
													class="w-full aspect-square rounded-xl overflow-hidden border border-transparent hover:border-gray-300/80 dark:hover:border-gray-600/80 bg-gray-100 dark:bg-gray-800 transition"
													on:click={() => {
														void selectGif(gifItem);
													}}
												>
													{#if previewUrl}
														<img
															src={previewUrl}
															alt={gifItem.title}
															class="size-full object-cover"
															loading="lazy"
														/>
													{:else}
														<div
															class="size-full flex items-center justify-center text-[11px] text-gray-500 dark:text-gray-400"
														>
															GIF
														</div>
													{/if}
												</button>

												<button
													type="button"
													class="absolute top-1 right-1 rounded-full bg-white/90 dark:bg-gray-900/90 p-1 border border-gray-200/90 dark:border-gray-700/90 opacity-0 group-hover/gif:opacity-100 transition"
													on:click|stopPropagation={() => toggleGifFavorite(gifItem)}
													aria-label={$i18n.t('Toggle favorite')}
												>
													<Star
														className={`size-3 ${isGifFavorite(gifItem) ? 'fill-yellow-400 text-yellow-500' : 'text-gray-500 dark:text-gray-300'}`}
														strokeWidth="2"
													/>
												</button>
											</div>
										{/each}
									</div>

									{#if activeSection.type !== 'favorites' && sectionState.loading && sectionItems.length > 0}
										<div class="w-full py-2 text-center text-xs text-gray-500 dark:text-gray-400">
											{$i18n.t('Loading...')}
										</div>
									{/if}
								{/if}
							{/if}
						{/if}
					{/if}
				</div>
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
									class="w-full h-9 rounded-lg flex items-center justify-center transition {activeSectionId ===
									section.id
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
