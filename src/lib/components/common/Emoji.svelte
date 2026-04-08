<script>
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { config, shortCodesToEmojis } from '$lib/stores';

	export let shortCode;
	export let className = 'size-4';

	const normalizeShortCode = (value) =>
		String(value ?? '')
			.trim()
			.replace(/^:+|:+$/g, '')
			.toLowerCase();

	$: normalizedShortCode = normalizeShortCode(shortCode);

	$: customEmoji =
		($config?.ui?.custom_emojis ?? []).find(
			(item) =>
				String(item?.name ?? '')
					.trim()
					.toLowerCase() === normalizedShortCode &&
				String(item?.data_url ?? '').startsWith('data:image/')
		) ?? null;

	$: standardEmojiCodepoint =
		$shortCodesToEmojis[normalizedShortCode] ?? $shortCodesToEmojis[String(shortCode ?? '')];
</script>

{#if customEmoji}
	<img src={customEmoji.data_url} alt={normalizedShortCode} class={className} loading="lazy" />
{:else if standardEmojiCodepoint}
	<img
		src="{WEBUI_BASE_URL}/assets/emojis/{standardEmojiCodepoint.toLowerCase()}.svg"
		alt={normalizedShortCode}
		class={className}
		loading="lazy"
	/>
{:else}
	<div>
		:{normalizedShortCode}:
	</div>
{/if}
