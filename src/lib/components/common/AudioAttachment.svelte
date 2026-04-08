<script lang="ts">
	import { formatFileSize } from '$lib/utils';

	export let src = '';
	export let name = '';
	export let size: number | null = null;
	export let contentType = '';

	const decodeString = (value: string) => {
		try {
			return decodeURIComponent(value);
		} catch {
			return value;
		}
	};
</script>

<div
	class="w-full min-w-[18rem] max-w-xl rounded-2xl border border-gray-200/70 bg-white/90 p-3 shadow-sm dark:border-gray-800/80 dark:bg-gray-900/80"
>
	<div class="mb-3 flex items-start gap-3">
		<div
			class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 24 24"
				fill="currentColor"
				class="size-5"
				aria-hidden="true"
			>
				<path
					d="M8.25 6.75A2.25 2.25 0 0 1 10.5 4.5h3A2.25 2.25 0 0 1 15.75 6.75v6.856a3.75 3.75 0 1 1-1.5-3.005V6.75a.75.75 0 0 0-.75-.75h-3a.75.75 0 0 0-.75.75v8.856a3.75 3.75 0 1 1-1.5-3.005V6.75Z"
				/>
			</svg>
		</div>

		<div class="min-w-0 flex-1">
			<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
				{decodeString(name) || 'Audio file'}
			</div>

			<div class="mt-0.5 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
				{#if size !== null}
					<span>{formatFileSize(size)}</span>
				{/if}

				{#if contentType}
					<span class="truncate">{contentType}</span>
				{/if}
			</div>
		</div>
	</div>

	<audio class="h-10 w-full" controls preload="metadata">
		<source {src} type={contentType || undefined} />
		Your browser does not support the audio tag.
	</audio>
</div>
