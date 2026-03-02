<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Image from '$lib/components/common/Image.svelte';
	import Star from '$lib/components/icons/Star.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	export let href = '';
	export let alt = '';
	export let forceImage = false;

	const i18n = getContext('i18n');

	type EmbedKind = 'none' | 'image' | 'video' | 'audio' | 'youtube' | 'spotify' | 'soundcloud';

	const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.avif', '.svg'];
	const VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mov', '.m4v', '.mkv', '.ogv'];
	const AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wav', '.flac', '.ogg', '.opus', '.aac', '.weba'];
	const EMBED_GIF_EXTENSIONS = ['.gif', '.webp'];

	const GIF_FAVORITES_KEY = 'awu.gif-picker.favorites.v1';
	const GIF_EMBED_FAVORITES_KEY = 'awu.gif-embed.favorites.v1';
	const MAX_EMBED_GIF_FAVORITES = 2048;
	const GIF_FAVORITES_EVENT = 'awu:gif-favorites-updated';

	let favoriteGifSlugs: string[] = [];
	let favoriteGifUrls: string[] = [];
	let showGifPreview = false;

	const parseHttpUrl = (value: string) => {
		const rawValue = String(value ?? '').trim();
		if (!rawValue) {
			return null;
		}

		const parseWithBase = (input: string, base?: string) => {
			try {
				const parsed = base ? new URL(input, base) : new URL(input);
				if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
					return parsed;
				}
			} catch {
				// Ignore invalid URLs
			}

			return null;
		};

		return (
			parseWithBase(rawValue) ??
			(typeof window !== 'undefined' ? parseWithBase(rawValue, window.location.origin) : null)
		);
	};

	const hasKnownExtension = (url: URL, extensions: string[]) => {
		const pathname = url.pathname.toLowerCase();
		return extensions.some((extension) => pathname.endsWith(extension));
	};

	const normalizeEmbeddedGifUrl = (value: string) => {
		const parsed = parseHttpUrl(value);
		return parsed ? parsed.toString() : '';
	};

	const readStringList = (
		key: string,
		normalize: (value: unknown) => string = (value) => String(value ?? '').trim()
	) => {
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

			return values.slice(0, MAX_EMBED_GIF_FAVORITES);
		} catch {
			return [];
		}
	};

	const resolveGifSlugForUrl = (urlValue: string) => {
		const normalizedUrl = normalizeEmbeddedGifUrl(urlValue);
		if (!normalizedUrl) {
			return '';
		}

		const root = globalThis as typeof globalThis & {
			__awuGifCacheState?: {
				slugByAssetUrl?: Record<string, string>;
			};
		};

		return String(root.__awuGifCacheState?.slugByAssetUrl?.[normalizedUrl] ?? '').trim();
	};

	const persistGifFavorites = () => {
		if (typeof localStorage === 'undefined') {
			return;
		}

		localStorage.setItem(GIF_FAVORITES_KEY, JSON.stringify(favoriteGifSlugs));
		localStorage.setItem(GIF_EMBED_FAVORITES_KEY, JSON.stringify(favoriteGifUrls));

		if (typeof window !== 'undefined') {
			window.dispatchEvent(new CustomEvent(GIF_FAVORITES_EVENT));
		}
	};

	const syncGifFavorites = () => {
		favoriteGifSlugs = readStringList(GIF_FAVORITES_KEY);
		favoriteGifUrls = readStringList(GIF_EMBED_FAVORITES_KEY, normalizeEmbeddedGifUrl);
	};

	const isEmbeddedGifFavorite = (urlValue: string) => {
		const normalizedUrl = normalizeEmbeddedGifUrl(urlValue);
		if (!normalizedUrl) {
			return false;
		}

		const slug = resolveGifSlugForUrl(normalizedUrl);
		return Boolean(
			favoriteGifUrls.includes(normalizedUrl) || (slug && favoriteGifSlugs.includes(slug))
		);
	};

	const toggleEmbeddedGifFavorite = (urlValue: string) => {
		const normalizedUrl = normalizeEmbeddedGifUrl(urlValue);
		if (!normalizedUrl) {
			return;
		}

		const slug = resolveGifSlugForUrl(normalizedUrl);
		const isFavorited =
			favoriteGifUrls.includes(normalizedUrl) || Boolean(slug && favoriteGifSlugs.includes(slug));

		if (isFavorited) {
			favoriteGifUrls = favoriteGifUrls.filter((item) => item !== normalizedUrl);
			if (slug) {
				favoriteGifSlugs = favoriteGifSlugs.filter((item) => item !== slug);
			}

			persistGifFavorites();
			toast.success($i18n.t('Removed from GIF favorites'));
			return;
		}

		if (slug) {
			favoriteGifSlugs = [slug, ...favoriteGifSlugs.filter((item) => item !== slug)].slice(
				0,
				MAX_EMBED_GIF_FAVORITES
			);
		}
		favoriteGifUrls = [normalizedUrl, ...favoriteGifUrls.filter((item) => item !== normalizedUrl)].slice(
			0,
			MAX_EMBED_GIF_FAVORITES
		);

		persistGifFavorites();
		toast.success($i18n.t('Added to GIF favorites'));
	};

	const parseYouTubeTime = (value: string) => {
		const raw = String(value ?? '').trim().toLowerCase();
		if (!raw) {
			return 0;
		}

		if (/^\d+$/.test(raw)) {
			return Number(raw);
		}

		const match = raw.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/);
		if (!match) {
			return 0;
		}

		const hours = Number(match[1] ?? 0);
		const minutes = Number(match[2] ?? 0);
		const seconds = Number(match[3] ?? 0);

		return hours * 3600 + minutes * 60 + seconds;
	};

	const getYouTubeVideoId = (url: URL) => {
		const host = url.hostname.toLowerCase();
		const path = url.pathname;

		if (host === 'youtu.be' || host.endsWith('.youtu.be')) {
			return path.split('/').filter(Boolean)[0] ?? '';
		}

		if (
			host === 'youtube.com' ||
			host === 'www.youtube.com' ||
			host === 'm.youtube.com' ||
			host === 'youtube-nocookie.com' ||
			host === 'www.youtube-nocookie.com'
		) {
			if (path === '/watch') {
				return url.searchParams.get('v') ?? '';
			}

			const segments = path.split('/').filter(Boolean);
			if (segments.length >= 2 && ['shorts', 'embed', 'v', 'live'].includes(segments[0])) {
				return segments[1];
			}
		}

		return '';
	};

	const getSpotifyTypeAndId = (url: URL) => {
		const host = url.hostname.toLowerCase();
		if (host !== 'open.spotify.com') {
			return null;
		}

		const match = url.pathname.match(
			/^\/(track|album|playlist|episode|show|artist)\/([A-Za-z0-9]+)/
		);
		if (!match) {
			return null;
		}

		return {
			type: match[1],
			id: match[2]
		};
	};

	const getEmbedData = (urlValue: string) => {
		const rawValue = String(urlValue ?? '').trim();
		if (
			forceImage &&
			(rawValue.toLowerCase().startsWith('data:image/') || rawValue.toLowerCase().startsWith('blob:'))
		) {
			return { kind: 'image' as EmbedKind, src: rawValue };
		}

		const url = parseHttpUrl(urlValue);
		if (!url) {
			return { kind: 'none' as EmbedKind, src: '' };
		}

		const youtubeId = getYouTubeVideoId(url);
		if (youtubeId) {
			const start =
				parseYouTubeTime(url.searchParams.get('t') ?? '') ||
				parseYouTubeTime(url.searchParams.get('start') ?? '');
			const embedUrl = new URL(`https://www.youtube-nocookie.com/embed/${youtubeId}`);
			if (start > 0) {
				embedUrl.searchParams.set('start', String(start));
			}

			return { kind: 'youtube' as EmbedKind, src: embedUrl.toString() };
		}

		const spotify = getSpotifyTypeAndId(url);
		if (spotify) {
			return {
				kind: 'spotify' as EmbedKind,
				src: `https://open.spotify.com/embed/${spotify.type}/${spotify.id}`
			};
		}

		const host = url.hostname.toLowerCase();
		if (host === 'soundcloud.com' || host.endsWith('.soundcloud.com')) {
			return {
				kind: 'soundcloud' as EmbedKind,
				src: `https://w.soundcloud.com/player/?url=${encodeURIComponent(url.toString())}&auto_play=false&show_comments=false&hide_related=false&show_user=true&show_reposts=false&visual=true`
			};
		}

		if (hasKnownExtension(url, IMAGE_EXTENSIONS)) {
			return { kind: 'image' as EmbedKind, src: url.toString() };
		}

		if (hasKnownExtension(url, VIDEO_EXTENSIONS)) {
			return { kind: 'video' as EmbedKind, src: url.toString() };
		}

			if (hasKnownExtension(url, AUDIO_EXTENSIONS)) {
				return { kind: 'audio' as EmbedKind, src: url.toString() };
			}

			if (forceImage) {
				return { kind: 'image' as EmbedKind, src: url.toString() };
			}

			return { kind: 'none' as EmbedKind, src: '' };
		};

	const isGifImageUrl = (urlValue: string) => {
		const parsed = parseHttpUrl(urlValue);
		return Boolean(parsed && hasKnownExtension(parsed, EMBED_GIF_EXTENSIONS));
	};

	const closeGifPreview = () => {
		showGifPreview = false;
	};

	const handleWindowKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			showGifPreview = false;
		}
	};

	onMount(() => {
		syncGifFavorites();

		if (typeof window === 'undefined') {
			return;
		}

		const handleFavoritesUpdated = () => {
			syncGifFavorites();
		};

		window.addEventListener(GIF_FAVORITES_EVENT, handleFavoritesUpdated);
		window.addEventListener('storage', handleFavoritesUpdated);

		return () => {
			window.removeEventListener(GIF_FAVORITES_EVENT, handleFavoritesUpdated);
			window.removeEventListener('storage', handleFavoritesUpdated);
		};
	});

	$: embed = getEmbedData(href);
	$: isEmbeddedGif = embed.kind === 'image' && isGifImageUrl(embed.src);
	$: embeddedGifFavorited = isEmbeddedGif ? isEmbeddedGifFavorite(embed.src) : false;
