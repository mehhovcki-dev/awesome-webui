<script lang="ts">
	import { fade } from 'svelte/transition';
	import { config, shortCodesToEmojis } from '$lib/stores';
	import Emoji from '$lib/components/common/Emoji.svelte';

	export let token;
	export let done = true;

	let texts = [];
	$: texts = (token?.raw ?? '').split(' ');

	type TextPart =
		| {
				type: 'text';
				value: string;
		  }
		| {
				type: 'emoji';
				shortCode: string;
		  };

	const normalizeShortCode = (value: string) =>
		String(value ?? '')
			.trim()
			.replace(/^:+|:+$/g, '')
			.toLowerCase();

	const unicodeToCodepoint = (value: string) =>
		Array.from(value)
			.map((char) => char.codePointAt(0)?.toString(16).toUpperCase().padStart(4, '0'))
			.filter((part): part is string => Boolean(part))
			.join('-');

	const resolveShortCodeFromUnicode = (
		unicodeEmoji: string,
		codepointToShortCode: Record<string, string>
	) => {
		const codepoint = unicodeToCodepoint(unicodeEmoji);
		if (!codepoint) {
			return null;
		}

		const exact = codepointToShortCode[codepoint];
		if (exact) {
			return exact;
		}

		const withoutVariationSelectors = codepoint.replace(/-FE0E|-FE0F/g, '');
		return codepointToShortCode[withoutVariationSelectors] ?? null;
	};

	const emojiTokenRegex =
		/:([a-zA-Z0-9_+\-]+):|(?:\p{Regional_Indicator}{2}|[0-9#*]\uFE0F?\u20E3|\p{Extended_Pictographic}(?:\uFE0F|\uFE0E)?(?:\u200D\p{Extended_Pictographic}(?:\uFE0F|\uFE0E)?)*)/gu;

	let textParts: TextPart[] = [];

	$: {
		const raw = String(token?.raw ?? '');
		const parts: TextPart[] = [];
		const codepointToShortCode: Record<string, string> = {};
		const customShortCodes = new Set<string>();

		for (const customEmoji of Array.isArray($config?.ui?.custom_emojis) ? $config.ui.custom_emojis : []) {
			const shortCode = normalizeShortCode(customEmoji?.name ?? '');
			const dataUrl = String(customEmoji?.data_url ?? '').trim();
			if (shortCode && dataUrl.startsWith('data:image/')) {
				customShortCodes.add(shortCode);
			}
		}

		for (const [shortCode, codepoint] of Object.entries($shortCodesToEmojis ?? {})) {
			if (!codepointToShortCode[String(codepoint)]) {
				codepointToShortCode[String(codepoint)] = String(shortCode);
			}
		}

		let cursor = 0;
		emojiTokenRegex.lastIndex = 0;

		for (const match of raw.matchAll(emojiTokenRegex)) {
			const matchedValue = match[0] ?? '';
			const matchIndex = match.index ?? 0;

			if (matchIndex > cursor) {
				parts.push({
					type: 'text',
					value: raw.slice(cursor, matchIndex)
				});
			}

			const shortCodeMatch = match[1] ? normalizeShortCode(match[1]) : '';
			const resolvedShortCode =
				shortCodeMatch &&
				($shortCodesToEmojis[shortCodeMatch] || customShortCodes.has(shortCodeMatch))
					? shortCodeMatch
					: resolveShortCodeFromUnicode(matchedValue, codepointToShortCode);

			if (resolvedShortCode) {
				parts.push({
					type: 'emoji',
					shortCode: resolvedShortCode
				});
			} else {
				parts.push({
					type: 'text',
					value: matchedValue
				});
			}

			cursor = matchIndex + matchedValue.length;
		}

		if (cursor < raw.length) {
			parts.push({
				type: 'text',
				value: raw.slice(cursor)
			});
		}

		textParts = parts;
	}
</script>

{#if done}
	{#each textParts as part}
		{#if part.type === 'emoji'}
			<Emoji shortCode={part.shortCode} className="inline-block size-[1.1em] align-[-0.125em]" />
		{:else}
			{part.value}
		{/if}
	{/each}
{:else}
	{#each texts as text}
		<span class="" transition:fade={{ duration: 100 }}>
			{text}{' '}
		</span>
	{/each}
{/if}
