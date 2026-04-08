<script lang="ts">
	import DOMPurify from 'dompurify';
	import { toast } from 'svelte-sonner';

	import type { Token } from 'marked';
	import { getContext } from 'svelte';
	import { goto } from '$app/navigation';

	const i18n = getContext('i18n');

	import { WEBUI_BASE_URL } from '$lib/constants';
	import { copyToClipboard, unescapeHtml } from '$lib/utils';

	import KatexRenderer from './KatexRenderer.svelte';
	import Source from './Source.svelte';
	import HtmlToken from './HTMLToken.svelte';
	import TextToken from './MarkdownInlineTokens/TextToken.svelte';
	import CodespanToken from './MarkdownInlineTokens/CodespanToken.svelte';
	import MentionToken from './MarkdownInlineTokens/MentionToken.svelte';
	import NoteLinkToken from './MarkdownInlineTokens/NoteLinkToken.svelte';
	import LinkEmbed from './MarkdownInlineTokens/LinkEmbed.svelte';
	import SourceToken from './SourceToken.svelte';

	export let id: string;
	export let done = true;
	export let tokens: Token[];
	export let sourceIds: string[] = [];
	export let onSourceClick: Function = () => {};

	/**
	 * Check if a URL is a same-origin note link and return the note ID if so.
	 */
	const getNoteIdFromHref = (href: string): string | null => {
		try {
			const url = new URL(href, window.location.origin);
			if (url.origin === window.location.origin) {
				const match = url.pathname.match(/^\/notes\/([^/]+)$/);
				if (match) {
					return match[1];
				}
			}
		} catch {
			// Invalid URL
		}
		return null;
	};

	/**
	 * Handle link clicks - intercept same-origin app URLs for in-app navigation
	 */
	const handleLinkClick = (e: MouseEvent, href: string) => {
		try {
			const url = new URL(href, window.location.origin);
			// Check if same origin and an in-app route
			if (
				url.origin === window.location.origin &&
				(url.pathname.startsWith('/notes/') ||
					url.pathname.startsWith('/c/') ||
					url.pathname.startsWith('/channels/'))
			) {
				e.preventDefault();
				goto(url.pathname + url.search + url.hash);
			}
		} catch {
			// Invalid URL, let browser handle it
		}
	};

	const isWhitespaceOnlyTextToken = (token: Token) => {
		if (token.type !== 'text' && token.type !== 'escape') {
			return false;
		}

		return !String((token as { text?: string }).text ?? '').trim();
	};

	const isStandaloneLinkToken = (items: Token[], linkIndex: number) =>
		items.every((candidate, candidateIdx) => {
			if (candidateIdx === linkIndex) {
				return true;
			}

			if (candidate.type === 'br') {
				return true;
			}

			return isWhitespaceOnlyTextToken(candidate);
		});

	const IMAGE_LINK_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.avif', '.svg'];

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

	const isImageLikeHref = (href: string) => {
		const parsed = parseHttpUrl(href);
		const pathname = parsed?.pathname?.toLowerCase() ?? '';
		return IMAGE_LINK_EXTENSIONS.some((extension) => pathname.endsWith(extension));
	};

	const tokenContainsImage = (token: Token) =>
		token.type === 'link' && (token.tokens ?? []).some((item) => item.type === 'image');
</script>

{#each tokens as token, tokenIdx (tokenIdx)}
	{#if token.type === 'escape'}
		{unescapeHtml(token.text)}
	{:else if token.type === 'html'}
		<HtmlToken {id} {token} />
	{:else if token.type === 'link'}
		{@const noteId = getNoteIdFromHref(token.href)}
		{@const standaloneLink = isStandaloneLinkToken(tokens, tokenIdx)}
		{@const imageLikeLink = isImageLikeHref(token.href)}
		{@const renderImageWithoutAnchor =
			imageLikeLink && (standaloneLink || tokenContainsImage(token))}
		{#if noteId}
			<NoteLinkToken {noteId} href={token.href} />
		{:else if token.tokens}
			<span class="inline-block max-w-full">
				{#if renderImageWithoutAnchor}
					<svelte:self id={`${id}-a`} tokens={token.tokens} {onSourceClick} {done} />
				{:else}
					<a
						href={token.href}
						target="_blank"
						rel="nofollow"
						title={token.title}
						on:click={(e) => handleLinkClick(e, token.href)}
					>
						<svelte:self id={`${id}-a`} tokens={token.tokens} {onSourceClick} {done} />
					</a>
				{/if}
				{#if standaloneLink}
					<LinkEmbed href={token.href} />
				{/if}
			</span>
		{:else}
			<span class="inline-block max-w-full">
				{#if renderImageWithoutAnchor}
					<LinkEmbed href={token.href} />
				{:else}
					<a
						href={token.href}
						target="_blank"
						rel="nofollow"
						title={token.title}
						on:click={(e) => handleLinkClick(e, token.href)}>{token.text}</a
					>
					{#if standaloneLink}
						<LinkEmbed href={token.href} />
					{/if}
				{/if}
			</span>
		{/if}
	{:else if token.type === 'image'}
		<LinkEmbed href={token.href} alt={token.text} forceImage={true} />
	{:else if token.type === 'strong'}
		<strong><svelte:self id={`${id}-strong`} tokens={token.tokens} {onSourceClick} /></strong>
	{:else if token.type === 'em'}
		<em><svelte:self id={`${id}-em`} tokens={token.tokens} {onSourceClick} /></em>
	{:else if token.type === 'codespan'}
		<CodespanToken {token} {done} />
	{:else if token.type === 'br'}
		<br />
	{:else if token.type === 'del'}
		<del><svelte:self id={`${id}-del`} tokens={token.tokens} {onSourceClick} /></del>
	{:else if token.type === 'inlineKatex'}
		{#if token.text}
			<KatexRenderer content={token.text} displayMode={false} />
		{/if}
	{:else if token.type === 'iframe'}
		<iframe
			src="{WEBUI_BASE_URL}/api/v1/files/{token.fileId}/content"
			title={token.fileId}
			width="100%"
			frameborder="0"
			on:load={(e) => {
				try {
					const target = e.currentTarget as HTMLIFrameElement;
					const bodyHeight = target.contentWindow?.document.body.scrollHeight;
					if (bodyHeight) {
						target.style.height = `${bodyHeight + 20}px`;
					}
				} catch {}
			}}
		></iframe>
	{:else if token.type === 'mention'}
		<MentionToken {token} />
	{:else if token.type === 'footnote'}
		{@html DOMPurify.sanitize(
			`<sup class="footnote-ref footnote-ref-text">${token.escapedText}</sup>`
		) || ''}
	{:else if token.type === 'citation'}
		{#if (sourceIds ?? []).length > 0}
			<SourceToken {id} {token} {sourceIds} onClick={onSourceClick} />
		{:else}
			<TextToken {token} {done} />
		{/if}
	{:else if token.type === 'text'}
		<TextToken {token} {done} />
	{/if}
{/each}