</script>

<svelte:window on:keydown={handleWindowKeydown} />

{#if embed.kind === 'image'}
	{#if isEmbeddedGif}
		<span class="block mt-2 max-w-full">
			<div class="relative group/gif-embed inline-block max-w-full">
				<button
					type="button"
					class="max-w-full"
					on:click={() => {
						showGifPreview = true;
					}}
					aria-label={$i18n.t('Show image preview')}
				>
						<img
							src={embed.src}
							alt={alt || 'Embedded GIF'}
							class="w-full max-h-[26rem] rounded-xl border border-gray-200 dark:border-gray-800 object-contain bg-black/5 dark:bg-black/20"
							loading="lazy"
							draggable="false"
					/>
				</button>

					<button
						type="button"
						class={`absolute z-20 pointer-events-auto top-2 right-2 rounded-full bg-white/95 dark:bg-gray-900/95 p-1.5 border border-gray-200/90 dark:border-gray-700/90 transition ${embeddedGifFavorited ? 'opacity-100' : 'opacity-100 md:opacity-0 md:group-hover/gif-embed:opacity-100'}`}
						on:click|stopPropagation={() => {
							toggleEmbeddedGifFavorite(embed.src);
						}}
					aria-label={embeddedGifFavorited
						? $i18n.t('Remove from favorites')
						: $i18n.t('Add to favorites')}
				>
					<Star
						className={`size-3.5 ${embeddedGifFavorited ? 'fill-yellow-400 text-yellow-500' : 'text-gray-500 dark:text-gray-300'}`}
						strokeWidth="2"
					/>
				</button>
			</div>
		</span>

		{#if showGifPreview}
			<div class="fixed inset-0 z-[9999] bg-black/95 text-white flex items-center justify-center">
				<button
					type="button"
					class="absolute inset-0 z-0"
					on:click={closeGifPreview}
					aria-label={$i18n.t('Close preview')}
				></button>

				<div class="absolute inset-x-0 top-0 z-20 flex items-center justify-between p-3 pointer-events-none">
					<button
						type="button"
						class="rounded-full bg-black/70 border border-white/20 p-2 pointer-events-auto"
						on:click|stopPropagation={closeGifPreview}
						aria-label={$i18n.t('Close')}
					>
						<XMark className="size-5" />
					</button>

					<button
						type="button"
						class="rounded-full bg-black/70 border border-white/20 p-2 pointer-events-auto"
						on:click|stopPropagation={() => {
							toggleEmbeddedGifFavorite(embed.src);
						}}
						aria-label={embeddedGifFavorited
							? $i18n.t('Remove from favorites')
							: $i18n.t('Add to favorites')}
					>
						<Star
							className={`size-5 ${embeddedGifFavorited ? 'fill-yellow-400 text-yellow-500' : 'text-gray-100'}`}
							strokeWidth="2"
						/>
					</button>
				</div>

					<img
						src={embed.src}
						alt={alt || 'Embedded GIF preview'}
						class="relative z-10 max-w-full max-h-full object-contain p-4"
						draggable="false"
					/>
			</div>
		{/if}
	{:else}
		<span class="block mt-2 max-w-full">
			<Image src={embed.src} alt={alt || 'Embedded image'} />
		</span>
	{/if}
	{:else if embed.kind === 'video'}
	<span class="block mt-2 max-w-full">
		<video
			src={embed.src}
			class="w-full max-h-[26rem] rounded-xl border border-gray-200 dark:border-gray-800 bg-black"
			controls
			playsinline
			preload="metadata"
		>
			<track kind="captions" />
		</video>
	</span>
{:else if embed.kind === 'audio'}
	<span class="block mt-2 max-w-full">
		<audio src={embed.src} class="w-full" controls preload="none">
			<track kind="captions" />
		</audio>
	</span>
{:else if embed.kind === 'youtube'}
	<span class="block mt-2 w-full max-w-full overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
		<iframe
			src={embed.src}
			title="YouTube embed"
			class="w-full aspect-video bg-black"
			loading="lazy"
			allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
			allowfullscreen
		></iframe>
	</span>
{:else if embed.kind === 'spotify'}
	<span class="block mt-2 w-full max-w-full overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
		<iframe
			src={embed.src}
			title="Spotify embed"
			class="w-full h-[352px] bg-transparent"
			loading="lazy"
			allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
		></iframe>
	</span>
{:else if embed.kind === 'soundcloud'}
	<span class="block mt-2 w-full max-w-full overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
		<iframe
			src={embed.src}
			title="SoundCloud embed"
			class="w-full h-[166px] bg-transparent"
			loading="lazy"
			allow="autoplay"
		></iframe>
	</span>
{/if}
